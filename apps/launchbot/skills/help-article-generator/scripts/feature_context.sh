#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: feature_context.sh --feature "<feature name>" [--max 80] [--repo /path/to/pantheon]

Examples:
  feature_context.sh --feature "Timeclock Sidekick"
  feature_context.sh --feature "Timeclock Sidekick" --repo /path/to/pantheon
  feature_context.sh -f "BPJS calculation pay item" --max 120
USAGE
}

FEATURE=""
MAX=80
REPO_ROOT="${LAUNCH_PANTHEON_REPO:-${PANTHEON_REPO:-}}"
ENABLE_HELP_REF_SCAN="${ENABLE_HELP_REF_SCAN:-0}"
ENABLE_BACKEND_SCAN="${ENABLE_BACKEND_SCAN:-0}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --feature|-f)
      FEATURE="${2:-}"
      shift 2
      ;;
    --max|-m)
      MAX="${2:-80}"
      shift 2
      ;;
    --repo|-r)
      REPO_ROOT="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      if [[ -z "$FEATURE" ]]; then
        FEATURE="$1"
      else
        FEATURE="$FEATURE $1"
      fi
      shift
      ;;
  esac
done

if [[ -z "${FEATURE// }" ]]; then
  usage >&2
  exit 1
fi

if ! [[ "$MAX" =~ ^[0-9]+$ ]]; then
  MAX=80
fi
if (( MAX < 10 )); then
  MAX=10
fi
if (( MAX > 200 )); then
  MAX=200
fi

find_repo_root() {
  local current="$1"
  while [[ "$current" != "/" ]]; do
    if [[ -f "$current/AGENTS.md" && -d "$current/apps" ]]; then
      printf '%s\n' "$current"
      return 0
    fi
    current="$(dirname "$current")"
  done
  return 1
}

if [[ -n "${REPO_ROOT// }" ]]; then
  ROOT="$REPO_ROOT"
elif [[ -f "AGENTS.md" && -d "apps" ]]; then
  ROOT="$PWD"
else
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  ROOT="$(find_repo_root "$SCRIPT_DIR" || true)"
fi

if [[ ! -f "$ROOT/AGENTS.md" || ! -d "$ROOT/apps" ]]; then
  echo "Could not locate Pantheon repo root (missing AGENTS.md/apps)." >&2
  exit 1
fi

lower() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

contains_word() {
  local needle="$1"
  shift
  local current
  for current in "$@"; do
    if [[ "$current" == "$needle" ]]; then
      return 0
    fi
  done
  return 1
}

FEATURE_NORM="$(lower "$FEATURE" | sed -E 's/[^a-z0-9]+/ /g; s/^ +//; s/ +$//')"
STOP_WORDS=(a an and app are by for from in into is of on or staffany the to web with)
TOKENS=()

for word in $FEATURE_NORM; do
  if (( ${#word} < 3 )); then
    continue
  fi
  if contains_word "$word" "${STOP_WORDS[@]}"; then
    continue
  fi
  if ! contains_word "$word" "${TOKENS[@]-}"; then
    TOKENS+=("$word")
  fi
done

SEARCH_TERMS=("$FEATURE")
for token in "${TOKENS[@]-}"; do
  SEARCH_TERMS+=("$token")
done

extract_links() {
  local source="$1"
  local file="$2"

  if [[ ! -f "$file" ]]; then
    return 0
  fi

  sed -nE "s/^[[:space:]]*([A-Z0-9_]+)[[:space:]]*:[[:space:]]*'([^']+)'.*$/\1\t\2/p" "$file" \
    | awk -F'\t' -v src="$source" '{ print src "\t" $1 "\t" $2 }'
}

LINK_ROWS="$({
  extract_links "gryphon" "$ROOT/apps/gryphon/src/common/data/knowledgeBaseLinks.ts"
  extract_links "pixie" "$ROOT/apps/pixie/src/common/data/IntercomArticleLinks.ts"
} || true)"

TOKEN_JOINED="${TOKENS[*]-}"
SCORED_LINKS=""

if [[ -n "${LINK_ROWS// }" ]]; then
  SCORED_LINKS="$(printf '%s\n' "$LINK_ROWS" | awk -F'\t' -v phrase="$FEATURE_NORM" -v tokens="$TOKEN_JOINED" '
    {
      source=$1
      key=$2
      url=$3
      hay=tolower(key " " url)
      score=0

      if (phrase != "" && index(hay, phrase) > 0) {
        score += 8
      }

      n=split(tokens, arr, " ")
      for (i = 1; i <= n; i++) {
        t=arr[i]
        if (t == "") {
          continue
        }
        if (index(hay, t) > 0) {
          score += 2
        }
        if (index(tolower(key), t) > 0) {
          score += 1
        }
      }

      if (score > 0) {
        print score "\t" source "\t" key "\t" url
      }
    }
  ' | sort -t "$(printf '\t')" -k1,1nr | head -n 15)"
fi

run_search() {
  local max_lines="$1"
  shift
  local candidates=("$@")
  local existing=()
  local p

  for p in "${candidates[@]}"; do
    if [[ -e "$ROOT/$p" ]]; then
      existing+=("$ROOT/$p")
    fi
  done

  if (( ${#existing[@]} == 0 )); then
    return 0
  fi

  local rg_args=(-n -i --no-heading --color never -F)
  local term
  for term in "${SEARCH_TERMS[@]}"; do
    if [[ -n "${term// }" ]]; then
      rg_args+=(-e "$term")
    fi
  done

  local raw
  local capture_limit=$((max_lines * 20))
  raw="$(rg "${rg_args[@]}" "${existing[@]}" 2>/dev/null | head -n "$capture_limit" || true)"

  if [[ -z "${raw//[$'\n\t ']/}" ]]; then
    return 0
  fi

  local filtered=""
  local token_count=0
  token_count="${#TOKENS[@]-0}"
  if (( token_count >= 2 )); then
    filtered="$(printf '%s\n' "$raw" | awk -v tokens="$TOKEN_JOINED" '
      {
        line=tolower($0)
        n=split(tokens, arr, " ")
        hits=0
        for (i = 1; i <= n; i++) {
          t=arr[i]
          if (t == "") {
            continue
          }
          if (index(line, t) > 0) {
            hits += 1
          }
        }
        if (hits >= 2) {
          print
        }
      }
    ')"
  fi

  if [[ -n "${filtered//[$'\n\t ']/}" ]]; then
    raw="$filtered"
  fi

  printf '%s\n' "$raw" \
    | awk 'NF' \
    | awk '!seen[$0]++' \
    | head -n "$max_lines" || true
}

format_section() {
  local title="$1"
  local payload="$2"

  echo "## $title"
  echo

  if [[ -z "${payload//[$'\n\t ']/}" ]]; then
    echo "- No direct matches found."
    echo
    return
  fi

  while IFS= read -r line; do
    [[ -z "$line" ]] && continue

    local file="${line%%:*}"
    local rest="${line#*:}"
    local row="${rest%%:*}"
    local snippet="${rest#*:}"

    snippet="$(printf '%s' "$snippet" | tr '\t' ' ' | sed -E 's/[[:space:]]+/ /g; s/^ //; s/ $//')"
    snippet="${snippet:0:180}"

    echo "- $file:$row - $snippet"
  done <<< "$payload"

  echo
}

TOP_FILES=()
add_top_file() {
  local file="$1"
  local existing

  [[ -z "$file" ]] && return

  for existing in "${TOP_FILES[@]-}"; do
    if [[ "$existing" == "$file" ]]; then
      return
    fi
  done

  TOP_FILES+=("$file")
}

collect_top_files() {
  local payload="$1"
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    add_top_file "${line%%:*}"
  done <<< "$payload"
}

WEB_REFS="$(run_search "$MAX" \
  apps/gryphon/src/main/settings \
  apps/gryphon/src/main/payroll \
  apps/gryphon/src/main/leave \
  apps/gryphon/src/common/data/knowledgeBaseLinks.ts)"

MOBILE_REFS="$(run_search "$MAX" \
  apps/pixie/src/profile/settings \
  apps/pixie/src/profile/companyDocuments \
  apps/pixie/src/onBoarding \
  apps/pixie/src/common/data/IntercomArticleLinks.ts)"

BACKEND_REFS=""
if [[ "$ENABLE_BACKEND_SCAN" == "1" ]]; then
  ORIGINAL_SEARCH_TERMS=("${SEARCH_TERMS[@]-}")
  SEARCH_TERMS=("$FEATURE")
  BACKEND_REFS="$(run_search "$MAX" \
    apps/kraken/src/server/index.ts \
    apps/kraken/src/server/lib \
    apps/kraken/src/server/plugins)"
  SEARCH_TERMS=("${ORIGINAL_SEARCH_TERMS[@]-}")
fi

HELP_REFS=""

if [[ "$ENABLE_HELP_REF_SCAN" == "1" && -n "${SCORED_LINKS// }" ]]; then
  TOP_LINK_ROWS="$(printf '%s\n' "$SCORED_LINKS" | head -n 8)"
  while IFS=$'\t' read -r _score source key _url; do
    [[ -z "$key" ]] && continue

    if [[ "$source" == "gryphon" ]]; then
      HELP_REFS+="$(rg -n --no-heading --color never -F "KNOWLEDGE_BASE_LINKS.$key" "$ROOT/apps/gryphon/src" 2>/dev/null | head -n "$MAX" || true)"
      HELP_REFS+=$'\n'
    fi

    if [[ "$source" == "pixie" ]]; then
      HELP_REFS+="$(rg -n --no-heading --color never -F "IntercomArticleLinks.$key" "$ROOT/apps/pixie/src" 2>/dev/null | head -n "$MAX" || true)"
      HELP_REFS+=$'\n'
      HELP_REFS+="$(rg -n --no-heading --color never -F "INTERCOM_ARTICLE_LINKS.$key" "$ROOT/apps/pixie/src" 2>/dev/null | head -n "$MAX" || true)"
      HELP_REFS+=$'\n'
    fi
  done <<< "$TOP_LINK_ROWS"
fi

HELP_REFS="$(printf '%s\n' "$HELP_REFS" | awk 'NF' | awk '!seen[$0]++' | head -n "$MAX" || true)"

collect_top_files "$WEB_REFS"
collect_top_files "$MOBILE_REFS"
collect_top_files "$BACKEND_REFS"
collect_top_files "$HELP_REFS"

echo "# Help Article Context Pack"
echo
echo "- Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "- Repository: $ROOT"
echo "- Feature Query: $FEATURE"
if (( ${#TOKENS[@]} > 0 )); then
  echo "- Search Tokens: ${TOKENS[*]-}"
else
  echo "- Search Tokens: (none)"
fi

echo
echo "## Existing Help Center Links"
echo

if [[ -z "${SCORED_LINKS//[$'\n\t ']/}" ]]; then
  echo "- No close link matches found in code constants."
else
  echo "| Source | Key | URL |"
  echo "| --- | --- | --- |"
  while IFS=$'\t' read -r _score source key url; do
    [[ -z "$key" ]] && continue
    echo "| $source | $key | $url |"
  done <<< "$SCORED_LINKS"
fi

echo
format_section "Web Settings References (Gryphon)" "$WEB_REFS"
format_section "Mobile References (Pixie)" "$MOBILE_REFS"
format_section "Backend References (Kraken)" "$BACKEND_REFS"
format_section "Help-Link Usage References" "$HELP_REFS"

echo "## Suggested Files To Open First"
echo

if (( ${#TOP_FILES[@]-0} == 0 )); then
  echo "1. No specific files found; broaden feature query keywords."
else
  index=1
  for file in "${TOP_FILES[@]-}"; do
    echo "$index. $file"
    index=$((index + 1))
    if (( index > 12 )); then
      break
    fi
  done
fi

echo
echo "## Drafting Notes"
echo
echo "- Use exact UI labels/options from evidence lines when available."
echo "- If values/defaults are unclear, mark them under assumptions instead of asserting."
echo "- Keep setup steps in click-path order, then add a settings table and troubleshooting."
