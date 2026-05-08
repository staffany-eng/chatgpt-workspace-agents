# Agent Builder Agent Guide

This repo is now app-first for StaffAny Hermes Data Bot, with the earlier ChatGPT workspace-agent research retained as evidence.

## Before Decisions

Read these first:

- `README.md`
- `docs/product-compass.md`
- `docs/documentation-guide.md`
- `research/wiki/index.md`
- `research/wiki/weights.md`

For Hermes Data Bot app work, also read:

- `apps/hermes-data-bot/README.md`
- `apps/hermes-data-bot/AGENTS.md`
- `apps/hermes-data-bot/app.manifest.json`

## Research Workflow

- Preserve source evidence under `research/raw/`.
- Maintain readable source notes under `research/wiki/sources/`.
- Put cross-source learning under `research/wiki/syntheses/`.
- Promote stable guidance to `research/wiki/decisions.md` before treating it as product truth.
- Official OpenClaw docs are primary for OpenClaw design intent.
- `openclaw-kaiyi` is secondary implementation evidence for what Kai Yi already set up.

## Verification

For Hermes Data Bot packet changes:

```bash
npm run hermes-data-bot:verify
```

Run the audit before calling an ingest done:

```bash
bun research/tools/audit-agent-ingest.ts --wiki <source-note.md> --fail-under 10
```

For source inventories:

```bash
bun research/tools/build-source-inventories.ts
```
