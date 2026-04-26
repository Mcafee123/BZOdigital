# BZOdigital

Digitalize revised Swiss municipal **Bau- und Zonenordnung (BZO)** documents — building and zoning regulations published as PDFs on `ortsplanung.ch` — so residents and lawyers can ask questions about what changed, what applies today, and how it affects them.

See [`CLAUDE.md`](./CLAUDE.md) for project goals, the staged pipeline (Collect → Extract → Connect → Frontend), and repository conventions. The `docs/*.jpg` whiteboard slides are the closest thing to a spec.

## Repository layout

- `src/bzodigital/` — **stage I (Collect):** Python package that discovers and downloads BZO PDFs for any Swiss municipality. Ships a `bzo` CLI and a FastAPI service.
- `app/` — **stage IV slice:** Vue 3 SPA + FastAPI BFF that renders a unified-diff file. See [`app/README.md`](./app/README.md).
- `data/<municipality>/src/*.pdf` — original source PDFs (currently only `oberrieden`).
- `tf/` — Terraform for deploying `app/` to Azure Container Apps (PROD only).
- `.github/workflows/` — `build.yml`, `deploy-prod.yml`, `upload-data.yml`.
- `docs/*.jpg` — whiteboard spec.

Pipeline stages II (extract) and III (connect) are not yet implemented.

## Stage I: the `bzodigital` collector/search service

Lives in `src/bzodigital/`. Independent from `app/` — different package, different `pyproject.toml` (this repo's root `pyproject.toml`).

### Modules

- `cli.py` — `bzo` entry point with subcommands `bfs-update`, `refresh`, `list`, `search`, `serve`.
- `api.py` — FastAPI REST API (`bzo-api` entry point); also serves the vanilla-JS UI in `static/`.
- `bfs.py` — fuzzy lookup against the Swiss BFS municipality register.
- `cantons.py`, `cantons_zh.py`, `gemeinden.py` — canton-level URL mappings and scrapers.
- `crawler.py`, `search.py` — web search via Serper API or Playwright fallback; PDF discovery and metadata/content filtering.
- `converter.py` — PDF → Markdown via an external doc-converter service.
- `enrichment.py`, `law_enrichment.py`, `laws_combined.json` — legal-text enrichment.
- `db.py` — SQLModel/SQLite store for search cache, annotations, labels.
- `profiles.py` — search profiles (BZO, etc.).
- `static/index.html` — minimal frontend served by the API.

### Run it

From the repo root:

```bash
uv sync                              # install dependencies into .venv
uv run playwright install chromium   # one-time; needed when SERPER_API_KEY is unset
uv run bzo bfs-update                # one-time; downloads the BFS register
uv run bzo serve                     # http://localhost:7100 (UI + API; app/ uses 7000)
```

CLI examples:

```bash
uv run bzo list --canton ZH
uv run bzo search Oberrieden --pdfs --check-content
uv run bzo refresh --canton zh
```

### Environment variables

`load_dotenv()` reads a `.env` at the repo root. All variables are optional.

| Variable | Used by | Effect |
| --- | --- | --- |
| `SERPER_API_KEY` | `search.py` | Use Serper for Google search; without it falls back to Playwright crawling (slower). |
| `BASIC_AUTH_USER` / `BASIC_AUTH_PASS` | `api.py` | Protect the API + static UI with HTTP Basic. If unset, auth is disabled. |
| `DOCCONVERTER_URL` | `converter.py` | External PDF→Markdown service. Required only for endpoints that convert PDFs. |
| `DOCCONVERTER_USER` / `DOCCONVERTER_PASS` | `converter.py` | Basic-auth credentials for the doc-converter. |

## Stage IV slice: the diff viewer (`app/`)

Vue 3 SPA + FastAPI BFF that renders a unified-diff file. Local dev and container build instructions live in [`app/README.md`](./app/README.md).

## License

MIT — see [`LICENSE`](./LICENSE).
