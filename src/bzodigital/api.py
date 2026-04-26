"""FastAPI REST API for BZO document search."""

import asyncio
import json
import os
import re
import secrets
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from urllib.parse import unquote
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from bzodigital.bfs import Municipality, fuzzy_find_municipality, load_bfs, update_bfs_register
from bzodigital.cantons import find_url, get_canton
from bzodigital.db import (
    add_label,
    clear_search_cache,
    delete_annotation,
    get_annotations,
    get_cached_search,
    get_labels,
    init_db,
    save_search_cache,
    upsert_annotation,
)
from bzodigital.converter import convert_pdf_stream, download_pdf
from bzodigital.enrichment import enrich_markdown_safe
from bzodigital.profiles import DEFAULT_PROFILE, PROFILES
from bzodigital.search import (
    extract_pdfs,
    filter_pdfs_by_metadata,
    has_serper_key,
    infer_domain,
    search_or_crawl_open,
    search_or_crawl_site,
)

security = HTTPBasic()

AUTH_USER = os.environ.get("BASIC_AUTH_USER", "")
AUTH_PASS = os.environ.get("BASIC_AUTH_PASS", "")


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    if not AUTH_USER:
        return  # auth disabled when env vars are not set
    correct_user = secrets.compare_digest(credentials.username.encode(), AUTH_USER.encode())
    correct_pass = secrets.compare_digest(credentials.password.encode(), AUTH_PASS.encode())
    if not (correct_user and correct_pass):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


app = FastAPI(
    title="BZO Digital API",
    description="REST API for finding Bau- und Zonenordnungen of Swiss municipalities.",
    dependencies=[Depends(verify_credentials)],
)

STATIC_DIR = Path(__file__).parent / "static"


class AuthStaticFiles(StaticFiles):
    """StaticFiles that inherits Basic Auth from the app-level dependency."""

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)
            credentials = await security(request)
            verify_credentials(credentials)
        await super().__call__(scope, receive, send)


app.mount("/static", AuthStaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


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


class LabelCreate(BaseModel):
    name: str


class AnnotationRequest(BaseModel):
    pdf_url: str
    pdf_title: str = ""
    labels: list[str] = []
    selected: bool = False


class AnnotationResponse(BaseModel):
    id: int
    municipality_bfs_nr: int
    pdf_url: str
    pdf_title: str
    labels: list[str]
    selected: bool
    created_at: str
    updated_at: str


class ProcessedPdfResponse(BaseModel):
    municipality: str
    canton: str
    bfs_nr: int
    pdfs: list[AnnotationResponse]
    has_annotations: bool


class ProcessPdfItem(BaseModel):
    url: str
    title: str = ""


class ProcessRequest(BaseModel):
    pdfs: list[ProcessPdfItem] | None = None  # None = use selected annotations


class FileState(BaseModel):
    url: str
    title: str
    status: str = "pending"  # pending | processing | done | failed
    progress: str = ""
    error: str = ""
    markdown_path: str = ""
    page_count: int | None = None


class JobState(BaseModel):
    job_id: str
    municipality: str
    status: str = "running"  # running | done | failed
    files: list[FileState] = []


# --- Startup ---

_seeding = False


@app.on_event("startup")
async def on_startup():
    init_db()
    if not load_bfs():
        asyncio.create_task(_seed_in_background())


async def _seed_in_background():
    global _seeding
    _seeding = True
    try:
        print("[startup] BFS register empty, downloading...")
        await update_bfs_register()
        print("[startup] BFS register loaded. Refreshing ZH canton mapping...")
        await get_canton("zh", force_refresh=True)
        print("[startup] Seeding complete.")
    except Exception as e:
        print(f"[startup] Seeding failed: {e}")
    finally:
        _seeding = False


@app.get("/api/status")
def get_status():
    """Check if the API is ready (seeding may be in progress)."""
    return {"ready": not _seeding, "seeding": _seeding}


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


# --- Labels ---


@app.get("/api/labels", response_model=list[str])
def list_labels():
    """List all available labels."""
    return get_labels()


@app.post("/api/labels")
def create_label(body: LabelCreate):
    """Create a new label."""
    try:
        name = add_label(body.name.strip())
        return {"name": name}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


# --- Annotations ---


@app.get("/api/bzo/{municipality_name}/annotations", response_model=list[AnnotationResponse])
def get_municipality_annotations(municipality_name: str):
    """Get all PDF annotations for a municipality."""
    muni = _resolve_municipality(municipality_name)
    return get_annotations(muni.bfs_nr)


@app.put("/api/bzo/{municipality_name}/annotations", response_model=AnnotationResponse)
def put_annotation(municipality_name: str, body: AnnotationRequest):
    """Create or update a PDF annotation (keyed by municipality + pdf_url)."""
    muni = _resolve_municipality(municipality_name)
    return upsert_annotation(
        bfs_nr=muni.bfs_nr,
        pdf_url=body.pdf_url,
        pdf_title=body.pdf_title,
        labels=body.labels,
        selected=body.selected,
    )


@app.delete("/api/bzo/{municipality_name}/annotations/{annotation_id}")
def remove_annotation(municipality_name: str, annotation_id: int):
    """Delete an annotation."""
    _resolve_municipality(municipality_name)  # validate name
    delete_annotation(annotation_id)
    return {"message": "Deleted."}


@app.get("/api/bzo/{municipality_name}/processed", response_model=ProcessedPdfResponse)
async def get_processed(municipality_name: str):
    """Get labeled/selected PDFs for a municipality. Returns all PDFs if none are annotated."""
    muni = _resolve_municipality(municipality_name)
    annotations = get_annotations(muni.bfs_nr)

    has_annotations = len(annotations) > 0
    if has_annotations:
        # Return only selected ones
        selected = [a for a in annotations if a["selected"]]
        return ProcessedPdfResponse(
            municipality=muni.name,
            canton=muni.canton,
            bfs_nr=muni.bfs_nr,
            pdfs=[AnnotationResponse(**a) for a in selected],
            has_annotations=True,
        )

    # No annotations — return all PDFs from search results
    profile = PROFILES[DEFAULT_PROFILE]
    cache_key = _make_cache_key(muni, DEFAULT_PROFILE)
    cached_results = get_cached_search(cache_key)

    all_pdfs: list[AnnotationResponse] = []
    if cached_results:
        from bzodigital.search import extract_pdfs, filter_pdfs_by_metadata
        seen: set[str] = set()
        raw_pdfs: list[dict] = []
        tasks = [extract_pdfs(r["url"]) for r in cached_results]
        results_pdfs = await asyncio.gather(*tasks, return_exceptions=True)
        for page_pdfs in results_pdfs:
            if isinstance(page_pdfs, Exception):
                continue
            for pdf in page_pdfs:
                if pdf["url"] not in seen:
                    seen.add(pdf["url"])
                    raw_pdfs.append(pdf)
        matched, _ = filter_pdfs_by_metadata(raw_pdfs, profile)
        now = datetime.utcnow().isoformat()
        all_pdfs = [
            AnnotationResponse(
                id=0, municipality_bfs_nr=muni.bfs_nr,
                pdf_url=p["url"], pdf_title=p.get("title", ""),
                labels=[], selected=False, created_at=now, updated_at=now,
            )
            for p in matched
        ]

    return ProcessedPdfResponse(
        municipality=muni.name,
        canton=muni.canton,
        bfs_nr=muni.bfs_nr,
        pdfs=all_pdfs,
        has_annotations=False,
    )


# --- Processing ---

_jobs: dict[str, JobState] = {}
_queues: dict[str, asyncio.Queue] = {}

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _slug(name: str) -> str:
    """Municipality name → filesystem slug (lowercase, no spaces)."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _pdf_filename(url: str) -> str:
    """Extract a clean filename from a PDF URL."""
    raw = unquote(url.split("/")[-1].split("?")[0])
    return raw if raw.endswith(".pdf") else raw + ".pdf"


@app.post("/api/process/{municipality_name}")
async def start_processing(municipality_name: str, body: ProcessRequest | None = None):
    """Start converting selected PDFs to Markdown via DocConverter."""
    muni = _resolve_municipality(municipality_name)

    if body and body.pdfs:
        pdf_list = [(p.url, p.title) for p in body.pdfs]
    else:
        anns = get_annotations(muni.bfs_nr)
        selected = [a for a in anns if a["selected"]]
        if not selected:
            raise HTTPException(400, "No PDFs selected for processing.")
        pdf_list = [(a["pdf_url"], a["pdf_title"]) for a in selected]

    # Filter out files that already have a converted markdown
    slug = _slug(muni.name)
    md_dir = DATA_DIR / slug / "md"
    to_process = []
    skipped = []
    for url, title in pdf_list:
        md_name = Path(_pdf_filename(url)).stem + ".md"
        if (md_dir / md_name).exists():
            skipped.append({"url": url, "title": title or _pdf_filename(url), "markdown_path": str((md_dir / md_name).relative_to(DATA_DIR))})
        else:
            to_process.append((url, title))

    if not to_process:
        return {"job_id": None, "files_count": 0, "skipped": skipped, "message": "All files already converted."}

    job_id = str(uuid4())
    files = [FileState(url=url, title=title or _pdf_filename(url)) for url, title in to_process]
    job = JobState(job_id=job_id, municipality=muni.name, files=files)
    _jobs[job_id] = job

    queue: asyncio.Queue = asyncio.Queue()
    _queues[job_id] = queue

    asyncio.create_task(_process_job(job_id, muni.name, queue))

    return {"job_id": job_id, "files_count": len(files), "skipped": skipped}


@app.get("/api/process/{job_id}")
def get_job_status(job_id: str):
    """Poll current job state."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    return job


@app.get("/api/process/{job_id}/stream")
async def stream_job(job_id: str):
    """SSE stream of processing progress."""
    queue = _queues.get(job_id)
    if not queue:
        raise HTTPException(404, "Job not found.")

    async def event_generator():
        # Send current state as initial snapshot
        job = _jobs.get(job_id)
        if job:
            yield f"event: snapshot\ndata: {job.model_dump_json()}\n\n"

        while True:
            event = await queue.get()
            if event is None:
                # Job finished
                job = _jobs.get(job_id)
                completed = sum(1 for f in job.files if f.status == "done") if job else 0
                failed = sum(1 for f in job.files if f.status == "failed") if job else 0
                yield f"event: done\ndata: {json.dumps({'completed': completed, 'failed': failed})}\n\n"
                break
            yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/preview/{job_id}/{file_index}")
def get_preview(job_id: str, file_index: int):
    """Return the saved markdown for a processed file."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    if file_index < 0 or file_index >= len(job.files):
        raise HTTPException(404, "File index out of range.")
    f = job.files[file_index]
    if f.status != "done" or not f.markdown_path:
        raise HTTPException(400, "File not yet processed.")
    md_path = DATA_DIR / f.markdown_path
    if not md_path.exists():
        raise HTTPException(404, "Markdown file not found.")
    return {"filename": md_path.name, "markdown": md_path.read_text(encoding="utf-8")}


@app.get("/api/files/{municipality_name}")
def list_converted_files(municipality_name: str):
    """List already-converted markdown files for a municipality."""
    muni = _resolve_municipality(municipality_name)
    slug = _slug(muni.name)
    md_dir = DATA_DIR / slug / "md"
    if not md_dir.exists():
        return {"municipality": muni.name, "files": []}
    files = []
    for p in sorted(md_dir.glob("*.md")):
        files.append({
            "filename": p.name,
            "path": str(p.relative_to(DATA_DIR)),
            "size": p.stat().st_size,
        })
    return {"municipality": muni.name, "files": files}


@app.get("/api/files/{municipality_name}/{filename}")
def get_file_preview(
    municipality_name: str,
    filename: str,
    enriched: bool = Query(default=False, description="Enrich with law citation links on the fly"),
):
    """Return a converted markdown file, optionally enriched with law citations."""
    muni = _resolve_municipality(municipality_name)
    slug = _slug(muni.name)
    md_path = DATA_DIR / slug / "md" / filename
    if not md_path.exists() or not md_path.suffix == ".md":
        raise HTTPException(404, "File not found.")

    markdown = md_path.read_text(encoding="utf-8")

    if enriched:
        result = enrich_markdown_safe(markdown)
        if result:
            return {"filename": md_path.name, "markdown": result["markdown"], "enriched": True}

    return {"filename": md_path.name, "markdown": markdown, "enriched": False}


async def _process_job(job_id: str, municipality_name: str, queue: asyncio.Queue):
    """Background task: process each PDF in the job."""
    job = _jobs[job_id]
    slug = _slug(municipality_name)
    out_dir = DATA_DIR / slug / "md"
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, file_state in enumerate(job.files):
        file_state.status = "processing"
        await queue.put({"type": "file_start", "data": {"file_index": i, "url": file_state.url, "title": file_state.title}})

        try:
            # Download
            pdf_bytes = await download_pdf(file_state.url)

            # Convert via DocConverter with progress relay
            async def on_progress(data, _idx=i):
                file_state.progress = json.dumps(data)
                await queue.put({"type": "progress", "data": {"file_index": _idx, **data}})

            result = await convert_pdf_stream(pdf_bytes, _pdf_filename(file_state.url), on_progress)

            # Save markdown — content may be in sections rather than top-level
            markdown = result.get("markdown", "")
            if not markdown:
                sections = result.get("sections", [])
                markdown = "\n\n".join(s.get("markdown", "") for s in sections)

            md_name = Path(_pdf_filename(file_state.url)).stem + ".md"
            md_path = out_dir / md_name
            md_path.write_text(markdown, encoding="utf-8")

            file_state.status = "done"
            file_state.markdown_path = str(md_path.relative_to(DATA_DIR))
            file_state.page_count = result.get("page_count")
            await queue.put({
                "type": "file_done",
                "data": {"file_index": i, "markdown_path": file_state.markdown_path, "page_count": file_state.page_count},
            })

        except Exception as e:
            file_state.status = "failed"
            file_state.error = str(e)
            await queue.put({"type": "file_error", "data": {"file_index": i, "error": str(e)}})

    # Mark job complete
    job.status = "failed" if all(f.status == "failed" for f in job.files) else "done"
    await queue.put(None)  # sentinel


# --- Helpers ---


def _resolve_municipality(name: str) -> Municipality:
    """Fuzzy-resolve a municipality name, raise 404 if not found."""
    municipalities = load_bfs()
    if not municipalities:
        raise HTTPException(status_code=500, detail="BFS register not loaded.")
    matches = fuzzy_find_municipality(name, municipalities, limit=1)
    if not matches or matches[0][1] < 60:
        raise HTTPException(status_code=404, detail=f"Municipality '{name}' not found.")
    return matches[0][0]


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
    uvicorn.run("bzodigital.api:app", host="0.0.0.0", port=7000, reload=True)
