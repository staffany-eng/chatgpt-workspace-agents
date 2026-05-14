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
| `skills/help-article-generator/` | Launchbot help-article drafting skill upgraded from the 2026-05-11 handoff. |
| `runtime/launch-workflow.md` | Help-article, Google Docs review, Slack approval, and Intercom draft workflow contract. |
| `runtime/launchbot_e2e.py` | Minimal VM-safe handoff runner when the external source checkout is absent. |
| `tests/launch-workflow-regression-cases.md` | Manual/eval regression scenarios for the launch workflow. |

## Restore Order

1. Install Hermes and verify `hermes doctor`.
2. Create or select the `launchbot` profile on `hermes-data-bot-poc` only. If a Mac-local `~/.hermes/profiles/launchbot` exists, archive/delete it before live Slack testing.
3. Copy `profile/SOUL.md` to `~/.hermes/profiles/launchbot/SOUL.md`.
4. Use `profile/config.template.yaml` as the non-secret config guide.
5. Set Slack and model secrets from the approved secret store only.
6. Set Jira read-only env vars (`JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`) in the live profile `.env` before enabling KER lookup.
7. Copy `skills/help-article-generator/` into `~/.hermes/profiles/launchbot/skills/` when enabling article drafting.
8. Copy runtime scripts into `~/.hermes/profiles/launchbot/scripts/`.
9. Seed `~/.hermes/profiles/launchbot/source/pantheon` for code-grounded article verification. Install the daily Pantheon updater cron only after the VM has GitHub SSH access to `staffany-eng/pantheon`.
10. Start the managed gateway and install the no-agent health check cron.
11. Confirm no Mac-local `launchbot` profile or gateway exists before live Slack testing. Only the cloud Launchbot runtime should be connected to Slack, otherwise stale local profile state can answer first.
12. Treat the restore as verified only after the health check passes and the Slack smoke replies from Launchbot's bot identity in `#launch-bot-testing`.

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
