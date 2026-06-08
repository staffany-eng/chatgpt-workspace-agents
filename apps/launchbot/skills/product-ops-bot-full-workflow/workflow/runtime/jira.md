# Jira Runtime

Product Ops Bot safe default system is Jira.

## Mode

- Read-first operation for issue/query/reporting requests.
- Execute direct Jira writes when the user explicitly asks for a clear single-issue mutation.
- Keep confirmation gates for ambiguous intent, risky field changes, and bulk updates.

## Expected Tool Classes

- Read: search issues, list project tickets, issue detail lookup.
- Preview: draft update plan, draft transition plan, draft comments.
- Write: apply issue updates, transitions, and comments when target and scope are explicit.

## Safety Rules

- Do not mutate Jira on ambiguous intent.
- Do not bulk-update issues without explicit scope confirmation.
- Do not expose secrets, private tokens, or hidden internal metadata.
- For Product Ops intake triage, default backlog search scope is `KER` project tickets. `EDT` scope is opt-in only when explicitly requested.
