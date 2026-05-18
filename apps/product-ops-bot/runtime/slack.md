# Slack Runtime

Product Ops Bot runs in Slack with mention-required behavior.

## Required Behavior

- Mention-only responses.
- Use `product-ops-intake-linking` as the default skill path for new requests.
- Use `staffany-product-delivery-workflow` when a request is confirmed as delivery workflow execution.
- For Jira grooming and PRD generation, route to `staffany-product-delivery-workflow` by default.
- Read-first behavior; do not execute Jira writes without explicit same-thread `run`.
- Final answers should follow the labelled output contract.
- Do not post tool-progress or partial draft content.
- Automation-authored statuses must identify themselves as automation.
