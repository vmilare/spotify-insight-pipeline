"""Golden-set evaluation: compare saved pipeline predictions with the user's hand labels (held-out test set).

Reads predictions from the saved state (no model calls). The golden labels were never used in prompts,
Jev descriptions, thresholds or the sentiment mapping.
Usage: python -m evals.eval_golden [--labels evals/golden_50_labeled.csv] [--out evals/results/golden]
Writes per_case.csv, summary.json, summary.md (with confusion tables and the disagreement list).
"""
import argparse
import csv
import json
import statistics
from collections import Counter
from pathlib import Path

from pipeline import enrich, store
from pipeline.paths import dataset_file
from tools.check_submission import INTENTS, TOPICS, sha

HERE = Path(__file__).resolve().parent
SENTIMENT_TOLERANCE = 0.5  # predeclared: a sentiment prediction "passes" if within 0.5 of the human value


def confusion(pairs, labels):
    lines = ["| human \\ predicted | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
    c = Counter(pairs)
    for h in labels:
        if any(hh == h for hh, _ in pairs):
            lines.append(f"| **{h}** | " + " | ".join(str(c[(h, p)] or "·") for p in labels) + " |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default=str(HERE / "golden_50_labeled.csv"))
    ap.add_argument("--input", default=str(dataset_file("golden_50_to_label.csv")))
    ap.add_argument("--out", default=str(HERE / "results" / "golden"))
    ap.add_argument("--workspace", default="main")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    config = enrich.label_config(enrich.load_settings())
    conn = store.connect(sha(Path(args.input)), args.workspace)
    preds = {rid: json.loads(rj) for rid, rj in conn.execute(
        "SELECT review_id, record_json FROM results WHERE label_config=?", (config,))}
    status = dict(conn.execute("SELECT review_id, status FROM record_status"))
    conn.close()
    human = list(csv.DictReader(open(args.labels, encoding="utf-8")))

    cases = []
    for h in human:
        rid, p = h["review_id"], preds.get(h["review_id"])
        text = h["review_text"]
        row = {"review_id": rid, "text": text[:160].replace("\n", " "), "status": status.get(rid, "missing"),
               "human_topic": h["topic"], "human_intent": h["intent"], "human_severity": int(h["severity"]),
               "human_sentiment": float(h["sentiment"]), "human_needs_review": h["needs_review"] == "true",
               "labeler_note": h.get("labeler_note", "")}
        if p:
            h_ents = {e.lower() for e in json.loads(h["entities"] or "[]")}
            p_ents = set(p["entities"])
            row.update({"pred_topic": p["topic"], "pred_intent": p["intent"], "pred_severity": p["severity"],
                        "pred_sentiment": p["sentiment"], "pred_needs_review": p["needs_review"],
                        "needs_review_reasons": "|".join(p["internal"]["needs_review_reasons"]),
                        "topic_ok": p["topic"] == h["topic"], "intent_ok": p["intent"] == h["intent"],
                        "severity_ok": p["severity"] == int(h["severity"]),
                        "severity_abs_err": abs(p["severity"] - int(h["severity"])),
                        "sentiment_abs_err": round(abs(p["sentiment"] - float(h["sentiment"])), 3),
                        "sentiment_ok": abs(p["sentiment"] - float(h["sentiment"])) <= SENTIMENT_TOLERANCE,
                        "quote_is_substring": p["evidence_quote"] in text,
                        "quote_is_whole_text": p["evidence_quote"] == text,
                        "pred_entities": "|".join(sorted(p_ents)), "human_entities": "|".join(sorted(h_ents)),
                        "entities_unsupported_by_text": "|".join(e for e in p_ents if e.lower() not in text.lower()),
                        "entities_matched_human": len(p_ents & h_ents)})
        cases.append(row)

    with (out / "per_case.csv").open("w", newline="", encoding="utf-8") as f:
        fields = list(dict.fromkeys(k for c in cases for k in c))
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(cases)

    n = len(cases)
    done = [c for c in cases if "pred_topic" in c]
    def cnt(k):
        return sum(bool(c.get(k)) for c in done)  # missing predictions count as incorrect (denominator n)
    wrong_ti = [c for c in done if not (c["topic_ok"] and c["intent_ok"])]
    flagged = [c for c in done if c["pred_needs_review"]]
    summary = {
        "label_config": config, "golden_cases": n, "predicted": len(done), "missing_or_quarantined": n - len(done),
        "denominator_note": "missing/quarantined predictions count as incorrect",
        "topic_agreement": f"{cnt('topic_ok')}/{n}", "intent_agreement": f"{cnt('intent_ok')}/{n}",
        "topic_and_intent_both": f"{sum(c['topic_ok'] and c['intent_ok'] for c in done)}/{n}",
        "severity_exact": f"{cnt('severity_ok')}/{n}",
        "severity_within_1": f"{sum(c['severity_abs_err'] <= 1 for c in done)}/{n}",
        "severity_mae": round(statistics.mean(c["severity_abs_err"] for c in done), 3),
        "sentiment_mae": round(statistics.mean(c["sentiment_abs_err"] for c in done), 3),
        f"sentiment_within_{SENTIMENT_TOLERANCE}": f"{cnt('sentiment_ok')}/{n}",
        "evidence_quote_exact_substring": f"{cnt('quote_is_substring')}/{len(done)}",
        "evidence_quote_whole_text": f"{cnt('quote_is_whole_text')}/{len(done)}",
        "entities_unsupported_by_text": sum(bool(c["entities_unsupported_by_text"]) for c in done),
        "ambiguous_cases_flagged_by_labeler": sum(c["human_needs_review"] for c in cases),
        "cases_with_labeler_note": sum(bool(c["labeler_note"].strip()) for c in cases),
        "needs_review_as_predictor": {
            "flagged": len(flagged), "flagged_with_topic_or_intent_error": sum(c in wrong_ti for c in flagged),
            "unflagged": len(done) - len(flagged),
            "unflagged_with_topic_or_intent_error": sum(c in wrong_ti for c in done if not c["pred_needs_review"]),
            "errors_caught_by_flag": f"{sum(c in wrong_ti for c in flagged)}/{len(wrong_ti)}"},
        "per_topic_counts": {t: {"human": sum(c["human_topic"] == t for c in cases),
                                 "predicted": sum(c.get("pred_topic") == t for c in done),
                                 "correct": sum(c["human_topic"] == t and c.get("topic_ok") for c in done)} for t in TOPICS},
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    md = [f"# Golden-set evaluation ({n} hand-labeled reviews)", "",
          f"Config: `{config}` · predictions from saved state (no model calls)", "",
          "| Metric | Result |", "|---|---|"]
    for k in ("topic_agreement", "intent_agreement", "topic_and_intent_both", "severity_exact", "severity_within_1",
              "severity_mae", "sentiment_mae", f"sentiment_within_{SENTIMENT_TOLERANCE}", "evidence_quote_exact_substring",
              "evidence_quote_whole_text", "entities_unsupported_by_text", "missing_or_quarantined",
              "ambiguous_cases_flagged_by_labeler"):
        md.append(f"| {k} | {summary[k]} |")
    md += ["", "## Topic confusion", "", confusion([(c["human_topic"], c["pred_topic"]) for c in done], list(TOPICS)),
           "", "## Intent confusion", "", confusion([(c["human_intent"], c["pred_intent"]) for c in done], list(INTENTS)),
           "", "## Severity confusion", "", confusion([(str(c["human_severity"]), str(c["pred_severity"])) for c in done], list("12345")),
           "", "## needs_review as a predictor", "", "```", json.dumps(summary["needs_review_as_predictor"], indent=1), "```",
           "", "## Disagreements (topic, intent or severity)", "",
           "| review_id | text | human t/i/s | predicted t/i/s | flagged |", "|---|---|---|---|---|"]
    for c in done:
        if not (c["topic_ok"] and c["intent_ok"] and c["severity_ok"]):
            md.append(f"| `{c['review_id'][:8]}` | {c['text'][:90].replace('|', '/')} | {c['human_topic']}/{c['human_intent']}/{c['human_severity']} | "
                      f"{c['pred_topic']}/{c['pred_intent']}/{c['pred_severity']} | {'yes' if c['pred_needs_review'] else ''} |")
    (out / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "per_topic_counts"}, indent=2))


if __name__ == "__main__":
    main()
