# Manual Overtime Approval PRD (Skill Test)

## Target Releases
| Target releases | Start date | Status | DRI |
| :---- | :---- | :---- | :---- |
| Payroll v1 | 2026-05-05 | Planned | Product Ops |

## Overview
- Goals: Enable managers to approve manual overtime entries faster with fewer payroll disputes.
- Background and strategic fit: Current overtime correction flow is manual and inconsistent across teams.
- Scope: Add manual overtime request + approval states + payroll export mapping.
- Out of scope: Time-tracking hardware changes.
- Assumptions: Existing users/roles and payroll batch cycles remain unchanged.

## Team (RACI)
| Activity | [R]esponsible | [A]ccountable | [C]onsulted | [I]nform |
| :---- | :---- | :---- | :---- | :---- |
| Overall | PM | Product Lead | Payroll Ops | Support |
| Design | Designer | PM | FE Lead | QA |
| Engineering | FE/BE | Eng Manager | DevOps | Support |

## Timeline
| Milestone | PIC | Date | Status | Notes |
| :---- | :---- | :---- | :---- | :---- |
| Requirements sign-off | PM | 2026-05-01 | Planned | - |
| Build complete | FE/BE | 2026-05-20 | Planned | - |

## Product Discovery / Competitor Benchmarking
- Prototype: Internal draft v1.
- Eng Units: Gryphon + Kraken payroll modules.
- Regulatory / Compliance: Overtime payout rules must remain auditable.
- Technical Constraints: Existing payroll import/export contract.
- Data Insights: Disputes mostly originate from unapproved manual edits.
- Decision Log: 2026-04-28 choose approval workflow before payroll lock.

## Requirements
1. Managers can submit and approve manual overtime adjustments with reason and attachment.
2. Approved overtime records are exportable to payroll with status history.
3. Payroll admins can filter pending and approved manual overtime per pay cycle.

## Acceptance Criteria Authoring Rules
1. AC remains in requirements table/section and is testable.
2. Frontend behavior defined before backend logic.

## RICE Assessment (When Prioritization Is Requested)
- Reach: 120 users/month
- Impact: 2
- Confidence: 80%
- Effort: 1.5
- RICE Score: 128

## Current UX Baseline (Mandatory When UX Scope Exists)
- Current screen/flow: Overtime corrections are edited directly by payroll admins.
- Current behavior observed from code: No standardized approval checkpoint.
- Improvement delta: Introduce manager approval stage before payroll lock.
- New screen/module needed?: No, extend existing overtime views.

## Affected Files (Predicted)
- pantheon/apps/gryphon/src/... (overtime UI)
- pantheon/apps/kraken/src/... (overtime approval logic)

## Risks
- Approval latency near payroll cut-off.

## Open Questions
- Should approvals auto-expire after payroll lock?
