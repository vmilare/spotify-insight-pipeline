"""Repository paths and environment settings (no secrets are read here)."""
import os
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent
load_dotenv(REPO / ".env")

DATA_DIR = Path(os.environ.get("DATA_DIR") or REPO / "data")
STATE_DIR = REPO / "data" / "state"
RUNS_DIR = REPO / "runs"
GRADING_DIR = REPO / "grading"
CONFIG_DIR = REPO / "config"

FULL_CSV_NAME = "spotify_reviews_18months.csv"


def dataset_file(name):
    return DATA_DIR / name
