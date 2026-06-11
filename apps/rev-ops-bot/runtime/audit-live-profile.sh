#!/usr/bin/env bash
set -euo pipefail

profile_dir="${HERMES_PROFILE_DIR:-${HOME}/.hermes/profiles/revopsbot}"

if [[ ! -d "${profile_dir}" ]]; then
  echo "RevOps Bot profile directory not found: ${profile_dir}" >&2
  exit 1
fi

missing=()
for name in SLACK_APP_TOKEN SLACK_BOT_TOKEN REVOPS_WINDMILL_BASE_URL REVOPS_WINDMILL_WORKSPACE_ID REVOPS_WINDMILL_TOKEN; do
  if ! grep -q "^${name}=" "${profile_dir}/.env" 2>/dev/null; then
    missing+=("${name}")
  fi
done

if [[ ${#missing[@]} -gt 0 ]]; then
  printf 'Missing profile env entries: %s\n' "${missing[*]}" >&2
  exit 1
fi

echo "RevOps Bot live profile audit passed."
