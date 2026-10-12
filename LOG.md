# Project log

Chronological record of what we did, why, what it cost, and what we learned. Newest entries at
the bottom. Decisions also appear in `Plan.md` → Decisions log. Spend is real billed usage
unless marked *estimate*. Per-run spend is tracked automatically in `runs/spend_ledger.csv`.

| Running API spend | Jev | Anthropic | Total |
|---|---|---|---|
| as of last entry (from runs/spend_ledger.csv) | see ledger | see ledger | **$0.3218** |

---

## 2026-10-11 — Planning
- Read assignment PDF, `GRADING_CONTRACT.md`, `COST_CALCULATOR.md`, `manifest.json`, `check_submission.py`.
- Taxonomy (8 topics, 5 intents, severity 1–5) is fixed by the course; the user labels data, not categories.
- **Model choices (user):** Jev = primary classifier, no LLM fallback; Claude Haiku 4.5 = verifier;
  Claude Sonnet (high effort) = memo writer. Golden 50 = test set only; a separate hand-labeled
  dev 50 provides examples and thresholds (allowed: "use development records for prompt tuning").
- Plan approved → `Plan.md`. Repo at `~/code/spotify-insight-pipeline` (outside iCloud), public on GitHub.

## 2026-10-11 — Step 1a: ingestion + labeling tools (no API cost)
- `python -m pipeline ingest` read all 660,622 rows in 16 s. All 13 checks vs manifest pass:
  660,609 nonempty · 13 empty (quarantined `empty_review_text`) · 159,701 missing app versions ·
  0 duplicate IDs · 484,189 distinct texts (176,420 reviews reuse an exact text; "Good" alone ×12,845).
- `grading/ingestion.json` is byte-identical to the course checker's `profile` output.
- Dev 50 picked by code from `analysis_10000.csv` rows 501–10,000 (keyword buckets for coverage only).
- Labeling page `labeling/label.html` built and checked in headless Chrome.

## 2026-10-11 — Dev 50 labeled by the user
- `evals/dev_50_labeled.csv`: 50/50 complete and valid. Topics: usability 16, billing 12, other 10,
  playback 5, access 4, catalog 2, support 1, **downloads 0** (gap to fill before tuning).
  Intents: complaint 24, cancellation 10, unclear 7, praise 7, request 2. `needs_review` all false.

## 2026-10-11 — Decision: no translation of non-English reviews
- Estimated non-English share: ~0.7% non-Latin script + ~3.3% Latin-script non-English ≈ 4–6% of distinct texts.
- Translating with Haiku would cost ~$5–10. **User decided: no translation.** Non-English reviews are still
  classified by Jev from the original text (rules require every nonempty review), flagged
  `needs_review` (`non_english_unverified`), and disclosed in README/memo.

## 2026-10-11 — Budget target: $10 total
- User asked whether the whole project can be done for $10. Answer pending measurement (below).

## 2026-10-11 — Jev smoke test + token probe (≈$0.0002)
- Jev API: `POST https://api.typesafe.ai/v1/systemone`, model `jev-1.13.0`, $0.042 per 1M input tokens,
  output free, 80 req/s. One `state` (item) per request; many questions per request allowed.
  We call the HTTP API directly (the SDK auto-retries, which would hide attempts we must log).
- Smoke test: "Downloaded songs stop playing when I go offline." → downloads / complaint / severity 4 /
  sentiment −0.51. Correct. **Billed 891 input tokens** (output tokens are free).
- Probe of where tokens go (same short review; console output — raw call records were not saved):

  | Request content | Billed input tokens |
  |---|---|
  | only topic question | 523 |
  | only intent | 417 |
  | only severity | 440 |
  | only sentiment | 324 |
  | all four (full definitions) | 891 |
  | all four, option names only | 545 |
  | all four, names only + 1-char instructions | 472 |
  | all four, 300-char review | 946 |

- **Learned:** ~270-token fixed overhead per request; question text is billed on every request;
  review length adds ~0.22 tokens/char. Asking all questions in one request is much cheaper than
  separate requests (891 vs ~1,700).
- **Projection (one pass, 484,189 distinct texts):** full definitions ≈ $18; short descriptions ≈ $12.5
  (*estimate*); names only ≈ $9.8 but loses the course's labeling rules. → $10 total is not reachable
  with one review per request.
- Idea to test: put 10 reviews in one request to share the ~270 overhead (undocumented by Jev; docs warn
  unrelated context can lower accuracy).

## 2026-10-11 — Experiment: full vs short descriptions × 1 vs 10 reviews per request ($0.0066)
- Script: `python -m evals.dev_jev_test` · outputs: `evals/results/dev_compare/` (`summary.md`,
  `summary.json`, `predictions.jsonl`, `calls.jsonl` with every request). 110 requests, 0 failures.
- Packing 10 reviews in one request is **not a documented Jev feature**: state = {r1..r10}, each question
  repeated per review with "Answer for review rN only". Worked without errors.
- Results on the 50 dev reviews (human labels = reference). Full-pass $ = one pass over 484,189
  distinct texts, length-adjusted to the corpus mean review length (77 chars).

  | Config | Topic | Intent | Sev. exact | Sev. ±1 | Sev. MAE | Sent. MAE | Tokens/review | Full pass |
  |---|---|---|---|---|---|---|---|---|
  | full, 1/request | 30/50 | 33/50 | 27/50 | 42/50 | 0.64 | 0.18 | 903 | $18.36 |
  | short, 1/request | 32/50 | 35/50 | 28/50 | 44/50 | 0.58 | 0.18 | 837 | $17.02 |
  | full, 10/request | 31/50 | 35/50 | 25/50 | 40/50 | 0.76 | 0.16 | 704 | $14.32 |
  | short, 10/request | 34/50 | 38/50 | 24/50 | 41/50 | 0.72 | 0.16 | 638 | **$12.97** |

- **Learned:**
  1. Short descriptions saved only ~7% of tokens. **Correction:** the earlier "$12.5 with short
     descriptions" estimate was wrong — the contract definitions were already concise; most billed tokens
     are per-request and per-question overhead, not description text.
  2. Packing 10 reviews saves ~22–24% of tokens (shares the per-request overhead) with no visible loss on
     topic/intent; severity slightly worse. With 50 reviews, differences of 1–3 are within noise.
  3. Cheapest measured setup ≈ **$13 for one full pass** → $10 total still not reachable as-is.
  4. Agreement is modest everywhere (topic 60–68%, intent 66–76%, severity exact ~50%, ±1 80–88%).
     About half the reviews have confidence < 0.6 on at least one field.
- **Where Jev and the human disagree (short, 10/request):** topic usability→playback/catalog (6),
  billing→usability (3); intent cancellation→complaint (5); severity 5→3/4 (10 of 13 severity errors).
- **Possible dev-label issue:** 10 dev reviews are labeled severity 5, 8 of them cancellations about
  ads/paywalls/crashes. The contract reserves 5 for *explicit serious financial, privacy or data harm*
  and says cancellation intent and crashes alone don't raise severity. If these are re-checked against
  the rubric, measured severity agreement may change. (Dev labels may be revised; golden labels may not
  be tuned against.)

## 2026-10-11 — Experiment B: tiny wording + sentiment computed from intent ($0.0066, two runs)
- Goal: get one full Jev pass under ~$10 (user chose option B).
- Changes tested: `prompts/jev_tiny_v1.yaml` (keyword-level option descriptions, 3 questions) and no
  sentiment question — sentiment = Σ P(intent) × value, values = mean human dev sentiment per intent
  (`config/sentiment_from_intent.yaml`: cancellation −1.0, complaint −0.55, unclear −0.4, request −0.25,
  praise +0.7). Calibrated and scored on the same dev 50 → the sentiment MAE below is optimistic.
- **Bug found and fixed:** the first run projected $4.71 for 20 reviews/request. The length adjustment fit
  a line through requests of unequal size (20+20+10), confusing review count with review length. Fixed:
  unequal sizes now use measured mean − 0.22 tokens/char × (dev − corpus mean length). Re-ran (+$0.0033);
  outputs in `evals/results/dev_compare_b/` are from the corrected run.

  | Config | Topic | Intent | Sev. exact | Sev. ±1 | Sev. MAE | Sent. MAE | Tokens/review | Full pass |
  |---|---|---|---|---|---|---|---|---|
  | short, no sentiment q, 10/request | 34/50 | 37/50 | 24/50 | 40/50 | 0.76 | 0.26 | 581 | $11.81 |
  | **tiny, 10/request** | 34/50 | 35/50 | 27/50 | 44/50 | 0.62 | 0.25 | 467 | **$9.49** |
  | tiny, 20/request | 32/50 | 37/50 | 27/50 | 44/50 | 0.62 | 0.25 | 462 | $9.40 |
  | *(ref) short + sentiment q, 10/request* | 34/50 | 38/50 | 24/50 | 41/50 | 0.72 | 0.16 | 638 | $12.97 |

- **Learned:**
  1. Keyword-level wording cut ~20% more tokens with no visible accuracy loss on topic/intent/severity.
  2. Dropping the sentiment question saves ~9% but sentiment error rises (MAE 0.16 → 0.25).
  3. 20 vs 10 reviews per request: no meaningful extra saving (each review still needs its own questions).
  4. Jev is not perfectly repeatable: identical reruns differed by 1–3 reviews on some fields. Saved
     results (cache) are what make the final ranking reproducible.
- Projected total with tiny/10: Jev full pass ~$9.5 + retries ~$0.2 + 100/500/10k dev runs ~$0.2 +
  Haiku verify ~$0.3 + Sonnet memo ~$0.5 ≈ **$10.5–11** (estimate). Decision pending with the user.

## 2026-10-11 — Stage 2 built (`pipeline/enrich.py`) and tested on 100 and 500 reviews ($0.0094)
- Setup frozen for these runs: `label_config = jev-1.13.0+jev-q-tiny-v1-pack10+schema-v1+quote-v1+sent-from-intent-v1`
  (`config/settings.yaml`).
- What the stage does: pending distinct texts in a fixed pseudo-random order (a partial run is a fair
  sample) → 10 per Jev request → validate every answer → code builds quote (whole text if ≤200 chars,
  else best sentence for the topic), entities (keyword list) and needs_review (confidence < 0.6 or likely
  non-English) → **one atomic DB commit per request** (results + statuses + call record) → result cache
  keyed by exact text + label_config. Invalid output → retried once → quarantined with reason.
- Cost controls: spend ledger reserves a worst-case estimate before each request and refuses to send
  when spent + reserved + next > cap (run cap and project cap, `config/settings.yaml`, currently $10/$10);
  circuit breaker after 5 consecutive failed requests; Ctrl+C stops admitting work and saves progress.
- Workspaces: `--workspace main` (dev checkpoints + full run share one cache, so these results are reused
  later); a new workspace name = empty cache, for the required cold pilot.
- The ledger was seeded with the earlier experiments ($0.0134, from this log; token count approximate).

  | Run | Requests | Failed | Distinct texts labeled | Cache-hit reviews | Cost | Wall clock | Full-pass projection |
  |---|---|---|---|---|---|---|---|
  | cost_100 (cold) | 10 | 0 | 100 | 0 | $0.0020 | 1.5 s | $9.52 |
  | checkpoint_500 | 38 | 0 | 379 | 112 | $0.0074 | 5.5 s | $9.51 |
  | cost_100 again (warm) | **0** | 0 | 0 | — | **$0.0000** | 0.0 s | — |

- 100-review check: all 100 records valid (labels, ranges, quote is an exact substring, IDs match input).
  Labels: topic other 50 / catalog 13 / usability 12 / billing 10 / playback 10 / downloads 2 / access 2 /
  support 1; intent praise 41 / complaint 40 / cancellation 9 / unclear 6 / request 4; severity 1:47 2:25 3:21 4:7.
  needs_review 30/100 (low-confidence severity 13, topic 11, intent 5; likely non-English 4).
- Throughput ~68 texts/s with 1 worker → full pass ≈ 2 hours at 1 worker (*estimate*).
- Not yet: verification, grouping, ranking, memo (needed for the formal 100-review cost pilot).

## 2026-10-11 — Decision: budget cap $11
- User approved an **$11 project cap** (all API spend together). `config/settings.yaml`: project_cap_usd 11.00;
  run_cap_usd 10.50 for any single run (full Jev pass est. ~$9.50 + retries).
- Planned split (*estimate*): Jev full pass ~$9.50 · retries ~$0.20 · Haiku verification ~$0.30 ·
  Sonnet memo ~$0.50 · spent so far $0.023.
- Clarified: `needs_review` is an indicator only. Flagged reviews stay completed and flow into grouping,
  ranking and memo; the plan adds threshold tuning on dev, flag-vs-error evaluation on golden, and a
  ranking sensitivity check without flagged reviews.

## 2026-10-11 — Golden 50 labeled by the user; dev labels kept
- `evals/golden_50_labeled.csv` (exported 21:29): 50/50 complete and valid, source fields unchanged, every quote an
  exact substring. User flagged needs_review on 0. **Held-out test set**: not used for descriptions, prompts,
  thresholds or sentiment calibration; Jev has not been run on these reviews.
- User reviewed the severity-5 note and kept the dev labels unchanged (decision recorded; affects how dev
  severity agreement should be read).

## 2026-10-11 — Model IDs checked; Anthropic account needs credit
- Checked the current Claude API reference (claude-api skill, cached 2026-10-06): **Claude Haiku 5.5**
  (`claude-haiku-5-5`, $0.10 / $0.50 per M tokens) is the current, cheapest Haiku — 10× cheaper than Haiku 4.5
  ($1 / $5). Verifier switched to Haiku 5.5 (user's original instruction: "the cheapest Claude model").
  Memo: **Claude Sonnet 5.5** (`claude-sonnet-5-5`, $2 / $10), `output_config.effort = "high"`, with server-side
  `fallbacks: "default"` (beta `server-side-fallback-2026-07-01`) so a safety decline is retried on another model.
- Installed `anthropic==1.13.0`, `pydantic==2.14.1`. First test call → HTTP 400 "credit balance is too low";
  key is valid, account has no credit. **No charge.** User to add credit (Settings → Billing).

## 2026-10-11 — Stages 4–5 built: group + rank (code only, $0)
- `config/issues.yaml` (issues-v2): 32 issues across 8 topics. Each completed complaint/cancellation joins exactly
  one issue: its Jev topic selects the list; first issue whose keyword appears in the text wins; else the topic's
  general issue. Code owns membership. (Haiku "group" role will name/audit issues from bounded samples — pending credit.)
- `pipeline/rank.py`: contract baseline (`ranking.csv`: severity_sum, mean half-up 6 dp, tie by issue_id) plus
  `ranking_without_needs_review.csv` (sensitivity), `ranking_actionable.csv` (additional business ranking without
  OTH-GENERAL), `aggregates.csv`, `topic_rollup.csv`.
- `python -m pipeline rerank` twice → **byte-identical `ranking.csv`**, no model calls.
- v1 → v2 change after inspecting the 500 checkpoint: PLY-GENERAL hid crash reports ("black screen",
  "shoutdowning") and won't-play failures → added crash keywords and PLY-WONTPLAY.
- 500-review checkpoint (240 complaint/cancellation records), top baseline issues: OTH-GENERAL 122 · BIL-PAYWALL 113 ·
  USA-ADS 59 · PLY-WONTPLAY 42 · USA-REDESIGN 40. Top issue unchanged without needs_review records.
  OTH-GENERAL = "worst app"-type complaints with no specific defect (correct per contract, not actionable).
  *Small sample — indicative only.*

## 2026-10-11 — Credit added; Stage 3 verify built and tested ($0.0029)
- Anthropic test call OK (`claude-haiku-5-5`, 16 in / 4 out tokens, $0.0000036 — not in the ledger, rounding).
- `cost/rates.csv`: editable, dated rates for Jev, Haiku 5.5, Sonnet 5.5 (input / output / cache write / cache read);
  `pipeline/rates.py` computes cost = billed units × unit price per mutually exclusive item.
- `pipeline/claude.py`: SDK retries off (`max_retries=0`), own bounded retry, every attempt logged with request id,
  usage, cost; budget guard checks project cap before each request; refusal / max_tokens / invalid JSON handled.
- `pipeline/verify.py` + `prompts/verify_v1.md`: Haiku 5.5 (effort low, thinking off, structured JSON) re-labels a
  declared random sample (model-called records, seeded SHA-256 order) from text only, 25 per request, under opaque
  keys; prompt tells it to treat review text as data (injection defense). Code compares.
- Test on checkpoint_500, sample 100 (4 requests, 15 s, $0.0029):
  agreement Jev vs Haiku — topic 84/100, intent 92/100, severity exact 87/100 (±1: 98), sentiment MAE 0.25.
  Planted-error test (synthetic copy, 20 topics falsified): 18/20 caught by the comparison.
  needs_review predicts disagreement: flagged 11/28 (39%) vs unflagged 13/72 (18%).
- Note: Jev agrees more with Haiku (84% topic) than with the human dev labels (~68%) — the two models may share
  readings that differ from the human's; the golden-set evaluation is the reference for accuracy.

## 2026-10-11 — Stage 4b group review (model role "group", Claude Haiku 5.5) ($0.0032)
- `pipeline/group_review.py` + `prompts/group_review_v1.md`: one request per topic (8 requests); each issue's
  rule + up to 12 seeded-sample member quotes under opaque keys → model suggests name/description and lists misfits.
  Membership is not changed (ranking stays model-free and reproducible).
- checkpoint_500: 27 issues reviewed, 156 quotes sampled, 27 misfits → **83% fit**. BIL-PAYWALL 12/12, ACC-LOGIN 6/6,
  USA-ADS 10/12, USA-REDESIGN 10/12. Weakest: small catch-alls (CAT-GENERAL 3/5, BIL-GENERAL 7/10).
  Output: `runs/analysis/checkpoint_500/issue_review.csv`.
- Verify note: the 2 "missed" planted errors were cases where the planted wrong topic ("other") equaled the
  verifier's own choice, so the comparison could not flag them.

## 2026-10-11 — Stage 6 recommend (memo role, Claude Sonnet 5.5, effort high) ($0.0621)
- `pipeline/recommend.py` + `prompts/memo_v1.md`. Code builds `evidence_pack.json` (~5.6k tokens): scope counts,
  area roll-up (access / usability / playback incl. downloads / billing+support / catalog / other), baseline +
  actionable + no-needs_review rankings, top-8 actionable issue cards with 3 quotes each (highest severity, then
  helpful votes), verification summary, limitations. Sonnet returns structured JSON (memo, claims, dashboard
  recommendations). Server-side `fallbacks: "default"` enabled.
- Code checker: every claim's value must equal `ranking.csv`; cited [C#] must exist; review IDs must come from the
  pack; every number in the prose must appear in the pack. One corrective retry allowed.
- checkpoint_500 result: **checker passed on attempt 1**, 11 claims, recommended area **billing/support**
  (BIL-PAYWALL first, USA-ADS second); notes playback has the higher area severity sum (166 vs 150) but is spread
  across smaller issues. 10,459 in / 4,123 out tokens, 32 s. Output: `runs/analysis/checkpoint_500/memo.md`.
  *500-review sample — pipeline test, not the final recommendation.*
- All six stages now run end to end on the 500 checkpoint. Total project spend so far: $0.091.

## 2026-10-11 — Golden-set evaluation (held-out test, $0.001)
- Ran the frozen setup (`jev-q-tiny-v1-pack10`, threshold 0.6, sent-from-intent-v1) on `golden_50_to_label.csv`
  via the normal enrich stage (5 requests, 49 distinct texts, 50 reviews). Then `python -m evals.eval_golden`
  (no model calls) → `evals/results/golden/` (per_case.csv, summary.json, summary.md with confusion tables).
- **Results vs the user's labels:** topic 35/50 · intent 45/50 · both 33/50 · severity exact 36/50, ±1 49/50,
  MAE 0.30 · sentiment MAE 0.31, within 0.5 (predeclared tolerance) 46/50 · evidence quote exact substring 50/50
  (whole text 46/50) · entities not in text 0 · missing/quarantined 0.
- needs_review as a predictor: 7 of 11 flagged had a topic/intent error (64%) vs 10 of 39 unflagged (26%);
  the flag catches 7 of 17 such errors.
- **Golden results did not change the setup.** No descriptions, thresholds or mappings were edited after seeing them.
- Preliminary error-analysis themes (to be written up per case):
  1. Ads boundary: human billing/playback vs Jev usability on ad reviews (contract puts ad interruptions in usability).
  2. App won't open / crashes: human access vs Jev playback (contract: crashes are playback).
  3. Generic "hate this app" complaints: human severity 1 vs Jev 2 (contract: generic criticism = 2) — 6 cases.
  4. Short non-English texts: human other/unclear vs Jev catalog/usability request; 2 of 3 flagged by Jev.
  5. Praise topic: general praise human usability vs Jev other; recommendation praise human playback vs Jev catalog.
  6. Jev rates some billing/usability complaints one level more severe (2→3).
- The labeler left notes on 11 golden cases (mostly unclear / unsupported-language), although none were flagged
  needs_review — treat these as the ambiguous cases in the write-up.

## 2026-10-11 — Step 2: system tests (`python -m evals.system_tests`, ~$0.005 over 3 runs)
- Real pipeline code in throwaway workspaces (`systest-*`); failures simulated in-process; synthetic data never
  reaches business results. Report: `evals/results/system_tests/report.md|json`.
- Pre-work for the pilot: analysis folders are now per workspace; Claude stages (verify, group review, memo) got a
  **stage cache** (exact request → saved validated answer) so a warm rerun makes no new calls.
- **Run 1 found two real bugs:**
  1. Circuit breaker never fired: after a failed request the loop `continue`d past the breaker check → it now
     checks before admitting each request.
  2. Run IDs had 1-second resolution → a capped run and its resume (same second) shared an ID → now milliseconds.
- **Run 2:** A–D passed; E failed only on the benign *control* case (Haiku: other/praise vs expected catalog/praise),
  not on an attack — the test conflated injection resistance with accuracy. Test changed: attack cases pass if the
  injected labels are NOT adopted; accuracy reported separately.
- **Run 3 (final): all 5 pass.**
  A. Simulated 529 ×2 → retried with backoff → 30/30 completed, 2 failed attempts logged.
  B. Simulated outage → breaker stopped after 2 failed requests, 30 pending with reason `model_call_failed`;
     recovery run completed 30/30.
  C. Invalid topic injected into one response (both attempts) → retried once → quarantined
     `invalid_model_output: topic not allowed`; 29 completed.
  D. Run cap $0.0004 → stopped (`budget_cap`) after 1 request ($0.00019); resume completed the other 20 with
     0 completed IDs re-sent.
  E. 4 injection attacks (incl. one mimicking our "Answer for review rN only" packing line): Jev resisted 4/4,
     Haiku 4/4; both matched expected labels 5/5 this run.

## 2026-10-11 — Step 3: formal 100-review cost pilot + calculator ($0.065)
- `cost/calculator.py`: default = offline replay (no key, no network; importing makes no calls); `pilot` = explicit
  paid command. Files in `cost/`: rates.csv, assumptions.yaml, usage.csv, pilot_calls.jsonl, pilot_records.jsonl,
  pilot_measurements.json, report.md, README.md.
- Pilot on `cost_100.csv` (checksum = manifest), fresh workspace `pilot-20261011T215750`, 1 worker, all 7 stages,
  declared verify sample 20. **Cold:** 100/100 completed, $0.064722 (enrich $0.001966 · verify $0.000621 ·
  group review $0.001999 · memo $0.060136), 52.6 s end to end. **Warm:** 0 enrichment requests, 0 downstream model
  calls (stage cache), $0, 0.034 s.
- Arithmetic check: `--rate-scale 2` → measured cost ×2.0, all projections ×2.0, measured and projected time unchanged.

## 2026-10-11 — Step 4: 10,000-review development checkpoint ($0.157)
- `enrich` on analysis_10000.csv, main workspace, **2 workers** (first concurrency step): 798 requests, 0 failed,
  0 invalid, 7,972 texts labeled + 1,138 cache-hit reviews (500 checkpoint + exact duplicates), 57 s,
  139.4 texts/s = 69.7 per worker (≈2.0× the 1-worker 68.5) → concurrency scales linearly at 2.
- Tokens/text stable across refreshes: 468.1 (100) · 467.7 (500) · 468.4 (10k).
- Calculator refreshed (per-worker throughput fix): full run base **$9.79**, conservative $10.63 with exact-text
  reuse; no-reuse $13.33 / $14.44 (over budget → reuse is required). Elapsed ~0.7 h at 4 workers (modeled).
- Free group + rank on 10k (4,480 complaint/cancellation records): actionable top 5 BIL-PAYWALL 1,870 · USA-ADS 1,161 ·
  PLY-GENERAL 765 · PLY-WONTPLAY 737 · USA-GENERAL 676. Without needs_review records BIL-PAYWALL 705 vs USA-ADS 685
  (much closer). Area roll-up: playback+downloads 2,887 · usability 2,752 · billing+support 2,609 severity sum.
  PLY-GENERAL is large → keyword rules worth refining before the final grouping (code only, $0).
- Project spend to date: $0.3218.

## 2026-10-11/12 — Step 5, full run part 1 (planned stop) ($4.746)
- `python -m pipeline enrich --workers 2 --stop-after-requests 24000` on the full file (main workspace).
  Cache lookup: 484,189 pending distinct texts; **129,565 reviews completed from saved results** (texts already
  labeled in the 100/500/10k/golden runs under the same label_config, incl. high-frequency texts like "Good");
  475,697 texts left to call.
- Part 1: 24,000 requests, **0 failed, 0 invalid**, 240,000 texts labeled → 267,494 reviews; 113.0 M input tokens,
  **$4.746**, 29.2 min, 137 texts/s (2 workers), 470.9 tokens/text → full-pass projection $9.58.
- Status after part 1: 397,059 completed · 263,550 pending · 13 quarantined (empty text). Project spend $5.07.
- Part 2 (resume) is reserved for the recorded interrupt/resume demonstration.

## 2026-10-12 — Recorded interrupt/resume demonstration (user screen recording)
- Run 2 (`...20261012T083331875`, phase resume): resumed from 397,059 completed; after ~60 s a SIGINT (same as
  Ctrl+C) was sent → stopped admitting work, finished in-flight requests, exit 0, `stop_reason: interrupted`;
  702 requests, 0 failed, $0.1388. Completed 397,059 → 404,896, nothing lost.
- Run 3 (`...20261012T083441342`, phase resume): `checkpoint_before.json` = 404,896 IDs; after 350 requests,
  3,520 review IDs sent, **0 of them already completed** → no paid relabeling. Left running to completion.

## 2026-10-12 — Dashboard: database, backend, page (Vercel + Neon chosen by the user)
- User created Neon Postgres via Vercel; `DATABASE_URL` in local `.env` (gitignored). Connection verified.
- `pipeline/load_db.py` (`python -m pipeline load-db`): replaces tables `reviews` (one row per source review: status,
  date, rating, likes, topic, area, intent, severity, sentiment, needs_review, issue_id, cache_copy), `issues`,
  `ranking` (baseline / actionable / without_needs_review), `claims`, `evidence` (top 8 quotes per issue), `meta`.
- `web/api/index.py` (FastAPI, Vercel Python function, read-only): /api/health, /summary, /areas, /trend (live SQL over
  reviews), /ranking, /issues/{id}, /recommendations (claims re-checked against ranking in SQL).
- `web/public/index.html`: stat tiles, AI recommendation with claim chips (✓ = equals saved ranking), product-area
  bars, severity mix, issue ranking (actionable / baseline / without needs-review, table view, click → evidence
  quotes), monthly complaint-share trend with crosshair + table view, quality notes, full memo. Palette validated
  with the dataviz validator (light + dark pass; light contrast WARN relieved by value labels + table views).
- Tested locally on the 500-review data: all endpoints 200, bad input → 404/422; light/dark screenshots checked;
  375 px phone width: no horizontal overflow.

## 2026-10-12 — Full run complete
- Run 3 (`...20261012T083441342`, resume) finished: 22,868 requests, **0 failed, 0 invalid**, 228,677 texts →
  255,713 reviews, $4.5226, 32.4 min, 117.7 texts/s (2 workers).
- **Final status: 660,609 completed · 0 pending · 13 quarantined (`empty_review_text`) of 660,622.**
- Three enrichment runs on the full file: initial 24,000 requests ($4.7465) · interrupted resume 702 ($0.1388) ·
  final resume 22,868 ($4.5226) → **47,570 Jev requests, 0 failures, $9.4078**; plus 129,565 reviews completed from
  earlier same-config results (cache) at no cost. Tokens per text 470.9 (projection was 468.4: +0.5%).
- Project spend after the full run: **$9.73 of the $11 cap**.
- Vercel: site deployed at https://spotify-insight-pipeline.vercel.app ; static page OK but `/api/*` returned 404
  (project preset "Other" serves static files only). Backend moved to the zero-config layout `web/app.py`;
  user is redeploying with the FastAPI preset.

## 2026-10-12 — Issue taxonomy v3 on the full data (code only, $0)
- Full-data grouping with issues-v2: 290,720 complaint + cancellation records; catch-alls large (PLY-GENERAL 17,297,
  USA-GENERAL 16,111, BIL-GENERAL 12,158, DWN-GENERAL 3,893, ACC-GENERAL 3,083).
- Inspected the most frequent two-word phrases inside each catch-all (4,000-review samples) → missed spellings and
  phrasings: "adds" (ads), "to pay / pay for / basic features / for money / for free" (paywall), "can't listen /
  can't even play / random songs" (won't play), "can't download / sd card" (downloads), "no internet connection /
  logging in / log back / phone number" (access).
- issues-v3: added those phrases; new DWN-FAILS, DWN-STORAGE, ACC-NOCONNECTION (33 issues). Purpose: describe what the
  complaints say; the top of the ranking did not change order.
- v2 → v3 priority (actionable top): BIL-PAYWALL 109,104 → 118,521 · USA-ADS 74,924 → 87,029 · PLY-WONTPLAY 46,313 →
  58,604 · PLY-GENERAL 56,067 → 46,627 · USA-GENERAL 42,159 → 32,498 · BIL-GENERAL 34,333 → 25,732.
  v2 rankings kept for comparison in `data/` (local) and summarized here.

## 2026-10-12 — Full-data analysis: verify, group review, rank, memo, database load
- **Verify** (Haiku 5.5, declared random sample 500, 20 requests, $0.0147): Jev vs verifier topic 413/500, intent
  462/500, severity exact 378/500 (±1 480), sentiment MAE 0.27. Planted-error test: 96/100 caught. needs_review
  predicts disagreement: flagged 73/192 (38%) vs unflagged 45/308 (15%).
- **Group review** (Haiku 5.5, 8 requests, $0.0051): 33 issues, 396 sampled quotes, 65 misfits → 84% fit.
- **Rank** (code): actionable top 5 BIL-PAYWALL 118,521 · USA-ADS 87,029 · PLY-WONTPLAY 58,604 · PLY-GENERAL 46,627 ·
  USA-REDESIGN 34,446. **Without needs_review records the order changes:** USA-ADS 50,429 > BIL-PAYWALL 43,217 >
  PLY-WONTPLAY 32,883 → the paywall's lead depends on flagged labels. Area severity sums: playback (incl. downloads)
  193,130 · usability 174,227 · billing/support 154,065 · access 45,817.
- **Memo** (Sonnet 5.5, high effort, 1 request, $0.0671, 32 s): checker **passed on attempt 1**, 12 claims.
  Recommended area **playback** (PLY-WONTPLAY + PLY-GENERAL: fixable defects, highest area severity); paywall treated
  as a parallel packaging review (business-model question, sensitive to needs_review); ads on watch; ACC-LOGIN as a
  small targeted fix. Different from the 500-sample memo (billing/support) — the full data changes the area picture.
- **Database** (Neon): 660,622 review rows, 33 issues, 98 ranking rows, 12 claims, 264 evidence quotes; 160 MB.
- Vercel: backend now deployed (FastAPI preset); returns "DATABASE_URL not configured" → env var to be added in Vercel.
- Project spend: **$9.8165** of $11.

## 2026-10-12 — Dashboard live
- User added `DATABASE_URL` in Vercel and redeployed (FastAPI preset, root `web`).
- Live checks (https://spotify-insight-pipeline.vercel.app): page 200; /api/health, summary, areas, trend, ranking ×3,
  issues/{id}, recommendations all 200; unknown issue → 404. First-call latency 0.06–2.2 s (trend scans all 660k
  rows), cached repeat calls ~0.04 s. Health: 660,622 reviews, 33 issues, 264 evidence quotes served from Neon.
- Visual check (headless Chrome, light theme, full data): tiles, recommendation with ✓ claim chips, area bars,
  severity mix, issue ranking, monthly trend with end labels, quality notes all render.

## 2026-10-12 — grading/ export + course self-check: PASS
- `python -m pipeline export-grading` (no model calls) → grading/: run.json, ingestion.json, records.jsonl.gz (660,622),
  membership.csv, ranking.csv, claims.csv, calls.jsonl.gz (48,450 calls: 47,570 full-run + 868 from the 100/500/10k/golden
  runs whose results seeded the exact-text cache + 20 verify + 8 group + 1 memo... plus earlier same-config enrich runs),
  checkpoint_before.json (397,059 = state at the start of the recorded demo), checkpoint_after.json (660,609).
- `check_submission.py reference` + `check` (report kept outside grading/ in data/): **status pass, issue_counts empty**.
  Coverage: 660,622 received, 0 missing/duplicate/invalid, 660,609 valid completed, 13 quarantined, 176,420 valid cache
  reuses, working coverage point candidate 1.0. Reported tokens in 228,071,780 /
  out 91,121,600 (Jev output tokens are reported by the API but free).

## 2026-10-12 — Memo regenerated with per-issue verification evidence (memo-v2, $0.0772)
- While preparing the README trace, the verify sample showed topic agreement differs sharply by issue: USA-ADS 35/37,
  BIL-PAYWALL 35/44 (9 → usability), **PLY-WONTPLAY 11/20 (7 → usability: free-tier "can't play the song I want")**,
  **PLY-GENERAL 2/12**. By area (complaints in sample): usability 65/74 same area, billing/support 45/57, playback 34/53.
- memo-v1 (playback) had only overall verifier agreement in its evidence pack. Added `verification_breakdown()` to the pack
  and rule 6 to the prompt (`prompts/memo_v2.md`): weigh per-issue/area label reliability. Regenerated once:
  checker passed on attempt 1, 12 claims. **Recommended area: usability** (USA-ADS + USA-REDESIGN; paywall handled jointly
  with ads; playback needs human re-labeling before committing a quarter).
- Kept for transparency: `memo_v1.md`, `claims_v1.csv`, `recommendations_v1.json` in runs/analysis/spotify_reviews_18months/.
- Finding: the recommendation moved billing (500 sample) → playback (full data, memo-v1) → usability (full data + label
  reliability, memo-v2). The top areas are close; the answer depends on how much weight uncertain labels get. Stopped
  regenerating; the choice of memo to present is the user's.
- DB reloaded, grading/ re-exported (48,451 calls incl. both memo calls), self-check pass (no issues). Live API serves memo-v2.
- Project spend: $9.8937.

## 2026-10-12 — Wrap-up
- README rewritten as the grader's entry point (results, architecture diagram, trace of review 4b5220da…, ambiguous case,
  golden error analysis, system tests, resume evidence, calculator, ranking sensitivity and trend, limitations, rubric map,
  setup and commands). Final memo copied to `memo.md`. `.env.example` gained a blank `DATABASE_URL`.
- Secret scan over the working tree and all git history: no keys or credentialed URLs; `.env` ignored and untracked.
- GitHub release v1.0: `full_enriched_with_confidences.jsonl.gz` (90 MB), `grading_export.zip` (112 MB).
- Signed-out access check: repository, README, grading folder, memo, release and assets, live dashboard and API all public.
- Total API spend: $9.89 of the $11 cap.
- Open for the author: choose the memo to present (memo-v2 usability vs the late-2023 billing surge not in its pack),
  final read-through, submit the repository URL on bCourses.
