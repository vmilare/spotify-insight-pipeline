"""Dashboard backend (FastAPI on Vercel, zero-config entrypoint `web/app.py`). Read-only: every response is retrieved from the Postgres
database loaded by `python -m pipeline load-db`. No model calls are made here.

Routes:
  GET /api/health                 database reachable + row counts
  GET /api/summary                overall metrics computed live from the reviews table + run metadata
  GET /api/areas                  product-area roll-up + severity mix (live SQL over reviews)
  GET /api/trend                  monthly complaint share per product area (live SQL over reviews)
  GET /api/ranking?kind=...       baseline | actionable | without_needs_review
  GET /api/appendix               memo appendix tables: baseline top 10 (with actionable rank) and the ranking by
                                  specific topic ("other" excluded, returned separately for the note)
  GET /api/issues/{issue_id}      issue detail, severity mix, evidence quotes
  GET /api/recommendations        AI recommendations, memo, claims checked against the ranking
"""
import json
import os
from contextlib import contextmanager

import psycopg
from fastapi import FastAPI, HTTPException, Query
from psycopg.rows import dict_row

app = FastAPI(title="Spotify Review Insight API", docs_url="/api/docs", openapi_url="/api/openapi.json")
AREAS = ["access", "usability", "playback", "billing_support", "catalog", "other"]


@contextmanager
def db():
    url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    if not url:
        raise HTTPException(503, "DATABASE_URL not configured")
    with psycopg.connect(url, row_factory=dict_row, connect_timeout=10) as conn:
        yield conn


def meta(conn, *keys):
    rows = conn.execute("SELECT key, value FROM meta WHERE key = ANY(%s)", (list(keys),)).fetchall()
    return {r["key"]: r["value"] for r in rows}


@app.get("/api/health")
def health():
    with db() as conn:
        counts = conn.execute("""SELECT (SELECT count(*) FROM reviews) AS reviews, (SELECT count(*) FROM issues) AS issues,
                                        (SELECT count(*) FROM evidence) AS evidence""").fetchone()
    return {"ok": True, **counts}


@app.get("/api/summary")
def summary():
    with db() as conn:
        c = conn.execute("""
            SELECT count(*) AS source_rows,
                   count(*) FILTER (WHERE status = 'completed') AS completed,
                   count(*) FILTER (WHERE status = 'quarantined') AS quarantined,
                   count(*) FILTER (WHERE status = 'pending') AS pending,
                   count(*) FILTER (WHERE intent IN ('complaint', 'cancellation')) AS complaint_records,
                   count(*) FILTER (WHERE intent = 'cancellation') AS cancellation_records,
                   count(*) FILTER (WHERE needs_review) AS needs_review,
                   count(*) FILTER (WHERE cache_copy) AS cache_copies,
                   min(review_date) AS first_date, max(review_date) AS last_date
            FROM reviews""").fetchone()
        intents = conn.execute("""SELECT intent, count(*) AS n FROM reviews WHERE status = 'completed'
                                  GROUP BY intent ORDER BY n DESC""").fetchall()
        m = meta(conn, "generated_at", "input", "label_config", "spend_usd", "verification", "golden", "group_review", "memo_check")
    c["first_date"], c["last_date"] = str(c["first_date"]), str(c["last_date"])
    g = m.get("golden") or {}
    return {"counts": c, "intents": intents, "run": {k: m.get(k) for k in ("generated_at", "input", "label_config", "spend_usd")},
            "verification": m.get("verification"),
            "golden": {k: g.get(k) for k in ("golden_cases", "topic_agreement", "intent_agreement", "severity_exact",
                                              "severity_within_1", "sentiment_mae")} if g else None,
            "group_review": m.get("group_review"), "memo_check": m.get("memo_check")}


@app.get("/api/areas")
def areas():
    with db() as conn:
        rows = conn.execute("""
            SELECT area, count(*) AS complaint_count, sum(severity) AS severity_sum,
                   round(avg(severity)::numeric, 3) AS mean_severity,
                   count(*) FILTER (WHERE intent = 'cancellation') AS cancellation_count,
                   count(*) FILTER (WHERE needs_review) AS needs_review_count,
                   count(*) FILTER (WHERE severity = 1) AS s1, count(*) FILTER (WHERE severity = 2) AS s2,
                   count(*) FILTER (WHERE severity = 3) AS s3, count(*) FILTER (WHERE severity = 4) AS s4,
                   count(*) FILTER (WHERE severity = 5) AS s5
            FROM reviews WHERE intent IN ('complaint', 'cancellation') AND issue_id IS NOT NULL
            GROUP BY area ORDER BY severity_sum DESC""").fetchall()
    for r in rows:
        r["mean_severity"] = float(r["mean_severity"])
    return {"areas": rows, "note": "playback includes downloads; billing_support = billing + support topics"}


@app.get("/api/trend")
def trend():
    with db() as conn:
        rows = conn.execute("""
            SELECT to_char(date_trunc('month', review_date), 'YYYY-MM') AS month, area,
                   count(*) FILTER (WHERE intent IN ('complaint', 'cancellation')) AS complaints
            FROM reviews WHERE status = 'completed' GROUP BY 1, 2 ORDER BY 1, 2""").fetchall()
        totals = conn.execute("""SELECT to_char(date_trunc('month', review_date), 'YYYY-MM') AS month, count(*) AS reviews
                                 FROM reviews WHERE status = 'completed' GROUP BY 1 ORDER BY 1""").fetchall()
    return {"rows": rows, "totals": totals,
            "note": "share = area complaints / all classified reviews that month; first and last months are partial"}


@app.get("/api/ranking")
def ranking(kind: str = Query("baseline", pattern="^(baseline|actionable|without_needs_review)$")):
    with db() as conn:
        rows = conn.execute("""
            SELECT k.rank, k.issue_id, k.complaint_count, k.severity_sum, k.mean_severity, k.priority_score,
                   i.topic, i.area, i.name, i.model_name, i.fit_rate
            FROM ranking k JOIN issues i USING (issue_id) WHERE k.kind = %s ORDER BY k.rank""", (kind,)).fetchall()
    return {"kind": kind, "rows": rows,
            "formula": "priority_score = severity_sum = complaint_count x mean_severity; ties by issue_id"}


@app.get("/api/appendix")
def appendix():
    with db() as conn:
        baseline = conn.execute("""
            SELECT b.rank, b.issue_id, i.name, i.area, b.complaint_count, b.severity_sum, b.mean_severity, b.priority_score,
                   a.rank AS actionable_rank
            FROM ranking b JOIN issues i USING (issue_id)
            LEFT JOIN ranking a ON a.issue_id = b.issue_id AND a.kind = 'actionable'
            WHERE b.kind = 'baseline' ORDER BY b.rank LIMIT 10""").fetchall()
        total = conn.execute("SELECT count(*) AS n FROM ranking WHERE kind = 'baseline'").fetchone()["n"]
        topics = conn.execute("""SELECT kind, rank, topic, area, issues, complaint_count, severity_sum, mean_severity,
                                        priority_score FROM topic_ranking ORDER BY kind, rank""").fetchall()
    specific = [t for t in topics if t["kind"] == "actionable"]
    excluded = [t for t in topics if t["kind"] == "all" and t["topic"] not in {s["topic"] for s in specific}]
    return {"baseline_top10": baseline, "issues_ranked": total, "topics": specific, "topics_excluded": excluded,
            "formula": "priority_score = severity_sum = complaint_count x mean_severity; ties by id",
            "note": "Appendix A of the memo: required baseline (the actionable view drops only OTH-GENERAL). "
                    "Appendix B: the same arithmetic with each issue summed into its contract topic, \"other\" excluded."}


@app.get("/api/issues/{issue_id}")
def issue(issue_id: str):
    with db() as conn:
        info = conn.execute("SELECT * FROM issues WHERE issue_id = %s", (issue_id,)).fetchone()
        if not info:
            raise HTTPException(404, "unknown issue")
        mix = conn.execute("""SELECT severity, count(*) AS n FROM reviews WHERE issue_id = %s
                              GROUP BY severity ORDER BY severity""", (issue_id,)).fetchall()
        stats = conn.execute("""SELECT count(*) AS members, count(*) FILTER (WHERE intent = 'cancellation') AS cancellations,
                                       count(*) FILTER (WHERE needs_review) AS needs_review
                                FROM reviews WHERE issue_id = %s""", (issue_id,)).fetchone()
        quotes = conn.execute("""SELECT position, review_id, quote, severity, intent, review_date::text AS review_date, likes
                                 FROM evidence WHERE issue_id = %s ORDER BY position""", (issue_id,)).fetchall()
        ranks = conn.execute("SELECT kind, rank, priority_score FROM ranking WHERE issue_id = %s", (issue_id,)).fetchall()
    return {"issue": info, "stats": stats, "severity_mix": mix, "evidence": quotes, "ranks": ranks}


@app.get("/api/recommendations")
def recommendations():
    with db() as conn:
        m = meta(conn, "recommendations", "memo_markdown", "memo_check", "generated_at")
        claims = conn.execute("""
            SELECT c.claim_id, c.issue_id, c.metric, c.value, i.name, i.area,
                   CASE c.metric WHEN 'complaint_count' THEN k.complaint_count::text WHEN 'severity_sum' THEN k.severity_sum::text
                                 WHEN 'mean_severity' THEN k.mean_severity WHEN 'priority_score' THEN k.priority_score::text END AS ranking_value
            FROM claims c LEFT JOIN issues i USING (issue_id)
            LEFT JOIN ranking k ON k.issue_id = c.issue_id AND k.kind = 'baseline'
            ORDER BY length(c.claim_id), c.claim_id""").fetchall()
    for c in claims:
        c["matches_ranking"] = c["value"] == c["ranking_value"]
    return {"recommendations": m.get("recommendations"), "memo_markdown": m.get("memo_markdown"),
            "memo_check": m.get("memo_check"), "claims": claims}

