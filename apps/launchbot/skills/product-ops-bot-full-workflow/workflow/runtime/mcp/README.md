# Product Ops MCP Contract

Current safe default: Slack + Jira only.

## Jira Adapter Contract (TBD)

Add Jira adapter implementation and keep this contract updated with:

- Auth env vars
- Expected tools by class: `read`, `preview`, `write_approval_gated`
- Read/write boundaries
- Failure/timeout behavior

## Write Policy

- Read tools can run without extra approval.
- Preview tools can run to show planned writes.
- Write tools require explicit same-thread `run`.

## Future Expansion

When adding Notion, Docs, Sheets, or other systems, add each as a separate section with explicit boundaries before enabling.
