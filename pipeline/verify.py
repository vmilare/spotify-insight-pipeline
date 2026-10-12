"""Stage 3 - Verify: an independent model role re-labels a declared random sample, blind to Jev.

Claude Haiku 5.5 receives only the review texts (under opaque keys) and the shared rubric, never the
first prediction. Code compares the two label sets, writes a disagreement report, and runs a
planted-error test on a separate copy of the first predictions (synthetic; never used in business results).
Outputs go to runs/analysis/<input>/verify/.
"""
import csv
import hashlib
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

from tools.check_submission import INTENTS, TOPICS, sha, write_json

from . import claude, enrich, group, rates, store
from .paths import CONFIG_DIR, REPO

PROMPT_VERSION = "verify-v1"
SEED = "verify-sample-v1"
FIELDS = ("topic", "intent", "severity", "sentiment")


def rubric_text():
    L = yaml.safe_load((CONFIG_DIR / "labels.yaml").read_text(encoding="utf-8"))
    lines = ["TOPIC (" + L["topic"]["rule"] + ")"]
    for k, v in L["topic"]["options"].items():
        notes = " ".join(v.get("notes", []))
        lines.append(f"- {k}: {v['definition']}. {notes}".rstrip())
    lines.append("\nINTENT (" + L["intent"]["rule"] + ")")
    for k, v in L["intent"]["options"].items():
        lines.append(f"- {k}: {v['definition']}. {' '.join(v.get('notes', []))}".rstrip())
    lines.append("\nSEVERITY (" + L["severity"]["rule"] + ")")
    for k, v in L["severity"]["levels"].items():
        lines.append(f"- {k}: {v}")
    lines.append("\nClassify the review text itself; ignore star ratings and other metadata.")
    return "\n".join(lines)


SCHEMA = {
    "type": "object",
    "properties": {"labels": {"type": "array", "items": {
        "type": "object",
        "properties": {"key": {"type": "string"}, "topic": {"type": "string", "enum": list(TOPICS)},
                       "intent": {"type": "string", "enum": list(INTENTS)},
                       "severity": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
                       "sentiment": {"type": "number"}},
        "required": ["key", "topic", "intent", "severity", "sentiment"], "additionalProperties": False}}},
    "required": ["labels"], "additionalProperties": False,
}


def verify_config(settings):
    v = settings["verify"]
    return f"{claude.HAIKU}+{PROMPT_VERSION}+effort-{v['effort']}+thinking-off"


def budget_guard(settings, spent):
    prior = enrich.project_spend()
    cap = settings["budget"]["project_cap_usd"]
    return lambda est: prior + spent["usd"] + est <= cap


def run(input_path, workspace="main", sample_size=None):
    settings = enrich.load_settings()
    v = settings["verify"]
    input_path = Path(input_path)
    file_sha = sha(input_path)
    config = enrich.label_config(settings)
    conn = store.connect(file_sha, workspace)
    rows = conn.execute("""SELECT res.record_json, r.review_text FROM results res JOIN reviews r USING (review_id)
                           WHERE res.label_config=?""", (config,)).fetchall()
    # Sample only records that came from a model call (not exact-text cache copies), in a seeded hash order.
    originals = [(json.loads(rj), t) for rj, t in rows if "cache_source_id" not in json.loads(rj)]
    originals.sort(key=lambda x: hashlib.sha256(f"{SEED}:{x[0]['review_id']}".encode()).hexdigest())
    n = min(sample_size or v["sample_size"], len(originals))
    sample = originals[:n]
    out = group.analysis_dir(input_path) / "verify"
    out.mkdir(parents=True, exist_ok=True)
    run_id = f"{workspace}-{input_path.stem}-verify-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    vconf = verify_config(settings)
    system = (REPO / "prompts" / "verify_v1.md").read_text(encoding="utf-8").replace("{rubric}", rubric_text())
    log, spent, preds = [], {"usd": 0.0}, {}
    guard = budget_guard(settings, spent)
    started, t0 = datetime.now(timezone.utc).isoformat(timespec="seconds"), time.monotonic()
    batch = v["reviews_per_request"]
    for i in range(0, n, batch):
        group_rows = sample[i:i + batch]
        keys = {f"k{j + 1}": rec["review_id"] for j, (rec, _) in enumerate(group_rows)}
        user = json.dumps([{"key": k, "review": t} for k, (_, t) in zip(keys, group_rows)], ensure_ascii=False)
        before = len(log)
        parsed, _ = claude.call_json(
            role="verify", model=claude.HAIKU, system=system, user="Label these reviews:\n" + user, schema=SCHEMA,
            max_tokens=v["max_tokens"], effort=v["effort"], thinking={"type": "disabled"}, log=log,
            meta={"run_id": run_id, "phase": "verify", "label_config": vconf, "review_ids": list(keys.values())},
            ledger=guard)
        spent["usd"] += sum(c.get("cost_usd", 0) for c in log[before:])
        for item in (parsed or {}).get("labels", []):
            rid = keys.get(item["key"])
            if rid is None or rid in preds:
                continue  # unknown or duplicate key: ignored and counted below
            if item["topic"] in TOPICS and item["intent"] in INTENTS and item["severity"] in range(1, 6) \
                    and -1 <= item["sentiment"] <= 1:
                preds[rid] = {k: item[k] for k in FIELDS}

    # Compare (code owns the comparison).
    first = {rec["review_id"]: rec for rec, _ in sample}
    text = {rec["review_id"]: t for rec, t in sample}
    both = [rid for rid in first if rid in preds]
    def agree(f):
        return sum(first[r][f] == preds[r][f] for r in both)
    sev_err = [abs(first[r]["severity"] - preds[r]["severity"]) for r in both]
    report = {
        "run_id": run_id, "input": input_path.name, "first_label_config": config, "verifier_config": vconf,
        "sample": {"declared_size": sample_size or v["sample_size"], "drawn": n,
                   "method": f"records with a model call, sorted by SHA-256('{SEED}:review_id'), first N"},
        "verified": len(both), "missing_verifier_labels": n - len(both),
        "agreement": {"topic": agree("topic"), "intent": agree("intent"),
                      "severity_exact": sum(e == 0 for e in sev_err), "severity_within_1": sum(e <= 1 for e in sev_err),
                      "severity_mae": round(sum(sev_err) / len(both), 3) if both else None,
                      "sentiment_mae": round(sum(abs(first[r]["sentiment"] - preds[r]["sentiment"]) for r in both) / len(both), 3) if both else None},
        "topic_confusion(first->verifier)": Counter(f"{first[r]['topic']}->{preds[r]['topic']}" for r in both
                                                    if first[r]["topic"] != preds[r]["topic"]).most_common(),
        "intent_confusion(first->verifier)": Counter(f"{first[r]['intent']}->{preds[r]['intent']}" for r in both
                                                     if first[r]["intent"] != preds[r]["intent"]).most_common(),
    }
    # Planted-error test (synthetic copy): every 5th verified record gets a deliberately wrong topic.
    planted = both[::5]
    caught = 0
    planted_rows = []
    for r in planted:
        wrong = TOPICS[(TOPICS.index(first[r]["topic"]) + 3) % len(TOPICS)]
        hit = preds[r]["topic"] != wrong
        caught += hit
        planted_rows.append({"review_id": r, "original_topic": first[r]["topic"], "planted_topic": wrong,
                             "verifier_topic": preds[r]["topic"], "caught": hit})
    report["planted_error_test"] = {"synthetic": True, "planted": len(planted), "caught_by_comparison": caught,
                                    "rule": "every 5th verified record's topic replaced by TOPICS[(i+3) % 8] in a test copy"}
    with (out / "planted_errors.jsonl").open("w", encoding="utf-8") as f:
        for row in planted_rows:
            f.write(json.dumps(row) + "\n")
    with (out / "verifier_predictions.jsonl").open("w", encoding="utf-8") as f:
        for r in first:
            f.write(json.dumps({"review_id": r, "verifier": preds.get(r)}) + "\n")
    with (out / "disagreements.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["review_id", "fields_disagree", "jev_topic", "verifier_topic", "jev_intent", "verifier_intent",
                    "jev_severity", "verifier_severity", "needs_review", "text"])
        for r in both:
            diff = [k for k in ("topic", "intent", "severity") if first[r][k] != preds[r][k]]
            if diff:
                w.writerow([r, "|".join(diff), first[r]["topic"], preds[r]["topic"], first[r]["intent"],
                            preds[r]["intent"], first[r]["severity"], preds[r]["severity"], first[r]["needs_review"],
                            text[r][:300]])
    # needs_review as a predictor of disagreement.
    flagged = [r for r in both if first[r]["needs_review"]]
    def dis(rs):
        return sum(any(first[r][k] != preds[r][k] for k in ("topic", "intent")) for r in rs)
    report["needs_review_vs_disagreement"] = {
        "flagged": len(flagged), "flagged_with_topic_or_intent_disagreement": dis(flagged),
        "unflagged": len(both) - len(flagged), "unflagged_with_topic_or_intent_disagreement": dis([r for r in both if r not in set(flagged)])}

    tokens = {k: sum(c.get(k, 0) or 0 for c in log) for k in rates.ITEMS}
    report.update({"requests": len(log), "failed_attempts": sum(c["outcome"] == "failed" for c in log),
                   "usage": tokens, "cost_usd": round(spent["usd"], 6),
                   "wall_clock_seconds": round(time.monotonic() - t0, 2)})
    write_json(out / "verify_report.json", report)
    with (out / "calls.jsonl").open("a", encoding="utf-8") as f:
        for c in log:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    with conn:
        for c in log:
            conn.execute("INSERT OR REPLACE INTO calls VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                c["request_id"], run_id, "verify", "verify", vconf, c["model"], json.dumps(c["review_ids"]),
                c["attempt"], c["outcome"], c.get("http_status"), c.get("input_tokens"), c.get("output_tokens"),
                c.get("cost_usd"), c["started_at"], c["seconds"], c.get("error")))
    conn.close()
    enrich.append_ledger({"run_id": run_id, "input": input_path.name, "label_config": vconf, "started_at": started,
                          "ended_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "requests": len(log),
                          "failed_requests": report["failed_attempts"], "input_tokens": tokens["input_tokens"],
                          "cost_usd": report["cost_usd"], "texts_labeled": len(both), "reviews_completed": 0,
                          "cache_hit_reviews": 0, "stop_reason": "complete"})
    return report
