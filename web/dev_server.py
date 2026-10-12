"""Local preview of the deployed site: API routes from app.py + the static dashboard from public/.
On Vercel, public/ is served by the CDN automatically (it must not be mounted in app.py).
Usage (from the repo root): .venv/bin/python web/dev_server.py   -> http://localhost:8765
"""
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles

HERE = Path(__file__).resolve().parent
load_dotenv(HERE.parent / ".env")

from app import app  # noqa: E402

app.mount("/", StaticFiles(directory=HERE / "public", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, port=8765, log_level="warning")
