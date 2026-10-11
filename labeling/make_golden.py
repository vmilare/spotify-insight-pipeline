"""Build the labeling-page data file for the course golden set (blank labels; code only).

The golden 50 is the held-out TEST set: its human labels are written only to
evals/golden_50_labeled.csv and are never read by prompts, Jev descriptions or thresholds.
Usage: python -m labeling.make_golden
"""
from pipeline.paths import dataset_file
from tools.check_submission import csv_rows

from .select_dev import write_label_set

if __name__ == "__main__":
    rows = list(csv_rows(dataset_file("golden_50_to_label.csv")))
    assert len(rows) == 50
    write_label_set("golden_50", "Golden test set (50) — label from scratch; never used for tuning", rows)
    print("Wrote labeling/sets/golden_50.js")
