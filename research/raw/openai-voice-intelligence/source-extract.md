# OpenAI Voice Intelligence Source Extract

## Source Metadata

- Type: official OpenAI public article, developer-doc, and research extract
- Source class: OpenAI voice, realtime audio, speech-to-text, speech-to-speech, and voice safety sources
- Base URL: https://openai.com/
- Date checked: 2026-05-15
- Date ingested: 2026-05-15
- Retrieved by: Codex web browser and OpenAI developer-docs MCP, restricted to official OpenAI domains and OpenAI-hosted PDFs
- Privacy: public docs and public PDFs; no StaffAny data, private audio, call recording, transcript, credential, or customer PII copied

## Raw Content Policy

This record preserves short, source-attributed evidence notes and compact extracts from public OpenAI sources. It does not copy full articles, full PDFs, model pricing tables, code samples, private eval data, recordings, transcripts, or customer data. Treat these sources as OpenAI capability, architecture, and safety evidence only. They do not prove StaffAny has a live audio stream, Aircall live-listen access, WhatsApp call recording access, or permission to perform live coaching.

## Source Inventory

| Source | URL | Date or status | Evidence focus |
| --- | --- | --- | --- |
| Advancing voice intelligence with new models in the API | https://openai.com/index/advancing-voice-intelligence-with-new-models-in-the-api/ | 2026-05-07 | GPT-Realtime-2, GPT-Realtime-Translate, GPT-Realtime-Whisper, voice-to-action, systems-to-voice, voice-to-voice, realtime safety |
| Realtime and audio overview | https://developers.openai.com/api/docs/guides/realtime | checked 2026-05-15 | Architecture picker for voice agents, realtime translation, realtime transcription, speech-to-text, text-to-speech, audio-capable chat |
| Voice agents guide | https://developers.openai.com/api/docs/guides/voice-agents | checked 2026-05-15 | Speech-to-speech realtime sessions versus chained voice pipeline tradeoffs |
| Realtime transcription guide | https://developers.openai.com/api/docs/guides/realtime-transcription | checked 2026-05-15 | Live transcript deltas, gpt-realtime-whisper, standard speech-to-text for bounded/offline files, latency and evaluation guidance |
| gpt-realtime-2 model page | https://developers.openai.com/api/docs/models/gpt-realtime-2 | checked 2026-05-15 | Realtime voice model with configurable reasoning effort, stronger instruction following, and tool use |
| Introducing gpt-realtime and Realtime API updates | https://openai.com/index/introducing-gpt-realtime/ | 2025-08-28 | Production voice agents, single speech-to-speech model/API path, MCP, image input, SIP phone calling |
| Introducing next-generation audio models in the API | https://openai.com/index/introducing-our-next-generation-audio-models/ | 2025-03-20 | gpt-4o-transcribe, gpt-4o-mini-transcribe, gpt-4o-mini-tts, WER, accents, noise, speech-speed robustness |
| Introducing Whisper | https://openai.com/index/whisper/ | 2022-09-21 | Open-source ASR, multilingual/multitask data, accents, background noise, technical language, translation |
| Robust Speech Recognition via Large-Scale Weak Supervision | https://cdn.openai.com/papers/whisper.pdf | checked 2026-05-15 | Whisper paper, 680k hours, robust speech recognition, multilingual and multitask setup |
| Hello GPT-4o | https://openai.com/index/hello-gpt-4o/ | 2024-05-13 | End-to-end audio, vision, and text; pipeline limitations for tone, multiple speakers, background noise |
| GPT-4o System Card | https://cdn.openai.com/gpt-4o-system-card.pdf | 2024-08-08 | Speech-to-speech focus, voice safety risks, red teaming, unauthorized voice generation, speaker identification, ungrounded inference |
| Seven tips for prompting voice agents with the Realtime API | https://cdn.openai.com/API/docs/realtime-prompting-guide.pdf | checked 2026-05-15 | Prompt precision, short bullets, unclear audio handling, language pinning, repetition control |
| Investigating Affective Use and Emotional Well-being on ChatGPT | https://cdn.openai.com/papers/15987609-5f71-433c-9972-e91131f399a1/openai-affective-use-study.pdf | checked 2026-05-15 | Advanced Voice Mode study, affective use, privacy-preserving analysis, emotional well-being caveats |

## Evidence Extracts

- May 2026 voice release: OpenAI introduces three API audio models: GPT-Realtime-2 for realtime voice reasoning and action, GPT-Realtime-Translate for live speech translation, and GPT-Realtime-Whisper for streaming speech-to-text. Source: Advancing voice intelligence.
- Voice product patterns: OpenAI describes three emerging patterns: voice-to-action, systems-to-voice, and voice-to-voice. The common theme is not just transcription, but live speech driving tasks, spoken guidance, or cross-language conversation. Source: Advancing voice intelligence.
- GPT-Realtime-2 capabilities: The release says the model is built for live voice interactions that keep conversation moving while reasoning, calling tools, handling corrections or interruptions, and responding with moment-appropriate delivery. Source: Advancing voice intelligence.
- GPT-Realtime-2 controls: OpenAI lists preambles, parallel tool calls, stronger recovery behavior, longer 128K context, stronger domain understanding, controllable tone and delivery, and adjustable reasoning effort. Source: Advancing voice intelligence.
- Live translation: GPT-Realtime-Translate supports more than 70 input languages and 13 output languages, and targets live multilingual voice experiences where participants can speak preferred languages while seeing realtime transcriptions. Source: Advancing voice intelligence.
- Live transcription: GPT-Realtime-Whisper is positioned as streaming transcription for low-latency speech-to-text, from captions to meeting notes and faster follow-up workflows. Source: Advancing voice intelligence.
- Safety: OpenAI says the Realtime API has safeguards such as active classifiers over sessions and that developers must make AI interaction clear unless obvious from context. Source: Advancing voice intelligence.
- Architecture picker: OpenAI developer docs separate low-latency voice agents, realtime translation, realtime transcription, bounded audio transcription, text-to-speech, and audio-capable chat into different model/API starting points. Source: Realtime and audio overview.
- Voice-agent architecture: OpenAI says live speech-to-speech sessions fit natural, low-latency conversations, while a chained voice pipeline fits predictable workflows or existing text agents where transcription, reasoning, and speech output need explicit control. Source: Voice agents guide.
- Realtime transcription docs: OpenAI recommends gpt-realtime-whisper for live transcript deltas, while standard speech-to-text models remain the path for offline files or workflows that do not need streaming deltas. Source: Realtime transcription guide.
- Realtime transcription evaluation: OpenAI warns teams to test with real microphones, telephony audio, accents, background noise, code-switching, domain vocabulary, and long sessions; synthetic audio alone is not enough. Source: Realtime transcription guide.
- gpt-realtime-2 docs: The model page describes GPT Realtime 2 as a realtime voice model with speech-to-speech interactions, configurable reasoning effort, stronger instruction following, and reliable tool use for complex voice-agent workflows. Source: gpt-realtime-2 model page.
- August 2025 gpt-realtime release: OpenAI positions gpt-realtime as production-ready speech-to-speech and says the Realtime API can process and generate audio directly through one model/API instead of chaining speech-to-text, text reasoning, and text-to-speech. Source: Introducing gpt-realtime.
- August 2025 API expansion: The same release highlights remote MCP support, image input, and SIP phone calling as ways to give voice agents tools, context, and telephony connectivity. Source: Introducing gpt-realtime.
- March 2025 audio models: OpenAI introduces gpt-4o-transcribe and gpt-4o-mini-transcribe with improved word error rate and stronger language recognition compared with earlier Whisper models, especially for accents, noise, and varied speech speed. Source: Introducing next-generation audio models.
- March 2025 TTS: OpenAI introduces gpt-4o-mini-tts with steerability over how text is spoken, while noting preset synthetic voices. Source: Introducing next-generation audio models.
- Whisper release: OpenAI describes Whisper as an ASR system trained on 680,000 hours of multilingual and multitask supervised web-collected data, improving robustness to accents, background noise, and technical language. Source: Introducing Whisper.
- Whisper paper: The paper frames robust speech recognition as a large-scale weak-supervision problem, with multilingual and multitask supervision enabling zero-shot transfer without dataset-specific fine-tuning. Source: Robust Speech Recognition via Large-Scale Weak Supervision.
- GPT-4o architecture: OpenAI says GPT-4o is trained end-to-end across text, vision, and audio, so one neural network processes all inputs and outputs. Source: GPT-4o System Card.
- GPT-4o pipeline limitation: The Hello GPT-4o article contrasts older voice pipelines with an end-to-end audio model, noting that chained pipelines lose direct access to tone, multiple speakers, and background noise. Source: Hello GPT-4o.
- GPT-4o safety risks: The system card focuses on speech-to-speech voice and discusses risks such as unauthorized voice generation, speaker identification, ungrounded inference, sensitive trait attribution, and disallowed audio output. Source: GPT-4o System Card.
- Realtime prompting: OpenAI's realtime prompting guide recommends precise, conflict-free instructions, short bullets, explicit unclear-audio behavior, language rules where needed, varied sample phrases, and repetition controls. Source: Seven tips for prompting voice agents.
- Affective use research: The OpenAI/MIT study focuses on Advanced Voice Mode and finds voice-based interaction effects on emotional well-being are nuanced and influenced by factors such as initial emotional state and total usage duration. Source: Investigating Affective Use and Emotional Well-being on ChatGPT.

## Local Interpretation Notes

- The May 2026 release is the most current OpenAI source found for realtime voice models. It supersedes the older gpt-realtime and GPT-4o voice release path for current API model names, but older sources remain useful for architecture and safety context.
- For NurtureAny's current post-call Aircall review, the most relevant production path remains selected recording -> bounded transcription -> coaching summary. This is a chained pipeline, not a live speech-to-speech agent.
- GPT-Realtime-Whisper is the relevant candidate only if NurtureAny later gets an approved live audio stream and wants live transcript deltas. It does not by itself grant access to WhatsApp, Aircall live calls, call recording consent, or call-center audio routing.
- GPT-Realtime-2 is relevant for a future live voice agent that speaks, reasons, and uses tools during the conversation. It is heavier than needed for transcript-only post-call coaching unless the product deliberately moves into live coaching or spoken assistant behavior.
- OpenAI's own safety sources reinforce the current NurtureAny boundary: describe observable cues from audio, but do not infer hidden emotions, speaker identity, protected traits, or unsupported psychological states.
- Deep follow-up reading on voice should prioritize the GPT-4o System Card, the Whisper paper,
  the affective-use study, the realtime prompting guide, and the current Realtime transcription/voice-agent docs.
