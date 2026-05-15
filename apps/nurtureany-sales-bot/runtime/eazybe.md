# Eazybe Runtime

Server name: `eazybe_nurtureany`

Purpose: approval-gated WhatsApp template delivery for approved NurtureAny preview flows. No free-form WhatsApp sends are allowed. Daily nurture automation is disabled pending refinement; HubSpot Task reminder digests are separate no-agent automation and do not send WhatsApp.

## Environment

- `EAZYBE_API_KEY`: Eazybe API key.
- `EAZYBE_BROADCAST_API_URL`: Broadcast API endpoint for approved template sends.
- `EAZYBE_STATUS_API_URL`: optional provider status endpoint; otherwise pass statuses from the send result or a provider poller.

## Tools

- `preview_eazybe_template_messages`: preview selected message IDs, validate `templateName` plus ordered templateParams, redact phone numbers, and return `will_send=false`.
- `send_approved_eazybe_messages`: sends only selected approved template messages after `approval_marker` is provided.
- `check_eazybe_send_status`: summarizes accepted, queued, sent, delivered, failed, and pending statuses.

## Safety Contract

- No free-form WhatsApp sends.
- `approval_marker` is mandatory for sends.
- Phone numbers are redacted in Slack output; phone numbers are redacted before Slack output is returned.
- Template payloads must use an approved Eazybe `templateName` and ordered `templateParams`.
