---
name: launch-priority-identifier
description: Identify and normalize StaffAny Launch Priority from a Jira-to-Slack LaunchBot command or KER ticket context, then route the ticket to the correct launch-material skill. Use when a Slack command or Jira automation message asks LaunchBot to start release notes, help articles, changelog, or launch workflow for a KER ticket.
---

# Launch Priority Identifier

Use this skill when LaunchBot receives a Jira-to-Slack command such as:

```text
@Launch Bot start release notes for KER-123
@Launch Bot start help article workflow for KER-123
Launch Priority: P2 - Broad customer impact
```

## Inputs

- Slack message or thread text.
- Jira key, usually `KER-123`.
- Launch Priority from the Slack message when present.
- Fresh Jira lookup when the Slack message omits or ambiguously renders Launch Priority.

## Field Authority

- Jira Launch Priority field: `customfield_10561`.
- Do not use Jira engineering priority.
- Do not infer a final priority when the field is blank. Return `needs-check` with a suggested priority only when evidence is strong.

## Workflow

1. Parse the Slack command:
   - Extract the first `KER-\d+`.
   - Extract a visible `Launch Priority:` value if present.
   - Extract help article link if present.
2. If Launch Priority is missing, blank, or rendered as an object/string fragment, fetch the KER ticket from Jira and read `customfield_10561`.
3. Normalize priority:
   - `P1`, `P1 - ...`, `Priority 1` -> `P1`
   - `P2`, `P2 - ...`, `Priority 2` -> `P2`
   - `P3`, `P3 - ...`, `Priority 3` -> `P3`
   - `P4`, `P4 - ...`, `Priority 4` -> `P4`
4. Decide material route:
   - `P1`: help article and release notes.
   - `P2`: help article and release notes.
   - `P3`: release notes or internal update by default; help article only when user behavior changes.
   - `P4` or blank: no customer-facing material by default unless the change is customer-visible.
5. For release notes, immediately route to `release-notes-generator`.

## Output Contract

```text
Jira: <KER-key>
Launch Priority: <P1 | P2 | P3 | P4 | blank>
Priority Source: <slack_message | jira_customfield_10561 | needs-check>
Confidence: <verified | needs-check | blocked>
Material Route:
- Help article: <needed | not_needed | needs-check>
- Release notes: <needed | not_needed | needs-check>
Next Skill: release-notes-generator when release notes is needed.
```

## Guardrails

- If the ticket is not shipped or not in `6 - Shipped & Launching`, mark release materials `blocked` unless the user explicitly asks for a draft preview.
- If the Slack message and Jira disagree, Jira `customfield_10561` wins.
- Keep raw Jira descriptions, customer names, private URLs, and implementation details out of customer-facing material.
