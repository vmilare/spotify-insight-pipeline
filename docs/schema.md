# Output schema

## Completed record (`grading/records.jsonl.gz`, one line per source review)

| Field | Type | Meaning / producer |
|---|---|---|
| `review_id` | string | Original source ID (unchanged) |
| `source_sha256` | string | SHA-256 of compact UTF-8 JSON of the six original field strings (course `row_sha`) — code |
| `status` | `"completed"` | — |
| `topic` | one of access, usability, playback, downloads, catalog, billing, support, other | Jev Choice |
| `intent` | one of cancellation, complaint, request, praise, unclear | Jev Choice |
| `severity` | integer 1–5 | Jev Choice over the five defined levels |
| `sentiment` | number −1…1 | code: Σ P(intent) × value (`config/sentiment_from_intent.yaml`), clipped |
| `entities` | list of strings | code: feature terms found in the text (keyword list in `pipeline/extract.py`) |
| `evidence_quote` | string | code: exact substring — whole text if ≤ 200 chars, else the sentence with most terms for the topic |
| `needs_review` | boolean | code: Jev confidence < 0.6 on topic/intent/severity, or likely non-English |
| `label_config` | string | `jev-1.13.0+jev-q-tiny-v1-pack10+schema-v1+quote-v1+sent-from-intent-v1` |
| `cache_source_id` | string (optional) | present when the labels were reused from an identical text; points directly to the review whose model call produced them |

## Quarantined record

`review_id`, `source_sha256`, `status: "quarantined"`, `reason` (`empty_review_text` for the 13 empty texts;
`invalid_model_output: …` or `model_call_failed` for other failures — none in the final run). Per-run quarantine logs:
`runs/<run_id>/quarantine.jsonl` (with `attempts`).

## Internal fields (release asset `full_enriched_with_confidences.jsonl.gz`)

`internal.needs_review_reasons` (e.g. `low_confidence_severity`, `non_english_unverified`), `internal.confidence`
(per field, Jev), `internal.probabilities` (topic, intent, severity distributions), `internal.sentiment_source`.

## Other handoff files

| File | Columns / shape |
|---|---|
| `membership.csv` | `issue_id, review_id` — one issue per complaint/cancellation record |
| `ranking.csv` | `rank, issue_id, complaint_count, severity_sum, mean_severity, priority_score` |
| `claims.csv` | `claim_id, issue_id, metric, value` |
| `calls.jsonl.gz` | `request_id, role, review_ids, model, phase, outcome, label_config, input_tokens, output_tokens, run_id, attempt, …` |
| `issues.csv` | `issue_id, topic, name, keywords, members` (taxonomy `config/issues.yaml`, issues-v3) |
| `issue_review.csv` | issue audit by the group role: sampled, misfits, fit_rate, model_suggested_name, model_description |
| `evidence_pack.json` | the memo role's only input (scope, area roll-up, rankings, issue cards with quotes, verification, monthly trend, limitations) |
