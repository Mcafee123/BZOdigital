"""Fuzzy-find a Gemeinde and search its website for matching pages."""

import os
import re
from urllib.parse import unquote, urljoin, urlparse

import httpx
from thefuzz import fuzz, process

from bzodigital.profiles import SearchProfile


def fuzzy_find(query: str, gemeinden: list[dict[str, str]], limit: int = 5) -> list[dict]:
    """Fuzzy-match a query against Gemeinde names. Returns top matches with scores."""
    names = [g["name"] for g in gemeinden]
    results = process.extract(query, names, scorer=fuzz.WRatio, limit=limit)

    matches = []
    for name, score, *_ in results:
        gemeinde = next(g for g in gemeinden if g["name"] == name)
        matches.append({**gemeinde, "score": score})
    return matches


async def search_site(base_url: str, profile: SearchProfile, max_results: int = 50) -> list[dict[str, str]]:
    """Search a Gemeinde website for pages matching a profile using Serper.dev.

    Paginates automatically until results are exhausted or max_results is reached.
    """
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        raise RuntimeError("SERPER_API_KEY not set. Add it to your .env file.")

    domain = urlparse(base_url).netloc or urlparse(base_url).path.split("/")[0]
    search_query = f"{profile.search_query} site:{domain}"

    results: list[dict[str, str]] = []
    seen: set[str] = set()
    page = 1

    async with httpx.AsyncClient() as client:
        while len(results) < max_results:
            resp = await client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": search_query, "num": 10, "page": page},
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


async def extract_pdfs(page_url: str) -> list[dict[str, str]]:
    """Extract all PDF links from an HTML page."""
    if page_url.lower().endswith(".pdf"):
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
