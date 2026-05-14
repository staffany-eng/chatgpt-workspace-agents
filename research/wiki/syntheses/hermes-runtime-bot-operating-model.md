# Hermes Runtime Bot Operating Model

## Evidence Used

- [Hermes Agent Docs And Patterns](../sources/hermes-agent-docs.md) - weight 4.
- [Workspace Agent Abstraction Boundaries](./workspace-agent-abstraction-boundaries.md) - current repo synthesis.
- [Instruction Surfaces](./instruction-surfaces.md) - current repo synthesis.
- [Skills vs Apps vs MCP](./skills-vs-apps-vs-mcp.md) - current repo synthesis.

## Synthesis

For the three StaffAny Hermes bots, use the same runtime model:

- Da Ta Hermz: `apps/hermes-data-bot`
- NurtureAny: `apps/nurtureany-sales-bot`
- Launchbot: `apps/launchbot`

The source packet is durable product behavior. The live Hermes profile is runtime state. A live profile can accumulate sessions, memory, cron state, gateway state, logs, and temporary local fixes, but those are not durable until a specific useful change is reviewed and promoted into the app packet.

Hermes has several different "keep working / get smarter" primitives:

- Skills: repeatable procedures, examples, scripts, references, and output contracts.
- MCPs: narrow external-system tool boundaries.
- Memory: confirmed recall, not source of truth for StaffAny business state.
- Cron: scheduled work.
- No-agent scripts: deterministic health, audit, and watchdog checks.
- Kanban: durable task queues with worker profiles and run history.
- Delegation: in-turn parallel work.
- Persistent goals: session continuation, separate from cron or Kanban.

Do not collapse these into one vague learning layer. Pick the primitive that matches the job.

## Planning Rules

- Before changing any of the three bot packets, read `research/wiki/sources/hermes-agent-docs.md` plus this synthesis.
- Put durable bot behavior in `SOUL.md`, skills, reference files, MCP contracts, config templates, runtime docs, tests, and runbooks.
- Keep `.env`, credentials, raw Slack transcripts, raw HubSpot rows, query rows, logs, sessions, memory dumps, and unreviewed runtime learning out of the repo.
- Treat runtime learning as unreviewed drift until it is promoted into a repo file and verified.
- Use memory only for confirmed recall. Do not use Honcho or built-in memory as StaffAny account, contact, metric, approval, permission, or source-of-truth storage.
- Prefer no-agent health checks for routine bot operations so healthy runs consume no model tokens and create no Slack noise.
- Add or narrow MCP tools before writing skill instructions that depend on them.
- Use Kanban only when the workflow needs durable task state, named workers, comments, run history, or queue dispatch.
- Use cron only for scheduled work, and keep bot-authored Slack output clearly identified as automation.

## Bot-Specific Consequences

- Da Ta Hermz can use Honcho only under its explicit memory contract; confirmed metric or terminology truth still belongs in repo registries or skill references.
- NurtureAny V1 keeps Honcho disabled and HubSpot as business truth. A future lessons loop should be a reviewed promotion workflow, not silent auto-learning from Slack.
- Launchbot should keep help-article truth grounded in Pantheon, Jira/KER, cached Intercom shape evidence, and live stale checks. Runtime article attempts are not durable rules until promoted into the Launchbot packet.
