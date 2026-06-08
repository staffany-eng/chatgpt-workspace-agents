# Product Ops MCP Contract

Current safe default: Slack + Jira only.

## Jira Adapter Contract (TBD)

Add Jira adapter implementation and keep this contract updated with:

- Auth env vars
- Expected tools by class: `read`, `preview`, `write`
- Read/write boundaries
- Failure/timeout behavior

## Write Policy

- Read tools can run without extra approval.
- Preview tools can run to show planned writes.
- Write tools can execute immediately for explicit single-issue requests with clear scope.
- Keep preview/confirmation only for ambiguous or bulk writes.

## Future Expansion

When adding Notion, Docs, Sheets, or other systems, add each as a separate section with explicit boundaries before enabling.
