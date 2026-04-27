"""Pipeline-side helpers shared by the FastAPI routes and the cross-references orchestrator.

Kept separate from ``api.py`` so ``crossreferences.py`` can import them
without creating an api ↔ orchestrator import cycle.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

from fastapi import HTTPException

from nupla.pipeline.bfs import Municipality, fuzzy_find_municipality, load_bfs


def _slug(name: str) -> str:
    """Municipality name → filesystem slug (lowercase, no spaces)."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _pdf_filename(url: str) -> str:
    """Extract a clean filename from a PDF URL."""
    raw = unquote(url.split("/")[-1].split("?")[0])
    return raw if raw.endswith(".pdf") else raw + ".pdf"


def _find_md_for_label(annotations: list[dict], label: str, md_dir: Path) -> Path | None:
    """Find the markdown file for a PDF annotation with a specific label."""
    for ann in annotations:
        if label in ann.get("labels", []) and ann.get("selected"):
            md_name = Path(_pdf_filename(ann["pdf_url"])).stem + ".md"
            md_path = md_dir / md_name
            if md_path.exists():
                return md_path
    return None


def _resolve_municipality(name: str) -> Municipality:
    """Fuzzy-resolve a municipality name, raise 404 if not found."""
    municipalities = load_bfs()
    if not municipalities:
        raise HTTPException(status_code=500, detail="BFS register not loaded.")
    matches = fuzzy_find_municipality(name, municipalities, limit=1)
    if not matches or matches[0][1] < 60:
        raise HTTPException(status_code=404, detail=f"Municipality '{name}' not found.")
    return matches[0][0]
