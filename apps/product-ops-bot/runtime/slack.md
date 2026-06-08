# Slack Runtime

Product Ops Bot runs in Slack with mention-required behavior.

## Required Behavior

- Mention-only responses.
- Use `product-ops-intake-linking` as the default skill path for new requests.
- Use `staffany-product-delivery-workflow` when a request is confirmed as delivery workflow execution.
- For Jira grooming and PRD generation, route to `staffany-product-delivery-workflow` by default.
- For explicit Jira mutation requests with clear ticket target and field change, execute in the same flow without requiring a separate `run`.
- Ask follow-up questions only when the target issue, field change, or scope is ambiguous.
- Final answers should follow the labelled output contract.
- Do not post tool-progress or partial draft content.
- Automation-authored statuses must identify themselves as automation.
