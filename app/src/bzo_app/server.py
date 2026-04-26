"""FastAPI backend that serves the SPA and exposes diff endpoints."""
from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

DIFF_PATH = Path(os.environ.get("DIFF_PATH", "/app/data/sample.diff"))
WEB_DIST = Path(os.environ.get("WEB_DIST", "/app/web/dist"))

_LEFT_RE = re.compile(r"^---\s+(?:a/)?(.+?)(?:\t.*)?$", re.MULTILINE)
_RIGHT_RE = re.compile(r"^\+\+\+\s+(?:b/)?(.+?)(?:\t.*)?$", re.MULTILINE)

app = FastAPI(title="bzo-app", version="0.1.0")


def _extract_filenames(diff_text: str) -> tuple[str, str]:
    left_match = _LEFT_RE.search(diff_text)
    right_match = _RIGHT_RE.search(diff_text)
    left = left_match.group(1).strip() if left_match else "left"
    right = right_match.group(1).strip() if right_match else "right"
    return left, right


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/diff")
def get_diff() -> dict[str, str]:
    if not DIFF_PATH.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Diff file not found at {DIFF_PATH}",
        )
    text = DIFF_PATH.read_text(encoding="utf-8")
    left, right = _extract_filenames(text)
    return {
        "unified_diff": text,
        "left_filename": left,
        "right_filename": right,
    }


if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="spa")
