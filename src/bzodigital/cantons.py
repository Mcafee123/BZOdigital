"""Canton scraper registry — generic cache and URL lookup for per-canton Gemeinde mappings."""

import json
from collections.abc import Awaitable, Callable
from pathlib import Path

from thefuzz import fuzz, process

CANTON_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cantons"

# Type for a canton scraper function
type CantonScraper = Callable[[], Awaitable[list[dict[str, str]]]]

# Registry of canton scrapers
SCRAPERS: dict[str, CantonScraper] = {}


def register(canton_id: str) -> Callable:
    """Decorator to register a canton scraper."""
    def decorator(fn: CantonScraper) -> CantonScraper:
        SCRAPERS[canton_id] = fn
        return fn
    return decorator


def cache_path(canton_id: str) -> Path:
    return CANTON_CACHE_DIR / f"{canton_id}.json"


def load_canton(canton_id: str) -> list[dict[str, str]] | None:
    """Load cached canton name→URL mapping, or None if not cached."""
    p = cache_path(canton_id)
    if p.exists():
        return json.loads(p.read_text())
    return None


def save_canton(canton_id: str, data: list[dict[str, str]]) -> Path:
    """Save canton name→URL mapping to cache."""
    p = cache_path(canton_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return p


async def get_canton(canton_id: str, force_refresh: bool = False) -> list[dict[str, str]] | None:
    """Get canton mapping: from cache, or scrape if scraper exists. Returns None if no scraper."""
    if not force_refresh:
        cached = load_canton(canton_id)
        if cached is not None:
            return cached
    scraper = SCRAPERS.get(canton_id)
    if scraper is None:
        return None
    data = await scraper()
    if data:
        save_canton(canton_id, data)
    return data


def find_url(name: str, canton_data: list[dict[str, str]]) -> str | None:
    """Fuzzy-find a municipality URL within canton data. Returns best match URL or None."""
    if not canton_data:
        return None
    names = [g["name"] for g in canton_data]
    results = process.extract(name, names, scorer=fuzz.WRatio, limit=1)
    if results and results[0][1] >= 80:
        best_name = results[0][0]
        gemeinde = next(g for g in canton_data if g["name"] == best_name)
        return gemeinde["url"]
    return None


# Auto-discover canton scrapers
from bzodigital import cantons_zh as _  # noqa: F401, E402
