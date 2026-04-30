# BigQuery MCP Proxy

## Source Metadata

- Type: implementation architecture source
- Source class: ChatGPT custom MCP to BigQuery
- Source URL or path: `apps/bq-mcp-proxy/`
- Date ingested: 2026-04-30
- Context: service-account BigQuery access from ChatGPT
- Default weight: 5
- Privacy: private

## Context Caveat

Google's BigQuery remote MCP feature is preview and ChatGPT custom MCP behavior can change. Re-check official docs before production rollout.

## Evidence Used

- Raw record: [research/raw/chatgpt/bigquery-mcp-proxy.md](../../raw/chatgpt/bigquery-mcp-proxy.md)

## What They Said

- BigQuery MCP uses OAuth 2.0 with IAM and does not accept API keys.
- The BigQuery MCP endpoint is `bigquery.googleapis.com/mcp` over HTTP.
- BigQuery MCP requires the BigQuery OAuth scope and IAM roles for MCP tool calls, jobs, and data viewing.
- Cloud Run supports hosting streamable HTTP MCP servers and provides an HTTPS service URL with response streaming.
- OpenAI recommends OAuth for custom remote MCP server authentication in ChatGPT.
- Custom MCP servers can receive sensitive data and must be trusted and carefully reviewed.

## Evidence Trace

- Claim: BigQuery MCP uses OAuth 2.0 with IAM and does not accept API keys. Evidence: The raw record captures Google's authentication guidance. Source: `research/raw/chatgpt/bigquery-mcp-proxy.md:25`.
- Claim: The BigQuery MCP endpoint is `bigquery.googleapis.com/mcp` over HTTP. Evidence: The raw record lists the endpoint and transport. Source: `research/raw/chatgpt/bigquery-mcp-proxy.md:28`.
- Claim: BigQuery MCP requires the BigQuery OAuth scope and IAM roles for MCP tool calls, jobs, and data viewing. Evidence: The raw record lists roles and scope. Source: `research/raw/chatgpt/bigquery-mcp-proxy.md:26`.
- Claim: Cloud Run supports hosting streamable HTTP MCP servers and provides an HTTPS service URL with response streaming. Evidence: The raw record summarizes Cloud Run MCP hosting docs. Source: `research/raw/chatgpt/bigquery-mcp-proxy.md:30`.
- Claim: OpenAI recommends OAuth for custom remote MCP server authentication in ChatGPT. Evidence: The raw record summarizes OpenAI MCP auth guidance. Source: `research/raw/chatgpt/bigquery-mcp-proxy.md:32`.
- Claim: Custom MCP servers can receive sensitive data and must be trusted and carefully reviewed. Evidence: The raw record captures OpenAI's custom MCP risk warning. Source: `research/raw/chatgpt/bigquery-mcp-proxy.md:33`.

## Learning Summary

- ChatGPT should connect to a StaffAny proxy URL, not directly to Google's BigQuery MCP URL, when service-account execution is needed.
- The proxy should run as the service account and add a Google OAuth access token before forwarding upstream.
- The proxy needs its own caller authentication; OAuth is the production path, while a temporary unauthenticated or shared-secret test is only acceptable briefly.
- Read-only query controls, request logging, dataset/view allowlisting, and monitoring are required before production.

## Synthesis Gate

- Mode: autonomous_current_focus_synthesis
- Status: completed
- Focus source: `docs/product-compass.md`, `research/wiki/weights.md`, `research/wiki/syntheses/skills-vs-apps-vs-mcp.md`
- Evidence weight check: weight 5 for official Google/OpenAI behavior and local implementation.
- Decision: implement a Cloud Run proxy scaffold under `apps/bq-mcp-proxy/` and keep OAuth hardening as a production blocker.

## Possible Agent Builder Relevance

- Agent-synthesized: Custom MCPs are the right surface when ChatGPT needs controlled access to internal data through StaffAny-owned infrastructure.
- Agent-synthesized: App/tool identity and warehouse identity should be separated: ChatGPT authenticates to StaffAny, StaffAny authenticates to BigQuery.
- Do-not-promote: A no-auth Cloud Run URL is only for short testing and must not become the production pattern.

## Follow-Up Questions

- Which OAuth provider should protect the production proxy: Google OAuth, StaffAny SSO, or another StaffAny auth service?
- Which BigQuery datasets or views should the proxy allow for the first ChatGPT agent?
