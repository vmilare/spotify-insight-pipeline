"""Stage 1 - Ingest (code only, no model calls).

Reads every row of an input CSV with the course checker's multiline-safe parser, stores the
original field strings unchanged with their source row hash, finds exact duplicate texts,
quarantines empty texts, queues everything else as pending, and writes an ingestion report.
"""
import hashlib
import json
import statistics
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from tools.check_submission import FIELDS, csv_rows, profile, row_sha, sha, write_json

from . import store
from .paths import CONFIG_DIR, GRADING_DIR, RUNS_DIR

EMPTY_REASON = "empty_review_text"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def text_sha(text):
    # Exact text only: no trimming, case folding or Unicode normalization.
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def manifest_expectations(input_path, file_sha):
    """Return the manifest's expected values when the input is a course file we know."""
    manifest = json.loads((CONFIG_DIR / "source_manifest.json").read_text(encoding="utf-8"))
    for name, info in manifest["files"].items():
        if info["sha256"] == file_sha:
            expected = {"file": name, "bytes": info["bytes"], "sha256": info["sha256"]}
            if name == manifest["assignment_scope"]["final_input"]:
                expected["profile"] = manifest["profile"]
                expected["reviews_by_month"] = manifest["reviews_by_month"]
                expected["reviews_by_rating"] = manifest["reviews_by_rating"]
                expected["first_review"] = manifest["window"]["first_review"]
                expected["last_review"] = manifest["window"]["last_review"]
            return expected
    return None


def check(name, expected, actual):
    return {"check": name, "expected": expected, "actual": actual, "pass": expected == actual}


def run(input_path, out_dir=None):
    started = time.monotonic()
    input_path = Path(input_path)
    file_sha = sha(input_path)
    out_dir = Path(out_dir or RUNS_DIR / "ingest" / input_path.stem)
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = store.connect(file_sha)
    with conn:
        conn.execute("DELETE FROM reviews")
        conn.execute("DELETE FROM texts")
        # Re-ingesting must never discard completed work; only (re)queue rows without a status.

    ids_seen = set()
    duplicate_ids = 0
    texts = {}  # text_sha -> [first_review_id, n_reviews, text]
    empties = []
    lengths = []
    invalid_ratings = Counter()
    bad_timestamps = 0
    batch = []
    row_index = 0

    def flush():
        conn.executemany("INSERT OR REPLACE INTO reviews VALUES (?,?,?,?,?,?,?,?,?,?)", batch)
        batch.clear()

    for row in csv_rows(input_path):
        rid = row["review_id"]
        duplicate_ids += rid in ids_seen
        ids_seen.add(rid)
        text = row["review_text"]
        is_empty = not text.strip()
        tsha = text_sha(text)
        if is_empty:
            empties.append({"review_id": rid, "source_sha256": row_sha(row), "row_index": row_index,
                            "raw_review_text": text})
        else:
            lengths.append(len(text))
            entry = texts.get(tsha)
            if entry:
                entry[1] += 1
            else:
                texts[tsha] = [rid, 1, text]
        if row["review_rating"] not in {"1", "2", "3", "4", "5"}:
            invalid_ratings[row["review_rating"]] += 1
        try:
            datetime.strptime(row["review_timestamp"], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            bad_timestamps += 1
        batch.append((rid, row_index, *(row[k] for k in FIELDS[1:]), row_sha(row), tsha, int(is_empty)))
        row_index += 1
        if len(batch) >= 20000:
            flush()
    flush()

    stamp = now()
    with conn:
        conn.executemany("INSERT INTO texts VALUES (?,?,?,?)",
                         ((t, v[2], v[0], v[1]) for t, v in texts.items()))
        conn.execute(
            "INSERT OR IGNORE INTO record_status (review_id, status, reason, attempts, updated_at) "
            "SELECT review_id, 'pending', NULL, 0, ? FROM reviews WHERE is_empty = 0", (stamp,))
        conn.executemany(
            "INSERT OR REPLACE INTO record_status VALUES (?, 'quarantined', ?, 0, ?)",
            ((e["review_id"], EMPTY_REASON, stamp) for e in empties))
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('input_sha256', ?)", (file_sha,))
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('input_path', ?)", (str(input_path),))
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('ingested_at', ?)", (stamp,))
    status_counts = dict(conn.execute("SELECT status, COUNT(*) FROM record_status GROUP BY status"))
    conn.close()

    # Independent second pass with the grader's own helper.
    checker_profile = profile(input_path)

    records = row_index
    nonempty = records - len(empties)
    repeated = sorted(texts.values(), key=lambda v: (-v[1], v[0]))
    report = {
        "generated_at": stamp,
        "input": {"path": input_path.name, "bytes": input_path.stat().st_size, "sha256": file_sha},
        "counts": {
            "records": records,
            "nonempty_review_text": nonempty,
            "empty_review_text": len(empties),
            "duplicate_review_ids": duplicate_ids,
            "missing_app_version": checker_profile["counts"]["missing_app_version"],
            "distinct_nonempty_texts": len(texts),
            "reviews_reusing_an_exact_text": nonempty - len(texts),
            "texts_appearing_more_than_once": sum(1 for v in texts.values() if v[1] > 1),
            "invalid_ratings": dict(invalid_ratings),
            "unparseable_timestamps": bad_timestamps,
        },
        "text_length_chars": {
            "min": min(lengths), "median": statistics.median(lengths),
            "p90": statistics.quantiles(lengths, n=10)[-1], "max": max(lengths),
        } if lengths else {},
        "most_repeated_texts": [{"text": v[2][:80], "reviews": v[1], "first_review_id": v[0]}
                                for v in repeated[:15]],
        "reviews_by_rating": checker_profile["reviews_by_rating"],
        "reviews_by_month": checker_profile["reviews_by_month"],
        "first_review": checker_profile["first_review"],
        "last_review": checker_profile["last_review"],
        "checker_profile": checker_profile,
        "status_after_ingest": status_counts,
        "quarantined_empty_texts": [{k: e[k] for k in ("review_id", "source_sha256", "row_index", "raw_review_text")}
                                    for e in empties],
        "notes": [
            "Raw field strings are stored unchanged; source_sha256 uses the course checker's row_sha.",
            "Empty means review_text.strip() == '' (same rule as the checker); such rows are quarantined "
            "with reason empty_review_text and are never sent to a model.",
            "Missing app_version does not block classification.",
            "Distinct texts are exact byte-identical review_text values; similar texts are not merged.",
        ],
    }

    expected = manifest_expectations(input_path, file_sha)
    checks = []
    if expected:
        checks.append(check("file_bytes", expected["bytes"], report["input"]["bytes"]))
        checks.append(check("file_sha256", expected["sha256"], file_sha))
        if "profile" in expected:
            for key, value in expected["profile"].items():
                checks.append(check(key, value, checker_profile["counts"][key]))
            checks.append(check("reviews_by_month", expected["reviews_by_month"], checker_profile["reviews_by_month"]))
            checks.append(check("reviews_by_rating", expected["reviews_by_rating"], checker_profile["reviews_by_rating"]))
            checks.append(check("first_review", expected["first_review"], checker_profile["first_review"]))
            checks.append(check("last_review", expected["last_review"], checker_profile["last_review"]))
            checks.append(check("distinct_nonempty_texts (assignment brief)", 484189, len(texts)))
            checks.append(check("nonempty_to_classify (assignment brief)", 660609, nonempty))
    checks.append(check("pipeline_count_equals_checker_count", checker_profile["counts"]["records"], records))
    report["manifest_checks"] = checks
    report["all_checks_pass"] = all(c["pass"] for c in checks)
    report["runtime_seconds"] = round(time.monotonic() - started, 2)

    write_json(out_dir / "ingestion_report.json", report)
    with (out_dir / "quarantine.jsonl").open("w", encoding="utf-8") as f:
        for e in empties:
            f.write(json.dumps({"review_id": e["review_id"], "source_sha256": e["source_sha256"],
                                "status": "quarantined", "reason": EMPTY_REASON, "attempts": 0},
                               ensure_ascii=False) + "\n")
    write_json(out_dir / "data_manifest.json", {
        "input": report["input"],
        "manifest_match": expected["file"] if expected else None,
        "state_db": str(store.db_path(file_sha).name),
        "ingested_at": stamp,
        "records": records,
        "pending_reviews": status_counts.get("pending", 0),
        "pending_distinct_texts": len(texts),
        "quarantined": status_counts.get("quarantined", 0),
    })
    # The grading export's ingestion.json must be the helper's exact output for the full file.
    if expected and expected.get("file") == "spotify_reviews_18months.csv":
        write_json(GRADING_DIR / "ingestion.json", checker_profile)
    return report
