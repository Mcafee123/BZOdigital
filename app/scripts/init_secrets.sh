#!/usr/bin/env bash
#
# Push all GitHub Actions secrets required by this repo's workflows.
#
# Usage:
#   1. cp secrets.env.example secrets.env
#   2. Fill in the real values in secrets.env (gitignored).
#   3. ./init_secrets.sh                    # uses the repo of the current dir
#      ./init_secrets.sh -R owner/repo      # explicit target
#      SECRETS_FILE=other.env ./init_secrets.sh
#
# Requires: gh CLI, authenticated (`gh auth login`).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRETS_FILE="${SECRETS_FILE:-$SCRIPT_DIR/secrets.env}"

REPO_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -R|--repo) REPO_ARGS=(--repo "$2"); shift 2 ;;
    -h|--help)
      sed -n '2,12p' "$0"
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

# Source values without exporting them globally — use a subshell-style read.
# `set -a` makes assignments in the file available as env vars here.
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

target="${REPO_ARGS[*]:-current repo}"
echo "Setting secrets on ${target/--repo /}"

for name in "${REQUIRED[@]}"; do
  # Pipe the value via stdin so it never appears in argv / process listings.
  printf '%s' "${!name}" | gh secret set "$name" "${REPO_ARGS[@]}" --body -
  echo "  ✓ $name"
done

for name in "${OPTIONAL[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "  - $name (empty, skipped)"
    continue
  fi
  printf '%s' "${!name}" | gh secret set "$name" "${REPO_ARGS[@]}" --body -
  echo "  ✓ $name"
done

echo "Done."
