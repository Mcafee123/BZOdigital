"""Rules-first classifier for BZO-related PDFs.

The classifier produces internal category keys (e.g. "regulation_old"); the
human-readable labels written into PdfAnnotation.labels_json are sourced from
the `label` table in the database — substring rules pick the right row per
category. Anything we can't classify, or a category that doesn't match any
existing label, is left without a proposed label so the operator can decide.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

# Internal sentinel for "looks like a regulation but old/new not yet decided".
_REGULATION = "regulation"

# Each rule receives a lowercased label name and returns True if the row
# represents the given category. The first matching DB row wins.
_LABEL_MATCHERS: dict[str, Callable[[str], bool]] = {
    "synopsis":              lambda n: "synops" in n,
    "regulation_old":        lambda n: ("zonenordnung" in n or re.search(r"\bbzo\b", n) is not None) and "alt" in n,
    "regulation_new":        lambda n: ("zonenordnung" in n or re.search(r"\bbzo\b", n) is not None) and "neu" in n,
    "einwendungsbericht":    lambda n: "einwendung" in n,
    "erlauterungsbericht":   lambda n: "erläut" in n or "erlaut" in n,
    "versammlungsbeschluss": lambda n: "versammlung" in n,
}

# Categories that must be unique per municipality. If two or more PDFs match
# one of these, none gets the label — the operator picks the right one.
_SINGLE_INSTANCE = ("synopsis", "erlauterungsbericht", "versammlungsbeschluss")

_GERMAN_MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4,
    "mai": 5, "juni": 6, "juli": 7, "august": 8, "september": 9,
    "oktober": 10, "november": 11, "dezember": 12,
}


def _filename_from_url(url: str) -> str:
    path = urlparse(url).path
    return unquote(PurePosixPath(path).name)


def _norm(text: str) -> str:
    return text.lower().strip()


def classify_pdf(url: str, title: str) -> str | None:
    """Return a category key, or None when nothing in the filename/title is a
    BZO-document signal. For BZO-itself documents the bare key "regulation"
    is returned — old/new is decided by resolve_batch once all files are known.
    """
    fname = _filename_from_url(url)
    text = _norm(f"{fname} {title}")

    # Reject obvious non-law artefacts up front. The `öa - ` prefix is the
    # publication notice; `info - ` is the citizen-info presentation.
    if re.search(r"(^|\s)öa\s*-", text) or re.search(r"(^|\s)info\s*-", text):
        return None
    if "publikationstext" in text or "infoveranstaltung" in text:
        return None

    if "synopse" in text or "synopsis" in text or re.search(r"(^|\s)sy\s*-", text):
        return "synopsis"

    if "einwendung" in text:
        return "einwendungsbericht"

    if (
        "erläut" in text
        or "erlaut" in text
        or re.search(r"(^|\s)erl\s*-", text)
    ):
        return "erlauterungsbericht"

    if "versammlungsbeschluss" in text or "gemeindeversammlung" in text:
        return "versammlungsbeschluss"

    if (
        "bau- und zonenordnung" in text
        or "bau und zonenordnung" in text
        or re.search(r"\bbzo\b", text)
        or "zonenordnung" in text
    ):
        return _REGULATION

    return None


def _resolve_label(category: str, db_labels: Iterable[str]) -> str | None:
    """Pick the DB label name that matches a category, or None if no row fits."""
    matcher = _LABEL_MATCHERS.get(category)
    if matcher is None:
        return None
    for label in db_labels:
        if matcher(label.lower()):
            return label
    return None


def _extract_sort_key(url: str, title: str) -> tuple[int, tuple[int, int, int]]:
    """Return a sort key that orders BZO files newest → oldest under ascending sort.

    Priority bands keep explicit hints from being outranked by parsed dates:
    0 = explicit "aktuell"/"neu" hint, 1 = has a parsed date,
    2 = explicit "previous"/"alt" hint, 3 = nothing — falls last.
    Within the date band the tuple is negated so larger dates come first.
    """
    fname = _filename_from_url(url)
    text = _norm(f"{fname} {title}")

    has_new_hint = bool(re.search(r"\b(aktuell|neu)\b", text))
    has_old_hint = bool(re.search(r"\b(previous|alt|vorgaengig|vorgängig)\b", text))

    date = _parse_date(text)
    neg_date = tuple(-v for v in date) if date else (0, 0, 0)

    if has_new_hint and not has_old_hint:
        return (0, neg_date)
    if date:
        return (1, neg_date)
    if has_old_hint:
        return (2, (0, 0, 0))
    return (3, (0, 0, 0))


def _parse_date(text: str) -> tuple[int, int, int] | None:
    """Extract a (year, month, day) from German date strings, year-only OK."""
    m = re.search(
        r"(\d{1,2})\.?\s+(januar|februar|märz|maerz|april|mai|juni|juli|august|september|oktober|november|dezember)\s+((?:19|20)\d{2})",
        text,
    )
    if m:
        day = int(m.group(1))
        month = _GERMAN_MONTHS[m.group(2)]
        year = int(m.group(3))
        return (year, month, day)

    m = re.search(r"\b(19|20)(\d{2})\b", text)
    if m:
        return (int(m.group(1) + m.group(2)), 0, 0)

    return None


def resolve_batch(
    items: Iterable[dict],
    db_labels: Iterable[str] | None = None,
) -> dict[str, list[str]]:
    """Classify a whole batch of PDFs for one municipality.

    items: iterable of {"url": str, "title": str}.
    db_labels: list of label names from the `label` table — the source of truth
    for the strings written into PdfAnnotation.labels_json. If omitted, fetched
    lazily via db.get_labels() so this module stays unit-testable without a DB.

    Returns {url: [label, ...]}. Documents that don't match any category, or
    whose category has no corresponding DB label, get an empty list — the
    classifier deliberately does not propose a catch-all "Andere" tag.
    """
    items = list(items)
    if db_labels is None:
        from nupla.pipeline.db import get_labels  # local import to avoid cycles in tests
        db_labels = get_labels()
    db_labels = list(db_labels)

    raw: list[tuple[dict, str | None]] = [
        (i, classify_pdf(i["url"], i.get("title", ""))) for i in items
    ]

    suggestions: dict[str, list[str]] = {i["url"]: [] for i in items}

    def assign(url: str, category: str) -> None:
        label = _resolve_label(category, db_labels)
        if label:
            suggestions[url] = [label]

    # Single-instance categories: assign only when exactly one candidate exists.
    for cat in _SINGLE_INSTANCE:
        candidates = [it for it, c in raw if c == cat]
        if len(candidates) == 1:
            assign(candidates[0]["url"], cat)

    # einwendungsbericht: not enforced as unique (multiple sub-reports may exist).
    for it, c in raw:
        if c == "einwendungsbericht":
            assign(it["url"], "einwendungsbericht")

    # Regulation old vs new: compare across candidates.
    regulations = [it for it, c in raw if c == _REGULATION]
    if len(regulations) == 1:
        assign(regulations[0]["url"], "regulation_new")
    elif len(regulations) >= 2:
        ranked = sorted(
            regulations,
            key=lambda it: _extract_sort_key(it["url"], it.get("title", "")),
        )
        assign(ranked[0]["url"], "regulation_new")
        assign(ranked[-1]["url"], "regulation_old")

    return suggestions
