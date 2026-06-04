# RICE Assessment Guide

Use this guide when prioritizing Jira grooming outputs or PRD options.

## Formula

`RICE score = (Reach * Impact * Confidence) / Effort`

## Input Definitions

- `Reach`: How many customers/users are affected in a fixed period (for example, monthly active orgs).
- `Impact`: Expected outcome per affected customer (use a consistent scale such as `3=Massive`, `2=High`, `1=Medium`, `0.5=Low`, `0.25=Minimal`).
- `Confidence`: Certainty in assumptions/data (percentage scale, typically 50-100%).
- `Effort`: Total delivery effort in person-months (or another consistent engineering unit).

## Evidence Requirements

- Do not invent business data; mark uncertain inputs as assumptions.
- Use available evidence from codebase behavior, linked tickets, support patterns, and known constraints.
- When no reliable value exists, provide a bounded estimate range and explain why.

## Output Format

Use this structure in Jira/PRD outputs:

| Factor | Value | Notes |
| :---- | :---- | :---- |
| Reach | `<number>` | `<time window and source/assumption>` |
| Impact | `<3/2/1/0.5/0.25>` | `<expected value/outcome effect>` |
| Confidence | `<percent>` | `<data quality and uncertainty>` |
| Effort | `<person-months>` | `<scope and delivery dependencies>` |
| RICE Score | `<computed value>` | `<(Reach * Impact * Confidence)/Effort>` |

## Jira Field Guidance

- If Jira has a short-text `RICE Rationale` field, keep it concise (<=255 chars).
- Include only product-critical context (value + key risk/dependency).
- Avoid title repetition and score shorthand like `C45`.
