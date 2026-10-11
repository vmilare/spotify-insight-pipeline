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

    args = parser.parse_args()
    if args.command == "ingest":
        from . import ingest
        report = ingest.run(args.input or dataset_file(FULL_CSV_NAME), args.out)
        print(json.dumps({"counts": report["counts"], "all_checks_pass": report["all_checks_pass"],
                          "failed_checks": [c["check"] for c in report["manifest_checks"] if not c["pass"]],
                          "runtime_seconds": report["runtime_seconds"]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
