# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

The repo is mid-pipeline: source collection (stage I) is in progress, and a first frontend slice for stage IV (the diff viewer) is now scaffolded under `app/`.

Top-level contents:

- `LICENSE` — MIT
- `docs/*.jpg` — hand-drawn whiteboard slides describing the project's intent, user stories, tasks, and challenges. They are the closest thing to a spec; read them before proposing structure.
- `data/<municipality>/src/*.pdf` — original source documents per Swiss municipality (currently only `oberrieden`). These are the inputs the pipeline will consume.
- `app/` — Vue 3 SPA + FastAPI BFF boilerplate that renders a unified-diff file. First concrete piece of stage IV. See `app/README.md` for local dev (`uv sync` + `npm run dev`), container build, and the deploy prereqs.
- `tf/` — Terraform for deploying `app/` to Azure Container Apps. PROD-only environment. Generic, public-safe code; private bootstrap (`tf/_project_init/`) is gitignored.
- `.github/workflows/` — `build.yml` (sanity Docker build), `deploy-prod.yml` (build + push + `terraform apply` on push to `main`), `upload-data.yml` (sync `data/` and `app/data/` to the mounted Azure File share when those paths change).

When asked to "build" or "run":
- For the diff-viewer app: see `app/README.md`. Local: `cd app && uv sync && uv run uvicorn bzo_app.server:app --reload --port 8000` plus `cd app/web && npm i && npm run dev`. Container: `docker build -t bzo-app:local app/`.
- For pipeline stages I–III (PDF ingestion, extraction, topic linking): no code yet — ask which stage to bootstrap before scaffolding.

## What the project is about

"BZOdigital" digitalizes revised Swiss municipal **Bau- und Zonenordnung (BZO)** — building and zoning regulations published as PDFs on ortsplanung.ch. Each municipality publishes several related document types (Erläuterungsbericht, Einwendungsbericht, Synopse, Beschlussbuch, Protokoll, publication text, info-event slides, etc.), often as old/new pairs.

Goals captured in the whiteboard docs:

1. Let an affected resident ask **"how does the change affect me, and should I file an objection?"** (before the revision is enacted).
2. Let someone reason about the **current situation under the old law** (after enactment).
3. Produce **summaries with drill-down into topics of interest**.

## Intended pipeline (from `docs/4. tasks.jpg`)

The work is staged. Future code should slot into one of these stages:

- **I. Collect** source documents per municipality (today: manual drop into `data/<municipality>/src/`; later: scrape ortsplanung.ch and similar).
- **II. Extract** text and images from PDFs → Markdown.
- **III. Connect** extracted content into consolidated data; **IIIa.** organize topic-by-topic with back-references to the source PDFs (preserve "ground truth" linkage — this is called out explicitly in `docs/2. ba.jpg`).
- **IV. Frontend** — feed the consolidated data to an LLM with task-specific prompts for the user stories above.

## Repository conventions

- **Per-municipality data layout:** `data/<municipality>/src/` holds the original PDFs. New stages should add sibling directories (e.g. `data/<municipality>/extracted/`, `data/<municipality>/topics/`) rather than mixing artifacts with sources.
- **Source filenames are kebab-cased and prefixed with a short type tag** (`erl - …`, `sy - …`, `öa - …`, `info - …`). Preserve this when adding new documents — downstream tooling will likely key off the prefix.
- **Languages in source material are German** (Swiss High German). Generated artifacts and user-facing output should default to German unless the user says otherwise.

## Challenge to keep in mind

Two approaches contributors take:
- **Lawyers** throw everything at an LLM with detailed instructions, expecting precise, citation-linked answers.
- **Tech-savvy residents** want an LLM-style overview they can drill down into.

The pipeline must support both approaches while preserving the link back to originating text.
