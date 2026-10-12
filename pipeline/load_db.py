"""Load processed results into the dashboard database (Postgres on Neon). Code only, no model calls.

Reads the saved state DB (labels + statuses + source metadata) and the analysis folder (membership,
rankings, issue review, evidence pack, memo, claims, recommendations, verification), then replaces the
dashboard tables in one transaction. The deployed backend (web/api) only reads these tables.

Usage: python -m pipeline load-db [--input CSV] [--workspace main]   (needs DATABASE_URL in .env)
"""
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg

from tools.check_submission import sha

from . import enrich, group, store
from .paths import REPO

AREA = {"access": "access", "usability": "usability", "playback": "playback", "downloads": "playback",
        "billing": "billing_support", "support": "billing_support", "catalog": "catalog", "other": "other"}

SCHEMA = """
DROP TABLE IF EXISTS reviews, issues, ranking, claims, evidence, meta;
CREATE TABLE reviews (
    review_id    text PRIMARY KEY,
    status       text NOT NULL,          -- completed | quarantined | pending
    reason       text,
    review_date  date,
    rating       smallint,
    likes        integer,
    topic        text,
    area         text,
    intent       text,
    severity     smallint,
    sentiment    real,
    needs_review boolean,
    issue_id     text,
    cache_copy   boolean                 -- true when labels were reused from an identical text (cache_source_id)
);
CREATE TABLE issues (
    issue_id text PRIMARY KEY, topic text, area text, name text, keywords text,
    model_name text, model_description text, members integer, fit_rate real
);
CREATE TABLE ranking (
    kind text, rank integer, issue_id text, complaint_count integer, severity_sum integer,
    mean_severity text, priority_score integer, PRIMARY KEY (kind, rank)
);
CREATE TABLE claims (claim_id text PRIMARY KEY, issue_id text, metric text, value text);
CREATE TABLE evidence (
    issue_id text, position integer, review_id text, quote text, severity smallint, intent text,
    review_date date, likes integer, PRIMARY KEY (issue_id, position)
);
CREATE TABLE meta (key text PRIMARY KEY, value jsonb NOT NULL);
"""

INDEXES = """
CREATE INDEX reviews_area_month ON reviews (area, review_date);
CREATE INDEX reviews_issue ON reviews (issue_id);
CREATE INDEX reviews_status ON reviews (status);
"""


def read_csv(path):
    with Path(path).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run(input_path, workspace="main", evidence_per_issue=8):
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set (add it to .env)")
    input_path = Path(input_path)
    folder = group.analysis_dir(input_path, workspace)
    config = enrich.label_config(enrich.load_settings())
    membership = {r["review_id"]: r["issue_id"] for r in read_csv(folder / "membership.csv")}

    conn = store.connect(sha(input_path), workspace)
    rows = conn.execute("""
        SELECT r.review_id, s.status, s.reason, r.review_timestamp, r.review_rating, r.review_likes, res.record_json
        FROM reviews r JOIN record_status s USING (review_id)
        LEFT JOIN results res ON res.review_id = r.review_id AND res.label_config = ?""", (config,))

    def review_rows():
        for rid, status, reason, ts, rating, likes, rj in rows:
            rec = json.loads(rj) if rj else {}
            topic = rec.get("topic")
            yield (rid, status, reason, ts[:10] or None, int(rating) if rating.isdigit() else None,
                   int(likes) if likes.isdigit() else None, topic, AREA.get(topic), rec.get("intent"),
                   rec.get("severity"), rec.get("sentiment"), rec.get("needs_review"), membership.get(rid),
                   ("cache_source_id" in rec) if rec else None)

    issues = {r["issue_id"]: r for r in read_csv(folder / "issues.csv")}
    review = {r["issue_id"]: r for r in read_csv(folder / "issue_review.csv")} if (folder / "issue_review.csv").exists() else {}
    rankings = {kind: read_csv(folder / f) for kind, f in (("baseline", "ranking.csv"), ("actionable", "ranking_actionable.csv"),
                                                           ("without_needs_review", "ranking_without_needs_review.csv"))}
    claims = read_csv(folder / "claims.csv") if (folder / "claims.csv").exists() else []

    # Evidence: top quotes per issue (highest severity, then helpful votes), from saved labels only.
    quotes = {}
    for rid, issue_id, sev, intent, quote, ts, likes in conn.execute("""
            SELECT r.review_id, NULL, NULL, NULL, res.record_json, r.review_timestamp, r.review_likes
            FROM results res JOIN reviews r USING (review_id) WHERE res.label_config = ?""", (config,)):
        if rid in membership:
            rec = json.loads(quote)
            quotes.setdefault(membership[rid], []).append(
                (-rec["severity"], -int(likes or 0), rid, rec["evidence_quote"][:300], rec["severity"], rec["intent"], ts[:10], int(likes or 0)))
    evidence = []
    for issue_id, qs in quotes.items():
        for pos, q in enumerate(sorted(qs)[:evidence_per_issue], 1):
            evidence.append((issue_id, pos, q[2], q[3], q[4], q[5], q[6], q[7]))

    meta = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "input": input_path.name,
            "input_sha256": sha(input_path), "workspace": workspace, "label_config": config}
    for key, fname in (("group_manifest", "group_manifest.json"), ("rank_summary", "rank_summary.json"),
                       ("group_review", "group_review.json"), ("recommendations", "recommendations.json"),
                       ("memo_check", "memo_check.json"), ("evidence_pack", "evidence_pack.json")):
        p = folder / fname
        if p.exists():
            meta[key] = json.loads(p.read_text(encoding="utf-8"))
    if (folder / "memo.md").exists():
        meta["memo_markdown"] = (folder / "memo.md").read_text(encoding="utf-8")
    vr = folder / "verify" / "verify_report.json"
    if vr.exists():
        v = json.loads(vr.read_text(encoding="utf-8"))
        meta["verification"] = {k: v[k] for k in ("verified", "agreement", "planted_error_test", "needs_review_vs_disagreement", "verifier_config")}
    golden = REPO / "evals" / "results" / "golden" / "summary.json"
    if golden.exists():
        meta["golden"] = json.loads(golden.read_text(encoding="utf-8"))
    meta["spend_usd"] = round(enrich.project_spend(), 4)
    meta["area_mapping"] = AREA

    with psycopg.connect(url, autocommit=False) as pg:
        with pg.cursor() as cur:
            cur.execute(SCHEMA)
            with cur.copy("COPY reviews FROM STDIN") as cp:
                n = 0
                for row in review_rows():
                    cp.write_row(row)
                    n += 1
            cur.executemany("INSERT INTO issues VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", [
                (i, r["topic"], AREA[r["topic"]], r["name"], r["keywords"], review.get(i, {}).get("model_suggested_name"),
                 review.get(i, {}).get("model_description"), int(r["members"]),
                 float(review[i]["fit_rate"]) if review.get(i, {}).get("fit_rate") not in (None, "") else None)
                for i, r in issues.items()])
            cur.executemany("INSERT INTO ranking VALUES (%s,%s,%s,%s,%s,%s,%s)", [
                (kind, int(r["rank"]), r["issue_id"], int(r["complaint_count"]), int(r["severity_sum"]), r["mean_severity"],
                 int(r["priority_score"])) for kind, rs in rankings.items() for r in rs])
            cur.executemany("INSERT INTO claims VALUES (%s,%s,%s,%s)",
                            [(c["claim_id"], c["issue_id"], c["metric"], c["value"]) for c in claims])
            cur.executemany("INSERT INTO evidence VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", evidence)
            cur.executemany("INSERT INTO meta VALUES (%s,%s)", [(k, json.dumps(v)) for k, v in meta.items()])
            cur.execute(INDEXES)
            cur.execute("ANALYZE")
        pg.commit()
        size = pg.execute("SELECT pg_size_pretty(pg_database_size(current_database()))").fetchone()[0]
    conn.close()
    return {"reviews_loaded": n, "issues": len(issues), "ranking_rows": sum(len(v) for v in rankings.values()),
            "claims": len(claims), "evidence_quotes": len(evidence), "meta_keys": sorted(meta), "db_size": size}
