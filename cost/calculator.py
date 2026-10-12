#!/usr/bin/env python3
"""100-review cost and runtime calculator.

  python cost/calculator.py                 OFFLINE REPLAY (default): recompute measured pilot cost from
                                            cost/usage.csv x cost/rates.csv, refresh estimates, project the
                                            full run, write cost/report.md. No API key, no network.
  python cost/calculator.py --rate-scale 2  same, with every API rate multiplied (arithmetic check)
  python cost/calculator.py pilot           PAID: run the real pipeline on cost_100.csv in a fresh, empty
                                            workspace with 1 worker (cold), then again (warm); save evidence.

Importing this module never makes API calls; pipeline code is imported only inside `pilot`.
"""
import argparse
import csv
import glob
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

COST = Path(__file__).resolve().parent
REPO = COST.parent
ITEMS = ("input_tokens", "output_tokens", "cache_write_tokens", "cache_read_tokens")
STAGE_ORDER = ("ingest", "enrich", "verify", "group", "group_review", "rank", "recommend")


# ---------------------------------------------------------------- offline arithmetic
def load_rates(path, scale=1.0):
    rates, meta = {}, []
    with Path(path).open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rates[(row["model"], row["billing_item"])] = float(row["usd_per_unit"]) / float(row["unit_size"]) * scale
            meta.append(row)
    return rates, meta


def load_usage(path):
    with Path(path).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def measured_costs(usage, rates):
    """cost per (pilot_run, stage) = sum over rows of units x unit price; missing rates are reported, not zeroed."""
    out = defaultdict(lambda: {"usd": 0.0, "units": defaultdict(int), "requests": set(), "missing_rates": set()})
    for row in usage:
        key = (row["pilot_run"], row["stage"])
        units = int(row["units"])
        out[key]["units"][row["billing_item"]] += units
        out[key]["requests"].add(row["request_id"])
        rate = rates.get((row["model"], row["billing_item"]))
        if rate is None:
            if units:
                out[key]["missing_rates"].add(f"{row['model']}/{row['billing_item']}")
        else:
            out[key]["usd"] += units * rate
    return out


def refresh_runs():
    """Measured enrichment runs on the development checkpoints (main workspace), for estimate refreshes."""
    rows = []
    for name in ("cost_100", "checkpoint_500", "analysis_10000"):
        for path in sorted(glob.glob(str(REPO / "runs" / f"main-{name}-*" / "run_summary.json"))):
            s = json.loads(Path(path).read_text(encoding="utf-8"))
            if s.get("texts_labeled"):
                rows.append({"checkpoint": name, "run_id": s["run_id"], "texts_labeled": s["texts_labeled"],
                             "cache_hit_reviews": s["cache_hit_reviews"], "input_tokens": s["input_tokens"],
                             "tokens_per_text": s["tokens_per_text"], "wall_clock_seconds": s["wall_clock_seconds"],
                             "texts_per_second": s["throughput_texts_per_second"], "workers": s["workers"]})
    return rows


def spent_so_far():
    path = REPO / "runs" / "spend_ledger.csv"
    if not path.exists():
        return 0.0
    with path.open(encoding="utf-8") as f:
        return sum(float(r["cost_usd"]) for r in csv.DictReader(f))


def project(m, costs, rates, a, refresh):
    """Full-run projection per stage for base / conservative scenarios, with and without exact-text reuse."""
    jev_rate = rates[("jev-1.13.0", "input_tokens")]
    latest = refresh[-1] if refresh else None
    tok = latest["tokens_per_text"] if latest else m["stages"]["enrich"]["tokens_per_text"]
    # Per-worker throughput: a run with W workers is divided by W (the 10k run at 2 workers measured ~2.0x of 1 worker).
    tps = latest["texts_per_second"] / latest["workers"] if latest else m["stages"]["enrich"]["texts_per_second"]
    c = a["controls"]
    workers = c["max_workers"]
    speedup = 1 + (workers - 1) * c["parallel_efficiency"]
    verify_cost_per_review = costs[("cold", "verify")]["usd"] / max(1, m["stages"]["verify"]["verified"])
    verify_sec_per_review = m["runs"]["cold"]["stage_seconds"]["verify"] / max(1, m["stages"]["verify"]["verified"])
    gr_cost, gr_sec = costs[("cold", "group_review")]["usd"], m["runs"]["cold"]["stage_seconds"]["group_review"]
    memo_cost, memo_sec = costs[("cold", "recommend")]["usd"], m["runs"]["cold"]["stage_seconds"]["recommend"]
    local_per_row = (m["runs"]["cold"]["stage_seconds"]["ingest"] + m["runs"]["cold"]["stage_seconds"]["group"]
                     + m["runs"]["cold"]["stage_seconds"]["rank"]) / m["input"]["rows"]
    out = {}
    for name, sc in a["scenarios"].items():
        for reuse in (True, False):
            texts = a["volume"]["distinct_nonempty_texts"] if reuse else a["volume"]["nonempty_reviews"]
            enrich_usd = texts * tok * jev_rate * (1 + sc["retry_rate"])
            enrich_sec = texts * (1 + sc["retry_rate"]) / (tps * speedup)
            n_verify = a["stages"]["verify_sample_size"]
            verify_usd = n_verify * verify_cost_per_review * sc["verify_multiplier"]
            memo_calls = a["stages"]["memo_calls_base" if name == "base" else "memo_calls_conservative"]
            stages = {
                "enrich": (enrich_usd, enrich_sec),
                "verify": (verify_usd, n_verify * verify_sec_per_review),
                "group_review (fixed)": (gr_cost * sc["group_review_multiplier"], gr_sec * sc["group_review_multiplier"]),
                "recommend (fixed, per memo x calls)": (memo_cost * memo_calls, memo_sec * memo_calls),
                "local stages (ingest, group, rank)": (0.0, local_per_row * a["volume"]["source_rows"]),
                "fallback model": (0.0, 0.0),
            }
            out[(name, reuse)] = {"stages": stages, "usd": sum(v[0] for v in stages.values()),
                                  "seconds": sum(v[1] for v in stages.values()), "texts": texts}
    return out, {"tokens_per_text": tok, "texts_per_second_per_worker": tps, "workers": workers, "speedup": speedup,
                 "source": f"{latest['checkpoint']} run {latest['run_id']}" if latest else "pilot"}


def fmt(x, d=4):
    return f"${x:,.{d}f}"


def replay(args):
    rates, rate_meta = load_rates(args.rates, args.rate_scale)
    a = yaml.safe_load(Path(args.assumptions).read_text(encoding="utf-8"))
    m = json.loads((COST / "pilot_measurements.json").read_text(encoding="utf-8"))
    usage = load_usage(COST / "usage.csv")
    costs = measured_costs(usage, rates)
    refresh = refresh_runs()
    proj, basis = project(m, costs, rates, a, refresh)
    spent = a["controls"]["spent_before_full_run_usd"]
    spent = spent_so_far() if spent is None else spent
    budget = a["controls"]["budget_usd"]
    L = [f"# Cost and runtime calculator — report", "",
         f"Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} by `python cost/calculator.py` "
         f"(offline replay; rate scale {args.rate_scale}). Inputs: `cost/usage.csv`, `cost/rates.csv`, "
         f"`cost/pilot_measurements.json`, `cost/assumptions.yaml`.", "",
         "## 1. Measured: real 100-review pilot (`cost_100.csv`)", "",
         f"- Input `{m['input']['file']}` · SHA-256 `{m['input']['sha256']}` · matches manifest: **{m['input']['matches_manifest']}** · "
         f"{m['input']['rows']} IDs · {m['input']['unique_texts']} unique texts",
         f"- Workspace `{m['workspace']}` (empty result cache at start) · workers: 1 · run at {m['started_at']}",
         f"- Record statuses (cold): {m['runs']['cold']['status_counts']}", "",
         "| Stage | Provider / model | Effort / settings | Prompt / schema | Batch | Cold requests (attempts) | Failed | Cache hits (warm) | Cold usage | Cold API cost | Warm requests | Warm cost |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    tot = {"cold": 0.0, "warm": 0.0}
    for st in STAGE_ORDER:
        info = m["stages"][st]
        cold, warm = costs.get(("cold", st)), costs.get(("warm", st))
        cu = cold["units"] if cold else {}
        usage_txt = ", ".join(f"{k.replace('_tokens', '')} {v:,}" for k, v in cu.items() if v) or "—"
        c_usd = cold["usd"] if cold else 0.0
        w_usd = warm["usd"] if warm else 0.0
        tot["cold"] += c_usd; tot["warm"] += w_usd
        miss = (cold["missing_rates"] if cold else set()) | (warm["missing_rates"] if warm else set())
        L.append(f"| {st} | {info['provider']} / `{info['model']}` | {info['settings']} | {info['prompt_schema']} | "
                 f"{info['batch']} | {len(cold['requests']) if cold else 0} ({info['cold_attempts']}) | {info['cold_failed']} | "
                 f"{info['warm_cache_hits']} | {usage_txt} | {fmt(c_usd, 6)}{' ⚠ missing rate ' + ','.join(miss) if miss else ''} | "
                 f"{len(warm['requests']) if warm else 0} | {fmt(w_usd, 6)} |")
    cold_s, warm_s = m["runs"]["cold"]["end_to_end_seconds"], m["runs"]["warm"]["end_to_end_seconds"]
    completed = m["runs"]["cold"]["status_counts"].get("completed", 0)
    L += ["", f"**Cold run:** API cost **{fmt(tot['cold'], 6)}** · end-to-end wall clock **{cold_s:.3f} s** "
          f"(stage clocks: {', '.join(f'{k} {v:.3f}s' for k, v in m['runs']['cold']['stage_seconds'].items())})",
          f"- Cost per 1,000 input rows: {fmt(tot['cold'] / m['input']['rows'] * 1000, 4)} · per completed record: "
          f"{fmt(tot['cold'] / max(1, completed), 6)} · enrichment throughput {m['stages']['enrich']['texts_per_second']} texts/s (1 worker)",
          f"- **Warm run** (same settings, saved results): enrichment requests **{m['stages']['enrich']['warm_requests']}**, "
          f"downstream model calls {m['runs']['warm']['model_calls']}, incremental API cost **{fmt(tot['warm'], 6)}**, "
          f"wall clock **{warm_s:.3f} s**",
          "- API spend vs other costs: all figures above are API spend from recorded usage. Local compute "
          f"(laptop CPU/electricity): **unknown, not measured** ({a['local_compute']['note']})", "",
          "## 2. Estimate refreshes on development checkpoints (enrichment, main workspace)", "",
          "| Checkpoint | Run | Texts labeled | Cache-hit reviews | Tokens / text | Texts / s | Workers | Texts / s per worker |", "|---|---|---|---|---|---|---|---|"]
    for r in refresh:
        L.append(f"| {r['checkpoint']} | `{r['run_id']}` | {r['texts_labeled']:,} | {r['cache_hit_reviews']:,} | "
                 f"{r['tokens_per_text']} | {r['texts_per_second']} | {r['workers']} | {r['texts_per_second'] / r['workers']:.1f} |")
    L += ["", f"Projection basis: **{basis['tokens_per_text']} tokens/text**, **{basis['texts_per_second_per_worker']:.1f} texts/s per "
          f"worker** from {basis['source']}; {basis['workers']} workers at {a['controls']['parallel_efficiency']} efficiency "
          f"→ {basis['speedup']:.1f}× (modeled, not measured).", "",
          "## 3. Full-run projection (660,622 rows · 660,609 nonempty · 13 empty-text quarantines)", "",
          "| Scenario | Exact-text reuse | Model work units | Enrich | Verify | Group review | Memo | Total API | Elapsed |",
          "|---|---|---|---|---|---|---|---|---|"]
    for (name, reuse), p in proj.items():
        s = p["stages"]
        L.append(f"| {name} | {'yes (484,189 texts)' if reuse else 'no (660,609 reviews)'} | {p['texts']:,} | "
                 f"{fmt(s['enrich'][0], 2)} | {fmt(s['verify'][0], 3)} | {fmt(s['group_review (fixed)'][0], 3)} | "
                 f"{fmt(s['recommend (fixed, per memo x calls)'][0], 3)} | **{fmt(p['usd'], 2)}** | {p['seconds'] / 3600:.1f} h |")
    L += ["", "Fixed overhead (group review, memo) is counted once, not per review. Fallback model cost is $0 by design "
          "(no stronger-model fallback; low-confidence labels are flagged needs_review instead).", "",
          "## 4. Controls and budget", "",
          f"- Budget (project spending limit): **{fmt(budget, 2)}** · already spent (ledger): **{fmt(spent, 4)}** · "
          f"remaining: **{fmt(budget - spent, 4)}**",
          f"- Max workers: {a['controls']['max_workers']} · fallback fraction: {a['controls']['fallback_fraction']} · "
          f"output-token caps per request: {a['controls']['output_token_caps']} (Jev output tokens are free)",
          "- Enforcement in code: spend ledger reserves worst-case cost before each request and refuses to send past the cap "
          "(`config/settings.yaml` budget); circuit breaker after consecutive failures; bounded retries with backoff + jitter."]
    for (name, reuse), p in proj.items():
        if spent + p["usd"] > budget:
            L.append(f"- ⚠ **{name} / {'reuse' if reuse else 'no reuse'} exceeds the budget**: "
                     f"{fmt(spent, 2)} + {fmt(p['usd'], 2)} = {fmt(spent + p['usd'], 2)} > {fmt(budget, 2)}")
        else:
            L.append(f"- ✓ {name} / {'reuse' if reuse else 'no reuse'} fits: {fmt(spent + p['usd'], 2)} ≤ {fmt(budget, 2)}")
    L += ["", "## 5. Rates used (editable `cost/rates.csv`)", "",
          "| Provider | Model | Billing item | USD per unit | Unit size | Source | Checked |", "|---|---|---|---|---|---|---|"]
    for r in rate_meta:
        L.append(f"| {r['provider']} | {r['model']} | {r['billing_item']} | {float(r['usd_per_unit']) * args.rate_scale:g} | "
                 f"{r['unit_size']} {r['unit']} | {r['source_url']} | {r['checked_on']} |")
    L += ["", "Formula: item_cost = billed_units × (usd_per_unit / unit_size); items are mutually exclusive "
          "(input = uncached input; output already includes thinking tokens); total = Σ item_cost."]
    report = "\n".join(L) + "\n"
    out = Path(args.out)
    out.write_text(report, encoding="utf-8")
    print(report)


# ---------------------------------------------------------------- paid pilot
def pilot(args):
    sys.path.insert(0, str(REPO))
    from pipeline import enrich, group, group_review, ingest, rank, recommend, store, verify  # noqa: E402
    from pipeline.paths import dataset_file  # noqa: E402
    from tools.check_submission import csv_rows, row_sha, sha  # noqa: E402

    src = dataset_file("cost_100.csv")
    manifest = json.loads((REPO / "config" / "source_manifest.json").read_text(encoding="utf-8"))
    file_sha = sha(src)
    ws = "pilot-" + datetime.now().strftime("%Y%m%dT%H%M%S")
    settings = enrich.load_settings()
    folder = group.analysis_dir(src, ws)
    m = {"workspace": ws, "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "input": {"file": src.name, "sha256": file_sha,
                   "matches_manifest": file_sha == manifest["files"]["cost_100.csv"]["sha256"],
                   "rows": sum(1 for _ in csv_rows(src))}, "runs": {}, "verify_sample": args.verify_sample}
    claude_logs = {"verify": folder / "verify" / "calls.jsonl", "group_review": folder / "group_review_calls.jsonl",
                   "recommend": folder / "memo_calls.jsonl"}
    all_calls = []
    for phase in ("cold", "warm"):
        offsets = {k: (sum(1 for _ in p.open()) if p.exists() else 0) for k, p in claude_logs.items()}
        stage_seconds, results = {}, {}
        t0 = time.monotonic()
        for st, fn in (("ingest", lambda: ingest.run(src, COST / "pilot_ingest", ws)),
                       ("enrich", lambda: enrich.run(src, workers=1, workspace=ws)),
                       ("verify", lambda: verify.run(src, ws, args.verify_sample)),
                       ("group", lambda: group.run(src, ws)),
                       ("group_review", lambda: group_review.run(src, ws)),
                       ("rank", lambda: rank.run(folder)),
                       ("recommend", lambda: recommend.run(src, ws, phase="memo"))):
            s = time.monotonic()
            results[st] = fn()
            stage_seconds[st] = round(time.monotonic() - s, 3)
            print(f"[{phase}] {st}: {stage_seconds[st]} s", flush=True)
        end_to_end = round(time.monotonic() - t0, 3)
        conn = store.connect(file_sha, ws)
        jev_calls = conn.execute("""SELECT request_id, role, phase, label_config, model, review_ids, attempt, outcome,
                                    http_status, input_tokens, output_tokens, started_at, seconds, error, run_id
                                    FROM calls WHERE role='enrich' AND run_id=?""", (results["enrich"]["run_id"],)).fetchall()
        status = dict(conn.execute("SELECT status, COUNT(*) FROM record_status GROUP BY status"))
        unique_texts = conn.execute("SELECT COUNT(*) FROM texts").fetchone()[0]
        conn.close()
        for c in jev_calls:
            all_calls.append({"pilot_run": phase, "stage": "enrich", "role": "enrich", "request_id": c[0], "run_id": c[14],
                              "phase": c[2], "label_config": c[3], "model": c[4], "review_ids": json.loads(c[5]),
                              "attempt": c[6], "outcome": c[7], "http_status": c[8], "input_tokens": c[9] or 0,
                              "output_tokens": c[10] or 0, "cache_write_tokens": 0, "cache_read_tokens": 0,
                              "started_at": c[11], "seconds": c[12], "error": c[13]})
        model_calls = 0
        for st, p in claude_logs.items():
            lines = p.read_text(encoding="utf-8").splitlines()[offsets[st]:] if p.exists() else []
            for line in lines:
                c = json.loads(line)
                model_calls += 1
                all_calls.append({"pilot_run": phase, "stage": st, **{k: c.get(k) for k in (
                    "role", "request_id", "run_id", "phase", "label_config", "model", "review_ids", "attempt", "outcome",
                    "http_status", "input_tokens", "output_tokens", "cache_write_tokens", "cache_read_tokens",
                    "started_at", "seconds", "error", "effort", "stop_reason")}})
        m["runs"][phase] = {"stage_seconds": stage_seconds, "end_to_end_seconds": end_to_end, "status_counts": status,
                            "model_calls": model_calls, "enrich_requests": results["enrich"]["requests"],
                            "stage_cache_hits": {k: results[k].get("stage_cache_hits", 0) for k in ("verify", "group_review", "recommend")}}
        m.setdefault("results", {})[phase] = {"enrich": {k: results["enrich"][k] for k in (
            "run_id", "phase", "stop_reason", "requests", "failed_requests", "texts_labeled", "reviews_completed",
            "cache_hit_reviews", "input_tokens", "cost_usd", "wall_clock_seconds")},
            "verify": {k: results["verify"][k] for k in ("verified", "agreement", "requests", "cost_usd")},
            "memo": {k: results["recommend"][k] for k in ("status", "attempts", "requests", "cost_usd", "recommended_area")}}
        if phase == "cold":
            m["input"]["unique_texts"] = unique_texts
            cold_enrich = results["enrich"]
            ver = results["verify"]

    e = settings["enrich"]
    cold = m["runs"]["cold"]
    def attempts(st, phase="cold"):
        return sum(1 for c in all_calls if c["stage"] == st and c["pilot_run"] == phase)
    def failed(st):
        return sum(1 for c in all_calls if c["stage"] == st and c["pilot_run"] == "cold" and c["outcome"] == "failed")
    m["stages"] = {
        "ingest": {"provider": "local code", "model": "-", "settings": "-", "prompt_schema": "-", "batch": "CSV stream",
                   "cold_attempts": 0, "cold_failed": 0, "warm_cache_hits": "-"},
        "enrich": {"provider": "TypeSafe", "model": "jev-1.13.0", "settings": "questions: topic, intent, severity (Choice)",
                   "prompt_schema": cold_enrich and enrich.label_config(settings), "batch": f"{e['reviews_per_request']} reviews/request",
                   "cold_attempts": attempts("enrich"), "cold_failed": failed("enrich"),
                   "warm_cache_hits": f"{m['results']['warm']['enrich']['requests']} new requests",
                   "warm_requests": m["results"]["warm"]["enrich"]["requests"],
                   "tokens_per_text": cold_enrich["tokens_per_text"] if "tokens_per_text" in cold_enrich else
                   round(cold_enrich["input_tokens"] / max(1, cold_enrich["texts_labeled"]), 1),
                   "texts_per_second": round(cold_enrich["texts_labeled"] / max(0.001, cold_enrich["wall_clock_seconds"]), 2)},
        "verify": {"provider": "Anthropic", "model": "claude-haiku-5-5", "settings": "effort low, thinking off",
                   "prompt_schema": "verify-v1 / JSON schema", "batch": "25 reviews/request",
                   "cold_attempts": attempts("verify"), "cold_failed": failed("verify"),
                   "warm_cache_hits": m["runs"]["warm"]["stage_cache_hits"]["verify"], "verified": ver["verified"],
                   "declared_sample": args.verify_sample},
        "group": {"provider": "local code", "model": "-", "settings": "issues-v2 keyword rules", "prompt_schema": "-",
                  "batch": "-", "cold_attempts": 0, "cold_failed": 0, "warm_cache_hits": "-"},
        "group_review": {"provider": "Anthropic", "model": "claude-haiku-5-5", "settings": "effort low, thinking off",
                         "prompt_schema": "group-review-v1 / JSON schema", "batch": "1 request/topic, ≤12 quotes/issue",
                         "cold_attempts": attempts("group_review"), "cold_failed": failed("group_review"),
                         "warm_cache_hits": m["runs"]["warm"]["stage_cache_hits"]["group_review"]},
        "rank": {"provider": "local code", "model": "-", "settings": "-", "prompt_schema": "-", "batch": "-",
                 "cold_attempts": 0, "cold_failed": 0, "warm_cache_hits": "-"},
        "recommend": {"provider": "Anthropic", "model": "claude-sonnet-5-5", "settings": "effort high, adaptive thinking, fallbacks default",
                      "prompt_schema": "memo-v1 / JSON schema", "batch": "1 evidence pack",
                      "cold_attempts": attempts("recommend"), "cold_failed": failed("recommend"),
                      "warm_cache_hits": m["runs"]["warm"]["stage_cache_hits"]["recommend"]},
    }
    (COST / "pilot_measurements.json").write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")
    with (COST / "pilot_calls.jsonl").open("w", encoding="utf-8") as f:
        for c in all_calls:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    with (COST / "usage.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["pilot_run", "stage", "role", "request_id", "attempt", "outcome", "model", "billing_item", "units"])
        for c in all_calls:
            for item in ITEMS:
                w.writerow([c["pilot_run"], c["stage"], c["role"], c["request_id"], c["attempt"], c["outcome"],
                            c["model"], item, int(c.get(item) or 0)])
    # One final status per pilot ID (contract record format, with the original row hash).
    run_dir = REPO / "runs" / m["results"]["cold"]["enrich"]["run_id"]
    recs = {json.loads(l)["review_id"]: json.loads(l) for l in (run_dir / "enriched.jsonl").open(encoding="utf-8")}
    quar = {json.loads(l)["review_id"]: json.loads(l) for l in (run_dir / "quarantine.jsonl").open(encoding="utf-8")}
    with (COST / "pilot_records.jsonl").open("w", encoding="utf-8") as f:
        for row in csv_rows(src):
            rid = row["review_id"]
            rec = recs.get(rid) or quar.get(rid) or {"review_id": rid, "source_sha256": row_sha(row), "status": "pending"}
            rec = {k: v for k, v in rec.items() if k != "internal"}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Pilot saved to {COST}. Now running offline replay...")
    replay(args)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", default="replay", choices=["replay", "pilot"])
    ap.add_argument("--rates", default=str(COST / "rates.csv"))
    ap.add_argument("--assumptions", default=str(COST / "assumptions.yaml"))
    ap.add_argument("--rate-scale", type=float, default=1.0, help="multiply every API rate (arithmetic check)")
    ap.add_argument("--out", default=str(COST / "report.md"))
    ap.add_argument("--verify-sample", type=int, default=20, help="declared verification sample for the pilot")
    args = ap.parse_args()
    if args.command == "pilot":
        pilot(args)
    else:
        replay(args)


if __name__ == "__main__":
    main()
