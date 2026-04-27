"""Zurich canton scraper — extracts Gemeinde names and website URLs from gpvzh.ch."""

from nupla.pipeline.cantons import register

SOURCE_URL = "https://www.gpvzh.ch/gemeindenabisz"


@register("zh")
async def scrape_zurich() -> list[dict[str, str]]:
    """Scrape Gemeinde names and website URLs from gpvzh.ch using Playwright."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(SOURCE_URL, wait_until="networkidle")

        links = await page.query_selector_all("a[href^='http']")
        gemeinden: list[dict[str, str]] = []

        for link in links:
            href = (await link.get_attribute("href")) or ""
            text = (await link.inner_text()).strip()
            if not text or not href or "gpvzh.ch" in href or "i-web.ch" in href:
                continue
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
