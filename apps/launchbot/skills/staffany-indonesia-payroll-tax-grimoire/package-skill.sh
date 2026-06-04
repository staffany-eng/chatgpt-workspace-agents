#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"
SKILLS_ROOT="$SCRIPT_DIR/skills"
OUT_DIR_INPUT="${1:-$ROOT_DIR/dist}"
mkdir -p "$OUT_DIR_INPUT"
OUT_DIR="$(cd "$OUT_DIR_INPUT" && pwd)"
VERSION="$(cat "$SCRIPT_DIR/VERSION")"
DATE_TAG="$(date +%Y%m%d)"
PKG_NAME="staffany-indonesia-payroll-tax-grimoire-v${VERSION}-${DATE_TAG}"
TMP_DIR="$(mktemp -d)"

REQUIRED_SKILLS=(
  "indonesia-payroll-tax-advisor"
  "indonesia-tax-knowledge-updater"
  "pph21-settings-explainer"
)

OPTIONAL_SKILLS=(
  "employee-payroll-breakdown"
)

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

mkdir -p "$TMP_DIR/$PKG_NAME/skills"
mkdir -p "$TMP_DIR/$PKG_NAME/scripts"

for skill in "${REQUIRED_SKILLS[@]}"; do
  if [[ ! -f "$SKILLS_ROOT/$skill/SKILL.md" ]]; then
    echo "Missing required skill: $skill" >&2
    exit 2
  fi
  cp -R "$SKILLS_ROOT/$skill" "$TMP_DIR/$PKG_NAME/skills/"
done

for skill in "${OPTIONAL_SKILLS[@]}"; do
  if [[ -f "$SKILLS_ROOT/$skill/SKILL.md" ]]; then
    cp -R "$SKILLS_ROOT/$skill" "$TMP_DIR/$PKG_NAME/skills/"
  fi
done

# Never distribute local env/config files in a shared skill bundle.
find "$TMP_DIR/$PKG_NAME/skills" -type f \( -name "*.env" -o -name "*.pem" -o -name "*.key" \) -delete

cp "$SCRIPT_DIR/SKILL.md" "$TMP_DIR/$PKG_NAME/"
cp "$SCRIPT_DIR/README.md" "$TMP_DIR/$PKG_NAME/"
cp "$SCRIPT_DIR/VERSION" "$TMP_DIR/$PKG_NAME/"
cp "$SCRIPT_DIR/manifest.json" "$TMP_DIR/$PKG_NAME/"
cp "$SCRIPT_DIR/scripts/quick_validate.py" "$TMP_DIR/$PKG_NAME/scripts/"

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
