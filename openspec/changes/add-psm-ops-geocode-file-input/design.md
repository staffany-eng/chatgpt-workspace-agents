# Design: PSM Ops Geocode File Input

## Runtime Primitive

Extend the existing `psm_google_geocode` MCP server. This keeps Slack file download, CSV/TSV parsing, Google Geocoding, and Slack result upload inside one secret-backed runtime boundary.

## Tool Surface

Add `geocode_slack_address_file`, which accepts a Slack thread permalink and optional file id/name hint. The tool fetches the current Slack thread messages, finds the relevant CSV/TSV attachment, downloads it with `SLACK_BOT_TOKEN`, parses rows, and then uses the same geocode/output code path as `geocode_slack_addresses`.

The tool rejects unsupported file types, missing files, missing `address` columns, empty address rows, and files over the existing 25-address limit.

## Slack Contract

For tagged requests such as `@PS Wee Manager geocode these addresses` with an attached `.csv` or `.tsv`, the bot should call `geocode_slack_address_file` instead of asking the user to paste rows.

Hermes Slack gateway prompts can omit attachment metadata even when the Slack thread has a file. Therefore, if the tagged request asks to geocode "these addresses", "these address", "the attached file", or equivalent file/list wording and no address rows are visible in message text, the bot should still call `geocode_slack_address_file` with the current Slack thread permalink before asking for pasted addresses. The MCP owns thread inspection and returns a blocked response when no supported file exists.

The result remains an uploaded geocoded `.tsv` file in the same thread. Slack replies must only include the short upload status and the normal source/scope/confidence/caveat lines.

## Safety

- Use only `text/csv`, `text/tab-separated-values`, `.csv`, and `.tsv` attachments.
- Parse with Python `csv`/`DictReader`.
- Require an `address` column.
- Do not persist source file content, parsed rows, raw Google API payloads, or coordinates outside the current tool result/upload.
- Do not paste latitude/longitude rows into Slack.
