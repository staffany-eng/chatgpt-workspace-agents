# Jira Grooming Template

Use this template when the user asks to groom a Jira ticket.

## Overview

- Business context:
- Problem/gap today:
- Goal to solve:
- Current behavior (brief, based on existing code):

## Current UX Baseline (Mandatory When UX Scope Exists)

- Current screen/flow: `<existing Gryphon screen or flow>`
- Current behavior observed from code: `<what users can do today>`
- Improvement delta: `<what changes on top of existing screen/flow>`
- New screen/module needed?: `<No by default; if Yes, include rationale from codebase gap>`

## Review Status Annotation

- Add this line at the top of Jira description when drafted by Codex and awaiting PM validation:
  - `Groomed by Codex. Pending product review. After manual product acceptance, remove this line and untick Need Product Review.`
- Do not rewrite the ticket title as the first line.
- After product manually accepts the grooming, remove this annotation line and unset `Need Product Review`.

## Linked IFI Requirement

- Always inspect linked Jira items and treat `IFI-*` links as customer-demand evidence.
- Extract recurring JTBD from linked `IFI-*` insights and reflect them directly in `Acceptance Criteria`.

## RICE Assessment (Mandatory)

Use `references/rice-assessment.md` for definitions and formula.
Complete this section after drafting `Acceptance Criteria` and before syncing to Jira.

| Factor | Value | Notes |
| :---- | :---- | :---- |
| Reach | `<number>` | `<time window and source/assumption>` |
| Impact | `<3/2/1/0.5/0.25>` | `<expected outcome effect>` |
| Confidence | `<percent>` | `<data quality and uncertainty>` |
| Effort | `<person-months>` | `<scope and dependencies>` |
| RICE Score | `<computed value>` | `<(Reach * Impact * Confidence)/Effort>` |

RICE Rationale (for short Jira field, if used):
- `<<=255 chars, product value + key risk/dependency only>`

## Acceptance Criteria

1. Functional/Technical requirements

## Affected Files (Predicted)

- `path/to/file.ext` - why this file is affected

## Writing Style Rules

- Keep criteria concise and direct.
- Use numbered points for concrete behavior.
- Keep AC flat-numbered only (no nested bullet/letter hierarchy).
- Prefer implementation-observable statements over vague outcomes.
- Reference existing StaffAny behavior from `pantheon/apps/kraken` first.
- After backend review, include affected Gryphon paths when frontend flow/screen changes are required.
- In `Acceptance Criteria`, include both frontend and backend requirements.
- Order `Acceptance Criteria` with frontend requirements first, then backend/logic requirements.
- Frontend criteria should reference affected Gryphon behavior/screens.
- For UX scope, map current impacted screens/flows first and phrase each criterion as a concrete delta from current behavior.
- Do not propose net-new screens/modules unless codebase evidence confirms existing screens cannot support the requirement; include rationale.
- Do not explicitly prefix each criterion with `Frontend`/`Backend`; write concise requirement statements directly.
- Always include an `Affected Files (Predicted)` section with concrete repo paths; if unknown, write `TBD` plus reason.
- If RICE rationale is included in ticket fields, keep it <=255 chars, no title repetition, no score shorthand, and only product-critical context.

## Example Style

1. In `<screen/module>`, replace `<old behavior>` with `<new behavior>`.
2. Applicable only when `<feature flag>` is enabled.
3. For `<endpoint/logic>`, apply `<new backend behavior>`.
4. Allow `<option A>` and `<option B>` in the same control.
5. Persist value in `<field/source>` and return it in `<API response>`.
6. If `<condition>`, fallback to `<expected default behavior>`.
7. Edge cases
