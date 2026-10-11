# Spotify Review Insight Pipeline

Haas MBA 290T1 final project: a multi-agent pipeline that turns 660,622 Spotify Google Play reviews
(May 2022 – Nov 2023) into a product-priority recommendation with traceable evidence.

> 🚧 Work in progress. See [`Plan.md`](Plan.md) for the build status and the full plan.

## Setup
```sh
python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # set DATA_DIR to the folder holding spotify_reviews_18months.csv; add only keys you use
```
Raw data is not committed. Source: course ZIP (Kaggle "3.4 Million Spotify Google Store Reviews" v2, CC0),
`spotify_reviews_18months.csv`, 97,400,616 bytes, SHA-256
`1fc85de68a304dd8978b537cfa58793d5f41cbaf417fa32cb53899f83a2fcef6`.

## Commands (so far)
| Command | What it does | Model calls |
|---|---|---|
| `python -m pipeline ingest [--input CSV]` | Stage 1: parse, hash, profile, dedup, quarantine empties, queue pending | none |
| `python -m labeling.select_dev` | Pick the 50 development reviews to hand-label | none |
| `open "labeling/label.html?set=dev_50"` | Local labeling page (works offline from the file) | none |

## Ingestion result (full file)
660,622 rows · 660,609 nonempty · 13 empty texts quarantined (`empty_review_text`) · 159,701 missing
app versions · 0 duplicate IDs · 484,189 distinct nonempty texts (176,420 reviews reuse an exact text).
All counts match `manifest.json`; details in
[`runs/ingest/spotify_reviews_18months/ingestion_report.json`](runs/ingest/spotify_reviews_18months/ingestion_report.json).
