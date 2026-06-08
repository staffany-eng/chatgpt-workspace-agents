# Launchbot

Canonical Hermes app packet for the Launchbot Slack profile.

## Runtime Shape

- Runtime: Hermes Agent
- Profile: `launchbot` on `hermes-data-bot-poc` only; do not create or run a Mac-local `launchbot` profile.
- Surface: Slack mentions in `#launch-bot-testing`, configured project channels, and read-only product-commitment / KER lookup in `#all-product-questions`
- Source packet: this directory
- Live runtime state: `~/.hermes/profiles/launchbot/` on `hermes-data-bot-poc`
- Status: cloud-primary; release gate is green managed gateway health plus a bot-owned Slack smoke in `#launch-bot-testing`. Scheduled Pantheon refresh still requires VM GitHub SSH access.
- Pantheon source checkout: `~/.hermes/profiles/launchbot/source/pantheon`, refreshed from `git@github.com:staffany-eng/pantheon.git` branch `develop` after VM GitHub SSH access is authorized.
- Slack Socket Mode event subscriptions: `app_mention` and `message.channels`; OAuth scopes must include `app_mentions:read`, `channels:history`, `channels:read`, `channels:join`, and `chat:write`.
- Help article planning: cached Intercom article-shape profile plus metadata inventory first, then live Intercom only for affected search and pre-stage stale checks.
- Feature intake: guarded Slack thread to Jira Product Discovery KER preview/create in configured channels, with explicit confirmation before Jira mutation.
- Feature-intake monitor: no-agent poller for `#input-features-ux` (`CF8PK6V4J`) that posts one Launchbot-owned preview for likely KER intake candidates, then creates only after exact `create intake` in-thread.
- Weekly support watch: no-agent Thursday 09:00 SGT report-only scan of BigQuery-backed Intercom conversations plus optional WhatsApp support logs, deduped against `#team-cs-eng-duty`, EDT, and prior state, posting only new findings to `#all-bugs-production`.
- Product commitment check: read-only Slack thread to Jira KER/JPD lookup in configured channels, with explicit commitment evidence from reviewed Jira fields only.
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
| `runtime/update-app-from-repo.sh` | Schedules a detached repo pull + profile sync + gateway restart only when `origin/main` is ahead. |
| `runtime/apply-app-update.sh` | Worker used by the detached repo update unit. |
| `runtime/update-pantheon-repo.sh` | Daily Pantheon checkout refresher for code-grounded help article verification. |
| `runtime/monitor-feature-intake.py` | No-agent Slack channel monitor for guarded feature-intake previews and approvals. |
| `runtime/monitor-support-watch.py` | No-agent weekly support-watch runner that posts only new reports to `#all-bugs-production`. |
| `runtime/mcp/launchbot_ker_server.py` | Read-only Slack thread to Jira KER lookup tool. |
| `runtime/mcp/launchbot_ifi_server.py` | Preview-first HubSpot company to IFI feature request tracking tool, including BD-notes intake into the same IFI contract. |
| `runtime/mcp/launchbot_product_commitment_server.py` | Read-only Slack thread to Jira KER/JPD product commitment checker. |
| `runtime/mcp/launchbot_feature_intake_core.py` | Shared Slack/Jira feature-intake preview and create contract. |
| `runtime/mcp/launchbot_feature_intake_server.py` | Confirmed Slack thread to Jira Product Discovery KER intake tool. |
| `runtime/mcp/launchbot_support_watch_core.py` | Shared BigQuery support-source query, clustering, Slack/EDT dedupe, and Pantheon trace logic. |
| `runtime/mcp/launchbot_support_watch_server.py` | Read-only weekly support-watch preview tool. |
| `runtime/mcp/launchbot_help_article_server.py` | Draft-only registered Loom video-slot updater for existing help articles. |
| `skills/help-article-generator/` | Launchbot help-article drafting skill upgraded from the 2026-05-11 handoff. |
| `skills/help-article-generator/references/video-placement-registry.json` | Registry authority for help article video placement. |
| `skills/weekly-support-watch/SKILL.md` | Weekly support-watch operating contract and live-smoke checklist. |
| `skills/staffany-indonesia-payroll-tax-grimoire/` | Source-backed StaffAny Indonesia payroll-tax answer bundle. |
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
6. Set Jira env vars (`JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`) in the live profile `.env` before enabling KER lookup, IFI tracking, product commitment checks, or confirmed feature intake.
7. Copy `skills/help-article-generator/` into `~/.hermes/profiles/launchbot/skills/` when enabling article drafting and registered video-slot updates.
8. Copy `skills/staffany-indonesia-payroll-tax-grimoire/` into `~/.hermes/profiles/launchbot/skills/` when enabling Indonesia payroll-tax answers.
9. Copy runtime scripts into `~/.hermes/profiles/launchbot/scripts/`, including `launchbot-monitor-feature-intake.py` and `launchbot-monitor-support-watch.py`.
10. Copy `runtime/mcp/launchbot_ifi_server.py`, `runtime/mcp/launchbot_support_watch_server.py`, `runtime/mcp/launchbot_support_watch_core.py`, and `runtime/mcp/launchbot_help_article_server.py` into the live profile source tree before enabling the matching MCP servers.
11. Set `HUBSPOT_ACCESS_TOKEN` and `JIRA_IFI_HUBSPOT_COMPANY_ID_FIELD_ID=customfield_10881` before enabling IFI tracking. `HUBSPOT_PORTAL_ID` defaults to `4137076`.
12. Seed `~/.hermes/profiles/launchbot/source/pantheon` for code-grounded article verification and StaffAny Indonesia payroll-tax capability checks. Install the daily Pantheon updater cron only after the VM has GitHub SSH access to `staffany-eng/pantheon`.
13. Start the managed gateway and install the no-agent health check cron.
14. Install the feature-intake monitor cron only after Slack/Jira env is present and a dry-run against `CF8PK6V4J` succeeds:
    ```bash
    cp apps/launchbot/runtime/monitor-feature-intake.py ~/.hermes/profiles/launchbot/scripts/launchbot-monitor-feature-intake.py
    ~/.hermes/profiles/launchbot/scripts/launchbot-monitor-feature-intake.py --dry-run --channel CF8PK6V4J --since-minutes 30
    hermes -p launchbot cron create "* * * * *" \
      --name "launchbot feature intake monitor" \
      --script launchbot-monitor-feature-intake.py \
      --no-agent
    ```
15. Install the support-watch cron only after BigQuery/Jira/Slack env is present, `#all-bugs-production` resolves with the Launchbot bot token, Launchbot can join configured public channels with `channels:join`, and a dry-run succeeds. Public support-watch channels resolve by name with `channels:read`; use explicit channel IDs only for private channels:
    ```bash
    cp apps/launchbot/runtime/monitor-support-watch.py ~/.hermes/profiles/launchbot/scripts/launchbot-monitor-support-watch.py
    LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME=all-bugs-production \
      LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_NAMES=team-cs-eng-duty \
      ~/.hermes/profiles/launchbot/scripts/launchbot-monitor-support-watch.py --dry-run --max-tickets 20
    hermes -p launchbot cron create "0 1 * * 4" \
      --name "launchbot support watch" \
      --script launchbot-monitor-support-watch.py \
      --no-agent
    ```
16. Confirm no Mac-local `launchbot` profile or gateway exists before live Slack testing. Only the cloud Launchbot runtime should be connected to Slack, otherwise stale local profile state can answer first.
17. Treat the restore as verified only after the health check passes and the Slack smoke replies from Launchbot's bot identity in `#launch-bot-testing`.

Preferred deploy path:

```bash
npm run launchbot:deploy -- --apply --ref origin/main
```

The deploy script syncs the app packet into `~/.hermes/profiles/launchbot/source/launchbot`, copies every bundled skill into `~/.hermes/profiles/launchbot/skills/`, restarts `hermes-gateway-launchbot.service`, and runs live audit plus health checks. This prevents repo-only skill merges where Launchbot's live skill index stays stale.

Manual or bot-triggered app update path:

```bash
/home/leekaiyi/.hermes/profiles/launchbot/scripts/launchbot-update-app-from-repo.sh
```

It exits quickly with one of:
- `launchbot-app-update:no-change:<sha>` when the local checkout already matches `origin/main`
- `launchbot-app-update:scheduled:<from_sha>:<to_sha>:<unit>` when a detached user unit was created to pull, sync, restart, and health-check Launchbot
- `launchbot-app-update:error:<reason>` when the repo is dirty or the update flow is blocked

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

IFI tracking is a preview-first customer-demand lane. Preview APQ or Slack requests with `preview_ifi_feature_request_tracking`; preview BD-notes feature demand with `preview_ifi_feature_request_from_bd_note`. Both routes require a confirmed HubSpot company URL or numeric HubSpot Company ID before Jira writes. After exact `confirm IFI`, create/update IFI through `create_or_update_ifi_feature_request_tracking` or `create_or_update_ifi_feature_request_from_bd_note`; the MCP never mutates HubSpot or posts Slack.

Product commitment checks are read-only. Use `check_product_commitment_from_slack_thread` for prompts like `check product commitment for this thread` or `can u check if this is committed on roadmap`. The commitment lane is allowed in `#all-product-questions` (`C01RZ7SHC8K`) through `LAUNCHBOT_PRODUCT_COMMITMENT_ALLOWED_CHANNEL_IDS`; keep it separate from feature intake. Only Jira `fixVersions` and reviewed field IDs from `LAUNCHBOT_PRODUCT_COMMITMENT_FIELD_IDS` count as commitment evidence. If no reviewed evidence is present, Launchbot must say no committed Jira roadmap evidence was found and must not infer an ETA or create intake.

Indonesia payroll-tax answers are skill-backed. Route PPh21, PPh26, TER, PTKP, DTP, SPT Masa PPh 21/26, e-Bupot 21/26, bukti potong, Formulir 1721-A1 / BPA1, BPMP, BP21, BP26, and StaffAny Indonesia payroll-tax settings to `skills/staffany-indonesia-payroll-tax-grimoire/SKILL.md`. Current laws, rates, forms, deadlines, and regulator platform changes must use the bundled regulation update workflow at `skills/staffany-indonesia-payroll-tax-grimoire/skills/indonesia-tax-knowledge-updater/SKILL.md` before final answers; if the knowledge bank is updated, run `skills/indonesia-tax-knowledge-updater/scripts/validate_knowledge_bank.rb` from the grimoire root. StaffAny product behavior claims still need Pantheon code, model, seeded-reference, or verified read-only query evidence.

For `#input-features-ux`, the no-agent monitor watches top-level messages and thread replies with the Launchbot bot token. It keeps normal Launchbot replies mention-gated, stores only safe summaries and source pointers, posts one `Launchbot automation:` preview for high-confidence candidates, and creates a KER Idea only after exact `create intake` / `create KER intake` in the same thread.

Weekly support watch is report-only. Preview with `preview_weekly_support_watch_report`; scheduled runs use `runtime/monitor-support-watch.py` on cron `0 1 * * 4` UTC. It queries BigQuery-backed Intercom conversations and optional WhatsApp support logs, clusters repeated or severe production-bug signals, traces Pantheon evidence heuristically, dedupes against `#team-cs-eng-duty`, EDT, and prior state, and posts only new findings to `#all-bugs-production` with `Launchbot automation:`. It must not create Jira/Linear tickets, tag engineers, assign owners, or persist raw support transcripts.
