#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: export_help_article.sh --input <article.md> [--out-dir <dir>] [--name <file-stem>] [--require-docx]

Examples:
  export_help_article.sh --input /tmp/article.md
  export_help_article.sh --input /tmp/article.md --out-dir /tmp/help-exports --name dtp-setup-id
USAGE
}

INPUT=""
OUT_DIR=""
NAME=""
REQUIRE_DOCX=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --input|-i)
      INPUT="${2:-}"
      shift 2
      ;;
    --out-dir|-o)
      OUT_DIR="${2:-}"
      shift 2
      ;;
    --name|-n)
      NAME="${2:-}"
      shift 2
      ;;
    --require-docx)
      REQUIRE_DOCX=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      if [[ -z "$INPUT" ]]; then
        INPUT="$1"
        shift
      else
        echo "Unknown argument: $1" >&2
        usage >&2
        exit 1
      fi
      ;;
  esac
done

if [[ -z "${INPUT// }" ]]; then
  usage >&2
  exit 1
fi

if [[ ! -f "$INPUT" ]]; then
  echo "Input file not found: $INPUT" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || pwd)"

if [[ -z "${OUT_DIR// }" ]]; then
  OUT_DIR="$ROOT_DIR/dist/help-articles"
fi

if [[ -z "${NAME// }" ]]; then
  NAME="$(basename "$INPUT")"
  NAME="${NAME%.*}"
fi

mkdir -p "$OUT_DIR"

GMD_OUT="$OUT_DIR/${NAME}.gdocs.md"
HTML_OUT="$OUT_DIR/${NAME}.gdocs.html"
DOCX_OUT="$OUT_DIR/${NAME}.docx"

# Normalize line endings for consistent copy/paste.
perl -pe 's/\r\n/\n/g' "$INPUT" > "$GMD_OUT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required to generate Google Docs HTML output." >&2
  exit 1
fi

python3 "$SCRIPT_DIR/md_to_gdocs_html.py" \
  --input "$GMD_OUT" \
  --output "$HTML_OUT"

DOCX_CREATED=0
if command -v textutil >/dev/null 2>&1; then
  textutil -convert docx "$HTML_OUT" -output "$DOCX_OUT" >/dev/null 2>&1 || true
  if [[ -f "$DOCX_OUT" ]]; then
    DOCX_CREATED=1
  fi
elif command -v pandoc >/dev/null 2>&1; then
  pandoc "$HTML_OUT" -o "$DOCX_OUT" >/dev/null 2>&1 || true
  if [[ -f "$DOCX_OUT" ]]; then
    DOCX_CREATED=1
  fi
fi

echo "Created outputs:"
echo "- Google Docs copy format (Markdown): $GMD_OUT"
echo "- Google Docs copy format (HTML): $HTML_OUT"
if [[ "$DOCX_CREATED" -eq 1 ]]; then
  python3 "$SCRIPT_DIR/modernize_docx.py" --input "$DOCX_OUT" --compatibility-mode 16
  echo "- DOCX file: $DOCX_OUT"
else
  if [[ "$REQUIRE_DOCX" -eq 1 ]]; then
    echo "- DOCX file: failed"
    echo "ERROR: DOCX export is required but not available. Ensure textutil or pandoc is installed and accessible." >&2
    exit 2
  fi
  echo "- DOCX file: not created (install textutil or pandoc to enable DOCX export)"
fi

echo ""
echo "How to use:"
echo "1. Open $HTML_OUT in a browser, copy all, then paste into Google Docs."
if [[ "$DOCX_CREATED" -eq 1 ]]; then
  echo "2. Or upload $DOCX_OUT directly to Google Drive and open with Google Docs."
fi
