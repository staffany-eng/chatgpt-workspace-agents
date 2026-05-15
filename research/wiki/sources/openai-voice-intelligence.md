# OpenAI Voice Intelligence

## Source Metadata

- Type: official OpenAI public article, developer-doc, and research ingest
- Source class: OpenAI realtime voice, speech-to-text, speech-to-speech, and voice safety sources
- Source URL or path: https://openai.com/ and https://developers.openai.com/
- Date ingested: 2026-05-15
- Context: technical evidence for voice model capabilities, audio architecture choices, and NurtureAny call-coaching boundaries
- Default weight: 5
- Privacy: public docs and public PDFs, no StaffAny data, call recordings, transcripts, secrets, or customer PII copied

## Context Caveat

These sources are official OpenAI evidence for OpenAI voice capabilities and safety guidance.
They do not prove StaffAny has live audio access, WhatsApp call access, Aircall live-listen access,
recording consent, or a deployed live-coaching workflow. For NurtureAny, HubSpot remains account truth,
Aircall remains selected-call artifact enrichment, and OpenAI remains the transcription/audio model provider.

## Evidence Used

- Raw record: [research/raw/openai-voice-intelligence/source-extract.md](../../raw/openai-voice-intelligence/source-extract.md)

## What They Said

- OpenAI's May 2026 voice release introduces GPT-Realtime-2, GPT-Realtime-Translate, and GPT-Realtime-Whisper for realtime voice reasoning, translation, and streaming transcription.
- OpenAI frames modern voice products around voice-to-action, systems-to-voice, and voice-to-voice patterns, not transcription alone.
- GPT-Realtime-2 is positioned for live voice interactions that can reason, call tools, handle corrections, and control tone/delivery while a conversation continues.
- OpenAI developer docs separate realtime voice agents, realtime translation, realtime transcription, bounded file transcription, text-to-speech, and audio-capable chat into different architecture paths.
- The voice-agent docs distinguish live speech-to-speech sessions from chained voice pipelines; chained pipelines fit workflows that need explicit control over transcript, reasoning, and output.
- Realtime transcription docs recommend GPT-Realtime-Whisper for live transcript deltas, while standard speech-to-text models remain the path for offline or bounded audio files.
- OpenAI's older audio and Whisper sources are still useful deep research: Whisper shows robust multilingual ASR from 680k hours, and newer gpt-4o transcription models improve WER for accents, noise, and speech-speed variation.
- GPT-4o voice safety sources warn about risks such as unauthorized voice generation, speaker identification, ungrounded inference, sensitive trait attribution, and other audio-output risks.
- The OpenAI/MIT affective-use paper treats Advanced Voice Mode as a real-time speech-to-speech interface and cautions that voice interaction effects on emotional well-being are nuanced.

## Evidence Trace

- Claim: May 2026 release introduced three realtime voice models. Evidence: Raw extract lists GPT-Realtime-2, GPT-Realtime-Translate, and GPT-Realtime-Whisper. Source: `research/raw/openai-voice-intelligence/source-extract.md:37`.
- Claim: Voice products are broader than transcription. Evidence: Raw extract captures voice-to-action, systems-to-voice, and voice-to-voice as source patterns. Source: `research/raw/openai-voice-intelligence/source-extract.md:38`.
- Claim: GPT-Realtime-2 is for live reasoning and tool-using voice interactions. Evidence: Raw extract says it reasons, calls tools, handles corrections, and controls delivery. Source: `research/raw/openai-voice-intelligence/source-extract.md:39`.
- Claim: OpenAI docs split voice use cases into different architectures. Evidence: Raw extract lists separate starts for voice agents, translation, transcription, bounded STT, TTS, and audio chat. Source: `research/raw/openai-voice-intelligence/source-extract.md:44`.
- Claim: Chained voice pipelines are valid when deterministic control matters. Evidence: Raw extract compares live speech-to-speech with chained transcript/reason/output control. Source: `research/raw/openai-voice-intelligence/source-extract.md:45`.
- Claim: GPT-Realtime-Whisper is live-streaming specific, not a blanket replacement. Evidence: Raw extract says live deltas use GPT-Realtime-Whisper and offline files use standard STT. Source: `research/raw/openai-voice-intelligence/source-extract.md:46`.
- Claim: Older OpenAI speech research remains important. Evidence: Raw extract records Whisper's 680k-hour multilingual setup and newer gpt-4o transcription WER improvements. Source: `research/raw/openai-voice-intelligence/source-extract.md:51`.
- Claim: Voice safety boundaries matter for NurtureAny. Evidence: Raw extract lists speaker ID, unauthorized voice generation, ungrounded inference, and sensitive trait risks. Source: `research/raw/openai-voice-intelligence/source-extract.md:57`.
- Claim: Voice emotional effects should be handled cautiously. Evidence: Raw extract summarizes the Advanced Voice Mode affective-use finding as nuanced and usage-dependent. Source: `research/raw/openai-voice-intelligence/source-extract.md:59`.

## Learning Summary

- The article the user asked about is the current OpenAI realtime voice release as of 2026-05-15: GPT-Realtime-2, GPT-Realtime-Translate, and GPT-Realtime-Whisper.
- For NurtureAny V1 selected-call coaching, the right current path is still post-call selected recording -> bounded transcription/audio evidence -> rubric summary. This is a chained pipeline.
- Live sales coaching would require a separate approved live audio stream, consent/compliance design, Aircall or telephony streaming support, and realtime transcription or voice-agent plumbing.
- GPT-Realtime-Whisper is the model family to evaluate for live transcript deltas. GPT-Realtime-2 is relevant only if NurtureAny should become a live spoken agent with tools.
- Deep voice reading should include the GPT-4o System Card, Whisper paper, affective-use study, realtime prompting guide, realtime transcription docs, and voice-agent docs.
- OpenAI voice safety sources reinforce the existing NurtureAny rule: report observable audio/interaction cues only and never infer hidden emotion, identity, protected traits, or psychological state as fact.

## Synthesis Gate

- Mode: autonomous_current_focus_synthesis
- Status: completed
- Focus source: OpenAI official voice release, developer docs, GPT-4o system card, Whisper paper, and Advanced Voice Mode research.
- Evidence weight check: default weight 5 for OpenAI capability and safety evidence; does not override HubSpot or StaffAny sales guidance for business truth.
- Output: synthesize as technical capability and safety guidance for NurtureAny call coaching, not as proof of live-call access.

## Possible Agent Builder Relevance

- Agent-synthesized: Add a source-backed OpenAI voice synthesis so NurtureAny can distinguish post-call transcription from future live coaching.
- Agent-synthesized: Keep Aircall/OpenAI selected-call review source-agnostic and bounded; do not switch to realtime models without an approved live audio path.
- Agent-synthesized: Use GPT-Realtime-Whisper as the likely future model path for live transcript deltas, and GPT-Realtime-2 only for future spoken voice-agent workflows.
- Do-not-promote: Do not claim NurtureAny can listen to WhatsApp or Aircall calls live because OpenAI released realtime models.
- Do-not-promote: Do not infer emotion, speaker identity, protected traits, or psychological state from voice/audio.

## Follow-Up Questions

- Should NurtureAny's next call-coaching milestone stay post-call selected recordings, or should StaffAny design a separate consented live-coaching pilot with telephony streaming?
