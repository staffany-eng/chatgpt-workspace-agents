# OpenClaw Kaiyi Current Implementation

## Source Metadata

- Type: local implementation audit
- Source class: Kai Yi OpenClaw repo
- Source URL or path: `/Users/leekaiyi/workspace/openclaw-kaiyi`
- Date ingested: 2026-04-30
- Context: current local implementation evidence
- Default weight: 5
- Privacy: private local repo, no secrets copied

## Context Caveat

This source is authoritative for what Kai Yi has set up locally. It is not authoritative for OpenClaw product design when it differs from official docs.

## Evidence Used

- Raw record: [research/raw/openclaw-kaiyi/current-implementation.md](../../raw/openclaw-kaiyi/current-implementation.md)
- Generated file inventory: [research/raw/openclaw-kaiyi/file-inventory.md](../../raw/openclaw-kaiyi/file-inventory.md)

## What They Said

- `openclaw-kaiyi` splits coding-agent instructions, Claude shims, path-scoped rules, and runtime agent workspaces.
- Runtime workspaces use `AGENTS.md`, `SOUL.md`, `USER.md`, `TOOLS.md`, `HEARTBEAT.md`, `LESSONS.md`, `MEMORY.md`, and daily memory.
- `LESSONS.md` is used as safe operational knowledge, separate from personal/contextual `MEMORY.md`.
- Repo-local hooks share behavior across Claude and Codex for startup context, Bash audit, and verification-before-stop.
- Katalyst uses a structured lifecycle around plan, code, doctor, smoke, promotion, and rollback.
- The repo has a verification convention via `npm run verify`.

## Evidence Trace

- Claim: `openclaw-kaiyi` splits coding-agent instructions, Claude shims, path-scoped rules, and runtime agent workspaces. Evidence: The raw record summarizes root instruction surfaces. Source: `research/raw/openclaw-kaiyi/current-implementation.md:28`.
- Claim: Runtime workspaces use `AGENTS.md`, `SOUL.md`, `USER.md`, `TOOLS.md`, `HEARTBEAT.md`, `LESSONS.md`, `MEMORY.md`, and daily memory. Evidence: The raw inventory lists runtime files. Source: `research/raw/openclaw-kaiyi/current-implementation.md:22`.
- Claim: `LESSONS.md` is used as safe operational knowledge, separate from personal/contextual `MEMORY.md`. Evidence: The raw record describes the lessons/memory split. Source: `research/raw/openclaw-kaiyi/current-implementation.md:31`.
- Claim: Repo-local hooks share behavior across Claude and Codex for startup context, Bash audit, and verification-before-stop. Evidence: The raw record summarizes `.codex/hooks.json`, `.claude/settings.json`, and shared scripts. Source: `research/raw/openclaw-kaiyi/current-implementation.md:32`.
- Claim: Katalyst uses a structured lifecycle around plan, code, doctor, smoke, promotion, and rollback. Evidence: The raw record summarizes Katalyst feature docs and scripts. Source: `research/raw/openclaw-kaiyi/current-implementation.md:33`.
- Claim: The repo has a verification convention via `npm run verify`. Evidence: The raw record identifies `scripts/verify.sh`, workflow, and tests. Source: `research/raw/openclaw-kaiyi/current-implementation.md:38`.

## Learning Summary

- Kai Yi has already implemented a strong local version of OpenClaw's instruction and memory split.
- The repo goes beyond official docs with a lessons discipline and shared Claude/Codex hook scripts.
- Katalyst is the most important local pattern for safe iteration on agents: isolate, test, promote, rollback.
- Local practice should be audited against official docs rather than treated as the product baseline.

## Synthesis Gate

- Mode: autonomous_current_focus_synthesis
- Status: completed
- Focus source: official OpenClaw docs source note, `docs/product-compass.md`, `research/wiki/syntheses/openclaw-kaiyi-current-state-audit.md`
- Evidence weight check: weight 5 for current-state audit, weight 3 for general design claims outside Kai Yi's setup.
- Decision: promoted into current-state audit synthesis.

## Possible Agent Builder Relevance

- Agent-synthesized: Use `openclaw-kaiyi` as an implementation checklist for instruction surfaces, lessons, runtime memory, hooks, and verification.
- Agent-synthesized: Convert Katalyst's lifecycle into a ChatGPT workspace-agent iteration rubric.
- Do-not-promote: Do not assume repo-local hooks or shell scripts exist inside ChatGPT workspace agents.

## Follow-Up Questions

- Which `openclaw-kaiyi` lessons should become reusable ChatGPT workspace-agent skills?
- Should future work add a per-file deeper audit for Katalyst scripts?

