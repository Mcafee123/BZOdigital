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
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_MIN_CLEANED_LEN = 50
_CHANGELOG_RE = re.compile(r"\d{2}\.\d{2}\.\d{4}\s*—\s*\d{2}\.\d{2}\.\d{4}")
_MAX_PARAGRAPH_LEN = 600
# Split on ". " followed by an uppercase letter or on ".\n", but not after
# common abbreviations (Art., Abs., Bst., Nr., Kap., vgl., bzw., resp., gem.)
_SENTENCE_SPLIT_RE = re.compile(
    r"(?<!Art)(?<!Abs)(?<!Bst)(?<!Kap)(?<!vgl)(?<!bzw)(?<!gem)(?<!resp)"
    r"(?<!\bNr)"
    r"\.\s+(?=[A-ZÄÖÜ«\-\(])"
)


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

    cross_references = _remove_contained(cross_references)
    cross_references = _truncate_paragraphs(cross_references)

    return CrossRefResult(
        bzo_filename=bzo_filename,
        bzo_markdown=bzo_enriched,
        articles=articles,
        cross_references=cross_references,
    )


def _remove_contained(
    cross_references: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """Drop paragraphs that are contained within a longer one for the same provision.

    When two citations in the same text region produce overlapping extractions,
    the shorter paragraph is a substring of the longer one.  Keep only the
    shorter (more focused) version.
    """
    result: dict[str, list[dict[str, Any]]] = {}
    for provision, refs in cross_references.items():
        paragraphs = [r["paragraph"] for r in refs]
        # Sort shortest first so we prefer the focused version
        indexed = sorted(enumerate(paragraphs), key=lambda t: len(t[1]))
        drop: set[int] = set()
        for i, (idx_a, para_a) in enumerate(indexed):
            if idx_a in drop:
                continue
            for idx_b, para_b in indexed[i + 1 :]:
                if idx_b in drop:
                    continue
                if para_a in para_b:
                    drop.add(idx_b)
        result[provision] = [r for j, r in enumerate(refs) if j not in drop]
    return result


def _clean_paragraph(paragraph: str) -> str:
    """Clean up a paragraph extracted from markdown.

    - Strips HTML comments.
    - Removes markdown table formatting (pipe delimiters, empty cells).
    - Rejoins words hyphenated across line breaks by PDF extraction
      (e.g. ``Zuläs- sig`` → ``Zulässig``).
    """
    cleaned = _HTML_COMMENT_RE.sub("", paragraph).strip()
    # Strip table row formatting: split cells, drop empties, rejoin
    if cleaned.startswith("|") or "\t|" in cleaned:
        cells = [c.strip() for c in cleaned.split("|") if c.strip()]
        cleaned = " — ".join(cells) if len(cells) > 1 else cells[0] if cells else ""
    # Rejoin words hyphenated across PDF line breaks, but preserve
    # suspended hyphens ("Wohn- und", "Einzel-, Doppel-", "WG- Zonen").
    # PDF hyphenation always continues lowercase (mid-word).
    cleaned = re.sub(
        r"(?<!,)(\w)- (?!und |oder |bzw\.? |sowie |bis |wie |als )([a-zäöüéèê])",
        r"\1\2",
        cleaned,
    )
    return cleaned


def _is_low_value(paragraph: str) -> bool:
    """Return True for paragraphs that add no substantive context.

    After cleaning (pipes stripped, HTML comments removed), filters
    paragraphs that are just bare headings, pointer stubs, changelog
    entries, or otherwise too short to be useful.
    """
    # Changelog rows: "09.12.2021 — 01.08.2023 — Art. 43 — eingefügt"
    if _CHANGELOG_RE.search(paragraph):
        return True
    without_headings = re.sub(
        r"^#{1,6}\s+.*$", "", paragraph, flags=re.MULTILINE
    ).strip()
    return len(without_headings) < _MIN_CLEANED_LEN


def _truncate_paragraphs(
    cross_references: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """Truncate paragraphs that exceed the maximum length.

    Keeps the citation visible: truncates from the start when the citation
    is near the beginning, or centers a window around the citation when it
    would otherwise be cut off.
    """
    result: dict[str, list[dict[str, Any]]] = {}
    for provision, refs in cross_references.items():
        truncated = []
        for ref in refs:
            para = ref["paragraph"]
            if len(para) > _MAX_PARAGRAPH_LEN:
                para = _truncate(para, ref["citation_text"])
                ref = {**ref, "paragraph": para}
            truncated.append(ref)
        result[provision] = truncated
    return result


def _truncate(para: str, citation_text: str) -> str:
    """Truncate a paragraph to ~_MAX_PARAGRAPH_LEN, keeping the citation visible.

    Splits into sentences, finds the one containing the citation, then
    expands outward sentence-by-sentence until the budget is exhausted.
    """
    # Split into sentences, preserving the period with each sentence
    parts = _SENTENCE_SPLIT_RE.split(para)
    if len(parts) <= 1:
        # Can't split — hard-truncate around citation
        return _hard_truncate(para, citation_text)

    # Re-attach the period that was consumed by the split
    sentences: list[str] = []
    for i, part in enumerate(parts):
        s = part.strip()
        if i < len(parts) - 1:
            s += "."
        if s:
            sentences.append(s)

    # Find which sentence contains the citation
    cite_idx = 0
    for i, sent in enumerate(sentences):
        if citation_text in sent:
            cite_idx = i
            break

    # Expand outward from the citation sentence until budget is filled
    selected = [cite_idx]
    total_len = len(sentences[cite_idx])
    lo, hi = cite_idx - 1, cite_idx + 1

    while total_len < _MAX_PARAGRAPH_LEN:
        added = False
        if (
            hi < len(sentences)
            and total_len + len(sentences[hi]) + 1 <= _MAX_PARAGRAPH_LEN
        ):
            selected.append(hi)
            total_len += len(sentences[hi]) + 1
            hi += 1
            added = True
        if lo >= 0 and total_len + len(sentences[lo]) + 1 <= _MAX_PARAGRAPH_LEN:
            selected.append(lo)
            total_len += len(sentences[lo]) + 1
            lo -= 1
            added = True
        if not added:
            break

    selected.sort()
    prefix = "… " if selected[0] > 0 else ""
    suffix = " …" if selected[-1] < len(sentences) - 1 else ""
    return prefix + " ".join(sentences[i] for i in selected) + suffix


def _hard_truncate(para: str, citation_text: str) -> str:
    """Fallback truncation when sentence splitting isn't possible."""
    cite_pos = para.find(citation_text)
    if cite_pos != -1 and cite_pos + len(citation_text) > _MAX_PARAGRAPH_LEN:
        half = _MAX_PARAGRAPH_LEN // 2
        center = cite_pos + len(citation_text) // 2
        win_start = max(0, center - half)
        win_end = min(len(para), center + half)
        prefix = "… " if win_start > 0 else ""
        suffix = " …" if win_end < len(para) else ""
        return prefix + para[win_start:win_end].strip() + suffix
    return para[:_MAX_PARAGRAPH_LEN].rstrip() + " …"


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
