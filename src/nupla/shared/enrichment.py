"""Safe wrapper around law_enrichment.

Catches errors from the citation-extraction engine so callers can degrade
gracefully (return raw markdown, skip a doc, etc.) instead of 500-ing.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from nupla.shared.law_enrichment import enrich_markdown, LawEntry


def enrich_markdown_safe(
    markdown: str,
    *,
    default_law: Optional[str | LawEntry] = None,
    custom_laws: Optional[Any] = None,
) -> dict | None:
    """Run law enrichment, return result or None on error."""
    try:
        return enrich_markdown(
            markdown,
            default_law=default_law,
            custom_laws=custom_laws,
        )
    except Exception as e:
        print(f"[enrichment] Failed: {e}")
        return None


def build_bzo_custom_law(bzo_filename: str) -> Dict[str, Any]:
    """Build a custom law entry for a municipality's BZO.

    The link_template points to the BZO file's heading anchors using the
    convention produced by ``build_heading_anchor`` (e.g. ``art-5``).

    ``default_markers`` restricts the default-law fallback to ``Art.``-style
    markers only, so bare ``§ 278`` references (PBG / cantonal law convention)
    don't incorrectly resolve to BZO.
    """
    return {
        "abbreviation": "BZO",
        "title": "Bau- und Zonenordnung",
        "link_template": f"{bzo_filename}#art-{{provision_lower}}",
        "default_markers": ["Art", "art", "Artikel", "article", "Article"],
    }
