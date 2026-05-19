# Reviewed Lessons

Reviewed lessons are the only approved way for NurtureAny to become smarter from live usage in V1.

## Contract

- Runtime lesson candidates are stored in the Hermes profile, not in HubSpot, Honcho, Curator, memory, or this repo.
- A candidate does not change bot behavior. It is pending evidence for a human reviewer.
- Approved behavior becomes durable only after it is promoted into the repo packet, covered by verification, merged, deployed, and live-checked.
- Lessons never override HubSpot account/contact/activity truth, runtime access policy, Slack identity rules, PII/body safety, approval gates, or explicit sales best-practice references.
- Honcho remains disabled for NurtureAny V1.

## Runtime Candidate Tools

Use these only for reusable behavior corrections, not one-off facts:

- `record_nurtureany_lesson_candidate`
- `list_nurtureany_lesson_candidates`
- `read_nurtureany_lesson_candidate`
- `update_nurtureany_lesson_candidate_status`

`record_nurtureany_lesson_candidate` writes only `pending_review` candidates. The bot must not mark its own candidates approved, rejected, or promoted.

`update_nurtureany_lesson_candidate_status` is a human-review primitive for runtime JSON only. It requires `approval_marker="human reviewed lesson"`, `reviewer`, and `review_notes`; automation, bot, system, or agent identities must not approve, reject, or promote candidates. It never writes HubSpot, GitHub, Honcho, memory, Slack messages, or repo files.

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
- `needs_more_evidence`
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
2. Let the weekday no-agent digest surface only safe pending summaries to the allowlisted internal Slack review channel. Empty pending queue stays silent.
3. A human reviewer chooses `rejected`, `needs_more_evidence`, or `approved_for_repo_promotion`; the bot must not self-approve.
4. If approved, promote the rule into the smallest durable repo surface: this reference, another skill reference, `SOUL.md`, an MCP contract, a config template, a regression case, or a runbook.
5. Run NurtureAny verification and relevant unit tests.
6. Deploy to production and verify the live MCP tool list, Honcho-disabled state, gateway health, cloud doctor candidate counts, and Slack digest behavior.
7. Mark the runtime candidate `promoted` only after live verification, with repo commit SHA, live verification timestamp, and live verification summary.

## Review Digest

The review digest is `runtime/scripts/nurtureany_lesson_review_digest.py` and should run as Hermes no-agent cron:

```bash
hermes -p nurtureanysalesbot cron create "30 1 * * 1-5" \
  --name "nurtureanysalesbot learning review digest" \
  --script nurtureany_lesson_review_digest.py \
  --deliver slack:#nurtureany-testing \
  --no-agent
```

The script reads `NURTUREANY_LESSON_CANDIDATES_DIR` or the profile `lesson-candidates` directory. It prints nothing when no `pending_review` candidate exists. Non-empty output starts with `NurtureAny automation:` and includes lesson id, created date, source permalink, proposed rule, target repo surface, risk, status, and recommended reviewer action.

It must never include raw Slack transcripts, raw HubSpot rows, phone numbers, contact exports, secrets, tokens, OAuth material, or raw business data.

## Kanban Boundary

Do not use Kanban for first review or approval storage. Kanban is allowed only after a candidate is `approved_for_repo_promotion` and the repo change needs durable task lifecycle, named owner, comments, run history, queue dispatch, or PR review.

Kanban card pattern:

```text
nurtureany-lesson-promotion:<lesson_id>
```

Assign the card to a repo-worker profile, not `nurtureanysalesbot`. The worker prepares a branch, PR, or patch and stops at `review-required: <PR or diff ready>` for human review. Only after merge, deploy, and live check should the runtime candidate become `promoted`.

## Current Candidate Handling

- Smoke/test candidates should be rejected or archived as smoke evidence, not promoted into product behavior.
- The Lusha LinkedIn URL fallback candidate should be reviewed as an `mcp_contract` change: update the Lusha/lead-enrichment contract, add tests, verify NurtureAny, deploy, live-check, then mark the runtime candidate `promoted`.

## Answering Rule

When a user asks whether NurtureAny learned something, distinguish the layers:

- `candidate recorded`: live runtime evidence captured, not behavior yet
- `needs_more_evidence`: human reviewer asked for more proof; not behavior yet
- `approved_for_repo_promotion`: reviewed and ready to encode in the packet
- `promoted`: encoded in repo, verified, deployed, and live-checked

If no candidate or promoted lesson exists, say so plainly. Do not imply that usage alone changed future behavior.
