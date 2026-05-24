# Design: Da Ta Hermz Reviewed Learning Loop

## Approach

Add a local stdio MCP server named `staffany_data_learning` under the Da Ta Hermz packet. It records safe lesson candidates into the live Hermes profile. The skill and SOUL route explicit learning/correction requests to that MCP.

This mirrors the NurtureAny reviewed-lessons pattern, but keeps naming and source boundaries specific to Da Ta Hermz and StaffAny data work.

## Hermes Learning Primitives

Do not create one vague "self-learning" layer. Use the primitive that matches the job:

| Primitive | V1 role for Da Ta Hermz | Durable behavior rule |
| --- | --- | --- |
| Built-in memory | Lightweight recall of safe preferences only | Never source of truth for StaffAny metrics, customers, permissions, or product terms |
| Honcho | Optional recall/search layer with tools-only access | Must not auto-inject raw Slack/data context or replace registries |
| Lesson candidates | Reviewed behavior proposals from live usage | Not active until promoted, verified, deployed, and live-checked |
| Source packet skills/references/SOUL | Durable behavior and workflow contracts | Canonical after repo review and deploy |
| Runtime-created or Curator-patched skills | Runtime evidence that a skill may need promotion | Review artifact only; do not treat as source-packet truth |
| No-agent cron/script | Safe monitoring and stale-candidate review cadence | Counts/status only; no raw lesson content in cron output |
| Kanban | V2 durable review queue if candidate volume grows | Out of V1 because gateway Kanban dispatch stays disabled |
| Persistent goals | Long-running session continuation | Not used for Slack learning capture |
| Self-evolution/GEPA | Future offline optimizer using traces/evals | Out of V1; PR proposal only behind tests and review |

## Runtime Store

Default candidate directory:

```text
~/.hermes/profiles/staffanydatabot/runtime/lesson-candidates/
```

Configurable env:

```text
STAFFANY_DATA_LEARNING_CANDIDATES_DIR
```

Storage format:

- one JSON file per normalized `lesson_id`
- atomic write
- no raw Slack transcripts, query rows, secrets, tokens, or sensitive personal data

Candidate fields:

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

`record_staffany_data_lesson_candidate` always creates `pending_review`; the bot cannot self-approve or self-promote. Review transitions require the explicit status-update tool and a human reviewer.

## Honcho Safety

Honcho remains useful recall, not StaffAny source of truth. The live profile should keep the existing safe shape:

- `recallMode=tools`
- `saveMessages=false`
- `sessionStrategy=per-session`
- bounded context through `contextTokens` or equivalent profile policy when auto context is enabled
- no raw Slack transcripts, query rows, customer/org facts, or sensitive data in memory smoke tests

Verification should audit these fields or block when the configured memory provider could auto-inject broad raw conversation context into future Slack answers. Same-session behavior must also be explicit: memory snapshots and provider context may not affect the current Slack answer immediately, so the bot should rely on the candidate MCP response and candidate ID in-thread, not assume memory has changed current behavior.

## MCP Tools

Add exactly these tools:

- `record_staffany_data_lesson_candidate(source_summary, proposed_rule, applies_to, target_repo_surface, risk_class, source_thread_permalink="", lesson_id="")`
- `list_staffany_data_lesson_candidates(status="", limit=20)`
- `read_staffany_data_lesson_candidate(lesson_id)`
- `update_staffany_data_lesson_candidate_status(lesson_id, status, reviewer, review_notes, approval_marker, repo_commit_sha="", live_verified_at="", live_verification_summary="")`

Allowed `target_repo_surface` values:

- `skill_reference`
- `soul`
- `mcp_contract`
- `config_template`
- `regression_case`
- `runbook`
- `research_wiki`
- `app_manifest`

Allowed `risk_class` values:

- `low`
- `medium`
- `high`

## Review Status Tool

`update_staffany_data_lesson_candidate_status` updates only the profile-runtime candidate JSON.

Rules:

- requires `reviewer`, `review_notes`, and exact `approval_marker="human reviewed lesson"`;
- blocks bot, automation, agent, and system reviewer identities using whole-word automation detection;
- supports `needs_more_evidence` for under-evidenced candidates;
- treats `approved_for_repo_promotion` as ready for repo work, not active behavior;
- requires `repo_commit_sha`, `live_verified_at`, and `live_verification_summary` before `promoted`;
- stores review events in `review_history`;
- does not mutate BigQuery, Slack, Honcho, repo files, GitHub, Kanban, persistent goals, or self-evolution state.

## Slack Behavior

When the user says something like `learn this`, `remember this`, `next time`, or gives a reusable correction, the bot should:

- summarize the behavior-level lesson safely;
- record a `pending_review` candidate if safe;
- reply that the candidate was recorded but is not active behavior yet;
- explain that durable behavior requires repo promotion, verification, deployment, and live check.

For one-off facts, raw outputs, or sensitive content, the bot must refuse candidate recording and offer a safe behavior-level summary if possible.

## Runtime Skill And Curator Boundary

Hermes can create or patch skills and Curator can review agent-created skills. For StaffAny bots, those runtime skill changes are not durable product behavior. The implementation should:

- keep source-controlled `apps/hermes-data-bot/skills/staffany-data-bot/` canonical;
- treat runtime-created or Curator-patched skills as lesson evidence only;
- surface runtime skill drift in review/audit output without copying raw runtime files into the repo;
- require repo promotion, prompt evals, verifier, deploy, and live smoke before future Slack behavior changes.

## Candidate Review Cadence

Add a no-agent review report script or cron-compatible check in implementation. Healthy output should contain only safe metadata:

- total candidate count
- pending candidate count
- oldest pending age
- count by status and risk class
- blocked/unsafe write count if tracked safely

It must not print raw lesson text, raw Slack content, query rows, or sensitive data. Da Ta Hermz keeps this report count/staleness-only by default because data-bot lesson text may mention metrics, schemas, payroll, or customer-sensitive context. Human reviewers can use the MCP list/read path for safe candidate details. If delivered to Slack, it must use the bot-owned automation path and identify itself as automation.

## Promotion Flow

1. Operator runs the count/staleness report.
2. Operator lists pending candidates.
3. Operator reads candidate safely.
4. Human reviewer marks it `rejected`, `needs_more_evidence`, or `approved_for_repo_promotion` with `approval_marker="human reviewed lesson"`.
5. Implementer promotes approved behavior into the app packet.
6. Run prompt evals, unit tests, and `npm run hermes-data-bot:verify`.
7. Deploy with `npm run hermes-data-bot:deploy -- --apply --ref HEAD`.
8. Run live audit and Slack smoke.
9. Only after live verification, mark the runtime candidate `promoted` with repo commit and live-verification metadata.

## V2 Options

If candidate volume or review handoff gets heavy, add Hermes Kanban as a durable review queue with reviewer gates and run history. Do not enable this in V1.

If enough prompt-eval traces and lesson candidates accumulate, consider an offline self-evolution experiment that proposes skill/reference changes through a PR. The experiment must preserve semantic purpose, enforce size limits, pass tests/evals, and never commit directly to `main`.

## Source Boundaries

- Honcho remains recall-only for preferences and confirmed reusable clarification.
- Local registries, BigQuery, Customer 360, and reviewed repo references remain stronger than memory.
- Runtime lesson candidates are review evidence only.
- Approved behavior must land in the smallest durable repo surface before the bot treats it as behavior.
- Persistent goals, Kanban dispatch, and offline self-evolution are not part of the V1 Slack runtime path.
