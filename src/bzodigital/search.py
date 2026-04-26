"""Search Gemeinde websites for zoning documents."""

import os
import re
from collections import Counter
from urllib.parse import unquote, urljoin, urlparse

import httpx

from bzodigital.profiles import SearchProfile

SERPER_URL = "https://google.serper.dev/search"
NOISE_DOMAINS = frozenset({
    "de.wikipedia.org", "en.wikipedia.org", "fr.wikipedia.org",
    "www.wikipedia.org", "www.facebook.com", "twitter.com", "x.com",
    "www.instagram.com", "www.linkedin.com", "www.youtube.com",
})


def has_serper_key() -> bool:
    """Check if Serper API key is configured."""
    return bool(os.environ.get("SERPER_API_KEY"))


def _get_serper_key() -> str:
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        raise RuntimeError("SERPER_API_KEY not set. Add it to your .env file.")
    return api_key


async def _serper_paginate(query: str, max_results: int) -> list[dict[str, str]]:
    """Run a paginated Serper search, return deduplicated results."""
    api_key = _get_serper_key()

    results: list[dict[str, str]] = []
    seen: set[str] = set()
    page = 1

    async with httpx.AsyncClient() as client:
        while len(results) < max_results:
            resp = await client.post(
                SERPER_URL,
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": query, "num": 10, "page": page},
            )
            resp.raise_for_status()
            data = resp.json()

            organic = data.get("organic", [])
            if not organic:
                break

            for item in organic:
                url = item.get("link", "")
                if url and url not in seen:
                    seen.add(url)
                    results.append({
                        "url": url,
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                    })

            if len(organic) < 10:
                break

            page += 1

    return results[:max_results]


async def search_site(base_url: str, profile: SearchProfile, max_results: int = 50) -> list[dict[str, str]]:
    """Search within a specific domain using site: operator."""
    domain = urlparse(base_url).netloc or urlparse(base_url).path.split("/")[0]
    query = f"{profile.search_query} site:{domain}"
    return await _serper_paginate(query, max_results)


async def search_open(village_name: str, profile: SearchProfile, max_results: int = 50) -> list[dict[str, str]]:
    """Search without site: scope — for municipalities with no known URL."""
    query = f'{profile.search_query} "{village_name}"'
    return await _serper_paginate(query, max_results)


def infer_domain(results: list[dict[str, str]]) -> str | None:
    """Find the most common .ch domain in search results (likely the official Gemeinde site)."""
    domains = [urlparse(r["url"]).netloc for r in results]
    if not domains:
        return None
    counts = Counter(domains)
    for domain, _count in counts.most_common():
        if domain not in NOISE_DOMAINS and domain.endswith(".ch"):
            return domain
    return None


async def search_or_crawl_site(base_url: str, profile: SearchProfile, max_results: int = 50) -> list[dict[str, str]]:
    """Search with Serper if API key is available, otherwise crawl the site."""
    if has_serper_key():
        return await search_site(base_url, profile, max_results)
    from bzodigital.crawler import crawl_site
    # Crawler needs to visit many pages to find PDFs — max_pages != max_results
    return await crawl_site(base_url, profile, max_pages=200)


async def search_or_crawl_open(village_name: str, base_url: str | None, profile: SearchProfile, max_results: int = 50) -> list[dict[str, str]]:
    """Open search with Serper if available, otherwise crawl the given URL."""
    if has_serper_key():
        return await search_open(village_name, profile, max_results)
    if base_url:
        from bzodigital.crawler import crawl_site
        return await crawl_site(base_url, profile, max_pages=max_results)
    return []


def parse_pdf_links(html: str, base_url: str) -> list[dict[str, str]]:
    """Parse PDF links from HTML content.

    Detects PDFs via 4 signals:
    1. .pdf in the href
    2. title="*.pdf" attribute on the <a> tag
    3. "(PDF, ...)" text after the </a> tag (iCMS/iWeb pattern)
    4. "(PDF, ...)" inside the link inner HTML
    """
    pdfs: list[dict[str, str]] = []
    seen: set[str] = set()

    for match in re.finditer(
        r'(<a\s[^>]*?href=["\']([^"\']+)["\'][^>]*>)(.*?)</a>',
        html, re.IGNORECASE | re.DOTALL,
    ):
        tag = match.group(1)
        href = match.group(2)
        inner = match.group(3)

        # Check for title="...pdf"
        title_match = re.search(r'title=["\']([^"\']*\.pdf)["\']', tag, re.IGNORECASE)

        # Check for .pdf in href
        href_is_pdf = ".pdf" in href.lower().split("?")[0]

        # Check for "(PDF, ...)" in surrounding context (common CMS pattern)
        after_tag = html[match.end():match.end() + 200]
        context_pdf = bool(re.search(r'\(PDF[,\s]', after_tag, re.IGNORECASE))
        # Also check inside the link inner html
        inner_pdf = bool(re.search(r'\(PDF[,\s]', inner, re.IGNORECASE))

        # Check title attribute without .pdf extension
        title_attr = re.search(r'title=["\']([^"\']+)["\']', tag)

        is_pdf = href_is_pdf or bool(title_match) or context_pdf or inner_pdf
        if not is_pdf:
            continue

        full_url = urljoin(base_url, href)
        if full_url in seen:
            continue
        seen.add(full_url)

        title = ""
        if title_match:
            title = title_match.group(1)
        elif title_attr:
            title = title_attr.group(1)
        elif inner:
            title = re.sub(r'<[^>]+>', '', inner).strip()
        pdfs.append({"url": full_url, "title": title, "source": base_url})

    return pdfs


def _url_is_pdf(url: str) -> bool:
    """Check if a URL points to a PDF (ignoring query params)."""
    path = urlparse(url).path.lower()
    return path.endswith(".pdf")


async def extract_pdfs(page_url: str) -> list[dict[str, str]]:
    """Extract all PDF links from an HTML page."""
    if _url_is_pdf(page_url):
        return [{"url": page_url, "title": "", "source": page_url}]

    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        resp = await client.get(
            page_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; BZOdigital/0.1)"},
        )
        resp.raise_for_status()

    return parse_pdf_links(resp.text, page_url)


def filter_pdfs_by_metadata(pdfs: list[dict[str, str]], profile: SearchProfile) -> tuple[list[dict], list[dict]]:
    """Split PDFs into matched (by filename/title) and ambiguous (need content check)."""
    matched = []
    ambiguous = []

    for pdf in pdfs:
        url_decoded = unquote(pdf["url"])
        if profile.matches_metadata(url_decoded, pdf.get("title", "")):
            pdf["match"] = "metadata"
            matched.append(pdf)
        else:
            ambiguous.append(pdf)

    return matched, ambiguous


async def check_pdf_content(pdf_url: str, profile: SearchProfile) -> bool:
    """Download first chunk of a PDF and check if content matches filter terms."""
    try:
        import fitz  # pymupdf
    except ImportError:
        return False

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            resp = await client.get(
                pdf_url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; BZOdigital/0.1)"},
            )
            resp.raise_for_status()

        doc = fitz.open(stream=resp.content, filetype="pdf")
        # Check first 3 pages
        text = ""
        for page_num in range(min(3, len(doc))):
            text += doc[page_num].get_text()
        doc.close()

        return profile.matches_text(text)
    except Exception:
        return False
