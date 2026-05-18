# Product Requirements Document - Manual Overtime Feature

## Target Releases

| Target releases | Start date | Status | DRI |
| :---- | :---- | :---- | :---- |
| Discovery + Scope Freeze | 2026-05-04 | Planned | Product Manager |
| MVP Build + Internal QA | 2026-05-18 | Planned | Kraken + Gryphon Eng |
| Pilot Rollout (Selected Orgs) | 2026-06-08 | Planned | Product + Support |

## Overview

| Section | Guidance |
| :---- | :---- |
| **Goals** | 1. Enable managers/owners to record auditable overtime when clock data is incomplete or operationally blocked. 2. Reduce payroll delays caused by pending or missing Work More requests. 3. Improve trust by separating employee-submitted overtime requests from admin-entered manual overtime adjustments. 4. Expand payroll readiness by allowing controlled manual overtime before payrun cut-off with explicit approval trail. |
| **Background and strategic fit** | Current Work More flow is designed around clock-out extension approval and depends on pending request lifecycle. In practice, payroll and ops teams still need a controlled fallback to capture overtime that cannot be represented cleanly through existing clock events (late submissions, device/network issues, post-lock reconciliation, correction after manager review). A dedicated manual overtime flow reduces workarounds and preserves compliance/audit quality. |
| **Scope** | - Add Manual Overtime entry and edit flow as a delta on existing timesheet details and/or payroll preparation flow (no standalone module by default). - Store manual overtime as explicit, auditable records with actor, reason, and timestamps. - Reflect manual overtime in total OT, discrepancy surfaces, and payroll-exported overtime hours/costs. - Permission-gate create/edit/void actions to manager+ levels (final scope to confirm). - Keep Work More Approval flow intact and interoperable. |
| **Out of scope** | - Replacing Work More Request flow. - Rewriting base overtime calculation engine (contract/shift-based OT logic remains source of truth). - Country-specific statutory formula redesign in this phase. - Auto-approval rules powered by AI or external integrations. |
| **Assumptions** | - Existing orgs already use current timesheet + OT configuration and need incremental capability. - Manual overtime must be distinguishable from normal clock-derived OT in audit/reporting. - Payroll exports can include both clock-derived and manual OT without breaking downstream templates. |

## Team (RACI)

| Activity | [R]esponsible | [A]ccountable | [C]onsulted | [I]nform |
| :---- | :---- | :---- | :---- | :---- |
| Overall | PM | Product Lead | Engineering Manager, Support Lead | CS, Ops |
| Design | Product Designer | PM | Frontend Lead | Engineering |
| Engineering | Kraken + Gryphon Engineers | Engineering Manager | PM, QA | Support |

## Timeline

| Milestone | PIC | Date | Status | Notes |
| :---- | :---- | :---- | :---- | :---- |
| PRD sign-off | PM | 2026-05-06 | Planned | Resolve open questions on permissions + representation |
| Technical design review | Backend Lead | 2026-05-12 | Planned | Confirm schema and recalculation impact |
| MVP code complete | Eng Team | 2026-05-29 | Planned | Includes FE/BE and core tests |
| Pilot readiness | PM + Support | 2026-06-08 | Planned | Enable for selected orgs |

## Product Discovery / Competitor Benchmarking

### Prototype
- TBD (Gryphon timesheet details and/or payroll prep flow extension)

### Eng Units
- Kraken: timesheet/workhours/work more/org settings/payroll export paths
- Gryphon: timesheet details, discrepancy actions, approval modals, settings + API clients

### Competitor Benchmark (Required for New Features)
| Competitor | Similar capability | Strength observed | Gap / tradeoff | Implication for StaffAny |
| :---- | :---- | :---- | :---- | :---- |
| Talenta | Employee/admin overtime request + approval flows | Strong request lifecycle with explicit approval queue and status filtering; supports admin-assisted submission | Primarily request-centric; operational corrections may still depend on request pathway | Keep approval rigor but add manager manual-entry path for exceptional reconciliation without forcing employee request flow |
| Talenox | Payroll overtime processing with manual entry under attendance tab | Simple payroll-friendly manual input for OT hours/days | Lightweight audit semantics in comparison to request-first systems | Adopt straightforward manual entry UX, but enforce richer audit trail (reason, actor, immutable history) |
| 7shifts | Overtime warnings/alerts and compliance-oriented labor controls | Proactive overtime visibility (warning/alerts) reduces surprises | Focuses strongly on alerting and schedule-time control, less on explicit post-facto manual adjustment workflow | Include warning surfaces around manual OT volume and require justifications to prevent silent over-adjustments |
| BrioHR | Attendance overtime with manager/HR approval and category mapping | Clear HR/admin override path and approval model | Can blur automatic vs manual sources if not strongly labeled in downstream reports | Clearly separate manual overtime source in UI/export so payroll can trace origin quickly |

### Regulatory / Compliance
- OT representation must preserve legal defensibility via actor/time/reason history.
- Country payroll rules remain enforced by current engine; manual entry should feed into existing formula paths, not bypass statutory multipliers.

### Technical Constraints
- Existing Work More behavior in Kraken couples overtime extension to clock-out/request lifecycle (`/cico` with `WORK_MORE`, `/work-more-request/*`).
- Work More Approval toggle currently interacts with Late Clock Out Prevention and invalidates pending requests when turned off.
- OT summary and details in Gryphon are currently derived from timesheet/workhours data structures; manual records must integrate without breaking totals or export assumptions.

### Data Insights
- Current product copy and behavior indicate Work More is intended to avoid unintended overtime via approval, which leaves a gap for legitimate overtime corrections outside request timing.
- Existing UI already supports approval/rejection and adjustment patterns; manual overtime should leverage these existing surfaces for low adoption friction.

### Decision Log
- 2026-04-27: Use existing timesheet/payroll surfaces (delta-first) instead of introducing a new standalone module, because current Kraken/Gryphon architecture already contains overtime + approval touchpoints.
- 2026-04-27: Keep Work More and Manual Overtime as separate concepts, because one is employee request-based while the other is admin correction-based.

## Requirements

| #No | User stories | #SR | Requirements | Acceptance criteria | Priority | Eng-Unit |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| A | As a manager/owner, I want to add manual overtime for a staff member, so that payroll can proceed when actual overtime cannot be represented by normal clock flow. | A-01 | Manual Overtime Entry (create) | 1) Navigation & permissions: from existing timesheet detail/payroll prep view, users with configured permission can open **Add Manual Overtime** action; unauthorized users only see read-only values. 2) UI details: form includes **Date**, **Overtime Hours**, **Reason**, optional **Reference Note**. 3) Functional logic: submission creates a manual overtime record linked to user, shift/timesheet period, creator, and org. 4) Validation rules: OT hours > 0, date within allowed period, reason required. 5) State changes: totals/OT badges refresh immediately and include manual OT in summary. | MVP | Gryphon + Kraken |
|  |  | A-02 | Manual Overtime Edit/Void (controlled correction) | 1) Existing manual overtime records can be edited/voided only by authorized users and only within configurable lock window. 2) Every edit/void creates immutable audit history (before/after, actor, timestamp, reason). 3) Voided records are excluded from active OT totals but remain visible in audit/history views. | MVP | Kraken + Gryphon |
|  |  | A-03 | Overtime Source Transparency | 1) Timesheet/detail views label overtime source clearly as **Clock-derived**, **Work More-approved**, or **Manual**. 2) Hover/details panel shows source metadata (who entered/approved, when, reason). 3) Export/report payload includes source flags for downstream payroll traceability. | MVP | Gryphon + Kraken |
|  |  | A-04 | Interoperability with Work More Approval | 1) Manual overtime can coexist with Work More requests without overwriting historical request records. 2) Conflict handling is explicit: if same shift/date already has pending Work More, user is prompted with clear options before saving manual OT. 3) Disabling Work More Approval does not delete manual OT records. | P1 | Kraken + Gryphon |
|  |  | A-05 | Payroll & Recalculation Integration | 1) Manual overtime feeds existing overtime calculation and payroll export paths consistently across supported modes. 2) Recalculation jobs/processes include manual overtime deltas and keep totals deterministic. 3) Validation ensures manual OT does not produce negative/invalid breakdown values. | MVP | Kraken |
|  |  | A-06 | Safety Controls & Operational Guardrails | 1) Org-level optional limits can warn/block unusually high manual OT entries (per day/per staff threshold). 2) Managers see warning copy before submit for outlier values. 3) Admin reporting includes count and total hours of manual OT entries per period. | P2 | Kraken + Gryphon |

## Acceptance Criteria Authoring Rules
- Acceptance criteria are kept in the `Requirements` table only.
- Frontend behavior is listed before backend/data behavior per requirement.

## Current UX Baseline (Mandatory When UX Scope Exists)
- Current screen/flow: Gryphon Timesheet details and Work More Approval modal/action cells; Attendance Approval settings toggle.
- Current behavior observed from code: overtime extension is handled through Work More request creation/approval/rejection; approval can overwrite clock out and recalculates work breakdown.
- Improvement delta: add explicit manager-entered Manual Overtime action in existing timesheet/payroll context with audit-grade metadata and source labeling.
- New screen/module needed?: No (default). If usability testing fails, consider lightweight drawer/modal refinement only.

## Affected Files (Predicted)
- `apps/kraken/src/server/lib/timesheets/workHours/workHoursRecalculation/countWorkHours.ts` - integrate manual OT inputs into breakdown calculation path.
- `apps/kraken/src/server/lib/workMore/workMoreService.ts` - align coexistence rules between Work More and manual OT flows.
- `apps/kraken/src/server/plugins/timesheets/show.ts` - include manual OT source payload in timesheet response.
- `apps/kraken/src/server/plugins/timesheets/list.ts` - include source-aware OT aggregates in list responses.
- `apps/kraken/src/server/plugins/payroll/payruns/*` - ensure payroll exports and payrun item calculations include manual OT entries.
- `apps/gryphon/src/main/timesheet/details/TableCols/index.tsx` - surface Manual OT action/state in existing table interactions.
- `apps/gryphon/src/main/timesheet/details/TableData.ts` - render source-labeled OT values and metadata.
- `apps/gryphon/src/common/api/timesheets.ts` - consume manual OT/source fields from backend responses.
- `apps/gryphon/src/main/timesheet/summary/table/Columns.tsx` - reflect manual OT in summary totals/tooltip context.
- `apps/gryphon/src/locales/*/main.json` - add i18n strings for manual overtime UI and validation states.

## Risks
- Double-count risk when manual OT overlaps with existing Work More-approved or clock-derived OT for same shift/date.
- Compliance risk if manual OT edits are allowed without strict audit reason and role checks.
- Payroll regression risk across country-specific templates if source-aware OT fields are not backward compatible.

## Open Questions
- Should manual overtime be constrained to post-shift only, or also allow day-level OT without linked shift slot?
- What is the exact permission mapping (owner, manager, supervisor, payroll admin)?
- Do we need separate approval for manager-entered manual OT above threshold values?
- Should manual OT be blocked after timesheet lock, or allowed with elevated override + mandatory note?
- How should manual OT appear in employee-facing views (visible, partially visible, or hidden)?

## PRD Sync Status
- Sync mode: `md-only`
- Google Doc target: `TBD`
- Suggested sync command (new PRD from template, when doc is ready):
  - `node scripts/sync-prd-google-doc.mjs --copy-template --template-doc "https://docs.google.com/document/d/1xxmNiX31waARy63GpSsyGl64kU5NGaoZwzhWZaaBmSM/edit?usp=sharing" --folder "https://drive.google.com/drive/u/2/folders/1zey2F4CgRn1cS2kmSjOPxF63X9PLoHMh" --title "PRD - Manual Overtime Feature" --file outputs/prd/2026-04-27-manual-overtime-feature-prd.md --mode replace`

## Reference Links Used for Benchmarking
- Talenta Overtime Request: https://help-center.talenta.co/hc/en-us/articles/11158406381209-How-to-Request-Overtime
- Talenta Overtime Settings: https://help-center.talenta.co/hc/en-us/articles/11446032209305-How-to-Manage-Overtime-in-Settings-Menu
- Talenox Overtime Payroll: https://help.talenox.com/en/articles/5264730-steps-to-process-overtime-payment-in-payroll
- 7shifts Labor & Overtime: https://kb.7shifts.com/hc/en-us/articles/4417504930963-Labor-Overtime
- BrioHR Overtime Approval: https://support.briohr.com/knowledge/hr-admin-approve-overtime-in-briohr-browser-guide
