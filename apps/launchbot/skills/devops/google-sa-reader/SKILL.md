---
name: google-sa-reader
description: Read Google Docs, Sheets, and Drive files using the Launchbot service account credentials stored in .env. Load this skill whenever a user asks to read a Google Doc, Google Sheet, or find files in Google Drive. The service account has read-only access to files explicitly shared with it.
tags: [google, docs, sheets, drive, service-account, read-only]
---

# Google Service Account Reader

Read-only access to Google Docs, Sheets, and Drive via Launchbot's service account.

## Script

```
/home/leekaiyi/.hermes/profiles/launchbot/scripts/google_sa.py
```

Credentials are read automatically from `/home/leekaiyi/.hermes/profiles/launchbot/.env`:
- `GOOGLE_SERVICE_ACCOUNT_EMAIL`
- `GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY`
- `GOOGLE_SERVICE_ACCOUNT_TOKEN_URI`

## Usage

```bash
GSA="python3 /home/leekaiyi/.hermes/profiles/launchbot/scripts/google_sa.py"
```

### Google Docs

```bash
# Read full document text + raw structure
$GSA docs get <DOC_ID>
# Returns: { doc_id, title, text (plain), raw (full API response) }
```

### Google Sheets

```bash
# List all sheet tabs in a spreadsheet
$GSA sheets list <SHEET_ID>

# Read a range (A1 notation)
$GSA sheets get <SHEET_ID> "Sheet1!A1:Z100"
$GSA sheets get <SHEET_ID> "Sheet1"          # entire sheet

# Returns: { sheet_id, range, values: [[row], [row], ...] }
```

### Google Drive

```bash
# Get file metadata by ID
$GSA drive get <FILE_ID>

# Search files (Drive query syntax, optional max results)
$GSA drive search "trashed=false" 20
$GSA drive search "name contains 'PRD'" 10
$GSA drive search "mimeType='application/vnd.google-apps.document'" 20

# Returns: { files: [{ id, name, mimeType, modifiedTime, webViewLink }] }
```

## Extracting IDs from URLs

| URL pattern | ID location |
|-------------|-------------|
| `docs.google.com/document/d/<ID>/edit` | after `/d/` |
| `docs.google.com/spreadsheets/d/<ID>/edit` | after `/d/` |
| `drive.google.com/file/d/<ID>/view` | after `/d/` |

## Access Model

The service account can only read files that have been **shared with the service account email** or that are in a **shared drive** it has access to.

If a file returns a 403, the file has not been shared with the service account. Ask the user to share the file with:
```
GOOGLE_SERVICE_ACCOUNT_EMAIL value from .env
```

## Python Access (for agents processing data inline)

```python
import subprocess, json

def gsa(cmd: str):
    result = subprocess.run(
        f"python3 /home/leekaiyi/.hermes/profiles/launchbot/scripts/google_sa.py {cmd}",
        shell=True, capture_output=True, text=True
    )
    return json.loads(result.stdout)

# Examples
doc = gsa("docs get 1gwIsroesQtUq2chZL661QbIT82_84vv9au8BszMmPsk")
print(doc["title"])
print(doc["text"][:2000])

sheet = gsa("sheets get 1InBlfDlat93Tqoic-YECsxOIQbEz-4ysZP3V39DdMWw 'Sheet1!A1:D20'")
rows = sheet["values"]
```

## Pitfalls

- **Service account ≠ user account.** Files in "My Drive" that are not shared will return 403. The SA only sees what is explicitly shared with it or in a shared drive it belongs to.
- **Private key newlines:** The `.env` stores `\\n` as literal `\n` — the script handles the unescaping automatically.
- **Quoted values in .env:** The loader strips surrounding `"` and `'` from all values automatically.
- **Large docs/sheets:** `docs get` returns full `raw` response which can be large. Use `text` field for plain reading; use `raw` only when structure matters.
- **Sheets range:** Always quote ranges with spaces or special chars: `'My Sheet!A1:Z'`. Use `sheets list` first to confirm tab names.
