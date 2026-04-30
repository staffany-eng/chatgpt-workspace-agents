# Workspace Agent Rubric

Use this rubric before finalizing any ChatGPT workspace-agent change packet. Cover every item or mark it `not used in v1`.

## Evidence Priority

1. Official ChatGPT/OpenAI docs for ChatGPT workspace-agent behavior.
2. Accepted local decisions in `research/wiki/decisions.md`.
3. Cross-source syntheses in `research/wiki/syntheses/`.
4. OpenClaw and Hermes patterns only as analogies, not product truth.

Re-check official docs when product behavior, UI labels, availability, auth behavior, skills behavior, Slack behavior, schedules, or admin controls matter.

## Required Questions

1. Task: What repeatable workflow does the agent own?
2. Audience: Who runs it, and where: ChatGPT, Slack, schedule, or multiple channels?
3. Apps/tools/MCPs: Which systems must it access?
4. Auth: Which connections are end-user account versus agent-owned account?
5. Write safety: Which actions require confirmation?
6. Skills: Which repeatable procedures, formats, scripts, or examples should be packaged as skills?
7. Files: Which templates, examples, policies, or source docs should be uploaded?
8. Memory: What should be remembered per user or per agent, and what must stay out?
9. Output: What artifact should the agent produce, and where should it save or send it?
10. Testing: What preview prompts, negative cases, and source fixtures prove it works?
11. Sharing: Should it be private, link-shared, directory-published, Slack-connected, or schedule-only?
12. Iteration: What analytics, version history checks, run reviews, or feedback loop improves it?

## Surface Placement

- Instructions: mission, source hierarchy, operating rules, safety boundaries, output style.
- Apps/tools/custom MCPs: external systems and capabilities.
- Skills: repeatable methods, output formats, examples, scripts, and procedural knowledge.
- Files: durable reference material, templates, examples, and source docs.
- Memory: scoped user or agent continuity; never secrets or public instructions.
- Schedules/channels: when and where the agent runs.
- Auth/write approvals: whose credentials act, and what confirmations are required.

## Defaults

- Keep new agents private until preview tests pass.
- Keep write actions set to ask during runs unless the user explicitly accepts the risk.
- Use service accounts or least-privilege shared accounts for agent-owned auth.
- Use end-user auth for personal or per-user data.
- Keep Slack-connected agents on shared auth only.
- Avoid schedules that write/post/send until the output is stable and approvals are clear.
