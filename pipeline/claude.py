"""Claude client for the verify, group-naming and memo roles.

SDK retries are disabled (max_retries=0) and replaced by a bounded loop here, so every attempt,
including failures, is logged with its usage and cost, like the Jev client.
"""
import json
import random
import time
import uuid

import anthropic

from . import paths, rates  # noqa: F401  (paths loads .env)

HAIKU = "claude-haiku-5-5"
SONNET = "claude-sonnet-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"

_client = None


def client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(max_retries=0, timeout=600.0)
    return _client


def usage_dict(u):
    return {"input_tokens": u.input_tokens or 0, "output_tokens": u.output_tokens or 0,
            "cache_write_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
            "cache_read_tokens": getattr(u, "cache_read_input_tokens", 0) or 0}


def call_json(*, role, model, system, user, schema, max_tokens, effort, thinking=None, fallback=False,
              log=None, meta=None, attempts=3, ledger=None):
    """One structured-output request. Returns (parsed_json or None, response or None).
    `ledger` (optional) is checked before each attempt: ledger(estimated_usd) -> bool."""
    params = {"model": model, "max_tokens": max_tokens, "system": system,
              "messages": [{"role": "user", "content": user}],
              "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": schema}}}
    if thinking:
        params["thinking"] = thinking
    for attempt in range(1, attempts + 1):
        if ledger and not ledger(rates.cost(model, {"input_tokens": len(system + user) // 2,
                                                    "output_tokens": max_tokens})):
            if log is not None:
                log.append({"request_id": "not-sent-budget-" + uuid.uuid4().hex[:8], "role": role, "model": model,
                            "attempt": attempt, "outcome": "failed", "error": "budget_cap", "seconds": 0,
                            "started_at": time.time(), **(meta or {})})
            return None, None
        started = time.time()
        resp, error, status = None, None, None
        try:
            if fallback:
                resp = client().beta.messages.create(**params, betas=[FALLBACK_BETA], fallbacks="default")
            else:
                resp = client().messages.create(**params)
            status = 200
        except anthropic.RateLimitError as e:
            error, status = f"rate_limited: {e.message}", 429
        except anthropic.APIStatusError as e:
            error, status = f"api_error: {e.message}", e.status_code
        except anthropic.APIConnectionError as e:
            error = f"connection_error: {e}"
        parsed, outcome = None, "failed"
        if resp is not None:
            if resp.stop_reason == "refusal":
                error = f"refusal: {getattr(resp.stop_details, 'category', None)}"
            elif resp.stop_reason == "max_tokens":
                error = "max_tokens: output truncated"
            else:
                text = next((b.text for b in resp.content if b.type == "text"), None)
                try:
                    parsed = json.loads(text) if text else None
                    outcome = "succeeded" if parsed is not None else "failed"
                    if parsed is None:
                        error = "no text block"
                except json.JSONDecodeError as e:
                    error = f"invalid_json: {e}"
        usage = usage_dict(resp.usage) if resp is not None else {}
        served = resp.model if resp is not None else model
        try:
            cost = rates.cost(served, usage) if usage else 0.0
            cost_basis = served
        except KeyError:  # e.g. a fallback model without a row in cost/rates.csv: estimate at the requested model's rate
            cost, cost_basis = rates.cost(model, usage), f"estimated_at_{model}_rates"
        if log is not None:
            log.append({"request_id": resp._request_id if resp is not None else "local-" + uuid.uuid4().hex[:12],
                        "role": role, "model": resp.model if resp is not None else model,
                        "requested_model": model, "attempt": attempt, "outcome": outcome, "http_status": status,
                        "error": error, "stop_reason": resp.stop_reason if resp is not None else None,
                        "effort": effort, **usage, "cost_usd": round(cost, 8), "cost_basis": cost_basis,
                        "started_at": started, "seconds": round(time.time() - started, 3), **(meta or {})})
        if parsed is not None:
            return parsed, resp
        retryable = status is None or status == 429 or (status and status >= 500)
        if not retryable and not (error or "").startswith("invalid_json"):
            break
        if attempt < attempts:
            time.sleep(min(30, 2 ** attempt) * (0.5 + random.random()))
    return None, None
