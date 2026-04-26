"""Search profiles per canton — configures search queries and PDF filtering."""

from dataclasses import dataclass, field


@dataclass
class SearchProfile:
    """Defines how to search for and filter zoning documents."""

    # Serper query (supports Google OR syntax)
    search_query: str
    # Terms to match against PDF filename, link text, and content (case-insensitive)
    filter_terms: list[str]

    def matches_metadata(self, url: str, title: str) -> bool:
        """Check if a PDF matches based on URL filename or link text."""
        url_lower = url.lower()
        title_lower = title.lower()
        return any(
            term in url_lower or term in title_lower
            for term in self.filter_terms
        )

    def matches_text(self, text: str) -> bool:
        """Check if PDF content text matches filter terms."""
        text_lower = text.lower()
        return any(term in text_lower for term in self.filter_terms)


PROFILES: dict[str, SearchProfile] = {
    "zurich": SearchProfile(
        search_query='BZO OR "Bau- und Zonenordnung" OR "Zonenordnung" OR "Bauordnung"',
        filter_terms=[
            "bzo",
            "zonenordnung",
            "bauordnung",
            "zonenplan",
            "nutzungsplanung",
        ],
    ),
}

DEFAULT_PROFILE = "zurich"
