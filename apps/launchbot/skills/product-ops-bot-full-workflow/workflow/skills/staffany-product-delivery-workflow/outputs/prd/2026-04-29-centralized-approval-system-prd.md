# Product Requirements Document

## Target Releases

| Target releases | Start date | Status | DRI |
| :---- | :---- | :---- | :---- |
| Approval Core Unification (MVP) | 2026-05-18 | Planned | Product + Backend Lead |
| Approval Migration & Controls (Phase 2) | 2026-06-29 | Planned | Product + Fullstack Lead |

## Overview

| Section | Guidance |
| :---- | :---- |
| **Goals** | 1. Enable a single approval domain model across all request types in the app through iterative migration. 2. Improve admin setup speed by centralizing approver configuration and rule visibility in one place. 3. Reduce approval errors caused by fragmented approver logic and inconsistent stage handling. 4. Expand auditability with a unified approval timeline and decision log format for all request types. 5. Support up to 3 approval layers with clear stage progression and fallback rules. |
| **Background and strategic fit** | StaffAny currently supports approval behavior in multiple domains, but routing, setup surfaces, and approval statuses are split across feature-specific implementations. This causes setup overhead, repeated configuration patterns, and inconsistent user understanding across products. A centralized approval system aligns with platform consistency goals and lowers long-term maintenance cost. |
| **Scope** | - Introduce centralized approval policy entity and mapping to request types. - Support 1st, 2nd, and 3rd approver rules in centralized policy configuration. - Standardize approval state machine and audit event shape across migrated request types. - Add migration layer from existing approval pairs/configs to centralized policy records. - Keep existing end-user request submission and approve/reject actions, but route through centralized engine. - Roll out by request type iteratively until all approval-based request types are migrated. |
| **Out of scope** | - Net-new mobile-native approval UX redesign. - Replacing permission/access-control framework. - Retrospective rewrite of historical approval records beyond required compatibility mapping. |
| **Assumptions** | - Existing approver assignments and stage semantics are valid enough to migrate with deterministic mapping. - Most organizations can adopt up to 3 approval levels with progressive setup guidance. - Current request-type APIs can be adapted to shared approval orchestration without breaking client contracts. |

## Team (RACI)

| Activity | [R]esponsible | [A]ccountable | [C]onsulted | [I]nform |
| :---- | :---- | :---- | :---- | :---- |
| Overall | Product Manager | Product Director | Engineering Manager, QA Lead | Support, CS |
| Design | Product Designer | Product Manager | Frontend Lead | Support |
| Engineering | Backend Lead + Frontend Lead | Engineering Manager | DevOps, QA | Product, Support |

## Timeline

| Milestone | PIC | Date | Status | Notes |
| :---- | :---- | :---- | :---- | :---- |
| Discovery sign-off and data mapping | PM + Backend Lead | 2026-05-23 | Planned | Confirm request types and migration strategy |
| MVP implementation complete | FE/BE Leads | 2026-06-19 | Planned | Central policy module with up to 3-layer approval + first migrated request types |
| Iterative migration by request type | PM + EM | 2026-07-24 | Planned | Migrate remaining request types in controlled batches with parity checks |
| Full rollout complete | PM + EM | 2026-08-07 | Planned | All approval-based request types migrated to centralized system |

## Product Discovery / Competitor Benchmarking

### Prototype
- TBD (to be attached in Gryphon handoff)

### Eng Units
- Kraken backend domains: Leave, Attendance, Claims approval flows
- Gryphon frontend domains: Approval configuration and request action surfaces

### Competitor Benchmark (Required for New Features)
| Competitor | Similar capability | Strength observed | Gap / tradeoff | Implication for StaffAny |
| :---- | :---- | :---- | :---- | :---- |
| Homebase | Unified team request approvals (time-off/scheduling context) | Clear centralized pending queue and simple policy setup UX | Less flexible for complex cross-domain business rules | Prioritize one central admin surface and one central pending queue mental model |
| Gusto | Policy-driven approvals connected to payroll/HR workflows | Strong auditability and consistent event trails across workflows | Higher complexity in setup for smaller teams | Keep setup simple with progressive disclosure, but preserve strong audit logs |
| Talenta | Configurable approval chains across HR operations | Multi-module consistency and configurable approver structures | Can become complex when many rule dimensions are exposed at once | Start with constrained rule builder in MVP; expand after adoption data |

### Regulatory / Compliance
- Approval actions must preserve actor identity, timestamp, and decision reason for audit trails.
- Data retention and access to approval history must remain compliant with local labor/payroll governance where applicable.

### Technical Constraints
- Kraken currently has request-type-specific approval entities and logic; full replacement must be phased to avoid regressions.
- Gryphon currently renders approval-stage UI patterns that assume existing status shapes and max stage semantics.
- Backward-compatible API contracts are required for gradual rollout.

### Data Insights
- Approval strings and UI labels in Gryphon indicate multiple existing approval contexts and user education burden.
- Kraken schema and tests show domain-specific approval handling (leave/work more/edit attendance/claims), signaling fragmentation risk.

### Decision Log
- 2026-04-29: Expand centralized approval support from 2 to 3 approval levels.
- 2026-04-29: Centralize policy and orchestration first, then evaluate deeper UX consolidation in phase 2.
- 2026-04-29: Use iterative request-type migration strategy to reduce risk and protect SLA.

## Requirements

| #No | User stories | #SR | Requirements | Acceptance criteria | Priority | Eng-Unit |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| A | As an Org Admin, I want one place to configure approval policies, so that I can manage approvals consistently across modules. | A-01 | Central Approval Policy Module | 1) Navigation & permissions: only users with organization-level approval configuration permissions can access **Settings > Approval Center**. 2) UI details: policy list shows **Policy Name**, **Request Types**, **Scope**, **1st Approver Rule**, **2nd Approver Rule**, **3rd Approver Rule**, **Status**, **Last Updated By/At**. 3) Functional logic: admin can create, edit, enable/disable a policy and assign supported request types. 4) Validation rules: at least 1 approver rule must be defined; no duplicate approver assignment across stages under same policy scope unless explicit override is enabled. 5) State changes: saving policy persists centralized policy record and emits audit event with before/after snapshots. | MVP | FE + BE |
|  |  | A-02 | Centralized Approval Orchestration Engine | 1) Request submission for in-scope request types resolves active policy deterministically by org + scope. 2) Pending approval state is normalized into shared status model (`PENDING_STAGE_1`, `PENDING_STAGE_2`, `PENDING_STAGE_3`, `APPROVED`, `REJECTED`, `CANCELLED`). 3) Approve/reject actions validate acting user against current stage approver eligibility before mutating status. 4) Stage progression requires sequential completion (stage 1 -> stage 2 -> stage 3) when configured; if a stage is unconfigured, progression skips to the next configured stage. 5) Existing API response contracts for current request endpoints remain backward-compatible during rollout. 6) Audit payload schema is standardized for all in-scope request types with actor, stage, reason, and timestamp fields. | MVP | BE |
| B | As an Approver, I want consistent approval behavior and history across all request types, so that I can act confidently and trace decisions. | B-01 | Unified Approval Timeline and Action Rules | 1) Request detail views display standardized **Approval Timeline** rows with stage label, approver identity, decision, timestamp, and optional reason. 2) UI interaction: when user is not the current stage approver, **Approve** and **Reject** actions are hidden or disabled with a clear explanation. 3) Functional logic: rejection behavior is consistent and terminal unless policy explicitly permits resubmission via existing request flow. 4) Error handling: invalid stage/action mismatch returns consistent user-facing and API errors across modules. | P1 | FE + BE |
| C | As a Product/Ops team member, I want safe migration from legacy approval config, so that we can launch without breaking existing org behavior. | C-01 | Migration and Rollout Controls | 1) Migration job maps existing approver settings/pairs to centralized policy records with deterministic conflict handling and migration report output. 2) Existing 2-layer configs are auto-mapped to stage 1 and stage 2; stage 3 defaults to null until explicitly configured. 3) Feature flag supports org-level opt-in rollout and rollback to legacy execution path during rollout period. 4) Post-migration verification exposes policy parity checks (legacy vs centralized) before org activation. 5) No in-flight pending requests are dropped; pending items continue with preserved stage state after activation. | MVP | BE + Ops |
| D | As Product/Engineering, I want migration to cover all request types in the app iteratively, so that we can centralize safely without a big-bang release. | D-01 | Request-Type Migration Plan | 1) A migration registry lists all approval-based request types in the app and assigns each type a migration status (`NOT_STARTED`, `IN_MIGRATION`, `MIGRATED`, `ROLLED_BACK`). 2) Each request type is onboarded through the same playbook: schema mapping, API adapter, parity tests, canary org rollout, and monitoring gates. 3) Request types are migrated in small batches with explicit go/no-go checkpoints and rollback criteria per type. 4) Dashboard/reporting shows centralized coverage percentage across request types and highlights remaining legacy types. 5) Completion criteria for this initiative is 100% migration of approval-based request types to centralized orchestration. | P1 | PM + FE + BE + Ops |

## Acceptance Criteria Authoring Rules
- Keep acceptance criteria in the `Requirements` table only (no separate AC section).
- Use numbered points and add sub-points when needed (`1`, `a`, `i`) for complex logic.
- Use **bold** for concrete UI elements (labels/buttons/fields) and *italics* for user actions or placeholders.
- Make each `#SR` independently testable.
- Order acceptance criteria with frontend behavior first, then backend/logic/data behavior.

## RICE Assessment (When Prioritization Is Requested)

| Factor | Value | Notes |
| :---- | :---- | :---- |
| Reach | 0 | Not requested for this PRD draft |
| Impact | 0 | Not requested for this PRD draft |
| Confidence | 0 | Not requested for this PRD draft |
| Effort | 0 | Not requested for this PRD draft |
| RICE Score | 0 | Not requested for this PRD draft |

## Current UX Baseline (Mandatory When UX Scope Exists)
- Current screen/flow: approval setup and request actions are distributed across module-specific settings and request pages.
- Current behavior observed from code: approval-stage and approver-related rendering exists, with module-specific labels and action constraints.
- Improvement delta: introduce centralized Approval Center while preserving existing request interaction patterns; add consistent timeline/action language across modules.
- New screen/module needed?: Yes. A centralized admin module is required because current setup surfaces are fragmented and do not provide one cross-domain policy source.

## Affected Files (Predicted)
- `apps/kraken/src/server/plugins/dayOffApplications/approve.ts` - adapt leave approval actions to centralized orchestration.
- `apps/kraken/src/server/plugins/dayOffApplications/reject.ts` - align rejection checks and status transitions to shared model.
- `apps/kraken/src/database/models/Claim/*` - adapt claim approval status mapping and approver checks.
- `apps/kraken/src/database/schema/*` - add centralized approval policy and mapping tables.
- `apps/gryphon/src/components/Approval/ApprovalStageRowItem.tsx` - normalize timeline display semantics.
- `apps/gryphon/src/components/Approval/util.ts` - map centralized status/stage labels.
- `apps/gryphon/src/main/**` - add Approval Center settings module routes/pages.

## Risks
- Migration mismatch can create unintended approver routing for some orgs.
- Backward-compatibility gaps may break existing frontend assumptions during phased rollout.
- Cross-domain orchestration can increase latency if not optimized.

## Open Questions
- Should Claims and future request types use identical stage constraints as Leave/Attendance, or allow per-type stage behavior overrides?
- Do we need policy simulation tooling before enabling centralized mode per org?
- What notification channels (in-app/email/push) must be standardized in MVP vs phase 2?
- What is the final ordered migration sequence across all approval-based request types?

## Writing Style Rules
- Draft in detail first, then tighten wording without removing requirement-critical behavior.
- Keep requirements implementation-observable and unambiguous.
- Reference existing StaffAny behavior from `pantheon/apps/kraken` first, then map impact to `pantheon/apps/gryphon`.
- For UX scope, define changes as deltas from current screen/flow.
- Do not propose net-new screens/modules unless codebase evidence shows a real gap.
