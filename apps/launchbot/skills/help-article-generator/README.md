# Help Article Generator Skill

Generate StaffAny Help Center articles from Pantheon feature evidence.

## Included Files

- `SKILL.md`: Skill instructions and workflow
- `templates/help-article-template.md`: Draft template
- `scripts/feature_context.sh`: Context extraction via `rg`
- `scripts/feature_context.mjs`: Context extraction via Node.js
- `scripts/md_to_gdocs_html.py`: Convert Markdown article to Google Docs-friendly HTML
- `scripts/publish_to_google_docs.py`: Create a Google Doc from generated HTML (Drive import)
- `scripts/publish_help_article_gdocs.sh`: One-command markdown -> HTML -> Google Doc publish
- `scripts/requirements-gdocs.txt`: Python dependencies for Google APIs
- `scripts/export_help_article.sh`: Generate shareable `.gdocs.*` and `.docx` outputs
- `scripts/modernize_docx.py`: Upgrade DOCX to modern Word mode + normalize article fonts
- `agents/openai.yaml`: Agent metadata

## Requirements

- `bash`
- `rg` (ripgrep)
- `node` (for `feature_context.mjs`)
- `python3` (for `md_to_gdocs_html.py`)
- Optional for direct Google Docs publishing:
  - `pip` packages from `scripts/requirements-gdocs.txt`
  - Google Cloud OAuth client credentials JSON (Desktop app)
- Optional for `.docx` export:
  - `textutil` (macOS) or `pandoc`
- Pantheon repo checked out (expects `AGENTS.md` and `apps/`). Set `LAUNCH_PANTHEON_REPO` or pass `--repo`.

## Install

1. Copy the `help-article-generator` folder into one of:
- Launchbot repo skill: `apps/launchbot/skills/help-article-generator`
- Repo-local: `.agents/skills/help-article-generator`
- Global Codex skills: `$CODEX_HOME/skills/help-article-generator`

2. Restart Codex session (if already running) so the skill list refreshes.

## Usage

Use in prompt:

```text
Use $help-article-generator to draft a help article for <feature>.
```

Generate context pack manually:

```bash
bash apps/launchbot/skills/help-article-generator/scripts/feature_context.sh \
  --feature "PPh21 DTP setup" \
  --repo "$LAUNCH_PANTHEON_REPO" \
  --max 100
```

Optional deeper scan:

```bash
ENABLE_BACKEND_SCAN=1 ENABLE_HELP_REF_SCAN=1 \
bash apps/launchbot/skills/help-article-generator/scripts/feature_context.sh \
  --feature "PPh21 DTP setup" \
  --repo "$LAUNCH_PANTHEON_REPO" \
  --max 100
```

Publish article directly to Google Docs:

```bash
python3 -m pip install -r apps/launchbot/skills/help-article-generator/scripts/requirements-gdocs.txt

bash apps/launchbot/skills/help-article-generator/scripts/publish_help_article_gdocs.sh \
  --input /path/to/final-article.md \
  --title "PPh21 DTP Setup - Indonesia" \
  --credentials /absolute/path/to/oauth-client.json \
  --folder-id <optional-drive-folder-id>
```

Google Docs one-time setup:
1. In Google Cloud Console, create a project and enable **Google Drive API**.
2. Configure **OAuth consent screen**.
3. Create **OAuth client ID** with type **Desktop app**.
4. Download the credentials JSON and pass its absolute path to `--credentials`.
5. Run the publish command once; browser OAuth will open and token cache is stored at:
   - `apps/launchbot/skills/help-article-generator/.tokens/google-token.json`

Fallback export (if you only want local files):

```bash
bash apps/launchbot/skills/help-article-generator/scripts/export_help_article.sh \
  --input /path/to/final-article.md \
  --out-dir /tmp/help-exports \
  --name pph21-dtp-setup
```

Output files:
- `/tmp/help-exports/pph21-dtp-setup.gdocs.md`
- `/tmp/help-exports/pph21-dtp-setup.gdocs.html`
- `/tmp/help-exports/pph21-dtp-setup.docx`

If `.docx` is required for a specific workflow, use `--require-docx`.

DOCX notes:
- Exporter upgrades DOCX metadata to modern compatibility mode (`16`, newer than 2007 mode).
- Exporter normalizes generated article font defaults to better match Help Center reading format.
