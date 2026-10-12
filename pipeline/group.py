"""Stage 4 - Group (code owns membership; no model needed to rerun).

Every completed complaint/cancellation record joins exactly one issue from config/issues.yaml:
its Jev topic selects the issue list, the first issue whose keywords occur in the review text wins,
otherwise the topic's general issue. Writes a self-contained analysis folder so ranking can be
regenerated from saved files only:
  runs/analysis/<input>/enriched.jsonl   snapshot of completed records used
  runs/analysis/<input>/issues.csv       issue_id, topic, name, keywords, member count
  runs/analysis/<input>/membership.csv   issue_id, review_id  (contract format)
  runs/analysis/<input>/group_manifest.json
"""
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

from tools.check_submission import sha, write_json

from . import enrich, store
from .paths import CONFIG_DIR, RUNS_DIR

BASELINE_INTENTS = ("complaint", "cancellation")


def load_taxonomy():
    spec = yaml.safe_load((CONFIG_DIR / "issues.yaml").read_text(encoding="utf-8"))
    compiled = {}
    for topic, issues in spec["topics"].items():
        compiled[topic] = []
        for issue in issues:
            patterns = []
            for kw in issue["keywords"]:
                core = re.escape(kw.strip().lower())
                patterns.append(re.compile((r"\b" if kw.startswith(" ") else "") + core + (r"\b" if kw.endswith(" ") else "")))
            compiled[topic].append({**issue, "patterns": patterns})
        if compiled[topic][-1]["keywords"]:
            raise ValueError(f"topic {topic}: last issue must be the keyword-free general issue")
    return spec["version"], compiled


def assign(topic, text, taxonomy):
    low = text.lower()
    for issue in taxonomy[topic]:
        if not issue["patterns"] or any(p.search(low) for p in issue["patterns"]):
            return issue["id"]
    raise AssertionError("unreachable: general issue has no keywords")


def analysis_dir(input_path):
    return RUNS_DIR / "analysis" / Path(input_path).stem


def run(input_path, workspace="main"):
    input_path = Path(input_path)
    file_sha = sha(input_path)
    config = enrich.label_config(enrich.load_settings())
    version, taxonomy = load_taxonomy()
    conn = store.connect(file_sha, workspace)
    rows = conn.execute("""SELECT res.record_json, r.review_text FROM results res JOIN reviews r USING (review_id)
                           WHERE res.label_config=? ORDER BY r.row_index""", (config,)).fetchall()
    status = dict(conn.execute("SELECT status, COUNT(*) FROM record_status GROUP BY status"))
    conn.close()
    if status.get("pending"):
        print(f"WARNING: {status['pending']} reviews are still pending; grouping covers completed records only.")

    out = analysis_dir(input_path)
    out.mkdir(parents=True, exist_ok=True)
    membership = []
    with (out / "enriched.jsonl").open("w", encoding="utf-8") as f:
        for record_json, text in rows:
            f.write(record_json + "\n")
            rec = json.loads(record_json)
            if rec["intent"] in BASELINE_INTENTS:
                membership.append((assign(rec["topic"], text, taxonomy), rec["review_id"]))
    membership.sort(key=lambda m: (m[0], m[1]))
    assert len({rid for _, rid in membership}) == len(membership), "a review may belong to only one issue"

    with (out / "membership.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["issue_id", "review_id"])
        w.writerows(membership)
    counts = Counter(issue for issue, _ in membership)
    with (out / "issues.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["issue_id", "topic", "name", "keywords", "members"])
        for topic, issues in taxonomy.items():
            for issue in issues:
                w.writerow([issue["id"], topic, issue["name"], "|".join(k.strip() for k in issue["keywords"]),
                            counts.get(issue["id"], 0)])
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input": input_path.name, "input_sha256": file_sha, "workspace": workspace,
        "label_config": config, "issue_taxonomy": version, "allow_multi_issue": False,
        "completed_records": len(rows), "status_counts": status,
        "baseline_records(complaint+cancellation)": len(membership),
        "issues_with_members": sum(1 for c in counts.values() if c),
        "rule": "topic selects issue list; first issue whose keyword occurs in the text wins; else topic general issue",
    }
    write_json(out / "group_manifest.json", manifest)
    return manifest
