"""Editable billing rates (cost/rates.csv) and cost = billed units x price per unit, per item.

Billing items are mutually exclusive: input_tokens are uncached input only (the API reports cache
reads/writes separately), and output_tokens already include thinking tokens, so nothing is double-counted.
"""
import csv
from functools import lru_cache
from pathlib import Path

from .paths import REPO

RATES_PATH = REPO / "cost" / "rates.csv"
ITEMS = ("input_tokens", "output_tokens", "cache_write_tokens", "cache_read_tokens")


@lru_cache(maxsize=None)
def load(path=RATES_PATH):
    table = {}
    with Path(path).open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            table[(row["model"], row["billing_item"])] = float(row["usd_per_unit"]) / float(row["unit_size"])
    return table


def cost(model, usage, path=RATES_PATH):
    """usage: dict with any of ITEMS. Missing rate for a nonzero item raises (never silently zero)."""
    table = load(path)
    total = 0.0
    for item in ITEMS:
        units = usage.get(item) or 0
        if units:
            if (model, item) not in table:
                raise KeyError(f"no rate for {model} / {item} in {path}")
            total += units * table[(model, item)]
    return total
