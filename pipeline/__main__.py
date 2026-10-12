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

    p = commands.add_parser("group", help="Stage 4: assign complaint/cancellation records to issues (no model calls)")
    p.add_argument("--input", type=Path, default=None, help=f"Input CSV (default: $DATA_DIR/{FULL_CSV_NAME})")
    p.add_argument("--workspace", default="main")

    p = commands.add_parser("rerank", help="Stage 5: recompute ranking from saved files only (no model calls)")
    p.add_argument("--input", type=Path, default=None, help="Input CSV whose analysis folder to rank")
    p.add_argument("--folder", type=Path, default=None, help="Or an analysis folder path directly")

    args = parser.parse_args()
    if args.command == "ingest":
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
    elif args.command == "group":
        from . import group
        print(json.dumps(group.run(args.input or dataset_file(FULL_CSV_NAME), args.workspace), indent=2))
    elif args.command == "rerank":
        from . import group, rank
        folder = args.folder or group.analysis_dir(args.input or dataset_file(FULL_CSV_NAME))
        print(json.dumps(rank.run(folder), indent=2))


if __name__ == "__main__":
    main()
