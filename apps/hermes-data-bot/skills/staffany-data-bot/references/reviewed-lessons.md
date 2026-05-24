# Reviewed Lessons

Reviewed lessons are the only approved V1 path for Da Ta Hermz to learn from live Slack usage.

## Contract

- Runtime lesson candidates are stored in the Hermes profile, not in Honcho, BigQuery, Customer 360, Slack, or this repo.
- A candidate does not change bot behavior. It is pending evidence for a human reviewer.
- Approved behavior becomes durable only after it is promoted into the repo packet, covered by verification, merged, deployed, and live-checked.
- Lessons never override StaffAny metric registries, product registries, Customer 360 current-customer truth, BigQuery schema evidence, Slack identity rules, PII safety, or approval gates.
- Honcho remains recall only. It must not become StaffAny source of truth.

## Hermes Learning Primitives

Use the primitive that matches the job. Do not collapse these into one vague self-learning layer.

| Primitive | Da Ta Hermz role | Durable behavior rule |
| --- | --- | --- |
| Built-in memory | Lightweight safe recall | Never source of truth for StaffAny metrics, customer facts, permissions, or product terms |
| Honcho | Optional recall/search layer with tools-only access | Must not auto-inject raw Slack/data context or replace repo registries |
| Lesson candidates | Reviewed behavior proposals from live usage | Not active until promoted, verified, deployed, and live-checked |
| Source packet skills/references/SOUL | Durable behavior and workflow contracts | Canonical after repo review and deploy |
| Runtime-created or Curator-patched skills | Evidence that a skill may need promotion | Review artifact only |
| No-agent report script | Safe monitoring and stale-candidate review cadence | Counts/status only; no raw lesson text |
| Kanban | V2 durable review queue if candidate volume grows | Out of V1 |
| Persistent goals | Long-running session continuation | Not used for Slack learning capture |
| Self-evolution/GEPA | Future offline optimizer using traces/evals | Out of V1; PR proposal only behind tests and review |

## Runtime Candidate Tools

Use these only for reusable behavior corrections, not one-off facts:

- `record_staffany_data_lesson_candidate`
- `list_staffany_data_lesson_candidates`
- `read_staffany_data_lesson_candidate`
- `update_staffany_data_lesson_candidate_status`

`record_staffany_data_lesson_candidate` writes only `pending_review` candidates. The bot must not mark its own candidates approved, rejected, or promoted. Human review decisions use `update_staffany_data_lesson_candidate_status` with `approval_marker="human reviewed lesson"`.

Required candidate fields:

- `lesson_id`
- `created_at`
- `source_thread_permalink`
- `source_summary`
- `proposed_rule`
- `applies_to`
- `target_repo_surface`
- `risk_class`
- `status`
- `reviewer`
- `review_notes`
- `reviewed_at`
- `review_history`
- `repo_commit_sha`
- `live_verified_at`
- `live_verification_summary`
- `promotion_policy`
- `source_of_truth_boundary`
- `honcho_used`

Allowed statuses:

- `pending_review`
- `needs_more_evidence`
- `approved_for_repo_promotion`
- `rejected`
- `promoted`

Review status rules:

- `needs_more_evidence` means plausible but not ready for repo promotion.
- `approved_for_repo_promotion` means ready for repo work, not active behavior.
- `promoted` requires repo commit SHA, live verification timestamp, and live verification summary.
- Bot, automation, agent, or system reviewer identities cannot approve, reject, or promote candidates.
- Review notes and live verification summaries must stay safe: no raw Slack transcripts, raw query rows, secrets, tokens, PII, phone numbers, bank details, NRIC/FIN, or employee-level payroll detail.

Allowed target repo surfaces:

- `skill_reference`
- `soul`
- `mcp_contract`
- `config_template`
- `regression_case`
- `runbook`
- `research_wiki`
- `app_manifest`

## What To Record

Record a candidate when a user correction is reusable and behavior-level, for example:

- a metric-definition routing correction
- a StaffAny terminology correction
- a source-order mistake
- a Slack answer-contract correction
- a safety or approval-boundary correction
- a compact output preference that should become a regression case

Do not record:

- raw Slack transcripts or screenshots
- raw BigQuery query rows
- Customer 360 source rows
- secrets, tokens, OAuth material, or `.env` content
- PII, phone numbers, bank details, NRIC/FIN, or employee-level payroll detail
- one-off customer/org facts that belong in Customer 360, BigQuery, or another approved source
- reminders, tasks, or workflow state

## Honcho Safety

When Honcho is enabled, live audit and health checks must verify the safe recall shape:

- `recallMode=tools`
- `saveMessages=false`
- `sessionStrategy=per-session`
- bounded context through `contextTokens` or equivalent policy when auto context exists
- safe memory smoke only; no customer data, raw Slack transcripts, raw query rows, or sensitive employee details

Honcho memory can help recall prior confirmed preferences, but it must lose to current-thread context, repo registries, BigQuery schema evidence, and Customer 360 source truth.

Same-session caveat: a lesson candidate or memory write may not affect the current Slack answer immediately. In-thread, rely on the returned candidate ID and explicit current-thread context, not a claim that active behavior already changed.

## Runtime Skill And Curator Boundary

Hermes can create or patch skills, and Curator can review agent-created skills. For Da Ta Hermz, runtime-created or Curator-patched skills are review artifacts only. They must not change durable Slack behavior until the useful rule is promoted into `apps/hermes-data-bot`, covered by prompt evals/verifier, deployed, and live-checked.

## Review Cadence

Use the no-agent report script for a safe review cadence:

```bash
apps/hermes-data-bot/runtime/report-staffany-data-learning.py --stale-days 14
```

Healthy output contains only safe metadata:

- total candidate count
- pending candidate count
- oldest pending age
- stale pending count
- counts by status and risk class

It must not print raw lesson text, raw Slack content, query rows, or sensitive data. Keep Da Ta Hermz reports count/staleness-only by default because data-bot lesson text may mention metrics, schemas, payroll, or customer-sensitive context. Human reviewers can use list/read MCP tools for safe details. If the report is ever delivered to Slack, it must use a bot-owned automation path and identify itself as automation.

## Promotion Flow

1. Record the candidate with safe summary text and a Slack permalink when available.
2. Review candidates outside the live answer path.
3. Mark the runtime candidate `rejected`, `needs_more_evidence`, or `approved_for_repo_promotion` only after explicit human review with `approval_marker="human reviewed lesson"`.
4. If approved, promote the rule into the smallest durable repo surface: this reference, another skill reference, `SOUL.md`, an MCP contract, a config template, a regression case, a runbook, or the app manifest.
5. Run unit tests, prompt evals, and `npm run hermes-data-bot:verify`.
6. Deploy to the live `staffanydatabot` profile and verify MCP tool list, Honcho safe config, health, cloud doctor, and Slack smoke.
7. Mark the runtime candidate `promoted` only after live verification, with repo commit SHA and live verification metadata.

## Answering Rule

When a user asks whether Da Ta Hermz learned something, distinguish the layers:

- `candidate recorded`: live runtime evidence captured, not behavior yet
- `needs_more_evidence`: reviewed but not ready for repo promotion
- `approved_for_repo_promotion`: reviewed and ready to encode in the packet
- `promoted`: encoded in repo, verified, deployed, and live-checked

If no candidate or promoted lesson exists, say so plainly. Do not imply that usage alone changed future behavior.
