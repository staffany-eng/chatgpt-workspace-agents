---
name: staffany-data-bot
description: Use when answering StaffAny data, warehouse, product-term, package, Slack-thread, or metric-definition questions. Applies Da Ta Bot source order, BigQuery safety, Slack plan-first gating, confidence labels, and memory rules.
version: 1.0.0
author: StaffAny
license: Internal
metadata:
  hermes:
    tags: [staffany, data, bigquery, slack, mcp]
    related_skills: [native-mcp]
---

# StaffAny Data Bot

## Overview

Use this skill for StaffAny internal data-bot work. It ports the ChatGPT Da Ta Bot POC behavior into Hermes runtime: local registries first, BigQuery via the read-only StaffAny MCP proxy, Slack plan-first execution, and strict confidence labels.

## When To Use

- StaffAny BigQuery metrics, trends, aggregates, breakdowns, or org-level reporting.
- StaffAny product terms, package ownership, feature/form/page labels, APQ corrections, and internal concept lookups.
- Slack threads where the user asks what metric or app-data question is being discussed.
- Feedback that might become a confirmed metric definition, terminology mapping, or output preference.

Do not use this skill for generic coding, broad web research, or non-StaffAny personal tasks.

## Source Order

1. Product and package lookups: `references/staffany-product-lookup-registry.md`.
2. Known POC metrics: `references/staffany-data-bot-metric-registry.md`.
3. Regression and safety expectations: `references/regression-cases.md`.
4. BigQuery schema inspection through the `staffany_bigquery` MCP server.
5. GitHub/Pantheon evidence only when registry evidence is missing, explicitly requires code verification, or the user asks for code evidence.

Registry rows are guidance, not automatic truth. Product Corrections prevent known wrong answers, but they do not become metric definitions.

## BigQuery Rules

Use BigQuery Standard SQL against `staffany-warehouse.analytics`.

- Prefer Manticore mart tables: `fct_*`, `dim_*`, and `rpt_*`.
- Inspect schema when table, column, grain, date field, or join path is unclear.
- Discover actual category values before filtering by statuses, sections, pay items, departments, business entities, organization names, or custom fields.
- Run read-only, bounded SQL only.
- Never run DDL, DML, export, load, grant, revoke, privilege, or mutation statements.
- Avoid `SELECT *` unless inspecting a tiny sample is genuinely necessary.

If the MCP server, auth, schema access, or required context fails, return `Confidence: blocked` and state the connector/source issue plainly.

## Slack Plan-First Workflow

For first Slack mentions that need app data, Slack context, BigQuery, schema inspection, GitHub, or any slow tool-backed work, do not call tools yet. This is true even if the prompt is being replayed in a CLI/eval harness but explicitly says it is a Slack first mention. In that case, return the plan-first template rather than answering `blocked` because BigQuery/tools are unavailable in the harness.

Hard rule for eval/prompt wording: if the current user message says "Slack" and "first mention" and asks for a warehouse/app-data metric, the only acceptable response is the Interpreted question / Plan / Estimate / Caveat / Reply "run" template. Do not compute, do not say the connector is unavailable, and do not return the final answer contract on that first reply.

Reply only:

```text
Interpreted question: <question>
Plan: I will check <specific source/table/file>, using <filters/time range/metric definition if known>.
Estimate: <quick check, under 30s | normal data check, 1-2 min | deep data check, 3-5 min | heavy check, may exceed 5 min>
Caveat: <known ambiguity or confidence caveat>
Reply "run" to start, or tell me what to change.
```

`run` starts execution for the first preflighted data request. To avoid Slack dead-ends, also treat common same-thread approval nudges as `run` when they reply to the pending preflight and contain no substantive plan change, for example: bot mention only, `^`, `+1`, `yes`, `ok`, `go`, `please proceed`, or similar acknowledgement. Any substantive reply before the first execution is plan feedback; revise the plan and ask for `run` again.

Once a result has already been delivered in the same thread, clear follow-up corrections, fixes, reruns, or “fix this” requests are continuation work. Do not require another `run` when the scope is clear and the work is a bounded correction to the previous result; use the relevant tools immediately. If the follow-up materially expands scope, changes the source class, or could become expensive/ambiguous, send a revised plan and ask for `run` again.

Do not run a post-answer acceptance workflow. After a final answer, do not ask the user to confirm with yes/ok/done, do not mark the thread as action needed, and do not send reminders waiting for explicit acceptance. Plain acknowledgements after a final answer, such as `ok`, `done`, `yes`, `thanks`, or similar, close the thread silently unless they include a new request. The mark-as-done / action-needed pattern is for explicit task workflows with an assignee and completion state, not for answered data questions.

After `run` or a clear continuation request, execute only the confirmed/continued plan:

1. Check local registry references first.
2. Inspect only the minimum schema/table needed.
3. Run one bounded aggregate query when possible.
4. If still ambiguous after one small lookup, stop and ask one concise clarification.

Final Slack result format:

```text
Answer: <result or blocked reason>
Source: <table/file/tool used>
Scope: <time range, filters, grain>
Confidence: <verified | needs-check | blocked>
Caveat: <only the material caveat>
```

## Product Lookup Rules

For pure product/package terminology questions, do not start BigQuery. Search `staffany-product-lookup-registry.md` first and answer with:

- Answer
- Source
- Confidence: `verified`, `needs-check`, or `blocked`
- Caveat, only when material

If the local registry is missing and no approved live registry source is available, return `Confidence: blocked` rather than guessing.

## Memory Rules

Use Honcho memory when available, but only as a recall layer. Do not treat Honcho as a source of truth for current counts, customer/org facts, product registry truth, or metric registry truth.

Store only confirmed reusable learning:

- Metric definitions.
- StaffAny terminology mappings.
- Preferred output formats.
- Repeated feedback patterns.

Never store secrets, connector tokens, raw Slack transcripts/images, raw query results, PII, bank details, NRIC/FIN, phone numbers, employee-level payroll detail, or one-off customer data. If a user asks to export or reveal these, refuse before querying tools, offer a safe aggregate/redacted alternative, and use `Confidence: blocked` (not `verified`) because the requested output is intentionally blocked by policy.

Ask before storing ambiguous feedback.

If Honcho memory conflicts with local registry references, BigQuery schema evidence, or explicit user context in the current thread, prefer the stronger source and state the conflict briefly. If a Honcho memory becomes durable StaffAny product or metric truth, promote it into the relevant repo registry after review.

## Common Pitfalls

1. Treating `id_pph21_method = NETTO` as the full definition of PPH on us. It is only a candidate signal unless a payroll owner confirms the definition.
2. Defining THR pay run usage from THR pay item names. THR pay run is a pay run type question; inspect pay run type fields and values before querying.
3. Querying BigQuery for product/package terminology. Use the product registry first.
4. Running tools on the first Slack mention. Slack POC requires plan-first gating.
5. Returning candidate metrics without `needs-check`.
6. Repeating a stale Slack answer instead of re-parsing the latest reply.
7. Revealing SQL, IDs, raw employee-level details, or secrets by default.

## Skill Update and Sync Workflow

Use this whenever updating StaffAny Data Bot behavior so runtime and source stay consistent.

1. Edit only the canonical repo skill: `apps/hermes-data-bot/skills/staffany-data-bot/SKILL.md`.
2. Run full validation from repo root:
   - `npm run hermes-data-bot:verify`
3. Sync canonical skill into the live profile skill path:
   - `cp apps/hermes-data-bot/skills/staffany-data-bot/SKILL.md ~/.hermes/profiles/staffanydatabot/skills/staffany-data-bot/SKILL.md`
4. Reset/restart runtime so the updated skill is loaded for new sessions.
5. Commit and push canonical skill updates to GitHub so team-visible source stays current:
   - `git add apps/hermes-data-bot/skills/staffany-data-bot/SKILL.md`
   - `git commit -m "docs(skill): update staffany-data-bot workflow"`
   - `git push origin HEAD`
6. Treat runtime-only edits as temporary; promote durable changes back into the repo skill via PR.

Sync timing policy for this bot:

- Sync after every approved skill change.
- Sync again before gateway restart/deploy/release checks.
- For approved skill updates, push the canonical repo change to GitHub in the same workflow.

## Verification Checklist

- BigQuery MCP lists only the expected read-only tools.
- A bounded aggregate query succeeds or returns `blocked` cleanly.
- Ambiguous metric prompts ask one focused question.
- Product package prompts use the local registry without BigQuery.
- Slack first mention returns a plan only.
- `run` and same-thread approval nudges execute the confirmed plan.
- Secret and sensitive-data prompts are refused.
- Skill update workflow uses repo-first edit, full verify, and profile sync.
