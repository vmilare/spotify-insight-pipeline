"""Stage 6 - Recommend: the memo role (Claude Sonnet 5.5, effort high) writes the decision memo from a
bounded evidence pack built by code; code checks every claim, review ID and number before saving.

Inputs: only saved files in runs/analysis/<input>/ (+ quote metadata from the state DB).
Outputs: evidence_pack.json, memo_output.json (validated model output), memo.md (rendered by code with
appendix tables), claims.csv, memo_quantities.csv, recommendations.json, memo_check.json, memo_calls.jsonl
"""
import csv
import hashlib
import json
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from tools.check_submission import sha, write_json

import yaml

from . import claude, enrich, group, rates, store, verify
from .rank import mean6
from .paths import REPO

PROMPT_VERSION = "memo-v5"  # v2: per-issue/area verification; v3: monthly trend; v4: baseline ranking basis + sourced
# quantities; v5: leadership decision criteria (config/decision_criteria.yaml), up to two recommended areas
METRICS = ("complaint_count", "severity_sum", "mean_severity", "priority_score")
AREAS = {"access": ["access"], "usability": ["usability"], "playback": ["playback", "downloads"],
         "billing_support": ["billing", "support"], "catalog": ["catalog"], "other": ["other"]}
AREA_LABELS = {"playback": "playback (incl. downloads)", "billing_support": "billing/support",
               "other": "other (general dissatisfaction)"}
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
NUMBER = re.compile(r"(?<![A-Za-z#])\d[\d,]*(?:\.\d+)?")
DATE = re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?\b")
PATH_PART = re.compile(r"\[([^=\]]+)=([^\]]+)\]|\[(\d+)\]|([^.\[\]]+)")

SCHEMA = {
    "type": "object",
    "properties": {
        "recommended_areas": {"type": "array", "items": {"type": "string",
                              "enum": ["access", "usability", "playback", "billing_support"]}},
        "headline": {"type": "string"},
        "memo_markdown": {"type": "string"},
        "claims": {"type": "array", "items": {"type": "object", "properties": {
            "claim_id": {"type": "string"}, "issue_id": {"type": "string"},
            "metric": {"type": "string", "enum": list(METRICS)}, "value": {"type": "string"}},
            "required": ["claim_id", "issue_id", "metric", "value"], "additionalProperties": False}},
        "other_quantities": {"type": "array", "items": {"type": "object", "properties": {
            "value": {"type": "string"}, "meaning": {"type": "string"}, "pack_path": {"type": "string"}},
            "required": ["value", "meaning", "pack_path"], "additionalProperties": False}},
        "recommendations": {"type": "array", "items": {"type": "object", "properties": {
            "title": {"type": "string"}, "rationale": {"type": "string"},
            "claim_ids": {"type": "array", "items": {"type": "string"}},
            "review_ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["title", "rationale", "claim_ids", "review_ids"], "additionalProperties": False}},
    },
    "required": ["recommended_areas", "headline", "memo_markdown", "claims", "other_quantities", "recommendations"],
    "additionalProperties": False,
}


def read_csv(path):
    with Path(path).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def pct(a, b):
    return round(100 * a / b, 1) if b else 0.0


def verification_breakdown(folder, records, membership):
    """Verifier vs Jev topic agreement inside the random verify sample, per top issue and per product area.
    Small per-issue samples: counts are reported so the reader can judge them."""
    issue_of = {rid: iid for iid, ids in membership.items() for rid in ids}
    area_of = {t: a for a, ts in AREAS.items() for t in ts}
    per_issue, per_area = defaultdict(lambda: {"sampled": 0, "topic_agree": 0, "verifier_other_topics": defaultdict(int)}), \
        defaultdict(lambda: {"sampled_complaints": 0, "verifier_same_area": 0, "verifier_other_areas": defaultdict(int)})
    for line in (folder / "verify" / "verifier_predictions.jsonl").open(encoding="utf-8"):
        row = json.loads(line)
        rid, v = row["review_id"], row["verifier"]
        if not v or rid not in issue_of:
            continue
        rec = records[rid]
        pi = per_issue[issue_of[rid]]
        pi["sampled"] += 1
        pi["topic_agree"] += v["topic"] == rec["topic"]
        if v["topic"] != rec["topic"]:
            pi["verifier_other_topics"][v["topic"]] += 1
        pa = per_area[area_of[rec["topic"]]]
        pa["sampled_complaints"] += 1
        if area_of[v["topic"]] == area_of[rec["topic"]]:
            pa["verifier_same_area"] += 1
        else:
            pa["verifier_other_areas"][area_of[v["topic"]]] += 1
    top = sorted(per_issue.items(), key=lambda x: -x[1]["sampled"])[:10]
    return {"by_issue_in_sample": {k: {**d, "verifier_other_topics": dict(d["verifier_other_topics"])} for k, d in top},
            "by_area_in_sample": {k: {**d, "verifier_other_areas": dict(d["verifier_other_areas"])} for k, d in per_area.items()},
            "breakdown_note": "complaint/cancellation records of the random verify sample, grouped by Jev's issue/area; "
                              "per-issue samples are small (see 'sampled')"}


def monthly_trend(records, membership, meta):
    """Per month: classified reviews and each area's complaint+cancellation count and share of all classified reviews.
    The first (2022-05) and last (2023-11) months are partial."""
    area_of = {t: a for a, ts in AREAS.items() for t in ts}
    member = {rid for ids in membership.values() for rid in ids}
    totals, counts = defaultdict(int), defaultdict(lambda: defaultdict(int))
    for rid, rec in records.items():
        month = meta[rid][1][:7]
        totals[month] += 1
        if rid in member:
            counts[month][area_of[rec["topic"]]] += 1
    months = sorted(totals)
    rows = []
    for m in months:
        rows.append({"month": m, "partial_month": m in (months[0], months[-1]), "classified_reviews": totals[m],
                     **{f"{a}_complaints": counts[m][a] for a in ("access", "usability", "playback", "billing_support")},
                     **{f"{a}_share_pct": pct(counts[m][a], totals[m]) for a in ("access", "usability", "playback", "billing_support")}})
    return {"rows": rows, "note": "share = area complaint+cancellation records / all classified reviews that month; "
                                  "first and last months are partial"}


def build_pack(input_path, workspace="main", top_n=10, quotes_per_issue=3):
    folder = group.analysis_dir(input_path, workspace)
    records = {json.loads(l)["review_id"]: json.loads(l) for l in (folder / "enriched.jsonl").open(encoding="utf-8")}
    ranking = read_csv(folder / "ranking.csv")
    actionable = read_csv(folder / "ranking_actionable.csv")
    sens = read_csv(folder / "ranking_without_needs_review.csv")
    aggregates = {r["issue_id"]: r for r in read_csv(folder / "aggregates.csv")}
    review = {r["issue_id"]: r for r in read_csv(folder / "issue_review.csv")} if (folder / "issue_review.csv").exists() else {}
    membership = defaultdict(list)
    for row in read_csv(folder / "membership.csv"):
        membership[row["issue_id"]].append(row["review_id"])
    manifest = json.loads((folder / "group_manifest.json").read_text(encoding="utf-8"))
    conn = store.connect(sha(Path(input_path)), workspace)
    meta = {rid: (likes, ts) for rid, likes, ts in conn.execute("SELECT review_id, review_likes, review_timestamp FROM reviews")}
    trend = monthly_trend(records, membership, meta)
    status = dict(conn.execute("SELECT status, COUNT(*) FROM record_status GROUP BY status"))
    conn.close()
    total_rows = sum(status.values())
    baseline = int(manifest["baseline_records(complaint+cancellation)"])
    completed = len(records)
    needs_review = sum(r["needs_review"] for r in records.values())

    topic_totals = defaultdict(lambda: [0, 0, 0])
    for a in aggregates.values():
        t = topic_totals[a["topic"]]
        t[0] += int(a["complaint_count"]); t[1] += int(a["severity_sum"]); t[2] += int(a["cancellation_count"])
    area_rollup = []
    for area, topics in AREAS.items():
        c = sum(topic_totals[t][0] for t in topics); s = sum(topic_totals[t][1] for t in topics)
        area_rollup.append({"area": area, "label": AREA_LABELS.get(area, area), "topics": topics,
                            "complaint_count": c, "severity_sum": s, "mean_severity": mean6(s, c) if c else "",
                            "share_of_baseline_complaints_pct": pct(c, baseline),
                            "cancellation_count": sum(topic_totals[t][2] for t in topics)})
    area_rollup.sort(key=lambda x: -x["severity_sum"])

    def quotes(issue_id):
        ids = sorted(membership[issue_id], key=lambda r: (-records[r]["severity"], -int(meta[r][0] or 0),
                                                          hashlib.sha256(r.encode()).hexdigest()))
        return [{"review_id": r, "severity": records[r]["severity"], "intent": records[r]["intent"],
                 "helpful_votes": int(meta[r][0] or 0), "date": meta[r][1][:10],
                 "quote": records[r]["evidence_quote"][:240]} for r in ids[:quotes_per_issue]]

    def issue_card(row):
        a, rv = aggregates[row["issue_id"]], review.get(row["issue_id"], {})
        return {**{k: row[k] for k in ("rank", "issue_id", "complaint_count", "severity_sum", "mean_severity", "priority_score")},
                "topic": a["topic"], "name": a["name"], "model_description": rv.get("model_description", ""),
                "share_of_baseline_complaints_pct": pct(int(row["complaint_count"]), baseline),
                "cancellation_count": int(a["cancellation_count"]), "needs_review_count": int(a["needs_review_count"]),
                "severity_counts": {s: int(a[f"severity_{s}"]) for s in range(1, 6)},
                "membership_fit_rate_in_sample": rv.get("fit_rate", ""), "quotes": quotes(row["issue_id"])}

    vr = folder / "verify" / "verify_report.json"
    verification = None
    if vr.exists():
        v = json.loads(vr.read_text(encoding="utf-8"))
        verification = {"sample_size": v["verified"], "topic_agreement": v["agreement"]["topic"],
                        "intent_agreement": v["agreement"]["intent"], "severity_exact_agreement": v["agreement"]["severity_exact"],
                        "note": "independent model re-label (blind); agreement counts out of sample_size"}
        verification.update(verification_breakdown(folder, records, membership))
    criteria_file = REPO / "config" / "decision_criteria.yaml"
    criteria = yaml.safe_load(criteria_file.read_text(encoding="utf-8")) if criteria_file.exists() else None
    pack = {
        "question": "Where should the next quarter of product effort go: access, usability, playback, or billing/support?",
        "scope": {"input": Path(input_path).name, "source_rows": total_rows, "completed_classifications": completed,
                  "quarantined": status.get("quarantined", 0), "pending_unclassified": status.get("pending", 0),
                  "baseline_complaint_and_cancellation_records": baseline,
                  "needs_review_records": needs_review,
                  "needs_review_share_of_all_classified_pct": pct(needs_review, completed),
                  "issues_in_baseline_ranking": len(ranking),
                  "highest_mean_severity_issue_in_full_ranking": max(
                      ({"issue_id": r["issue_id"], "mean_severity": r["mean_severity"], "baseline_rank": r["rank"]}
                       for r in ranking), key=lambda x: float(x["mean_severity"])),
                  "first_review_date": min(m[1] for m in meta.values())[:10],
                  "last_review_date": max(m[1] for m in meta.values())[:10]},
        "definitions": {"priority_score": "severity_sum = complaint_count x mean_severity (required baseline)",
                        "severity": "1 no problem ... 4 core task blocked, 5 explicit financial/privacy/data harm",
                        "area_mapping": "playback area includes downloads (offline playback); billing/support = billing + support topics",
                        "ranking_views": {
                            "baseline": "required ranking (grading contract): every complaint/cancellation record, incl. OTH-GENERAL",
                            "actionable": "additional view: the baseline with only OTH-GENERAL removed (no specific defect); "
                                          "other issues keep identical numbers and order",
                            "without_needs_review": "sensitivity check: recomputed after dropping records flagged needs_review"}},
        "area_rollup": area_rollup,
        **({"decision_criteria": criteria} if criteria else {}),
        "ranking_baseline_top10": ranking[:10],
        "ranking_actionable_top10 (excludes OTH-GENERAL)": actionable[:10],
        "ranking_without_needs_review_top5": sens[:5],
        "top_actionable_issues": [issue_card(r) for r in actionable[:top_n]],
        "verification": verification,
        "monthly_complaint_share": trend,
        "limitations": [
            "Google Play reviews are self-selected and historical; no revenue, plan tier or confirmed churn data.",
            "Labels come from a classifier (Jev) without human review of every record; needs_review flags uncertain labels.",
            "Non-English reviews were classified without translation and flagged needs_review.",
            "Issue membership uses keyword rules within each classified topic; fit rates come from a sampled model audit.",
        ],
    }
    write_json(folder / "evidence_pack.json", pack)
    return pack, ranking


def resolve(pack, path):
    """Value at a pack path such as area_rollup[area=playback].severity_sum or rows[0].x; KeyError if absent."""
    cur = pack
    for field, match, index, key in PATH_PART.findall(path):
        if key:
            cur = cur[key]
        elif index:
            cur = cur[int(index)]
        else:
            cur = next((x for x in cur if isinstance(x, dict) and str(x.get(field)) == match), None)
            if cur is None:
                raise KeyError(f"[{field}={match}]")
    return cur


def same_number(a, b):
    try:
        return float(str(a).replace(",", "")) == float(str(b).replace(",", ""))
    except ValueError:
        return False


def check(out, pack, ranking):
    errors, warnings = [], []
    rank_by_id = {r["issue_id"]: r for r in ranking}
    claim_ids = []
    for c in out["claims"]:
        claim_ids.append(c["claim_id"])
        r = rank_by_id.get(c["issue_id"])
        if not r:
            errors.append(f"{c['claim_id']}: unknown issue_id {c['issue_id']}")
        elif str(r[c["metric"]]) != str(c["value"]).strip():
            errors.append(f"{c['claim_id']}: {c['issue_id']} {c['metric']} is {r[c['metric']]}, claim says {c['value']}")
    if len(set(claim_ids)) != len(claim_ids):
        errors.append("duplicate claim_id")
    text = out["memo_markdown"]
    cited = set(re.findall(r"\[(C\d+)\]", text))
    errors += [f"cited {c} has no claim" for c in sorted(cited - set(claim_ids))]
    warnings += [f"claim {c} never cited in memo" for c in claim_ids if c not in cited]
    pack_ids = {q["review_id"] for card in pack["top_actionable_issues"] for q in card["quotes"]}
    used_ids = set(UUID.findall(text)) | {r for rec in out["recommendations"] for r in rec["review_ids"]}
    errors += [f"review id not in evidence pack: {r}" for r in sorted(used_ids - pack_ids)]
    for rec in out["recommendations"]:
        errors += [f"recommendation cites unknown claim {c}" for c in rec["claim_ids"] if c not in claim_ids]
    # Leadership direction: the recommended areas must be exactly the declared focus areas.
    focus = (pack.get("decision_criteria") or {}).get("focus_areas")
    if not out["recommended_areas"] or len(out["recommended_areas"]) > 2 or len(set(out["recommended_areas"])) != len(out["recommended_areas"]):
        errors.append("recommended_areas must list one or two distinct areas")
    elif focus and set(out["recommended_areas"]) != set(focus):
        errors.append(f"recommended_areas {out['recommended_areas']} must match decision_criteria.focus_areas {focus}")
    # The required baseline must be represented: its rank-1 issue named in the prose and backed by a claim.
    top = ranking[0]["issue_id"]
    if top not in text or not any(c["issue_id"] == top for c in out["claims"]):
        errors.append(f"baseline rank-1 issue {top} must be named in the memo and backed by a claim")
    # Non-ranking quantities: each listed path must resolve in the pack to the stated value.
    sourced = set()
    for q in out["other_quantities"]:
        try:
            found = resolve(pack, q["pack_path"])
        except (KeyError, IndexError, TypeError, ValueError):
            errors.append(f"other_quantities: path not in evidence pack: {q['pack_path']}")
            continue
        if not same_number(found, q["value"]):
            errors.append(f"other_quantities: {q['pack_path']} is {found}, memo says {q['value']}")
        else:
            sourced.add(q["value"].replace(",", ""))
    # Every number in the prose must be a claim value, a sourced quantity, or a small ordinal (dates excluded).
    allowed = sourced | {str(c["value"]) for c in out["claims"]} | {str(i) for i in range(0, 11)}
    stripped = DATE.sub(" ", UUID.sub(" ", re.sub(r"\[C\d+\]", " ", text)))
    for n in NUMBER.findall(stripped):
        v = n.replace(",", "").rstrip(".")
        if not any(v == a or same_number(v, a) for a in allowed):
            errors.append(f"number not backed by a claim or other_quantities entry: {n}")
    return errors, warnings


def appendix(out, ranking, actionable, topics, topics_all):
    """Code-built tables: the required baseline ranking, the ranking by specific topic, the claims, and the sourced
    non-ranking quantities."""
    act_rank = {r["issue_id"]: r["rank"] for r in actionable}
    lines = ["## Appendix A: required baseline ranking (top 10 of "
             f"{len(ranking)}, from `ranking.csv`)", "",
             "Priority score = severity sum = complaint count × mean severity. The actionable view removes only "
             "OTH-GENERAL; every other issue keeps the same numbers.", "",
             "| Baseline rank | Issue | Complaints | Severity sum | Mean severity | Priority score | Actionable rank |",
             "|---|---|---|---|---|---|---|"]
    lines += [f"| {r['rank']} | {r['issue_id']} | {r['complaint_count']} | {r['severity_sum']} | {r['mean_severity']} | "
              f"{r['priority_score']} | {act_rank.get(r['issue_id'], '— (excluded)')} |" for r in ranking[:10]]
    excluded = [t for t in topics_all if t["topic"] not in {x["topic"] for x in topics}]
    lines += ["", f"## Appendix B: ranking by topic, specific topics only ({len(topics)} of {len(topics_all)} contract "
              "topics, from `ranking_topics_actionable.csv`)", "",
              "The same baseline arithmetic and tie rule as Appendix A, with every issue's complaints summed into its topic. "
              "The memo's product areas combine playback with downloads and billing with support.", ""]
    lines += [f"Excluded: **{t['topic']}** (general praise or criticism, boycott posts, no specific product topic; "
              f"{t['issues']} issues, {t['complaint_count']} complaints, priority score {t['priority_score']}), which would "
              f"rank {t['rank']} in the full topic ranking (`ranking_topics.csv`)." for t in excluded]
    lines += ["",
              "| Rank | Topic | Issues | Complaints | Severity sum | Mean severity | Priority score |",
              "|---|---|---|---|---|---|---|"]
    lines += [f"| {t['rank']} | {t['topic']} | {t['issues']} | {t['complaint_count']} | {t['severity_sum']} | "
              f"{t['mean_severity']} | {t['priority_score']} |" for t in topics]
    lines += ["", "## Appendix C: claims (checked against `ranking.csv`; exported as `claims.csv`)", "",
              "| Claim | Issue | Metric | Value |", "|---|---|---|---|"]
    lines += [f"| {c['claim_id']} | {c['issue_id']} | {c['metric']} | {c['value']} |" for c in out["claims"]]
    lines += ["", "## Appendix D: other quantities (not ranking metrics; each checked against `evidence_pack.json`)", "",
              "| Value | Meaning | Evidence-pack field |", "|---|---|---|"]
    lines += [f"| {q['value']} | {q['meaning']} | `{q['pack_path']}` |" for q in out["other_quantities"]]
    return "\n".join(lines)


def render(input_path, workspace="main"):
    """Write memo.md from the saved model output (memo_output.json), memo_check.json and the saved rankings.
    Code only: re-rendering after a rerank or an appendix change makes no model call."""
    folder = group.analysis_dir(Path(input_path), workspace)
    saved = json.loads((folder / "memo_output.json").read_text(encoding="utf-8"))
    out, status = saved["output"], json.loads((folder / "memo_check.json").read_text(encoding="utf-8"))["status"]
    areas = out.get("recommended_areas") or [out["recommended_area"]]
    scope = json.loads((folder / "evidence_pack.json").read_text(encoding="utf-8"))["scope"]
    header = (f"# Decision memo: {out['headline']}\n\n"
              f"*Recommended {'areas' if len(areas) > 1 else 'area'}: **{' + '.join(AREA_LABELS.get(a, a) for a in areas)}**"
              f"{' (leadership direction: `config/decision_criteria.yaml`)' if saved.get('decision_criteria') else ''}"
              f" · Generated by `{saved['served_model']}` "
              f"(effort high) from `evidence_pack.json` · Checker: **{status}** · Input `{Path(input_path).name}` · "
              f"{scope['completed_classifications']} classified reviews, {scope['pending_unclassified']} unclassified.*\n\n")
    tables = appendix(out, read_csv(folder / "ranking.csv"), read_csv(folder / "ranking_actionable.csv"),
                      read_csv(folder / "ranking_topics_actionable.csv"), read_csv(folder / "ranking_topics.csv"))
    (folder / "memo.md").write_text(header + out["memo_markdown"].strip() + "\n\n" + tables + "\n", encoding="utf-8")
    return {"memo": str(folder / "memo.md"), "run_id": saved["run_id"], "check_status": status}


def run(input_path, workspace="main", phase="memo"):
    settings = enrich.load_settings()
    input_path = Path(input_path)
    folder = group.analysis_dir(input_path, workspace)
    pack, ranking = build_pack(input_path, workspace)
    system = (REPO / "prompts" / f"{PROMPT_VERSION.replace('-', '_')}.md").read_text(encoding="utf-8")
    run_id = f"{workspace}-{input_path.stem}-memo-{datetime.now().strftime('%Y%m%dT%H%M%S%f')[:-3]}"
    mconf = f"{claude.SONNET}+{PROMPT_VERSION}+effort-high+fallbacks-default"
    log, spent, stats = [], {"usd": 0.0}, {"cache_hits": 0}
    cache = store.connect_cache(workspace)
    guard = verify.budget_guard(settings, spent)
    started, t0 = datetime.now(timezone.utc).isoformat(timespec="seconds"), time.monotonic()
    user = "Evidence pack (JSON):\n" + json.dumps(pack, ensure_ascii=False, indent=1)
    out, errors, warnings, attempts = None, ["not run"], [], 0
    for attempt in (1, 2):  # one corrective retry if the checker rejects the memo
        attempts = attempt
        before = len(log)
        out, resp = claude.call_json(role="memo", model=claude.SONNET, system=system, user=user, schema=SCHEMA,
                                     max_tokens=16000, effort="high", fallback=True, log=log, ledger=guard,
                                     cache=cache, stats=stats,
                                     meta={"run_id": run_id, "phase": phase, "label_config": mconf, "review_ids": []})
        spent["usd"] += sum(c.get("cost_usd", 0) for c in log[before:])
        if out is None:
            errors = ["memo call failed"]
            break
        errors, warnings = check(out, pack, ranking)
        if not errors:
            break
        user += ("\n\nYour previous memo was rejected by the checker for these reasons; fix them and return the full "
                 "memo again:\n- " + "\n- ".join(errors))
    status = "passed" if out and not errors else "failed"
    write_json(folder / "memo_check.json", {"status": status, "errors": errors, "warnings": warnings,
                                            "attempts": attempts, "config": mconf, "run_id": run_id})
    with (folder / "memo_calls.jsonl").open("a", encoding="utf-8") as f:
        for c in log:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    if out:
        with (folder / "claims.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["claim_id", "issue_id", "metric", "value"])
            for c in out["claims"]:
                w.writerow([c["claim_id"], c["issue_id"], c["metric"], str(c["value"]).strip()])
        write_json(folder / "recommendations.json", {"recommended_area": out["recommended_areas"][0],
                                                     "recommended_areas": out["recommended_areas"], "headline": out["headline"],
                                                     "recommendations": out["recommendations"], "check_status": status})
        served = next((c["model"] for c in reversed(log) if c["outcome"] == "succeeded"), claude.SONNET)
        write_json(folder / "memo_output.json", {"run_id": run_id, "served_model": served, "output": out,
                                                 "decision_criteria": pack.get("decision_criteria")})
        with (folder / "memo_quantities.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["value", "meaning", "pack_path"])
            w.writerows([q["value"], q["meaning"], q["pack_path"]] for q in out["other_quantities"])
        render(input_path, workspace)
    tokens = {k: sum(c.get(k, 0) or 0 for c in log) for k in rates.ITEMS}
    summary = {"run_id": run_id, "status": status, "errors": errors, "warnings": warnings, "attempts": attempts,
               "stage_cache_hits": stats["cache_hits"], "requests": len(log), "usage": tokens, "cost_usd": round(spent["usd"], 6),
               "wall_clock_seconds": round(time.monotonic() - t0, 2),
               "recommended_area": out["recommended_areas"][0] if out else None,
               "recommended_areas": out["recommended_areas"] if out else None}
    enrich.append_ledger({"run_id": run_id, "input": input_path.name, "label_config": mconf, "started_at": started,
                          "ended_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "requests": len(log),
                          "failed_requests": sum(c["outcome"] == "failed" for c in log), "input_tokens": tokens["input_tokens"],
                          "cost_usd": summary["cost_usd"], "texts_labeled": 0, "reviews_completed": 0,
                          "cache_hit_reviews": 0, "stop_reason": status})
    return summary
