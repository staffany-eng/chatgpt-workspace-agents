# Google Geocode Runtime

PSM Ops Bot can geocode explicit address rows from a tagged Slack message through `psm_google_geocode` and upload the result as a `.tsv` file in the same Slack thread.

## Access Contract

- Tool server: `psm_google_geocode`
- Allowed tools:
  - `check_google_geocode_access`
  - `geocode_slack_addresses`
- Credential sources, checked in this order:
  - `GOOGLE_GEOCODING_API_KEY` from the live profile `.env`
  - `PSM_OPS_GOOGLE_GEOCODE_CREDENTIALS_FILE`
  - `GEOCODE_CREDENTIALS_FILE`
  - `~/.staffany/google-geocode/credentials.json`
- Credentials file schema: JSON with `google_geocoding_api_key`.

Secrets live only in Secret Manager, the live profile `.env`, or the runtime user credential file. Do not commit API keys or credential JSON.

## Behavior

- Use only address text explicitly present in the current Slack request.
- Do not geocode customer names, person names, phone numbers, or vague location hints as if they were addresses.
- Max addresses per Slack request: 25.
- Default `region_bias` is `sg`; set `country_restriction` only when the user or address clearly specifies the country.
- The uploaded `.tsv` contains rows with `address`, `latitude`, `longitude`, `geocode_status`, `formatted_address`, and `place_id`.
- Preserve non-`OK` rows in the output so PSMs can fix bad addresses or quota issues.
- Upload the generated `.tsv` through Slack `files.getUploadURLExternal` and `files.completeUploadExternal`.
- If Slack upload is unavailable or missing `files:write`, block instead of pasting latitude/longitude rows as raw Slack text.
- Do not store address rows, raw Slack transcripts, or API responses outside the current tool result.

## Slack Output

For successful geocode requests, upload a `.tsv` file and reply only with the normal PSM Ops answer contract:

```text
Answer: Uploaded geocoded TSV file: <filename>.tsv (<OK count>/<total count> OK).
Source: Google Geocoding API
Scope: current Slack thread; <N> address rows
Confidence: verified | needs-check | blocked
Caveat: Rows with non-OK geocode_status need manual address review.
```

Do not paste the geocoded rows into the Slack message body.
