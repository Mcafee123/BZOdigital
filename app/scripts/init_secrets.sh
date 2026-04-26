#!/usr/bin/env bash
#
# Push the minimum GitHub Actions secrets to a deployment ENVIRONMENT
# (default: production) with the current gh user added as a required reviewer.
# Workflow jobs that reference `environment: production` will pause until
# you approve them.
#
# Usage:
#   1. cp secrets.env.example secrets.env
#   2. Fill in the values in secrets.env (gitignored).
#   3. ./init_secrets.sh                              # current repo, env=production
#      ./init_secrets.sh -R owner/repo                # explicit repo
#      ./init_secrets.sh -e staging                   # different environment
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
  ARM_CLIENT_ID
  ARM_CLIENT_SECRET
  ARM_TENANT_ID
  ARM_SUBSCRIPTION_ID
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
  [[ -z "${!name:-}" ]] && missing+=("$name")
done

if (( ${#missing[@]} > 0 )); then
  echo "The following values are empty in $SECRETS_FILE:" >&2
  printf '  %s\n' "${missing[@]}" >&2
  exit 1
fi

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

# SSH deploy key from a file path (multi-line content), default ~/.ssh/id_ed25519.
SSH_PRIVATE_KEY_PATH="${SSH_PRIVATE_KEY_PATH:-$HOME/.ssh/id_ed25519}"
SSH_PRIVATE_KEY_PATH="${SSH_PRIVATE_KEY_PATH/#\~/$HOME}"
if [[ -f "$SSH_PRIVATE_KEY_PATH" ]]; then
  gh secret set SSH_PRIVATE_KEY \
    --repo "$REPO_NWO" \
    --env "$GH_ENVIRONMENT" \
    --body - < "$SSH_PRIVATE_KEY_PATH"
  echo "  ✓ SSH_PRIVATE_KEY (from $SSH_PRIVATE_KEY_PATH)"
else
  echo "  - SSH_PRIVATE_KEY (no key at $SSH_PRIVATE_KEY_PATH, skipped)"
fi

echo "Done. Workflow runs that reference 'environment: $GH_ENVIRONMENT' will pause until you approve them."
