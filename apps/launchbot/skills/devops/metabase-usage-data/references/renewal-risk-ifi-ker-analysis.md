# Renewal Risk + IFI/KER Analysis — Working Reference

Captured from session 2026-06-09. Full working pattern for cross-referencing
renewing orgs against IFI tickets and KER backlog.

## Jira API Notes

- **`/rest/api/3/search` (GET) returns HTTP 410** — removed by Atlassian.
- Use **`POST /rest/api/3/search/jql`** with JSON body `{jql, fields, maxResults, nextPageToken}`.
- Paginate with `nextPageToken` from response until it's absent or issues is empty.
- Auth: `requests` with `auth=(email, token)` — Basic auth. Strip quotes from `.env` values.
- `.env` values may have surrounding single quotes — always `.strip("'").strip('"')` after reading.

## IFI Data Shape

- **3,872 IFI issues** as of 2026-06-09 (StaffAny Jira).
- `customfield_10881` = HubSpot Company ID — **only populated on newer IFI tickets** (~2025+). Unreliable for historical org lookup.
- Org names appear in IFI **summaries**:
  - Imported insights: `[Imported Insight] KER-NNN: ...org name in body...`
  - Live tickets: usually end with ` — Org Name` or ` - Org Name`
- KER links are in `issuelinks` field as `inwardIssue` / `outwardIssue` with key `KER-NNN`.

## Full Script (fetch all IFI + match orgs + extract KER + fetch KER details)

```python
import requests, json
from collections import defaultdict

# 1. Load creds
with open('/home/leekaiyi/.hermes/profiles/launchbot/.env') as f:
    env = {}
    for line in f:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            env[k] = v.strip("'").strip('"')

base_url = env['JIRA_BASE_URL']
auth = (env['JIRA_EMAIL'], env['JIRA_API_TOKEN'])

# 2. Fetch all IFI issues (paginated)
all_issues = []
cursor = None
while True:
    body = {
        'jql': 'project=IFI ORDER BY created DESC',
        'fields': ['summary', 'customfield_10881', 'status', 'issuelinks'],
        'maxResults': 100
    }
    if cursor:
        body['nextPageToken'] = cursor
    resp = requests.post(f'{base_url}/rest/api/3/search/jql', json=body, auth=auth, timeout=30)
    d = resp.json()
    issues = d.get('issues', [])
    all_issues.extend(issues)
    cursor = d.get('nextPageToken')
    if not cursor or not issues:
        break

print(f'Total IFI: {len(all_issues)}')

# 3. Define org search terms (use multiple name variants)
org_search_terms = {
    'Org Display Name': ['search term 1', 'search term 2'],
    # ...
}

# 4. Match orgs to IFI by summary substring
ker_to_orgs = defaultdict(set)
org_ifi_issues = defaultdict(list)

for issue in all_issues:
    summary = (issue['fields'].get('summary') or '').lower()
    links = issue['fields'].get('issuelinks', []) or []
    ker_keys = []
    for link in links:
        for side in ['inwardIssue', 'outwardIssue']:
            linked = link.get(side, {})
            if linked and linked.get('key', '').startswith('KER-'):
                ker_keys.append(linked['key'])
    for org, terms in org_search_terms.items():
        for term in terms:
            if term.lower() in summary:
                org_ifi_issues[org].append(issue['key'])
                for k in ker_keys:
                    ker_to_orgs[k].add(org)
                break

# 5. Fetch KER details
ker_keys_list = list(ker_to_orgs.keys())
jql = 'project=KER AND key in (' + ','.join(ker_keys_list) + ')'
resp = requests.post(
    f'{base_url}/rest/api/3/search/jql',
    json={'jql': jql, 'fields': ['summary', 'status'], 'maxResults': 100},
    auth=auth, timeout=30
)
ker_issues = {i['key']: i for i in resp.json().get('issues', [])}

# 6. IFI demand count per KER (cross-org reach proxy)
ker_demand = defaultdict(int)
for issue in all_issues:
    for link in (issue['fields'].get('issuelinks', []) or []):
        for side in ['inwardIssue', 'outwardIssue']:
            linked = link.get(side, {})
            if linked and linked.get('key', '') in ker_issues:
                ker_demand[linked['key']] += 1
```

## Step 6 — Total-Reach MRR per KER

After building `ker_to_orgs` (KER key → set of org names from all IFI), sum MRR from the Metabase data for all those orgs. This gives the "total MRR at stake" per KER across the entire customer base — not limited to renewing orgs.

```python
# Build org → MRR lookup (use organisation_name from Metabase records)
org_mrr = {r['organisation_name']: r.get('company_mrr', 0) or 0 for r in records}

# Per-KER: sum MRR of all orgs that have an IFI linked to this KER
ker_total_mrr = {}
for ker_key, orgs in ker_to_orgs.items():
    total = sum(org_mrr.get(org, 0) for org in orgs)
    unknown = [org for org in orgs if org not in org_mrr]
    ker_total_mrr[ker_key] = {'mrr': total, 'mrr_unknown_orgs': unknown}
```

**Caveat:** Org name matching between Metabase `organisation_name` and IFI summary text is fuzzy and uses multi-variant search terms. Orgs that don't match any Metabase record will produce 0 MRR — list them under `mrr_unknown_orgs` so they're auditable.

## Output Table (final KER report)

```
KER key | status | IFI demand | total MRR (all IFI orgs) | # red renewing orgs | summary
KER-318 | In Progress | 62 IFI | SGD 45,200 | 8 | <summary>
KER-27  | Backlog     | 62 IFI | SGD 38,100 | 6 | <summary>
...
```

- **IFI demand** — total IFI issues linked to this KER (all orgs, all time)
- **total MRR** — sum of `company_mrr` for all Metabase orgs whose org name matched any IFI linked to this KER
- **# red renewing orgs** — count of red health orgs renewing the target quarter that have an IFI linked to this KER



For each red renewing org:
- List IFI ticket count (0 = blind spot ❌)
- List linked KER keys

For each unique KER:
- `KER-NNN | status | IFI_demand IFI | N_red_orgs red orgs | summary`

Highlight:
- **Shipped KERs** → CS/PSM talking point for retention
- **In-sprint KERs** → communicate ETA before renewal date
- **Backlog KERs with high demand** → escalation candidates
- **Orgs with zero IFI** → PSM blind spots, need outreach

## Q3 2026 Snapshot (reference)

- 146 orgs renewing Q3, SGD 61,425 MRR
- 37 red health, SGD 11,879 MRR
- 17/37 red orgs had IFI (SGD 3,653 MRR covered)
- 18/37 red orgs had **no IFI at all** (SGD 8,226 MRR — blind spots)
- 45 unique KER tickets surfaced; top demand: KER-318 (62 IFI), KER-27 (62), KER-1288 (56), KER-12 (48), KER-23 (48)
- FU HUI GEN TANG (SGD 5,530, no PSM, no IFI) was largest single blind spot
