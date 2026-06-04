# Task Plan - Centralized Approval System PRD

## Request Summary
- `request_type`: `product-output`
- User asked to generate a PRD to centralize approval system.
- Skill route selected: `Triage -> PM`.

## Preflight Gate
- [x] `request_type` identified: `product-output`
- [x] Route confirmed
- [x] Model tier per agent recorded (`Triage=Low`, `PM=Medium`)
- [x] Output path reserved under `outputs/<type>/`
- [x] Jira sync mode set for Jira grooming: N/A
- [x] Jira target issue recorded (`TBD`)
- [x] Existing Jira context read first when `direct-sync` is used: N/A
- [x] Jira existing context reconciliation logged: N/A
- [x] Jira required fields confirmed for direct sync: N/A
- [x] Jira setup/bootstrap checked when direct sync is used: N/A
- [x] PRD notion sync mode set when PRD has a target page: `md-only`
- [x] PRD notion target recorded: `TBD`
- [x] PRD lifecycle state identified: `new`
- [x] If `new`, PRD page created from Notion PRD template and styling reviewed: N/A (`md-only`)
- [x] Notion integration access confirmed for target database/page: N/A (`md-only`)
- [x] PRD notion freshness checked when `direct-sync` is used: N/A
- [x] PRD update mode logged: `add-missing-only` (default for future sync)
- [x] RICE assessment completed for Jira grooming: N/A (PRD request)
- [x] Backend-first review planned (`kraken` then `gryphon`)
- [x] Current screen inventory checked for UX scope
- [x] UX improvement delta defined for UX scope
- [x] Net-new benchmark scope set (>=3 competitors)

## Handoff Log

### Transition 1
- `destination_agent`: `PM`
- `task_summary`: Draft a net-new PRD for centralized approval system aligned to existing approval logic.
- `request_type`: `product-output`
- `selected_reasoning_tier`: `Medium`
- `source_of_truth_checked`: `apps/kraken` (approval entities/routes), `apps/gryphon` (approval UI components/labels)
- `constraints`: Use PRD template, include competitor benchmark >=3, output to `outputs/prd/`, no Jira/Notion direct sync.
- `acceptance_criteria_or_fix_target`: Requirements table with testable acceptance criteria, frontend-first ordering.
- `affected_files`: `outputs/prd/2026-04-29-centralized-approval-system-prd.md`
- `jira_target_ticket`: `TBD`
- `notion_target_document`: `TBD`
- `open_questions`: rollout region sequencing, migration strategy strictness, notification channels.
- `done_signal`: PRD markdown generated and validated against template sections.

## Completion Gate
- [x] Output file path(s) listed
- [x] Source-of-truth files listed
- [x] Validation/checks listed
- [x] Remaining open questions listed

## Outputs
- `outputs/prd/2026-04-29-centralized-approval-system-prd.md`

## Source-of-Truth Files Used
- `apps/kraken/src/database/schema/baseline.sql`
- `apps/kraken/src/server/plugins/dayOffApplications/approve.ts`
- `apps/kraken/src/server/plugins/dayOffApplications/reject.test.ts`
- `apps/gryphon/src/components/Approval/ApprovalStageRowItem.tsx`
- `apps/gryphon/src/components/Approval/util.ts`
- `apps/gryphon/src/locales/en/main.json`

## Validation Notes
- Followed `references/prd-template.md` section structure.
- Included competitor benchmark with 3 competitors (Homebase, Gusto, Talenta).
- Captured backend-first baseline and frontend improvement delta.

## Remaining Open Questions
- Should centralized approvals include payroll approval objects in phase 1, or attendance/leave/claims only?
- Should orgs be allowed >2 approval levels, or keep current 1-2 level model at launch?
- Is notification unification in scope for MVP or phase 2?
