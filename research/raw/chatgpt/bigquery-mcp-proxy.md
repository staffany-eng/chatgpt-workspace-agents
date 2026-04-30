# BigQuery MCP Proxy Raw Record

## Source Metadata

- Type: architecture and implementation source
- Source class: ChatGPT custom MCP to BigQuery
- Date checked: 2026-04-30
- Privacy: implementation notes, no secrets copied
- Primary sources:
  - `https://docs.cloud.google.com/bigquery/docs/use-bigquery-mcp`
  - `https://docs.cloud.google.com/bigquery/docs/reference/mcp/get_dataset_info`
  - `https://docs.cloud.google.com/run/docs/host-mcp-servers`
  - `https://developers.openai.com/api/docs/mcp`

## Raw Content Policy

This record stores source metadata and short evidence extracts. It does not copy full official docs pages and does not store service-account keys or tokens.

## Source Inventory

- Google BigQuery remote MCP docs for endpoint, auth, roles, scopes, and limitations.
- Google BigQuery MCP tool reference for the `https://bigquery.googleapis.com/mcp` HTTP endpoint.
- Google Cloud Run MCP hosting docs for streamable HTTP hosting and Cloud Run authentication behavior.
- OpenAI MCP docs for ChatGPT remote MCP setup and OAuth/security guidance.
- Local implementation: `apps/bq-mcp-proxy/`.

## Evidence Extracts

- Google BigQuery remote MCP docs say BigQuery MCP uses OAuth 2.0 with IAM and does not accept API keys.
- BigQuery MCP docs list required roles for tool use: `roles/mcp.toolUser`, `roles/bigquery.jobUser`, and `roles/bigquery.dataViewer`.
- BigQuery MCP docs list the scope `https://www.googleapis.com/auth/bigquery`.
- BigQuery MCP docs say the remote endpoint is `bigquery.googleapis.com/mcp`, with HTTP transport.
- The BigQuery MCP reference shows curl calls to `https://bigquery.googleapis.com/mcp` using JSON-RPC MCP tool calls.
- Cloud Run docs say streamable HTTP MCP servers can be hosted on Cloud Run and deployed from Node.js or Python source.
- Cloud Run docs say Cloud Run gives the service an HTTPS URL and supports HTTP response streaming.
- OpenAI MCP docs say ChatGPT can import a remote MCP server by server URL and recommends OAuth for authentication.
- OpenAI MCP docs warn that custom MCP servers can receive sensitive data and should be trusted, reviewed, and designed carefully.

## First-Pass Learning

The safe shape is a StaffAny-controlled Cloud Run proxy. ChatGPT connects to the proxy, the proxy authenticates the caller, and the proxy calls Google's BigQuery MCP endpoint using the Cloud Run service account identity.

