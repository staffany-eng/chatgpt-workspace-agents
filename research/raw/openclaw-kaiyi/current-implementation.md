# openclaw-kaiyi Current Implementation Raw Record

## Source Metadata

- Type: local implementation audit
- Source class: Kai Yi OpenClaw repo
- Source path: `/Users/leekaiyi/workspace/openclaw-kaiyi`
- Date checked: 2026-04-30
- Privacy: private local repo; no `.env`, credentials, auth profiles, or session transcripts copied

## Raw Content Policy

This record summarizes structure and selected non-secret implementation patterns. It intentionally excludes `.env`, `.env.local`, `~/.openclaw`, credentials, and session transcripts.

## Source Inventory

- Root instructions: `AGENTS.md`, `CLAUDE.md`, `.claude/rules/*.md`
- Codex/Claude hooks: `.codex/hooks.json`, `.claude/settings.json`, `scripts/agent-hooks/*.py`
- Feature specs: `docs/features/*.md`
- Runtime workspaces: `workspace-kaios/`, `workspace-katalyst/`, `workspace-kea/`
- Runtime files: `AGENTS.md`, `SOUL.md`, `USER.md`, `TOOLS.md`, `HEARTBEAT.md`, `LESSONS.md`, `MEMORY.md`, `memory/*.md`
- OpenClaw extensions: `workspace-*/.openclaw/extensions/*`
- Katalyst scripts: `scripts/katalyst-*.sh`
- Verification: `scripts/verify.sh`, `.github/workflows/verify.yml`, `tests/*.test.ts`

## Evidence Extracts

- Root `AGENTS.md` splits instruction surfaces: root `AGENTS.md` for shared coding-agent guidance, `CLAUDE.md` as thin Claude shim, `.claude/rules/` for Claude/path-scoped rules, and `workspace-*/AGENTS.md` for runtime agent behavior.
- Root `AGENTS.md` treats `~/.openclaw/openclaw.json` as live gateway config and warns that remote gateway mode makes the remote host config authoritative.
- Workspace `AGENTS.md` files tell runtime agents to read `SOUL.md`, `USER.md`, `LESSONS.md`, recent daily memory, and `MEMORY.md` only in main private sessions.
- `LESSONS.md` is used as safe operational knowledge, separate from personal/contextual `MEMORY.md`.
- Repo-local hooks share scripts across Claude and Codex for session context, Bash audit logging, and a stop hook that requires verification evidence once.
- Katalyst feature docs describe a run lifecycle: request, plan, code, doctor, smoke test, promote, rollback.
- Katalyst uses isolated worktrees and manifest-backed release/rollback concepts for safer bot changes.
- Kaios docs and runtime files separate heartbeat behavior, task capture, Google Tasks commitment source of truth, and local `memory/todo.md` mirror.
- Plugin lessons record that plugin paths must point to self-contained plugin directories with required manifest fields, including `configSchema`.
- Verification convention is `npm run verify`, backed by Node tests and shell syntax checks.

## First-Pass Learning

`openclaw-kaiyi` already implements several mature patterns from the OpenClaw docs: instruction-surface separation, runtime workspace files, lessons vs memory split, heartbeat/cron distinction, repo-local hooks, and verification loops. Its strongest local additions are Katalyst's structured run lifecycle and the hard requirement to record durable lessons.

