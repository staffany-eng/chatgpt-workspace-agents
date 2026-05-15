# Gong-Inspired Call Coaching

## Scope

This synthesis translates Gong's public coaching workflow into NurtureAny selected-call coaching behavior. It is product-pattern evidence only. It does not create a Gong integration, Gong data source, or Gong parity claim.

## Source Base

- Gong Coaching Public Docs: [source note](../sources/gong-coaching-public-docs.md), [raw record](../../raw/gong-coaching/source-extract.md).
- NurtureAny Sales Best Practices: [synthesis](./nurtureany-sales-best-practices.md).
- NurtureAny source packet: `apps/nurtureany-sales-bot/`.

## Source Hierarchy

1. HubSpot and live tool outputs remain source of truth for account, owner, country, contacts, calls, meetings, tasks, notes, deals, follow-up, and CRM hygiene.
2. StaffAny Tactical Pause and current sales training materials remain the source of truth for sales operating rhythm, I-C-BANT, demo quality, follow-up, and 0/1/2 coaching score semantics.
3. Aircall selected-call metadata and OpenAI transcription/audio analysis are call-artifact enrichment only.
4. Gong public docs are design inspiration for coaching workflow shape, scorecard UX, call evidence organization, and trend/review loops.

## Imported Pattern

- Selected call review should start with the call outcome, not a transcript dump.
- Structured feedback should be scored against explicit dimensions so managers can compare calls and coach consistently.
- Evidence should be tied to moments in the call: timestamps, speaker context, objection moments, customer reaction moments, and next-step handling.
- Interaction-style cues are useful when available: talk ratio, interactivity, patience, longest monologue, customer story length, and question balance.
- Trackers/topics map to StaffAny business priorities: pricing, payroll risk, attendance accuracy, outlet operations, current tools, competitor/custom-build objections, decision process, timeline, and follow-up commitment.
- Manager feedback should be copy-ready: one praise, one correction, one practice assignment, and one next action.
- Trend loops come later: once enough calls are reviewed, manager dashboards can group recurring weak dimensions by rep/team.

## NurtureAny V1 Contract

Selected-call coaching output should use this order:

1. `Answer:` short call assessment.
2. `Scorecard:` 0/1/2 rows with concise evidence.
3. `Coachable moments:` timestamps and concise notes.
4. `Tone / interaction cues:` observable cues only. For transcript/timing-only V1, say interaction cues were checked from transcript/timing and audio-native tone was not checked.
5. `Manager coaching note:` copy-ready feedback.
6. `Next action:` the rep's next step.
7. `Source / Scope / Confidence / Caveat`.

The scorecard dimensions are:

- Discovery.
- I-C-BANT.
- Talk ratio.
- Interactivity.
- Patience.
- Monologue length.
- Objections.
- Next step.
- CRM hygiene.
- Customer reaction moments.
- StaffAny value framing.

Use 0/1/2 semantics:

- `0 = missed`.
- `1 = partial`.
- `2 = strong`.

## Safety Boundary

- Do not claim Gong is connected.
- Do not call Gong APIs.
- Do not add Gong credentials, MCP servers, webhooks, or ingestion jobs.
- Do not return raw transcripts, raw audio, recording URLs, phone numbers, or bulk call exports.
- Do not infer hidden emotion. Phrase tone/audio as observable evidence, for example `prospect answers shortened after pricing` or `rep overlapped twice after objection`, not `prospect was angry`.
- If only transcript/timing is available, write `Interaction cues checked from transcript/timing` and `Tone/audio cues: audio-native tone not checked`.
- If a future approved audio-native analysis runs, write `Tone/audio cues checked from recording` and still avoid emotion certainty.

## Implementation Implications

- Keep NurtureAny's skill and SOUL prompt pointed at `analyze_aircall_call_coaching` for selected Aircall call review.
- Keep `sales-best-practices.md` on the 0/1/2 StaffAny rubric without relying on Gong.
- Keep `sop-tool-coverage.md` and `runtime/aircall.md` clear: HubSpot truth, Aircall/OpenAI enrichment, Gong design only.
- Keep regression cases for structure, no Gong integration claim, no raw transcript/audio/phone-number exposure, transcript/timing-only tone caveat, and HubSpot source-of-truth preservation.
