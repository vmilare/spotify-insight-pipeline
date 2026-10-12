"""Stage 4b - Group review: the 'group' model role (Claude Haiku 5.5) audits issue membership.

For each issue with members, a bounded, seeded sample of member quotes (with opaque keys) is sent with the
issue's rule. The model suggests a name/description and lists quotes that do not fit. Code computes a fit
rate per issue. Membership is NOT changed (code owns it, so ranking stays reproducible without a model).
Writes runs/analysis/<input>/issue_review.csv and group_review.json.
"""
import csv
import hashlib
import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from tools.check_submission import write_json

from . import claude, enrich, group, rates, store, verify
from .paths import REPO

PROMPT_VERSION = "group-review-v1"
SAMPLE_PER_ISSUE = 12
SCHEMA = {
    "type": "object",
    "properties": {"issues": {"type": "array", "items": {
        "type": "object",
        "properties": {"issue_id": {"type": "string"}, "suggested_name": {"type": "string"},
                       "description": {"type": "string"},
                       "misfit_keys": {"type": "array", "items": {"type": "string"}}},
        "required": ["issue_id", "suggested_name", "description", "misfit_keys"], "additionalProperties": False}}},
    "required": ["issues"], "additionalProperties": False,
}


def run(input_path, workspace="main"):
    settings = enrich.load_settings()
    folder = group.analysis_dir(input_path, workspace)
    records = {json.loads(l)["review_id"]: json.loads(l) for l in (folder / "enriched.jsonl").open(encoding="utf-8")}
    members = defaultdict(list)
    for row in csv.DictReader((folder / "membership.csv").open(encoding="utf-8")):
        members[row["issue_id"]].append(row["review_id"])
    issues = {r["issue_id"]: r for r in csv.DictReader((folder / "issues.csv").open(encoding="utf-8"))}
    system = (REPO / "prompts" / "group_review_v1.md").read_text(encoding="utf-8")
    run_id = f"{workspace}-{Path(input_path).stem}-groupreview-{datetime.now().strftime('%Y%m%dT%H%M%S%f')[:-3]}"
    gconf = f"{claude.HAIKU}+{PROMPT_VERSION}+effort-low+thinking-off"
    log, spent, results, keymaps, stats = [], {"usd": 0.0}, {}, {}, {"cache_hits": 0}
    cache = store.connect_cache(workspace)
    guard = verify.budget_guard(settings, spent)
    started, t0 = datetime.now(timezone.utc).isoformat(timespec="seconds"), time.monotonic()
    by_topic = defaultdict(list)
    for issue_id, ids in members.items():
        by_topic[issues[issue_id]["topic"]].append(issue_id)
    for topic in sorted(by_topic):  # one request per topic keeps each request small and bounded
        payload = []
        for issue_id in sorted(by_topic[topic]):
            ids = sorted(members[issue_id], key=lambda r: hashlib.sha256(f"{PROMPT_VERSION}:{r}".encode()).hexdigest())
            sample = ids[:SAMPLE_PER_ISSUE]
            keymaps[issue_id] = {f"{issue_id}#{n + 1}": rid for n, rid in enumerate(sample)}
            payload.append({"issue_id": issue_id, "current_name": issues[issue_id]["name"],
                            "rule_keywords": issues[issue_id]["keywords"] or "(none: catch-all for this topic)",
                            "member_quotes": [{"key": k, "quote": records[rid]["evidence_quote"][:220]}
                                              for k, rid in keymaps[issue_id].items()]})
        before = len(log)
        parsed, _ = claude.call_json(
            role="group", model=claude.HAIKU, system=system,
            user=f"Topic: {topic}\nIssues:\n" + json.dumps(payload, ensure_ascii=False), schema=SCHEMA,
            max_tokens=3000, effort="low", thinking={"type": "disabled"}, log=log, ledger=guard, cache=cache, stats=stats,
            meta={"run_id": run_id, "phase": "group", "label_config": gconf,
                  "review_ids": [rid for i in by_topic[topic] for rid in keymaps[i].values()]})
        spent["usd"] += sum(c.get("cost_usd", 0) for c in log[before:])
        for item in (parsed or {}).get("issues", []):
            if item["issue_id"] in keymaps:
                results[item["issue_id"]] = item

    rows = []
    for issue_id in sorted(members):
        r = results.get(issue_id)
        sampled = len(keymaps.get(issue_id, {}))
        misfits = [k for k in (r or {}).get("misfit_keys", []) if k in keymaps.get(issue_id, {})]
        rows.append({"issue_id": issue_id, "topic": issues[issue_id]["topic"], "name": issues[issue_id]["name"],
                     "members": len(members[issue_id]), "sampled": sampled, "reviewed": r is not None,
                     "misfits": len(misfits), "fit_rate": round(1 - len(misfits) / sampled, 3) if r and sampled else "",
                     "misfit_review_ids": "|".join(keymaps[issue_id][k] for k in misfits),
                     "model_suggested_name": (r or {}).get("suggested_name", ""),
                     "model_description": (r or {}).get("description", "")})
    with (folder / "issue_review.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    tokens = {k: sum(c.get(k, 0) or 0 for c in log) for k in rates.ITEMS}
    reviewed = [r for r in rows if r["reviewed"]]
    summary = {"run_id": run_id, "config": gconf, "issues_reviewed": len(reviewed), "issues_total": len(rows),
               "sampled_quotes": sum(r["sampled"] for r in reviewed), "misfits": sum(r["misfits"] for r in reviewed),
               "stage_cache_hits": stats["cache_hits"], "requests": len(log), "failed_attempts": sum(c["outcome"] == "failed" for c in log),
               "usage": tokens, "cost_usd": round(spent["usd"], 6), "wall_clock_seconds": round(time.monotonic() - t0, 2),
               "note": "Membership unchanged; fit rates are a quality signal for the keyword rules."}
    write_json(folder / "group_review.json", summary)
    with (folder / "group_review_calls.jsonl").open("a", encoding="utf-8") as f:
        for c in log:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    enrich.append_ledger({"run_id": run_id, "input": Path(input_path).name, "label_config": gconf, "started_at": started,
                          "ended_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "requests": len(log),
                          "failed_requests": summary["failed_attempts"], "input_tokens": tokens["input_tokens"],
                          "cost_usd": summary["cost_usd"], "texts_labeled": 0, "reviews_completed": 0,
                          "cache_hit_reviews": 0, "stop_reason": "complete"})
    return summary
