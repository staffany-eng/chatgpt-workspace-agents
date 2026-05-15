# Launchbot

Canonical Hermes app packet for the Launchbot Slack profile.

## Runtime Shape

- Runtime: Hermes Agent
- Profile: `launchbot` on `hermes-data-bot-poc` only; do not create or run a Mac-local `launchbot` profile.
- Surface: Slack mentions in `#launch-bot-testing` and explicitly configured project channels
- Source packet: this directory
- Live runtime state: `~/.hermes/profiles/launchbot/` on `hermes-data-bot-poc`
- Status: cloud-primary; release gate is green managed gateway health plus a bot-owned Slack smoke in `#launch-bot-testing`. Scheduled Pantheon refresh still requires VM GitHub SSH access.
- Pantheon source checkout: `~/.hermes/profiles/launchbot/source/pantheon`, refreshed from `git@github.com:staffany-eng/pantheon.git` branch `develop` after VM GitHub SSH access is authorized.
- Slack Socket Mode event subscriptions: `app_mention` and `message.channels`; OAuth scopes must include `app_mentions:read`, `channels:history`, `channels:read`, and `chat:write`.
- Help article planning: cached Intercom article-shape profile plus metadata inventory first, then live Intercom only for affected search and pre-stage stale checks.
- Feature intake: guarded Slack thread to Jira Product Discovery KER preview/create in configured channels, with explicit confirmation before Jira mutation.
- Publish surface: Intercom draft/staging output only; public publish stays manual in Intercom.

## Packet Contents

| Path | Purpose |
| --- | --- |
| `TODO.md` | Open operational follow-ups for Launchbot. |
| `profile/SOUL.md` | Source-controlled profile instruction. |
| `profile/config.template.yaml` | Non-secret profile config template. |
| `runtime/slack.md` | Slack channel and identity rules. |
| `runtime/health-checks.md` | Expected health checks and cron pattern. |
| `runtime/check-health.sh` | Silent no-agent health check. |
| `runtime/audit-live-profile.sh` | Live profile drift audit. |
| `runtime/update-pantheon-repo.sh` | Daily Pantheon checkout refresher for code-grounded help article verification. |
| `runtime/mcp/launchbot_ker_server.py` | Read-only Slack thread to Jira KER lookup tool. |
| `runtime/mcp/launchbot_feature_intake_server.py` | Confirmed Slack thread to Jira Product Discovery KER intake tool. |
| `runtime/mcp/launchbot_help_article_server.py` | Draft-only registered Loom video-slot updater for existing help articles. |
| `skills/help-article-generator/` | Launchbot help-article drafting skill upgraded from the 2026-05-11 handoff. |
| `skills/help-article-generator/references/video-placement-registry.json` | Registry authority for help article video placement. |
| `runtime/launch-workflow.md` | Help-article, Google Docs review, Slack approval, and Intercom draft workflow contract. |
| `runtime/launchbot_e2e.py` | Minimal VM-safe handoff runner when the external source checkout is absent. |
| `runtime/intercom-format-gate.mjs` | Pantheon evidence scan/check, Intercom search, cached article-shape planning, curated format-profile pull, and pre-publish format check CLI. |
| `tests/launch-workflow-regression-cases.md` | Manual/eval regression scenarios for the launch workflow. |
| `tests/prompt-evals.json` | Machine-readable static, tool-trace, answer-contract, and live-smoke prompt eval specs. |

## Restore Order

1. Install Hermes and verify `hermes doctor`.
2. Create or select the `launchbot` profile on `hermes-data-bot-poc` only. If a Mac-local `~/.hermes/profiles/launchbot` exists, archive/delete it before live Slack testing.
3. Copy `profile/SOUL.md` to `~/.hermes/profiles/launchbot/SOUL.md`.
4. Use `profile/config.template.yaml` as the non-secret config guide.
5. Set Slack and model secrets from the approved secret store only.
6. Set Jira env vars (`JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`) in the live profile `.env` before enabling KER lookup or confirmed feature intake.
7. Copy `skills/help-article-generator/` into `~/.hermes/profiles/launchbot/skills/` when enabling article drafting and registered video-slot updates.
8. Copy runtime scripts into `~/.hermes/profiles/launchbot/scripts/`.
9. Copy `runtime/mcp/launchbot_help_article_server.py` into the live profile source tree before enabling the `launchbot_help_article` MCP server.
10. Seed `~/.hermes/profiles/launchbot/source/pantheon` for code-grounded article verification. Install the daily Pantheon updater cron only after the VM has GitHub SSH access to `staffany-eng/pantheon`.
11. Start the managed gateway and install the no-agent health check cron.
12. Confirm no Mac-local `launchbot` profile or gateway exists before live Slack testing. Only the cloud Launchbot runtime should be connected to Slack, otherwise stale local profile state can answer first.
13. Treat the restore as verified only after the health check passes and the Slack smoke replies from Launchbot's bot identity in `#launch-bot-testing`.

## Launch Workflow Skill

Launchbot is the app. The Launch Superpower handoff is represented here as a Launchbot skill and workflow capability, not as a separate app identity.

The handoff evidence remains under `research/raw/launch-superpower-bot/2026-05-11-handoff/`, with the maintained source note at `research/wiki/sources/launch-superpower-bot-handoff.md`.

Run the VM-safe handoff path from the repo root after the required runtime secrets are available:

```bash
python3 apps/launchbot/runtime/launchbot_e2e.py --issue KER-1742 --version v006
```

If a review message already exists and a human reviewer has reacted with ✅, process only the approval gate:

```bash
python3 apps/launchbot/runtime/launchbot_e2e.py --issue KER-1742 --version v006 --approval-only
```

For local commands that need live Launchbot credentials, use Secret Manager through the wrapper instead of copying values into this worktree:

```bash
node scripts/launchbot-with-secrets.mjs --check --only intercom
node scripts/launchbot-with-secrets.mjs --only intercom -- node apps/launchbot/runtime/intercom-format-gate.mjs intercom:affected --topic "ClubAny brands and perks"
```

Core help article planning and gate commands:

```bash
npm run help-article:plan -- --topic "<topic>"
npm run help-article:pantheon-scan -- --topic "<topic>" --app gryphon,kraken
npm run help-article:evidence-check -- --draft <draft.md> --evidence <pantheon-evidence.json> --title "<article title>"
npm run help-article:format-check -- --draft <draft.md> --title "<article title>"
npm run intercom:affected -- --topic "<topic>"
npm run intercom:stage-update -- --article-id <article_id> --draft <draft.md> --evidence <pantheon-evidence.json> --title "<article title>"
```

Video-only help article updates are part of the existing Update lane. They are registry-only and draft-only: preview with `preview_help_article_video_update`, wait for `draft it`, then create the Intercom draft with `create_help_article_video_update_draft`. No public publish or article text rewrite is exposed.

Feature intake is a guarded Jira Product Discovery lane. Preview with `preview_feature_intake_from_slack_thread`, wait for `create intake`, then create one KER idea with `create_feature_intake_from_slack_thread`. The Slack permalink is written to `Slack / PRD` and used as the duplicate key; the MCP never posts Slack messages, comments on Jira, transitions issues, or assigns owners.
