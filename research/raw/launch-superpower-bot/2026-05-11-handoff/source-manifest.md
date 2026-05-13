# Launch Superpower Bot Handoff Source Manifest

## Source Metadata

- Type: user-supplied handoff package
- Source class: private StaffAny launch workflow handoff
- Source path: `/Users/leekaiyi/Downloads/HANDOFF (1).md`
- Source path: `/Users/leekaiyi/Downloads/help-article-generator-skill-handoff (1).zip`
- Date checked: 2026-05-13
- Date ingested: 2026-05-13
- Handoff last updated: 2026-05-11
- Handoff SHA-256: `103993db42687d54c6a2b375b0a8d5dcbe65c7e57e521f1fded4a582788a934d`
- Skill zip SHA-256: `1f13a6dbb33a282569b8ba3832baf5512fa03c799ed6289b8d3bb0b2a5f3e840`

## Raw Content Policy

The full handoff markdown and extracted skill package are preserved because they are the source evidence for rebuilding the Launch Superpower Bot packet. The handoff names required environment variables and uses redacted Slack token examples only; no real secret values, OAuth credentials, service-account JSON, raw Slack transcript, or private customer data were copied into this manifest.

## Source Inventory

| Path | Bytes | SHA-256 | Purpose |
| --- | ---: | --- | --- |
| `handoff.md` | 10786 | `103993db42687d54c6a2b375b0a8d5dcbe65c7e57e521f1fded4a582788a934d` | Workflow handoff, test outputs, env names, rerun notes, gaps |
| `extracted-skill/help-article-generator/SKILL.md` | 6512 | `579f8ddc9b1098a4d9b12900c21bd8f6c0b208c226e2f563ac32d326351af376` | Upgraded help-article generator skill instructions |
| `extracted-skill/help-article-generator/references/help-article-skeleton.md` | 990 | `12d50137387c06b9af930590468b4d58c50e6bbce2de01c64fa01f825a101950` | Review-ready article skeleton, normalized to remove Markdown trailing whitespace |
| `extracted-skill/help-article-generator/README.md` | 771 | `c25c7687a0724285104d4dd31c24391ff9014574f3d99eaf58ab07df01056da9` | Original sharing note for the skill folder |

## Evidence Extracts

- The Launch Superpower workflow turns a shipped Jira feature into launch assets: Step 1 drafts help articles from code-grounded evidence, Step 2 promotes drafts to Google Docs and Slack review, Step 3 creates Intercom draft articles from approval reactions, and Step 4 is still launch-derivative work.
- The latest clean test feature is `KER-1742` / Club Blue / ClubAny brands, perks, and redemptions, with `v005` as the latest clean test version.
- Step 1 generated two `v005` articles: `owner-setup` for creating and managing ClubAny brands and perks, and `staff-redemption` for discovering and redeeming ClubAny perks.
- Step 2 produced separate Google Docs and Slack review messages for the two articles; Step 3 produced separate Intercom draft article links for both.
- Step 1 changes tightened the drafting prompt against raw HTML, repeated titles, visible divider lines, and internal appendix content, and added ClubAny guidance to use `Product: StaffAny`.
- Step 2 changes upgraded single-article manifests into structured article records and tracked multiple Google Docs separately.
- Step 3 changes used Slack approval reactions, ignored unauthorized reviewers, posted bot-owned progress replies, accepted Intercom draft responses without returned URLs, and normalized Google Docs HTML for Intercom.
- Required integration configuration is environment-variable based for Slack, Google Docs export, and Intercom draft creation; the handoff explicitly says secret values must come through a proper secure sharing path.
- Vanessa's target format prefers one combined ClubAny management article with `Managing Brands`, `Managing Perks`, and `FAQ`, plus the brand/perk object model and active-brand visibility note.
- Known remaining gaps are stronger ClubAny content planning, real Word numbering in DOCX output, screenshot capture or placeholders, visual DOCX render QA, and Step 4 launch derivatives.
