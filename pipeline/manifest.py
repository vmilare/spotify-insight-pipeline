"""Final run manifest: ties source checksum, code version, prompts, model IDs, settings, run IDs and output
hashes together (written by `export-grading`)."""
import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

from tools.check_submission import sha, write_json

from . import claude, enrich, group, jev
from .paths import CONFIG_DIR, GRADING_DIR, REPO, RUNS_DIR


def git(*args):
    try:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def write(input_path, workspace="main"):
    input_path = Path(input_path)
    folder = group.analysis_dir(input_path, workspace)
    enrich_runs = []
    for d in sorted(RUNS_DIR.glob(f"{workspace}-{input_path.stem}-*")):
        f = d / "run_summary.json"
        if f.exists():
            s = json.loads(f.read_text(encoding="utf-8"))
            enrich_runs.append({k: s.get(k) for k in ("run_id", "phase", "stop_reason", "requests", "failed_requests",
                                                     "texts_labeled", "reviews_completed", "cache_hit_reviews",
                                                     "input_tokens", "cost_usd", "wall_clock_seconds", "workers")})
    def runid(path):
        return json.loads(path.read_text(encoding="utf-8")).get("run_id") if path.exists() else None
    outputs = [*sorted(GRADING_DIR.glob("*")), REPO / "memo.md"] + [folder / n for n in (
        "membership.csv", "ranking.csv", "ranking_actionable.csv", "ranking_without_needs_review.csv", "aggregates.csv",
        "issues.csv", "issue_review.csv", "evidence_pack.json", "claims.csv", "recommendations.json", "memo.md",
        "verify/verify_report.json")]
    spend = sum(float(r["cost_usd"]) for r in csv.DictReader((RUNS_DIR / "spend_ledger.csv").open(encoding="utf-8")))
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "code": {"repository": "https://github.com/vmilare/spotify-insight-pipeline", "git_commit": git("rev-parse", "HEAD"),
                 "uncommitted_changes": bool(git("status", "--porcelain"))},
        "source": {"file": input_path.name, "bytes": input_path.stat().st_size, "sha256": sha(input_path)},
        "label_config": enrich.label_config(enrich.load_settings()),
        "models": {"enrich": jev.MODEL, "verify": claude.HAIKU, "group_review": claude.HAIKU, "memo": claude.SONNET},
        "settings": yaml.safe_load((CONFIG_DIR / "settings.yaml").read_text(encoding="utf-8")),
        "prompts_and_configs_sha256": {str(p.relative_to(REPO)): sha(p) for p in sorted(
            [*(REPO / "prompts").glob("*"), *CONFIG_DIR.glob("*.yaml")])},
        "enrichment_runs": enrich_runs,
        "analysis_runs": {"verify": runid(folder / "verify" / "verify_report.json"),
                          "group_review": runid(folder / "group_review.json"),
                          "memo": runid(folder / "memo_check.json"),
                          "memo_prompt": json.loads((folder / "memo_check.json").read_text()).get("config")},
        "outputs_sha256": {str(p.relative_to(REPO)): sha(p) for p in outputs if p.exists() and p.is_file()},
        "project_api_spend_usd": round(spend, 4),
    }
    write_json(RUNS_DIR / "final_run_manifest.json", manifest)
    return manifest
