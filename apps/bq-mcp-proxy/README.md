# BigQuery MCP Proxy

Tiny Cloud Run proxy for using the Google BigQuery remote MCP server from ChatGPT while executing BigQuery calls as a service account.

## Architecture

```text
ChatGPT Custom MCP
  -> Cloud Run proxy /mcp
  -> https://bigquery.googleapis.com/mcp
  -> BigQuery
```

The Cloud Run service should run as:

```text
data-bot-bq-reader@gws-cli-260305163132.iam.gserviceaccount.com
```

## Required IAM

Grant the service account these roles on the BigQuery project:

```text
roles/bigquery.dataViewer
roles/bigquery.jobUser
roles/mcp.toolUser
```

Enable the remote BigQuery MCP server:

```bash
gcloud beta services mcp enable bigquery.googleapis.com --project=gws-cli
```

## Deploy

For a temporary ChatGPT test without OAuth, use a shared bearer token:

```bash
gcloud run deploy bq-mcp-proxy \
  --region=asia-southeast1 \
  --source=apps/bq-mcp-proxy \
  --service-account=data-bot-bq-reader@gws-cli-260305163132.iam.gserviceaccount.com \
  --set-env-vars=PROXY_SHARED_SECRET="$(openssl rand -hex 32)",ENFORCE_READ_ONLY=true
```

Then allow unauthenticated HTTP only if ChatGPT cannot provide Cloud Run IAM auth:

```bash
gcloud run services add-iam-policy-binding bq-mcp-proxy \
  --region=asia-southeast1 \
  --member=allUsers \
  --role=roles/run.invoker
```

Use the Cloud Run URL with `/mcp` in ChatGPT.

## ChatGPT Setup

Use:

```text
https://<cloud-run-service-url>/mcp
```

Do not use:

```text
https://bigquery.googleapis.com/mcp
```

For this temporary bearer-token version, configure ChatGPT as unauthenticated only if the shared-secret path is not usable in the product UI. Long term, replace this with proper OAuth on the proxy so ChatGPT authenticates as Kai Yi to the proxy, while the proxy calls BigQuery as the service account.

## Guardrails

The proxy defaults to:

- requiring `PROXY_SHARED_SECRET`, unless `ALLOW_UNAUTHENTICATED=true`
- forwarding upstream as the Cloud Run service account
- using `https://www.googleapis.com/auth/bigquery`
- preserving upstream streaming responses
- rejecting obvious non-read-only BigQuery MCP calls and mutation/export SQL

This is not a complete data access policy. Before production, add OAuth, user allowlisting, dataset/view allowlisting, request logging, and alerting.

