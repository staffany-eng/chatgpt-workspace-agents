# Product Ops Workflow Contract

## Intent

Provide a repeatable flow for Product Ops requests.

## Standard Flow

1. Clarify scope: objective, owner, due date, and success metric.
2. Gather evidence from configured systems.
3. If the user asked for a clear single-ticket Jira mutation, execute it in the same flow.
4. Otherwise return the smallest clarification needed, then execute and report outcomes.

## Write Safety

- Execute immediately only when the target, intended field change, and scope are explicit.
- Pause for confirmation when the write is ambiguous, risky, or bulk.
- Keep a clear record of proposed vs executed actions.
