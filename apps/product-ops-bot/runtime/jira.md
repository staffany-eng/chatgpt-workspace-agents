# Jira Runtime

Product Ops Bot safe default system is Jira.

## Mode

- Read-first operation for issue/query/reporting requests.
- Write actions are approval-gated.
- No external writes without explicit same-thread `run`.

## Expected Tool Classes

- Read: search issues, list project tickets, issue detail lookup.
- Preview: draft update plan, draft transition plan, draft comments.
- Write (approval-gated): apply issue updates, transitions, and comments.

## Safety Rules

- Do not mutate Jira on ambiguous intent.
- Do not bulk-update issues without explicit scope confirmation.
- Do not expose secrets, private tokens, or hidden internal metadata.
