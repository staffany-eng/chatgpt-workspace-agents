#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-productopsbot}"
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

PROFILE_DIR="$HOME/.hermes/profiles/$PROFILE"

cmp -s "$BASE_DIR/profile/SOUL.md" "$PROFILE_DIR/SOUL.md"

grep -q 'provider: "anthropic"' "$BASE_DIR/profile/config.template.yaml"
grep -q 'default: "claude-sonnet-4-6"' "$BASE_DIR/profile/config.template.yaml"
