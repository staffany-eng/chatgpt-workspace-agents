---
name: ker-merge-workflow
description: Merge duplicate KER tickets (with IFI migration) or split a bundled KER into focused sub-tickets (with Work item split link). Covers all KER structural operations — merge, split, duplicate-linking, roadmap assignment.
---

# KER Merge Workflow

## Trigger

Any message containing "merge KER-X into KER-Y", "merge KER-X with KER-Y", or "consolidate KER-X → KER-Y".

**Do NOT ask for confirmation before executing.** Fetch both tickets, show summaries, then immediately migrate IFIs.

## Abel's Rule (2026-05-29)

> "Whenever merging tickets always move the IFI associated to the new one"

This is a standing rule. Every KER merge = full IFI migration to the target. No exceptions.

## Steps

1. **Fetch both tickets in parallel**
   - GET `/rest/api/3/issue/KER-X?fields=issuelinks,summary`
   - GET `/rest/api/3/issue/KER-Y?fields=issuelinks,summary`
   - Print both summaries so user can confirm identity before mutation.

2. **Extract source IFIs**
   - From KER-X `issuelinks`: collect all `inwardIssue.key` values starting with `IFI`.

3. **Extract target IFIs**
   - From KER-Y `issuelinks`: collect all `inwardIssue.key` values starting with `IFI`.

4. **Diff**
   - `to_link = source_ifis - target_ifis`
   - Never re-link IFIs already on target — the API will 400.

5. **Link each missing IFI to target**
   ```json
   POST /rest/api/3/issueLink
   { "type": {"name": "Relates"}, "inwardIssue": {"key": "IFI-NNN"}, "outwardIssue": {"key": "KER-Y"} }
   ```
   HTTP 201 empty body = success.

6. **Transition sources to Cancelled**
   - For each source ticket (KER-X), POST the Cancelled transition:
   ```bash
   curl -s -o /tmp/trans_resp.txt -w "%{http_code}" \
     -X POST \
     -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
     -H "Content-Type: application/json" \
     --data '{"transition":{"id":"8"}}' \
     "$JIRA_BASE_URL/rest/api/3/issue/KER-X/transitions"
   ```
   HTTP 204 empty body = success. Transition ID `8` = Cancelled (verified on KER project).

7. **Verify**
   - Re-fetch KER-Y `issuelinks`, count IFIs, confirm all expected keys present.

8. **Report**
   - Source: key + summary
   - Target: key + summary
   - IFIs moved: count + full list (or "0 — nothing to migrate" if source had no IFIs)
   - Total IFIs on target post-merge
   - Link to target KER
   - Offer to close old KER as duplicate (one line, no pressure)

**Fast path — source has 0 IFIs:** Skip steps 3–6 IFI migration loop, go straight to marking the Duplicate link, transitioning sources to Cancelled, and reporting. No migration loop needed.

## Curl Patterns (verified working)

```bash
source ~/.hermes/profiles/launchbot/.env

# Fetch
curl -s -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  "$JIRA_BASE_URL/rest/api/3/issue/KER-X?fields=issuelinks,summary" \
  -o /tmp/kerX.json

# Create link (per IFI in loop)
PAYLOAD='{"type":{"name":"Relates"},"inwardIssue":{"key":"IFI-NNN"},"outwardIssue":{"key":"KER-Y"}}'
curl -s -o /tmp/link_resp.txt -w "%{http_code}" \
  -X POST \
  -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  -H "Content-Type: application/json" \
  --data "$PAYLOAD" \
  "$JIRA_BASE_URL/rest/api/3/issueLink"
```

## JSON Parsing (verified working)

Always use heredoc `python3 << 'EOF' ... EOF` — never inline `-c "..."` when field values may contain quotes:

```bash
python3 << 'EOF'
import json
with open('/tmp/kerX.json') as f:
    d = json.load(f)
links = d['fields'].get('issuelinks', [])
ifis = [l['inwardIssue']['key'] for l in links
        if l.get('inwardIssue', {}).get('key', '').startswith('IFI')]
print(ifis)
EOF
```

## Pitfalls

- **`/rest/api/3/search` is 410 Gone** — Atlassian removed both `POST /rest/api/3/search` and `GET /rest/api/3/search?jql=...`. They return HTTP 410 with `"migrate to /rest/api/3/search/jql"`. Use `POST /rest/api/3/search/jql` instead (see KER Backlog Search section above).
- **`JIRA_USER_EMAIL` does not exist in `.env`** — the correct key is `JIRA_EMAIL`. Using the wrong key silently gives empty email → 401 Unauthorized.
- **Polaris merge work item links** — auto-created by Jira Polaris when the merge is triggered in the UI. They appear as `[Polaris merge work item link inward/outward]`. Ignore them; don't try to create via API.
- **`-c "..."` inline Python breaks** — field summaries often contain quotes. Always use heredoc.
- **`-w "%{http_code}"` + `-o /tmp/resp.txt`** — success body is empty; status code is the only signal.
- **Target may already have some IFIs** — always diff; never blindly re-link all source IFIs.
- **Old KER is NOT auto-closed** — offer transition to "Duplicate" or "Won't Do" at end of report. Don't do it silently.
- **`fields` NameError in python `-c`** — confirmed gotcha: `d['fields']` in single-quoted shell inline breaks due to quote escaping. Use heredoc.
- **`servicedeskapi/organization` TIMES OUT** — `GET /rest/servicedeskapi/organization` reliably times out (300s+) on the StaffAny instance. Do NOT call it to look up org/company IDs. Instead: embed HubSpot Company ID in the IFI description when available, omit `customfield_10881` if unknown, and ask the user for the HubSpot URL/ID post-creation. Never block IFI creation waiting for org lookup.

## KER Backlog Search — JPD Constraint (applies to all KER operations)

KER is a **Jira Product Discovery (JPD)** project.

### JQL Search — what works and what doesn't (verified 2026-06)

- **`POST /rest/api/3/search`** → **410 Gone** — this endpoint is fully removed by Atlassian. Never use it.
- **`GET /rest/api/3/search?jql=...`** → **410 Gone** — same, also removed.
- **`POST /rest/api/3/search/jql`** → ✅ **works for `summary ~` JQL on KER** — use this.
  - Confirmed working for: `project = KER AND summary ~ "keyword" ORDER BY priority ASC`
  - Also confirmed working: `project = KER AND text ~ "email notification" ORDER BY updated DESC` — full-text `text ~` works on JPD via this endpoint (earlier note was wrong; `text ~` and `summary ~` both work).

```python
import json, urllib.request, base64

env = {}
with open('/home/leekaiyi/.hermes/profiles/launchbot/.env') as f:
    for line in f:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            env[k] = v.strip().strip('"').strip("'")

credentials = base64.b64encode(f"{env['JIRA_EMAIL']}:{env['JIRA_API_TOKEN']}".encode()).decode()
auth_header = f'Basic {credentials}'
base_url = env['JIRA_BASE_URL']

def search_ker(jql, max_results=5):
    payload = json.dumps({'jql': jql, 'maxResults': max_results, 'fields': ['summary', 'status', 'priority']})
    url = f'{base_url}/rest/api/3/search/jql'
    req = urllib.request.Request(url, data=payload.encode(), headers={
        'Authorization': auth_header,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }, method='POST')
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    return [{'key': i['key'], 'summary': i['fields']['summary'],
             'status': i['fields']['status']['name'],
             'priority': (i['fields'].get('priority') or {}).get('name')}
            for i in data.get('issues', [])]

# Example
results = search_ker('project = KER AND summary ~ "manual OT" ORDER BY priority ASC', 3)
for r in results:
    print(r['key'], '|', r['summary'], '|', r['status'])
```

**Fallback — individual fetch + range scan** (when `summary ~` JQL doesn't match well enough):

1. If `Jira-updated.csv` snapshot is absent, scan KER issues by number range using individual `GET /rest/api/3/issue/KER-{N}` requests.
2. Latest known KER number: ~**KER-2210** (as of 2026-06). Scan backward from there.
3. Match summaries against keyword sets derived from the request topic.
4. For candidates with hits, fetch full description to confirm meaning-level match.
5. Scan at least 200 issues back; use 400+ for older feature areas.

**Use a Python script file at `/tmp/ker_scan.py`** — see `references/ker-jpd-scan-pattern.md` for the full template.

**Critical environment pitfall:** `$HOME` resolves to the profile subdir on this VM, not `/home/leekaiyi`. Always load `.env` with the **absolute path** `/home/leekaiyi/.hermes/profiles/launchbot/.env`.

**Shell heredoc + gcloud approach TIMES OUT.** Never use `source ~/.hermes/profiles/launchbot/.env` in a shell heredoc for KER searches. Write a `.py` file and run `python3 /tmp/script.py`.

## IFI Direct Creation (when MCP bd_note extraction produces garbage)

When `preview_ifi_feature_request_from_bd_note` extracts a nonsensical `featureGap` from a long paragraph note, bypass the MCP and POST directly. See `references/ifi-direct-rest-creation.md` for the full Python recipe, key IDs, and pitfalls.

**TL;DR:** `project: {key: IFI}`, `issuetype: {id: "10151"}`, craft `summary` manually, `customfield_10881` = HubSpot Company ID string, OMIT `labels`. issueLink `Relates` with `inwardIssue = IFI-key`, `outwardIssue = KER-key`. 201 empty = success.

## Roadmap / Sprint Assignment on KER tickets

KER is a JPD project — **no agile board, no sprint field**. "Sprint" in KER context means the **Roadmap** dropdown (`customfield_10064`).

### Finding the option ID for a roadmap slot (e.g. S26072)

1. Fetch any KER ticket you know is in the target slot and read `customfield_10064`:
   ```python
   d = api('GET', '/rest/api/3/issue/KER-XXXX?fields=customfield_10064')
   cf = d['fields']['customfield_10064']
   # → {'id': '12101', 'value': '26072'}
   ```
2. The `id` is what you pass when writing: `{"customfield_10064": {"id": "12101"}}`.

### Known Roadmap option IDs (verified 2026-06)

| Roadmap label | Option ID |
|---|---|
| `26071` (sprint S26071) | `12100` |
| `26072` (sprint S26072) | `12101` |
| `26Q2 (Consideration)` | `11071` |
| `26Q3 (Backlog)` | `10626` |
| `25102` | `10691` |

If the target slot isn't in this table, fetch a ticket already in it and read the id.

### Setting Roadmap on a KER ticket

```python
payload = {"fields": {"customfield_10064": {"id": "<option_id>"}}}
status, body = api('PUT', '/rest/api/3/issue/KER-XXXX', payload)
# HTTP 204 empty body = success
```

### Splitting a bundled KER into a focused sub-ticket

Use this when a KER covers multiple distinct concepts and one needs independent delivery/prioritisation.

**Trigger phrases:** "split KER-X into a separate ticket for Y", "create a sub-ticket from KER-X for Y", "separate Y out of KER-X".

**Steps:**

1. **Read the parent** — `read-jira-ticket.mjs --issue KER-X --include-links` to pull summary, description, IFI list, and linked KERs.
2. **Identify Time Bank / sub-concept IFIs** — scan IFI summaries in the linked list to identify which ones belong to the sub-concept being split out. Note their keys for the report; do NOT re-link them automatically (that's a separate clean-up task unless asked).
3. **Create the new KER Idea** — `POST /rest/api/3/issue` with:
   - `project: {key: KER}`, `issuetype: {id: "10043"}` (Idea — only valid type)
   - `summary`: focused name, not a copy of the parent
   - `description`: ADF doc with sections — Problem/Background, Core Use Cases (from IFI evidence), Q3/quarter consideration if relevant, Split From reference, References (PRD TBD, Figma TBD)
   - `priority`: default P2 unless Abel specifies
4. **Link via Work Item Split** — `POST /rest/api/3/issueLink` with type `id: "10201"` ("Work item split"):
   - `inwardIssue`: new KER key (the one "split from" parent)
   - `outwardIssue`: parent KER key (the one "split to" child)
   - HTTP 201 empty body = success
5. **Report** — new KER key + link, parent key, summary of what stays vs what moved, note on IFI re-linking if relevant.

**Q3/quarter consideration note pattern:**
> "Multiple [health] accounts renewing [quarter] have IFI tickets linked to this concept via [parent KER]. [Sub-concept] is a retention risk signal for this quarter. Prioritise scoping by end of [quarter]; aim for design-ready spec so engineering can start [next quarter]."

```python
# Step 4 — Work item split link
payload = {
    "type": {"id": "10201"},          # "Work item split"
    "inwardIssue": {"key": "KER-NEW"},   # split FROM parent
    "outwardIssue": {"key": "KER-PARENT"} # split TO child
}
r = requests.post(f'{base}/rest/api/3/issueLink', json=payload, auth=auth, timeout=15)
# 201 empty body = success
```

**Pitfall:** The `inward/outward` direction for Work item split: `inward = "split from"`, `outward = "split to"`. The new child ticket is the inward issue (it "split from" the parent). The parent is the outward issue (it "split to" the child).

### Linking source tickets as Duplicate of target

When merging KER-A and KER-B into KER-C, mark the sources as duplicates:
```python
payload = {
    "type": {"name": "Duplicate"},
    "inwardIssue": {"key": "KER-A"},   # the one being closed
    "outwardIssue": {"key": "KER-C"}   # the canonical target
}
status, body = api('POST', '/rest/api/3/issueLink', payload)
# HTTP 201 empty body = success
```
Verify: on KER-C, `issuelinks` will show `KER-A dupes <empty>` (inward direction). On KER-A, it shows `<empty> dupes KER-C` (outward).

### Agile board search returns 0 boards for KER

`GET /rest/agile/1.0/board?projectKeyOrId=KER` → `{"total": 0}`. This is expected — JPD projects don't appear on agile boards. Don't retry. Use Roadmap field instead.

## Known Jira Link Type IDs (verified 2026-06)

| ID | Name | Inward label | Outward label |
|---|---|---|---|
| 10000 | Blocks | is blocked by | blocks |
| 10001 | Cloners | is cloned by | clones |
| 10002 | Duplicate | is duplicated by | duplicates |
| 10003 | Relates | relates to | relates to |
| 10201 | Work item split | split from | split to |
| 10202 | Polaris work item link | is implemented by | implements |
| 10203 | Polaris datapoint work item link | added to idea | is idea for |
| 10204 | Polaris merge work item link | merged into | merged from |
| 10205 | Discovery - Connected | is connected to | connects to |

Use `GET /rest/api/3/issueLinkType` to refresh this table if a new type is needed.

## Credentials

```bash
source ~/.hermes/profiles/launchbot/.env
# Provides: JIRA_EMAIL, JIRA_API_TOKEN, JIRA_BASE_URL
```

## Output Contract

```
**KER-X → KER-Y merge complete**
- *KER-X:* `<summary>` → Cancelled ✅
- *KER-Y:* `<summary>`

**N IFIs moved (all HTTP 201 ✅):**
> IFI-NNN, IFI-NNN, ...

KER-Y now has **N total IFIs**.
🔗 Verify: https://staffany.atlassian.net/browse/KER-Y
```
