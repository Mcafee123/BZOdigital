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
_MIN_TABLE_SUBSTANCE = 60
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_MIN_CLEANED_LEN = 50


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
    seen: dict[str, set[str]] = {}  # provision → set of paragraph texts
    for doc in companions:
        result = enrich_markdown_safe(
            doc.markdown,
            default_law="BZO",
            custom_laws=custom_laws,
        )
        if not result:
            continue

        for cite in result["citations"]:
            if cite.get("law_abbreviation") != "BZO" or not cite.get("is_resolved"):
                continue

            provision = cite["provision"]
            paragraph = _extract_paragraph(
                doc.markdown,
                cite["start_index"],
                cite["end_index"],
            )

            paragraph = _clean_paragraph(paragraph)

            if _is_low_value(paragraph):
                continue

            seen_set = seen.setdefault(provision, set())
            if paragraph in seen_set:
                continue
            seen_set.add(paragraph)

            cross_references.setdefault(provision, []).append(
                {
                    "source_file": doc.filename,
                    "source_labels": doc.labels,
                    "citation_text": cite["text"],
                    "paragraph": paragraph,
                }
            )

    return CrossRefResult(
        bzo_filename=bzo_filename,
        bzo_markdown=bzo_enriched,
        articles=articles,
        cross_references=cross_references,
    )


def _clean_paragraph(paragraph: str) -> str:
    """Strip HTML comments and leading/trailing whitespace from a paragraph."""
    cleaned = _HTML_COMMENT_RE.sub("", paragraph).strip()
    return cleaned


def _is_low_value(paragraph: str) -> bool:
    """Return True for paragraphs that add no substantive context.

    Catches:
    - Table rows that are just article-title listings (TOC-style).
    - Very short paragraphs after cleanup (bare headings, pointer stubs
      like ``*Art. 20*`` or ``zu Art. 29``).
    """
    if paragraph.startswith("|") or "\t|" in paragraph:
        stripped = re.sub(r"[|\-\s]+", " ", paragraph).strip()
        return len(stripped) < _MIN_TABLE_SUBSTANCE
    # Strip markdown headings and check remaining substance
    without_headings = re.sub(
        r"^#{1,6}\s+.*$", "", paragraph, flags=re.MULTILINE
    ).strip()
    return len(without_headings) < _MIN_CLEANED_LEN


def _extract_paragraph(text: str, start_index: int, end_index: int) -> str:
    """Extract the paragraph containing a citation.

    Finds the nearest blank-line boundaries, then expands outward when the
    result is very short (common with OCR-broken text or diagram labels).
    For markdown table rows, grabs the full row.
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

    paragraph = text[para_start:para_end].strip()

    if paragraph.startswith("|") or "\n|" in paragraph:
        lines = paragraph.split("\n")
        offset = para_start
        for line in lines:
            line_end = offset + len(line)
            if offset <= start_index < line_end or offset < end_index <= line_end:
                return line.strip()
            offset = line_end + 1

    return paragraph
