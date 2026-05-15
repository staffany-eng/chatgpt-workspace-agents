# OpenAI Voice For Call Coaching

## Scope

This synthesis translates OpenAI's official voice-model articles, developer docs, and voice-safety papers into NurtureAny call-coaching architecture guidance. It is capability and safety evidence only. It does not create live-call access, Aircall streaming, WhatsApp call access, or a deployed live-coaching workflow.

## Source Base

- OpenAI Voice Intelligence: [source note](../sources/openai-voice-intelligence.md), [raw record](../../raw/openai-voice-intelligence/source-extract.md).
- Gong-Inspired Call Coaching: [synthesis](./gong-inspired-call-coaching.md).
- NurtureAny source packet: `apps/nurtureany-sales-bot/`.

## Source Hierarchy

1. HubSpot and live tools remain source of truth for account, owner, contact, activity, task, deal, and CRM hygiene facts.
2. StaffAny sales materials remain source of truth for I-C-BANT, demo quality, follow-up, QO/QO Met, and 0/1/2 coaching semantics.
3. Aircall selected-call metadata and recording access are the current call-artifact path.
4. OpenAI voice docs are technical evidence for transcription, realtime speech, voice-agent architecture, and safety boundaries.
5. Gong docs remain design-pattern evidence for coaching output shape only.

## Imported Pattern

- Do not treat voice as transcription only. OpenAI's current voice model stack separates live voice agents, live translation, live transcription, file transcription, and text-to-speech.
- Choose architecture based on product need:
  - Post-call review: chained pipeline with selected recording, bounded transcript/audio evidence, rubric, and manager note.
  - Live captions or live call notes: realtime transcription with transcript deltas.
  - Live spoken coaching or voice assistant: speech-to-speech realtime session with tools, guardrails, and explicit interruption/unclear-audio handling.
- Test voice workflows with real telephony audio, accents, background noise, domain terms, code-switching, numbers, and long sessions before treating outputs as dependable.
- Prompting for live voice needs short, conflict-free rules, explicit unclear-audio behavior, language handling, and variation controls.
- Safety policy must block unsupported inference from audio: hidden emotion, speaker identity, protected traits, mental state, or intent beyond observable cues.

## NurtureAny V1 Contract

Current NurtureAny selected-call coaching should stay:

1. HubSpot selected call candidate and account truth.
2. Aircall selected recording lookup when an Aircall ID exists or can be safely matched.
3. `analyze_aircall_call_coaching` for that selected recording: OpenAI bounded transcription, local transcript/timing interaction metrics, and OpenAI structured coaching review.
4. Gong-inspired output: answer, 0/1/2 scorecard, coachable moments, observable tone/interaction cues, manager note, next action, source/scope/confidence/caveat.

This remains a post-call coaching workflow. It is not live sales coaching and not live listen-in.

## Future Live-Coaching Gate

Before NurtureAny can coach live, StaffAny would need all of these:

- A consented live audio source from Aircall, SIP, or another telephony layer.
- Clear policy for call participant notice, recording, retention, and redaction.
- A live transcript path, likely GPT-Realtime-Whisper if transcript deltas are enough.
- A live voice-agent path, likely GPT-Realtime-2 only if the assistant needs to speak, reason, or use tools during the call.
- A manager/rep UI that avoids distracting the rep and keeps advice short.
- Eval data from real StaffAny sales calls, including noisy audio, accents, domain terms, numbers, and objections.
- Regression rules that prevent raw transcript dumps, phone numbers, hidden-emotion claims, and CRM truth overwrite.

## Deep Voice Reading List

- Current API release: OpenAI's May 2026 voice intelligence article.
- Architecture docs: Realtime overview, voice agents, realtime transcription, and gpt-realtime-2 model docs.
- Production voice-agent context: August 2025 gpt-realtime release.
- Post-call transcription context: March 2025 next-generation audio models and Whisper.
- Safety context: GPT-4o System Card.
- Human factors context: OpenAI/MIT affective-use and emotional well-being paper.
- Prompting context: Realtime prompting guide.

## Implementation Implications

- Update NurtureAny prompt references to say OpenAI realtime models are future architecture evidence, not current live-call access.
- Keep the current Aircall adapter on selected-call post-call coaching through `analyze_aircall_call_coaching` until a live stream exists.
- When users ask whether the new OpenAI model can pick up tone, answer: possible for observable audio/interaction cues, but only when raw audio or an approved audio-native analysis path is actually checked.
- When users ask whether NurtureAny can listen live, answer: not from OpenAI alone. Need telephony access, consent, realtime routing, and safety/eval work.
