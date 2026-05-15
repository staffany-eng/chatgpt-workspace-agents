# ElevenLabs Voice Stack

## Source Metadata

- Type: official ElevenLabs public documentation, API reference, and blog ingest
- Source class: ElevenLabs speech-to-text, realtime transcription, voice agents, telephony, post-call analysis, retention, and audio-processing sources
- Source URL or path: https://elevenlabs.io/
- Date ingested: 2026-05-15
- Context: technical capability and architecture evidence for NurtureAny call-coaching boundaries
- Default weight: 5 for ElevenLabs product behavior; lower than HubSpot or StaffAny sales materials for NurtureAny business truth
- Privacy: public docs and articles only; no StaffAny data, recordings, transcripts, secrets, or customer PII copied

## Context Caveat

These sources are official ElevenLabs evidence for voice-stack capabilities and product architecture.
They do not prove StaffAny has live Aircall audio access, WhatsApp call access, SIP routing,
participant consent, approved vendor credentials, or a deployed ElevenLabs integration. For NurtureAny,
HubSpot remains account truth and Aircall/OpenAI remain the current selected-call artifact path.

## Evidence Used

- Raw record: [research/raw/elevenlabs-voice-stack/source-extract.md](../../raw/elevenlabs-voice-stack/source-extract.md)

## What They Said

- ElevenLabs describes itself as AI voice infrastructure for text-to-speech, speech-to-text, voice cloning, conversational agents, and generative audio through REST API, Python SDK, TypeScript SDK, and web app.
- The models page lists Scribe v2 for speech recognition and Scribe v2 Realtime for realtime speech recognition, alongside speech generation and speech-to-speech models.
- Scribe v2 is positioned as STT in 90+ languages with keyterm prompting, entity detection, word timestamps, diarization up to 32 speakers, dynamic audio tagging, and smart language detection.
- The STT API can transcribe audio or video, run asynchronously through webhooks, support multichannel transcripts, and return webhook metadata for correlation.
- Scribe v2 Realtime uses WebSockets for streaming audio input and returns partial, committed, and timestamped transcript results.
- Realtime transcript commits can be manual or voice-activity-detection based; docs also describe PCM and u-law input formats and chunk-size guidance.
- ElevenAgents analysis supports success evaluation, data collection, conversation search, and post-call analytics over transcripts.
- Success evaluation returns `success`, `failure`, or `unknown` with rationale against custom transcript criteria.
- Post-call webhooks can deliver transcription, audio, or call-initiation-failure events and require HMAC signature validation.
- Twilio native integration and SIP trunking show ElevenLabs can sit in telephony infrastructure, but those docs do not provide Aircall or WhatsApp access by themselves.
- Retention docs say agent conversation data defaults to two-year retention unless configured, and Zero Retention Mode is an enterprise control with product limitations.
- Voice Isolator, Voice Changer, and Dubbing show audio-stack handling of noise and delivery cues, but they do not justify hidden-emotion inference for sales coaching.

## Evidence Trace

- Claim: ElevenLabs provides broad AI voice infrastructure. Evidence: Raw extract summarizes REST/SDK/web access for TTS, STT, voice cloning, agents, and generative audio. Source: `research/raw/elevenlabs-voice-stack/source-extract.md:45`.
- Claim: Scribe models are the speech-recognition path. Evidence: Raw extract lists Scribe v2 and Scribe v2 Realtime under model families. Source: `research/raw/elevenlabs-voice-stack/source-extract.md:46`.
- Claim: Scribe v2 supports rich post-call transcript evidence. Evidence: Raw extract lists 90+ languages, keyterms, entities, timestamps, diarization, audio tags, and language detection. Source: `research/raw/elevenlabs-voice-stack/source-extract.md:47`.
- Claim: Dynamic audio tags are observable non-speech events. Evidence: Raw extract names `audio_event` examples such as laughter, applause, and footsteps. Source: `research/raw/elevenlabs-voice-stack/source-extract.md:48`.
- Claim: Batch STT supports large audio/video files and multichannel. Evidence: Raw extract records 3 GB, 10-hour standard mode, and up to 5 channels. Source: `research/raw/elevenlabs-voice-stack/source-extract.md:49`.
- Claim: The STT API has async and correlation support. Evidence: Raw extract records webhook mode, multichannel transcripts, and webhook metadata. Source: `research/raw/elevenlabs-voice-stack/source-extract.md:50`.
- Claim: Realtime STT is WebSocket based. Evidence: Raw extract says realtime input returns partial, committed, and timestamped transcription results. Source: `research/raw/elevenlabs-voice-stack/source-extract.md:52`.
- Claim: Realtime commit strategy matters. Evidence: Raw extract records partial versus committed transcripts, optional word timestamps, manual commit, VAD, formats, and chunk guidance. Source: `research/raw/elevenlabs-voice-stack/source-extract.md:54`.
- Claim: ElevenAgents includes transcript analysis patterns. Evidence: Raw extract lists success evaluation, data collection, search, and post-call analytics. Source: `research/raw/elevenlabs-voice-stack/source-extract.md:60`.
- Claim: Success evaluation resembles scorecard-style criteria. Evidence: Raw extract says criteria return success, failure, or unknown with rationale for sales, objection, conversion, compliance, and training examples. Source: `research/raw/elevenlabs-voice-stack/source-extract.md:61`.
- Claim: Post-call webhooks have security requirements. Evidence: Raw extract lists post-call webhook event types, transcript/analysis payloads, HMAC validation, and IP allowlist guidance. Source: `research/raw/elevenlabs-voice-stack/source-extract.md:62`.
- Claim: Telephony support is possible but not equivalent to Aircall or WhatsApp access. Evidence: Raw extract records Twilio, SIP trunking, PBX routing, headers, and TLS/media settings. Source: `research/raw/elevenlabs-voice-stack/source-extract.md:64`.
- Claim: Retention is a first-class design issue. Evidence: Raw extract records two-year default agent retention and enterprise ZRM controls. Source: `research/raw/elevenlabs-voice-stack/source-extract.md:69`.
- Claim: Tone-like cues must stay observable. Evidence: Raw extract names voice isolation, delivery nuance, and dubbing tone preservation but local notes reject hidden-emotion certainty. Source: `research/raw/elevenlabs-voice-stack/source-extract.md:71`.

## Learning Summary

- ElevenLabs is useful as alternative/future technical evidence: Scribe v2 for post-call STT, Scribe v2 Realtime for live transcript deltas, ElevenAgents for deployed voice agents, and Twilio/SIP for telephony integration.
- The docs do not make NurtureAny live-coaching capable. Live coaching still needs a consented live audio source, participant notice, routing adapter, retention policy, evals, and approved credentials.
- For "tone and other stuff," the safe feature set is observable: diarization, word timestamps, pauses, silences, overlap, language switches, transcript segment timing, and non-speech audio events.
- ElevenLabs webhook, retention, and Zero Retention Mode docs reinforce that call-coaching architecture must be designed around privacy and security before any pilot.
- NurtureAny V1 should keep the current executable path: selected Aircall recording -> OpenAI transcription/audio evidence -> StaffAny scorecard.

## Synthesis Gate

- Mode: autonomous_current_focus_synthesis
- Status: completed
- Focus source: ElevenLabs official voice docs, API references, and public Scribe v2 articles.
- Evidence weight check: default weight 5 for ElevenLabs capability evidence; does not override HubSpot, StaffAny sales materials, or NurtureAny runtime truth.
- Output: synthesize as future/alternative voice-stack architecture evidence, not as a current NurtureAny source, integration, or live-call access proof.

## Possible Agent Builder Relevance

- Agent-synthesized: Add ElevenLabs to NurtureAny's voice architecture reading as alternative/future evidence beside OpenAI, not as a provider switch.
- Agent-synthesized: Keep selected-call review source-agnostic and bounded; ElevenLabs should not be named as current provider unless a future adapter exists.
- Agent-synthesized: If StaffAny pilots ElevenLabs later, require consent, telephony routing, retention/ZRM decision, webhook HMAC validation, raw audio redaction, and evals.
- Do-not-promote: Do not claim NurtureAny uses ElevenLabs, has ElevenLabs credentials, can join WhatsApp calls, or can route Aircall audio through ElevenLabs today.
- Do-not-promote: Do not infer hidden emotion, speaker identity, protected traits, or psychological state from voice/audio.

## Follow-Up Questions

- Should StaffAny compare OpenAI and ElevenLabs on the same consented historical Aircall sample before deciding whether a future voice-stack pilot is worth building?
