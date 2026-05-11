# Google Drive Runtime

NurtureAny may use the StaffAny `team@staffany.com` Google Drive OAuth account to read selected Google Slides decks, list event-photo metadata from the `all-random` folder, and read the Indonesia Rev LL/HHH registration Sheet as an attendance fallback. HubSpot remains the contact/company source of truth.

## Contract

- Server name: `google_drive_nurtureany`
- Account: `team@staffany.com`
- Auth env vars:
  - `GOOGLE_DRIVE_TOKEN_FILE`
  - `GOOGLE_DRIVE_CLIENT_SECRET_FILE`
  - `GOOGLE_DRIVE_ACCOUNT_EMAIL`
  - `SLACK_BOT_TOKEN` for best-effort uploader display names from Slack-export filenames
  - `ANTHROPIC_API_KEY`
  - optional `NURTUREANY_DRIVE_VISION_MODEL`
- Access mode: read-only OAuth token file. This is not a Google service account.
- Required OAuth scope: `https://www.googleapis.com/auth/drive.readonly`
- Default folder: `1qXlFnr5TKFtsYNWk7ZywBBctDaae3RY-` (`all-random`)
- Indonesia event registration fallback Sheet: `ID REV - LL & HHH EVENTS` (`1mXixAVJGk0Uy0u1LtOmDFxU3XuW8DRfedB69E1f-drc`)
- Manual attendance fallback column: `Attend The Event`
- Allowed tools:
  - `list_drive_folder_images`
  - `read_google_slides_deck`
  - `extract_drive_image_clues`
  - `read_nurture_material_registry`
  - `read_indonesia_event_registration_attendance`

## Query Rules

- List only bounded image metadata from the configured Drive folder.
- Read Google Slides or Drive-hosted `.pptx` decks only when the user supplies a specific Google Slides URL or presentation ID and has approved the Slack plan with `run`.
- Use `read_google_slides_deck` to extract bounded text through the Drive API using `team@staffany.com`. Native Google Slides are exported as text. `.pptx` files are downloaded transiently for ZIP/XML text extraction, then raw bytes are discarded.
- If Slides access is blocked, return `Confidence: blocked` and ask the deck owner to share viewer access with `team@staffany.com` or an approved StaffAny group. Do not ask for "Anyone with the link" public sharing as the fix.
- Use `read_nurture_material_registry` only for the one-sheet NurtureAny material registry configured by `NURTUREANY_MATERIAL_REGISTRY_SPREADSHEET_ID`. It returns safe rows from approved registry tabs and does not mutate Drive/Sheets.
- Return Drive file IDs, filenames, MIME type, timestamps, webViewLink, checksum, and size.
- Parse Slack-export filenames into `source_timestamp`, `slack_user_id`, and `original_filename`.
- Resolve `slack_uploader_name` with Slack `users.info` when `SLACK_BOT_TOKEN` has access; keep it best-effort and do not block Drive scans if Slack profile lookup fails.
- Download image bytes only transiently inside `extract_drive_image_clues` for OCR/vision, then discard bytes before returning.
- Do not export files, mutate Drive, return raw image bytes, or copy raw images into HubSpot.
- Pass returned metadata to `scan_drive_event_photos` before photo matching.
- Pass extracted `vision_clues` into `propose_photo_people_matches`; if no badge/signage/company/contact text is visible, ask for one missing clue instead of claiming a match.
- Use `read_indonesia_event_registration_attendance` only for Indonesia LL/HHH event follow-up when Luma `checked_in_at` attendance is empty or check-in was not used.
- The fallback reads bounded rows from `ID REV - LL & HHH EVENTS`, for example `HHH Bali 7 May - Rsvp`, and treats `Attend The Event` as manual attendance evidence.
- The fallback must return safe rows only: company, role/title, account mapping, RSVP/WA confirm, attended flag, QO/remarks, email domain/hash, and match keys. It must not return phone numbers, full emails, raw registration exports, or mutate Drive/Sheets.
- Sheet fallback is `Confidence: needs-check` until the attended company/domain match keys are resolved back to scoped HubSpot target accounts and follow-up evidence is checked in HubSpot.
- Cap reads at 100 files per call.
- Cap vision extraction at 5 files per call; scan larger batches through repeated bounded calls.
- Return `Confidence: blocked` when OAuth files, scopes, auth refresh, or Drive access fails.
