"""Jev (TypeSafe System One) client and the enrichment question set.

Plain HTTP (no SDK) so every attempt, retry and failure is visible in our own call log:
the SDK retries 429/529 automatically, which would hide attempts we must report.
"""
import json
import os
import random
import time
import urllib.error
import urllib.request
import uuid

import yaml

from .paths import CONFIG_DIR, REPO

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"  # pinned exact version (jev-latest currently aliases this)
PRICE_PER_M_INPUT = 0.042  # USD per million input tokens; output tokens are free (docs.typesafe.ai/models)
RETRYABLE = {429, 500, 502, 503, 504, 529}


def load_labels():
    return yaml.safe_load((CONFIG_DIR / "labels.yaml").read_text(encoding="utf-8"))


def build_questions(labels, variant="full"):
    """Enrichment questions.
    'full'  = contract definitions from config/labels.yaml (~900 billed tokens per request);
    'short' = prompts/jev_short_v1.yaml, compressed phrases of the same rules (fewer tokens)."""
    if variant in ("short", "short3", "tiny"):
        # short3 = short wording without the sentiment question (sentiment computed from intent).
        source = "jev_tiny_v1.yaml" if variant == "tiny" else "jev_short_v1.yaml"
        spec = yaml.safe_load((REPO / "prompts" / source).read_text(encoding="utf-8"))
        types = {"topic": "choice", "intent": "choice", "severity": "choice", "sentiment": "score"}
        questions = {name: {"type": types[name], **spec[name]} for name in types if name in spec}
        if variant == "short3":
            questions.pop("sentiment")
        return questions

    def describe(opt):
        return opt["definition"]

    topic_instr = ("Which product area is this Spotify app review about? Pick the problem with the highest "
                   "severity (first mentioned on a tie); for praise, the first praised feature. "
                   "A paid-plan mention alone is not billing.")
    intent_instr = "Reviewer intent. Precedence: cancellation > complaint > request > praise > unclear."
    sev_instr = "Severity of the reported impact (not the emotion or star rating)."
    return {
        "topic": {"type": "choice", "instructions": topic_instr,
                  "criteria": {k: describe(v) for k, v in labels["topic"]["options"].items()}},
        "intent": {"type": "choice", "instructions": intent_instr,
                   "criteria": {k: describe(v) for k, v in labels["intent"]["options"].items()}},
        "severity": {"type": "choice", "instructions": sev_instr,
                     "criteria": {str(k): v for k, v in labels["severity"]["levels"].items()}},
        "sentiment": {"type": "score", "instructions": "Overall sentiment of the review.",
                      "criteria": ["very negative", "negative", "neutral or mixed", "positive", "very positive"]},
    }


def question_set_version(variant, pack=1):
    return f"jev-q-{variant}-v1" + (f"-pack{pack}" if pack > 1 else "")


def pack_request(texts, questions):
    """EXPERIMENTAL multi-review request (not a documented Jev feature).
    State holds reviews r1..rN; each base question is repeated per review with an instruction
    naming that review. Question keys are not sent to the model, so the instruction must name it."""
    state = {f"r{i}": t for i, t in enumerate(texts, 1)}
    packed = {}
    for i in range(1, len(texts) + 1):
        for name, q in questions.items():
            packed[f"r{i}__{name}"] = {**q, "instructions": f"Answer for review r{i} only: " + q["instructions"]}
    return state, packed


def unpack(payload, n):
    """Split a packed response back into per-review answer dicts (same shape as an unpacked response)."""
    answers = payload["answers"]
    names = {key.split("__", 1)[1] for key in answers}
    return [{"answers": {name: answers[f"r{i}__{name}"] for name in names}} for i in range(1, n + 1)]


def sentiment_from_intent(intent_probabilities):
    """Code-computed sentiment for question sets without a sentiment question."""
    values = yaml.safe_load((CONFIG_DIR / "sentiment_from_intent.yaml").read_text(encoding="utf-8"))["values"]
    raw = sum(p * values[k] for k, p in intent_probabilities.items())
    return round(max(-1.0, min(1.0, raw)), 2)


def call(state, questions, *, max_attempts=3, timeout=60, log=None, meta=None):
    """POST one state. Retries only 429/5xx/network errors with exponential backoff + jitter.
    Every attempt (success or failure) is appended to `log` (a list) if given.
    Returns (response_json or None, attempts)."""
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        raise RuntimeError("TYPESAFE_API_KEY is not set (add it to .env)")
    body = json.dumps({"state": state, "model": MODEL, "questions": questions}).encode("utf-8")
    for attempt in range(1, max_attempts + 1):
        local_id = "jev-" + uuid.uuid4().hex[:16]
        started = time.time()
        status, payload, error = None, None, None
        try:
            req = urllib.request.Request(ENDPOINT, data=body, method="POST", headers={
                "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.status
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            status = e.code
            error = e.read().decode("utf-8", "replace")[:500]
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            error = f"{type(e).__name__}: {e}"
        elapsed = round(time.time() - started, 3)
        usage = (payload or {}).get("usage", {})
        if log is not None:
            log.append({"request_id": local_id, "attempt": attempt, "http_status": status,
                        "outcome": "succeeded" if payload else "failed", "error": error,
                        "model": (payload or {}).get("model", MODEL),
                        "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
                        "started_at": started, "seconds": elapsed, **(meta or {})})
        if payload:
            return payload, attempt
        if status is not None and status not in RETRYABLE:
            break  # 4xx validation/auth errors are not retried
        if attempt < max_attempts:
            time.sleep(min(30, 2 ** attempt) * (0.5 + random.random()))
    return None, attempt


def parse(payload):
    """Map Jev answers to our schema fields (code owns the mapping, not the model)."""
    a = payload["answers"]
    if "sentiment" in a:
        sentiment = round(a["sentiment"]["score"] / 2 - 1, 2)  # Score 0..4 -> -1..1
    else:
        sentiment = sentiment_from_intent(a["intent"]["probabilities"])
    return {
        "topic": a["topic"]["choice"],
        "intent": a["intent"]["choice"],
        "severity": int(a["severity"]["choice"]),
        "sentiment": sentiment,
        "sentiment_source": "jev_score" if "sentiment" in a else "computed_from_intent",
        "confidence": {k: a[k].get("confidence") for k in ("topic", "intent", "severity", "sentiment") if k in a},
        "probabilities": {k: a[k].get("probabilities") for k in ("topic", "intent", "severity")},
    }
