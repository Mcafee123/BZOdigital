# bzo-app

Vue 3 SPA fronted by a FastAPI backend, packaged as a single container, deployed to Azure Container Apps. The first feature renders a unified-diff file.

## Local development

You need: Node 22+, Python 3.12+ with [uv](https://docs.astral.sh/uv/).

Two terminals:

```bash
# Terminal 1 — backend (FastAPI on :8001)
cd app
uv sync
DIFF_PATH=./data/sample.diff WEB_DIST=./web/dist \
  uv run uvicorn bzo_app.server:app --reload --port 8001
```

```bash
# Terminal 2 — frontend (Vite on :5173)
cd app/web
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api/*` to the backend on `:8001`.

## Smoke test

```bash
curl http://localhost:8001/api/health
curl http://localhost:8001/api/diff
```

## Container build

```bash
docker build -t bzo-app:local app/
docker run --rm -p 8080:8080 bzo-app:local
```

The container serves SPA + API on `:8080`. Open http://localhost:8080.

## Where the data lives

In production, an Azure File share is mounted into the Container App at `/mnt/repo`. The tree on the share mirrors the repo: `data/...` from the repo root and `app/data/...` from this folder both end up under `/mnt/repo/`. `DIFF_PATH` is set to `/mnt/repo/app/data/sample.diff` by Terraform.

The image bundles `app/data/` as a fallback (so `docker run` works locally without a mount), but production reads from the mount.

A separate workflow (`.github/workflows/upload-data.yml`) syncs `data/` and `app/data/` to the share on push to `main` whenever those paths change.

### Swapping the diff file

- **Locally (uvicorn):** `DIFF_PATH=/path/to/your.diff uv run uvicorn ...`
- **Locally (docker):** `docker run --rm -p 8080:8080 -v $(pwd)/your.diff:/app/data/sample.diff:ro bzo-app:local`
- **Production:** drop the new diff into `app/data/`, push to `main`, the upload workflow syncs it; the running container picks it up live (no redeploy needed).

The file must be plain unified-diff text. Filenames are extracted from the `--- ` and `+++ ` headers.

## Deployment to Azure Container Apps

`deploy-prod.yml` builds + pushes the image to ACR and runs `terraform apply` on push to `main` (or `workflow_dispatch`). Both jobs reference the `production` GitHub environment, so they pause for your approval.

### How config flows

The TF code creates the project's RG, storage account, file share, identity, and Container App. Platform identifiers (ACR, Container App Environment, Key Vault) are read at apply time from the platform's terraform state via `module "read_core"`. Cloudflare credentials are read from Key Vault via `data "azurerm_key_vault_secret"`.

The committed file `tf/prod/app/_platform.auto.tfvars` (generated once locally by `tf/_project_init/`) contains the platform seed: tenant_id, subscription_id, state location, KV name. CI doesn't pass any of these — terraform reads them from the file and uses `read_core` for the rest.

### One-time prerequisites

1. **Azure side** — these must already exist on the platform:
   - The platform Key Vault `affolternet-vault`
   - The platform ACR (`anplatformacr`)
   - The platform Container App Environment
   - The platform tfstate storage container
   - A service principal with: `Contributor` on the subscription (or RG-creator scope), `AcrPush` on the registry, `Key Vault Secrets User` on `affolternet-vault`, and access to the platform tfstate blob
   - The Cloudflare zone `nupla.info` and KV secrets `nupla-cloudflare-token` + `nupla-cloudflare-zone-id`

2. **Generate per-env config** — runs the bootstrap module locally (gitignored), which generates the committed `_backend.hcl`, `_basics.tf`, `_init.sh`, `_platform.auto.tfvars`, `_platform_variables.tf` files in `tf/prod/app/`:

   ```bash
   cd tf/_project_init
   terraform init
   terraform apply
   ```

   This also creates the GitHub `production` environment with you as required reviewer and pushes the 5 secrets below.

3. **GitHub Actions secrets** — only 5, all on the `production` environment:

   | Secret | Purpose |
   |---|---|
   | `ARM_CLIENT_ID` | Service principal app ID |
   | `ARM_CLIENT_SECRET` | Service principal secret |
   | `ARM_TENANT_ID` | Azure AD tenant ID |
   | `ARM_SUBSCRIPTION_ID` | Subscription ID |
   | `SSH_PRIVATE_KEY` | Deploy key with read access to `affolterNET-Cloud-HelperModules` and `affolterNET-Cloud-ContainerApp` (the bootstrap reads it from `$SSH_PRIVATE_KEY_PATH`, default `~/.ssh/id_ed25519`, and pushes it for you) |

   Everything else — ACR creds, storage names, KV ID, ACE ID, Cloudflare token, custom domain — is derived at apply time. Workflows that need az lookups use `azure/login` with the ARM_* secrets.

   **File-based fallback:** if you don't have KV access, fill in `app/scripts/secrets.env` (gitignored) and run `app/scripts/init_secrets.sh`.

4. **First terraform apply locally** — bootstraps the Container App and outputs its FQDN:

   ```bash
   cd tf/prod/app
   bash _init.sh                        # az login check + terraform init
   terraform plan -var "image_name=anplatformacr.azurecr.io/bzo-app:0.1.0"
   terraform apply -var "image_name=..."
   ```

   You'll need an image already pushed to ACR. Build + push it locally first:
   ```bash
   az acr login --name anplatformacr
   docker build -t anplatformacr.azurecr.io/bzo-app:0.1.0 app/
   docker push anplatformacr.azurecr.io/bzo-app:0.1.0
   ```

### Push-to-deploy

After the first apply, push to `main` triggers:
1. `build-and-push` job — builds image tagged `${pyproject.version}-${short_sha}`, pushes to ACR via `az acr login`. Pauses for approval.
2. `deploy` job — `terraform apply` with the new image_name. Pauses for approval.
3. Commit gets tagged `v${tag}`.

For data-only changes (`data/**` or `app/data/**`), only `upload-data.yml` runs and pauses for one approval.

## Type check / lint

```bash
cd app/web && npm run type-check
```
