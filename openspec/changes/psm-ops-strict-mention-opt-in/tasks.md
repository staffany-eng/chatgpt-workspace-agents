# Tasks: PSM Ops Strict Mention Opt-In

- [x] Create OpenSpec proposal, design, tasks, and spec files manually because the local `openspec` binary is unavailable.
- [x] Read SCHE-19906, linked KER context, Obsidian P0.3 notes, and the new Slack feedback thread.
- [x] Set `slack.strict_mention: true` in the PSM Ops config template and manifest.
- [x] Update SOUL, skill, runtime Slack docs, health docs, README, and profile registry.
- [x] Add regression/eval coverage for untagged same-thread replies after a bot response.
- [x] Add verifier and health-check guards for strict mention drift.
- [ ] Run `openspec validate psm-ops-strict-mention-opt-in --strict` when the `openspec` CLI is available.
- [x] Run `pnpm psm-ops-bot:verify`.
- [x] Run `pnpm psm-ops-bot:prompt-evals`.
- [ ] Deploy to `hermes-psm-ops-bot-poc` and run live health/audit checks.
