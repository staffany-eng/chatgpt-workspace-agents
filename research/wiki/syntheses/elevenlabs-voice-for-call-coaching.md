# ElevenLabs Voice For Call Coaching

## Scope

This synthesis translates ElevenLabs public voice-stack docs into NurtureAny call-coaching architecture guidance.
It is technical capability evidence only. It does not create a NurtureAny ElevenLabs integration, Aircall live stream,
WhatsApp call access, SIP routing, consent coverage, or a deployed live-coaching workflow.

## Source Base

- ElevenLabs Voice Stack: [source note](../sources/elevenlabs-voice-stack.md), [raw record](../../raw/elevenlabs-voice-stack/source-extract.md).
- OpenAI Voice Intelligence: [source note](../sources/openai-voice-intelligence.md), [raw record](../../raw/openai-voice-intelligence/source-extract.md).
- Gong-Inspired Call Coaching: [synthesis](./gong-inspired-call-coaching.md).
- NurtureAny source packet: `apps/nurtureany-sales-bot/`.

## Source Hierarchy

1. HubSpot and live tools remain source of truth for account, owner, contact, activity, task, deal, and CRM hygiene facts.
2. StaffAny sales materials remain source of truth for I-C-BANT, demo quality, follow-up, QO/QO Met, and 0/1/2 coaching semantics.
3. Aircall selected-call metadata plus OpenAI transcription/audio analysis are the current call-artifact path.
4. OpenAI and ElevenLabs voice docs are technical capability and safety evidence only.
5. Gong public docs remain design-pattern evidence for coaching output shape only.

## Imported Pattern

- Scribe v2 is a credible future option for post-call transcription features: diarization, word timestamps, dynamic audio tags, entity detection, keyterm prompting, and multichannel support.
- Scribe v2 Realtime is a future option for live transcript deltas when StaffAny has a consented live audio stream.
- ElevenAgents, Twilio native integration, SIP trunking, and batch calls show possible telephony/voice-agent architectures, but they are not current Aircall or WhatsApp access.
- Success Evaluation and data collection resemble scorecard-style review, but they are transcript/agent criteria patterns, not StaffAny sales truth.
- Post-call webhooks require HMAC validation, careful retry/error handling, raw-payload controls, and explicit redaction.
- Retention and Zero Retention Mode need product decisions before any real call-audio pilot.

## NurtureAny V1 Contract

Current NurtureAny selected-call coaching should stay:

1. HubSpot selected call candidate and account truth.
2. Aircall selected recording lookup when an Aircall ID exists or can be safely matched.
3. `analyze_aircall_call_coaching` for that selected recording: OpenAI bounded transcription, local transcript/timing interaction metrics, and OpenAI structured coaching review.
4. StaffAny/Gong-inspired output: answer, 0/1/2 scorecard, coachable moments, observable tone/interaction cues, manager note, next action, source/scope/confidence/caveat.

ElevenLabs is not part of this runtime path today. Do not mention it as a source unless the user asks about future voice architecture or vendor options.

## Future Pilot Gate

Before NurtureAny can use ElevenLabs for call coaching, StaffAny would need all of these:

- Consented live or post-call audio source from Aircall, SIP, Twilio, or another approved telephony layer.
- Participant notice, recording policy, retention policy, and redaction policy.
- Approved ElevenLabs credentials and budget/cost reporting.
- Explicit choice between Scribe post-call STT, Scribe Realtime transcript deltas, or ElevenAgents as a spoken agent.
- Webhook HMAC validation and IP allowlisting when webhooks are used.
- Zero Retention Mode decision, with product limitations documented.
- Evals on real StaffAny sales calls covering noisy audio, accents, domain terms, numbers, code-switching, pauses, and objections.
- Regression rules that prevent raw transcript dumps, raw audio exposure, phone numbers, hidden-emotion claims, and CRM truth overwrite.

## Implementation Implications

- Update NurtureAny prompt references to say ElevenLabs is alternative/future technical evidence, not a current provider.
- Keep the Aircall adapter on selected-call post-call coaching through OpenAI until a separate ElevenLabs adapter is approved and implemented.
- When users ask whether ElevenLabs can pick up tone, answer: it can provide observable audio/transcript cues, but NurtureAny should not infer hidden emotions as fact.
- When users ask whether ElevenLabs enables live sales coaching, answer: not by itself. Live coaching requires telephony access, consent, routing, retention, and eval work.
- If a future vendor bakeoff happens, compare OpenAI and ElevenLabs on the same consented historical Aircall sample and score WER, diarization, timestamps, latency, event tags, redaction, and safety.
