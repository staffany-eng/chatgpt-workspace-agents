# Eazybe Runtime

Server name: `eazybe_nurtureany`

Purpose: approval-gated WhatsApp template delivery for the daily NurtureAny nurture workflow. No free-form WhatsApp sends are allowed. Draft copy from `build_daily_nurture_plan` is preview text until it is mapped into an approved Eazybe template.

## Environment

- `EAZYBE_API_KEY`: Eazybe API key.
- `EAZYBE_BROADCAST_API_URL`: Broadcast API endpoint for approved template sends.
- `EAZYBE_STATUS_API_URL`: optional provider status endpoint; otherwise pass statuses from the send result or a provider poller.
- `NURTUREANY_DAILY_RUNS_DIR`: local JSON run payload directory shared with `build_daily_nurture_plan`, so 12pm preview/status/reminder tools reload the 9am `run_id` messages instead of recomputing account selection. If missing, daily nurture returns `Confidence: needs-check`.

## Tools

- `preview_eazybe_template_messages`: preview selected message IDs, validate `templateName` plus ordered templateParams, redact phone numbers, and return `will_send=false`.
- `send_approved_eazybe_messages`: sends only selected approved template messages after `approval_marker` is provided.
- `check_eazybe_send_status`: summarizes accepted, queued, sent, delivered, failed, and pending statuses.
- `build_daily_nurture_reminder`: builds the 12pm Slack reminder text for unsent and unskipped stakeholder messages. When `messages` are omitted, it loads the persisted 9am run from `NURTUREANY_DAILY_RUNS_DIR`.

## Safety Contract

- No free-form WhatsApp sends.
- `approval_marker` is mandatory for sends.
- Phone numbers are redacted in Slack output; phone numbers are redacted before Slack output is returned.
- Template payloads must use an approved Eazybe `templateName` and ordered `templateParams`.
- Sent for the 12pm workflow means Eazybe accepted/queued the approved template, or HubSpot later shows a matching WhatsApp communication for the stakeholder/account after run start.
