# Product Requirements Document

## Target Releases

| Target releases | Start date | Status | DRI |
| :---- | :---- | :---- | :---- |
| `<release / phase name>` | `<YYYY-MM-DD>` | `<Planned/In Progress/Done>` | `<owner>` |
| `<release / phase name>` | `<YYYY-MM-DD>` | `<Planned/In Progress/Done>` | `<owner>` |

## Overview

| Section | Guidance |
| :---- | :---- |
| **Goals** | Use a numbered list. Focus on business outcomes and user benefits. Start each point with an active verb (Enable, Improve, Reduce, Expand). |
| **Background and strategic fit** | Write one concise paragraph or short bullets describing the current pain point and why existing process/flow fails. |
| **Scope** | Use bullets that define functional boundaries clearly (settings added, user interaction, migration, mass edit/bulk actions). |
| **Out of scope** | Use bullets to explicitly state what is not built in this phase to prevent scope creep. |
| **Assumptions** | Use bullets for external factors/technical conditions assumed true. |

## Team (RACI)

| Activity | [R]esponsible | [A]ccountable | [C]onsulted | [I]nform |
| :---- | :---- | :---- | :---- | :---- |
| Overall |  |  |  |  |
| Design |  |  |  |  |
| Engineering |  |  |  |  |

## Timeline

| Milestone | PIC | Date | Status | Notes |
| :---- | :---- | :---- | :---- | :---- |
| `<milestone>` | `<owner>` | `<YYYY-MM-DD>` | `<status>` | `<notes>` |
| `<milestone>` | `<owner>` | `<YYYY-MM-DD>` | `<status>` | `<notes>` |

## Product Discovery / Competitor Benchmarking

### Prototype
- `<Figma / Readdy link>`

### Eng Units
- `<eng squad / unit mapping>`

### Competitor Benchmark (Required for New Features)
| Competitor | Similar capability | Strength observed | Gap / tradeoff | Implication for StaffAny |
| :---- | :---- | :---- | :---- | :---- |
| `<Competitor name>` | `<Comparable feature>` | `<What works well>` | `<What is missing / weak>` | `<What to adopt or avoid>` |
| `<Competitor name>` | `<Comparable feature>` | `<What works well>` | `<What is missing / weak>` | `<What to adopt or avoid>` |
| `<Competitor name>` | `<Comparable feature>` | `<What works well>` | `<What is missing / weak>` | `<What to adopt or avoid>` |

### Regulatory / Compliance
- `<laws, policy, or payroll constraints>`

### Technical Constraints
- `<backend/frontend/platform limits and blast-radius notes>`

### Data Insights
- `<analytics/interviews/support patterns proving the problem>`

### Decision Log
- `<YYYY-MM-DD>: <decision> because <reason>`

## Requirements

| #No | User stories | #SR | Requirements | Acceptance criteria | Priority | Eng-Unit |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| A | As a `<persona>`, I want `<action>`, so that `<value/benefit>`. | A-01 | `<Feature/system capability title>` | 1) Navigation & permissions: state who can access and where in UI. 2) UI details: fields, labels, descriptions, table columns. 3) Functional logic: happy path behavior. 4) Validation rules: mandatory fields and constraints. 5) State changes: post-action outcomes and persistence/response behavior. 6) Prototype links when relevant. | MVP | `<team>` |
|  |  | A-02 | `<Feature/system capability title>` | 1) `<Frontend/UI behavior in observable terms>`. 2) `<State/validation/error behavior>`. 3) `<Backend/logic/API/data contract behavior>`. | P1 | `<team>` |

## Acceptance Criteria Authoring Rules
- Keep acceptance criteria in the `Requirements` table only (no separate AC section).
- Use numbered points and add sub-points when needed (`1`, `a`, `i`) for complex logic.
- Use **bold** for concrete UI elements (labels/buttons/fields) and *italics* for user actions or placeholders.
- Make each `#SR` independently testable.
- Order acceptance criteria with frontend behavior first, then backend/logic/data behavior.

## RICE Assessment (When Prioritization Is Requested)

| Factor | Value | Notes |
| :---- | :---- | :---- |
| Reach | `<number>` | `<time window and source/assumption>` |
| Impact | `<3/2/1/0.5/0.25>` | `<expected outcome effect>` |
| Confidence | `<percent>` | `<data quality and uncertainty>` |
| Effort | `<person-months>` | `<scope and dependencies>` |
| RICE Score | `<computed value>` | `<(Reach * Impact * Confidence)/Effort>` |

## Current UX Baseline (Mandatory When UX Scope Exists)
- Current screen/flow: `<existing Gryphon screen or flow>`
- Current behavior observed from code: `<what users can do today>`
- Improvement delta: `<what changes on top of existing screen/flow>`
- New screen/module needed?: `<No by default; if Yes, include rationale from codebase gap>`

## Affected Files (Predicted)
- `path/to/backend/file.ts` - why this file is affected.
- `path/to/frontend/file.tsx` - why this file is affected.
- `TBD` - reason if exact path is unknown.

## Risks
- `<risk>`

## Open Questions
- `<question>`

## Writing Style Rules
- Draft in detail first, then tighten wording without removing requirement-critical behavior.
- Keep requirements implementation-observable and unambiguous.
- Reference existing StaffAny behavior from `pantheon/apps/kraken` first, then map impact to `pantheon/apps/gryphon`.
- For UX scope, define changes as deltas from current screen/flow.
- Do not propose net-new screens/modules unless codebase evidence shows a real gap.
