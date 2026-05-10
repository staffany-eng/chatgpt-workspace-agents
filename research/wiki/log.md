# Research Log

Append-only record of research activity.

## [2026-04-30] setup | Research corpus scaffold

Created the Agent Builder research wiki structure, documentation guide, evidence weights, source-note schema, audit tool, and initial source notes for Midas, OpenClaw docs, Hermes, ChatGPT workspace-agent docs, and `openclaw-kaiyi`.

## [2026-04-30] ingest | Midas Karpathy research process

Ingested the Midas research process as the operating model for this repo: raw/wiki split, source-note schema, evidence traces, weights, syntheses, decisions, and audit-until-clean workflow.

## [2026-04-30] ingest | OpenClaw official docs

Ingested official OpenClaw documentation as the primary source for OpenClaw design intent: workspace, memory, skills, gateway, automation, security, agents, sessions, and routing.

## [2026-04-30] ingest | Hermes Agent docs and repo patterns

Ingested Hermes Agent as a secondary architecture source for skills, memory, context files, plugin surfaces, gateway, cron/webhooks, delegation, and OpenClaw migration.

## [2026-04-30] ingest | Hermes Agent Docs And Patterns

Alias entry for the maintained source note title.

## [2026-04-30] ingest | ChatGPT workspace-agent official docs

Ingested official ChatGPT/OpenAI docs for workspace agents, ChatGPT skills, app/tool configuration, schedules, Slack, files/memory, write approvals, version history, analytics, Apps SDK state management, and security/privacy.

## [2026-04-30] ingest | ChatGPT Workspace Agent Official Docs

Alias entry for the maintained source note title.

## [2026-04-30] ingest | openclaw-kaiyi current implementation

Ingested `openclaw-kaiyi` as secondary local implementation evidence and created the first current-state audit synthesis.

## [2026-04-30] ingest | OpenClaw Kaiyi Current Implementation

Alias entry for the maintained source note title.

## [2026-04-30] ingest | BigQuery MCP Proxy

Ingested the ChatGPT-to-BigQuery service-account proxy architecture using official Google BigQuery MCP, Cloud Run MCP hosting, and OpenAI remote MCP guidance. Added a local Cloud Run proxy scaffold under `apps/bq-mcp-proxy/`.

## [2026-05-08] ingest | StaffAny Hermes Data Bot POC

Captured the current `staffanydatabot` Hermes profile hardening state: Slack effective scopes, secret-redaction config, read-only BigQuery MCP surface, silent no-agent health check, and StaffAny data-bot eval pack. No secrets, raw Slack transcripts, raw query rows, or employee-level data were copied.

## [2026-05-10] ingest | Hermes Agent live docs refresh

Refreshed the Hermes source note from `https://hermes-agent.nousresearch.com/docs/`, `llms.txt`, and `llms-full.txt`. Captured retrieval metadata, hashes, 98 curated index links, 147 source pages, and short extracts only; updated related syntheses and the Hermes app-packet decision without copying the full docs body.

## [2026-05-10] decision | NurtureAny durable HubSpot fields

Promoted the NurtureAny field decision after checking HubSpot company property metadata and Slack workflow evidence: use `contract_end_date` for renewal timing/T-90 windows and `current_tools` for current-tools context. Kept `current_tool_renewal_date` as secondary context only. No raw Slack transcripts or HubSpot rows were copied.

## [2026-05-10] ingest | NurtureAny Leadership Tactical Pause

Ingested the Leadership Tactical Pause Drive folder as private NurtureAny operating evidence. Recorded 9 files, preserved a raw inventory, and extracted sales-rhythm guidance for 150-account ownership, 120/150 coverage, double tap, 30 WhatsApp rhythm, 40 connected calls, QO/QO Met quality, warm activity, event discipline, and Friday correction.

## [2026-05-10] ingest | NurtureAny Sales Training Materials

Ingested the Sales Training Drive folder as private NurtureAny training evidence. Recorded 41 files plus one empty folder, extracted current instructor/rubric guidance for CCC, CBANT, I-C-BANT, pre-demo nurturing, value-driven demos, post-demo follow-up, onboarding, and market-specific training context. The inventoried Google Form remains blocked by Drive 403 unless an export is found.

## [2026-05-10] synthesis | NurtureAny Sales Best Practices

Synthesized Tactical Pause and Sales Training sources into a NurtureAny sales best-practices operating reference. The promoted app reference keeps HubSpot as live source of truth and treats old, copy, archived, outdated, or trainee materials as lower-authority conflict context.

## [2026-05-10] ingest | NurtureAny Sales Onboarding Master Template

Ingested the sales onboarding master template and its linked Drive files. Parsed 13 sheet tabs, 47 first-level Drive files, 25 folder-child links, and 18 second-order Drive links. Copied only safe training/rubric excerpts; secret forms, response sheets, raw pricing rows, and account-list style sheets were inventoried but not copied as raw operating guidance.

## [2026-05-10] ingest | StaffAny Rev Team Planning And Metrics

Ingested the 2026 Rev Team planning Sheet, 2025Q3 sales onboarding Slides, and Manticore/BigQuery metric evidence. Promoted NurtureAny guidance to treat QO as `fct_sales_points.qo_set`, keep planning targets separate from warehouse actuals, and disambiguate `new ARR` before querying.

## [2026-05-11] ingest | StaffAny Public Customer Case Studies

Ingested 26 approved public StaffAny customer case studies from StaffAny Singapore and Malaysia public pages. Added a structured NurtureAny case-study catalog for pre-demo name-drop matching and kept Slack-only/WIP case-study mentions out of approved source context until a published page or approved internal asset exists.
