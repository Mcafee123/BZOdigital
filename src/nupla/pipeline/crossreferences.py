"""Pipeline-side orchestrator for the cross-references endpoint.

Resolves a municipality, loads its annotations from the DB, reads the
markdown files from disk, then delegates the pure aggregation to
``nupla.shared.crossreferences``.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from fastapi import HTTPException

from nupla.pipeline.db import get_annotations
from nupla.pipeline.lookup import _find_md_for_label, _pdf_filename, _resolve_municipality, _slug
from nupla.shared.crossreferences import CompanionDoc, compute_cross_references


LABEL_NEU = "Bau- und Zonenordnung neu"


def get_cross_references_for_municipality(name: str, *, data_dir: Path) -> dict:
    """Pre-compute all BZO cross-references for a municipality."""
    muni = _resolve_municipality(name)
    md_dir = data_dir / _slug(muni.name) / "md"
    anns = get_annotations(muni.bfs_nr)

    bzo_path = _find_md_for_label(anns, LABEL_NEU, md_dir)
    if not bzo_path:
        raise HTTPException(404, "No file labeled 'Bau- und Zonenordnung neu' found.")

    bzo_markdown = bzo_path.read_text(encoding="utf-8")

    label_map: dict[str, list[str]] = {}
    for ann in anns:
        if not ann.get("labels"):
            continue
        md_name = Path(_pdf_filename(ann["pdf_url"])).stem + ".md"
        label_map[md_name] = ann["labels"]

    companions = [
        CompanionDoc(
            filename=md_file.name,
            markdown=md_file.read_text(encoding="utf-8"),
            labels=label_map.get(md_file.name, []),
        )
        for md_file in sorted(md_dir.glob("*.md"))
        if md_file.name != bzo_path.name
    ]

    result = compute_cross_references(
        bzo_filename=bzo_path.name,
        bzo_markdown=bzo_markdown,
        companions=companions,
    )
    return {"municipality": muni.name, **dataclasses.asdict(result)}
