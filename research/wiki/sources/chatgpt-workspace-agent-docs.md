# ChatGPT Workspace Agent Official Docs

## Source Metadata

- Type: official OpenAI documentation cluster
- Source class: ChatGPT workspace agents
- Source URL or path: official OpenAI Help Center and developer docs
- Date ingested: 2026-04-30
- Context: target product behavior
- Default weight: 5
- Privacy: public docs

## Context Caveat

ChatGPT workspace agents are currently rolling out and product behavior may change. Re-check official docs before implementing or publishing a real agent.

## Evidence Used

- Raw record: [research/raw/chatgpt/official-workspace-agent-docs.md](../../raw/chatgpt/official-workspace-agent-docs.md)
- Generated URL inventory: [research/raw/chatgpt/url-inventory.md](../../raw/chatgpt/url-inventory.md)

## What They Said

- ChatGPT workspace agents target repeatable tasks and workflows, and can be built, tested, shared, scheduled, and used in Slack.
- The builder supports tools, apps, custom MCPs, skills, and files.
- ChatGPT channel settings cover access, schedules, description, starter prompts, and appearance.
- App authentication can be end-user account or agent-owned account, with least privilege and service accounts recommended for shared access.
- Write actions default to asking during an agent run, and risky workflows need write action safety.
- ChatGPT skills are reusable workflows that can bundle instructions, examples, resources, and code and follow the Agent Skills open standard.
- Apps SDK state guidance separates authoritative business data, ephemeral UI state, and durable cross-session state.
- Apps SDK security guidance emphasizes least privilege, consent, validation, audit logs, redaction, retention, and human confirmation for irreversible operations.

## Evidence Trace

- Claim: ChatGPT workspace agents target repeatable tasks and workflows, and can be built, tested, shared, scheduled, and used in Slack. Evidence: The raw record summarizes the workspace-agent help and release notes. Source: `research/raw/chatgpt/official-workspace-agent-docs.md:27`.
- Claim: The builder supports tools, apps, custom MCPs, skills, and files. Evidence: The raw record captures builder surface support. Source: `research/raw/chatgpt/official-workspace-agent-docs.md:28`.
- Claim: ChatGPT channel settings cover access, schedules, description, starter prompts, and appearance. Evidence: The raw record summarizes channel settings. Source: `research/raw/chatgpt/official-workspace-agent-docs.md:29`.
- Claim: App authentication can be end-user account or agent-owned account, with least privilege and service accounts recommended for shared access. Evidence: The raw record captures auth-type guidance. Source: `research/raw/chatgpt/official-workspace-agent-docs.md:30`.
- Claim: Write actions default to asking during an agent run, and risky workflows need write action safety. Evidence: The raw record summarizes write action guidance. Source: `research/raw/chatgpt/official-workspace-agent-docs.md:31`.
- Claim: ChatGPT skills are reusable workflows that can bundle instructions, examples, resources, and code and follow the Agent Skills open standard. Evidence: The raw record captures the skills docs. Source: `research/raw/chatgpt/official-workspace-agent-docs.md:32`.
- Claim: Apps SDK state guidance separates authoritative business data, ephemeral UI state, and durable cross-session state. Evidence: The raw record summarizes Apps SDK state guidance. Source: `research/raw/chatgpt/official-workspace-agent-docs.md:34`.
- Claim: Apps SDK security guidance emphasizes least privilege, consent, validation, audit logs, redaction, retention, and human confirmation for irreversible operations. Evidence: The raw record summarizes Apps SDK security guidance. Source: `research/raw/chatgpt/official-workspace-agent-docs.md:35`.

## Learning Summary

- ChatGPT workspace-agent design should start from product-native surfaces: instructions, apps/tools/MCPs, skills, files, memory, schedules, channels, auth, approvals, versioning, and analytics.
- ChatGPT's auth and write-action controls are central design constraints, not afterthoughts.
- Skills should encode repeatable procedures, while apps/tools/MCPs provide external capability.
- State should be placed deliberately: business data in source systems, UI state in widgets, durable cross-session state in backend/storage or memory where available.

## Synthesis Gate

- Mode: autonomous_current_focus_synthesis
- Status: completed
- Focus source: `docs/product-compass.md`, `research/wiki/weights.md`, all active syntheses
- Evidence weight check: default weight 5; target product behavior source.
- Decision: promoted as normative source for final ChatGPT workspace-agent plans.

## Possible Agent Builder Relevance

- Agent-synthesized: The final builder rubric should be ChatGPT-native and should not expose OpenClaw/Hermes implementation internals unless needed.
- Agent-synthesized: Every planned workflow should decide app auth type, write approval behavior, file/memory boundary, and sharing scope.
- Do-not-promote: Do not assume features unavailable in the user's workspace without re-checking admin/product availability.

## Follow-Up Questions

- Which ChatGPT workspace-agent admin settings are enabled in Kai Yi's workspace?
- Should the final agent be private first, link-shared, or published to the organization directory?

