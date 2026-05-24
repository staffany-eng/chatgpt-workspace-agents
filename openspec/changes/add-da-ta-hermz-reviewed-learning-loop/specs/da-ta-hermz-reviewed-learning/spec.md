# Specification: Da Ta Hermz Reviewed Learning

## ADDED Requirements

### Requirement: Reviewed Lesson Candidate MCP

The system SHALL expose a `staffany_data_learning` MCP with write/list/read/status-update tools for runtime-local reviewed-learning candidates.

#### Scenario: Record safe lesson candidate

- GIVEN a reusable behavior correction with safe summary text
- WHEN `record_staffany_data_lesson_candidate` is called
- THEN the system SHALL write a `pending_review` candidate
- AND SHALL return `Confidence: verified`
- AND SHALL state that the candidate does not change behavior until promoted.

#### Scenario: Reject unsafe lesson payload

- GIVEN a candidate containing raw Slack transcript shape, raw query rows, secrets, tokens, PII, phone numbers, or employee payroll detail
- WHEN the record tool is called
- THEN the system SHALL return `Confidence: blocked`
- AND SHALL not write a candidate file.

#### Scenario: List and read review candidates

- GIVEN one or more runtime lesson candidates exist
- WHEN `list_staffany_data_lesson_candidates` is called
- THEN the system SHALL return compact safe candidate metadata
- AND SHALL support optional filtering by candidate status.

- GIVEN a specific safe candidate exists
- WHEN `read_staffany_data_lesson_candidate` is called with its `lesson_id`
- THEN the system SHALL return the compact candidate details
- AND SHALL state that the candidate is not durable behavior until promoted.

#### Scenario: Human status update

- GIVEN a safe runtime lesson candidate exists
- WHEN `update_staffany_data_lesson_candidate_status` is called with a human reviewer, review notes, and `approval_marker="human reviewed lesson"`
- THEN the system SHALL update only the profile-runtime JSON status
- AND SHALL append a review-history event
- AND SHALL NOT mutate BigQuery, Slack, Honcho, repo files, GitHub, Kanban, persistent goals, or self-evolution state.

#### Scenario: Review status update blocks self-approval

- GIVEN a safe runtime lesson candidate exists
- WHEN a bot, automation, agent, or system reviewer identity tries to approve, reject, or promote the candidate
- THEN the system SHALL return `Confidence: blocked`
- AND SHALL leave the candidate unchanged.

#### Scenario: Review status update requires explicit marker

- GIVEN a safe runtime lesson candidate exists
- WHEN a status update omits the exact `approval_marker="human reviewed lesson"`
- THEN the system SHALL return `Confidence: blocked`
- AND SHALL leave the candidate unchanged.

#### Scenario: Needs more evidence

- GIVEN a safe runtime lesson candidate exists
- WHEN a human reviewer marks it `needs_more_evidence`
- THEN the candidate SHALL remain inactive behavior
- AND SHALL be filterable by `needs_more_evidence`.

### Requirement: Slack Learning Capture

The bot SHALL capture explicit reusable learning requests as candidates, not as immediate active behavior.

#### Scenario: Explicit learning request

- GIVEN a Slack user says `learn this for next time`
- WHEN the proposed lesson is reusable and safe
- THEN the bot SHALL call `record_staffany_data_lesson_candidate`
- AND SHALL reply that the candidate was recorded for review.

#### Scenario: One-off fact

- GIVEN a user asks the bot to remember a one-off customer/org/result fact
- WHEN that fact belongs in BigQuery, Customer 360, Slack evidence, or a repo registry
- THEN the bot SHALL refuse to store it as durable truth
- AND SHALL explain the correct source boundary.

#### Scenario: Sensitive learning request

- GIVEN a user asks the bot to remember raw Slack transcripts, raw query rows, tokens, credentials, PII, bank details, NRIC/FIN, phone numbers, or employee-level payroll detail
- WHEN the bot evaluates the request
- THEN the bot SHALL refuse before storing or querying
- AND SHALL offer a safe behavior-level summary only when possible.

### Requirement: Promotion Boundary

The system SHALL keep runtime learning separate from durable behavior.

#### Scenario: Candidate not active behavior

- GIVEN a candidate exists with status `pending_review`
- WHEN a later Slack question hits the same topic
- THEN the bot SHALL NOT treat the candidate as canonical behavior
- AND SHALL use repo references, BigQuery, Customer 360, or approved registries first.

#### Scenario: Approved promotion

- GIVEN a human approves a candidate
- WHEN an implementer promotes it
- THEN the smallest durable repo surface SHALL be updated
- AND verification, deploy, and live check SHALL pass before marking the candidate `promoted`.

#### Scenario: Promoted requires repo and live evidence

- GIVEN a candidate is `approved_for_repo_promotion`
- WHEN `update_staffany_data_lesson_candidate_status` requests `promoted` without `repo_commit_sha`, `live_verified_at`, or `live_verification_summary`
- THEN the system SHALL return `Confidence: blocked`
- AND SHALL leave the candidate not promoted.

#### Scenario: Honcho conflict

- GIVEN Honcho memory conflicts with local registry references, BigQuery schema evidence, Customer 360, or explicit current-thread context
- WHEN the bot answers
- THEN the bot SHALL prefer the stronger source
- AND SHALL not use Honcho as StaffAny source of truth.

#### Scenario: Same-session memory caveat

- GIVEN the bot records a lesson candidate or memory during a Slack thread
- WHEN the same Slack session continues
- THEN the bot SHALL rely on the returned candidate ID and explicit current-thread context
- AND SHALL NOT assume memory/provider context has changed active behavior mid-thread.

### Requirement: Hermes Learning Primitive Boundaries

The system SHALL map each Hermes learning primitive to one bounded role.

#### Scenario: Honcho safe configuration

- GIVEN Honcho is enabled for `staffanydatabot`
- WHEN live-profile audit or health verification runs
- THEN the system SHALL verify a safe recall-oriented configuration including `recallMode=tools`, `saveMessages=false`, `sessionStrategy=per-session`, and bounded context policy
- AND SHALL block or warn when broad auto-injection or message persistence could expose raw Slack/data context.

#### Scenario: Runtime skill drift

- GIVEN Hermes creates a runtime skill or Curator patches an agent-created skill
- WHEN the source-packet audit runs
- THEN the system SHALL treat the runtime skill change as review evidence only
- AND SHALL require promotion into `apps/hermes-data-bot` before it changes durable Slack behavior.

#### Scenario: No-agent review report

- GIVEN lesson candidates exist in the runtime store
- WHEN the no-agent review report runs
- THEN the report SHALL print safe metadata only, including total count, pending count, oldest pending age, and counts by status/risk
- AND SHALL NOT print raw lesson text, Slack transcript snippets, query rows, or sensitive data.
- AND SHALL remain count/staleness-only by default for Da Ta Hermz.

#### Scenario: Kanban and self-evolution stay out of V1

- GIVEN the reviewed-learning loop is deployed in V1
- WHEN a candidate is recorded
- THEN the system SHALL NOT create a Kanban task, start a persistent goal, run GEPA/self-evolution, or auto-open a PR
- AND SHALL leave those as explicit future options behind human review.

### Requirement: Verification

The system SHALL verify the learning loop locally and in the live profile.

#### Scenario: Local verifier

- GIVEN the packet changes are implemented
- WHEN `npm run hermes-data-bot:verify` runs
- THEN it SHALL check the learning MCP, required docs, config wiring, Honcho safety expectations, no-agent review-report behavior, and unit tests.

#### Scenario: Live smoke

- GIVEN the deployed `staffanydatabot` profile is updated
- WHEN a safe Slack learning smoke runs in `#da-ta-hermz-testing`
- THEN the candidate SHALL be recorded and readable through the bot-owned MCP path
- AND no raw transcript, token, or sensitive data SHALL be persisted.
