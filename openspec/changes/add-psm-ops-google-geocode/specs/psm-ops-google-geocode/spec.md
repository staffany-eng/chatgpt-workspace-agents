# Spec: PSM Ops Google Geocode

## ADDED Requirements

### Requirement: Slack Address Geocoding

PSM Ops Bot SHALL geocode explicit address rows from a tagged Slack request.

#### Scenario: User provides address rows

- GIVEN a Slack message directly mentions PS WEE
- AND the message includes one or more explicit postal addresses
- WHEN the bot handles the request
- THEN it SHALL call `geocode_slack_addresses`
- AND it SHALL upload a `.tsv` file containing latitude and longitude for rows with `geocode_status = OK`
- AND it SHALL preserve non-OK rows and `partial_match=true` rows for manual review.
- AND it SHALL NOT paste latitude/longitude rows as raw Slack message text.

#### Scenario: Slack file upload is unavailable

- GIVEN a Slack message directly mentions PS WEE
- AND the message includes explicit postal addresses
- AND Slack upload is missing `files:write` or cannot complete
- WHEN the bot handles the request
- THEN it SHALL return a blocked response
- AND it SHALL NOT paste latitude/longitude rows as raw Slack message text.

### Requirement: Runtime-Only Google Credential

The geocode MCP SHALL read the Google Geocoding API key only from runtime secrets or local runtime credential files.

#### Scenario: Credential file is configured

- GIVEN `~/.staffany/google-geocode/credentials.json` exists for the runtime user
- AND the file contains `google_geocoding_api_key`
- WHEN `check_google_geocode_access` runs
- THEN it SHALL report verified credential presence
- AND it SHALL NOT print or return the API key.

### Requirement: Address Safety Boundaries

The bot SHALL avoid geocoding ambiguous non-address text.

#### Scenario: User gives a customer name only

- GIVEN a tagged Slack message asks for latitude/longitude
- AND the only provided text is a customer name, person name, phone number, or vague place hint
- WHEN the bot handles the request
- THEN it SHALL ask for the exact address
- AND it SHALL NOT call Google Geocoding.
