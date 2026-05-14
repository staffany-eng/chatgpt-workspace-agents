# Research Decisions

This page stores accepted research-backed learnings before promotion into future templates or implementation plans.

## Accepted Learnings

### Use Official Product Docs As Normative Sources

- Status: accepted for this corpus.
- Evidence: OpenClaw official docs source note; ChatGPT workspace-agent source note.
- Learning: For platform behavior, official docs outrank local implementations and analogies.
- Planning implication: `openclaw-kaiyi` can show what Kai Yi has already set up, but it should not silently override official OpenClaw or ChatGPT product guidance.

### Keep Apps, Skills, Files, Memory, And Instructions Separate

- Status: accepted for planning.
- Evidence: ChatGPT workspace-agent docs, OpenClaw workspace docs, Hermes skills/memory/context docs.
- Learning: Mature agent systems distinguish connector/tool access, procedural skills, reference files, durable memory, and operating instructions.
- Planning implication: Future ChatGPT workspace-agent plans should explicitly place each capability in the right surface rather than dumping everything into instructions.

### Preserve A Research Corpus Before Creating Templates

- Status: accepted for current phase.
- Evidence: Midas research-process source and current user request.
- Learning: The first useful artifact is the source map and evidence-backed synthesis, not premature templates.
- Planning implication: Build and audit the corpus before generating reusable ChatGPT workspace-agent templates.

### Use A StaffAny Proxy For Service-Account BigQuery MCP

- Status: accepted for implementation scaffold.
- Evidence: [BigQuery MCP Proxy](./sources/bigquery-mcp-proxy.md), [ChatGPT Workspace Agent Official Docs](./sources/chatgpt-workspace-agent-docs.md)
- Learning: ChatGPT should connect to a StaffAny-controlled MCP proxy when BigQuery calls must execute as a service account.
- Planning implication: The proxy owns BigQuery identity, read-only guardrails, logging, and production auth. ChatGPT should not connect directly to `https://bigquery.googleapis.com/mcp` for the service-account path.
- Caveat: Production use requires OAuth or equivalent strong auth in front of the proxy.

### Make StaffAny Hermes Data Bot The First App Proper

- Status: accepted for this repo.
- Evidence: [StaffAny Hermes Data Bot POC](./sources/staffany-hermes-data-bot-poc.md), [Hermes Agent Docs And Patterns](./sources/hermes-agent-docs.md)
- Learning: StaffAny Hermes Data Bot is now the primary runtime app, while earlier ChatGPT workspace-agent packets are deprecated evidence.
- Planning implication: Durable Hermes Data Bot behavior belongs under `apps/hermes-data-bot/`. Live `staffanydatabot` profile changes should be treated as runtime drift until reviewed and promoted.
- Caveat: Historical `agents/` snapshots stay available during the staged transition.

### Keep Hermes App Packets Repo-First And Profiles Stateful

- Status: accepted for Hermes app planning.
- Evidence: [Hermes Agent Docs And Patterns](./sources/hermes-agent-docs.md), [StaffAny Hermes Data Bot POC](./sources/staffany-hermes-data-bot-poc.md)
- Learning: A Hermes app packet should define durable identity, skills, MCP contracts, channel/runtime behavior, health checks, and runbooks, while the live profile owns secrets, sessions, memory, logs, cron state, gateway state, and temporary learning.
- Planning implication: New StaffAny Hermes Data Bot features should first decide which source packet surface changes; runtime-only changes remain drift until a specific reviewed artifact is promoted back into `apps/hermes-data-bot/`.
- Caveat: Do not copy raw memory, Slack transcripts, query rows, logs with sensitive content, or credentials from the live profile into the repo.

### Treat Launchbot As The App And Launch Superpower As A Skill

- Status: accepted for Launchbot packet cleanup.
- Evidence: current GCP topology places profile `launchbot` behind `hermes-gateway-launchbot.service`; the 2026-05-11 Launch Superpower handoff is workflow evidence and a reusable help-article procedure.
- Learning: Launchbot is the main Hermes app identity. Launch Superpower should not be modeled as a second app; its useful behavior belongs inside Launchbot as a help-article launch workflow skill.
- Planning implication: Durable Launchbot behavior belongs under `apps/launchbot/`; handoff evidence can remain under `research/raw/launch-superpower-bot/`, but runtime skill and workflow files should live under the Launchbot app packet.

### Use HubSpot Contract End Date And Current Tools For NurtureAny

- Status: accepted for the NurtureAny Sales Bot source packet.
- Evidence: HubSpot company property metadata checked on 2026-05-10; Slack workflow evidence from Eugene, Kerren, and Sarah teaching reps to fill contract end date/current tools in HubSpot notes and deal/company properties.
- Learning: NurtureAny renewal timing should use HubSpot company `contract_end_date` as the durable source of truth. NurtureAny current-tools context should use HubSpot company `current_tools` as the durable source of truth.
- Planning implication: `current_tool_renewal_date` can be returned as secondary context, but must not drive T-90 renewal inclusion or remove an account from missing-`contract_end_date` classification.
- Caveat: Do not store raw Slack transcripts or raw HubSpot rows in this research wiki.

### Promote NurtureAny Sales Best Practices As A Skill Reference

- Status: accepted for the NurtureAny Sales Bot source packet.
- Evidence: [NurtureAny Leadership Tactical Pause](./sources/nurtureany-leadership-tactical-pause.md), [NurtureAny Sales Training Materials](./sources/nurtureany-sales-training-materials.md), and [NurtureAny Sales Best Practices](./syntheses/nurtureany-sales-best-practices.md).
- Learning: NurtureAny sales workflow answers should consult a dedicated sales best-practices reference before drafting, Friday reviews, pre-demo plans, event follow-ups, coaching summaries, QO/QO Met quality advice, or operating-rhythm advice.
- Planning implication: The durable app reference belongs under `apps/nurtureany-sales-bot/skills/nurtureany-sales-bot/references/`; it should not be implemented as a new MCP server.
- Caveat: HubSpot still overrides training or tactical sources for live account, owner, country, contract end date, current tools, follow-up, calls, meetings, and deal facts.

### Separate Rev Planning Targets From Warehouse Actuals

- Status: accepted for StaffAny Rev metric answers.
- Evidence: [StaffAny Rev Team Planning And Metrics](./sources/staffany-rev-team-planning-and-metrics.md), [BigQuery MCP Proxy](./sources/bigquery-mcp-proxy.md)
- Learning: Rev planning Sheets and onboarding Slides explain targets, definitions, and operating rules, while Manticore/BigQuery is the source for actual QO, ARR, MRR, and movement metrics.
- Planning implication: NurtureAny should label source class in revenue answers, use QO for qualified-opportunity pace, and ask for clarification when "new ARR" could mean multiple metrics. Generic Hermes Data Bot answers should follow the same target-vs-actual split when asked for Rev metrics.
- Caveat: Planning artifacts can be used for target comparisons, but they should not be treated as actuals.

### Use Jira Links And SCHE FixVersion For PCO Release Watches

- Status: accepted for the PSM Ops Bot source packet.
- Evidence: [PSM Ops PCO Release Watch](./sources/psm-ops-pco-release-watch.md), [PSM Ops Release Watch](./syntheses/psm-ops-release-watch.md).
- Learning: For customer follow-up blocked by engineering shipment, PCO owns PS/customer work while KER/SCHE own engineering context and shipment truth. Jira issue links should connect PCO to KER/SCHE, and released `fixVersion` on linked SCHE shipment tickets should be the durable release signal.
- Planning implication: Future PSM Ops release-watch work should promote distilled behavior into `apps/psm-ops-bot/` because the live bot does not read the research wiki at runtime. Use Jira `duedate` for reminders and avoid labels when issue links can model the relationship.
- Caveat: KER and parent/container SCHE links give context; actual child SCHE shipment tickets still need to be linked once engineering confirms them.

## Rejected Or Deferred Learnings

- Do not copy OpenClaw workspace file structure directly into ChatGPT workspace agents. ChatGPT has its own product surfaces for apps, skills, files, memory, schedules, and channels.
- Do not treat Hermes' model/provider/runtime flexibility as a ChatGPT workspace-agent requirement unless a specific workflow needs custom MCPs or external infrastructure.
