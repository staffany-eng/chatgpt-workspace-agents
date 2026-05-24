# KER — Decouple "Edit Leave Hours" Permission from Leave Assignment When Hours Are Auto-Filled

> Groomed by ProductOpsBot. Pending product review. After manual product acceptance, remove this line and untick Need Product Review.

## Overview

- **Business context:** Permission groups allow admins to deny the *Edit Leave Hours* function to restrict certain managers/supervisors from manually changing leave hour values. However, the current system conflates two distinct user actions — *manually editing leave hours* and *assigning a leave where hours are auto-filled from the staff's default leave hours setting* — under the same permission gate.
- **Problem/gap today:** When a user belongs to a permission group that denies *Edit Leave Hours*, they are completely blocked from assigning leaves for staff who have (a) a default leave hours value > 0 set on their profile AND (b) a leave type configured to auto-fill those default hours on assignment. The block applies even though the user is not manually editing any hours — the auto-fill is system-driven.
- **Goal to solve:** Allow users denied *Edit Leave Hours* to still assign leaves via the schedule when the leave hours are auto-filled by the system (default leave hours), while still correctly blocking them from *manually changing* the hours value during assignment.

## Current UX Baseline

- **Current screen/flow:** Schedule view → assign leave to staff → leave assignment modal (Gryphon, schedule/leave assignment flow)
- **Current behavior observed:** When "Edit Leave Hours" is denied in the PG, the system blocks the leave assignment API call if the resulting leave hours > 0, regardless of whether the hours originated from a manual edit or the auto-fill mechanism.
- **Improvement delta:** The system should permit the assignment to proceed when the hours value is purely auto-filled (i.e., the user has not modified the hours input). The permission block should only trigger if the user actively changes the hours field from its auto-filled value.
- **New screen/module needed?** No — this is a backend permission enforcement logic change, with a potential minor UI change to disable (not hide) the hours input field for denied users while still allowing the assignment to submit.

## Acceptance Criteria

1. In the leave assignment flow (schedule view), users with *Edit Leave Hours* denied can successfully assign a leave for a staff whose leave type is configured to auto-fill the staff's default leave hours, provided the user has not manually changed the hours value.
2. When the hours input is auto-filled and the user has *Edit Leave Hours* denied, the hours input field is rendered as read-only/disabled in the assignment modal — the auto-filled value is submitted as-is.
3. If the user has *Edit Leave Hours* denied and the auto-filled leave hours is 0, the assignment continues to succeed (no regression from current behavior).
4. If the user has *Edit Leave Hours* denied and the leave type does NOT auto-fill default hours, the hours field defaults to 0 and the assignment can proceed.
5. If the user has *Edit Leave Hours* allowed, behavior is unchanged — the hours field remains editable.
6. The backend permission check for *Edit Leave Hours* distinguishes between: (a) hours submitted equal to the system-auto-filled default → allow; (b) hours submitted differ from the system-auto-filled default → block with existing permission error.
7. Half-day leave assignments follow the same logic: if auto-filled to half of the default leave hours and the user has not changed the value, the assignment is permitted.
8. No change to leave approval, leave balance deduction, or timesheet behavior.

## Affected Files (Predicted)

- `TBD — Kraken` — backend leave assignment endpoint; permission check logic for `EDIT_LEAVE_HOURS`; likely in leave/assignment service or middleware (exact paths require Kraken codebase inspection)
- `TBD — Gryphon` — leave assignment modal component; hours input field; disable/read-only rendering when `EDIT_LEAVE_HOURS` is denied (exact paths require Gryphon codebase inspection)

## RICE Assessment

| Factor | Value | Notes |
| :---- | :---- | :---- |
| Reach | 40 | Estimated orgs using PG with Edit Leave Hours denied + leave types with auto-fill enabled; assumption based on PG adoption pattern |
| Impact | 2 | High — users are completely blocked from a core scheduling action (assigning leave) due to a permission scope mismatch; direct workflow disruption |
| Confidence | 70% | Behavior confirmed from thread discussion; no usage data on exact org/PG count; implementation complexity TBD pending code inspection |
| Effort | 0.5 | Estimated 2–3 engineer-days; backend permission logic delta + minor UI field disable; no new screen needed |
| RICE Score | 112 | (40 × 2 × 0.70) / 0.5 = 112 |

**RICE Rationale:** Users denied Edit Leave Hours are blocked from assigning leaves with auto-filled hours — unintended scope collision. Medium reach, high workflow impact per org. Fix is backend logic delta + UI field disable, low effort. No new module needed.
