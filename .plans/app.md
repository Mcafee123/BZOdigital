# App: Vue + FastAPI boilerplate with diff viewer

Single-page Vue 3 app fronted by a small Python FastAPI backend, packaged as one container, deployed to Azure Container Apps via Terraform + GitHub Actions.

## Goals

- Reusable Vue 3 frontend boilerplate (TypeScript strict, Pinia, Vue Router, BeerCSS).
- Tiny FastAPI backend that serves the SPA and exposes a `/api/diff` endpoint reading a unified-diff file from disk.
- One Docker image (multi-stage: Node build → Python runtime).
- Terraform for the Azure Container App (PROD environment only).
- GitHub Actions workflow builds the image, pushes to a container registry, and runs `terraform apply`.
- No authentication for now (anonymous BFF). OIDC can be added later.

## Architecture

```
┌────────────────────┐    GET /            ┌──────────────────────┐
│  Browser           │ ──────────────────► │  FastAPI (port 8080) │
│                    │ ◄────── SPA ─────── │   - serves web/dist  │
│                    │                     │   - GET /api/diff    │
│                    │ GET /api/diff       │   - GET /api/health  │
└────────────────────┘ ──────────────────► └──────────────────────┘
                                                       │
                                                       ▼
                                            reads $DIFF_PATH
                                                       │
                                                       ▼
                                          ┌────────────────────────┐
                                          │  Azure File share      │
                                          │  mounted at /mnt/repo  │
                                          │   /mnt/repo/data/...   │
                                          │   /mnt/repo/app/data/. │
                                          └────────────────────────┘
                                                       ▲
                                                       │ az storage file upload-batch
                                          ┌────────────────────────┐
                                          │  upload-data.yml       │
                                          │  on push to main when  │
                                          │  data/** or app/data/  │
                                          │  changes               │
                                          └────────────────────────┘
```

## Repository layout

```
app/                          # all application code
├── web/                      # Vue 3 SPA
│   ├── src/
│   │   ├── components/DiffView.vue
│   │   ├── views/DiffPage.vue
│   │   ├── stores/diff.ts
│   │   ├── composables/useApi.ts
│   │   ├── router/index.ts
│   │   ├── App.vue
│   │   ├── main.ts
│   │   └── style.css
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
├── src/bzo_app/              # FastAPI server
│   ├── __init__.py
│   └── server.py
├── data/sample.diff          # bundled sample diff
├── pyproject.toml            # uv-managed Python deps
├── Dockerfile                # multi-stage build
└── README.md
.github/workflows/
├── build.yml                 # sanity build on side branches
├── deploy-prod.yml           # PROD deploy on main / workflow_dispatch
└── upload-data.yml           # syncs data/ and app/data/ to the file share
tf/
├── prod/app/                 # PROD environment
└── modules/main/             # reusable Container App module (inlined; no external deps)
.plans/app.md                 # this file
```

## Diff rendering

- The frontend uses `@git-diff-view/vue` to render the unified diff.
- The BFF reads the file at `$DIFF_PATH` (default `/app/data/sample.diff`), extracts left/right filenames from the `--- ` and `+++ ` headers, and returns `{ unified_diff, left_filename, right_filename }`.
- Split-mode rendering is best-effort in v1 (only the diff text is available; full file contents are passed as empty strings). Unified mode renders fully.

## Deployment

- One environment: PROD.
- Trigger: push to `main`, or manual `workflow_dispatch`.
- Steps: checkout → read version from `pyproject.toml` → build Docker image → push to the configured container registry → `terraform apply` against `tf/prod/app`.

## Configuration

All environment-specific values are variables. Nothing is hardcoded in committed files:

| Concern | Where it lives |
|---|---|
| Container registry login server | `terraform.tfvars` (gitignored) + GH Actions secret `ACR_LOGIN_SERVER` |
| Registry credentials | GH Actions secrets `ACR_USERNAME` / `ACR_PASSWORD` |
| Azure subscription / tenant / SP | GH Actions secrets `ARM_*` and `AZURE_CREDENTIALS` |
| Resource group, Container App Env ID | `terraform.tfvars` (gitignored), `terraform.tfvars.example` committed with placeholders |
| Terraform state backend | `_backend.hcl` (gitignored), `_backend.hcl.example` committed |
| Storage account, file share | `terraform.tfvars` (gitignored) + GH Actions secrets `STORAGE_ACCOUNT_NAME`, `STORAGE_ACCOUNT_RESOURCE_GROUP`, `STORAGE_ACCOUNT_KEY`, `FILE_SHARE_NAME` |

See `app/README.md` for the full prerequisite checklist before the first deploy.

## Verification

- `cd app/web && npm i && npm run dev` — Vite serves on `http://localhost:5173`, proxies `/api/*` to `http://localhost:7000`.
- `cd app && uv sync && uv run uvicorn bzo_app.server:app --reload --port 7000` — FastAPI on `:7000`.
- `docker build -t bzo-app:local app/ && docker run --rm -p 8080:8080 bzo-app:local` — full SPA + API on `:8080`.
- `cd tf/prod/app && terraform init -backend=false && terraform validate` — TF parses cleanly.
