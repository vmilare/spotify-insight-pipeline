# Plan.md — living build reference

This file is the shared reference for what is being built. **Status checklist first**, then the
approved plan (copied verbatim from the planning session on Oct 11, 2026). Updated as each piece lands.

## Decisions log
- **Oct 11 — Non-English reviews: no translation** (cost). They are still classified by Jev from the
  original text (required: every nonempty review must be classified; ~4–6% of distinct texts, ~$1 of Jev
  usage). A free offline language detector flags them `needs_review=true`, reason `non_english_unverified`.
  README and memo disclose the count and show the ranking with and without them.

- **Oct 11 — Budget cap $11** for all API spend (project_cap_usd in `config/settings.yaml`).
- **Oct 11 — `needs_review` is an indicator, not a filter**: flagged reviews stay in all analyses; sensitivity check without them.

## Status checklist

Legend: ✅ done · 🔄 in progress · ⬜ todo · 👤 needs the user

### Step 1 — Oct 11
- ✅ 1a Repo, `.gitignore` (committed first), `.env.example`, Python 3.13 venv, `requirements.txt`
- ✅ 1a Ingestion stage — `pipeline/ingest.py`, run with `python -m pipeline ingest`
  - Full file: 660,622 rows · 660,609 nonempty · 13 empty (quarantined `empty_review_text`) ·
    159,701 missing app versions · 0 duplicate IDs · 484,189 distinct texts — **all 13 manifest checks pass**
  - Report: `runs/ingest/spotify_reviews_18months/ingestion_report.json`
  - `grading/ingestion.json` is byte-identical to `check_submission.py profile` output
- ✅ 1a Shared label definitions draft — `config/labels.yaml` (labels-v1)
- ✅ 1a Dev-50 selection — `labeling/select_dev.py` → `labeling/dev_50_to_label.csv` (analysis_10000 rows 501–10,000; golden + checkpoint_500 excluded and asserted)
- ✅ 1a Labeling page — `labeling/label.html?set=dev_50` (also `?set=golden_50` for later)
- ✅ 1b User labeled dev 50 → `evals/dev_50_labeled.csv` (50/50 valid; no `downloads` examples yet → add a few dev downloads cases before tuning)
- ✅ 1c User added `TYPESAFE_API_KEY` to `.env`
- ✅ 1c Jev client + dev experiments (see LOG.md) → frozen setup `jev-q-tiny-v1-pack10`
- ✅ 1c Stage 2 enrich built; tested on cost_100 (cold + warm) and checkpoint_500 → `runs/`, `runs/spend_ledger.csv`
- ✅ Stages 4–5 group + rank (code) built; rerank reproducible (LOG.md)
- ✅ Anthropic credit added
- ✅ Verify (Haiku 5.5) + group review (Haiku 5.5) + memo (Sonnet 5.5) built; all 6 stages run end to end on checkpoint_500
- ✅ Golden-set evaluation (topic 35/50, intent 45/50, severity 36/50) → `evals/results/golden/`
- ✅ System tests A–E pass (retry, breaker+recovery, malformed→quarantine, budget cap+resume, injection) → `evals/results/system_tests/`
- ✅ Formal 100-review cold/warm pilot + calculator (offline replay, rate-scale check) → `cost/`
- ✅ 10,000-review checkpoint (2 workers) + estimate refresh → full run est. $9.79 base / $10.63 conservative
- ✅ Budget cap: $11 project / $10.50 per run (user, Oct 11)
- ✅ Severity-5 dev labels reviewed by user; kept as is

### Step 2–3 — Oct 12 (done)
- ✅ Golden 50 labeled; golden evaluation → `evals/results/golden/`
- ✅ System tests A–E pass → `evals/results/system_tests/`
- ✅ Cost pilot + calculator → `cost/`; 10k checkpoint refresh
- ✅ Full run: 660,609 classified, 13 quarantined, 0 pending, 0 failed calls; recorded interrupt/resume → `evals/resume_demo.mov`
- ✅ Issues v3, verify 500, group review, ranking, memo-v2 (memo-v1 kept) → `memo.md`
- ✅ Dashboard live: https://spotify-insight-pipeline.vercel.app (Vercel FastAPI + Neon Postgres)
- ✅ `grading/` export; course self-check pass (no issues)
- ✅ README with rubric → evidence map; release v1.0 with large files
- ⬜👤 Final review by the author (memo choice incl. late-2023 billing trend), signed-out link check, submit URL on bCourses

---

# Approved plan (v4)

> **Execute now: Step 1a only** (user decision). Stop after 1a and hand the user the labeling-page
> location + how to open it. 1b/1c and later steps wait for the user.
>
> 1a deliverables: repo at `~/code/spotify-insight-pipeline` + GitHub repo; `Plan.md` (this plan +
> status checklist); `.gitignore`, `.env.example`, `requirements.txt`, Python 3.13 venv;
> `pipeline/ingest.py` → `runs/ingest/ingestion_report.json` + SQLite, verified against manifest and the
> checker's `profile`; `labeling/select_dev.py` → `labeling/dev_50_to_label.csv` (analysis_10000 rows
> 501–10,000, stratified with keyword heuristics only — no model); `labeling/index.html` (local page,
> loads the CSV, shows contract definitions, saves `dev_50_labeled.csv`); `config/labels.yaml` draft.

## Context
Haas MBA 290T1 final project, due **Oct 13, 2026, 11:59pm PT** (today Oct 11 → ~2.5 days).
Goal: a multi-agent pipeline that turns all 660,622 Spotify reviews into a product-priority
recommendation (access / usability / playback / billing-support) with traceable evidence.
Deliverable = one public GitHub repo + a deployed dashboard (backend + database).
Binding specs in the dataset folder (`Final Assignment - Spotify Reviews Dataset/`):
`GRADING_CONTRACT.md`, `COST_CALCULATOR.md`, `check_submission.py` (zero-API checker, has `row_sha`
and `profile` helpers to reuse), `manifest.json`. Taxonomy (8 topics, 5 intents, 1–5 severity) is
fixed by the course.

**First build action after approval:** create `Plan.md` at the repo root — this plan plus a living
status checklist (per step: todo / in progress / done, with links to code and outputs).

---

## Final outputs (what exists when we're done)

**A. Submission**
1. Public GitHub repo URL (submitted on bCourses); README is the entry point.
2. Live dashboard URL (Render) + access instructions in README.

**B. Business result**
3. `memo.md` — recommended priority, supporting counts/severity, alternatives, representative
   review IDs, limitations; every number cites a `claims.csv` claim ID.
4. Dashboard: overall metrics, issue ranking, AI recommendation with clickable evidence
   (claim → issue → sample reviews), served by the backend from Postgres.
5. `issues.csv`, `ranking.csv`, `aggregates.csv`, `claims.csv`.

**C. Processed data (full run)**
6. `data_manifest.json`, `ingestion_report.json` (verified vs manifest: 660,622 rows, 13 empty texts,
   159,701 missing versions, 0 duplicate IDs, 484,189 distinct texts).
7. `enriched.jsonl`, `quarantine.jsonl`, `membership.csv`.
8. `run_log.jsonl`, `run_summary.json` (timing, statuses, attempts, failures, usage, cost, limits).

**D. Labels & evaluation**
9. `config/labels.yaml` (definitions + worked examples); versioned Jev question sets / prompts.
10. `evals/dev_50_labeled.csv` and `evals/golden_50_labeled.csv` (both labeled by the user).
11. Golden evaluation: topic/intent agreement, severity exact + MAE, sentiment MAE, quote check,
    confusion tables, per-case pass/fail, error analysis. Plus dev before/after comparison
    (bare definitions vs definitions + examples).
12. Verifier report, planted-error test, injection test, interruption/resume evidence.

**E. Cost calculator (`cost/`)** — offline replay default, separate paid pilot command, real
100-review cold/warm pilot, `rates.csv`, `usage.csv`, `report.md` with projections and controls.

**F. Grading export (`grading/`)** — the 9 contract files, passing `check_submission.py`.

**G. Code** — pipeline CLI (any CSV in), rerank-without-models, backend, dashboard, DB loader,
`.env.example`, `.gitignore`, `requirements.txt`, README (architecture diagram, traced review,
failure case, results, limitations).

---

## Human labeling (user's tasks — Claude never fills in golden labels)
1. **Dev 50** from `analysis_10000.csv` rows 501–10,000 (disjoint from cost_100, checkpoint_500,
   golden), stratified across topics/intents + hard cases. Allowed by the brief ("use development
   records for prompt tuning"; "choose thresholds using development examples"). ~20 → worked
   examples in Jev descriptions; ~30 held out to measure and set the needs_review threshold.
   Claude may pre-draft dev labels for the user to correct (dev only).
2. **Golden 50** (`golden_50_to_label.csv`): labeled by the user from scratch; never in
   descriptions, prompts or thresholds.
3. Local labeling page: one review at a time, dropdowns, definitions on screen, quote by
   highlighting; exports CSV in the template's columns.

## Model strategy
| Role | Model | Task | Est. cost |
|---|---|---|---|
| enrich | **Jev** `jev-1.13.0` (TypeSafe `/v1/systemone`, $0.042/M input, output free, 80 req/s) | 1 review/request, questions batched: topic, intent, severity (Choice), sentiment (Score 0–4 → s/2−1), evidence-sentence Choice for long reviews | ~$15–25 |
| verify | **Claude Haiku 4.5** `claude-haiku-4-5-20251001` | Blind re-label of random sample (1,000) + planted-error + injection tests | ~$1 |
| group | **Jev** | Assign each complaint/cancellation to one issue from user-approved per-topic list | ~$3 |
| memo | **Claude Sonnet, high effort** (confirm ID/price/effort param via claude-api docs) | Memo + dashboard recommendations from ranking + bounded evidence pack | ~$1–2 |

- No LLM fallback: low Jev confidence → keep label, `needs_review=true` + reason. Invalid → retry
  once → quarantine with reason + attempts.
- Code (no model): ingest/profile, dedup cache, entity lexicon, short-review quote = full text,
  quote check, schema validation, ranking, claim checking.
- Total est. ~$20–30, replaced by measured 100 → 500 → 10k numbers. Spend caps: $5 for all
  development runs; $40 hard cap for the full run (editable in `config/settings.yaml`).

## Pipeline stages
| Stage | Owner | Output |
|---|---|---|
| 1 Ingest | code | SQLite (raw strings + `row_sha`), ingestion report, dedup map, 13 empties quarantined |
| 2 Enrich | Jev + code | validated records, atomic per-batch commits, cache by text + `label_config`, `cache_source_id` for duplicates |
| 3 Verify | Haiku + code | verifier labels, disagreement report, planted-error + injection results |
| 4 Group | code + Jev | `issues.csv`, `membership.csv` |
| 5 Rank | code only | `aggregates.csv`, `ranking.csv` |
| 6 Recommend | Sonnet + code checker | `memo.md`, `claims.csv`, dashboard recommendations |

Controls: spend ledger with pre-dispatch reservation, global rate limiter, max workers, bounded
backoff + jitter, stop-on-cap with saved progress, `resume` dispatches only pending IDs.

## Repo
- Location: `~/code/spotify-insight-pipeline` (outside iCloud — sync can corrupt `.git` and a
  busy SQLite file). Dataset stays in the iCloud class folder, referenced via `DATA_DIR` in `.env`.
- GitHub: `vmilare/spotify-insight-pipeline`, public, created with `gh` (already authenticated).
  `.gitignore` (.env, .env.*, !.env.example, data/, *.sqlite, .venv/) committed before anything else.
- Python 3.13 venv (`/opt/homebrew/bin/python3.13`; 3.14 skipped for package compatibility).
```
spotify-insight-pipeline/
  Plan.md README.md memo.md .env.example .gitignore requirements.txt
  config/ prompts/ pipeline/ labeling/ cost/ evals/ runs/ grading/ backend/ dashboard/
```
Commands: `python -m pipeline run --input <csv>`, `resume`, `rerank` (no model calls),
`export-grading`; `python cost/calculator.py` (offline) / `python cost/calculator.py pilot` (paid).

## Deployment
Render (FastAPI: JSON API + dashboard page) + Neon free Postgres; load script pushes records,
aggregates, ranking, issues, memo. No paid calls from the dashboard.

## Sequence
**Step 1 — Oct 11 (today)**
- 1a (no keys needed): create repo + `Plan.md`, `.gitignore`, `.env.example`, venv; ingest + profile
  full CSV and verify against manifest; select dev 50; build labeling page; draft `labels.yaml`.
- 1b (user): label dev 50 (~30–45 min) on the labeling page.
- 1c (needs TYPESAFE key): Jev question set; dev before/after test; 100-review cold/warm pilot;
  calculator v1.

**Step 2 — Oct 12:** user labels golden 50; tune descriptions/threshold on dev; 500 → 10k runs,
refresh estimates; full run in background with interrupt/resume demo (user screen-records);
verifier + planted/injection tests; backend/dashboard/DB in parallel (needs Render + Neon accounts).

**Step 3 — Oct 13:** golden eval; group → rank → memo (needs ANTHROPIC key); load DB + deploy;
export grading/ + checker; README; push and signed-out link check.

## What the user provides, and when
| When | Item |
|---|---|
| Now | Approve plan (repo location/name/public, spend caps above) |
| Before 1c | `TYPESAFE_API_KEY` typed into `.env` by the user (never pasted in chat); Jev credits checked |
| During step 1 | ~30–45 min to label dev 50 |
| Step 2 | Golden 50 labels; Render + Neon accounts (free); QuickTime recording during resume demo |
| Before step 3 | `ANTHROPIC_API_KEY` in `.env` with a few dollars of credit |

## Verification
- Ingestion profile equals `manifest.json` counts and the checker's `profile` output
- `check_submission.py profile / reference / check` on grading/ → status `pass`
- `rerank` twice → byte-identical ranking.csv
- calculator: doubling rates doubles API subtotal, time unchanged; warm pilot = 0 enrichment calls
- dashboard numbers match ranking.csv; every memo number matches claims.csv
