# Hermes Test Channels

Use these channels for live Slack smoke tests and runtime checks.

| Bot | Hermes profile | Slack channel | Channel ID | Notes |
| --- | --- | --- | --- | --- |
| Da Ta Hermz | `staffanydatabot` | `#da-ta-hermz-testing` | `C0AU19E6T0C` | StaffAny data, BigQuery, registry, release-feature, and metric smoke tests. |
| NurtureAny | `nurtureanysalesbot` on `nurtureany-sales-bot-prod` | `#nurtureany-testing` | `C0B2UGK4DB6` | Sales nurture, HubSpot, manager, Eazybe-preview, event, and CRO smoke tests. |
| PS WEE / PSM Ops Bot | `psmopsbot` | `#ps-weeman-bot-test` | `C0B2VT50YT1` | PSM Ops, Jira PCO, Customer 360, central ops audit, adoption digest, and public/open-channel smoke tests. |
| Launchbot | `launchbot` | `#launch-bot-testing` | `C0B32M34J3W` | Launch/deploy ops smoke tests. Experimental until health cron is green. |

`PS WEE`, `PS Wee Manager`, and `PSM Manager Ops Bot` are PSM Ops workflows. Test them with `psmopsbot` in `#ps-weeman-bot-test` (`C0B2VT50YT1`). Sales-manager and manager-chase tests remain NurtureAny workflows in `#nurtureany-testing` (`C0B2UGK4DB6`).

Do not use these NurtureAny event channels for live automation until the bot is invited and membership is verified:

| Channel | Channel ID | Current state |
| --- | --- | --- |
| `#team-rev-community-sg` | `C06CD9B6LDU` | Bot token can see channel info but is not a member. |
| `#team-rev-community-my` | `C06V8DS1B7B` | Bot token can see channel info but is not a member. |

Slack runtime inspection should use the relevant bot token from that profile. Do not use Kai Yi's user token or the Slack connector for bot/runtime checks when the bot token exists.
