"""Wrapper around law_enrichment for use in the pipeline."""

from bzodigital.law_enrichment import enrich_markdown


def enrich_markdown_safe(markdown: str) -> dict | None:
    """Run law enrichment, return result or None on error."""
    try:
        return enrich_markdown(markdown)
    except Exception as e:
        print(f"[enrichment] Failed: {e}")
        return None
