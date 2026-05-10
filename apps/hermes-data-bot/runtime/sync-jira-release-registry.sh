#!/usr/bin/env bash
set -euo pipefail

JIRA_BASE_URL="${JIRA_BASE_URL:-}"
JIRA_EMAIL="${JIRA_EMAIL:-}"
JIRA_API_TOKEN="${JIRA_API_TOKEN:-}"
JIRA_JQL="${JIRA_JQL:-project = KER AND \"Launch Priority\" = \"P1 - High Reach Retention and Growth\" ORDER BY updated DESC}"
JIRA_MAX_RESULTS="${JIRA_MAX_RESULTS:-100}"
JIRA_FIELD_CANDIDATE_RE="${JIRA_FIELD_CANDIDATE_RE:-launch|priority|gtm|release|rollout}"
JIRA_LAUNCH_PRIORITY_FIELD_ID="${JIRA_LAUNCH_PRIORITY_FIELD_ID:-}"
JIRA_LAUNCH_PRIORITY_FIELD_NAME="${JIRA_LAUNCH_PRIORITY_FIELD_NAME:-}"
JIRA_HIGH_PRIORITY_VALUES="${JIRA_HIGH_PRIORITY_VALUES:-}"

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

need_command() {
  command -v "$1" >/dev/null 2>&1 || fail "dependency:$1:not-found"
}

need_env() {
  [ -n "${!1:-}" ] || fail "env:$1:missing"
}

jira_get() {
  curl -fsS -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
    -H "Accept: application/json" \
    "$JIRA_BASE_URL$1"
}

jira_post() {
  curl -fsS -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    --data "$2" \
    "$JIRA_BASE_URL$1"
}

need_command curl
need_command jq
need_env JIRA_BASE_URL
need_env JIRA_EMAIL
need_env JIRA_API_TOKEN

JIRA_BASE_URL="${JIRA_BASE_URL%/}"
fields_json="$(jira_get "/rest/api/3/field")"

if [ -z "$JIRA_LAUNCH_PRIORITY_FIELD_ID" ] || [ -z "$JIRA_HIGH_PRIORITY_VALUES" ]; then
  printf '# Jira Launch Priority Field Candidates\n\n'
  printf 'Review these candidates, then rerun with JIRA_LAUNCH_PRIORITY_FIELD_ID and JIRA_HIGH_PRIORITY_VALUES.\n\n'
  printf '| jira_field_id | jira_field_name | schema_type | schema_custom |\n'
  printf '| --- | --- | --- | --- |\n'
  printf '%s\n' "$fields_json" | jq -r --arg re "$JIRA_FIELD_CANDIDATE_RE" '
    .[]
    | select((.name // "") | test($re; "i"))
    | "| \(.id // "") | \((.name // "") | gsub("\\|"; "/")) | \(.schema.type // "") | \(.schema.custom // "") |"
  '
  fail "sync:priority-mapping-needs-confirmation"
fi

JIRA_LAUNCH_PRIORITY_FIELD_NAME="${JIRA_LAUNCH_PRIORITY_FIELD_NAME:-$JIRA_LAUNCH_PRIORITY_FIELD_ID}"
sync_timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
search_body="$(
  jq -n \
    --arg jql "$JIRA_JQL" \
    --arg field_id "$JIRA_LAUNCH_PRIORITY_FIELD_ID" \
    --argjson max_results "$JIRA_MAX_RESULTS" \
    '{
      jql: $jql,
      maxResults: $max_results,
      fields: [
        "summary",
        "fixVersions",
        "components",
        "assignee",
        "status",
        "priority",
        $field_id
      ]
    }'
)"
issues_json="$(jira_post "/rest/api/3/search/jql" "$search_body")"

printf '# StaffAny Release Feature Registry Draft\n\n'
printf 'Generated at `%s` from Jira JQL: `%s`.\n\n' "$sync_timestamp" "$JIRA_JQL"
printf 'Review before copying rows into `skills/staffany-data-bot/references/staffany-release-feature-registry.md`.\n\n'
printf '## Priority Mapping\n\n'
printf '| mapping_key | jira_field_id | jira_field_name | candidate_values | included_high_priority_values | status | confirmed_by | confirmed_at | notes |\n'
printf '| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n'
printf '| launch_priority | %s | %s | review Jira values | %s | confirmed | TBD | TBD | Confirmed outside Hermes before registry promotion. |\n\n' \
  "$JIRA_LAUNCH_PRIORITY_FIELD_ID" \
  "$JIRA_LAUNCH_PRIORITY_FIELD_NAME" \
  "$JIRA_HIGH_PRIORITY_VALUES"

printf '## Release Feature Rows\n\n'
printf '| jira_issue_key | release_version | release_date | canonical_feature_name | product_area | launch_priority_field | launch_priority_value | priority_mapping_status | priority_class | usage_metric_key | source_table_hint | owner | sync_timestamp | tracking_status | caveat |\n'
printf '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n'
printf '%s\n' "$issues_json" | jq -r \
  --arg field_id "$JIRA_LAUNCH_PRIORITY_FIELD_ID" \
  --arg field_name "$JIRA_LAUNCH_PRIORITY_FIELD_NAME" \
  --arg high_values "$JIRA_HIGH_PRIORITY_VALUES" \
  --arg sync_timestamp "$sync_timestamp" '
  def clean:
    tostring
    | gsub("\\|"; "/")
    | gsub("[\r\n]+"; " ")
    | gsub("^ +| +$"; "");

  def field_value($value):
    if $value == null then ""
    elif ($value | type) == "object" then (($value.value // $value.name // $value.displayName // $value.id // "") | tostring)
    elif ($value | type) == "array" then ($value | map(if (type == "object") then (.value // .name // .displayName // .id // "") else tostring end) | join(";"))
    else ($value | tostring)
    end;

  ($high_values | split(",") | map(ascii_downcase | gsub("^ +| +$"; ""))) as $high
  | (.issues // [])[]
  | .fields as $fields
  | (field_value($fields[$field_id])) as $priority_value
  | ($priority_value | split(";") | map(ascii_downcase | gsub("^ +| +$"; ""))) as $priority_values
  | (any($priority_values[]; . as $candidate | ($high | index($candidate)) != null)) as $is_high
  | [
      (.key // ""),
      (($fields.fixVersions // []) | map(.name // "") | join(";")),
      (($fields.fixVersions // []) | map(.releaseDate // "") | map(select(. != "")) | join(";")),
      ($fields.summary // ""),
      (($fields.components // []) | map(.name // "") | join(";")),
      $field_name,
      $priority_value,
      "confirmed",
      (if $is_high then "high" else "not-high" end),
      (if $is_high then "needs-mapping" else "" end),
      (if $is_high then "needs-mapping" else "" end),
      ($fields.assignee.displayName // ""),
      $sync_timestamp,
      (if $is_high then "needs-mapping" else "ignore" end),
      (if $is_high then "High-priority Jira row needs a reviewed StaffAny usage metric mapping before tracking." else "Not high priority under confirmed launch-priority mapping." end)
    ]
  | "| " + (map(clean) | join(" | ")) + " |"
'
