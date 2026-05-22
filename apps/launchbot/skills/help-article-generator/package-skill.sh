#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || pwd)"
OUT_DIR="${1:-$ROOT_DIR/dist}"
VERSION="$(cat "$SCRIPT_DIR/VERSION")"
DATE_TAG="$(date +%Y%m%d)"
PKG_NAME="help-article-generator-skill-v${VERSION}-${DATE_TAG}"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

mkdir -p "$OUT_DIR"
mkdir -p "$TMP_DIR/$PKG_NAME/help-article-generator"

cp "$SCRIPT_DIR/SKILL.md" "$TMP_DIR/$PKG_NAME/help-article-generator/"
cp "$SCRIPT_DIR/README.md" "$TMP_DIR/$PKG_NAME/help-article-generator/"
cp "$SCRIPT_DIR/VERSION" "$TMP_DIR/$PKG_NAME/help-article-generator/"
cp "$SCRIPT_DIR/.gitignore" "$TMP_DIR/$PKG_NAME/help-article-generator/"
cp -R "$SCRIPT_DIR/agents" "$TMP_DIR/$PKG_NAME/help-article-generator/"
cp -R "$SCRIPT_DIR/references" "$TMP_DIR/$PKG_NAME/help-article-generator/"
cp -R "$SCRIPT_DIR/scripts" "$TMP_DIR/$PKG_NAME/help-article-generator/"
cp -R "$SCRIPT_DIR/templates" "$TMP_DIR/$PKG_NAME/help-article-generator/"

(
  cd "$TMP_DIR"
  tar -czf "$OUT_DIR/$PKG_NAME.tar.gz" "$PKG_NAME"
  zip -qr "$OUT_DIR/$PKG_NAME.zip" "$PKG_NAME"
)

(
  cd "$OUT_DIR"
  shasum -a 256 "$PKG_NAME.tar.gz" "$PKG_NAME.zip" > "$PKG_NAME.sha256"
)

echo "Created:"
echo "- $OUT_DIR/$PKG_NAME.zip"
echo "- $OUT_DIR/$PKG_NAME.tar.gz"
echo "- $OUT_DIR/$PKG_NAME.sha256"
