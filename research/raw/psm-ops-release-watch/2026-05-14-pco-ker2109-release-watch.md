# PSM Ops PCO Release Watch For KER-2109 Raw Record

## Source Metadata

- Type: internal operational workflow and implementation evidence
- Source class: StaffAny PSM Ops release-watch workflow
- Source path: current Codex session plus local source packet changes in `apps/psm-ops-bot/`
- Date checked: 2026-05-14
- Context: PCO customer-follow-up tracking for `KER-2109` / Data-blocking PG and related `SCHE` shipment work
- Default weight: 4 for the current PSM Ops workflow; 3 when generalized outside PCO/JSM release-watch work
- Privacy: private internal operational note; no secrets, raw Slack transcript, raw Jira comments, raw Jira descriptions, or customer source packs copied

## Raw Content Policy

- Preserve only concise operational facts, safe issue keys, safe public-internal links, and source-packet file paths.
- Do not copy Slack thread bodies, Jira internal comment bodies beyond approved summary text, Jira descriptions, credentials, tokens, `.env` values, or bulk issue exports.
- Treat live Jira and Slack actions as point-in-time verification evidence, not permanent release-state truth.

## Source Inventory

- Source Slack thread permalink: `https://staffany.slack.com/archives/C0AJAUNCEL8/p1778742168171509?thread_ts=1778123999.615759&cid=C0AJAUNCEL8`
- Engineering context issue: `https://staffany.atlassian.net/browse/KER-2109`
- Engineering shipment parent/container: `https://staffany.atlassian.net/browse/SCHE-19631`
- Release checklist: `https://docs.google.com/spreadsheets/d/1qToYF_FisrlBBQFk83-IVHGTRowfBoN1i_uu1qGJLSI/edit?gid=85120961#gid=85120961`
- PS follow-up tracker created during implementation: `https://staffany.atlassian.net/browse/PCO-156`
- Source-packet implementation files: `apps/psm-ops-bot/runtime/mcp/psm_jira_server.py`, `apps/psm-ops-bot/skills/psm-ops-bot/SKILL.md`, `apps/psm-ops-bot/runtime/jira.md`

## Evidence Extracts

- User intent: track the customer-facing follow-up in PCO while keeping `KER-2109` as product/engineering context and avoiding duplicate PCO tickets.
- Release-truth finding: the Release Checklist is version-level release-run tracking; it does not independently map `KER-2109` or `SCHE` child tickets to shipment.
- Jira-truth finding: `fixVersion` belongs on actual shipment tickets when engineering updates it; parent KER or parent/container SCHE should not be treated as sufficient shipment proof.
- Operating split: PCO is the PS/customer task source of truth; KER/SCHE are engineering source of truth; Jira issue links are the durable relationship between them.
- Link strategy: link the PCO directly to `KER-2109`, `SCHE-19631`, and confirmed actual child `SCHE-*` shipment tickets once engineering identifies them.
- Link type strategy: default to Jira `Blocks` so the PCO reads as blocked by the engineering issue; use `Relates` only if the Jira site lacks the standard Blocks link type.
- Automation strategy: scheduled Jira Automation should look up linked `SCHE` issues where `statusCategory = Done` and `fixVersion in releasedVersions()`, then surface the PCO for PS review.
- Reminder strategy: PS Wee reminders should continue using Jira `duedate`; do not introduce separate reminder state for release watches.
- Runtime bootstrap: the research wiki preserves why this pattern exists, but the PS Wee source packet must hold the distilled runtime rule because the live bot does not automatically read the wiki.
- Bot capability guard: `link_pco_to_engineering_issue` is intentionally narrow; source must be `PCO-*`, target must be `KER-*` or `SCHE-*`, default link type is `Blocks`, and raw Jira content is not exposed.
- Implementation verification: local `test_psm_jira_server.py` passed 33 tests after adding link-tool cases.
- Packet verification: `scripts/verify-psm-ops-bot.mjs` passed after adding the new tool to manifest/config verification.
- Slack identity verification: `scripts/verify-slack-automation-identity.mjs` passed after Slack-facing packet changes.
- Live setup evidence: `PCO-156` was created, linked to `KER-2109` and `SCHE-19631`, moved to `Waiting Internal`, and announced by bot-owned PS Wee Manager in the original Slack thread.

## Implementation Boundary

- The reusable pattern is not tied to `KER-2109`; future PCO release watches should use the same PCO-to-KER/SCHE issue-link shape.
- `KER-2109` remains context, not the final shipped signal.
- `SCHE-19631` is useful context but direct child `SCHE-*` links are still needed once engineering confirms which tickets carry the actual release `fixVersion`.
- Slack and the Release Checklist can support human review, but automation should prefer Jira issue links and released `fixVersion`.
