# IFI Direct REST Creation — Workaround for MCP bd_note Extraction Failures

## Problem

`preview_ifi_feature_request_from_bd_note` / `create_or_update_ifi_feature_request_from_bd_note`
auto-extract `featureGap` from the `bd_note` text. When the note is a long paragraph, the extractor
grabs a mid-sentence fragment and uses it as the IFI summary title, producing garbage like:

  "this and they are having a hard time tracking leave accurately - TIM HORTONS MY"

The MCP also fails with HTTP 400 on `labels` (known) and sometimes on `customfield_10881`.

## When to bypass the MCP

- MCP preview shows a `featureGap` that is clearly a sentence fragment or mid-paragraph snippet.
- You want to control the IFI summary exactly (structured BD notes, company/module/JTBD context).
- MCP throws HTTP 400 on `labels` field.

## Direct REST Recipe (Python, verified 2026-06-02)

```python
import json, urllib.request, base64

# Load from ~/.hermes/profiles/launchbot/.env: JIRA_EMAIL, JIRA_API_TOKEN, JIRA_BASE_URL
auth = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()
headers = {
    "Authorization": f"Basic {auth}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# Step 1: Create IFI
payload = json.dumps({
    "fields": {
        "project": {"key": "IFI"},                         # IFI project key
        "issuetype": {"id": "10151"},                      # "Submit a request or incident"
        "summary": "<clean summary> - <COMPANY NAME>",     # craft this manually — do NOT let MCP generate it from long bd_note
        "description": {
            "type": "doc", "version": 1,
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Customer context"}]},
                {"type": "bulletList", "content": [
                    {"type": "listItem", "content": [{"type": "paragraph", "content": [
                        {"type": "text", "text": "HubSpot Company ID: <ID>"}]}]},
                    {"type": "listItem", "content": [{"type": "paragraph", "content": [
                        {"type": "text", "text": "HubSpot Company URL: https://app.hubspot.com/contacts/4137076/company/<ID>"}]}]},
                    {"type": "listItem", "content": [{"type": "paragraph", "content": [
                        {"type": "text", "text": "Requester: <name>"}]}]},
                    {"type": "listItem", "content": [{"type": "paragraph", "content": [
                        {"type": "text", "text": "Source: <meeting/thread name, date>"}]}]},
                ]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Product request"}]},
                {"type": "bulletList", "content": [
                    # Feature gap, requirements, APQ classification, linked KER
                ]},
            ]
        },
        "customfield_10881": "<HubSpot Company ID as string>",
        # OMIT "labels" — IFI screen rejects it with HTTP 400
    }
}).encode()

url = f"{JIRA_BASE_URL}/rest/api/3/issue"
req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
with urllib.request.urlopen(req) as resp:
    result = json.loads(resp.read())
    ifi_key = result["key"]   # e.g. "IFI-3869"

# Step 2: Link IFI → KER (Relates)
link_payload = json.dumps({
    "type": {"name": "Relates"},
    "inwardIssue": {"key": ifi_key},
    "outwardIssue": {"key": "KER-XXXX"}
}).encode()
link_req = urllib.request.Request(
    f"{JIRA_BASE_URL}/rest/api/3/issueLink",
    data=link_payload, headers=headers, method="POST"
)
with urllib.request.urlopen(link_req) as resp:
    pass  # 201 empty body = success
```

## Key IDs

| Field | Value |
|-------|-------|
| IFI project key | `IFI` |
| IFI project ID | `10116` |
| Issue type: Submit a request or incident | `10151` |
| Issue type: Task | `10002` |
| HubSpot Company ID custom field | `customfield_10881` |
| Launchbot Jira author | `JIRA_EMAIL` + `JIRA_API_TOKEN` from `.env` |

## Pitfalls

- **Do NOT include `labels`** — IFI screen rejects with HTTP 400.
- **`customfield_10881` may also 400** — if so, omit the field and embed HubSpot ID only in description.
- `issuetype` must use `{"id": "..."}` — name lookup (`{"name": "..."}`) fails on IFI screen config.
- `project` accepts both `{"key": "IFI"}` and `{"id": "10116"}`.
- issueLink POST returns 201 with empty body on success; don't expect a JSON response body.
- Write the Python to a /tmp file and run with `python3 /tmp/script.py` — don't use heredoc for long scripts.

## Example: Tim Hortons MY (2026-06-02)

- HubSpot Company: TIM HORTONS MY, ID `15896813576`, domain `tims-mgca.com`
- IFI: `IFI-3869` — "Custom leave entitlement period (financial year Apr–Mar) - TIM HORTONS MY"
- Linked KER: `KER-811` — "Leave Change entitlement period from annual to arbitrary period (financial year)" (Backlog)
- Gap: Leave runs Apr 1–Mar 31 (not calendar year); Brio couldn't support; Jul 1 go-live blocker.
- KER found via `mcp_launchbot_ker_find_ker_ticket_from_slack_thread` with channel_id + thread_ts.
