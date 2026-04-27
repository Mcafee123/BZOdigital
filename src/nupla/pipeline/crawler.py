"""Sitemap + BFS crawler for finding BZO documents without external search APIs."""

import re
import xml.etree.ElementTree as ET
from collections import deque
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from nupla.pipeline.profiles import SearchProfile
from nupla.pipeline.search import parse_pdf_links

IGNORED_EXTENSIONS = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico", ".webp",
    ".zip", ".doc", ".docx", ".xls", ".xlsx", ".mp4", ".mp3",
    ".css", ".js", ".woff", ".woff2", ".ttf", ".eot",
})

CLIENT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BZOdigital/0.1)",
}


def _is_valid_internal_url(url: str, base_domain: str) -> bool:
    """Check if URL belongs to the same domain and is likely an HTML page."""
    try:
        parsed = urlparse(url)
        if base_domain not in parsed.netloc:
            return False
        ext = parsed.path.rsplit(".", 1)[-1].lower() if "." in parsed.path else ""
        if f".{ext}" in IGNORED_EXTENSIONS:
            return False
        return True
    except Exception:
        return False


async def _fetch_page(client: httpx.AsyncClient, url: str) -> str | None:
    """Fetch a page, return HTML text or None."""
    try:
        resp = await client.get(url, timeout=10)
        ct = resp.headers.get("content-type", "").lower()
        if "text/html" in ct or "text/xml" in ct or "application/xml" in ct:
            return resp.text
        return None
    except Exception:
        return None


async def _crawl_via_sitemap(
    start_url: str, client: httpx.AsyncClient, profile: SearchProfile,
) -> list[dict[str, str]] | None:
    """Try sitemap.xml, scan promising pages for PDFs."""
    base = start_url.rstrip("/") + "/"
    sitemap_url = urljoin(base, "sitemap.xml")

    html = await _fetch_page(client, sitemap_url)
    if not html or "<urlset" not in html:
        return None

    # Strip namespace for easier parsing
    content = re.sub(r'\sxmlns="[^"]+"', "", html, count=1)
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return None

    urls_to_scan: list[str] = []
    found_pdfs: list[dict[str, str]] = []
    seen: set[str] = set()

    for loc in root.findall(".//loc"):
        url = (loc.text or "").strip()
        if not url:
            continue
        if url.lower().endswith(".pdf"):
            if any(t in url.lower() for t in profile.filter_terms):
                if url not in seen:
                    seen.add(url)
                    found_pdfs.append({"url": url, "title": "", "snippet": ""})
        else:
            url_lower = url.lower()
            if any(kw in url_lower for kw in profile.sitemap_keywords):
                urls_to_scan.append(url)

    # Scan promising pages for PDF links
    for url in urls_to_scan:
        page_html = await _fetch_page(client, url)
        if not page_html:
            continue
        for pdf in parse_pdf_links(page_html, url):
            if pdf["url"] not in seen:
                seen.add(pdf["url"])
                found_pdfs.append({"url": pdf["url"], "title": pdf.get("title", ""), "snippet": ""})

    return found_pdfs if found_pdfs else None


async def _crawl_bfs(
    start_url: str, client: httpx.AsyncClient, profile: SearchProfile, max_pages: int,
) -> list[dict[str, str]]:
    """Breadth-first crawl with keyword-prioritized queue."""
    parsed_start = urlparse(start_url)
    base_domain = parsed_start.netloc.replace("www.", "")

    visited: set[str] = set()
    queue: deque[str] = deque([start_url])
    found_pdfs: list[dict[str, str]] = []
    seen_pdfs: set[str] = set()
    pages_crawled = 0

    while queue and pages_crawled < max_pages:
        current_url = queue.popleft().split("#")[0]
        if current_url in visited:
            continue

        visited.add(current_url)
        pages_crawled += 1

        page_html = await _fetch_page(client, current_url)
        if not page_html:
            continue

        # Extract PDF links from this page
        for pdf in parse_pdf_links(page_html, current_url):
            if pdf["url"] not in seen_pdfs:
                seen_pdfs.add(pdf["url"])
                found_pdfs.append({"url": pdf["url"], "title": pdf.get("title", ""), "snippet": ""})

        # Find internal links to continue crawling
        soup = BeautifulSoup(page_html, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            absolute_url = urljoin(current_url, href).split("#")[0]

            if absolute_url in visited or absolute_url in queue:
                continue
            if not _is_valid_internal_url(absolute_url, base_domain):
                continue

            # Prioritize promising links
            if any(kw in absolute_url.lower() for kw in profile.sitemap_keywords):
                queue.appendleft(absolute_url)
            else:
                queue.append(absolute_url)

    return found_pdfs


async def crawl_site(
    base_url: str, profile: SearchProfile, max_pages: int = 100,
) -> list[dict[str, str]]:
    """Two-tier crawler: sitemap first, BFS crawl fallback.

    Returns list of dicts with url, title, snippet keys (same shape as search_site).
    """
    if not base_url.startswith("http"):
        base_url = "https://" + base_url

    async with httpx.AsyncClient(follow_redirects=True, headers=CLIENT_HEADERS) as client:
        # Stage 1: Try sitemap
        sitemap_results = await _crawl_via_sitemap(base_url, client, profile)
        if sitemap_results:
            return sitemap_results

        # Stage 2: BFS crawl fallback
        return await _crawl_bfs(base_url, client, profile, max_pages)
