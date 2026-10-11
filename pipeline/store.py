"""SQLite working store. One database per input file (keyed by its SHA-256), so a pilot on
cost_100.csv never shares saved results with the full run unless we copy them on purpose."""
import sqlite3

from .paths import STATE_DIR

SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    review_id        TEXT PRIMARY KEY,
    row_index        INTEGER NOT NULL,
    review_text      TEXT NOT NULL,
    review_rating    TEXT NOT NULL,
    review_likes     TEXT NOT NULL,
    app_version      TEXT NOT NULL,
    review_timestamp TEXT NOT NULL,
    source_sha256    TEXT NOT NULL,
    text_sha256      TEXT NOT NULL,
    is_empty         INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS reviews_text ON reviews(text_sha256);

-- One row per distinct nonempty text: the unit of model work (exact-text reuse).
CREATE TABLE IF NOT EXISTS texts (
    text_sha256      TEXT PRIMARY KEY,
    review_text      TEXT NOT NULL,
    first_review_id  TEXT NOT NULL,
    n_reviews        INTEGER NOT NULL
);

-- Final status per source review: pending, completed or quarantined.
CREATE TABLE IF NOT EXISTS record_status (
    review_id   TEXT PRIMARY KEY,
    status      TEXT NOT NULL CHECK (status IN ('pending', 'completed', 'quarantined')),
    reason      TEXT,
    attempts    INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def db_path(input_sha256):
    return STATE_DIR / f"state_{input_sha256[:12]}.sqlite"


def connect(input_sha256):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path(input_sha256))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)
    return conn
