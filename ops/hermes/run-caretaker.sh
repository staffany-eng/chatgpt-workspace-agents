#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

export PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/v24.12.0/bin:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export HERMES_ACCEPT_HOOKS=1

mkdir -p "$HOME/.hermes/logs"
cd "$REPO_ROOT"

exec node ops/hermes/caretaker.mjs --apply --post-report --json
