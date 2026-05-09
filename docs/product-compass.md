# Agent Builder Product Compass

This repo helps us operate and evolve StaffAny Hermes Data Bot, while preserving the research corpus that led to the app shape.

## Purpose

Agent Builder should answer one practical question: how should a StaffAny internal agent app be structured so it can do repeatable work reliably, safely, and with the right abstraction boundaries?

The first app proper is StaffAny Hermes Data Bot. NurtureAny Sales Bot now uses the same app-packet pattern for sales target-account nurture work. Earlier ChatGPT workspace-agent snapshots remain as historical evidence and migration input.

## Current Thesis

A good agent app needs separated surfaces:

- Runtime profile: profile config, `SOUL.md`, gateway state, cron, logs, and live memory.
- Instructions: stable role, operating rules, safety boundaries, and source hierarchy.
- Apps and tools: connector access and custom MCPs for external systems.
- Skills: repeatable procedures, output formats, and local workflow knowledge.
- Files: durable reference material, examples, templates, and shared knowledge.
- Memory: personal or per-user continuity that should not be confused with public instructions.
- Operations: health checks, deploy runbooks, secret boundaries, and regression tests.

Hermes is now the primary runtime target for the first app. ChatGPT workspace agents, OpenClaw, and Midas remain evidence sources, not the default product surface.

## Source Priority

1. StaffAny Hermes Data Bot app packet under `apps/hermes-data-bot/`.
2. NurtureAny Sales Bot app packet under `apps/nurtureany-sales-bot/` for sales nurture behavior.
3. Hermes official repo/docs for runtime architecture patterns.
4. Official ChatGPT/OpenAI docs for legacy ChatGPT workspace-agent behavior.
5. Official OpenClaw docs for OpenClaw design intent.
6. Midas for the research wiki and Karpathy-style ingestion process.
7. `openclaw-kaiyi` for Kai Yi's current local implementation patterns and gaps.

## Current Guardrails

- Do not promote one system's implementation detail as universal product truth.
- Keep evidence, synthesis, and decisions separate.
- Treat public web docs as citation sources, not content to copy wholesale.
- Do not ingest secrets, `.env` values, API keys, OAuth tokens, or raw private credentials.
- Keep `openclaw-kaiyi` memory content private and summarize structure unless the research question requires content-level inspection.
- Treat live Hermes profile changes as runtime drift until explicitly promoted into `apps/hermes-data-bot/`.

## Known Unknowns

- Which runtime learnings from `staffanydatabot` should be promoted into durable app sources.
- Whether Customer 360 should become a read-only customer-wiki source for Hermes Data Bot.
- Whether future apps should follow the same `apps/<app-slug>/` packet shape.
- Which team workflows should become first-class apps after Hermes Data Bot.
