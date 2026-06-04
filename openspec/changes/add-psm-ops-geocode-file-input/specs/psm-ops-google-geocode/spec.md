# Spec: PSM Ops Google Geocode

## ADDED Requirements

### Requirement: Slack CSV/TSV Address File Geocoding

PSM Ops Bot SHALL geocode explicit address rows from a CSV or TSV file attached to the current tagged Slack geocode request.

#### Scenario: User attaches a TSV with an address column

- GIVEN a Slack message directly mentions PS WEE
- AND the message asks to geocode addresses
- AND the current Slack thread contains an attached `.tsv` file with an `address` column
- WHEN the bot handles the request
- THEN it SHALL call `geocode_slack_address_file`
- AND it SHALL geocode the rows in the `address` column
- AND it SHALL upload the geocoded result as a `.tsv` file in the same Slack thread
- AND it SHALL NOT ask the user to paste the same addresses into Slack.

#### Scenario: User attaches a CSV with optional metadata columns

- GIVEN a tagged Slack geocode request includes an attached `.csv` file
- AND the file has an `address` column plus optional `label`, `customer`, `outlet`, or `source` columns
- WHEN `geocode_slack_address_file` parses the file
- THEN it SHALL use `address` as the Google Geocoding input
- AND it SHALL preserve optional metadata as row label/source where available.

#### Scenario: File is unsupported or missing address column

- GIVEN a tagged Slack geocode request includes an unsupported file type or a CSV/TSV without an `address` column
- WHEN the bot handles the request
- THEN it SHALL return a blocked response naming the missing supported input
- AND it SHALL NOT call Google Geocoding.

#### Scenario: Attachment metadata is absent from the model prompt

- GIVEN a Slack message directly mentions PS WEE
- AND the message asks to geocode "these addresses" or "these address"
- AND no address rows or attachment metadata are visible in the model prompt
- AND the current Slack thread permalink is available
- WHEN the bot handles the request
- THEN it SHALL call `geocode_slack_address_file` with the current Slack thread permalink before asking the user to paste addresses
- AND it SHALL let the MCP inspect the Slack thread for a supported CSV/TSV file
- AND it SHALL NOT call `geocode_slack_addresses` with an empty or guessed address list.
