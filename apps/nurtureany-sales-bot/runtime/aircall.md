# Aircall Runtime Contract

NurtureAny may use Aircall as read-only selected-call enrichment. HubSpot remains source of truth for account scope, ownership, contacts, deals, tasks, notes, follow-up status, and nurture fields.

## Credentials

Production credentials live only in Secret Manager dotenv:

- `AIRCALL_API_ID`
- `AIRCALL_API_TOKEN`
- `OPENAI_API_KEY`

Do not commit or print secret values. The Aircall adapter uses Basic Auth for `https://api.aircall.io/v1`. OpenAI transcription uses `https://api.openai.com/v1/audio/transcriptions`.

## Tools

`find_aircall_calls`

- Reads recent Aircall call metadata from `/v1/calls`.
- Caps output at 5 calls.
- Returns safe call IDs, timestamps, status, direction, duration, user display metadata, and whether a recording exists.
- Never returns raw phone numbers, raw recording URLs, audio bytes, or transcripts.

`transcribe_aircall_recording`

- Reads one selected numeric Aircall call ID.
- Downloads the recording transiently only when a recording exists.
- Caps audio at 25 MB and 60 minutes.
- Sends the transient audio to OpenAI audio transcription.
- Defaults to `gpt-4o-transcribe-diarize` with `response_format=diarized_json` and `chunking_strategy=auto`.
- Deletes the downloaded audio before returning.
- Returns redacted bounded transcript text/segments only.
- Never mutates Aircall or HubSpot.

## Output Rules

Default call-review output should summarize:

- Call handling.
- Customer/prospect concerns.
- Objections or buying signals.
- Agreed next steps.
- Coaching gaps.

Do not paste raw transcript blocks into Slack by default. Do not expose recording links, raw audio, phone numbers, full emails, secrets, or bulk call transcript exports.

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
