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

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from bzodigital.bfs import Municipality, fuzzy_find_municipality, load_bfs, update_bfs_register
from bzodigital.cantons import find_url, get_canton
from bzodigital.classify import fallback_label, resolve_batch as classify_batch
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
from bzodigital.converter import compare_documents, convert_pdf_stream, download_pdf
from bzodigital.enrichment import build_bzo_custom_law, enrich_markdown_safe
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


@app.get("/viewer")
async def viewer():
    return FileResponse(STATIC_DIR / "viewer.html")


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


@app.delete("/api/bzo/{municipality_name}/reset")
def reset_municipality(municipality_name: str):
    """Clear search cache and all annotations for a municipality."""
    muni = _resolve_municipality(municipality_name)
    clear_search_cache()
    for ann in get_annotations(muni.bfs_nr):
        delete_annotation(ann["id"])
    return {"message": f"Cache and annotations cleared for {muni.name}."}


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
        matched, ambiguous = filter_pdfs_by_metadata(raw_pdfs, profile)
        suggestions = _seed_classifications(muni.bfs_nr, [*matched, *ambiguous])
        fb = fallback_label(get_labels())
        now = datetime.utcnow().isoformat()
        all_pdfs = [
            AnnotationResponse(
                id=0, municipality_bfs_nr=muni.bfs_nr,
                pdf_url=p["url"], pdf_title=p.get("title", ""),
                labels=suggestions.get(p["url"], []),
                selected=bool(suggestions.get(p["url"])) and (
                    fb is None or suggestions[p["url"]][0] != fb
                ),
                created_at=now, updated_at=now,
            )
            for p in [*matched, *ambiguous]
        ]

    return ProcessedPdfResponse(
        municipality=muni.name,
        canton=muni.canton,
        bfs_nr=muni.bfs_nr,
        pdfs=all_pdfs,
        has_annotations=False,
    )


# --- Uploads ---


@app.post("/api/upload/{municipality_name}")
async def upload_pdf(municipality_name: str, request: Request, file: UploadFile = File(...)):
    """Upload a PDF and create an annotation for it."""
    muni = _resolve_municipality(municipality_name)
    slug = _slug(muni.name)

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported.")

    upload_dir = DATA_DIR / slug / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = upload_dir / file.filename
    content = await file.read()
    file_path.write_bytes(content)

    # Build a URL that points to our own serve endpoint
    base_url = str(request.base_url).rstrip("/")
    serve_url = f"{base_url}/api/uploads/{_slug(muni.name)}/{file.filename}"

    # Create annotation
    ann = upsert_annotation(
        bfs_nr=muni.bfs_nr,
        pdf_url=serve_url,
        pdf_title=file.filename,
        labels=[],
        selected=False,
    )

    return ann


@app.get("/api/uploads/{municipality_slug}/{filename}")
async def serve_upload(municipality_slug: str, filename: str):
    """Serve an uploaded PDF file."""
    file_path = DATA_DIR / municipality_slug / "uploads" / filename
    if not file_path.exists():
        raise HTTPException(404, "File not found.")
    return FileResponse(file_path, media_type="application/pdf", filename=filename)


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
    md_dir = DATA_DIR / slug / "md"
    md_path = md_dir / filename
    if not md_path.exists() or not md_path.suffix == ".md":
        raise HTTPException(404, "File not found.")

    markdown = md_path.read_text(encoding="utf-8")

    if enriched:
        custom_laws = None
        default_law = None

        # Register the municipality's BZO as a linkable custom law
        anns = get_annotations(muni.bfs_nr)
        bzo_file = _find_md_for_label(anns, LABEL_NEU, md_dir)
        if bzo_file:
            custom_laws = [build_bzo_custom_law(bzo_file.name)]
            # For companion documents, use BZO as default so bare "Art. X"
            # references (without trailing law abbreviation) resolve to it
            if md_path.name != bzo_file.name:
                default_law = "BZO"

        result = enrich_markdown_safe(
            markdown, default_law=default_law, custom_laws=custom_laws,
        )
        if result:
            return {"filename": md_path.name, "markdown": result["markdown"], "enriched": True}

    return {"filename": md_path.name, "markdown": markdown, "enriched": False}


# --- Cross-references ---

LABEL_ALT = "Bau- und Zonenordnung alt"
LABEL_NEU = "Bau- und Zonenordnung neu"

_ARTICLE_HEADING_RE = re.compile(r"^#{1,6}\s+Art\.?\s*(\d+[a-zA-Z]?)\b", re.MULTILINE)


_MIN_PARAGRAPH_LEN = 80


def _extract_paragraph(text: str, start_index: int, end_index: int) -> str:
    """Extract the paragraph containing a citation.

    Finds the nearest blank-line boundaries, then expands outward when the
    result is very short (common with OCR-broken text or diagram labels).
    For markdown table rows, grabs the full row.
    """
    para_start = text.rfind("\n\n", 0, start_index)
    para_start = para_start + 2 if para_start != -1 else 0
    para_end = text.find("\n\n", end_index)
    if para_end == -1:
        para_end = len(text)

    # Expand short paragraphs by merging adjacent blocks (OCR fragments)
    for _ in range(3):
        if para_end - para_start >= _MIN_PARAGRAPH_LEN:
            break
        expanded = False
        # Try expanding forward
        next_end = text.find("\n\n", para_end + 2)
        if next_end != -1 and next_end - para_start < 500:
            para_end = next_end
            expanded = True
        # Try expanding backward
        prev_start = text.rfind("\n\n", 0, para_start - 2) if para_start > 2 else -1
        if prev_start != -1 and para_end - (prev_start + 2) < 500:
            para_start = prev_start + 2
            expanded = True
        if not expanded:
            break

    paragraph = text[para_start:para_end].strip()

    # For table rows: extract just the row containing the citation
    if paragraph.startswith("|") or "\n|" in paragraph:
        lines = paragraph.split("\n")
        offset = para_start
        for line in lines:
            line_end = offset + len(line)
            if offset <= start_index < line_end or offset < end_index <= line_end:
                # Include separator rows around the match for context
                return line.strip()
            offset = line_end + 1  # +1 for \n

    return paragraph


def _build_md_label_map(annotations: list[dict]) -> dict[str, list[str]]:
    """Map markdown filenames to their annotation labels."""
    label_map: dict[str, list[str]] = {}
    for ann in annotations:
        if not ann.get("labels"):
            continue
        md_name = Path(_pdf_filename(ann["pdf_url"])).stem + ".md"
        label_map[md_name] = ann["labels"]
    return label_map


@app.get("/api/crossrefs/{municipality_name}")
def get_cross_references(municipality_name: str):
    """Pre-compute all BZO cross-references for a municipality."""
    muni = _resolve_municipality(municipality_name)
    slug = _slug(muni.name)
    md_dir = DATA_DIR / slug / "md"
    anns = get_annotations(muni.bfs_nr)

    bzo_path = _find_md_for_label(anns, LABEL_NEU, md_dir)
    if not bzo_path:
        raise HTTPException(404, "No file labeled 'Bau- und Zonenordnung neu' found.")

    bzo_markdown = bzo_path.read_text(encoding="utf-8")
    custom_laws = [build_bzo_custom_law(bzo_path.name)]

    # Enrich the BZO itself (for anchors + self-reference links)
    bzo_result = enrich_markdown_safe(bzo_markdown, custom_laws=custom_laws)
    bzo_enriched = bzo_result["markdown"] if bzo_result else bzo_markdown

    # Extract article list from BZO headings
    articles = _ARTICLE_HEADING_RE.findall(bzo_markdown)

    # Build filename → labels map from annotations
    label_map = _build_md_label_map(anns)

    # Collect cross-references from all companion documents
    cross_references: dict[str, list[dict]] = {}
    for md_file in sorted(md_dir.glob("*.md")):
        if md_file.name == bzo_path.name:
            continue

        companion_md = md_file.read_text(encoding="utf-8")
        result = enrich_markdown_safe(
            companion_md, default_law="BZO", custom_laws=custom_laws,
        )
        if not result:
            continue

        labels = label_map.get(md_file.name, [])

        for cite in result["citations"]:
            if cite.get("law_abbreviation") != "BZO" or not cite.get("is_resolved"):
                continue

            provision = cite["provision"]
            paragraph = _extract_paragraph(
                companion_md, cite["start_index"], cite["end_index"],
            )

            cross_references.setdefault(provision, []).append({
                "source_file": md_file.name,
                "source_labels": labels,
                "citation_text": cite["text"],
                "paragraph": paragraph,
            })

    return {
        "municipality": muni.name,
        "bzo_filename": bzo_path.name,
        "bzo_markdown": bzo_enriched,
        "articles": articles,
        "cross_references": cross_references,
    }


# --- Compare ---


@app.get("/api/compare/{municipality_name}/status")
def compare_status(municipality_name: str):
    """Check if a comparison is possible and if a diff already exists."""
    muni = _resolve_municipality(municipality_name)
    slug = _slug(muni.name)
    md_dir = DATA_DIR / slug / "md"
    anns = get_annotations(muni.bfs_nr)

    alt_file = _find_md_for_label(anns, LABEL_ALT, md_dir)
    neu_file = _find_md_for_label(anns, LABEL_NEU, md_dir)

    diff_path = DATA_DIR / slug / "diff.unified"
    return {
        "has_alt": alt_file is not None,
        "has_neu": neu_file is not None,
        "can_compare": alt_file is not None and neu_file is not None,
        "has_diff": diff_path.exists(),
        "alt_filename": alt_file.name if alt_file else None,
        "neu_filename": neu_file.name if neu_file else None,
    }


@app.post("/api/compare/{municipality_name}")
async def run_compare(municipality_name: str):
    """Compare the alt and neu BZO markdown files via DocConverter."""
    muni = _resolve_municipality(municipality_name)
    slug = _slug(muni.name)
    md_dir = DATA_DIR / slug / "md"
    anns = get_annotations(muni.bfs_nr)

    alt_file = _find_md_for_label(anns, LABEL_ALT, md_dir)
    neu_file = _find_md_for_label(anns, LABEL_NEU, md_dir)

    if not alt_file or not neu_file:
        missing = []
        if not alt_file:
            missing.append(LABEL_ALT)
        if not neu_file:
            missing.append(LABEL_NEU)
        raise HTTPException(400, f"Missing labeled markdown files: {', '.join(missing)}")

    left_bytes = alt_file.read_bytes()
    right_bytes = neu_file.read_bytes()

    result = await compare_documents(left_bytes, alt_file.name, right_bytes, neu_file.name)

    # Save the unified diff
    diff_path = DATA_DIR / slug / "diff.unified"
    diff_path.write_text(result.get("unified_diff", ""), encoding="utf-8")

    return {
        "left_filename": result.get("left_filename"),
        "right_filename": result.get("right_filename"),
        "diff_path": str(diff_path.relative_to(DATA_DIR)),
        "processing_time_ms": result.get("processing_time_ms"),
    }


def _find_md_for_label(annotations: list[dict], label: str, md_dir: Path) -> Path | None:
    """Find the markdown file for a PDF annotation with a specific label."""
    for ann in annotations:
        if label in ann.get("labels", []) and ann.get("selected"):
            md_name = Path(_pdf_filename(ann["pdf_url"])).stem + ".md"
            md_path = md_dir / md_name
            if md_path.exists():
                return md_path
    return None


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
            # Download — read from disk if it's a local upload
            local_path = _resolve_local_upload(file_state.url)
            if local_path:
                pdf_bytes = local_path.read_bytes()
            else:
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
            err_msg = str(e) or f"{type(e).__name__}: (no message)"
            file_state.error = err_msg
            import traceback
            traceback.print_exc()
            await queue.put({"type": "file_error", "data": {"file_index": i, "error": err_msg}})

    # Mark job complete
    job.status = "failed" if all(f.status == "failed" for f in job.files) else "done"
    await queue.put(None)  # sentinel


# --- Helpers ---


def _resolve_local_upload(url: str) -> Path | None:
    """If the URL points to our own uploads endpoint, return the local file path."""
    # Match /api/uploads/<slug>/<filename> in any base URL
    import re as _re
    m = _re.search(r"/api/uploads/([^/]+)/(.+)$", url)
    if not m:
        return None
    slug, filename = m.group(1), unquote(m.group(2))
    path = DATA_DIR / slug / "uploads" / filename
    return path if path.exists() else None


def _seed_classifications(bfs_nr: int, pdfs: list[dict]) -> dict[str, list[str]]:
    """Run the rules-first classifier and upsert annotations with suggested labels.

    Skips rows the user has already labelled. Returns the suggestion map so
    callers can surface labels in the same response without a second DB read.
    """
    if not pdfs:
        return {}
    labels = get_labels()
    fallback = fallback_label(labels)
    suggestions = classify_batch(
        [{"url": p["url"], "title": p.get("title", "")} for p in pdfs],
        db_labels=labels,
    )
    for p in pdfs:
        suggested = suggestions.get(p["url"], [])
        # Auto-select rows with a real category match — anything that isn't
        # the "Andere" fallback. The user can deselect mistakes; an empty
        # suggestion stays unselected.
        is_real_match = bool(suggested) and (fallback is None or suggested[0] != fallback)
        upsert_annotation(
            bfs_nr=bfs_nr,
            pdf_url=p["url"],
            pdf_title=p.get("title", ""),
            labels=suggested,
            selected=is_real_match,
            skip_if_labeled=True,
        )
    return suggestions


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

        matched, ambiguous = filter_pdfs_by_metadata(all_pdfs, profile)
        for p in ambiguous:
            p["match"] = "ambiguous"
        _seed_classifications(muni.bfs_nr, [*matched, *ambiguous])
        pdf_results = [
            PdfResult(url=p["url"], title=p.get("title", ""), match=p.get("match", "metadata"))
            for p in [*matched, *ambiguous]
        ]

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
