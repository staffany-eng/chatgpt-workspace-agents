# Design: NurtureAny Learning Review Workflow

## Approach

Use a deterministic no-agent cron for review surfacing and a narrow MCP status-update primitive for human review state. The digest reads profile-runtime JSON files from `lesson-candidates/*.json`, filters reviewable statuses, redacts unsafe fields, and prints Slack markdown only when there is work.

The digest is not an agent and does not call HubSpot, Honcho, GitHub, Curator, or any LLM. It is a scheduled review inbox, not an approval engine.

## Runtime Data Model

Candidate JSON remains profile-runtime state. The durable repo packet remains the source of behavior.

Allowed statuses:

- `pending_review`
- `needs_more_evidence`
- `approved_for_repo_promotion`
- `rejected`
- `promoted`

`promoted` requires repo and live-verification metadata:

- `repo_commit_sha`
- `live_verified_at`
- `live_verification_summary`

Every human review transition stores:

- `reviewer`
- `review_notes`
- `reviewed_at`

## Digest

Add `runtime/scripts/nurtureany_lesson_review_digest.py`.

Default behavior:

- Candidate directory: `NURTUREANY_LESSON_CANDIDATES_DIR`, else profile `lesson-candidates`.
- Status filter: `pending_review`.
- Empty result: empty stdout and exit 0.
- Non-empty result: Slack markdown starting with `NurtureAny automation: Learning review`.
- Fields per lesson: lesson id, created date, source permalink, proposed rule, target repo surface, risk, status, and recommended reviewer action.

Safety:

- Reject or redact raw Slack transcripts, raw HubSpot rows, phone numbers, secrets, tokens, OAuth material, and contact exports.
- Never include raw message bodies, raw contact fields, phone exports, or credentials.

## Review Status Tool

Add `update_nurtureany_lesson_candidate_status` to `hubspot_nurtureany`.

Rules:

- Only updates runtime candidate JSON.
- Does not mutate HubSpot, Slack, GitHub, repo files, Honcho, or memory.
- Requires `reviewer`, `review_notes`, and exact `approval_marker="human reviewed lesson"`.
- Blocks bot or automation reviewer identities.
- `approved_for_repo_promotion` means ready for a repo change, not active behavior.
- `promoted` requires `repo_commit_sha`, `live_verified_at`, and `live_verification_summary`.

## Cron And Delivery

Install a no-agent cron:

- Name: `nurtureanysalesbot learning review digest`
- Schedule: `30 1 * * 1-5`
- Timezone: `Asia/Singapore`
- Script: `nurtureany_lesson_review_digest.py`
- Delivery: `slack:#nurtureany-testing` for pilot

The current Hermes CLI schedules on the deployment host timezone, so `30 1 * * 1-5` is the production UTC expression for 09:30 SGT. Health checks still validate the stored job timezone when available.

## Kanban Worker-Lane Use

Kanban is not used for approval. It is optional after a human sets `approved_for_repo_promotion`.

When an approved lesson becomes a multi-step implementation:

- Create Kanban card `nurtureany-lesson-promotion:<lesson_id>`.
- Assign to a repo-worker Hermes profile, not `nurtureanysalesbot`.
- Worker prepares branch/PR or patch, runs verify, and comments changed files/tests.
- Code-changing workers block with `review-required: <PR or diff ready>`.
- Human reviewer approves and deploys.
- Candidate is marked `promoted` only after live verification.

Keep `kanban.dispatch_in_gateway: false` for the NurtureAny Slack gateway.
