#!/usr/bin/env bash
# Fetches Metabase card 2257 (All Usages Pivot Filter, past 1 month)
# Output: /home/leekaiyi/.hermes/profiles/launchbot/data/metabase_card_2257.json
# Runs daily via Hermes cron. Silent on success, non-zero exit on failure.

set -euo pipefail

OUTPUT_DIR="/home/leekaiyi/.hermes/profiles/launchbot/data"
OUTPUT_FILE="${OUTPUT_DIR}/metabase_card_2257.json"
TMP_BODY=$(mktemp)
ENV_FILE="/home/leekaiyi/.hermes/profiles/launchbot/.env"

mkdir -p "$OUTPUT_DIR"

# Read token from .env
METABASE_TOKEN=$(grep '^METABASE_TOKEN=' "$ENV_FILE" | sed 's/^METABASE_TOKEN=//')
if [[ -z "$METABASE_TOKEN" ]]; then
  echo "ERROR: METABASE_TOKEN not found in $ENV_FILE"
  exit 1
fi

HTTP_STATUS=$(curl -s -o "$TMP_BODY" -w "%{http_code}" \
  'https://metabase.staffany.com/api/card/2257/query' \
  -H 'accept: application/json' \
  -H 'content-type: application/json' \
  -H "X-API-Key: ${METABASE_TOKEN}" \
  -H 'origin: https://metabase.staffany.com' \
  -H 'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36' \
  --data-raw '{"ignore_cache":false,"collection_preview":false,"parameters":[{"id":"dd44614d-d0d6-b43d-93e5-653f6f0ee709","type":"date/all-options","value":"past1months","target":["dimension",["template-tag","startweek"]]},{"id":"2b8a23de-cf30-fd56-bb51-1e2645112ea1","type":"date/all-options","value":null,"target":["dimension",["template-tag","deal_end"]]},{"id":"32039445-7561-524f-ad8e-8f8738386471","type":"string/=","value":null,"target":["dimension",["template-tag","company_country"]]}]}')

if [[ "$HTTP_STATUS" != "202" && "$HTTP_STATUS" != "200" ]]; then
  echo "ERROR: Metabase card 2257 fetch failed — HTTP $HTTP_STATUS"
  cat "$TMP_BODY" | head -c 500
  rm -f "$TMP_BODY"
  exit 1
fi

python3 - "$TMP_BODY" "$OUTPUT_FILE" <<'PYEOF'
import json, sys
from datetime import datetime, timezone

tmp_path, out_path = sys.argv[1], sys.argv[2]
with open(tmp_path) as f:
    body = json.load(f)

wrapped = {
    "fetched_at": datetime.now(timezone.utc).isoformat(),
    "card_id": 2257,
    "card_url": "https://metabase.staffany.com/question/2257-all-usages-pivot-filter",
    "parameters": {"startweek": "past1months", "deal_end": None, "company_country": None},
    "data": body
}
with open(out_path, "w") as f:
    json.dump(wrapped, f, indent=2)
print(f"OK: saved to {out_path}")
PYEOF

rm -f "$TMP_BODY"
