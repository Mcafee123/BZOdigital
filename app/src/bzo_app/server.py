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

DIFF_PATH = Path(os.environ.get("DIFF_PATH", "/app/data/sample.diff"))
WEB_DIST = Path(os.environ.get("WEB_DIST", "/app/web/dist"))

_LEFT_RE = re.compile(r"^---\s+(?:a/)?(.+?)(?:\t.*)?$", re.MULTILINE)
_RIGHT_RE = re.compile(r"^\+\+\+\s+(?:b/)?(.+?)(?:\t.*)?$", re.MULTILINE)

app = FastAPI(title="bzo-app", version="0.1.0")

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
