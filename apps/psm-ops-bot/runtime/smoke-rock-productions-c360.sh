#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_dir="${PSM_OPS_SOURCE_DIR:-$(cd "$script_dir/.." && pwd)}"
profile_dir="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/psmopsbot}"
mcp_dir="$source_dir/runtime/mcp"

if [ -f "$profile_dir/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$profile_dir/.env"
  set +a
fi

python_bin="${PSM_OPS_PYTHON:-}"
if [ -z "$python_bin" ]; then
  if [ -x "$HOME/.hermes/hermes-agent/venv/bin/python" ]; then
    python_bin="$HOME/.hermes/hermes-agent/venv/bin/python"
  else
    python_bin="python3"
  fi
fi

"$python_bin" - "$mcp_dir" <<'PY'
import json
import sys

mcp_dir = sys.argv[1]
sys.path.insert(0, mcp_dir)

from psm_c360_server import search_c360_customers  # noqa: E402


EXPECTED_HUBSPOT_ID = "8051493928"
EXPECTED_COMPANY = "rock productions pte ltd"
EXPECTED_ORG = "rock productions"
EXPECTED_VARIANTS = {
    "proj-cs-rockproductions",
    "rockproductions",
    "rock productions",
    "rock production",
    "Rock Productions Pte Ltd",
}


def fail(reason, payload=None):
    print(f"c360:rock-productions:{reason}")
    if payload is not None:
        safe_payload = {
            "searched_variants": payload.get("searched_variants"),
            "match_count": payload.get("match_count"),
            "missing_mapping": payload.get("missing_mapping"),
            "confidence": payload.get("confidence"),
            "caveat": payload.get("caveat"),
        }
        print(json.dumps(safe_payload, sort_keys=True))
    raise SystemExit(1)


result = search_c360_customers("proj-cs-rockproductions", limit=5)
if result.get("confidence") == "blocked":
    fail("blocked", result)
if result.get("missing_mapping") is not False:
    fail("missing-mapping", result)
if int(result.get("match_count") or 0) < 1:
    fail("no-matches", result)

variants = result.get("searched_variants")
if not isinstance(variants, list) or not EXPECTED_VARIANTS.issubset(set(variants)):
    fail("missing-variants", result)

matches = result.get("answer")
if not isinstance(matches, list):
    fail("bad-answer-shape", result)

rock_match = None
for match in matches:
    if not isinstance(match, dict):
        continue
    hubspot_id = str(match.get("hubspotCompanyId") or "")
    company_name = str(match.get("companyName") or "").strip().lower()
    if hubspot_id == EXPECTED_HUBSPOT_ID and company_name == EXPECTED_COMPANY:
        rock_match = match
        break

if rock_match is None:
    fail("expected-company-not-found", result)

org_matches = rock_match.get("orgMatches")
if not isinstance(org_matches, list):
    fail("missing-org-matches", result)

org_names = {
    str(
        item.get("matchedValue")
        or item.get("name")
        or item.get("orgName")
        or item.get("organisationName")
        or item.get("organizationName")
        or ""
    ).strip().lower()
    for item in org_matches
    if isinstance(item, dict)
}
if EXPECTED_ORG not in org_names:
    fail("expected-org-not-found", result)

matched_fields = rock_match.get("matchedFields")
if isinstance(matched_fields, list) and "StaffAny org" not in matched_fields:
    fail("missing-staffany-org-match-field", result)

print("c360:rock-productions:ok:hubspot=8051493928:org=Rock Productions")
PY
