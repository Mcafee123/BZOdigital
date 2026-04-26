"""FastAPI REST API for BZO document search."""

import asyncio
from datetime import datetime
from hashlib import sha256

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from pydantic import BaseModel

from bzodigital.bfs import Municipality, fuzzy_find_municipality, load_bfs
from bzodigital.cantons import find_url, get_canton
from bzodigital.db import (
    clear_search_cache,
    get_cached_search,
    init_db,
    save_search_cache,
)
from bzodigital.profiles import DEFAULT_PROFILE, PROFILES
from bzodigital.search import (
    extract_pdfs,
    filter_pdfs_by_metadata,
    has_serper_key,
    infer_domain,
    search_or_crawl_open,
    search_or_crawl_site,
)

app = FastAPI(
    title="BZO Digital API",
    description="REST API for finding Bau- und Zonenordnungen of Swiss municipalities.",
)


# --- Models ---


class SearchResult(BaseModel):
    url: str
    title: str
    snippet: str


class PdfResult(BaseModel):
    url: str
    title: str
    match: str


class BzoResponse(BaseModel):
    municipality: str
    canton: str
    domain: str | None
    search_method: str
    cached: bool
    results: list[SearchResult]
    pdfs: list[PdfResult] | None = None


class MunicipalityResponse(BaseModel):
    bfs_nr: int
    name: str
    canton: str


class BatchRequest(BaseModel):
    municipalities: list[str]


# --- Startup ---


@app.on_event("startup")
def on_startup():
    init_db()


# --- Endpoints ---


@app.get("/api/bzo/{municipality_name}", response_model=BzoResponse)
async def get_bzo(
    municipality_name: str,
    profile: str = Query(default=DEFAULT_PROFILE, description="Search profile"),
    pdfs: bool = Query(default=False, description="Extract and filter PDFs"),
):
    """Search for BZO documents for a municipality."""
    if profile not in PROFILES:
        raise HTTPException(status_code=400, detail=f"Unknown profile: {profile}")

    search_profile = PROFILES[profile]
    municipalities = load_bfs()
    if not municipalities:
        raise HTTPException(status_code=500, detail="BFS register not loaded. Run 'bzo bfs-update'.")

    matches = fuzzy_find_municipality(municipality_name, municipalities, limit=1)
    if not matches or matches[0][1] < 60:
        raise HTTPException(status_code=404, detail=f"Municipality '{municipality_name}' not found.")

    best_muni, _score = matches[0]

    # Check cache
    cache_key = _make_cache_key(best_muni, profile)
    cached_results = get_cached_search(cache_key)
    if cached_results is not None:
        return await _build_response(best_muni, cached_results, search_profile, cached=True, extract_pdfs_flag=pdfs)

    # Resolve URL and search
    canton_data = await get_canton(best_muni.canton.lower())
    base_url = find_url(best_muni.name, canton_data) if canton_data else None

    if base_url:
        results = await search_or_crawl_site(base_url, search_profile)
    else:
        results = await search_or_crawl_open(best_muni.name, None, search_profile)

    # Cache results
    save_search_cache(cache_key, results)

    return await _build_response(best_muni, results, search_profile, cached=False, extract_pdfs_flag=pdfs, base_url=base_url)


@app.post("/api/bzo/batch")
async def batch_search(request: BatchRequest, background_tasks: BackgroundTasks):
    """Queue multiple municipalities for background search/crawl."""
    background_tasks.add_task(_batch_worker, request.municipalities)
    return {
        "message": f"Search started for {len(request.municipalities)} municipalities.",
        "municipalities": request.municipalities,
    }


@app.delete("/api/bzo/cache")
def delete_cache():
    """Clear the search results cache."""
    clear_search_cache()
    return {"message": "Cache cleared."}


@app.get("/api/municipalities", response_model=list[MunicipalityResponse])
def list_municipalities(
    q: str | None = Query(default=None, description="Fuzzy search query"),
    canton: str | None = Query(default=None, description="Filter by canton (e.g. ZH)"),
    limit: int = Query(default=20, le=100),
):
    """List or search BFS municipalities."""
    municipalities = load_bfs()
    if canton:
        municipalities = [m for m in municipalities if m.canton.upper() == canton.upper()]

    if q:
        matches = fuzzy_find_municipality(q, municipalities, limit=limit)
        return [MunicipalityResponse(bfs_nr=m.bfs_nr, name=m.name, canton=m.canton) for m, _score in matches]

    return [MunicipalityResponse(bfs_nr=m.bfs_nr, name=m.name, canton=m.canton) for m in municipalities[:limit]]


# --- Helpers ---


def _make_cache_key(muni: Municipality, profile: str) -> str:
    return sha256(f"{muni.bfs_nr}:{profile}".encode()).hexdigest()[:16]


async def _build_response(
    muni: Municipality,
    results: list[dict],
    profile,
    cached: bool,
    extract_pdfs_flag: bool = False,
    base_url: str | None = None,
) -> BzoResponse:
    domain = infer_domain(results) if not base_url else base_url
    method = "serper" if has_serper_key() else "crawler"

    pdf_results = None
    if extract_pdfs_flag and results:
        all_pdfs: list[dict] = []
        seen: set[str] = set()
        tasks = [extract_pdfs(r["url"]) for r in results]
        results_pdfs = await asyncio.gather(*tasks, return_exceptions=True)
        for page_pdfs in results_pdfs:
            if isinstance(page_pdfs, Exception):
                continue
            for pdf in page_pdfs:
                if pdf["url"] not in seen:
                    seen.add(pdf["url"])
                    all_pdfs.append(pdf)

        matched, _ambiguous = filter_pdfs_by_metadata(all_pdfs, profile)
        pdf_results = [PdfResult(url=p["url"], title=p.get("title", ""), match=p.get("match", "metadata")) for p in matched]

    return BzoResponse(
        municipality=muni.name,
        canton=muni.canton,
        domain=domain,
        search_method=method,
        cached=cached,
        results=[SearchResult(**r) for r in results],
        pdfs=pdf_results,
    )


async def _batch_worker(municipality_names: list[str]):
    """Background worker that searches each municipality sequentially."""
    municipalities = load_bfs()
    for name in municipality_names:
        matches = fuzzy_find_municipality(name, municipalities, limit=1)
        if not matches or matches[0][1] < 60:
            continue

        best_muni, _ = matches[0]
        cache_key = _make_cache_key(best_muni, DEFAULT_PROFILE)

        if get_cached_search(cache_key) is not None:
            continue

        profile = PROFILES[DEFAULT_PROFILE]
        canton_data = await get_canton(best_muni.canton.lower())
        base_url = find_url(best_muni.name, canton_data) if canton_data else None

        if base_url:
            results = await search_or_crawl_site(base_url, profile)
        else:
            results = await search_or_crawl_open(best_muni.name, None, profile)

        save_search_cache(cache_key, results)


def start():
    """Entry point for bzo-api script."""
    import uvicorn
    uvicorn.run("bzodigital.api:app", host="0.0.0.0", port=8000, reload=True)
