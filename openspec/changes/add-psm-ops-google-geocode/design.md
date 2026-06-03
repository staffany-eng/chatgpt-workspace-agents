# Design: PSM Ops Google Geocode Capability

## Runtime Primitive

Use an MCP server, not prompt-only instructions, because geocoding is an external API call with a secret-backed credential boundary.

## Tool Surface

- `check_google_geocode_access`: local credential presence check only; it does not call Google or print the key.
- `geocode_slack_addresses`: geocodes explicit rows extracted from the current Slack message.

The tool limits each Slack request to 25 addresses and returns non-OK statuses instead of hiding them.

## Credential Resolution

The MCP loads the profile `.env` through `profile_env.load_profile_env()`, then resolves credentials in this order:

1. `GOOGLE_GEOCODING_API_KEY`
2. `PSM_OPS_GOOGLE_GEOCODE_CREDENTIALS_FILE`
3. `GEOCODE_CREDENTIALS_FILE`
4. `~/.staffany/google-geocode/credentials.json`

The checked-in packet documents the path and schema but never stores the key.

## Slack Contract

The bot must extract only explicit address text from the tagged Slack message, call `geocode_slack_addresses`, and return a compact TSV-style block plus source/scope/confidence/caveat lines.
