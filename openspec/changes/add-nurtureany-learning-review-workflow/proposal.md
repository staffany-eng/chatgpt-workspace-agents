# OpenSpec: Add NurtureAny Learning Review Workflow

## Summary

NurtureAny reviewed lessons must be promoted through human-gated repo changes, not automatic memory. Runtime lesson candidates stay JSON-only until reviewed.

The workflow is:

- Runtime tools capture safe lesson candidates.
- A no-agent weekday digest surfaces pending candidates to an allowlisted internal Slack review channel.
- A human reviewer chooses `rejected`, `needs_more_evidence`, or `approved_for_repo_promotion`.
- Approved lessons become repo changes in the smallest durable surface.
- Only after local verify, deploy, and live check may the candidate be marked `promoted`.

## Evidence Used

- Hermes Profiles docs: profiles keep separate config, `.env`, `SOUL.md`, memory, sessions, skills, cron jobs, and gateway state.
- Hermes Cron docs: no-agent mode runs scheduled scripts, delivers stdout verbatim, and stays silent on empty stdout.
- Hermes Kanban worker-lanes docs: Kanban owns task lifecycle and audit trail; worker lanes execute assigned cards; reviewers gate done.
- Hermes Curator docs: Curator reviews agent-authored skills in `~/.hermes/skills/`, not app-specific runtime JSON lessons.
- NurtureAny reviewed-lessons packet and Hermes runtime operating-model synthesis.

## Problem

Current `record_nurtureany_lesson_candidate`, `list_nurtureany_lesson_candidates`, and `read_nurtureany_lesson_candidate` tools capture runtime candidates, but there is no deterministic review surface and no narrow status-transition primitive.

As a result, useful learning can sit in `lesson-candidates/*.json` without being surfaced for review, while the bot correctly refuses to treat runtime candidates as durable behavior.

## Goals

- Add a no-agent weekday Slack digest for pending lesson candidates.
- Keep empty pending queues silent.
- Add explicit review state transitions, including `needs_more_evidence`.
- Block bot self-approval.
- Require repo verify, deploy, and live check before `promoted`.
- Keep Honcho, memory, and Curator out of the approval store.
- Use Kanban only after approval when a repo implementation task needs ownership, comments, run history, queue dispatch, or PR review.
- Treat the existing smoke candidate as reject/archive evidence, not product behavior.
- Review the existing Lusha LinkedIn URL fallback candidate as an `mcp_contract` repo-promotion candidate.

## Non-Goals

- No automatic behavior change from runtime candidates.
- No Honcho or memory approval store.
- No Hermes Curator usage for NurtureAny lesson candidates.
- No direct GitHub push or main-branch mutation from the NurtureAny runtime bot.
- No Kanban for the first review digest.
