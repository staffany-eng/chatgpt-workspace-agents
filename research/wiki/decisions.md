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

## Rejected Or Deferred Learnings

- Do not copy OpenClaw workspace file structure directly into ChatGPT workspace agents. ChatGPT has its own product surfaces for apps, skills, files, memory, schedules, and channels.
- Do not treat Hermes' model/provider/runtime flexibility as a ChatGPT workspace-agent requirement unless a specific workflow needs custom MCPs or external infrastructure.
