# Health Checks

NurtureAny needs deterministic runtime checks because prompt correctness does not guarantee connector scopes, HubSpot fields, or gateway restarts.

## Expected Checks

- Hermes gateway service for `nurtureanysalesbot` is active.
- Secret redaction remains enabled.
- Slack gateway can receive mentions and identify caller email.
- HubSpot owner lookup works for configured admins/managers.
- HubSpot company property metadata includes `hs_is_target_account`, `hubspot_owner_id`, and `company_country`.
- HubSpot `company_country` options include `Singapore`, `Malaysia`, and `Indonesia`.
- A tiny target-account count query succeeds for each supported country.
- StaffAny BigQuery MCP lists only expected read-only tools.
- A tiny read-only C360 smoke query succeeds when C360 is enabled.
- Luma read-only smoke check succeeds when Luma is enabled.
- Honcho is disabled.

Healthy checks print nothing and exit 0.

## Failure Behavior

On failure, print only the failing subsystem and next check. Do not print secrets, env values, raw logs, raw Slack messages, raw HubSpot rows, phone numbers, or contact exports.

