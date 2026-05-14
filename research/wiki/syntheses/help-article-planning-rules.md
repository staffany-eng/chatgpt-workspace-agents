# Help Article Planning Rules

## Purpose

LaunchBot should decide article count and target articles before drafting. The planner uses cached Intercom article-shape evidence for split/merge behavior, the all-article Intercom inventory as the Help Center map, Pantheon for product behavior, and live Intercom only for targeted refresh/search/freshness checks.

## Source Base

- Primary shape source: [StaffAny Intercom Help Article Shape](../sources/staffany-intercom-help-article-shape.md)
- LaunchBot workflow source: [Launch Superpower Bot Handoff](../sources/launch-superpower-bot-handoff.md)
- Operating model source: [Midas Karpathy Research Process](../sources/midas-research-process.md)

## Source Hierarchy

1. Live target Intercom article is current article truth.
2. Pantheon is product-behavior truth.
3. Cached Intercom planning synthesis is article-shape and planning truth.
4. Slack, Jira, and PRD are intent/context, not final behavior truth.

## Planning Rules

- Plan before drafting. Run `help-article:plan --topic "<topic>"` before creating or updating a help article.
- Use cached shape first. Do not pull all live Intercom articles every run; use curated family refreshes plus targeted live search.
- Use cached inventory before live search. The inventory covers all articles but contains metadata and derived signals only, not raw article bodies.
- Search live Intercom only to find affected existing articles and to stale-check exact staging targets.
- Split articles when different audiences perform different jobs.
- Split articles when Web, Mobile, API, or marketplace actor flows differ materially.
- Split multi-sided workflows by actor view when customer, provider, admin, and worker journeys differ.
- Keep one article when one audience completes one connected lifecycle on one product surface.
- Prefer updating an existing same-audience same-platform article over creating duplicates.
- Create or keep overview articles only when they coordinate related subflows and link out to detailed workflow articles.
- If cached profile and live target article disagree on timestamp or structural fingerprint, block as `needs-refresh`.
- If Pantheon evidence is missing, dirty, stale, or conflicting, block as `needs-check`.

## Current Family Rules

- New Joiner / Onboarding: split setup, onboarding review, and new-hire submission when HR and new hires perform different jobs.
- Company Documents: split admin Web document management from employee Mobile acknowledgement/viewing.
- ClubAny: keep brand/perk management together for Web owners; split Mobile redemption for staff.
- Claims: split setup, employee submission, approval management, payroll processing, and cutoff behavior.
- HireAny: split by marketplace side when customer, provider, and casual worker workflows differ.
- Leave: keep one combined article when the same manager workflow spans Web and Mobile; split approval/application flows when actor or platform changes.
- Timesheet: update the existing lifecycle article when behavior belongs to the same owner payroll-control workflow.
- Payroll / Payments: split by payroll operation when setup, disbursement, reports, statutory submission, and bank-file export differ.
- Scheduling: split manager Web scheduling from employee Mobile requests when acting user and surface differ.
- Permissions / Access: prefer updating the canonical access article unless a separate setup workflow is introduced.

## LaunchBot Implementation Implications

- `help-article:shape-refresh` refreshes the curated Intercom family sample and regenerates the normalized profile.
- `intercom:inventory` refreshes the all-article metadata map and keeps raw article bodies in ignored cache.
- `help-article:plan` reads the cached profile first, then the cached inventory, and only calls live Intercom for affected article search when inventory is missing or insufficient.
- `intercom:stage-update` pulls the exact live target article and runs a stale check against the cached profile before staging.
- Staged updates must include source article ID, source URL, direct edit URL, Pantheon evidence path, format gate result, article-shape stale-check result, and approval status.
- Public publishing remains manual in Intercom.
