# ElevenLabs Voice Stack Source Extract

## Source Metadata

- Type: official ElevenLabs public documentation, API reference, and blog extract
- Source class: ElevenLabs speech-to-text, realtime transcription, voice agents, telephony, post-call analysis, retention, and audio-processing sources
- Base URL: https://elevenlabs.io/
- Date checked: 2026-05-15
- Date ingested: 2026-05-15
- Retrieved by: Codex web browser and `curl` against ElevenLabs docs `.md` and public HTML pages
- Privacy: public docs and public articles; no StaffAny data, private audio, call recording, transcript, credential, or customer PII copied

## Raw Content Policy

This record preserves short, source-attributed evidence notes from public ElevenLabs sources. It does not copy full docs, full API specs, full code samples, pricing tables, private eval data, recordings, transcripts, credentials, or customer data. Treat these sources as vendor capability, architecture, retention, and safety evidence only. They do not prove StaffAny has a live Aircall stream, WhatsApp call access, participant consent, or a deployed ElevenLabs integration.

## Source Inventory

| Source | URL | Date or status | Evidence focus |
| --- | --- | --- | --- |
| ElevenLabs Documentation introduction | https://elevenlabs.io/docs/overview/intro | checked 2026-05-15 | Platform overview, REST API/SDKs, TTS, STT, voice cloning, agents, generative audio |
| Models | https://elevenlabs.io/docs/overview/models | checked 2026-05-15 | Scribe v2, Scribe v2 Realtime, Eleven v3, Flash v2.5, speech-to-speech, model selection |
| Speech to Text capability | https://elevenlabs.io/docs/overview/capabilities/speech-to-text | checked 2026-05-15 | Scribe v2, Scribe v2 Realtime, diarization, timestamps, dynamic audio tagging, file limits |
| Create transcript API | https://elevenlabs.io/docs/api-reference/speech-to-text/convert | checked 2026-05-15 | `/v1/speech-to-text`, webhook mode, multichannel, audio events, diarization, `enable_logging=false` |
| Realtime STT API | https://elevenlabs.io/docs/api-reference/speech-to-text/v-1-speech-to-text-realtime | checked 2026-05-15 | WebSocket STT, partial and committed transcripts, manual/VAD commit, API key or token auth |
| Server-side streaming STT | https://elevenlabs.io/docs/eleven-api/guides/how-to/speech-to-text/realtime/server-side-streaming | checked 2026-05-15 | Server-side realtime transcription from URL, file, or custom audio stream |
| Transcripts and commit strategies | https://elevenlabs.io/docs/eleven-api/guides/how-to/speech-to-text/realtime/transcripts-and-commit-strategies | checked 2026-05-15 | Partial transcripts, committed transcripts, timestamps, manual commit, VAD, supported audio formats |
| Conversation analysis | https://elevenlabs.io/docs/eleven-agents/customization/agent-analysis | checked 2026-05-15 | Success evaluation, data collection, search, post-call analytics |
| Success Evaluation | https://elevenlabs.io/docs/eleven-agents/customization/agent-analysis/success-evaluation | checked 2026-05-15 | Custom transcript criteria returning success, failure, or unknown with rationale |
| Post-call webhooks | https://elevenlabs.io/docs/eleven-agents/workflows/post-call-webhooks | checked 2026-05-15 | Transcription webhooks, audio webhooks, call failure webhooks, HMAC verification, metadata |
| Twilio native integration | https://elevenlabs.io/docs/eleven-agents/phone-numbers/twilio-integration/native-integration | checked 2026-05-15 | Inbound/outbound calls through Twilio numbers and verified caller IDs |
| SIP trunking | https://elevenlabs.io/docs/eleven-agents/phone-numbers/sip-trunking | checked 2026-05-15 | Connect existing PBX/SIP telephony, inbound/outbound calls, TLS/media encryption, SIP headers |
| Batch calling | https://elevenlabs.io/docs/eleven-agents/phone-numbers/batch-calls | checked 2026-05-15 | Outbound batch calls, recipient uploads, dynamic variables, compliance warning, ZRM limitation |
| Retention | https://elevenlabs.io/docs/eleven-agents/customization/privacy/retention | checked 2026-05-15 | Agent transcript/audio retention settings and default two-year retention |
| Zero Retention Mode | https://elevenlabs.io/docs/eleven-api/resources/zero-retention-mode | checked 2026-05-15 | Enterprise zero-retention behavior for STT, TTS, Voice Changer, and Agents |
| Voice Isolator | https://elevenlabs.io/docs/overview/capabilities/voice-isolator | checked 2026-05-15 | Speech isolation from background noise, supported formats, file limits |
| Voice Changer | https://elevenlabs.io/docs/overview/capabilities/voice-changer | checked 2026-05-15 | Speech-to-speech preserving delivery nuance, whispers, laughs, cries, accents |
| Dubbing | https://elevenlabs.io/docs/overview/capabilities/dubbing | checked 2026-05-15 | Speaker separation, cross-language dubbing, tone/timing preservation |
| Introducing Scribe v2 | https://elevenlabs.io/blog/introducing-scribe-v2/ | 2026-01-09 | Batch STT for long/complex recordings, keyterm prompting, entity detection, diarization, audio tags |
| Introducing Scribe v2 Realtime | https://elevenlabs.io/blog/introducing-scribe-v2-realtime | 2025-11-11 | Realtime STT, under-150ms positioning, VAD, manual commit, language detection, enterprise controls |
| Scribe v2 Realtime in ElevenLabs Agents | https://elevenlabs.io/blog/scribe-v2-realtime-in-elevenlabs-agents | 2025-11-13 | Realtime STT in Agents, 30-80ms claim, noisy/real-world conversations, FLEURS benchmark |

## Evidence Extracts

- ElevenLabs platform shape: ElevenLabs describes itself as AI voice infrastructure for text-to-speech, speech-to-text, voice cloning, conversational agents, and generative audio, accessible through REST API, Python SDK, TypeScript SDK, and web app. Source: Documentation introduction.
- Model family: The models page lists Scribe v2 for speech recognition, Scribe v2 Realtime for realtime speech recognition, Eleven v3 and Flash v2.5 for speech generation, and speech-to-speech models for voice conversion. Source: Models.
- Scribe v2 capability: ElevenLabs positions Scribe v2 as STT in 90+ languages with keyterm prompting, entity detection, word-level timestamps, diarization up to 32 speakers, dynamic audio tagging, and smart language detection. Source: Speech to Text and Models.
- Dynamic audio tags: The STT docs define `audio_event` as non-speech sounds such as laughter or applause, while the Scribe v2 blog says dynamic audio tagging detects non-speech events such as laughter or footsteps. Source: Speech to Text and Introducing Scribe v2.
- Batch STT limits: The STT docs say supported input includes audio and video, with files up to 3 GB, up to 10 hours in standard mode, and multichannel support up to 5 channels. Source: Speech to Text capability.
- Batch STT API behavior: The Create transcript API transcribes audio or video, can run asynchronously through webhooks, supports multichannel separate transcripts, and has a custom webhook metadata field for correlation. Source: Create transcript API.
- Batch STT privacy control: The Create transcript API exposes `enable_logging=false` for zero-retention mode when available to enterprise customers, with transcript/history features unavailable for that request. Source: Create transcript API.
- Realtime STT capability: The Realtime API uses WebSockets for streaming audio input and returns partial, committed, and timestamped transcription results. It supports manual commit or voice-activity-detection commit strategies. Source: Realtime STT API.
- Server-side realtime STT: Server-side streaming can transcribe a URL, file, or custom audio stream with Scribe v2 Realtime, using an ElevenLabs API key rather than a single-use client token. Source: Server-side streaming STT.
- Realtime commit details: Partial transcripts are interim results. Committed transcripts are final segment results. Word-level timestamps are optional when `include_timestamps` is enabled. Source: Transcripts and commit strategies.
- Realtime audio setup: The commit-strategy docs list PCM sample rates from 8 kHz to 48 kHz and u-law 8 kHz, recommend 16 kHz mono for balance, and advise 0.1 to 1 second chunks. Source: Transcripts and commit strategies.
- Scribe v2 release context: The January 2026 blog positions Scribe v2 for batch transcription, subtitling, captioning, long and complex recordings, pauses, tone changes, extended silence, diverse speakers, accents, and delivery styles. Source: Introducing Scribe v2.
- Scribe v2 production features: The same blog calls out keyterm prompting, entity detection with precise timestamps, automatic multi-language transcription, diarization, word-level timestamps, and dynamic audio tagging. Source: Introducing Scribe v2.
- Scribe v2 Realtime release context: The November 2025 blog positions Scribe v2 Realtime for live voice agents, meeting assistants, and realtime captioning, with less than 150 ms latency, VAD, manual commit, PCM/u-law input, and enterprise controls. Source: Introducing Scribe v2 Realtime.
- Scribe v2 Realtime in Agents: ElevenLabs says Scribe v2 Realtime is integrated into ElevenLabs Agents and is designed for noisy backgrounds, diverse accents, and identifiers like names, emails, and IDs. Source: Scribe v2 Realtime in ElevenLabs Agents.
- Conversation analysis: ElevenAgents analysis provides success evaluation, data collection, and conversation search, processing transcripts with language models for performance and business insights. Source: Conversation analysis.
- Success evaluation: Evaluation criteria analyze the transcript against a custom prompt and return `success`, `failure`, or `unknown` with rationale; examples include sales performance, objection handling, conversion, compliance, and training. Source: Success Evaluation.
- Post-call webhooks: ElevenLabs post-call webhooks can send `post_call_transcription`, `post_call_audio`, or `call_initiation_failure`; transcription webhooks include transcript, metadata, analysis, and conversation initiation data. Source: Post-call webhooks.
- Webhook security: Post-call webhook docs require endpoint validation through HMAC signatures and suggest IP allowlisting as an additional security layer. Source: Post-call webhooks.
- Twilio native telephony: ElevenLabs can connect a Twilio phone number to an agent for inbound and outbound calls when the number supports it; verified caller IDs are outbound-only. Source: Twilio native integration.
- SIP telephony: SIP trunking connects a PBX or SIP-enabled phone system to ElevenLabs Agents, routes inbound and outbound calls, and supports TLS signaling and media encryption settings. Source: SIP trunking.
- SIP traceability: SIP trunking docs recommend custom headers such as X-CALL-ID and X-CALLER-ID for call metadata traceability and expose normalized custom headers as dynamic variables. Source: SIP trunking.
- Batch calling: ElevenLabs batch calling can initiate multiple outbound calls with agents through Twilio or SIP, with recipient upload, dynamic variables, scheduling, realtime monitoring, and compliance warnings. Source: Batch calling.
- Batch calling privacy caveat: The batch calling docs say Zero Retention Mode cannot be enabled for batch calls; ZRM-required use cases must initiate calls individually. Source: Batch calling.
- Agent retention: ElevenLabs agent retention settings default to two years of conversation data and can separately configure transcript and audio recording retention periods. Source: Retention.
- Zero retention: Enterprise Zero Retention Mode restricts logging of STT audio input, STT text output, TTS input/output, Voice Changer input/output, and Agents input/output; data is not sent to long-term storage. Source: Zero Retention Mode.
- Voice isolation: The Voice Isolator API transforms noisy recordings into cleaner speech, supports audio and video files, and has a 500 MB / 1 hour limit. Source: Voice Isolator.
- Voice changer: The Voice Changer API preserves performance nuances such as whispers, laughs, cries, accents, subtle emotional cues, and speaking cadence while transforming voice. Source: Voice Changer.
- Dubbing: Dubbing separates speakers and translates audio/video while preserving emotion, timing, tone, and speaker characteristics; this is useful evidence for what voice-stack vendors can process, not a NurtureAny sales-coaching workflow by itself. Source: Dubbing.

## Local Interpretation Notes

- ElevenLabs is strongest as evidence for an alternative or future voice stack: Scribe v2 for post-call transcription, Scribe v2 Realtime for live transcript deltas, ElevenAgents for deployed voice agents, and Twilio/SIP for telephony integration.
- ElevenLabs docs do not prove StaffAny has access to live Aircall audio, WhatsApp call audio, SIP routing, call-consent coverage, or an approved ElevenLabs credential path.
- For NurtureAny V1, the current executable path remains selected Aircall recording -> OpenAI transcription/audio evidence -> NurtureAny rubric. ElevenLabs should not be named as a current data source unless a future adapter is implemented.
- For "tone and other stuff," ElevenLabs gives useful labels to evaluate: diarization, word timestamps, dynamic audio events, pauses, silences, language switches, transcript segment timing, and non-speech events. These are observable cues, not hidden emotion certainty.
- If StaffAny later wants live coaching, ElevenLabs provides two possible future paths: Scribe v2 Realtime for live transcript deltas, or ElevenAgents with Twilio/SIP if a spoken AI agent should participate in calls.
- A future ElevenLabs pilot must include consent/notice, retention settings, zero-retention feasibility, webhook HMAC validation, IP allowlisting if required, raw audio/transcript redaction, and evals on real StaffAny sales-call audio.
