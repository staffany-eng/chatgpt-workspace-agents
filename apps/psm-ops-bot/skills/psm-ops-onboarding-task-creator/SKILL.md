---
name: psm-ops-onboarding-task-creator
description: Use when PS WEE / PSM Ops is directly mentioned to create or link a parent onboarding PCO ticket and child onboarding tasks for one organisation.
license: Internal
metadata:
  version: 1.0.0
  author: StaffAny
  hermes:
    tags: [staffany, psm, jira, pco, onboarding, slack]
    related_skills: [psm-ops-bot, native-mcp]
---

# PSM Ops Onboarding Task Creator

Use this skill for direct PS WEE / PSM Ops Slack requests to create onboarding task lists for an organisation, for example `ps wee manager onboarding tasks for Bata`.

This is a Jira PCO workflow. Use the shared PSM Ops Slack identity rules and the `psm_jira` MCP only. Do not use SOUL, memory, Slack history, or local files as task truth.

## Trigger

Run this workflow only when the current Slack message directly mentions PS WEE / this bot and asks for onboarding task creation, parent/child onboarding task setup, or onboarding task linking for one organisation.

Untagged same-thread replies are silent under strict mention mode. Approval must be a same-thread message that directly mentions PS WEE.

## First Response Is Read-Only

On the first direct-mention request:

1. Parse the organisation name.
2. Parse the requested child task list from bullets, numbered lines, or concise task phrases.
3. Choose the parent summary, usually `<Organisation> Onboarding` unless the user supplied an exact parent title.
4. Call only `plan_pco_onboarding_tasks`, passing the current Slack thread permalink and current Slack sender ID/mention or profile email.
5. Return the proposed plan: existing parent, missing parent if any, existing child tasks, missing child tasks, and links to create.

Do not call `apply_pco_onboarding_task_plan`, `create_approved_pco_task`, `create_ps_wee_intake_ticket`, or `link_pco_to_pco_issue` before approval.

If the planning tool returns `choose_candidate`, ask the user to choose the PCO key before approval. Do not apply an ambiguous plan.

`plan_pco_onboarding_tasks` owns identity-sensitive field resolution. It verifies the current Slack tagger from the Slack thread permalink when available, resolves `PS Team` from that Slack user, and ignores any model-inferred `ps_team` override. Do not guess the single-select `PS Team` field from message wording or memory.

## Approval And Apply

After a same-thread direct-mention approval such as `@PS WEE approve create/link onboarding tasks`:

1. Use the exact plan returned by `plan_pco_onboarding_tasks`, with any user-selected candidate keys resolved.
2. Call `apply_pco_onboarding_task_plan` once.
3. Paste the returned `answer.slack_reply` first when present.
4. Add the normal PSM Ops source/scope/confidence/caveat lines.

The apply tool is the only public write entrypoint for this workflow.

## Link Direction

Every child must link to the parent as:

- Child `implements` parent.
- Parent is `implemented by` child.

Do not use the existing `link_pco_to_pco_issue` tool for this onboarding workflow. That tool remains for Event AA link-to-existing and always creates `Relates`.

## Output

Use the PSM Ops answer contract:

```text
Answer: <plan summary, blocked choice request, or apply result>
Source: Jira PCO
Scope: <organisation; parent summary; child task count>
Confidence: verified | needs-check | blocked
Caveat: <approval requirement, ambiguity, or write summary>
```

For the read-only plan, the caveat must say no Jira issues or links were created.
