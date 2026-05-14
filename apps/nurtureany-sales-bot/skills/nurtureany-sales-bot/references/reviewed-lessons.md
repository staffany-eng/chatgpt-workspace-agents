# Reviewed Lessons

Reviewed lessons are the only approved way for NurtureAny to become smarter from live usage in V1.

## Contract

- Runtime lesson candidates are stored in the Hermes profile, not in HubSpot, Honcho, or this repo.
- A candidate does not change bot behavior. It is pending evidence for a human reviewer.
- Approved behavior becomes durable only after it is promoted into the repo packet, covered by verification, merged, deployed, and live-checked.
- Lessons never override HubSpot account/contact/activity truth, runtime access policy, Slack identity rules, PII/body safety, approval gates, or explicit sales best-practice references.
- Honcho remains disabled for NurtureAny V1.

## Runtime Candidate Tools

Use these only for reusable behavior corrections, not one-off facts:

- `record_nurtureany_lesson_candidate`
- `list_nurtureany_lesson_candidates`
- `read_nurtureany_lesson_candidate`

`record_nurtureany_lesson_candidate` writes only `pending_review` candidates. The bot must not mark its own candidates approved, rejected, or promoted.

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

Allowed statuses:

- `pending_review`
- `approved_for_repo_promotion`
- `rejected`
- `promoted`

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

- a terminology correction that should apply to future NurtureAny drafting
- a repeated source-order mistake
- a workflow-routing correction
- a safety or approval-boundary correction
- a compact output contract correction that should become a regression case

Do not record:

- raw Slack transcripts
- raw HubSpot rows
- phone numbers, contact exports, or raw PII
- secrets, tokens, OAuth material, or `.env` content
- one-off account facts that belong in HubSpot
- unreviewed customer proof or private sales notes
- reminders, tasks, or workflow state

## Promotion Flow

1. Record the candidate with safe summary text and a Slack permalink when available.
2. Review candidates outside the live answer path.
3. If approved, promote the rule into the smallest durable repo surface: this reference, another skill reference, `SOUL.md`, an MCP contract, a config template, a regression case, or a runbook.
4. Run NurtureAny verification and relevant unit tests.
5. Deploy to production and verify the live MCP tool list, Honcho-disabled state, and gateway health.
6. Mark the runtime candidate `promoted` only after live verification.

## Answering Rule

When a user asks whether NurtureAny learned something, distinguish the layers:

- `candidate recorded`: live runtime evidence captured, not behavior yet
- `approved_for_repo_promotion`: reviewed and ready to encode in the packet
- `promoted`: encoded in repo, verified, deployed, and live-checked

If no candidate or promoted lesson exists, say so plainly. Do not imply that usage alone changed future behavior.
