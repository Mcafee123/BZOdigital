"""Rules-first classifier for BZO-related PDFs.

Maps a discovered PDF (filename + title) to one of the default labels in
db.DEFAULT_LABELS, or to no label ("other"). Old vs new Bau- und Zonenordnung
is decided across the whole batch by comparing dates / hint prefixes — a single
file can't make that call.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Iterable
from urllib.parse import unquote, urlparse

# Category keys returned by classify_pdf. The string mapping below is the
# canonical label written into PdfAnnotation.labels_json.
CATEGORY_TO_LABEL: dict[str, str] = {
    "synopsis": "Synopse",
    "regulation_old": "Bau- und Zonenordnung alt",
    "regulation_new": "Bau- und Zonenordnung neu",
    "einwendungsbericht": "Einwendungsbericht gemäss § 7 PBG",
    "erlauterungsbericht": "Erläuterungsbericht gemäss Art. 47 RPV",
    "versammlungsbeschluss": "Gemeindeversammlungsbeschluss",
}

# Internal sentinel for "looks like a regulation but old/new not yet decided".
_REGULATION = "regulation"

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
    """Return a category key, or None for "other".

    For BZO-itself documents the bare key "regulation" is returned — old/new
    is decided by resolve_batch once all files are known.
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
        or "erläuter" in text
        or "erlauter" in text
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
    # "26. Januar 2026" or "26 Januar 2026"
    m = re.search(
        r"(\d{1,2})\.?\s+(januar|februar|märz|maerz|april|mai|juni|juli|august|september|oktober|november|dezember)\s+((?:19|20)\d{2})",
        text,
    )
    if m:
        day = int(m.group(1))
        month = _GERMAN_MONTHS[m.group(2)]
        year = int(m.group(3))
        return (year, month, day)

    # Bare year as last resort
    m = re.search(r"\b(19|20)(\d{2})\b", text)
    if m:
        return (int(m.group(1) + m.group(2)), 0, 0)

    return None


def resolve_batch(items: Iterable[dict]) -> dict[str, list[str]]:
    """Classify a whole batch of PDFs for one municipality.

    items: iterable of {"url": str, "title": str}.
    Returns {url: [label, ...]} — empty list means "no suggestion".
    Enforces uniqueness for single-instance categories and resolves
    regulation_old vs regulation_new from date / hint signals.
    """
    items = list(items)
    raw: list[tuple[dict, str | None]] = [(i, classify_pdf(i["url"], i.get("title", ""))) for i in items]

    suggestions: dict[str, list[str]] = {i["url"]: [] for i in items}

    # Single-instance categories: assign only when exactly one candidate exists.
    for cat in ("erlauterungsbericht", "versammlungsbeschluss"):
        candidates = [it for it, c in raw if c == cat]
        if len(candidates) == 1:
            suggestions[candidates[0]["url"]] = [CATEGORY_TO_LABEL[cat]]

    # Multi-instance OK (synopsis + einwendungsbericht can technically repeat
    # across municipalities; they only need to appear once per BZO revision —
    # but we don't enforce here, just label everything that matches).
    for cat in ("synopsis", "einwendungsbericht"):
        for it, c in raw:
            if c == cat:
                suggestions[it["url"]] = [CATEGORY_TO_LABEL[cat]]

    # Regulation old vs new: compare across candidates.
    regulations = [it for it, c in raw if c == _REGULATION]
    if len(regulations) == 1:
        suggestions[regulations[0]["url"]] = [CATEGORY_TO_LABEL["regulation_new"]]
    elif len(regulations) >= 2:
        ranked = sorted(
            regulations,
            key=lambda it: _extract_sort_key(it["url"], it.get("title", "")),
        )
        # ranked[0] = newest, ranked[-1] = oldest. Anything in between is left
        # unlabelled — operator decides.
        suggestions[ranked[0]["url"]] = [CATEGORY_TO_LABEL["regulation_new"]]
        suggestions[ranked[-1]["url"]] = [CATEGORY_TO_LABEL["regulation_old"]]

    return suggestions
