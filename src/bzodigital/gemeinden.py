"""Scrape and cache the list of Gemeinden from gpvzh.ch."""

import json
from pathlib import Path

CACHE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "gemeinden.json"
SOURCE_URL = "https://www.gpvzh.ch/gemeindenabisz"


async def scrape_gemeinden() -> list[dict[str, str]]:
    """Scrape Gemeinde names and website URLs from gpvzh.ch using Playwright."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(SOURCE_URL, wait_until="networkidle")

        # Grab all external links — these are the Gemeinde websites
        links = await page.query_selector_all("a[href^='http']")
        gemeinden: list[dict[str, str]] = []

        for link in links:
            href = (await link.get_attribute("href")) or ""
            text = (await link.inner_text()).strip()
            # Only keep external links (not gpvzh.ch nav), clean up the name
            if not text or not href or "gpvzh.ch" in href or "i-web.ch" in href:
                continue
            # Strip accessibility suffixes like "Externer Link..."
            name = text.split("\n")[0].strip()
            if name:
                gemeinden.append({"name": name, "url": href})

        await browser.close()

    # Deduplicate by name
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for g in gemeinden:
        if g["name"] not in seen:
            seen.add(g["name"])
            unique.append(g)

    return unique


def save_gemeinden(gemeinden: list[dict[str, str]]) -> Path:
    """Save Gemeinden list to cache file."""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(gemeinden, indent=2, ensure_ascii=False))
    return CACHE_PATH


def load_gemeinden() -> list[dict[str, str]] | None:
    """Load cached Gemeinden list, or None if not cached."""
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return None


async def get_gemeinden(force_refresh: bool = False) -> list[dict[str, str]]:
    """Get Gemeinden list, scraping if not cached."""
    if not force_refresh:
        cached = load_gemeinden()
        if cached:
            return cached

    gemeinden = await scrape_gemeinden()
    if gemeinden:
        save_gemeinden(gemeinden)
    return gemeinden
