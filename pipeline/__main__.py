"""Command-line entry point: python -m pipeline <command> ...

Stages are added here as they are built (see Plan.md for status).
"""
import argparse
import json
from pathlib import Path

from .paths import FULL_CSV_NAME, dataset_file


def main():
    parser = argparse.ArgumentParser(prog="python -m pipeline", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("run", help="ALL stages on an input CSV: ingest -> enrich -> verify -> group -> group-review -> rank -> recommend (PAID)")
    p.add_argument("--input", type=Path, required=True, help="Input CSV path")
    p.add_argument("--workspace", default="main", help="Saved-state workspace (a new name = empty cache)")
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--verify-sample", type=int, default=None, help="Declared verification sample (default: settings)")

    p = commands.add_parser("ingest", help="Stage 1: read, hash, profile and queue an input CSV (no model calls)")
    p.add_argument("--input", type=Path, default=None,
                   help=f"Input CSV path (default: $DATA_DIR/{FULL_CSV_NAME})")
    p.add_argument("--out", type=Path, default=None, help="Output folder (default: runs/ingest/<input name>)")
    p.add_argument("--workspace", default="main", help="Saved-state workspace (default main)")

    p = commands.add_parser("enrich", help="Stage 2: label pending reviews with Jev (PAID API calls, budget-capped)")
    p.add_argument("--input", type=Path, default=None, help=f"Input CSV (default: $DATA_DIR/{FULL_CSV_NAME})")
    p.add_argument("--workers", type=int, default=None, help="Override max_workers from config/settings.yaml")
    p.add_argument("--stop-after-requests", type=int, default=None,
                   help="Stop admitting new requests after N (used to demonstrate interruption + resume)")
    p.add_argument("--workspace", default="main",
                   help="Saved-state workspace (default main). A new name = empty cache = cold run")

    p = commands.add_parser("verify", help="Stage 3: independent blind re-label of a random sample (Claude Haiku 5.5, PAID)")
    p.add_argument("--input", type=Path, default=None, help=f"Input CSV (default: $DATA_DIR/{FULL_CSV_NAME})")
    p.add_argument("--workspace", default="main")
    p.add_argument("--sample", type=int, default=None, help="Override verify.sample_size")

    p = commands.add_parser("status", help="Show saved progress for an input (no model calls)")
    p.add_argument("--input", type=Path, default=None, help=f"Input CSV (default: $DATA_DIR/{FULL_CSV_NAME})")
    p.add_argument("--workspace", default="main")

    p = commands.add_parser("group", help="Stage 4: assign complaint/cancellation records to issues (no model calls)")
    p.add_argument("--input", type=Path, default=None, help=f"Input CSV (default: $DATA_DIR/{FULL_CSV_NAME})")
    p.add_argument("--workspace", default="main")

    p = commands.add_parser("group-review", help="Stage 4b: model audit of issue membership (Claude Haiku 5.5, PAID)")
    p.add_argument("--input", type=Path, default=None, help=f"Input CSV (default: $DATA_DIR/{FULL_CSV_NAME})")
    p.add_argument("--workspace", default="main")

    p = commands.add_parser("recommend", help="Stage 6: decision memo from saved aggregates (Claude Sonnet 5.5, PAID)")
    p.add_argument("--input", type=Path, default=None, help=f"Input CSV (default: $DATA_DIR/{FULL_CSV_NAME})")
    p.add_argument("--workspace", default="main")

    p = commands.add_parser("memo-render", help="Rebuild memo.md and its appendix tables from the saved memo output (no model calls)")
    p.add_argument("--input", type=Path, default=None, help=f"Input CSV (default: $DATA_DIR/{FULL_CSV_NAME})")
    p.add_argument("--workspace", default="main")

    p = commands.add_parser("load-db", help="Load processed results into the dashboard Postgres DB (needs DATABASE_URL)")
    p.add_argument("--input", type=Path, default=None, help=f"Input CSV (default: $DATA_DIR/{FULL_CSV_NAME})")
    p.add_argument("--workspace", default="main")

    p = commands.add_parser("export-grading", help="Write the grading/ folder (GRADING_CONTRACT.md), no model calls")
    p.add_argument("--input", type=Path, default=None, help=f"Input CSV (default: $DATA_DIR/{FULL_CSV_NAME})")
    p.add_argument("--workspace", default="main")
    p.add_argument("--before-run", default=None, help="run folder whose checkpoint_after is the pre-resume snapshot")
    p.add_argument("--after-run", default=None, help="run folder whose checkpoint_after is the final snapshot")

    p = commands.add_parser("rerank", help="Stage 5: recompute ranking from saved files only (no model calls)")
    p.add_argument("--input", type=Path, default=None, help="Input CSV whose analysis folder to rank")
    p.add_argument("--folder", type=Path, default=None, help="Or an analysis folder path directly")
    p.add_argument("--workspace", default="main")

    args = parser.parse_args()
    if args.command == "run":
        import time
        from . import enrich, group, group_review, ingest, rank, recommend, verify
        stages, t0 = {}, time.monotonic()
        def stage(name, fn):
            s0 = time.monotonic(); out = fn(); stages[name] = round(time.monotonic() - s0, 2)
            print(f"[{name}] done in {stages[name]} s", flush=True); return out
        stage("ingest", lambda: ingest.run(args.input, workspace=args.workspace))
        e = stage("enrich", lambda: enrich.run(args.input, workers=args.workers, workspace=args.workspace))
        if e["stop_reason"] != "complete":
            raise SystemExit(f"enrichment stopped ({e['stop_reason']}); progress is saved - rerun the same command to resume")
        v = stage("verify", lambda: verify.run(args.input, args.workspace, args.verify_sample))
        g = stage("group", lambda: group.run(args.input, args.workspace))
        gr = stage("group_review", lambda: group_review.run(args.input, args.workspace))
        r = stage("rank", lambda: rank.run(group.analysis_dir(args.input, args.workspace)))
        m = stage("recommend", lambda: recommend.run(args.input, args.workspace))
        print(json.dumps({"input": str(args.input), "workspace": args.workspace, "stage_seconds": stages,
                          "end_to_end_seconds": round(time.monotonic() - t0, 2),
                          "enrich": {k: e[k] for k in ("requests", "reviews_completed", "cache_hit_reviews", "cost_usd", "status_counts")},
                          "verify": {k: v[k] for k in ("verified", "agreement", "stage_cache_hits", "cost_usd")},
                          "group": {k: g[k] for k in ("issue_taxonomy", "baseline_records(complaint+cancellation)")},
                          "group_review": {k: gr[k] for k in ("issues_reviewed", "misfits", "stage_cache_hits", "cost_usd")},
                          "rank_top3_actionable": r["top5_actionable"][:3],
                          "memo": {k: m[k] for k in ("status", "attempts", "recommended_area", "stage_cache_hits", "cost_usd")},
                          "outputs": str(group.analysis_dir(args.input, args.workspace))}, indent=2))
    elif args.command == "ingest":
        from . import ingest
        report = ingest.run(args.input or dataset_file(FULL_CSV_NAME), args.out, args.workspace)
        print(json.dumps({"counts": report["counts"], "all_checks_pass": report["all_checks_pass"],
                          "failed_checks": [c["check"] for c in report["manifest_checks"] if not c["pass"]],
                          "runtime_seconds": report["runtime_seconds"]}, indent=2, ensure_ascii=False))
    elif args.command == "enrich":
        from . import enrich
        summary = enrich.run(args.input or dataset_file(FULL_CSV_NAME), workers=args.workers,
                             stop_after_requests=args.stop_after_requests, workspace=args.workspace)
        keys = ("run_id", "phase", "stop_reason", "requests", "failed_requests", "invalid_outputs",
                "texts_labeled", "reviews_completed", "cache_hit_reviews", "status_counts", "input_tokens",
                "cost_usd", "tokens_per_text", "projection_full_pass_usd", "wall_clock_seconds",
                "throughput_texts_per_second")
        print(json.dumps({k: summary[k] for k in keys}, indent=2))
    elif args.command == "verify":
        from . import verify
        r = verify.run(args.input or dataset_file(FULL_CSV_NAME), args.workspace, args.sample)
        print(json.dumps({k: r[k] for k in ("verified", "missing_verifier_labels", "agreement",
                                            "planted_error_test", "needs_review_vs_disagreement", "requests",
                                            "failed_attempts", "usage", "cost_usd", "wall_clock_seconds")}, indent=2))
    elif args.command == "status":
        from . import enrich, store
        from tools.check_submission import sha
        path = args.input or dataset_file(FULL_CSV_NAME)
        conn = store.connect(sha(path), args.workspace)
        config = enrich.label_config(enrich.load_settings())
        counts = dict(conn.execute("SELECT status, COUNT(*) FROM record_status GROUP BY status"))
        calls = conn.execute("SELECT COUNT(*), COALESCE(SUM(cost_usd),0) FROM calls WHERE role='enrich'").fetchone()
        runs = conn.execute("SELECT run_id, phase, COUNT(*) FROM calls WHERE role='enrich' GROUP BY run_id, phase ORDER BY MIN(started_at)").fetchall()
        conn.close()
        total = sum(counts.values())
        print(f"input: {path.name} | label_config: {config}")
        print(f"records: {total:,} | completed: {counts.get('completed', 0):,} | pending: {counts.get('pending', 0):,} | "
              f"quarantined: {counts.get('quarantined', 0):,} | done: {100 * counts.get('completed', 0) / total:.1f}%")
        print(f"Jev enrichment calls logged: {calls[0]:,} | Jev spend on this input: ${calls[1]:.4f} | "
              f"project spend (ledger): ${enrich.project_spend():.4f}")
        for run_id, phase, n in runs:
            print(f"  run {run_id} | phase {phase} | calls {n:,}")
    elif args.command == "group":
        from . import group
        print(json.dumps(group.run(args.input or dataset_file(FULL_CSV_NAME), args.workspace), indent=2))
    elif args.command == "group-review":
        from . import group_review
        print(json.dumps(group_review.run(args.input or dataset_file(FULL_CSV_NAME), args.workspace), indent=2))
    elif args.command == "recommend":
        from . import recommend
        print(json.dumps(recommend.run(args.input or dataset_file(FULL_CSV_NAME), args.workspace), indent=2))
    elif args.command == "load-db":
        from . import load_db
        print(json.dumps(load_db.run(args.input or dataset_file(FULL_CSV_NAME), args.workspace), indent=2))
    elif args.command == "export-grading":
        from . import export
        print(json.dumps(export.run(args.input or dataset_file(FULL_CSV_NAME), args.workspace, args.before_run,
                                    args.after_run), indent=2))
    elif args.command == "memo-render":
        from . import recommend
        print(json.dumps(recommend.render(args.input or dataset_file(FULL_CSV_NAME), args.workspace), indent=2))
    elif args.command == "rerank":
        from . import group, rank
        folder = args.folder or group.analysis_dir(args.input or dataset_file(FULL_CSV_NAME), args.workspace)
        print(json.dumps(rank.run(folder), indent=2))


if __name__ == "__main__":
    main()
