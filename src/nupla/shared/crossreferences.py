"""Pure cross-reference aggregation across BZO + companion documents.

No filesystem, no DB, no FastAPI. Callers load the markdown + annotation
labels themselves and pass them in; both the pipeline orchestrator and
the diff-viewer BFF reach the same algorithm via this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from nupla.shared.enrichment import build_bzo_custom_law, enrich_markdown_safe


_ARTICLE_HEADING_RE = re.compile(r"^#{1,6}\s+Art\.?\s*(\d+[a-zA-Z]?)\b", re.MULTILINE)
_MIN_PARAGRAPH_LEN = 80


@dataclass(frozen=True)
class CompanionDoc:
    """A non-BZO document that may contain references back into the BZO."""

    filename: str
    markdown: str
    labels: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CrossRefResult:
    bzo_filename: str
    bzo_markdown: str
    articles: list[str]
    cross_references: dict[str, list[dict[str, Any]]]


def compute_cross_references(
    *,
    bzo_filename: str,
    bzo_markdown: str,
    companions: list[CompanionDoc],
) -> CrossRefResult:
    """Aggregate cross-references from companion docs back into a BZO.

    Returns the enriched BZO markdown (with anchors + self-links), the
    list of article numbers parsed from BZO headings, and a map of
    provision → list of incoming references with surrounding paragraph
    context.
    """
    custom_laws = [build_bzo_custom_law(bzo_filename)]

    bzo_result = enrich_markdown_safe(bzo_markdown, custom_laws=custom_laws)
    bzo_enriched = bzo_result["markdown"] if bzo_result else bzo_markdown

    articles = _ARTICLE_HEADING_RE.findall(bzo_markdown)

    cross_references: dict[str, list[dict[str, Any]]] = {}
    for doc in companions:
        result = enrich_markdown_safe(
            doc.markdown, default_law="BZO", custom_laws=custom_laws,
        )
        if not result:
            continue

        bzo_citations = [
            c for c in result["citations"]
            if c.get("law_abbreviation") == "BZO" and c.get("is_resolved")
        ]

        for cite in bzo_citations:
            provision = cite["provision"]
            paragraph, para_start, para_end = _extract_paragraph(
                doc.markdown, cite["start_index"], cite["end_index"],
            )
            paragraph_html = _highlight_citations(
                paragraph, para_start, para_end, bzo_citations,
            )

            cross_references.setdefault(provision, []).append({
                "source_file": doc.filename,
                "source_labels": doc.labels,
                "citation_text": cite["text"],
                "paragraph": paragraph.strip(),
                "paragraph_html": paragraph_html,
            })

    return CrossRefResult(
        bzo_filename=bzo_filename,
        bzo_markdown=bzo_enriched,
        articles=articles,
        cross_references=cross_references,
    )


def _extract_paragraph(
    text: str, start_index: int, end_index: int,
) -> tuple[str, int, int]:
    """Extract the paragraph containing a citation.

    Finds the nearest blank-line boundaries, then expands outward when the
    result is very short (common with OCR-broken text or diagram labels).
    For markdown table rows, grabs the full row.

    Returns ``(paragraph_text, start_offset, end_offset)`` where the offsets
    are absolute positions in ``text``. The slice ``text[start:end]`` matches
    ``paragraph_text`` exactly (no `.strip()` on the slice — leading/trailing
    whitespace is preserved so callers can re-locate citations by offset).
    """
    para_start = text.rfind("\n\n", 0, start_index)
    para_start = para_start + 2 if para_start != -1 else 0
    para_end = text.find("\n\n", end_index)
    if para_end == -1:
        para_end = len(text)

    for _ in range(3):
        if para_end - para_start >= _MIN_PARAGRAPH_LEN:
            break
        expanded = False
        next_end = text.find("\n\n", para_end + 2)
        if next_end != -1 and next_end - para_start < 500:
            para_end = next_end
            expanded = True
        prev_start = text.rfind("\n\n", 0, para_start - 2) if para_start > 2 else -1
        if prev_start != -1 and para_end - (prev_start + 2) < 500:
            para_start = prev_start + 2
            expanded = True
        if not expanded:
            break

    paragraph = text[para_start:para_end]

    if paragraph.lstrip().startswith("|") or "\n|" in paragraph:
        lines = paragraph.split("\n")
        offset = para_start
        for line in lines:
            line_end = offset + len(line)
            if offset <= start_index < line_end or offset < end_index <= line_end:
                return line, offset, line_end
            offset = line_end + 1

    return paragraph, para_start, para_end


def _highlight_citations(
    paragraph: str,
    para_start: int,
    para_end: int,
    citations: list[dict[str, Any]],
) -> str:
    """Wrap each citation that falls inside the paragraph in <mark class="cite">.

    Uses the absolute ``start_index``/``end_index`` from the enrichment output
    so we don't re-run regex on the snippet. Walks in reverse so insertions
    don't shift later positions.
    """
    in_para = sorted(
        (c for c in citations if para_start <= c["start_index"] < para_end),
        key=lambda c: c["start_index"],
        reverse=True,
    )
    out = paragraph
    for cite in in_para:
        rel_start = cite["start_index"] - para_start
        rel_end = min(cite["end_index"] - para_start, len(out))
        if rel_start < 0 or rel_end <= rel_start:
            continue
        out = (
            out[:rel_start]
            + '<mark class="cite">' + out[rel_start:rel_end] + '</mark>'
            + out[rel_end:]
        )
    return out.strip()
