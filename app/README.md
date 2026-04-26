# bzo-app

Vue 3 SPA fronted by a small FastAPI backend, packaged as a single container, deployable to Azure Container Apps. The first feature renders a unified-diff file.

## Local development

You need:

- Node 22+
- Python 3.12+ with [uv](https://docs.astral.sh/uv/)

Two terminals:

```bash
# Terminal 1 — backend
cd app
uv sync
DIFF_PATH=./data/sample.diff WEB_DIST=./web/dist \
  uv run uvicorn bzo_app.server:app --reload --port 8000
```

```bash
# Terminal 2 — frontend
cd app/web
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api/*` to the backend on `:8000`.

## Smoke test

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/diff
```

## Container build

From the repo root:

```bash
docker build -t bzo-app:local app/
docker run --rm -p 8080:8080 bzo-app:local
```

The container serves both the SPA and the API on `:8080`. Open http://localhost:8080.

## Where the data lives

In production, an Azure File share is mounted into the Container App at `/mnt/repo`. The tree on the share mirrors the repo: `data/...` from the repo root and `app/data/...` from this folder both end up under `/mnt/repo/`. The `DIFF_PATH` env var is set to `/mnt/repo/app/data/sample.diff` by Terraform.

The image still bundles `app/data/` as a fallback (so `docker run` works locally without a mount), but it's shadowed by the mount in production.

A separate workflow (`.github/workflows/upload-data.yml`) syncs `data/` and `app/data/` to the share on push to `main` whenever those paths change. You can also trigger it manually via `workflow_dispatch`.

### Swapping the diff file

- **Locally (uvicorn):** `DIFF_PATH=/path/to/your.diff uv run uvicorn ...`
- **Locally (docker):** `docker run --rm -p 8080:8080 -v $(pwd)/your.diff:/app/data/sample.diff:ro -e DIFF_PATH=/app/data/sample.diff bzo-app:local`
- **Production:** drop the new diff into `app/data/` (or `data/...`), push to `main`, the upload workflow syncs it to the share, and the running container picks it up immediately (the mount is live, no redeploy needed).

The file must be plain unified-diff text. The backend extracts left/right filenames from the `--- ` and `+++ ` headers; everything else is returned as-is.

## Deployment to Azure Container Apps

Production deploys run via `.github/workflows/deploy-prod.yml` on push to `main` (or manual `workflow_dispatch`).

### One-time prerequisites

1. **Azure side** — these must already exist:
   - A resource group
   - An Azure Container Apps environment
   - An Azure Container Registry
   - A storage account with a blob container for Terraform state **and** an Azure File share for repo data (can be the same storage account)
   - A service principal with `Contributor` on the resource group and `AcrPush` on the registry. It also needs to be able to read storage account keys (`Storage Account Key Operator Service Role`, or simply `Reader and Data Access`).
2. **GitHub Actions secrets** — pushed to a deployment **environment** named `production` (not repo-level). The current gh user is added as a required reviewer, so any workflow run that targets this environment pauses until you approve it. This means write-access collaborators on the public repo cannot trigger the deploy or steal secrets via workflow modifications without your approval click.

   Two paths:

   **Path A — Key Vault driven (`tf/_project_init/`, gitignored)**: if you have access to the platform Key Vault, run the bootstrap module. It generates the per-env Terraform config (`_backend.hcl`, `_init.sh`, `_platform.auto.tfvars`, `_basics.tf`, `_platform_variables.tf` — all gitignored), creates the `production` environment with you as required reviewer, and pushes the secrets there.

   ```bash
   cd tf/_project_init
   terraform init
   terraform apply        # generates files in tf/prod/app/ and runs _github_init.sh
   ```

   The bootstrap reads platform secrets (`an-platform-acr-admin-pw`, `an-platform-state-prod-sp-client-id`, etc.) plus project-specific secrets (`bzo-app-prod-resource-group`, `bzo-app-prod-storage-account-key`, etc.) from KV. Pre-populate the project-specific KV entries before running.

   Then locally:
   ```bash
   cd tf/prod/app
   bash _init.sh           # az account set + terraform init -backend-config=_backend.hcl
   ```

   **Path B — File-based fallback (`app/scripts/init_secrets.sh`)**: for anyone without KV access, or for one-off overrides.

   ```bash
   cd app/scripts
   cp secrets.env.example secrets.env   # gitignored
   # …fill in the values in secrets.env…
   ./init_secrets.sh                    # creates env, pushes to environment "production"
   # ./init_secrets.sh -e staging       # different environment
   ```

   Requires `gh` authenticated (`gh auth login`). The script idempotently creates/updates the GitHub environment with you as required reviewer.

   **Approval UX:** every push to `main` (or merge of a PR) that triggers `deploy-prod.yml` will pause for **two approvals** (one for the build job, one for the deploy job — both reference the environment). `upload-data.yml` pauses for one approval. You'll get an email/notification each time. Approve via the workflow run's "Review deployments" button.

   The full secret list, in case you'd rather set them via the GitHub UI (*Settings → Environments → production → Add secret*):

   | Secret | Purpose |
   |---|---|
   | `ACR_LOGIN_SERVER` | e.g. `example.azurecr.io` |
   | `ACR_USERNAME` | Registry admin user (or service principal with `AcrPush`) |
   | `ACR_PASSWORD` | Registry password |
   | `ARM_CLIENT_ID` | Service principal app ID |
   | `ARM_CLIENT_SECRET` | Service principal secret |
   | `ARM_TENANT_ID` | Azure AD tenant ID |
   | `ARM_SUBSCRIPTION_ID` | Subscription ID |
   | `TF_BACKEND_RESOURCE_GROUP` | RG holding the tfstate storage account |
   | `TF_BACKEND_STORAGE_ACCOUNT` | Storage account name |
   | `TF_BACKEND_CONTAINER` | Blob container (e.g. `tfstate`) |
   | `TF_BACKEND_KEY` | State file name (e.g. `bzo-app-prod.tfstate`) |
   | `TF_RESOURCE_GROUP` | RG that will hold the Container App |
   | `TF_CONTAINER_APP_ENV_ID` | Resource ID of the Container Apps environment |
   | `TF_ACR_ID` | Resource ID of the registry |
   | `KEYVAULT_ID` | Resource ID of the Key Vault (the shared Container App module writes `custom_domain_verification_id` here) |
   | `STORAGE_ACCOUNT_NAME` | Name of the storage account hosting the file share |
   | `STORAGE_ACCOUNT_RESOURCE_GROUP` | RG of that storage account |
   | `STORAGE_ACCOUNT_KEY` | Storage account key (used by `upload-data.yml` for SMB upload) |
   | `FILE_SHARE_NAME` | Name of the Azure File share whose tree mirrors the repo |
   | `CLOUDFLARE_API_TOKEN` | *(optional)* Cloudflare token with `Zone:DNS:Edit` for the target zone |
   | `CLOUDFLARE_ZONE_ID` | *(optional)* Zone ID containing `CUSTOM_DOMAIN` |
   | `CUSTOM_DOMAIN` | *(optional)* Custom hostname (e.g. `bzo-app.example.com`); when set, the TF module creates the `asuid` TXT + CNAME records, then runs `az containerapp hostname add/bind` via the shared `custom-domain` helper. |
   | `SSH_PRIVATE_KEY` | Deploy-key private key with read access to `affolterNET/affolterNET-Cloud-HelperModules`. Required for `terraform init` to clone the shared `cloudflare` and `custom-domain` modules. Set manually with `gh secret set SSH_PRIVATE_KEY < ~/.ssh/id_ed25519`. |

3. **Local Terraform setup** — for the very first apply you may want to run locally:

   - **Path A** (KV bootstrap): `_backend.hcl`, `_init.sh`, and `_platform.auto.tfvars` are generated by `terraform apply` in `tf/_project_init/`. Then in `tf/prod/app/`, copy `terraform.tfvars.example` to `terraform.tfvars`, fill in the project-specific values, and run `bash _init.sh && terraform plan && terraform apply`.
   - **Path B** (manual): in `tf/prod/app/`, copy both `terraform.tfvars.example` → `terraform.tfvars` and `_backend.hcl.example` → `_backend.hcl`, fill in the values, then `terraform init -backend-config=_backend.hcl && terraform plan && terraform apply`.

   `terraform.tfvars`, `_backend.hcl`, and the `_init.sh`/`_basics.tf`/`_platform.*` files are all gitignored.

### Push-to-deploy

After secrets are set, merging to `main` triggers:
1. Build the Docker image, tag as `${pyproject.version}-${short_sha}`.
2. Push to the registry.
3. `terraform apply` against `tf/prod/app` with the new image reference.
4. Tag the commit with `v${tag}`.

## Type check / lint

```bash
cd app/web && npm run type-check
```
