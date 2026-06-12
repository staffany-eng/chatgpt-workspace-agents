---
name: slack-file-download
description: Download and analyze Slack internal file URLs (files.slack.com / staffany.slack.com/files) using the bot token. Use when a user shares a Slack-hosted image or file and vision analysis is needed.
tags: [slack, file, image, screenshot, vision]
---

# Slack File Download

Use when a user shares a Slack-internal file URL in the format:
- `https://staffany.slack.com/files/<user_id>/<file_id>/<filename>`
- `https://files.slack.com/files-pri/<team_id>-<file_id>/<filename>`

These URLs require authentication — they cannot be fetched directly by vision tools.

## Steps

1. **Extract the file ID** from the Slack URL (e.g. `F0BA7JW1WG4`).

2. **Call `files.info` to get the private download URL:**

```bash
SLACK_BOT_TOKEN=$(grep '^SLACK_BOT_TOKEN=' /home/leekaiyi/.hermes/profiles/launchbot/.env | sed 's/SLACK_BOT_TOKEN=//' | tr -d '"')
FILE_ID="<file_id>"
curl -s "https://slack.com/api/files.info?file=$FILE_ID" \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN" | python3 -c "
import json, sys
d = json.load(sys.stdin)
f = d.get('file', {})
print(f.get('url_private', ''))
"
```

3. **Download the file to `/tmp/`:**

```bash
SLACK_BOT_TOKEN=$(grep '^SLACK_BOT_TOKEN=' /home/leekaiyi/.hermes/profiles/launchbot/.env | sed 's/SLACK_BOT_TOKEN=//' | tr -d '"')
curl -s -L "<url_private>" \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  -o /tmp/slack_file.<ext>
```

4. **Pass to `vision_analyze`:**

```python
vision_analyze(image_url="/tmp/slack_file.png", question="<your question>")
```

## Pitfalls

- **Token has surrounding quotes in `.env`** — always `tr -d '"'` when extracting.
- **`files.info` returns `ok: false` with `invalid_auth`** if the token has stray quote characters. Strip them.
- **`url_private` vs `url_private_download`** — either works; `url_private` is sufficient with a bot token.
- **File ID is in the URL path**, not the filename. Format: `F` followed by alphanumeric (e.g. `F0BA7JW1WG4`).
- The bot must be **in the channel** where the file was shared, or have `files:read` scope.

## When to Use

- User pastes a `staffany.slack.com/files/...` link and asks to analyze the image.
- Screenshot is referenced in a thread but not directly accessible by vision tools.
- Any Slack-hosted attachment (PNG, JPG, PDF screenshot) needs content extraction.

## Execute via `execute_code`

Use `execute_code` (not `terminal`) for the full fetch+analyze pipeline to avoid timeout issues with chained shell calls:

```python
from hermes_tools import terminal

result = terminal("""
SLACK_BOT_TOKEN=$(grep '^SLACK_BOT_TOKEN=' /home/leekaiyi/.hermes/profiles/launchbot/.env | sed 's/SLACK_BOT_TOKEN=//' | tr -d '"')
FILE_ID="F0BA7JW1WG4"
URL=$(curl -s "https://slack.com/api/files.info?file=$FILE_ID" \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN" | python3 -c "import json,sys; print(json.load(sys.stdin).get('file',{}).get('url_private',''))")
curl -s -L "$URL" -H "Authorization: Bearer $SLACK_BOT_TOKEN" -o /tmp/slack_screenshot.png
echo "done"
""")
# Then call vision_analyze(image_url="/tmp/slack_screenshot.png", ...)
```
