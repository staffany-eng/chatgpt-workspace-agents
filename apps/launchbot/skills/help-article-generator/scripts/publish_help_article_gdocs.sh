#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: publish_help_article_gdocs.sh --input <article.md> --title <doc-title> --credentials <oauth.json> [--folder-id <drive-folder-id>] [--out-dir <dir>] [--token <token.json>]

Examples:
  publish_help_article_gdocs.sh \
    --input /tmp/article.md \
    --title "PPh21 DTP Setup - Indonesia" \
    --credentials /Users/me/.config/gdocs/oauth-client.json

  publish_help_article_gdocs.sh \
    --input /tmp/article.md \
    --title "Permission Groups - Publish Schedule" \
    --credentials /Users/me/.config/gdocs/oauth-client.json \
    --folder-id 1AbCdEfGhIjK
USAGE
}

INPUT=""
TITLE=""
CREDENTIALS=""
FOLDER_ID=""
OUT_DIR=""
TOKEN_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --input|-i)
      INPUT="${2:-}"
      shift 2
      ;;
    --title|-t)
      TITLE="${2:-}"
      shift 2
      ;;
    --credentials|-c)
      CREDENTIALS="${2:-}"
      shift 2
      ;;
    --folder-id)
      FOLDER_ID="${2:-}"
      shift 2
      ;;
    --out-dir|-o)
      OUT_DIR="${2:-}"
      shift 2
      ;;
    --token)
      TOKEN_PATH="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "${INPUT// }" || -z "${TITLE// }" || -z "${CREDENTIALS// }" ]]; then
  usage >&2
  exit 1
fi

if [[ ! -f "$INPUT" ]]; then
  echo "Input file not found: $INPUT" >&2
  exit 1
fi

if [[ ! -f "$CREDENTIALS" ]]; then
  echo "Credentials file not found: $CREDENTIALS" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || pwd)"

if [[ -z "${OUT_DIR// }" ]]; then
  OUT_DIR="$ROOT_DIR/dist/help-articles"
fi

if [[ -z "${TOKEN_PATH// }" ]]; then
  TOKEN_PATH="$ROOT_DIR/apps/launchbot/skills/help-article-generator/.tokens/google-token.json"
fi

mkdir -p "$OUT_DIR"

NAME="$(basename "$INPUT")"
NAME="${NAME%.*}"
GMD_OUT="$OUT_DIR/${NAME}.gdocs.md"
HTML_OUT="$OUT_DIR/${NAME}.gdocs.html"

perl -pe 's/\r\n/\n/g' "$INPUT" > "$GMD_OUT"

python3 "$SCRIPT_DIR/md_to_gdocs_html.py" \
  --input "$GMD_OUT" \
  --output "$HTML_OUT" \
  --title "$TITLE"

JSON_OUTPUT="$(python3 "$SCRIPT_DIR/publish_to_google_docs.py" \
  --html "$HTML_OUT" \
  --title "$TITLE" \
  --credentials "$CREDENTIALS" \
  --token "$TOKEN_PATH" \
  --folder-id "$FOLDER_ID")"

DOC_URL="$(printf '%s' "$JSON_OUTPUT" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("url",""))')"
DOC_ID="$(printf '%s' "$JSON_OUTPUT" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("id",""))')"

echo "Created outputs:"
echo "- Google Docs copy format (Markdown): $GMD_OUT"
echo "- Google Docs copy format (HTML): $HTML_OUT"
echo "- Google Doc ID: $DOC_ID"
echo "- Google Doc URL: $DOC_URL"
