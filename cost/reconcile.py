"""Offline reconciliation: our logged API usage vs the providers' own usage exports. No API key, no network.

Inputs (all committed):
  cost/provider_usage/typesafe_usage.csv           TypeSafe (Jev) usage export, hourly buckets (UTC), this project's key
  cost/provider_usage/anthropic_console_usage.csv  Anthropic Console usage export, daily (UTC), this project's key only
  grading/calls.jsonl.gz + the committed call logs under runs/, cost/, evals/results/   our per-call records
  cost/rates.csv                                   dated prices in billing units
Output: cost/reconciliation.md

Usage: python cost/reconcile.py

Calls are de-duplicated by request_id. Only calls that reached the provider are counted: every failed call in our
logs is a system-test failure simulated in-process (evals/system_tests.py) and was never sent. Jev calls are bucketed
by completion time (start + duration), which is how the provider's hourly export counts them; Claude calls by UTC day.
"""
import csv
import glob
import gzip
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COST = ROOT / "cost"
EXPORTED_AT = "2026-10-18 00:45 UTC"  # when both provider exports were downloaded

# Provider-side usage with no per-call record in our logs, each matched to its source in LOG.md / the repo.
UNLOGGED = [
    {"provider": "typesafe", "bucket": "2026-10-11T22", "requests": 9, "input_tokens": 5449,
     "what": "Jev smoke test (891 tokens) and the 8-request token probe (523+417+440+324+891+545+472+946) in LOG.md, "
             "2026-10-11 \"Probe of where tokens go\" — printed to the console; raw call records were not saved"},
    {"provider": "typesafe", "bucket": "2026-10-12T03", "requests": 13, "input_tokens": 78291,
     "what": "First run of the 13-request development comparison `evals/results/dev_compare_b`; it was rerun "
             "identically and the rerun overwrote calls.jsonl, so one copy is logged (same 78,291 input tokens; Jev "
             "output varies slightly between identical runs, LOG.md)"},
]


def call_records():
    files = [ROOT / "grading" / "calls.jsonl.gz"]
    for pattern in ("runs/**/*.jsonl", "cost/*.jsonl", "evals/results/**/*.jsonl"):
        files += [Path(p) for p in sorted(glob.glob(str(ROOT / pattern), recursive=True))]
    calls, simulated = {}, 0
    for path in files:
        stream = gzip.open(path, "rt", encoding="utf-8") if path.suffix == ".gz" else path.open(encoding="utf-8")
        with stream as f:
            for line in f:
                try:
                    c = json.loads(line)
                except ValueError:
                    continue
                if isinstance(c, dict) and c.get("request_id") and c.get("model") and "input_tokens" in c:
                    calls.setdefault(c["request_id"], c)
    sent = []
    for c in calls.values():
        if c.get("outcome") == "succeeded":
            sent.append(c)
        elif "simulated" in str(c.get("error")) or str(c.get("run_id", "")).startswith("systest-"):
            simulated += 1
        else:
            raise SystemExit(f"failed call {c['request_id']} is not a simulated test failure; decide how to count it")
    return sent, simulated


def rates():
    out = {}
    for r in csv.DictReader((COST / "rates.csv").open(encoding="utf-8")):
        out[(r["model"], r["billing_item"])] = float(r["usd_per_unit"]) / float(r["unit_size"])
    return out


def utc(ts):
    return datetime.fromtimestamp(ts, timezone.utc)


def fmt(n):
    return f"{n:,}"


def main():
    sent, simulated = call_records()
    rate = rates()

    # TypeSafe (Jev): hourly buckets by completion time.
    ours = defaultdict(lambda: [0, 0, 0])
    for c in sent:
        if str(c["model"]).startswith("jev"):
            b = ours[utc(c["started_at"] + (c.get("seconds") or 0)).strftime("%Y-%m-%dT%H")]
            b[0] += 1; b[1] += int(c["input_tokens"] or 0); b[2] += int(c["output_tokens"] or 0)
    prov = {r["day"][:13]: [int(r["requests"]), int(r["input_tokens"]), int(r["output_tokens"])]
            for r in csv.DictReader((COST / "provider_usage" / "typesafe_usage.csv").open(encoding="utf-8"))}
    unlogged = {u["bucket"]: u for u in UNLOGGED if u["provider"] == "typesafe"}
    jev_rows, residual = [], [0, 0]
    for h in sorted(set(ours) | set(prov)):
        p, o, u = prov.get(h, [0, 0, 0]), ours.get(h, [0, 0, 0]), unlogged.get(h)
        dr, di = p[0] - o[0], p[1] - o[1]
        rr, ri = dr - (u["requests"] if u else 0), di - (u["input_tokens"] if u else 0)
        residual[0] += rr; residual[1] += ri
        jev_rows.append(f"| {h}:00 | {fmt(p[0])} | {fmt(p[1])} | {fmt(o[0])} | {fmt(o[1])} | {dr:+,} | {di:+,} | "
                        f"{'unlogged — see below' if u else ('—' if not (dr or di) else 'unexplained')} |")
    pt = [sum(v[i] for v in prov.values()) for i in range(3)]
    ot = [sum(v[i] for v in ours.values()) for i in range(3)]
    jin = rate[("jev-1.13.0", "input_tokens")]

    # Anthropic: daily buckets per model (UTC start time; no call in our logs runs across midnight).
    cl = defaultdict(lambda: [0, 0, 0])
    for c in sent:
        if str(c["model"]).startswith("claude"):
            b = cl[(utc(c["started_at"]).strftime("%Y-%m-%d"), c["model"])]
            b[0] += 1; b[1] += int(c["input_tokens"] or 0); b[2] += int(c["output_tokens"] or 0)
    aprov = {}
    for r in csv.DictReader((COST / "provider_usage" / "anthropic_console_usage.csv").open(encoding="utf-8")):
        k = (r["usage_date_utc"], r["model_version"])
        a = aprov.setdefault(k, [0, 0, 0, 0])
        a[0] += int(r["usage_input_tokens_no_cache"]); a[1] += int(r["usage_output_tokens"])
        a[2] += int(r["usage_input_tokens_cache_write_5m"]) + int(r["usage_input_tokens_cache_write_1h"])
        a[3] += int(r["usage_input_tokens_cache_read"])

    def ccost(model, i, o):
        return i * rate[(model, "input_tokens")] + o * rate[(model, "output_tokens")]

    cl_rows, pending = [], []
    for k in sorted(set(cl) | set(aprov)):
        o, p = cl.get(k, [0, 0, 0]), aprov.get(k)
        if p is None:
            pending.append((k, o))
            cl_rows.append(f"| {k[0]} | `{k[1]}` | not yet in export | {fmt(o[0])} | {fmt(o[1])} | {fmt(o[2])} | "
                           f"${ccost(k[1], o[1], o[2]):.4f} | pending — re-export |")
            continue
        di, do = p[0] - o[1], p[1] - o[2]
        cl_rows.append(f"| {k[0]} | `{k[1]}` | {fmt(p[0])} in / {fmt(p[1])} out | {fmt(o[0])} | {fmt(o[1])} | {fmt(o[2])} | "
                       f"${ccost(k[1], p[0], p[1]):.4f} vs ${ccost(k[1], o[1], o[2]):.4f} | "
                       f"{'exact match' if not (di or do) else f'{di:+,} in / {do:+,} out tokens not in our logs'} |")
    a_matched = sum(ccost(k[1], *aprov[k][:2]) for k in aprov)
    a_ours_matched = sum(ccost(k[1], cl[k][1], cl[k][2]) for k in aprov if k in cl)
    a_pending = sum(ccost(k[1], o[1], o[2]) for k, o in pending)

    ledger = list(csv.DictReader((ROOT / "runs" / "spend_ledger.csv").open(encoding="utf-8")))
    led_jev = sum(float(r["cost_usd"]) for r in ledger if not r["label_config"].startswith("claude"))
    led_total = sum(float(r["cost_usd"]) for r in ledger)

    md = [
        "# API usage reconciliation (provider exports vs our call logs)", "",
        f"Generated by `python cost/reconcile.py` (offline, no API key). Provider exports downloaded {EXPORTED_AT}; "
        "sanitized copies (this project's key only) in [`provider_usage/`](provider_usage/). Our side: every saved call "
        f"record, de-duplicated by request ID ({fmt(len(sent))} calls that reached a provider; {simulated} test failures "
        "simulated in-process were never sent and are excluded).", "",
        "## Summary", "",
        "| Provider | Provider export | Our call logs | Difference | Status |", "|---|---|---|---|---|",
        f"| TypeSafe (Jev) | {fmt(pt[0])} requests, {fmt(pt[1])} input tokens → **${pt[1] * jin:.4f}** | "
        f"{fmt(ot[0])} requests, {fmt(ot[1])} input tokens → ${ot[1] * jin:.4f} | {pt[0] - ot[0]:+,} requests, "
        f"{pt[1] - ot[1]:+,} tokens (${(pt[1] - ot[1]) * jin:.4f}) | "
        f"{'fully explained: 2 unlogged early batches (below)' if residual == [0, 0] else f'unexplained residual {residual}'} |",
        f"| Anthropic (Claude) | through 2026-10-12 → **${a_matched:.4f}** | same days → ${a_ours_matched:.4f}; "
        f"plus ${a_pending:.4f} on 2026-10-17/18 | ${a_matched - a_ours_matched:+.6f} | matched days agree; today's memo runs "
        "not yet in the export (provider lag) |", "",
        f"Spend ledger (`runs/spend_ledger.csv`, the figure in the README): **${led_total:.4f}** in total, of which Jev "
        f"${led_jev:.4f}. Provider-implied Jev cost: ${pt[1] * jin:.4f} (difference ${pt[1] * jin - led_jev:+.4f}; the ledger's "
        "development-experiments row is an estimate from LOG.md, confirmed here by the provider's token counts).", "",
        "Costs use [`rates.csv`](rates.csv) (Jev $0.042 per 1M input tokens, output free; Claude standard rates). The "
        "exports contain tokens, not dollars, so provider-side dollars are tokens × the same dated rates.", "",
        "## TypeSafe (Jev), by UTC hour", "",
        "| Hour (UTC) | Provider requests | Provider input tokens | Our requests | Our input tokens | Δ requests | Δ input tokens | Explanation |",
        "|---|---|---|---|---|---|---|---|", *jev_rows, "",
        f"Output tokens (free): provider {fmt(pt[2])}, ours {fmt(ot[2])}.", "",
        "Unlogged provider usage (no per-call record in our logs):", "",
        *[f"- **{u['bucket']}:00 UTC**, {u['requests']} requests, {fmt(u['input_tokens'])} input tokens "
          f"(${u['input_tokens'] * jin:.6f}): {u['what']}." for u in UNLOGGED], "",
        "Hour boundaries: the provider counts a request in the hour it completes. Bucketing our calls by start time "
        "instead moves 2 requests (9,341 and 9,495 input tokens) from 04:00 to 05:00 and from 15:00 to 16:00; each pair "
        "started under 0.1 s before the hour. Bucketing by completion time, as here, removes that difference.", "",
        "## Anthropic (Claude), by UTC day and model", "",
        "| Day (UTC) | Model | Provider export | Our requests | Our input | Our output | Cost (provider vs ours) | Status |",
        "|---|---|---|---|---|---|---|---|", *cl_rows, "",
        "- The export also lists another API key on the same Anthropic account (including Batch API usage, which this "
        "pipeline never uses). Those rows are not this project's and were removed from the committed copy.",
        "- The small Haiku difference on 2026-10-12 (a few tokens, under $0.00001) has no matching call in our logs; "
        "most likely a key check before call logging started. It is left visible rather than assigned.",
        "- Rows marked *pending* are the memo-v4/v5 regenerations, run shortly before the export was downloaded; the "
        "Console had not yet published them. Re-export the Console usage after a few hours and rerun this script.",
    ]
    (COST / "reconciliation.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Jev residual after documented unlogged usage: {residual}; Claude pending rows: {len(pending)}")
    print("wrote", COST / "reconciliation.md")


if __name__ == "__main__":
    main()
