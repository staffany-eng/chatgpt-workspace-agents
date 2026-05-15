#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-productopsbot}"

hermes -p "$PROFILE" gateway status >/dev/null

config_path="$(hermes -p "$PROFILE" config path)"

grep -Eq 'redact_secrets:\s*true' "$config_path"
grep -Eq 'provider:\s*"?(anthropic)"?' "$config_path"
grep -Eq 'default:\s*"?(claude-sonnet-4-6)"?' "$config_path"
grep -Eq 'require_mention:\s*true' "$config_path"
