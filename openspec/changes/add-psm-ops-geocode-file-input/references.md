# References: Add PSM Ops Geocode File Input

## Slack And PR Evidence

- Slack thread: `https://staffany.slack.com/archives/C0B665H9GDT/p1780542254312329`
  - Showed a tagged `PS Wee Manager` geocode request with an attached `psm-ops-geocode-smoke-sample.tsv`.
  - Bot response showed the current `psm_google_geocode` flow could not read the attached TSV and asked for pasted address rows instead.
- GitHub PR review: `https://github.com/staffany-eng/chatgpt-workspace-agents/pull/84`
  - CodeRabbit review called out attachment download hardening, source-column preservation, blank address row validation, and OpenSpec traceability.

## Repo Runtime Evidence

- `apps/psm-ops-bot/runtime/google-geocode.md`
  - Existing contract for `psm_google_geocode`, `geocode_slack_addresses`, Google credential boundaries, Slack TSV upload output, and no raw coordinate Slack replies.
- `apps/psm-ops-bot/runtime/mcp/psm_google_geocode_server.py`
  - Existing Google Geocoding request, TSV serialization, Slack upload, credential loading, and max-address behavior reused by `geocode_slack_address_file`.
- `apps/psm-ops-bot/runtime/mcp/psm_jira_server.py`
  - Existing Slack attachment download pattern for AA image ingestion using `url_private` and `SLACK_BOT_TOKEN`.
- `apps/psm-ops-bot/runtime/slack.md`
  - Existing Slack scope contract and bot-owned Slack identity rules.

## External API Docs

- Slack `files.getUploadURLExternal`: `https://api.slack.com/methods/files.getUploadURLExternal`
  - Source for the existing Slack external upload flow used to publish geocoded TSV output.
- Slack `files.completeUploadExternal`: `https://docs.slack.dev/reference/methods/files.completeUploadExternal/`
  - Source for finalizing and sharing uploaded TSV output in Slack.
- Slack file upload guide: `https://api.slack.com/messaging/files/uploading`
  - Source for the two-step Slack file upload behavior and Slack-hosted file workflow context.
- Google Geocoding request and response docs: `https://developers.google.com/maps/documentation/geocoding/requests-geocoding`
  - Source for address-to-coordinate geocoding behavior used by `psm_google_geocode`.

## Live/Runtime Observations

- The PSM Ops bot profile already has `files:read` available per user confirmation, so the missing piece was MCP support for reading and parsing CSV/TSV attachments, not Slack app permission.
- The source-packet verifier could validate durable packet wiring locally, but the local environment does not currently expose the `openspec` CLI, so strict OpenSpec validation remains gated.
