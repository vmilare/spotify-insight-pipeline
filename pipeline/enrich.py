"""Stage 2 - Enrich: Jev labels every pending distinct text; code validates, extracts, saves.

Work unit = one distinct nonempty text (exact-text reuse). Up to `reviews_per_request` texts per
Jev request. After every request, results + statuses + the call record are committed in ONE
transaction, so an interruption loses at most the requests in flight and a restart dispatches
only pending texts. A spend ledger reserves the worst-case cost of each request before sending it
and refuses to send when spent + reserved + next reservation would exceed the cap.
"""
import hashlib
import json
import signal
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path

import yaml

from tools.check_submission import INTENTS, TOPICS, sha, write_json

from . import extract, ingest, jev, store
from .paths import CONFIG_DIR, RUNS_DIR

SCHEMA_VERSION = "schema-v1"
QUOTE_VERSION = "quote-v1"
LEDGER = RUNS_DIR / "spend_ledger.csv"
LEDGER_HEADER = ("run_id,input,label_config,started_at,ended_at,requests,failed_requests,"
                 "input_tokens,cost_usd,texts_labeled,reviews_completed,cache_hit_reviews,stop_reason\n")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_settings():
    return yaml.safe_load((CONFIG_DIR / "settings.yaml").read_text(encoding="utf-8"))


def label_config(settings):
    e = settings["enrich"]
    parts = [jev.MODEL, jev.question_set_version(e["question_set"], e["reviews_per_request"]),
             SCHEMA_VERSION, QUOTE_VERSION]
    if e["question_set"] in ("tiny", "short3"):
        parts.append(yaml.safe_load((CONFIG_DIR / "sentiment_from_intent.yaml").read_text())["version"])
    return "+".join(parts)


def project_spend():
    if not LEDGER.exists():
        return 0.0
    lines = LEDGER.read_text(encoding="utf-8").splitlines()[1:]
    return sum(float(l.split(",")[8]) for l in lines if l.strip())


def validate(answers):
    """Return an error string, or None if Jev's answers for one review are usable."""
    try:
        if answers["topic"]["choice"] not in TOPICS:
            return "topic not allowed"
        if answers["intent"]["choice"] not in INTENTS:
            return "intent not allowed"
        if answers["severity"]["choice"] not in {"1", "2", "3", "4", "5"}:
            return "severity not allowed"
        if not answers["intent"].get("probabilities"):
            return "missing intent probabilities"
    except (KeyError, TypeError) as e:
        return f"malformed answer: {e}"
    return None


def build_labels(payload_for_review, text, settings):
    """Model answers -> schema fields (code owns mapping, quote, entities, needs_review)."""
    e = settings["enrich"]
    p = jev.parse(payload_for_review)
    reasons = [f"low_confidence_{k}" for k, v in p["confidence"].items()
               if v is not None and v < e["confidence_threshold"]]
    if extract.likely_non_english(text):
        reasons.append("non_english_unverified")
    return {
        "topic": p["topic"], "intent": p["intent"], "sentiment": p["sentiment"], "severity": p["severity"],
        "entities": extract.entities(text),
        "evidence_quote": extract.evidence_quote(text, p["topic"], e["quote_whole_text_max_chars"]),
        "needs_review": bool(reasons), "needs_review_reasons": reasons,
        "confidence": p["confidence"], "probabilities": p["probabilities"],
        "sentiment_source": p["sentiment_source"],
    }


class Ledger:
    def __init__(self, settings):
        b = settings["budget"]
        self.price = jev.PRICE_PER_M_INPUT / 1e6
        self.run_cap = b["run_cap_usd"]
        self.project_cap = b["project_cap_usd"]
        self.prior = project_spend()
        self.per_review_tokens = b["reservation_tokens_per_review"]
        self.spent = 0.0
        self.reserved = 0.0

    def estimate(self, texts):
        return (self.per_review_tokens * len(texts) + 0.3 * sum(len(t) for t in texts)) * self.price

    def can_admit(self, amount):
        return (self.spent + self.reserved + amount <= self.run_cap
                and self.prior + self.spent + self.reserved + amount <= self.project_cap)

    def reserve(self, amount):
        self.reserved += amount

    def settle(self, reserved, tokens):
        self.reserved -= reserved
        cost = (tokens or 0) * self.price
        self.spent += cost
        return cost


def pending_units(conn, limit=None):
    """Distinct texts that still have pending reviews, in a deterministic pseudo-random order
    (hash of the text hash) so any partial run is a fair sample rather than the first rows."""
    rows = conn.execute("""
        SELECT t.text_sha256, t.review_text, t.first_review_id
        FROM texts t
        WHERE EXISTS (SELECT 1 FROM reviews r JOIN record_status s ON s.review_id = r.review_id
                      WHERE r.text_sha256 = t.text_sha256 AND s.status = 'pending')""").fetchall()
    rows.sort(key=lambda r: hashlib.sha256(r[0].encode()).hexdigest())
    return rows[:limit] if limit else rows


def complete_text(conn, text_sha, labels, config, run_id, source_review_id, called=True):
    """Mark every pending review with this exact text completed. The source review is the one whose
    model call produced the labels; other reviews get cache_source_id pointing directly to it."""
    stamp = now()
    reviews = conn.execute("""SELECT r.review_id, r.source_sha256 FROM reviews r
                              JOIN record_status s ON s.review_id = r.review_id
                              WHERE r.text_sha256 = ? AND s.status = 'pending'""", (text_sha,)).fetchall()
    for review_id, source_sha in reviews:
        record = {"review_id": review_id, "source_sha256": source_sha, "status": "completed",
                  **{k: labels[k] for k in ("topic", "intent", "sentiment", "severity", "entities",
                                            "evidence_quote", "needs_review")},
                  "label_config": config}
        if review_id != source_review_id:
            record["cache_source_id"] = source_review_id
        record["internal"] = {k: labels[k] for k in ("needs_review_reasons", "confidence", "probabilities",
                                                     "sentiment_source")}
        conn.execute("INSERT OR REPLACE INTO results VALUES (?,?,?,?,?)",
                     (review_id, config, json.dumps(record, ensure_ascii=False), run_id, stamp))
        conn.execute("UPDATE record_status SET status='completed', reason=NULL, attempts=attempts+?, updated_at=? "
                     "WHERE review_id=?", (1 if called and review_id == source_review_id else 0, stamp, review_id))
    return len(reviews)


def quarantine_text(conn, text_sha, reason):
    stamp = now()
    conn.execute("""UPDATE record_status SET status='quarantined', reason=?, attempts=attempts+1, updated_at=?
                    WHERE status='pending' AND review_id IN (SELECT review_id FROM reviews WHERE text_sha256=?)""",
                 (reason, stamp, text_sha))


def run(input_path, *, stop_after_requests=None, workers=None, workspace="main", out_dir=None):
    settings = load_settings()
    e = settings["enrich"]
    workers = workers or e["max_workers"]
    input_path = Path(input_path)
    file_sha = sha(input_path)
    conn = store.connect(file_sha, workspace)
    if not conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]:
        conn.close()
        ingest.run(input_path, workspace=workspace)
        conn = store.connect(file_sha, workspace)
    cache = store.connect_cache(workspace)
    config = label_config(settings)
    questions = jev.build_questions(jev.load_labels(), e["question_set"])
    already = conn.execute("SELECT COUNT(*) FROM results WHERE label_config=?", (config,)).fetchone()[0]
    phase = "resume" if already else "initial"
    run_id = f"{workspace}-{input_path.stem}-{datetime.now().strftime('%Y%m%dT%H%M%S%f')[:-3]}"  # ms: unique per run
    out = Path(out_dir or RUNS_DIR / run_id)
    out.mkdir(parents=True, exist_ok=True)
    started_at, t0 = now(), time.monotonic()
    ledger = Ledger(settings)
    events = (out / "run_log.jsonl").open("a", encoding="utf-8")

    def event(kind, **kw):
        events.write(json.dumps({"at": now(), "event": kind, **kw}, ensure_ascii=False) + "\n")
        events.flush()

    event("start", run_id=run_id, workspace=workspace, input=input_path.name, input_sha256=file_sha, label_config=config,
          phase=phase, completed_before=already, workers=workers, settings=settings)
    checkpoint_before = sorted(r[0] for r in conn.execute(
        "SELECT review_id FROM results WHERE label_config=?", (config,)))
    write_json(out / "checkpoint_before.json", {"run_id": run_id, "label_config": config,
                                                "completed_ids": checkpoint_before})

    stats = {"requests": 0, "failed_requests": 0, "input_tokens": 0, "texts_labeled": 0,
             "reviews_completed": 0, "cache_hit_reviews": 0, "invalid_outputs": 0, "quarantined_texts": 0}
    stop_reason = None
    interrupted = {"flag": False}
    previous_handler = signal.signal(signal.SIGINT, lambda *_: interrupted.update(flag=True))

    # 1) Result-cache hits: same exact text + same label_config, produced by a call on a review that
    #    exists in this input (so cache_source_id points to a record with call evidence).
    units = pending_units(conn)
    ids_in_input = None
    to_call = []
    for text_sha, text, first_id in units:
        hit = cache.execute("SELECT labels_json, source_review_id FROM cache WHERE text_sha256=? AND label_config=?",
                            (text_sha, config)).fetchone()
        if hit:
            if ids_in_input is None:
                ids_in_input = {r[0] for r in conn.execute("SELECT review_id FROM reviews")}
            if hit[1] in ids_in_input:
                with conn:
                    stats["cache_hit_reviews"] += complete_text(conn, text_sha, json.loads(hit[0]), config,
                                                                run_id, hit[1], called=False)
                continue
        to_call.append((text_sha, text, first_id))
    event("cache_lookup", pending_texts=len(units), cache_hit_reviews=stats["cache_hit_reviews"],
          texts_to_call=len(to_call))

    # 2) Model calls, `pack` texts per request, retry queue for invalid outputs.
    pack = e["reviews_per_request"]
    groups = [to_call[i:i + pack] for i in range(0, len(to_call), pack)]
    retry_counts = {}
    consecutive_failures = 0

    def send(group):
        texts = [g[1] for g in group]
        log = []
        meta = {"run_id": run_id, "role": "enrich", "phase": phase, "label_config": config,
                "review_ids": [g[2] for g in group]}
        if len(group) == 1:
            payload, _ = jev.call(texts[0], questions, log=log, meta=meta, max_attempts=e["http_attempts"])
            per_review = [payload] if payload else None
        else:
            state, packed = jev.pack_request(texts, questions)
            payload, _ = jev.call(state, packed, log=log, meta=meta, max_attempts=e["http_attempts"], timeout=120)
            try:
                per_review = jev.unpack(payload, len(group)) if payload else None
            except KeyError:
                per_review = [None] * len(group)
        return group, payload, per_review, log

    def record_calls(log):
        cost_total = 0.0
        for c in log:
            cost = (c["input_tokens"] or 0) * ledger.price
            cost_total += cost
            conn.execute("INSERT INTO calls VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                c["request_id"], run_id, "enrich", phase, config, c["model"], json.dumps(c["review_ids"]),
                c["attempt"], c["outcome"], c["http_status"], c["input_tokens"], c["output_tokens"],
                round(cost, 8), c["started_at"], c["seconds"], c["error"]))
        return cost_total

    queue = list(groups)
    in_flight = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while queue or in_flight:
            # Admit work while budget, interruption and stop conditions allow.
            while queue and len(in_flight) < workers and not stop_reason:
                if interrupted["flag"]:
                    stop_reason = "interrupted"
                    break
                if consecutive_failures >= e["max_consecutive_failed_requests"]:
                    stop_reason = "too_many_consecutive_failures"  # circuit breaker; progress is already saved
                    break
                if stop_after_requests is not None and stats["requests"] + len(in_flight) >= stop_after_requests:
                    stop_reason = f"stop_after_requests={stop_after_requests}"
                    break
                group = queue[0]
                amount = ledger.estimate([g[1] for g in group])
                if not ledger.can_admit(amount):
                    stop_reason = "budget_cap"
                    break
                queue.pop(0)
                ledger.reserve(amount)
                in_flight[pool.submit(send, group)] = amount
            if not in_flight:
                break
            done, _ = wait(in_flight, return_when=FIRST_COMPLETED)
            for fut in done:
                reserved = in_flight.pop(fut)
                group, payload, per_review, log = fut.result()
                tokens = sum(c["input_tokens"] or 0 for c in log)
                stats["requests"] += 1
                stats["input_tokens"] += tokens
                with conn:  # one atomic commit per request: calls + results + statuses
                    ledger.settle(reserved, tokens)
                    record_calls(log)
                    if not payload:
                        stats["failed_requests"] += 1
                        consecutive_failures += 1
                        for text_sha, _, _ in group:
                            conn.execute("""UPDATE record_status SET attempts=attempts+1, reason='model_call_failed',
                                            updated_at=? WHERE status='pending' AND review_id IN
                                            (SELECT review_id FROM reviews WHERE text_sha256=?)""", (now(), text_sha))
                        event("request_failed", review_ids=[g[2] for g in group], error=log[-1]["error"] if log else None)
                        continue
                    consecutive_failures = 0
                    retry_group = []
                    for (text_sha, text, first_id), answer in zip(group, per_review):
                        error = validate(answer["answers"]) if answer else "missing answer"
                        if error:
                            stats["invalid_outputs"] += 1
                            if retry_counts.get(text_sha, 0) < e["invalid_output_retries"]:
                                retry_counts[text_sha] = retry_counts.get(text_sha, 0) + 1
                                retry_group.append((text_sha, text, first_id))
                            else:
                                quarantine_text(conn, text_sha, f"invalid_model_output: {error}")
                                stats["quarantined_texts"] += 1
                            event("invalid_output", review_id=first_id, error=error)
                            continue
                        labels = build_labels(answer, text, settings)
                        stats["reviews_completed"] += complete_text(conn, text_sha, labels, config, run_id, first_id)
                        stats["texts_labeled"] += 1
                        cache.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?,?,?)",
                                      (text_sha, config, json.dumps(labels, ensure_ascii=False), first_id, run_id))
                    cache.commit()
                    if retry_group:
                        queue.insert(0, retry_group)
                if stats["requests"] % 50 == 0:
                    event("progress", **stats, spent_usd=round(ledger.spent, 6))
    signal.signal(signal.SIGINT, previous_handler)

    if not stop_reason and conn.execute("SELECT COUNT(*) FROM record_status WHERE status='pending'").fetchone()[0]:
        stop_reason = "pending_remaining"
    wall = time.monotonic() - t0
    status_counts = dict(conn.execute("SELECT status, COUNT(*) FROM record_status GROUP BY status"))
    checkpoint_after = sorted(r[0] for r in conn.execute("SELECT review_id FROM results WHERE label_config=?", (config,)))
    write_json(out / "checkpoint_after.json", {"run_id": run_id, "label_config": config, "completed_ids": checkpoint_after})
    export(conn, config, out)
    cost = round(stats["input_tokens"] * ledger.price, 6)
    texts_total = conn.execute("SELECT COUNT(*) FROM texts").fetchone()[0]
    summary = {
        "run_id": run_id, "workspace": workspace, "input": input_path.name, "input_sha256": file_sha, "label_config": config,
        "phase": phase, "started_at": started_at, "ended_at": now(), "wall_clock_seconds": round(wall, 2),
        "workers": workers, "reviews_per_request": pack, "stop_reason": stop_reason or "complete",
        **stats, "cost_usd": cost,
        "price": {"model": jev.MODEL, "usd_per_million_input_tokens": jev.PRICE_PER_M_INPUT,
                  "output_tokens": "free", "source": "https://docs.typesafe.ai/models (checked 2026-10-11)"},
        "status_counts": status_counts,
        "completed_before": len(checkpoint_before), "completed_after": len(checkpoint_after),
        "throughput_texts_per_second": round(stats["texts_labeled"] / wall, 2) if wall else None,
        "tokens_per_text": round(stats["input_tokens"] / stats["texts_labeled"], 1) if stats["texts_labeled"] else None,
        "projection_full_pass_usd": (round(stats["input_tokens"] / stats["texts_labeled"] * 484189
                                           * ledger.price, 2) if stats["texts_labeled"] else None),
        "projection_note": "tokens per labeled text in this run x 484,189 distinct texts; this input's texts "
                           f"({texts_total}) may differ in length from the full corpus",
        "budget": {"run_cap_usd": ledger.run_cap, "project_cap_usd": ledger.project_cap,
                   "project_spend_before_run_usd": round(ledger.prior, 6)},
    }
    write_json(out / "run_summary.json", summary)
    event("end", **{k: summary[k] for k in ("stop_reason", "requests", "failed_requests", "cost_usd",
                                             "reviews_completed", "cache_hit_reviews", "wall_clock_seconds")})
    events.close()
    append_ledger(summary)
    conn.close()
    cache.close()
    return summary


def export(conn, config, out):
    """enriched.jsonl (completed records), quarantine.jsonl and calls.jsonl for this input's state."""
    with (out / "enriched.jsonl").open("w", encoding="utf-8") as f:
        for (record_json,) in conn.execute("""SELECT res.record_json FROM results res JOIN reviews r USING (review_id)
                                              WHERE res.label_config=? ORDER BY r.row_index""", (config,)):
            f.write(record_json + "\n")
    with (out / "quarantine.jsonl").open("w", encoding="utf-8") as f:
        for rid, ssha, reason, attempts in conn.execute("""
                SELECT s.review_id, r.source_sha256, s.reason, s.attempts FROM record_status s
                JOIN reviews r USING (review_id) WHERE s.status='quarantined' ORDER BY r.row_index"""):
            f.write(json.dumps({"review_id": rid, "source_sha256": ssha, "status": "quarantined",
                                "reason": reason, "attempts": attempts}) + "\n")
    cols = [d[1] for d in conn.execute("PRAGMA table_info(calls)")]
    with (out / "calls.jsonl").open("w", encoding="utf-8") as f:
        for row in conn.execute("SELECT * FROM calls ORDER BY started_at"):
            c = dict(zip(cols, row))
            c["review_ids"] = json.loads(c["review_ids"])
            f.write(json.dumps(c, ensure_ascii=False) + "\n")


def append_ledger(s):
    new = not LEDGER.exists()
    with LEDGER.open("a", encoding="utf-8") as f:
        if new:
            f.write(LEDGER_HEADER)
        f.write(",".join(str(x) for x in (s["run_id"], s["input"], s["label_config"], s["started_at"], s["ended_at"],
                                          s["requests"], s["failed_requests"], s["input_tokens"], s["cost_usd"],
                                          s["texts_labeled"], s["reviews_completed"], s["cache_hit_reviews"],
                                          s["stop_reason"])) + "\n")
