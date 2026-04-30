# Data Bot BigQuery MCP Setup

This is the restore note for the Data Bot BigQuery connector. It records where the service, endpoint, and secret live without storing the bearer token value.

## Current State

- Status: connected in ChatGPT Agent Builder on 2026-04-30.
- ChatGPT connector/app name: `StaffAny BigQuery Auth`.
- Use for Data Bot: add `StaffAny BigQuery Auth` from the agent builder app picker.
- Stale duplicate app names to ignore or delete if present: `BigQuery`, `StaffAny BigQuery`, `BigQuery-Service-Account`, `BigQuery-Service-Account-Auth`.

## ChatGPT Connector Settings

- App type: Custom MCP.
- Connector URL: `https://bq-mcp-proxy-1093387803298.asia-southeast1.run.app/mcp`.
- Alternate Cloud Run URL for the same service: `https://bq-mcp-proxy-qv4r5xkisq-as.a.run.app/mcp`.
- Auth type: `Access token / API key`.
- Scheme: `Bearer`.
- Token value: use the Secret Manager value from `bq-mcp-proxy-shared-secret`. Paste only the token value. Do not include `Bearer`.

Expected tools after connection:

- `list_dataset_ids`
- `list_table_ids`
- `get_table_info`
- `execute_sql_readonly`

## Cloud Run Service

- GCP project: `staffany-warehouse`.
- Cloud Run service: `bq-mcp-proxy`.
- Region: `asia-southeast1`.
- Service URL from `gcloud run services describe`: `https://bq-mcp-proxy-qv4r5xkisq-as.a.run.app`.
- Observed working ChatGPT request URL: `https://bq-mcp-proxy-1093387803298.asia-southeast1.run.app`.

Important environment variables:

- `ALLOW_UNAUTHENTICATED=false`
- `ENFORCE_READ_ONLY=true`
- `TARGET_SERVICE_ACCOUNT=data-bot-bq-reader@gws-cli-260305163132.iam.gserviceaccount.com`
- `PROXY_SHARED_SECRET` exposed from Secret Manager

The Cloud Run runtime service account may be the project compute service account. The proxy then uses `TARGET_SERVICE_ACCOUNT` to impersonate the BigQuery reader service account.

## Secret Location

- GCP project: `staffany-warehouse`.
- Product area: Security > Secret Manager.
- Secret name: `bq-mcp-proxy-shared-secret`.
- Version to use: `latest`.
- Console path: `Google Cloud Console -> staffany-warehouse -> Security -> Secret Manager -> bq-mcp-proxy-shared-secret -> Versions -> latest -> View secret value`.

Do not commit, paste into agent instructions, upload as a file, or save in memory:

- The secret value.
- OAuth tokens.
- Connector credentials.
- Raw request headers.

## Recreate Steps

1. Open ChatGPT Settings > Connectors.
2. Create a Custom MCP app.
3. Name it `StaffAny BigQuery Auth`.
4. Set connector URL to `https://bq-mcp-proxy-1093387803298.asia-southeast1.run.app/mcp`.
5. Set auth to `Access token / API key`.
6. Set scheme to `Bearer`.
7. Paste only the Secret Manager token value.
8. Create the connector and verify the four tools appear.
9. Open Data Bot in Agent Builder.
10. Add app `StaffAny BigQuery Auth`.
11. Ignore stale duplicate BigQuery app entries.

If the Data Bot app picker no-ops after successful connector creation:

- Refresh connector metadata from ChatGPT Settings > Connectors.
- Hard-refresh ChatGPT.
- Reopen the agent draft.
- Add only `StaffAny BigQuery Auth`.

## Verification Commands

These commands verify config without printing the secret.

```bash
gcloud run services describe bq-mcp-proxy \
  --region asia-southeast1 \
  --project staffany-warehouse \
  --format='yaml(status.url,spec.template.spec.containers[0].env[].name)'
```

```bash
TOKEN=$(gcloud secrets versions access latest \
  --secret=bq-mcp-proxy-shared-secret \
  --project=staffany-warehouse)

curl -sS -X POST \
  https://bq-mcp-proxy-1093387803298.asia-southeast1.run.app/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  | jq -r '.result.tools | map(.name) | join(",")'
```

Expected output:

```text
list_dataset_ids,list_table_ids,get_table_info,execute_sql_readonly
```

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="bq-mcp-proxy"' \
  --project=staffany-warehouse \
  --limit=20 \
  --freshness=30m \
  --format='table(timestamp,httpRequest.requestMethod,httpRequest.status,httpRequest.requestUrl)'
```
