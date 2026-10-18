# Cost and runtime calculator

Required deliverable (see the course's `COST_CALCULATOR.md`). Two separate commands:

| Command | Paid? | What it does |
|---|---|---|
| `python cost/calculator.py` | **No** (default) | **Offline replay.** Recomputes the measured pilot cost from `usage.csv` × `rates.csv`, shows estimate refreshes from the 500/10,000 checkpoints, projects the full run (base / conservative, with / without exact-text reuse), checks the budget, writes `report.md`. No API key, no network. Importing the module makes no calls. |
| `python cost/calculator.py --rate-scale 2 --out /tmp/report_x2.md` | No | Same replay with every API rate multiplied — arithmetic check (API cost doubles; measured time and projected time do not change). |
| `python cost/reconcile.py` | No | **Provider reconciliation.** Compares every saved call record with the providers' own usage exports (`provider_usage/`) by UTC hour (Jev) and day (Claude), and writes `reconciliation.md`. No API key, no network. |
| `python cost/calculator.py pilot` | **Yes** (~$0.07) | Runs the real pipeline on `cost_100.csv` (checksum verified against the manifest) in a fresh, empty workspace with 1 worker: ingest → enrich (Jev) → verify (Claude Haiku 5.5, declared sample of 20) → group → group review (Haiku) → rank → memo (Claude Sonnet 5.5). Then repeats it warm (saved results; expected 0 new model calls). Saves the evidence below and runs the replay. Needs `TYPESAFE_API_KEY` and `ANTHROPIC_API_KEY` in `.env`. |

## Files

| File | Contents |
|---|---|
| `rates.csv` | Editable, dated price per billing unit (Jev, Haiku 5.5, Sonnet 5.5) with source links |
| `assumptions.yaml` | Editable projection inputs: volumes, scenario retry rates, verify sample, memo calls, budget, max workers, fallback fraction, output-token caps |
| `usage.csv` | One row per attempted call × billing item (`pilot_run` cold/warm, stage, request id, model, units) — maps every charged item to the call log |
| `pilot_calls.jsonl` | Every attempted call in the cold and warm pilot runs: role, model, label_config, review IDs sent, outcome, raw usage, timing, run and request IDs |
| `pilot_records.jsonl` | One final record per pilot ID (contract format, original row hash, common labels) |
| `pilot_measurements.json` | Stage settings, wall-clock per stage and end to end (cold and warm), statuses, cache hits |
| `pilot_ingest/` | Ingestion report for `cost_100.csv` in the pilot workspace |
| `report.md` | Generated report (measured pilot, refreshes, projections, controls, rates) |
| `provider_usage/` | Provider usage exports downloaded 2026-10-18 00:45 UTC, sanitized to this project's API key: `typesafe_usage.csv` (hourly), `anthropic_console_usage.csv` (daily) |
| `reconciliation.md` | Generated reconciliation: provider export vs our call logs, every difference explained or marked pending |

Cost formula: `item_cost = billed_units × usd_per_unit / unit_size` for mutually exclusive items (uncached input,
output incl. thinking, cache write, cache read); `total = Σ item_cost`. Missing rates are reported, never zeroed.
Local compute is reported as unknown (not measured), separately from API spend.
