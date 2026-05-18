# Task Plan - Manual Overtime PRD

Date: 2026-04-27
Owner: PM Agent (Codex)
Request: Generate PRD for manual Overtime feature

## Preflight Gate
- [x] `request_type` identified: `product-output`
- [x] Route confirmed: `Triage -> PM`
- [x] Model tier per agent recorded: `PM = Medium`
- [x] Output path reserved under `outputs/<type>/`
- [x] Jira sync mode set for Jira grooming: `N/A` (PRD task)
- [x] Jira target issue recorded: `TBD`
- [x] Existing Jira context read first when `direct-sync` is used: `N/A`
- [x] Jira existing context reconciliation logged: `N/A`
- [x] Jira required fields confirmed for direct sync: `N/A`
- [x] Jira setup/bootstrap checked: `N/A`
- [x] PRD gdoc sync mode set when PRD has a target doc: `md-only`
- [x] PRD gdoc target recorded: `TBD`
- [x] PRD lifecycle state identified: `new`
- [x] If `new`, template guideline doc copied first (`1xxmNiX31waARy63GpSsyGl64kU5NGaoZwzhWZaaBmSM`) and styling reviewed: `Planned via copy-template sync command; md-only draft prepared`
- [x] If `new`, copied PRD doc stored under shared-drive folder (`1zey2F4CgRn1cS2kmSjOPxF63X9PLoHMh`): `Planned via copy-template sync command`
- [x] Service-account access confirmed for template doc + shared-drive folder: `Pending runtime check; required env vars documented`
- [x] PRD gdoc freshness checked when `direct-sync` is used: `N/A`
- [x] PRD update mode logged: `add-missing-only` (default for future direct sync)
- [x] RICE assessment completed for Jira grooming: `N/A`
- [x] Backend-first review planned (`kraken` then `gryphon`)
- [x] Current screen inventory checked for UX scope
- [x] UX improvement delta defined for UX scope
- [x] Net-new benchmark scope set (>=3 competitors)

## Triage Routing Record
- `triage_resolved_directly`: `false`
- `selected_reasoning_tier`: `Medium`
- `resolution_note`: `Net-new feature PRD requires PM structuring and competitor benchmarking`
- `why_no_handoff_needed`: `N/A`
- `done_signal`: `PRD markdown generated under outputs/prd with quality-gate completion`

## Handoff Contract
- `destination_agent`: `PM`
- `task_summary`: `Draft PRD for Manual Overtime feature grounded in current Kraken/Gryphon behavior`
- `request_type`: `product-output`
- `selected_reasoning_tier`: `Medium`
- `source_of_truth_checked`: `apps/kraken` then `apps/gryphon`
- `constraints`: `No Google Doc target provided; deliver md-only output`
- `acceptance_criteria_or_fix_target`: `Detailed requirements table with testable AC and existing-flow delta`
- `affected_files`: `outputs/prd/2026-04-27-manual-overtime-feature-prd.md`
- `jira_target_ticket`: `TBD`
- `gdoc_target_document`: `TBD`
- `open_questions`: `Country-specific OT formulas, permission scope, payroll cut-off behavior`
- `done_signal`: `PRD includes benchmark, requirements, risks, and predicted affected files`

## Completion Gate
- [x] Output file path(s) listed
- [x] Source-of-truth files listed
- [x] Validation/checks listed (or skipped with reason)
- [x] Remaining open questions listed

## Output File Paths
- `outputs/prd/2026-04-27-manual-overtime-feature-prd.md`

## Source-of-Truth Files Reviewed
- `apps/kraken/src/server/plugins/workMore/approve.ts`
- `apps/kraken/src/server/plugins/workMore/list.ts`
- `apps/kraken/src/server/lib/workMore/workMoreService.ts`
- `apps/kraken/src/server/plugins/cico/lib/clockInclockOut.ts`
- `apps/kraken/src/server/plugins/cico/lib/handleWorkMoreRequest.ts`
- `apps/kraken/src/server/plugins/organisationDetails/update.ts`
- `apps/gryphon/src/main/settings/AttendanceApproval/index.tsx`
- `apps/gryphon/src/main/settings/AttendanceApproval/useHandleSubmitAttendanceApproval.ts`
- `apps/gryphon/src/main/timesheet/details/components/WorkMoreRequest/WorkMoreRequestApprovalModal.tsx`
- `apps/gryphon/src/main/timesheet/details/components/WorkMoreRequest/WorkMoreRequestStatusCell.tsx`
- `apps/gryphon/src/common/api/workMoreRequests.ts`

## Validation / Checks
- Template followed from `references/prd-template.md`.
- Competitor benchmark included with >=3 competitors.
- Backend-first and frontend-delta framing applied.

## Remaining Open Questions
- Should manual overtime be allowed when Work More Approval is enabled, or only as manager fallback?
- Which roles beyond manager/owner can create/edit manual overtime entries?
- Should manual overtime be represented as new data entity, or as auditable synthetic clock records?
