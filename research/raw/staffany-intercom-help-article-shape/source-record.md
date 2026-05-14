# StaffAny Intercom Help Article Shape Source Record

## Source Metadata

- Type: live Intercom API curated article-shape refresh
- Source class: private StaffAny Intercom workspace evidence
- Source path: `apps/launch-superpower-bot/skills/help-article-generator/references/article-planning-profile.json`
- Cache path: `.cache/launch-superpower-bot/intercom-article-shape-corpus/`
- Date checked: 2026-05-14
- Retrieval command: `node apps/launch-superpower-bot/runtime/intercom-format-gate.mjs help-article:shape-refresh`
- Default weight: 4 for article-shape/planning behavior; live target Intercom article still outranks this cached profile at staging time
- Privacy: private internal API-derived metadata; no token values, raw HTML, or full article bodies copied into this raw record

## Raw Content Policy

- Full Intercom API JSON and HTML bodies are intentionally stored only under the ignored `.cache/launch-superpower-bot/intercom-article-shape-corpus/` directory.
- The committed evidence is normalized only: article IDs, URLs, titles, updated timestamps, headings, tags, family classification, split rationale, and structural fingerprints.
- This record does not copy full article bodies, raw HTML, screenshots, access tokens, customer data, or unpublished draft content.
- Live Intercom remains the current article source of truth; this cached record is a planning profile that must be refreshed or stale-checked before staging.

## Source Inventory

- Shape profile generated at `2026-05-14T13:04:15.069Z` from 37 curated published Intercom articles across 10 article families.
- Aggregate profile counts: 10 families, 37 reference articles, 22 audience blocks, 13 guide outlines, and 18 FAQ sections.
- Inventory profile generated on 2026-05-14 from 328 Intercom articles across 7 API pages; 276 articles were published and 52 were drafts.
- Inventory quality labels counted 22 strong references, 235 affected-search-only articles, 69 deprecated-or-weak articles, and 2 articles needing human review.
- Inventory raw JSON and HTML were cached under `.cache/launch-superpower-bot/intercom-article-inventory/`; the committed `intercom-article-inventory.json` contains metadata and derived content signals only.
- Family `new_joiner_onboarding` uses article IDs `14481424`, `14460084`, and `14753121`; observed titles were `Onboarding New Hires`, `Creating and Managing New Joiner Form`, and `Submitting New Joiner Form`.
- Family `company_documents` uses article IDs `13722083`, `13722074`, `11755931`, `14779347`, and `14318367`; observed titles covered company document creation, acknowledgement, employee documents, generation, and document types.
- Family `clubany` uses article IDs `14083228` and `14083405`; observed titles were `Managing Brands and Perks on ClubAny` and `Redeeming ClubAny Perks`.
- Family `claims` uses article IDs `9550497`, `9550638`, `9550707`, `9550732`, and `9550576`; observed titles covered claim types, claim submissions, mobile submission, payroll claims, and approval cutoff dates.
- Family `hireany` uses article IDs `10866862`, `10900205`, and `11016372`; observed titles were customer, vendor/provider, and casual worker views.
- Family `leave` uses article IDs `14715267`, `3589845`, `3542111`, and `6015355`; observed titles covered leave calendar, web approval, leave application, and mobile approval.
- Family `timesheet` uses article IDs `4871108`, `3458034`, and `7146545`; observed titles were `Timesheet Lock`, `Web App: Timesheet`, and `FAQ: Timesheets`.
- Family `payroll_payments` uses article IDs `13867429`, `13867569`, `9344548`, `10090085`, `8790142`, and `8898655`; observed titles covered disbursement wallet, disbursement creation, payroll reports, IR8A, payroll employee profile setup, and DBS bank file upload.
- Family `scheduling` uses article IDs `15082227`, `3180018`, `5900189`, and `6014271`; observed titles covered schedule import, web schedule, web unscheduled-shift approval, and mobile unscheduled-shift approval.
- Family `permissions_access` uses article IDs `4865824` and `3728187`; observed titles were `Permission Groups` and `StaffAny User & Access Levels`.

## Evidence Extracts

- Source hierarchy encoded in the profile: live target Intercom article, Pantheon product behavior, cached Intercom planning synthesis, then Slack/Jira/PRD context.
- Live Intercom usage encoded in the profile and inventory path: inventory refresh, shape refresh, affected-article search, and pre-stage stale check.
- Safety rules encoded in the profile: cached profile is required before drafting, stale cached article shape blocks staging, raw HTML is not committed, write boundary is `read_stage_only`, and publish mode is `draft_only`.
- Split rule for New Joiner / Onboarding: split setup, onboarding review, and new-hire submission when HR and new hires perform different jobs.
- Split rule for Company Documents: split admin Web document management from employee Mobile acknowledgement/viewing.
- Split rule for ClubAny: keep brand/perk management together for Web owners, and split Mobile redemption for staff.
- Split rule for Claims: split claim setup, employee submission, approval management, payroll processing, and cutoff behavior.
- Split rule for HireAny: split by marketplace side when customer, provider, and casual worker workflows differ.
- Split rule for Leave: keep one combined article when the same manager workflow spans Web and Mobile; split approval/application flows when actor or platform changes.
- Split rule for Timesheet: update the existing lifecycle article when behavior belongs to the same owner payroll-control workflow.
- Split rule for Payroll / Payments: split by payroll operation when setup, disbursement, reports, statutory submission, and bank-file export have different workflows.
- Split rule for Scheduling: split manager Web scheduling from employee Mobile requests when the acting user and surface differ.
- Split rule for Permissions / Access: prefer updating the canonical access article unless the change introduces a separate setup workflow.
- Live planning smoke on 2026-05-14 for topic `ClubAny brands and perks` selected the `clubany` family, recommended mode `mixed`, and returned only `Managing Brands and Perks on ClubAny` plus `Redeeming ClubAny Perks` as recommended article targets.
- The live planning smoke returned required Pantheon evidence of `kraken` plus `gryphon` for the Web ClubAny management article, and `kraken` plus `pixie` for the Mobile ClubAny redemption article.
- Inventory-backed planning smoke on 2026-05-14 for topic `ClubAny brands and perks` used `intercom-article-inventory.json` for affected-article lookup and still returned only the two ClubAny target articles.
