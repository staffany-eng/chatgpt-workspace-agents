# Demo Sources Runtime Contract

NurtureAny may use selected demo transcript evidence as read-only coaching enrichment. HubSpot remains source of truth for account scope, ownership, contacts, deals, tasks, notes, follow-up status, and nurture fields.

## Sources

V1 supports Loom share pages only when captions/VTT are available. The adapter fetches the selected Loom page, finds the captions/VTT URL internally, parses timing cues, and returns bounded redacted segments.

V1 does not download Loom MP4/HLS, audio, video, screenshots, or signed media bytes. User-supplied transcript text can be added later if the workflow needs it, but it is not a separate runtime primitive now.

## Tool

`extract_demo_transcript_evidence`

- Inputs: `slack_user_email`, `source_url`, and optional `source_type="auto"`.
- Supports `source_type=auto` and `source_type=loom`.
- Returns `title`, `source_type`, `cue_count`, `word_count`, bounded redacted `segments`, `timing_metadata`, canonical Loom source permalink, demo grading dimensions, source, scope, confidence, and caveat.
- Caps fetches at 1 MB and returned segments at 24.
- Never returns raw transcript dumps, signed Loom media URLs, video/audio bytes, phone numbers, full emails, or mutations.
- If captions are unavailable, private, blocked, or malformed, returns `Confidence: blocked` with a concrete blocker reason and asks for captions or transcript input.

## Demo Grading

Demo grading is internal shared logic, not a separate public MCP primitive. For a Loom/demo prompt, route:

1. Use `get_selected_slack_thread_context` only when the current Slack thread is needed to identify the selected Loom/demo source.
2. Call `extract_demo_transcript_evidence` for the selected source.
3. Grade using the 0/1/2 rubric in `skills/nurtureany-sales-bot/references/sales-best-practices.md`.
4. If the user asks for trend/history, export sanitized rows with `preview_analysis_sheet_export`, then `apply_analysis_sheet_export`.

Use these 9 demo scorecard dimensions:

- Control and conversational opening
- Discovery and I-C-BANT
- Consultative/contextual demo
- Before/after value framing
- Benefits over features
- Product knowledge accuracy
- Objection and negotiation handling
- Customer engagement and interaction cues
- Next step and post-demo follow-up quality

Default output fields are `Answer`, `Overall grade`, `Scorecard`, `Coachable moments`, `Better talk tracks`, `Manager coaching note`, `Next practice`, `Source`, `Scope`, `Confidence`, and `Caveat`.

## Safety Bounds

- Read-only only.
- Selected source only.
- Caption/transcript evidence only.
- `max_fetch_bytes=1000000`.
- `max_safe_segments=24`.
- `raw_transcript_returned=false`.
- `signed_loom_media_urls_returned=false`.
- `video_audio_bytes_returned=false`.
- `phone_numbers_returned=false`.
- `full_emails_returned=false`.
- `media_downloads=false`.

