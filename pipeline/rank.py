"""Stage 5 - Rank (code only, no model calls; reads only saved files in the analysis folder).

Contract baseline: for each issue, complaint_count = members, severity_sum = sum of member severity,
mean_severity = severity_sum / complaint_count (6 decimals, half-up), priority_score = severity_sum.
Sort by priority_score descending, then issue_id ascending; ranks start at 1.
Also writes aggregates.csv (extra context), a topic roll-up, and a sensitivity ranking that
excludes needs_review records.
"""
import csv
import gzip
import json
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from tools.check_submission import write_json


NON_ACTIONABLE = {"OTH-GENERAL"}  # general dissatisfaction without a specific product issue


def mean6(total, n):
    return str((Decimal(total) / Decimal(n)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def load(folder):
    """Saved inputs only. enriched.jsonl (local, >100 MB, not in git) or, in a fresh clone, the committed
    grading/records.jsonl.gz (same completed records in contract format)."""
    records = {}
    local = folder / "enriched.jsonl"
    if local.exists():
        stream = local.open(encoding="utf-8")
    else:
        fallback = Path(__file__).resolve().parent.parent / "grading" / "records.jsonl.gz"
        print(f"{local} not found; reading completed records from {fallback}")
        stream = gzip.open(fallback, "rt", encoding="utf-8")
    with stream as f:
        for line in f:
            r = json.loads(line)
            if r.get("status", "completed") == "completed":
                records[r["review_id"]] = r
    with (folder / "membership.csv").open(encoding="utf-8") as f:
        membership = [(row["issue_id"], row["review_id"]) for row in csv.DictReader(f)]
    with (folder / "issues.csv").open(encoding="utf-8") as f:
        issues = {row["issue_id"]: row for row in csv.DictReader(f)}
    return records, membership, issues


def ranking(membership, records, keep=lambda r: True):
    sums, counts = defaultdict(int), defaultdict(int)
    for issue_id, review_id in membership:
        rec = records[review_id]
        if keep(rec):
            sums[issue_id] += rec["severity"]
            counts[issue_id] += 1
    order = sorted(counts, key=lambda i: (-sums[i], i))
    return [{"rank": n, "issue_id": i, "complaint_count": counts[i], "severity_sum": sums[i],
             "mean_severity": mean6(sums[i], counts[i]), "priority_score": sums[i]}
            for n, i in enumerate(order, 1)]


def write_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def run(folder):
    folder = Path(folder)
    records, membership, issues = load(folder)
    base = ranking(membership, records)
    fields = ["rank", "issue_id", "complaint_count", "severity_sum", "mean_severity", "priority_score"]
    write_csv(folder / "ranking.csv", base, fields)
    sens = ranking(membership, records, keep=lambda r: not r["needs_review"])
    write_csv(folder / "ranking_without_needs_review.csv", sens, fields)
    # Additional business ranking (allowed alongside the baseline): same arithmetic, but drops issues that
    # name no specific product problem, so the recommendation targets something a team can fix.
    actionable = [r for r in base if r["issue_id"] not in NON_ACTIONABLE]
    write_csv(folder / "ranking_actionable.csv",
              [{**r, "rank": n} for n, r in enumerate(actionable, 1)], fields)

    # Extra context per issue (not part of the baseline arithmetic).
    agg = defaultdict(lambda: defaultdict(int))
    for issue_id, review_id in membership:
        r = records[review_id]
        a = agg[issue_id]
        a["members"] += 1
        a["cancellations"] += r["intent"] == "cancellation"
        a["needs_review"] += r["needs_review"]
        a[f"severity_{r['severity']}"] += 1
    agg_rows = []
    for row in base:
        a, meta = agg[row["issue_id"]], issues[row["issue_id"]]
        agg_rows.append({**row, "topic": meta["topic"], "name": meta["name"],
                         "cancellation_count": a["cancellations"], "needs_review_count": a["needs_review"],
                         **{f"severity_{s}": a[f"severity_{s}"] for s in range(1, 6)}})
    write_csv(folder / "aggregates.csv", agg_rows,
              fields + ["topic", "name", "cancellation_count", "needs_review_count"] + [f"severity_{s}" for s in range(1, 6)])

    # Roll-up to the product areas in the business question (topic level).
    topic = defaultdict(lambda: [0, 0, 0])
    for row in agg_rows:
        t = topic[row["topic"]]
        t[0] += row["complaint_count"]; t[1] += row["severity_sum"]; t[2] += row["cancellation_count"]
    roll = sorted(({"topic": k, "complaint_count": v[0], "severity_sum": v[1], "mean_severity": mean6(v[1], v[0]),
                    "cancellation_count": v[2]} for k, v in topic.items()), key=lambda x: (-x["severity_sum"], x["topic"]))
    write_csv(folder / "topic_rollup.csv", roll, ["topic", "complaint_count", "severity_sum", "mean_severity", "cancellation_count"])

    summary = {"issues_ranked": len(base), "baseline_records": len(membership),
               "top5_actionable": [(r["issue_id"], r["priority_score"]) for r in actionable[:5]],
               "top5": [(r["issue_id"], r["priority_score"]) for r in base[:5]],
               "top5_without_needs_review": [(r["issue_id"], r["priority_score"]) for r in sens[:5]],
               "top_issue_same_without_needs_review": bool(base and sens and base[0]["issue_id"] == sens[0]["issue_id"])}
    write_json(folder / "rank_summary.json", summary)
    return summary
