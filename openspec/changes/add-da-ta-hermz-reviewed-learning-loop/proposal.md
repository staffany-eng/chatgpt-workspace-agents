# OpenSpec: Da Ta Hermz Reviewed Learning Loop

## Summary

Add a reviewed self-learning loop for Da Ta Hermz. Live Slack usage can produce safe `pending_review` lesson candidates, but candidates do not change bot behavior until a human promotes them into the source-controlled app packet, verifies, deploys, and live-checks them.

The V1 loop is reviewed lesson capture, not autonomous behavior mutation. Hermes memory, skills, Curator, cron, Kanban, persistent goals, and offline self-evolution are separate primitives with separate jobs.

## Evidence Used

- Live `#da-ta-hermz-testing` bot-token check: `staffanydatabot` can read the channel and recent threads have real bot interactions.
- Live memory check: Honcho is available, but only 5 conclusions exist and all were created on `2026-05-09`; current Slack interactions are not creating fresh learning.
- Existing Da Ta Hermz packet: Honcho is recall-only and durable behavior belongs in `apps/hermes-data-bot`.
- Existing NurtureAny reviewed-lessons pattern: runtime candidates are safe, reviewable evidence, not active behavior.
- Recent Hermes docs: memory providers can auto-inject and sync context, skills can be agent-managed procedural memory, Curator maintains agent-created skills, cron runs isolated scheduled sessions, Kanban gives durable review queues, persistent goals continue sessions, and self-evolution/GEPA can propose optimized skill variants behind tests and PR review.

## Problem

Da Ta Hermz appears to answer and handle corrections in Slack, but there is no enforced loop that captures reusable corrections as reviewable learning. Honcho alone is too passive and too ambiguous: it can recall preferences, but it should not become canonical StaffAny product, metric, or workflow truth.

## Goals

- Add an explicit reviewed-learning candidate path for reusable Slack corrections.
- Keep candidate storage runtime-local and safe.
- Make the bot visibly distinguish `candidate recorded` from `active behavior`.
- Provide list/read/status-update tools so an operator can review candidates and record human decisions.
- Add a Hermes learning-primitives matrix so memory, skills, Curator, cron, Kanban, persistent goals, and self-evolution are not collapsed into one vague learning layer.
- Tighten Honcho safety requirements: `recallMode=tools`, `saveMessages=false`, `sessionStrategy=per-session`, bounded context, and audit coverage.
- Treat runtime-created or Curator-patched skills as review artifacts until promoted into the source packet.
- Add a no-agent candidate review cadence that reports safe counts and stale pending candidates only.
- Add human-gated status transitions with `needs_more_evidence`, reviewer notes, an exact approval marker, self-approval blocking, and deploy/live evidence before `promoted`.
- Promote approved learnings into the smallest durable repo surface: skill reference, SOUL, MCP contract, config template, regression case, runbook, research wiki, or app manifest.
- Cover the loop with verifier checks, unit tests, regression cases, deploy audit, and live Slack smoke.

## Non-Goals

- No silent auto-learning that changes future behavior immediately.
- No auto-commit, auto-push, or direct bot writes to `main`.
- No storage of raw Slack transcripts, raw BigQuery rows, customer/org facts, secrets, tokens, PII, phone numbers, bank details, NRIC/FIN, or employee payroll detail.
- No use of Honcho as source of truth for metrics, product terminology, customer facts, or approval state.
- No Kanban dispatch or reviewer queue in V1; keep it as a V2 option if candidate volume needs durable task lifecycle and reviewer gates.
- No GEPA/self-evolution pipeline in V1; future offline optimization may propose PRs only after evals, size/semantic gates, tests, and human review.
- No persistent-goal continuation for Slack learning capture; Slack learning remains explicit and bounded to the current request.
