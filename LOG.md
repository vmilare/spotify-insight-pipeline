# Project log

Chronological record of what we did, why, what it cost, and what we learned. Newest entries at
the bottom. Decisions also appear in `Plan.md` → Decisions log. Spend is real billed usage
unless marked *estimate*.

| Running API spend | Jev | Anthropic | Total |
|---|---|---|---|
| as of last entry | $0.0068 | $0.00 | **$0.0068** |

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
