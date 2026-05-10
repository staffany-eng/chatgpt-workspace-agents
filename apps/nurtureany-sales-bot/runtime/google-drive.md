# Google Drive Runtime

NurtureAny may use the StaffAny `team@staffany.com` Google Drive OAuth account to list event-photo metadata from the `all-random` folder. HubSpot remains the contact/company source of truth.

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
- Allowed tools:
  - `list_drive_folder_images`
  - `extract_drive_image_clues`

## Query Rules

- List only bounded image metadata from the configured Drive folder.
- Return Drive file IDs, filenames, MIME type, timestamps, webViewLink, checksum, and size.
- Parse Slack-export filenames into `source_timestamp`, `slack_user_id`, and `original_filename`.
- Resolve `slack_uploader_name` with Slack `users.info` when `SLACK_BOT_TOKEN` has access; keep it best-effort and do not block Drive scans if Slack profile lookup fails.
- Download image bytes only transiently inside `extract_drive_image_clues` for OCR/vision, then discard bytes before returning.
- Do not export files, mutate Drive, return raw image bytes, or copy raw images into HubSpot.
- Pass returned metadata to `scan_drive_event_photos` before photo matching.
- Pass extracted `vision_clues` into `propose_photo_people_matches`; if no badge/signage/company/contact text is visible, ask for one missing clue instead of claiming a match.
- Cap reads at 100 files per call.
- Cap vision extraction at 5 files per call; scan larger batches through repeated bounded calls.
- Return `Confidence: blocked` when OAuth files, scopes, auth refresh, or Drive access fails.
