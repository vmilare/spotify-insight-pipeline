# Project log

Chronological record of what we did, why, what it cost, and what we learned. Newest entries at
the bottom. Decisions also appear in `Plan.md` → Decisions log. Spend is real billed usage
unless marked *estimate*. Per-run spend is tracked automatically in `runs/spend_ledger.csv`.

| Running API spend | Jev | Anthropic | Total |
|---|---|---|---|
| as of last entry | $0.0228 | $0.00 | **$0.0228** |

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
