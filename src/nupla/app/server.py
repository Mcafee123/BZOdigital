"""FastAPI backend that serves the SPA and exposes diff endpoints."""
from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select, func
import json

from .database import get_session, BfsMunicipality, PdfAnnotation
from .paths import get_data_path

WEB_DIST = Path(os.environ.get("WEB_DIST", "/app/web/dist"))

_LEFT_RE = re.compile(r"^---\s+(?:a/)?(.+?)(?:\t.*)?$", re.MULTILINE)
_RIGHT_RE = re.compile(r"^\+\+\+\s+(?:b/)?(.+?)(?:\t.*)?$", re.MULTILINE)

_HEADING_RE = re.compile(r"^# (.+?)$", re.MULTILINE)
_ARTICLE_RE = re.compile(r"^Art\.\s+(\S+)\s*(.*)$")
_SECTION_MARKER_TRAILER_RE = re.compile(r"\n*<!--\s*section:.*?-->\s*$", re.DOTALL)
_WS_RE = re.compile(r"\s+")

app = FastAPI(title="nupla-app", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _extract_filenames(diff_text: str) -> tuple[str, str]:
    left_match = _LEFT_RE.search(diff_text)
    right_match = _RIGHT_RE.search(diff_text)
    left = left_match.group(1).strip() if left_match else "left"
    right = right_match.group(1).strip() if right_match else "right"
    return left, right


def _parse_articles(md_text: str) -> list[dict[str, str]]:
    """Split markdown into level-1 sections starting with 'Art. <id>'.

    Falls back to bare 'Art. <id>' lines (blank above and below) when the
    document doesn't use proper level-1 headings — see _parse_articles_fallback.
    """
    headings = list(_HEADING_RE.finditer(md_text))
    sections: list[dict[str, str]] = []
    for i, m in enumerate(headings):
        title = m.group(1).strip()
        article = _ARTICLE_RE.match(title)
        if not article:
            continue
        body_start = m.end()
        body_end = headings[i + 1].start() if i + 1 < len(headings) else len(md_text)
        body = _SECTION_MARKER_TRAILER_RE.sub("", md_text[body_start:body_end]).strip()
        sections.append({"key": article.group(1), "title": title, "body": body})
    if not sections:
        sections = _parse_articles_fallback(md_text)
    return sections


def _parse_articles_fallback(md_text: str) -> list[dict[str, str]]:
    """Bare 'Art. <id>' on its own line, with blank lines above and below."""
    lines = md_text.splitlines()
    starts: list[tuple[int, str, str]] = []
    for i, line in enumerate(lines):
        m = _ARTICLE_RE.match(line)
        if not m:
            continue
        prev_blank = i == 0 or lines[i - 1].strip() == ""
        next_blank = i + 1 >= len(lines) or lines[i + 1].strip() == ""
        if not (prev_blank and next_blank):
            continue
        rest = m.group(2).strip()
        title = f"Art. {m.group(1)}" + (f" {rest}" if rest else "")
        starts.append((i, m.group(1), title))

    sections: list[dict[str, str]] = []
    for j, (line_idx, key, title) in enumerate(starts):
        body_start = line_idx + 1
        body_end = starts[j + 1][0] if j + 1 < len(starts) else len(lines)
        body = "\n".join(lines[body_start:body_end]).strip()
        body = _SECTION_MARKER_TRAILER_RE.sub("", body).strip()
        sections.append({"key": key, "title": title, "body": body})
    return sections


def _norm(s: str) -> str:
    return _WS_RE.sub(" ", s).strip()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/municipalities")
def get_municipalities(session: Session = Depends(get_session)):
    """Return all municipalities that have entries in the pdfannotation table."""
    statement = select(BfsMunicipality).join(PdfAnnotation, BfsMunicipality.bfs_nr == PdfAnnotation.municipality_bfs_nr).distinct()
    results = session.exec(statement).all()
    
    municipalities = []
    for muni in results:
        municipalities.append({"name": muni.name, "folder": muni.name.lower()})
            
    municipalities.sort(key=lambda x: x["name"])
    return municipalities

@app.get("/api/municipalities/{folder}/pdfs")
def get_municipality_pdfs(folder: str, session: Session = Depends(get_session)):
    muni = session.exec(select(BfsMunicipality).where(func.lower(BfsMunicipality.name) == folder.lower())).first()
    if not muni:
        raise HTTPException(status_code=404, detail="Municipality not found")
        
    pdfs = session.exec(select(PdfAnnotation).where(PdfAnnotation.municipality_bfs_nr == muni.bfs_nr)).all()
    
    results = []
    for pdf in pdfs:
        try:
            labels = json.loads(pdf.labels_json)
            label = labels[0] if isinstance(labels, list) and len(labels) > 0 else pdf.pdf_title
        except:
            label = pdf.pdf_title
            
        results.append({
            "id": pdf.id,
            "title": pdf.pdf_title,
            "url": pdf.pdf_url,
            "label": label,
            "selected": pdf.selected
        })
        
    return {
        "municipality": {"name": muni.name, "status": "Genehmigt"}, 
        "pdfs": results
    }


@app.get("/api/municipalities/{folder}/diff")
def get_municipality_diff(folder: str, session: Session = Depends(get_session)) -> dict[str, str]:
    muni = session.exec(select(BfsMunicipality).where(func.lower(BfsMunicipality.name) == folder.lower())).first()
    if not muni:
        raise HTTPException(status_code=404, detail="Municipality not found")

    diff_path = get_data_path() / folder.lower() / "diff.unified"
    if not diff_path.is_file():
        raise HTTPException(status_code=404, detail=f"No diff for {folder}")

    text = diff_path.read_text(encoding="utf-8")
    left, right = _extract_filenames(text)
    return {
        "unified_diff": text,
        "left_filename": left,
        "right_filename": right,
    }


@app.get("/api/municipalities/{folder}/sections")
def get_municipality_sections(folder: str, session: Session = Depends(get_session)):
    """Return the changed Art.-level sections between alt and neu markdown."""
    muni = session.exec(select(BfsMunicipality).where(func.lower(BfsMunicipality.name) == folder.lower())).first()
    if not muni:
        raise HTTPException(status_code=404, detail="Municipality not found")

    folder_dir = get_data_path() / folder.lower()
    diff_path = folder_dir / "diff.unified"
    if not diff_path.is_file():
        raise HTTPException(status_code=404, detail=f"No diff for {folder}")

    alt_filename, neu_filename = _extract_filenames(diff_path.read_text(encoding="utf-8"))
    md_dir = folder_dir / "md"
    alt_path = md_dir / alt_filename
    neu_path = md_dir / neu_filename
    if not alt_path.is_file() or not neu_path.is_file():
        raise HTTPException(status_code=404, detail=f"Source markdown missing under {md_dir}")

    alt_sections = {s["key"]: s for s in _parse_articles(alt_path.read_text(encoding="utf-8"))}
    neu_sections = _parse_articles(neu_path.read_text(encoding="utf-8"))
    seen_keys: set[str] = set()

    rows: list[dict] = []
    for s in neu_sections:
        key = s["key"]
        seen_keys.add(key)
        alt = alt_sections.get(key)
        alt_body = alt["body"] if alt else ""
        if _norm(alt_body) == _norm(s["body"]):
            continue
        rows.append({
            "key": key,
            "title_alt": alt["title"] if alt else None,
            "title_neu": s["title"],
            "alt": alt_body,
            "neu": s["body"],
            "added": alt is None,
            "removed": False,
        })

    for key, alt in alt_sections.items():
        if key in seen_keys:
            continue
        rows.append({
            "key": key,
            "title_alt": alt["title"],
            "title_neu": None,
            "alt": alt["body"],
            "neu": "",
            "added": False,
            "removed": True,
        })

    return {
        "alt_filename": alt_filename,
        "neu_filename": neu_filename,
        "rows": rows,
    }


if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="spa")
