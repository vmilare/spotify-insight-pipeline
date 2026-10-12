"""Dev experiment: how do Jev's accuracy and cost change with (a) full vs short question
descriptions and (b) 1 vs N reviews per request? Runs on the 50 hand-labeled DEV reviews only
(never golden), compares to the human labels, and projects one full pass over 484,189 texts.

Usage: python -m evals.dev_jev_test [--configs full:1 short:1 full:10 short:10]
Writes evals/results/dev_compare/{summary.json, summary.md, predictions.jsonl, calls.jsonl}
"""
import argparse
import csv
import glob
import json
import sqlite3
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from pipeline import jev
from pipeline.paths import REPO

HERE = Path(__file__).resolve().parent
OUT = HERE / "results" / "dev_compare"
DISTINCT_TEXTS = 484189
FIELDS = ("topic", "intent", "severity", "sentiment")


def corpus_mean_chars():
    db = sorted(glob.glob(str(REPO / "data" / "state" / "state_1fc85de68a30*.sqlite")))
    if not db:
        return None
    return sqlite3.connect(db[0]).execute("SELECT AVG(LENGTH(review_text)) FROM texts").fetchone()[0]


def run_config(rows, labels, variant, pack, calls):
    questions = jev.build_questions(labels, variant)
    config = jev.question_set_version(variant, pack)
    preds, requests, started = {}, [], time.monotonic()
    for start in range(0, len(rows), pack):
        group = rows[start:start + pack]
        ids = [r["review_id"] for r in group]
        meta = {"role": "enrich", "phase": "dev_experiment", "label_config": config, "review_ids": ids}
        if pack == 1:
            payload, attempts = jev.call(group[0]["review_text"], questions, log=calls, meta=meta)
            per_review = [payload] if payload else None
        else:
            state, packed = jev.pack_request([r["review_text"] for r in group], questions)
            payload, attempts = jev.call(state, packed, log=calls, meta=meta, timeout=120)
            per_review = jev.unpack(payload, len(group)) if payload else None
        requests.append({"review_ids": ids, "attempts": attempts,
                         "input_tokens": payload["usage"]["input_tokens"] if payload else None,
                         "chars": sum(len(r["review_text"]) for r in group)})
        if per_review:
            for r, p in zip(group, per_review):
                preds[r["review_id"]] = jev.parse(p)
    return config, preds, requests, time.monotonic() - started


def score(rows, preds):
    ok = [r for r in rows if r["review_id"] in preds]
    if not ok:
        return {}
    p = lambda r: preds[r["review_id"]]
    sev_err = [abs(p(r)["severity"] - int(r["severity"])) for r in ok]
    low = [r for r in ok if min(v for v in p(r)["confidence"].values() if v is not None) < 0.6]
    return {
        "scored": len(ok),
        "topic_agree": sum(p(r)["topic"] == r["topic"] for r in ok),
        "intent_agree": sum(p(r)["intent"] == r["intent"] for r in ok),
        "severity_exact": sum(e == 0 for e in sev_err),
        "severity_within_1": sum(e <= 1 for e in sev_err),
        "severity_mae": round(statistics.mean(sev_err), 3),
        "sentiment_mae": round(statistics.mean(abs(p(r)["sentiment"] - float(r["sentiment"])) for r in ok), 3),
        "low_confidence_reviews(<0.6 on any field)": len(low),
        "low_conf_topic_errors": sum(p(r)["topic"] != r["topic"] for r in low),
    }


def project(requests, pack, corpus_chars):
    """Fit billed tokens = a + b * chars per request, then project one full pass."""
    good = [q for q in requests if q["input_tokens"]]
    xs, ys = [q["chars"] for q in good], [q["input_tokens"] for q in good]
    tokens = sum(ys)
    reviews = sum(len(q["review_ids"]) for q in good)
    out = {"requests": len(requests), "failed_requests": sum(1 for q in requests if not q["input_tokens"]),
           "billed_input_tokens": tokens, "tokens_per_review_measured": round(tokens / reviews, 1),
           "cost_measured_usd": round(tokens * jev.PRICE_PER_M_INPUT / 1e6, 6)}
    if len(set(xs)) > 1 and corpus_chars:
        fit = statistics.linear_regression(xs, ys)
        per_request = fit.intercept + fit.slope * corpus_chars * pack
        per_review = per_request / pack
        out.update({"fit_tokens_per_request": f"{fit.intercept:.0f} + {fit.slope:.3f} x chars",
                    "tokens_per_review_at_corpus_mean_length": round(per_review, 1),
                    "projected_full_pass_usd": round(per_review * DISTINCT_TEXTS * jev.PRICE_PER_M_INPUT / 1e6, 2)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", nargs="+", default=["full:1", "short:1", "full:10", "short:10"])
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader((HERE / "dev_50_labeled.csv").open(encoding="utf-8")))
    labels = jev.load_labels()
    corpus_chars = corpus_mean_chars()
    calls, results, all_preds = [], [], {}
    for spec in args.configs:
        variant, pack = spec.split(":")[0], int(spec.split(":")[1])
        config, preds, requests, wall = run_config(rows, labels, variant, pack, calls)
        all_preds[config] = preds
        results.append({"config": config, "variant": variant, "reviews_per_request": pack,
                        "wall_clock_seconds": round(wall, 1), **project(requests, pack, corpus_chars),
                        **score(rows, preds)})
        print(json.dumps(results[-1]), flush=True)

    with (OUT / "predictions.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"review_id": r["review_id"], "text": r["review_text"][:200],
                                "human": {k: r[k] for k in FIELDS},
                                "jev": {c: ({k: p[r["review_id"]][k] for k in FIELDS} if r["review_id"] in p else None)
                                        for c, p in all_preds.items()}}, ensure_ascii=False) + "\n")
    with (OUT / "calls.jsonl").open("w", encoding="utf-8") as f:
        for c in calls:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    summary = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "model": jev.MODEL,
               "price_per_million_input_usd": jev.PRICE_PER_M_INPUT,
               "price_source": "https://docs.typesafe.ai/models (checked 2026-10-11)",
               "dev_reviews": len(rows), "dev_mean_chars": round(statistics.mean(len(r["review_text"]) for r in rows), 1),
               "corpus_mean_chars": round(corpus_chars, 1) if corpus_chars else None,
               "total_cost_usd": round(sum(c["input_tokens"] or 0 for c in calls) * jev.PRICE_PER_M_INPUT / 1e6, 6),
               "results": results}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    n = len(rows)
    md = ["| Config | Topic | Intent | Severity exact | Sev. ±1 | Sev. MAE | Sent. MAE | Tokens/review (measured) | Tokens/review (corpus length) | Full pass $ | Low-conf. reviews |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in results:
        md.append(f"| {x['config']} | {x.get('topic_agree')}/{n} | {x.get('intent_agree')}/{n} | {x.get('severity_exact')}/{n} | "
                  f"{x.get('severity_within_1')}/{n} | {x.get('severity_mae')} | {x.get('sentiment_mae')} | {x['tokens_per_review_measured']} | "
                  f"{x.get('tokens_per_review_at_corpus_mean_length')} | {x.get('projected_full_pass_usd')} | "
                  f"{x.get('low_confidence_reviews(<0.6 on any field)')} |")
    (OUT / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    print("total experiment cost USD:", summary["total_cost_usd"])


if __name__ == "__main__":
    main()
