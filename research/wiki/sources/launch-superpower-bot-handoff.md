# Launch Superpower Bot Handoff

## Source Metadata

- Type: user-supplied workflow handoff and skill package
- Source class: private StaffAny launch workflow handoff
- Source path: `research/raw/launch-superpower-bot/2026-05-11-handoff/`
- Date ingested: 2026-05-13
- Context: Launch Superpower Bot help-article, Google Docs approval, Slack approval, and Intercom draft workflow
- Default weight: 3 for workflow and formatting guidance until the external source repo is checked; 4 for the specific handoff's recorded test outputs
- Privacy: private internal operational handoff; no real secret values copied into the maintained note

## Context Caveat

This note summarizes a teammate handoff, not a source-code audit. Current repo modeling treats Launchbot as the app and this handoff as a Launchbot skill/workflow input. Use it as implementation guidance only after checking the external `vk-super-productivity/launch-superpower-bot` source repo.

## Evidence Used

- Raw manifest: [Launch Superpower Bot Handoff Source Manifest](../../raw/launch-superpower-bot/2026-05-11-handoff/source-manifest.md)

## What They Said

- Launch Superpower Bot converts a shipped Jira feature into launch assets across help article drafting, Google Docs review, Slack approval, and Intercom draft creation.
- The current clean test case is `KER-1742` / Club Blue / ClubAny brands, perks, and redemptions at version `v005`.
- Step 1, Step 2, and Step 3 have working outputs recorded in the handoff, while Step 4 launch derivatives are still planned work.
- The reusable help-article generator should prevent raw HTML, repeated titles, visible divider lines, and internal appendix content from entering publishable articles.
- ClubAny brand/perk management should prefer one combined management article with `Managing Brands`, `Managing Perks`, and `FAQ`.
- Runtime credentials are supplied through environment names only and must come from the proper secure sharing path.
- Known next gaps are ClubAny planning, real Word numbering, screenshot handling, visual DOCX QA, and Step 4 derivatives.

## Evidence Trace

- Claim: Launch Superpower Bot converts shipped Jira features into launch assets across the first three workflow steps. Evidence: the manifest records Step 1 help article drafting, Step 2 Google Docs and Slack review, Step 3 Intercom draft creation, and Step 4 as planned work. Source:
  `research/raw/launch-superpower-bot/2026-05-11-handoff/source-manifest.md:34`.
- Claim: The clean test case is KER-1742 / ClubAny / v005. Evidence: the manifest records the Jira issue, feature name, and latest clean test version. Source: `research/raw/launch-superpower-bot/2026-05-11-handoff/source-manifest.md:35`.
- Claim: Step 1, Step 2, and Step 3 have working outputs, while Step 4 remains planned. Evidence: the manifest records generated article slugs, Google Docs and Slack review outputs, Intercom draft links, and the Step 4 gap. Source: `research/raw/launch-superpower-bot/2026-05-11-handoff/source-manifest.md:36`.
- Claim: The help-article generator should block raw HTML, repeated titles, visible divider lines, and internal appendix content. Evidence: the manifest records the Step 1 prompt hardening and skill package purpose. Source: `research/raw/launch-superpower-bot/2026-05-11-handoff/source-manifest.md:38`.
- Claim: ClubAny brand/perk management should prefer one combined management article. Evidence: the manifest records Vanessa's target format with Managing Brands, Managing Perks, FAQ, object model, and visibility rule. Source: `research/raw/launch-superpower-bot/2026-05-11-handoff/source-manifest.md:42`.
- Claim: Runtime credentials must stay out of the repo. Evidence: the manifest records environment-variable configuration and the secure sharing path requirement. Source: `research/raw/launch-superpower-bot/2026-05-11-handoff/source-manifest.md:41`.
- Claim: Remaining gaps include ClubAny planning, real Word numbering, screenshots, visual DOCX QA, and Step 4. Evidence: the manifest records the known remaining gaps. Source: `research/raw/launch-superpower-bot/2026-05-11-handoff/source-manifest.md:43`.

## Learning Summary

- Launchbot should be represented as the app packet. The Launch Superpower handoff should be folded into Launchbot as a help-article launch workflow skill, not treated as a second app identity.
- The reusable help-article generator belongs in the app packet as a skill because it captures repeatable drafting, formatting, and internal-note boundaries.
- Workflow evidence should stay split from durable instructions: the raw handoff is evidence, while `apps/launchbot/` carries the reviewed runtime, skill, and workflow contract.
- The strongest immediate product upgrade is better help-article quality control before Google Docs and Intercom promotion.
- Step 4 should stay marked as planned until source code and regression evidence exist.

## Synthesis Gate

- Mode: autonomous_current_focus_synthesis
- Status: completed
- Focus source: `docs/product-compass.md`, `docs/documentation-guide.md`, `research/wiki/weights.md`
- Evidence weight check: weight 3 for user-supplied workflow guidance until the external source repo is checked; weight 4 for the specific recorded `v005` test outputs.
- Result: fold the launch workflow into the Launchbot app packet and verifier, while keeping code-level runtime changes blocked on the external source checkout.

## Possible Agent Builder Relevance

- User-supplied correction: Launchbot is the main bot; the Launch Superpower handoff should be a skill/workflow inside `apps/launchbot/`.
- Agent-synthesized: Preserve the handoff and extracted skill package under `research/raw/` and keep the maintained note under `research/wiki/sources/`.
- Agent-synthesized: Reuse the handoff-upgraded help-article skill as the packet skill and override older help-article formatting rules where they conflict.
- Do-not-promote: Do not claim Step 4, screenshot automation, or real Word numbering are shipped until the external source code is updated and verified.

## Follow-Up Questions

- Where should the actual `vk-super-productivity/launch-superpower-bot` source repo be mounted for code-level Step 1, Step 2, Step 3, and Step 4 upgrades?
