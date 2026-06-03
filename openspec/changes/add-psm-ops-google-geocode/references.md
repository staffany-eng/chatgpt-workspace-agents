# References: PSM Ops Google Geocode Capability

## External API Docs

- Google Geocoding API request and response docs: https://developers.google.com/maps/documentation/geocoding/requests-geocoding
- Google Geocoding API status codes: https://developers.google.com/maps/documentation/geocoding/requests-geocoding#StatusCodes
- Slack external file upload flow:
  - `files.getUploadURLExternal`: https://api.slack.com/methods/files.getUploadURLExternal
  - `files.completeUploadExternal`: https://api.slack.com/methods/files.completeUploadExternal

## Credential Resolution

The MCP calls `profile_env.load_profile_env()` before resolving credentials so deployed profile `.env` values are available at runtime.

Credential lookup order:

1. `GOOGLE_GEOCODING_API_KEY`
2. `PSM_OPS_GOOGLE_GEOCODE_CREDENTIALS_FILE`
3. `GEOCODE_CREDENTIALS_FILE`
4. `~/.staffany/google-geocode/credentials.json`

Unresolved config placeholders such as `${GOOGLE_GEOCODING_API_KEY}` are treated as empty so the runtime can fall back to file-based credentials. No Google API key or credential JSON is checked into the app packet.

## Behavior Decisions

- Limit one Slack request to 25 address rows to keep runtime and Slack file output bounded.
- Use only explicit postal address rows; block customer names, person names, phone numbers, outlet-name-only values, and vague location hints before calling Google.
- Preserve duplicate input rows because each user-provided row may represent a distinct outlet or mapping line.
- Upload geocoded output as a `.tsv` file in the Slack thread instead of pasting latitude/longitude rows as raw Slack text.
- Treat non-`OK` Google statuses and `partial_match=true` rows as manual-review rows. These rows remain in the TSV, but do not count toward verified OK rows.
