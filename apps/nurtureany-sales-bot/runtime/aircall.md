# Aircall Runtime Contract

NurtureAny may use Aircall as read-only selected-call enrichment. HubSpot remains source of truth for account scope, ownership, contacts, deals, tasks, notes, follow-up status, and nurture fields.

## Credentials

Production credentials live only in Secret Manager dotenv:

- `AIRCALL_API_ID`
- `AIRCALL_API_TOKEN`
- `OPENAI_API_KEY`

Do not commit or print secret values. The Aircall adapter uses Basic Auth for `https://api.aircall.io/v1`. OpenAI transcription uses `https://api.openai.com/v1/audio/transcriptions`.

Default coaching config:

- `NURTUREANY_CALL_COACH_PROVIDER=openai`
- `NURTUREANY_CALL_COACH_TRANSCRIBE_MODEL=gpt-4o-transcribe-diarize`
- `NURTUREANY_CALL_COACH_REASONING_MODEL=gpt-5.5`
- `NURTUREANY_CALL_COACH_ELEVENLABS_ENABLED=false`

OpenAI's realtime voice models are future architecture evidence only for this packet. The current adapter is post-call selected-recording transcription, not live listen-in, live coaching, SIP routing, or WhatsApp call access.

ElevenLabs docs are future/alternative voice-stack evidence only. This Aircall adapter does not use ElevenLabs, has no `ELEVENLABS_API_KEY`, and does not do ElevenLabs Scribe, Agents, SIP, Twilio, or webhook routing.

## Tools

`find_aircall_calls`

- Reads recent Aircall call metadata from `/v1/calls`.
- Sends `from` / `to` to Aircall as UNIX timestamps. ISO input from Slack/HubSpot must be normalized before the API call; invalid timestamps block instead of falling back to latest calls.
- Can do bounded selected-call matching by safe timestamp, user display text, and duration when HubSpot does not expose an Aircall external ID.
- Caps output at 5 calls.
- Returns safe call IDs, timestamps, status, direction, duration, user display metadata, and whether a recording exists.
- Never returns raw phone numbers, raw recording URLs, audio bytes, or transcripts.

`resolve_aircall_call_for_coaching`

- Resolves a natural-language selected-call request or safe hint payload to one numeric Aircall call ID.
- Accepts an exact Aircall call ID, or bounded hints such as rep name, timestamp, and duration.
- Returns safe selected-call metadata only.
- Never returns raw recording URLs, audio bytes, transcript text, phone numbers, or mutation.
- If multiple candidates remain, asks the user to select one candidate before coaching.

`transcribe_aircall_recording`

- Reads one selected numeric Aircall call ID.
- Prefer the Aircall ID synced into HubSpot `hs_call_external_id`; never pass a HubSpot call object ID as the Aircall call ID.
- Downloads the recording transiently only when a recording exists.
- Caps audio at 25 MB and 60 minutes.
- Sends the transient audio to OpenAI audio transcription.
- Defaults to `gpt-4o-transcribe-diarize` with `response_format=diarized_json` and `chunking_strategy=auto`.
- Deletes the downloaded audio before returning.
- Returns redacted bounded transcript text/segments only.
- Never mutates Aircall or HubSpot.

`analyze_aircall_call_coaching`

- Reads one selected numeric Aircall call ID.
- Prefer the Aircall ID synced into HubSpot `hs_call_external_id`; never pass a HubSpot call object ID as the Aircall call ID.
- Downloads the recording transiently, transcribes it through OpenAI `gpt-4o-transcribe-diarize` with `diarized_json`, computes Gong-style interaction evidence locally, and sends only redacted segments/metrics plus supplied HubSpot IDs/context into OpenAI `gpt-5.5` via the Responses API with Structured Outputs.
- Computes talk ratio by speaker, longest monologue, turn count, interactivity, question count, objection moments, next-step clarity, and customer reaction moments such as short answers, follow-up questions, silence gaps, and repeated objections.
- Returns safe coaching JSON only: `answer`, `scorecard`, `coachable_moments`, `interaction_cues`, `manager_coaching_note`, `next_action`, `source`, `scope`, `confidence`, and `caveat`.
- Labels transcript/timing evidence as `Interaction cues checked from transcript/timing` and `audio-native tone not checked`.
- Never returns raw transcript blocks, raw recording URLs, audio, phone numbers, or full emails, and never mutates Aircall or HubSpot.
- Does not integrate Gong or ElevenLabs. Gong shapes the workflow only. ElevenLabs stays future/benchmark evidence only.

## Output Rules

Default selected-call review output should use `analyze_aircall_call_coaching` after resolving a selected numeric Aircall ID. It should follow the Gong-inspired NurtureAny coaching structure:

- `Answer:` short call assessment.
- `Scorecard:` 0/1/2 rows with concise evidence for discovery, I-C-BANT, talk ratio, interactivity, patience, monologue length, objections, next step, CRM hygiene, customer reaction moments, and StaffAny value framing.
- `Coachable moments:` timestamped notes tied to specific call moments.
- `Tone / interaction cues:` observable cues only. If only transcript/timing evidence is available, write `Interaction cues checked from transcript/timing` and `Tone/audio cues: audio-native tone not checked`. If a future approved audio-native analysis runs, write `Tone/audio cues checked from recording`.
- `Manager coaching note:` copy-ready manager feedback.
- `Next action:` rep action and owner/date when known.
- `Source / Scope / Confidence / Caveat`.

Do not paste raw transcript blocks into Slack by default. Do not expose recording links, raw audio, phone numbers, full emails, secrets, or bulk call transcript exports. Do not infer hidden emotion as fact; phrase tone/audio as observed behavior such as shorter answers, overlap, long monologue, delayed response, or follow-up questions. Gong public docs shape the output pattern only; there is no Gong API, credential, MCP, webhook, or parity claim. ElevenLabs docs are future/alternative voice-stack evidence only; there is no ElevenLabs API key, adapter, SIP/Twilio routing, webhook, or live-call claim.

## Safety Bounds

- Read-only only.
- Selected call only for transcription.
- `max_calls=5`.
- `max_audio_bytes=26214400`.
- `max_audio_seconds=3600`.
- `raw_recording_urls_returned=false`.
- `raw_audio_retained=false`.
- `bulk_transcript_exports=false`.

If Aircall returns no recording, or OpenAI/Aircall credentials are missing, answer `Confidence: blocked` and name the missing prerequisite.
