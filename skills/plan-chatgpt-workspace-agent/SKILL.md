---
name: plan-chatgpt-workspace-agent
description: Plan additions or updates to ChatGPT workspace agents by producing a manual change packet with exact agent fields, surface decisions, UI checklist, test prompts, safety notes, assumptions, and evidence. Use when Codex needs to design, add, update, test, share, schedule, publish, or review a ChatGPT workspace agent, especially when deciding instructions, apps/tools/MCPs, skills, files, memory, schedules, Slack/channel behavior, auth, and write approvals.
---

# Plan ChatGPT Workspace Agent

## Overview

Use this skill to turn a user request into a ChatGPT workspace-agent change packet. By default, prepare exact manual changes the user can apply in the ChatGPT agent builder. If the user explicitly asks for browser-assisted application, help apply the packet through ChatGPT's UI with Browser Use and stop for confirmation before saving, publishing, deleting, scheduling, or changing broad access.

Treat official OpenAI/ChatGPT docs as the normative source for product behavior. Because workspace agents and skills are rollout-sensitive, re-check official docs before final production guidance when accuracy matters.

## Workflow

1. Classify the request as `new agent`, `update existing agent`, `review existing plan`, `browser-assisted apply`, or `risky/destructive change`.
2. Read `references/workspace-agent-rubric.md` for the required planning surfaces.
3. Read `references/change-packet-template.md` and use that output shape unless the user requested another format.
4. Read `references/chatgpt-ui-checklist.md` when the user needs ChatGPT builder, sharing, schedule, Slack, or skills upload steps.
5. Ask at most one focused question only when a missing answer blocks a safe plan. Otherwise choose the conservative default and list it under assumptions.
6. Produce a change packet that covers every rubric item or marks it `not used in v1`.
7. If browser-assisted application was requested, apply only the approved packet values in the ChatGPT UI and verify visible state after each meaningful change.

## Rules

- Keep surfaces separate: instructions, apps/tools/MCPs, skills, files, memory, schedules, channels, auth, and write approvals.
- Put durable behavior and source hierarchy in agent instructions.
- Put repeatable procedures, output formats, and examples in skills.
- Put durable references, templates, policies, and source docs in files.
- Put channel-specific behavior in channel settings and schedule-specific behavior in schedule instructions.
- Prefer end-user auth for private/personal workflows and agent-owned/service-account auth for shared or Slack workflows.
- Keep write approvals on for actions that send, edit, post, delete, publish, mutate business data, or expose data to broader audiences.
- Do not store secrets, tokens, OAuth credentials, private keys, or raw session transcripts in agent instructions, files, skills, or memory.
- Do not claim a public API exists for managing ChatGPT workspace agents unless official docs explicitly show one.

## Browser-Assisted Apply

Use this mode only when the user explicitly asks to apply the change in ChatGPT or use Browser Use. If Browser Use is unavailable, fall back to the manual change packet and say so briefly.

1. Generate or confirm the change packet first.
2. Open ChatGPT in Browser Use and navigate through the visible agent builder UI.
3. Paste or select only values from the approved packet.
4. After each major section, check the visible UI state before continuing.
5. Run preview tests where the UI supports it.
6. Before clicking `Create`, `Update`, `Publish`, `Add schedule`, `Connect Slack`, `Delete`, or any equivalent final action, summarize the pending action and get explicit confirmation.
7. After confirmation and action, verify the visible success state, version/history signal, saved fields, or agent listing where available.

## Risk Handling

For destructive or broad-access changes, lead with the risk and require explicit user confirmation before presenting the final UI action. Risky changes include deleting an agent, publishing to an organization directory, disabling write confirmations, switching to agent-owned auth, connecting Slack, adding high-scope connectors, or adding schedules that can send/post/update content.

If a user asks for direct API automation, explain that this skill does not assume a public workspace-agent management API. Offer manual or browser-assisted application instead.

## References

- `references/workspace-agent-rubric.md`: required planning questions and evidence rules.
- `references/chatgpt-ui-checklist.md`: current UI checklist to create, update, share, schedule, and connect agents.
- `references/change-packet-template.md`: fixed output format.
