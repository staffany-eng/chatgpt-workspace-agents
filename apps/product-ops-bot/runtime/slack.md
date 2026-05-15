# Slack Runtime

Product Ops Bot runs in Slack with mention-required behavior.

## Required Behavior

- Mention-only responses.
- Read-first behavior; do not execute Jira writes without explicit same-thread `run`.
- Final answers should follow the labelled output contract.
- Do not post tool-progress or partial draft content.
- Automation-authored statuses must identify themselves as automation.
