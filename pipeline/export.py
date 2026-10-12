"""Write the standardized grading/ folder required by GRADING_CONTRACT.md (code only, no model calls).

grading/run.json, ingestion.json (already written by ingest), records.jsonl.gz, membership.csv, ranking.csv,
claims.csv, calls.jsonl.gz, checkpoint_before.json, checkpoint_after.json.

- records: one final record per source ID (completed with contract fields, or quarantined with reason).
- calls: every enrichment attempt under the final label_config from the main workspace (the full run plus the
  100/500/10k/golden runs whose saved results were reused as exact-text cache sources), plus the verify, group
  and memo calls of the full-data analysis.
- checkpoints: completed IDs saved when the first full-run segment stopped (397,059; the state shown at the start
  of the recorded interrupt/resume demo) and after the final resume completed the corpus.
"""
import csv
import gzip
import json
import shutil
import sqlite3
from pathlib import Path

from tools.check_submission import VERSION, sha, write_json

from . import enrich, group, store
from .paths import GRADING_DIR, RUNS_DIR

CONTRACT_FIELDS = ("review_id", "source_sha256", "status", "topic", "intent", "sentiment", "severity", "entities",
                   "evidence_quote", "needs_review", "label_config")


def run(input_path, workspace="main", before_run=None, after_run=None):
    input_path = Path(input_path)
    file_sha = sha(input_path)
    config = enrich.label_config(enrich.load_settings())
    folder = group.analysis_dir(input_path, workspace)
    GRADING_DIR.mkdir(exist_ok=True)

    write_json(GRADING_DIR / "run.json", {
        "version": VERSION, "analysis_count": 660622 if input_path.name == "spotify_reviews_18months.csv" else None,
        "analysis_sha256": file_sha, "classification_input_fields": ["review_text"], "allow_multi_issue": False})

    conn = store.connect(file_sha, workspace)
    if conn.execute("SELECT COUNT(*) FROM record_status WHERE status = 'pending'").fetchone()[0]:
        raise SystemExit("pending records remain; finish the run before exporting")
    n_records = 0
    with gzip.open(GRADING_DIR / "records.jsonl.gz", "wt", encoding="utf-8", compresslevel=9) as f:
        for rid, ssha, status, reason, rj in conn.execute("""
                SELECT r.review_id, r.source_sha256, s.status, s.reason, res.record_json FROM reviews r
                JOIN record_status s USING (review_id)
                LEFT JOIN results res ON res.review_id = r.review_id AND res.label_config = ?
                ORDER BY r.row_index""", (config,)):
            if status == "completed":
                rec = json.loads(rj)
                out = {k: rec[k] for k in CONTRACT_FIELDS}
                if "cache_source_id" in rec:
                    out["cache_source_id"] = rec["cache_source_id"]
            else:
                out = {"review_id": rid, "source_sha256": ssha, "status": "quarantined", "reason": reason}
            f.write(json.dumps(out, ensure_ascii=False) + "\n")
            n_records += 1

    # Calls: enrichment under the final label_config from every main-workspace input state.
    n_calls = 0
    cols = ("request_id", "role", "review_ids", "model", "phase", "outcome", "label_config", "input_tokens",
            "output_tokens", "run_id", "attempt", "http_status", "started_at", "seconds", "error")
    with gzip.open(GRADING_DIR / "calls.jsonl.gz", "wt", encoding="utf-8", compresslevel=9) as f:
        for db in sorted(store.workspace_dir(workspace).glob("state_*.sqlite")):
            c = sqlite3.connect(db)
            for row in c.execute("""SELECT request_id, role, review_ids, model, phase, outcome, label_config,
                                           input_tokens, output_tokens, run_id, attempt, http_status, started_at, seconds, error
                                    FROM calls WHERE role = 'enrich' AND label_config = ? ORDER BY started_at""", (config,)):
                ev = dict(zip(cols, row))
                ev["review_ids"] = json.loads(ev["review_ids"])
                ev["input_tokens"], ev["output_tokens"] = ev["input_tokens"] or 0, ev["output_tokens"] or 0
                f.write(json.dumps(ev) + "\n")
                n_calls += 1
            c.close()
        # Downstream roles of the full-data analysis (saved call logs; group/memo consume saved artifacts).
        for path, role in ((folder / "verify" / "calls.jsonl", "verify"), (folder / "group_review_calls.jsonl", "group"),
                           (folder / "memo_calls.jsonl", "memo")):
            for line in path.open(encoding="utf-8"):
                c = json.loads(line)
                ev = {"request_id": c["request_id"], "role": role, "review_ids": c.get("review_ids", []),
                      "model": c["model"], "phase": c.get("phase", role), "outcome": c["outcome"],
                      "label_config": c.get("label_config"), "input_tokens": int(c.get("input_tokens") or 0),
                      "output_tokens": int(c.get("output_tokens") or 0),
                      "cache_write_tokens": int(c.get("cache_write_tokens") or 0),
                      "cache_read_tokens": int(c.get("cache_read_tokens") or 0), "run_id": c.get("run_id"),
                      "attempt": c.get("attempt"), "started_at": c.get("started_at"), "seconds": c.get("seconds"),
                      "error": c.get("error")}
                if role != "verify":
                    ev["consumes"] = "evidence_pack.json" if role == "memo" else "membership.csv + issues.csv (sampled quotes)"
                f.write(json.dumps(ev) + "\n")
                n_calls += 1
    conn.close()

    for name in ("membership.csv", "ranking.csv", "claims.csv"):
        shutil.copyfile(folder / name, GRADING_DIR / name)

    runs = sorted(RUNS_DIR.glob(f"{workspace}-{input_path.stem}-*"))
    enrich_runs = [r for r in runs if (r / "run_summary.json").exists()]
    before_dir = RUNS_DIR / before_run if before_run else enrich_runs[0]
    after_dir = RUNS_DIR / after_run if after_run else enrich_runs[-1]
    before = json.loads((before_dir / "checkpoint_after.json").read_text(encoding="utf-8"))
    after = json.loads((after_dir / "checkpoint_after.json").read_text(encoding="utf-8"))
    write_json(GRADING_DIR / "checkpoint_before.json", {"completed_ids": before["completed_ids"], "source": before_dir.name,
               "note": "saved when the first full-run segment stopped; resumed in the recorded demo (evals/resume_demo.mov)"})
    write_json(GRADING_DIR / "checkpoint_after.json", {"completed_ids": after["completed_ids"], "source": after_dir.name,
               "note": "after resuming (one recorded Ctrl+C interruption and a second resume) and completing the corpus"})
    from . import manifest
    manifest.write(input_path, workspace)
    return {"records": n_records, "calls": n_calls, "checkpoint_before": len(before["completed_ids"]),
            "checkpoint_after": len(after["completed_ids"]),
            "files": {p.name: p.stat().st_size for p in sorted(GRADING_DIR.iterdir()) if p.is_file()}}
