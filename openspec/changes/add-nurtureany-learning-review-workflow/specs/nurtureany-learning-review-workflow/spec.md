# Specification: NurtureAny Learning Review Workflow

## ADDED Requirements

### Requirement: Runtime lesson candidates are surfaced by safe digest

A weekday no-agent cron SHALL read `lesson-candidates/*.json` and post only pending safe summaries to an allowlisted internal Slack channel with prefix `NurtureAny automation:`.

#### Scenario: Empty queue

- GIVEN no pending lesson candidates
- WHEN the digest runs
- THEN it exits successfully and posts nothing

#### Scenario: Pending candidates

- GIVEN one or more pending lesson candidates
- WHEN the digest runs
- THEN each item includes lesson id, created date, source permalink, proposed rule, target repo surface, risk, and recommended reviewer action
- AND it excludes raw Slack transcripts, raw HubSpot rows, phone numbers, secrets, and contact exports

### Requirement: Human review gates repo promotion

The bot SHALL NOT self-approve lesson candidates.

#### Scenario: Reviewer approves

- GIVEN a human approves a lesson for repo promotion
- WHEN the status is updated
- THEN the candidate becomes `approved_for_repo_promotion`
- AND the durable change must target the smallest repo surface: skill reference, `SOUL.md`, MCP contract, config template, regression case, or runbook

#### Scenario: Reviewer asks for evidence

- GIVEN a human decides the candidate is plausible but under-evidenced
- WHEN the status is updated
- THEN the candidate becomes `needs_more_evidence`
- AND it remains inactive behavior

### Requirement: Promotion requires verification

A candidate SHALL become `promoted` only after local verify, deploy, and live checks are recorded.

#### Scenario: Missing promotion evidence

- GIVEN a candidate is approved for repo promotion
- WHEN a status update requests `promoted` without repo commit and live-verification metadata
- THEN the update is blocked

### Requirement: Kanban is implementation lifecycle only

Kanban SHALL NOT be used for the first review digest or approval storage. Kanban MAY be used after approval for multi-step implementation work requiring owner, comments, run history, queue dispatch, or PR review.

#### Scenario: Approved lesson needs a code change

- GIVEN a candidate is `approved_for_repo_promotion`
- WHEN the change requires multi-step repo implementation
- THEN a Kanban task MAY be created for `nurtureany-lesson-promotion:<lesson_id>`
- AND worker output must stop at a PR, diff, or `review-required:` block until human review
