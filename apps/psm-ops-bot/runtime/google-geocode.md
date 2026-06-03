# Google Geocode Runtime

PSM Ops Bot can geocode explicit address rows from a tagged Slack message through `psm_google_geocode`.

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
- Return rows with `address`, `latitude`, `longitude`, `geocode_status`, `formatted_address`, and `place_id`.
- Preserve non-`OK` rows in the output so PSMs can fix bad addresses or quota issues.
- Do not store address rows, raw Slack transcripts, or API responses outside the current tool result.

## Slack Output

For successful geocode requests, reply with a compact TSV-style block and the normal PSM Ops answer contract:

```text
Answer: Geocoded address rows:
address latitude longitude geocode_status formatted_address
...
Source: Google Geocoding API
Scope: current Slack thread; <N> address rows
Confidence: verified | needs-check | blocked
Caveat: Rows with non-OK geocode_status need manual address review.
```
