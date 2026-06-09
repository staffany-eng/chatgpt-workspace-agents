# PSM Ops PCO Release Watch

## Source Metadata

- Type: internal operational workflow and implementation evidence
- Source class: StaffAny PSM Ops release-watch workflow
- Source URL or path: `research/raw/psm-ops-release-watch/2026-05-14-pco-ker2109-release-watch.md`
- Date ingested: 2026-05-14
- Context: PCO customer-follow-up tracking for `KER-2109`, `SCHE-19631`, and future confirmed `SCHE` shipment tickets
- Default weight: 4 for the current PSM Ops workflow; 3 when generalized outside PCO/JSM release-watch work
- Privacy: private internal operational note; no secrets, raw Slack transcript, raw Jira comments, raw Jira descriptions, or customer source packs copied

## Context Caveat

This note captures a PSM Ops release-watch pattern created around `KER-2109`.
The reusable learning is the operating split between PCO, KER, SCHE, Jira issue links, and released `fixVersion`.
It is not a generic StaffAny release-management rule unless the target workflow also uses PCO for customer follow-up and SCHE tickets for shipment.

## Evidence Used

- Raw record: [PSM Ops PCO Release Watch For KER-2109](../../raw/psm-ops-release-watch/2026-05-14-pco-ker2109-release-watch.md)

## What They Said

- PCO should own the PS/customer follow-up while `KER-2109` remains product/engineering context.
- The Release Checklist is release-version tracking and should not be treated as direct feature-shipment proof.
- Released `fixVersion` on actual SCHE shipment tickets is the durable engineering release signal.
- Jira issue links should connect the PCO to `KER-*`, the relevant parent/container `SCHE-*`, and confirmed child shipment `SCHE-*` tickets.
- The default issue-link relationship should make the PCO show as blocked by the engineering issue.
- PS Wee reminders should keep using Jira `duedate` instead of a separate release-watch reminder store.
- Karpathy/wiki ingest preserves the rationale, but PS Wee runtime behavior must be promoted into the Customer 360 source packet.
- The bot-side link capability should be narrow: source `PCO-*`, target `KER-*` or `SCHE-*`, no raw Jira content exposure.

## Evidence Trace

- Claim: PCO should own customer follow-up while KER remains context. Evidence: raw extract records the user intent to track customer follow-up in PCO while keeping `KER-2109` as product/engineering context. Source: `research/raw/psm-ops-release-watch/2026-05-14-pco-ker2109-release-watch.md:30`.
- Claim: The Release Checklist is supporting evidence, not direct shipment proof. Evidence: raw extract states the checklist is version-level release-run tracking and does not map `KER-2109` or child `SCHE` tickets to shipment. Source: `research/raw/psm-ops-release-watch/2026-05-14-pco-ker2109-release-watch.md:31`.
- Claim: Released `fixVersion` on shipment tickets is the engineering release signal. Evidence: raw extract says `fixVersion` belongs on actual shipment tickets and parent KER/container SCHE should not be sufficient shipment proof. Source: `research/raw/psm-ops-release-watch/2026-05-14-pco-ker2109-release-watch.md:32`.
- Claim: PCO, KER, and SCHE need issue links for the durable relationship. Evidence: raw extract says Jira issue links are the durable relationship between PS/customer task truth and engineering truth. Source: `research/raw/psm-ops-release-watch/2026-05-14-pco-ker2109-release-watch.md:33`.
- Claim: Direct SCHE child links are required once known. Evidence: raw extract says link the PCO directly to KER, SCHE parent, and confirmed actual child SCHE shipment tickets. Source: `research/raw/psm-ops-release-watch/2026-05-14-pco-ker2109-release-watch.md:34`.
- Claim: `Blocks` is the preferred link type. Evidence: raw extract says default to Jira `Blocks` so PCO reads as blocked by engineering, with `Relates` only as fallback. Source: `research/raw/psm-ops-release-watch/2026-05-14-pco-ker2109-release-watch.md:35`.
- Claim: PS Wee reminders should stay due-date based. Evidence: raw extract says reminders should continue using Jira `duedate` and should not introduce separate release-watch state. Source: `research/raw/psm-ops-release-watch/2026-05-14-pco-ker2109-release-watch.md:37`.
- Claim: Runtime bootstrap needs source-packet promotion, not just wiki storage. Evidence: raw extract states the wiki preserves rationale, while PS Wee source packet must hold the distilled runtime rule. Source: `research/raw/psm-ops-release-watch/2026-05-14-pco-ker2109-release-watch.md:38`.

## Learning Summary

- PSM Ops release watches need a two-layer bootstrap: research wiki for rationale and source packet promotion for runtime behavior.
- For customer follow-up blocked by engineering shipment, PCO should remain the PS task while KER/SCHE remain engineering context and release truth.
- The durable automation bridge is Jira issue links plus released `fixVersion` on linked SCHE shipment tickets.
- Release Checklist and Slack release channels can support human review, but they should not be primary automation truth for feature shipment.
- PS Wee should not add a parallel release-watch reminder database because Jira `duedate` already drives automatic reminders.
- The link tool must stay narrow and safe because cross-project Jira linking can create noisy or misleading relationships if left generic.

## Synthesis Gate

- Mode: autonomous_current_focus_synthesis
- Status: completed
- Focus source: `docs/product-compass.md`, `research/wiki/weights.md`, `apps/psm-ops-bot/AGENTS.md`, `research/wiki/syntheses/automation-heartbeat-cron-schedules.md`
- Evidence weight check: weight 4 for current PSM Ops behavior because it combines user intent, live Jira setup, and source-packet implementation; weight 3 outside PCO/JSM workflows.
- Promotion path: synthesize into a PSM Ops release-watch page, then promote distilled behavior into Customer 360 `apps/psm-ops-bot/` rather than making the runtime read the research wiki.

## Possible Agent Builder Relevance

- Agent-synthesized: Keep research wiki and runtime source packets separate; wiki explains why, app packet controls what the bot does.
- Agent-synthesized: Treat issue-link contracts as tool/API behavior, with strict project-key allowlists and regression cases.
- Agent-synthesized: Prefer existing Jira `duedate` reminder mechanics over new local reminder state when a PCO task already exists.
- Do-not-promote: Do not treat `KER-2109` or `SCHE-19631` as universal release truth; actual shipment tickets still need confirmation.

## Follow-Up Questions

- Should the PSM Ops packet eventually include a read-only release-watch query that lists linked SCHE tickets and their released `fixVersion` state?
- Should Jira Automation be configured globally for all PCO release-watch tickets, or only per-ticket until the pattern repeats?
