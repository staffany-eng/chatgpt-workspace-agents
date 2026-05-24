#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HERMES_PROFILE:-productopsbot}"
PROFILE_DIR="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/$PROFILE}"
GATEWAY_SERVICE_NAME="${HERMES_GATEWAY_SERVICE_NAME:-hermes-gateway-$PROFILE.service}"

if command -v hermes >/dev/null 2>&1; then
  hermes -p "$PROFILE" gateway status >/dev/null
else
  systemctl --user is-active --quiet "$GATEWAY_SERVICE_NAME"
fi

if command -v hermes >/dev/null 2>&1; then
  config_path="$(hermes -p "$PROFILE" config path)"
else
  config_path="$PROFILE_DIR/config.yaml"
fi

grep -Eq 'redact_secrets:\s*true' "$config_path"
grep -Eq 'provider:\s*"?(anthropic)"?' "$config_path"
grep -Eq 'default:\s*"?(claude-sonnet-4-6)"?' "$config_path"
grep -Eq 'require_mention:\s*true' "$config_path"
