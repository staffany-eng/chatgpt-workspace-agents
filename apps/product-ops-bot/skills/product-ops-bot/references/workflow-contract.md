# Product Ops Workflow Contract

## Intent

Provide a repeatable flow for Product Ops requests.

## Standard Flow

1. Clarify scope: objective, owner, due date, and success metric.
2. Gather evidence from configured systems.
3. If Jira write preconditions are met, execute the Jira update directly and report outcomes.
4. If write preconditions are missing, report blocker clearly and provide the smallest next step.

## Write Safety

- For routine Jira grooming requests, explicit `run` confirmation is not required.
- Never execute writes when issue target, credentials, or required context are missing.
- Keep a clear record of proposed vs executed actions.
