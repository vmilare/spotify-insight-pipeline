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

-- Validated enrichment result per completed review (the record exported to enriched.jsonl).
CREATE TABLE IF NOT EXISTS results (
    review_id    TEXT PRIMARY KEY,
    label_config TEXT NOT NULL,
    record_json  TEXT NOT NULL,
    run_id       TEXT NOT NULL,
    completed_at TEXT NOT NULL
);

-- Every model-call attempt, successful or not (source of calls.jsonl and the spend ledger).
CREATE TABLE IF NOT EXISTS calls (
    request_id    TEXT PRIMARY KEY,
    run_id        TEXT NOT NULL,
    role          TEXT NOT NULL,
    phase         TEXT NOT NULL,
    label_config  TEXT NOT NULL,
    model         TEXT NOT NULL,
    review_ids    TEXT NOT NULL,
    attempt       INTEGER NOT NULL,
    outcome       TEXT NOT NULL,
    http_status   INTEGER,
    input_tokens  INTEGER,
    output_tokens INTEGER,
    cost_usd      REAL,
    started_at    REAL NOT NULL,
    seconds       REAL NOT NULL,
    error         TEXT
);
"""

CACHE_SCHEMA = """
-- Result cache shared across inputs: exact text + full label_config -> validated labels.
-- source_review_id is the review whose model call produced the result (call evidence).
CREATE TABLE IF NOT EXISTS cache (
    text_sha256      TEXT NOT NULL,
    label_config     TEXT NOT NULL,
    labels_json      TEXT NOT NULL,
    source_review_id TEXT NOT NULL,
    run_id           TEXT NOT NULL,
    PRIMARY KEY (text_sha256, label_config)
);

-- Downstream model-stage cache: exact request (model + settings + prompt + input) -> validated JSON answer.
CREATE TABLE IF NOT EXISTS stage_cache (
    request_sha256 TEXT PRIMARY KEY,
    role           TEXT NOT NULL,
    model          TEXT NOT NULL,
    response_json  TEXT NOT NULL,
    request_id     TEXT NOT NULL,
    created_at     REAL NOT NULL
);
"""


def workspace_dir(workspace="main"):
    """Each workspace has its own per-input state DBs and result cache. 'main' holds the dev
    checkpoints and the full run (shared cache); a fresh workspace gives a genuinely cold run."""
    if not workspace.replace("-", "").replace("_", "").isalnum():
        raise ValueError("workspace name must be alphanumeric (dashes/underscores allowed)")
    return STATE_DIR / workspace


def db_path(input_sha256, workspace="main"):
    return workspace_dir(workspace) / f"state_{input_sha256[:12]}.sqlite"


def connect_cache(workspace="main"):
    path = workspace_dir(workspace) / "cache"
    path.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path / "enrich_cache.sqlite")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(CACHE_SCHEMA)
    return conn


def connect(input_sha256, workspace="main"):
    workspace_dir(workspace).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path(input_sha256, workspace))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)
    return conn
