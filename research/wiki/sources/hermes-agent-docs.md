# Hermes Agent Docs And Patterns

## Source Metadata

- Type: public repo docs and live architecture docs
- Source class: Hermes Agent
- Source URL or path: `https://github.com/NousResearch/hermes-agent`; `https://hermes-agent.nousresearch.com/docs/`
- Date ingested: 2026-04-30
- Date refreshed: 2026-05-15
- Context: primary Hermes runtime architecture source for this repo, alternate source for non-Hermes agent patterns
- Default weight: 4
- Privacy: public docs

## Context Caveat

Hermes is a self-hosted agent runtime, not ChatGPT workspace agents. Use it for Hermes bot architecture and runtime vocabulary. Do not copy Hermes implementation mechanics into non-Hermes plans without a stronger product-native source.

## Evidence Used

- Raw record: [research/raw/hermes/hermes-docs-and-patterns.md](../../raw/hermes/hermes-docs-and-patterns.md)
- Generated docs inventory: [research/raw/hermes/docs-inventory.md](../../raw/hermes/docs-inventory.md)
- May 10 live docs refresh: [research/raw/hermes/live-docs-refresh-2026-05-10.md](../../raw/hermes/live-docs-refresh-2026-05-10.md)
- May 15 live docs refresh: [research/raw/hermes/live-docs-refresh-2026-05-15.md](../../raw/hermes/live-docs-refresh-2026-05-15.md)

## What They Said

- The live docs expose both `llms.txt` and `llms-full.txt`; the May 15 refresh captured 98 curated index links and 153 full source pages.
- Compared with the May 10 refresh, the full bundle added six source pages and removed none: worker lanes, Codex app server runtime, LSP, Line messaging, LLM plugin access, and video-generation provider plugins.
- Hermes positions itself as a self-improving, terminal-native agent with persistent memory, agent-created skills, and a messaging gateway spanning many platforms.
- Hermes setup spans Linux, macOS, WSL2, Termux, Nix, native Windows beta, Docker, SSH-like remote usage, and deployment profiles, so runtime assumptions should be host-specific.
- Hermes profiles are separate runtime homes with their own config, `.env`, `SOUL.md`, memories, sessions, skills, cron jobs, gateway state, and shareable non-secret distribution shape.
- Prompt assembly keeps identity, memory snapshots, user-profile snapshots, skills index, project context files, timestamp/session data, platform hints, and ephemeral overlays as separate layers.
- Context files use priority ordering and progressive discovery, with `SOUL.md` as global identity and lower-level project files loaded as needed instead of all at startup.
- Skills are procedural memory with progressive disclosure; packages can include references, templates, scripts, assets, environment prompts, config settings, platform filters, and conditional activation.
- Hermes can create or update skills through a self-improvement loop, and Curator reviews generated skills for staleness, narrowness, duplication, and catalog quality.
- Built-in memory is bounded into `MEMORY.md` and `USER.md`, snapshotted at session start, and intentionally excludes raw dumps, ephemera, context-file content, secrets, and unsafe material.
- External memory providers such as Honcho are additive to built-in memory rather than replacements, adding semantic recall or user modeling while keeping file-memory boundaries.
- Hermes tool architecture includes built-in tools, custom tools, MCP servers, ACP/API/tool gateway surfaces, per-server filtering, dynamic refresh, utility wrappers, and subprocess environment filtering.
- Messaging gateway docs cover a broad adapter set; Slack uses Socket Mode, app and bot tokens, mention-first channel starts, thread continuation, reinstall after scope changes, and optional channel prompts or skills.
- Cron supports one-shot and recurring automation, skill attachment, workdir binding, local/origin/platform delivery, quiet-success `[SILENT]`, and script-only no-agent checks.
- Kanban is separate durable work management backed by SQLite and gateway dispatch, while delegation is an in-turn fork/join tool for volatile parallel work.
- The new Kanban worker-lanes page makes queue execution more explicit: lanes bind named worker profiles, concurrency, and work classes instead of one generic worker loop.
- Persistent goals keep a session objective alive across turns through judge-loop continuation and explicit pause, resume, and clear controls; they are distinct from cron and Kanban.
- Security guidance layers authorization, dangerous-command approval, container/sandbox isolation, MCP credential filtering, context-file scanning, cross-session isolation, input sanitization, checkpoints, and rollback.
- Developer docs describe agent loop, prompt assembly, context compression/caching, gateway internals, session storage, provider runtime, tool runtime, and extension points for plugins.
- Media and web features include browser supervision, web search, computer use, vision, image generation, text-to-speech, voice mode, Spotify, web dashboard, skins, RL training, and trajectory export.
- Reference docs cover CLI, slash commands, profile commands, environment variables, tools, toolsets, MCP config, model catalog, skills catalog, optional skills catalog, and FAQ.
- For StaffAny bots, Hermes docs support the source-packet pattern: durable prompts, config templates, skills, MCP contracts, Slack/runtime docs, health checks, and runbooks stay in repo control.
- For StaffAny bots, runtime learning should not be treated as product truth until promoted into a reviewed skill, reference, MCP contract, config template, test, or runbook.
- For StaffAny bots, choose the right primitive: skill for procedure, MCP for external systems, cron for schedules, no-agent script for health, Kanban for durable queues, delegation for in-turn parallel work, and memory for confirmed recall.

## Evidence Trace

- Claim: May 15 docs coverage captured. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:262`.
- Claim: Six pages were added since May 10. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:263`.
- Claim: Hermes frames itself as self-improving. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:264`.
- Claim: Hermes supports multiple host modes. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:265`.
- Claim: Profiles are separate runtime homes. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:266`.
- Claim: Prompt assembly keeps context layers separate. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:267`.
- Claim: Context files are priority ordered. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:268`.
- Claim: Skills are procedural memory packages. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:269`.
- Claim: Curator reviews generated skills. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:270`.
- Claim: Built-in memory is bounded and filtered. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:271`.
- Claim: External memory is additive. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:272`.
- Claim: Tools and MCPs are narrow runtime surfaces. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:273`.
- Claim: Slack uses Socket Mode and scoped app config. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:274`.
- Claim: Cron supports scheduled and no-agent work. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:275`.
- Claim: Kanban and delegation are separate primitives. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:276`.
- Claim: Worker lanes make Kanban dispatch explicit. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:277`.
- Claim: Persistent goals are separate from cron and Kanban. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:278`.
- Claim: Security is layered across auth, sandboxing, and rollback. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:279`.
- Claim: Developer docs expose runtime extension points. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:280`.
- Claim: Media and web features are first-class surfaces. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:281`.
- Claim: Reference docs cover command and config contracts. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:282`.
- Claim: StaffAny bots should use source packets for durable behavior. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:283`.
- Claim: Runtime learning needs reviewed promotion. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:284`.
- Claim: Bot capabilities should map to one Hermes primitive. Evidence: Raw extract. Source: `research/raw/hermes/live-docs-refresh-2026-05-15.md:285`.

## Learning Summary

- Hermes has a coherent app-runtime model: source-controlled app packets should define durable behavior, while live profiles carry runtime state and unreviewed learning.
- Hermes has multiple continuation primitives with different jobs: memory, skills, cron, Kanban, delegation, persistent goals, and gateway dispatch should not be collapsed into one vague learning surface.
- Hermes docs make runtime boundaries explicit: profiles own secrets, sessions, memories, cron state, gateway state, and logs; repo packets should own prompts, skills, MCP contracts, health checks, and runbooks.
- Hermes skills and MCPs should be paired carefully: skills encode repeatable procedure, while MCPs expose the smallest safe external-system capability surface.
- Hermes memory can improve recall, but for StaffAny business bots it should remain deliberate recall only until promoted through reviewed repo references, tests, and deploy checks.
- Hermes operations need evidence surfaces: health checks, no-agent scripts, gateway logs, service status, profile audits, and Slack smoke tests are part of the product shape, not afterthoughts.

## Synthesis Gate

- Mode: autonomous_current_focus_synthesis
- Status: completed
- Focus source: `docs/product-compass.md`, `research/wiki/weights.md`, active syntheses, and the three StaffAny Hermes app packets
- Evidence weight check: default weight 4; strong current Hermes runtime source for Hermes apps, but not universal product truth outside Hermes.
- Decision: refresh promoted into the shared Hermes runtime bot operating model and wired into the three bot app guides before bot-specific changes.

## Possible Agent Builder Relevance

- Agent-synthesized: For Da Ta Hermz, NurtureAny, and Launchbot work, read this source note before changing runtime profile shape, memory behavior, skill packaging, MCP exposure, Slack gateway behavior, cron, Kanban, or health checks.
- Agent-synthesized: Treat runtime learning as unreviewed drift until a specific change is promoted into a repo-owned skill, reference, config template, MCP contract, test, or runbook.
- Agent-synthesized: Prefer no-agent scripts for routine health and audit checks so healthy bot operations do not consume model tokens or create Slack noise.
- Agent-synthesized: Use Kanban only for durable task queues, delegation only for in-turn parallel work, cron for scheduled work, and memory only for confirmed recall.
- Do-not-promote: Do not use external memory providers such as Honcho as business source of truth for StaffAny account, contact, metric, permission, or approval state.
- Open question: Which StaffAny bot workflows should become Hermes Kanban queues instead of ad hoc Slack threads or cron prompts?

## Follow-Up Questions

- Should the three bot packets share a single checked-in Hermes runtime checklist, or keep the checklist as this wiki synthesis plus app-local AGENTS pre-read rules?
- Should NurtureAny get a reviewed lesson-promotion workflow that stores proposed lessons separately from HubSpot truth and requires repo promotion before deployment?
- Should Launchbot use Kanban worker lanes for multi-step help article updates once Pantheon and Intercom access are stable?
