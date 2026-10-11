"""Select the 50-review development set for hand labeling (code only, no model calls).

Pool: analysis_10000.csv rows 501-10,000, i.e. excluding checkpoint_500 (and therefore cost_100).
The golden 50 are disjoint from analysis_10000 by construction; this is re-checked below.
Keyword buckets only make the sample cover rare topics and hard cases. They are NOT labels:
the human assigns every label, and bucket names are kept out of the labeling page.

Usage:  python -m labeling.select_dev
Writes: labeling/dev_50_to_label.csv, labeling/dev_50_selection.json, labeling/sets/dev_50.js
"""
import csv
import hashlib
import json
import re
from pathlib import Path

import yaml

from pipeline.paths import CONFIG_DIR, dataset_file
from tools.check_submission import FIELDS, csv_rows, row_sha, sha

HERE = Path(__file__).resolve().parent
SEED = "spotify-insight-dev50-v1"
LABEL_COLUMNS = ["topic", "intent", "sentiment", "severity", "entities", "evidence_quote", "needs_review"]

# (bucket, target count, predicate on lowercased text). Order matters: earlier buckets pick first.
BUCKETS = [
    ("access", 5, r"\b(log ?in|logged out|log out|sign ?in|sign ?up|password|account|hacked)\b"),
    ("support", 3, r"\b(customer (service|support)|support team|contact(ed)? (spotify|support)|help ?desk)\b"),
    ("downloads", 4, r"\b(download\w*|offline)\b"),
    ("billing", 6, r"\b(premium|price|pay(ing|ment)?|charged?|subscription|money|trial|refund)\b"),
    ("catalog", 5, r"\b(lyrics?|search|recommend\w*|podcasts?|not available|missing songs?|artist)\b"),
    ("playback", 6, r"\b(crash\w*|stops?|stopped|lag\w*|won'?t play|buffer\w*|skips?|freez\w*|battery|bluetooth)\b"),
    ("usability", 6, r"\b(ads?|adverts?|shuffle|layout|interface|ui|navigation|queue|button|design)\b"),
    ("cancellation", 4, r"\b(uninstall\w*|cancel\w*|delet\w*|switch(ing)? to|leaving|goodbye|bye)\b"),
    ("boycott_or_offtopic", 2, r"\b(boycott|sweden|swedish|quran|qur'?an)\b"),
    ("non_english", 2, None),   # mostly non-ASCII letters
    ("long_mixed", 3, None),    # > 300 chars
    ("short_praise", 4, None),  # <= 4 words
]


def order_key(review_id):
    return hashlib.sha256(f"{SEED}:{review_id}".encode()).hexdigest()


def non_english(text):
    letters = [c for c in text if c.isalpha()]
    return len(letters) >= 8 and sum(ord(c) > 127 for c in letters) / len(letters) > 0.5


def matches(bucket, pattern, text):
    low = text.lower()
    if pattern:
        return re.search(pattern, low) is not None
    if bucket == "non_english":
        return non_english(text)
    if bucket == "long_mixed":
        return len(text) > 300
    if bucket == "short_praise":
        return len(text.split()) <= 4
    return False


def main():
    analysis = list(csv_rows(dataset_file("analysis_10000.csv")))
    checkpoint_ids = {r["review_id"] for r in csv_rows(dataset_file("checkpoint_500.csv"))}
    golden_ids = {r["review_id"] for r in csv_rows(dataset_file("golden_50_to_label.csv"))}
    assert [r["review_id"] for r in analysis[:500]] == [r["review_id"] for r in csv_rows(dataset_file("checkpoint_500.csv"))]

    pool = analysis[500:]
    assert len(pool) == 9500
    assert not (golden_ids & {r["review_id"] for r in pool}), "golden reviews must never enter the dev pool"
    assert not (checkpoint_ids & {r["review_id"] for r in pool})

    pool.sort(key=lambda r: order_key(r["review_id"]))
    chosen, buckets = [], {}
    for bucket, target, pattern in BUCKETS:
        taken = 0
        for row in pool:
            if taken == target:
                break
            if row["review_id"] in buckets or not matches(bucket, pattern, row["review_text"]):
                continue
            buckets[row["review_id"]] = bucket
            chosen.append(row)
            taken += 1
        if taken < target:
            raise SystemExit(f"bucket {bucket}: only {taken}/{target} candidates")
    assert len(chosen) == 50

    # Present in a neutral hashed order so buckets are not visible while labeling.
    chosen.sort(key=lambda r: order_key("present:" + r["review_id"]))

    with (HERE / "dev_50_to_label.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(list(FIELDS) + LABEL_COLUMNS)
        for row in chosen:
            writer.writerow([row[k] for k in FIELDS] + [""] * len(LABEL_COLUMNS))

    analysis_path = dataset_file("analysis_10000.csv")
    (HERE / "dev_50_selection.json").write_text(json.dumps({
        "seed": SEED,
        "source": {"file": "analysis_10000.csv", "sha256": sha(analysis_path), "rows_used": "501-10000"},
        "method": "Keyword buckets for coverage, then lowest SHA-256(seed:review_id) within each bucket. "
                  "Buckets are sampling aids only, not labels. No model calls.",
        "excluded": ["checkpoint_500.csv (first 500 rows, includes cost_100.csv)", "golden_50_to_label.csv"],
        "buckets": [{"bucket": b, "target": n, "pattern": p} for b, n, p in BUCKETS],
        "selected": [{"review_id": r["review_id"], "source_sha256": row_sha(r), "bucket": buckets[r["review_id"]]}
                     for r in chosen],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    write_label_set("dev_50", "Development set (50) — used for Jev examples and threshold tuning", chosen)
    print(f"Selected {len(chosen)} dev reviews -> labeling/dev_50_to_label.csv")


def write_label_set(name, title, rows):
    """Embed reviews + shared definitions as a JS file so the page works from file:// with no server."""
    labels = yaml.safe_load((CONFIG_DIR / "labels.yaml").read_text(encoding="utf-8"))
    (HERE / "sets").mkdir(exist_ok=True)
    payload = {"name": name, "title": title, "labels": labels,
               "rows": [{"review_id": r["review_id"], "review_text": r["review_text"],
                         "source": {k: r[k] for k in FIELDS}} for r in rows]}
    (HERE / "sets" / f"{name}.js").write_text(
        "window.LABEL_SET = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")


if __name__ == "__main__":
    main()
