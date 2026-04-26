#!/usr/bin/env bash
#
# Push GitHub Actions secrets to a deployment ENVIRONMENT (default: production)
# with the current gh user added as a required reviewer. Workflow jobs that
# reference `environment: production` will pause until you approve them.
#
# Usage:
#   1. cp secrets.env.example secrets.env
#   2. Fill in the values in secrets.env (gitignored).
#   3. ./init_secrets.sh                              # current repo, env=production
#      ./init_secrets.sh -R owner/repo                # explicit repo
#      ./init_secrets.sh -e staging                   # different environment
#      SECRETS_FILE=other.env ./init_secrets.sh
#
# Requires: gh CLI, authenticated (`gh auth login`).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRETS_FILE="${SECRETS_FILE:-$SCRIPT_DIR/secrets.env}"
GH_ENVIRONMENT="${GH_ENVIRONMENT:-production}"

REPO_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -R|--repo) REPO_ARGS=(--repo "$2"); shift 2 ;;
    -e|--env)  GH_ENVIRONMENT="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,16p' "$0"
      exit 0
      ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

REQUIRED=(
  ACR_LOGIN_SERVER
  ACR_USERNAME
  ACR_PASSWORD
  ARM_CLIENT_ID
  ARM_CLIENT_SECRET
  ARM_TENANT_ID
  ARM_SUBSCRIPTION_ID
  TF_BACKEND_RESOURCE_GROUP
  TF_BACKEND_STORAGE_ACCOUNT
  TF_BACKEND_CONTAINER
  TF_BACKEND_KEY
  TF_RESOURCE_GROUP
  TF_CONTAINER_APP_ENV_ID
  TF_ACR_ID
  KEYVAULT_ID
  STORAGE_ACCOUNT_NAME
  STORAGE_ACCOUNT_RESOURCE_GROUP
  STORAGE_ACCOUNT_KEY
  FILE_SHARE_NAME
)

# Optional secrets — pushed when non-empty, skipped silently when empty.
OPTIONAL=(
  CLOUDFLARE_API_TOKEN
  CLOUDFLARE_ZONE_ID
  CUSTOM_DOMAIN
)

command -v gh >/dev/null 2>&1 || {
  echo "gh CLI not found. Install from https://cli.github.com/" >&2
  exit 1
}

gh auth status >/dev/null 2>&1 || {
  echo "gh is not authenticated. Run: gh auth login" >&2
  exit 1
}

if [[ ! -f "$SECRETS_FILE" ]]; then
  echo "Missing $SECRETS_FILE" >&2
  echo "Copy secrets.env.example to secrets.env and fill in the values." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
. "$SECRETS_FILE"
set +a

missing=()
for name in "${REQUIRED[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    missing+=("$name")
  fi
done

if (( ${#missing[@]} > 0 )); then
  echo "The following secrets are empty in $SECRETS_FILE:" >&2
  printf '  %s\n' "${missing[@]}" >&2
  exit 1
fi

# Resolve repo for environment API calls (--repo flag or current dir's repo).
if [[ ${#REPO_ARGS[@]} -eq 2 ]]; then
  REPO_NWO="${REPO_ARGS[1]}"
else
  REPO_NWO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")
fi
if [[ -z "$REPO_NWO" ]]; then
  echo "Could not resolve repo. Pass -R owner/repo." >&2
  exit 1
fi

USER_ID=$(gh api user --jq .id 2>/dev/null || echo "")
if [[ -z "$USER_ID" ]]; then
  echo "Could not resolve current gh user id." >&2
  exit 1
fi

echo "Ensuring environment '$GH_ENVIRONMENT' on $REPO_NWO with user $USER_ID as required reviewer"
gh api --method PUT "repos/${REPO_NWO}/environments/${GH_ENVIRONMENT}" \
  -F "wait_timer=0" \
  -F "reviewers[][type]=User" \
  -F "reviewers[][id]=${USER_ID}" \
  -F "deployment_branch_policy=null" >/dev/null

echo "Setting secrets on ${REPO_NWO} (environment: ${GH_ENVIRONMENT})"

for name in "${REQUIRED[@]}"; do
  printf '%s' "${!name}" | gh secret set "$name" \
    --repo "$REPO_NWO" \
    --env "$GH_ENVIRONMENT" \
    --body -
  echo "  ✓ $name"
done

for name in "${OPTIONAL[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "  - $name (empty, skipped)"
    continue
  fi
  printf '%s' "${!name}" | gh secret set "$name" \
    --repo "$REPO_NWO" \
    --env "$GH_ENVIRONMENT" \
    --body -
  echo "  ✓ $name"
done

echo "Done. Workflow runs that reference 'environment: $GH_ENVIRONMENT' will pause until you approve them."
