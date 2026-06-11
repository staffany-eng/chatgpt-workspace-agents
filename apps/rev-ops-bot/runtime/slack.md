# RevOps Bot Slack Runtime

RevOps Bot runs in mention-required mode.

## Behavior

- Reply in the same Slack thread.
- Ask concise follow-up questions for missing fields.
- Label preview, approval-required, executed, and blocked states clearly.
- Do not post operational updates as a human user.
- Structured Slack modal intake is submitted to Hermes as text beginning with
  `PRESTRUCTURED_CREATE_SUB_DEAL_REQUEST` and a JSON block. Treat that JSON as
  the request payload and continue with Windmill preflight.
- `/revops-create-sub-deal` is handled by the Hermes Slack gateway through
  Slack Socket Mode. Request URLs are not needed while Socket Mode is enabled.
- The modal handler must run in the same Hermes gateway process as Slack message
  handling so interactive payloads do not compete across multiple Socket Mode
  clients for the same Slack app token.
- Configure `REVOPS_CREATE_SUB_DEAL_ALLOWED_CHANNEL_IDS` to restrict where the
  slash command can open the modal. Leave it empty only for early POC testing.

## Example

User asks:

```text
@revopsbot preview create sub deal for Acme...
```

Bot should:

1. Search or confirm main deal.
2. Collect missing Billing Engine fields.
3. Call Windmill dry-run preview.
4. Return the payload summary and required confirmation text.
5. Execute only after the user replies with the exact confirmation text.

The bot must not execute live creation before Windmill preview and exact Slack approval.
