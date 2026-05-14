# PSM Ops Release Watch

## Purpose

This synthesis turns the `KER-2109` release-watch work into a reusable PSM Ops pattern. Use it when a PCO customer-follow-up task is blocked by engineering shipment and the shipped signal must come from Jira rather than Slack.

## Evidence Used

- [PSM Ops PCO Release Watch](../sources/psm-ops-pco-release-watch.md) - weight 4 for current PSM Ops behavior.
- [StaffAny Hermes Data Bot POC](../sources/staffany-hermes-data-bot-poc.md) - weight 4 for app-packet and runtime-drift handling.
- [Midas Karpathy Research Process](../sources/midas-research-process.md) - weight 5 for raw/source/synthesis/decision workflow.

## Stable Pattern

- PCO owns PS/customer follow-up, status, comments, source links, and due-date reminders.
- KER provides product context and roadmap context, but should not by itself prove customer follow-up is ready.
- SCHE shipment tickets carry the release signal when they receive a released `fixVersion`.
- Jira issue links are the durable relationship between a PCO and the engineering issues it is blocked by.
- Link the PCO to the KER issue, the SCHE parent/container, and the confirmed SCHE child shipment tickets once engineering identifies them.
- Use the standard Jira `Blocks` relationship so the PCO reads as blocked by engineering work; use `Relates` only if `Blocks` is unavailable.

## Runtime Bootstrap Rule

Karpathy-style wiki ingest is not enough for runtime behavior. The distilled behavior must be promoted into the app packet that the bot actually reads:

- PS Wee skill reference for routing and tool choice.
- Jira field contract for issue-link constraints.
- Runtime Jira docs for release-watch automation guidance.
- SOUL prompt only for a short routing rule.
- MCP and tests when the bot needs a new mutation capability.

Live Hermes profile state remains drift until the source packet is synced and `audit-live-profile.sh` passes.

## Automation Shape

For a concrete PCO release watch, Jira Automation should:

- run on a daily schedule around the PS working day;
- look up linked `SCHE` issues where `statusCategory = Done` and `fixVersion in releasedVersions()`;
- only act while the PCO is still waiting internally;
- add an internal comment with released linked SCHE tickets and fixVersions;
- move the PCO back to PS attention;
- set Jira `duedate` to today so existing PS Wee reminders surface it.

Release Checklist and Slack release channels are useful for human sanity checks, but should not be the primary automation trigger.

## Implementation Implications

- Add PCO-to-engineering issue-link tools with project-key allowlists rather than generic Jira issue-link mutation.
- Regression cases must cover successful KER/SCHE links and rejected non-PCO or non-engineering issue keys.
- Avoid adding labels like `pco-track-ker-2109` when proper Jira issue links can model the relationship.
- Avoid separate local reminder state; use the existing PCO due-date reminder path.

## Open Questions

- Should PSM Ops add a read-only `check_pco_release_watch` tool that summarizes linked SCHE tickets and released fixVersions?
- Should Jira Automation be configured as one global rule for all linked release-watch PCOs, or as per-ticket rules until the pattern repeats?
