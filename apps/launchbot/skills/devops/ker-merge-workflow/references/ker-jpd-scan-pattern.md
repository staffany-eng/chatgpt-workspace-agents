# KER JPD Range-Scan Pattern

## Why This Exists

KER is a Jira Product Discovery (JPD) project.

**JQL search status (verified 2026-06):**
- `POST /rest/api/3/search` → **410 Gone** (endpoint removed by Atlassian)
- `GET /rest/api/3/search?jql=...` → **410 Gone** (same)
- `POST /rest/api/3/search/jql` → ✅ **works** for `summary ~` queries on KER

Use `POST /rest/api/3/search/jql` as the primary search path. Range-scan (below) is only needed when `summary ~` doesn't match well enough or you need description-level matching.

Individual issue fetch (`GET /rest/api/3/issue/KER-{N}`) always works.

## Python Script Template

Write to `/tmp/ker_scan.py` and run `python3 /tmp/ker_scan.py`.

```python
import requests

# Load env from absolute path — ~ expansion breaks on this VM ($HOME = profile subdir)
env = {}
with open("/home/leekaiyi/.hermes/profiles/launchbot/.env") as f:
    for line in f:
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")

email = env["JIRA_EMAIL"]
token = env["JIRA_API_TOKEN"]
base = "https://staffany.atlassian.net"

# === CUSTOMISE THESE PER REQUEST ===
start = 2130          # latest known KER number (update as backlog grows)
stop = 1900           # scan back this far; use 1500 for older feature areas
keywords = [          # lowercase; match against summary
    "citizenship",
    "my team",
    "identity",
    "column",
    "nric",
]
# ====================================

results = []
for num in range(start, stop, -1):
    key = f"KER-{num}"
    r = requests.get(
        f"{base}/rest/api/3/issue/{key}",
        auth=(email, token),
        headers={"Accept": "application/json"},
        params={"fields": "key,summary,status"},
        timeout=10,
    )
    if r.ok:
        d = r.json()
        summary = d["fields"].get("summary", "").lower()
        status = d["fields"].get("status", {}).get("name", "?")
        matched = [kw for kw in keywords if kw in summary]
        if matched:
            results.append((key, d["fields"]["summary"], status, matched))
    if num % 50 == 0:
        print(f"  ... scanned to KER-{num}, {len(results)} hits so far")

print(f"\n=== {len(results)} matches ===")
for key, summary, status, matched in results:
    print(f"{key} | {summary} | {status} | keywords: {matched}")
```

## Fetching Full Description for a Candidate

```python
def extract_text(node):
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        return "".join(extract_text(c) for c in node.get("content", []))
    return ""

r = requests.get(
    f"{base}/rest/api/3/issue/KER-XXXX",
    auth=(email, token),
    headers={"Accept": "application/json"},
    params={"fields": "key,summary,status,description"},
    timeout=10,
)
d = r.json()
print(extract_text(d["fields"].get("description") or {}))
```

## HubSpot Company Disambiguation

When multiple HubSpot results appear for a company name, pick the right one by:
1. `lifecyclestage = customer` over `lead`
2. Most recent `hs_lastmodifieddate`
3. Domain matches the requester's known domain (e.g. `tomoro-coffee.sg` vs `.com`)

```python
import requests

hs_token = env["HUBSPOT_PRIVATE_APP_TOKEN"]

r = requests.post(
    "https://api.hubapi.com/crm/v3/objects/companies/search",
    headers={"Authorization": f"Bearer {hs_token}", "Content-Type": "application/json"},
    json={
        "filterGroups": [{"filters": [{
            "propertyName": "name",
            "operator": "CONTAINS_TOKEN",
            "value": "company name"
        }]}],
        "properties": ["name", "hs_object_id", "domain", "lifecyclestage", "hs_lastmodifieddate"],
        "limit": 10,
    },
    timeout=15,
)
for co in r.json().get("results", []):
    p = co["properties"]
    print(co["id"], p.get("name"), p.get("lifecyclestage"), p.get("domain"), p.get("hs_lastmodifieddate"))
```

## Known KER Number Ranges (update as backlog grows)

| Range          | Notes                                   |
|----------------|-----------------------------------------|
| KER-2220–2223  | Latest as of 2026-06 (session ceiling)  |
| KER-2100–2220  | 2026 features                           |
| KER-1900–2100  | 2025–2026 features                      |
| KER-1600–1900  | 2024–2025 features                      |
| KER-1000–1600  | Older; scan only if feature area is old |
