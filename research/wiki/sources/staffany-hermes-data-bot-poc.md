# StaffAny Hermes Data Bot POC

## Source Metadata

- Type: deployed runtime current-state note
- Source class: StaffAny Hermes deployment evidence
- Source path: `research/raw/hermes-staffany-data-bot/current-hardening-state.md`
- Date ingested: 2026-05-08
- Context: working StaffAny Slack data-bot deployment pattern
- Default weight: 4 for the current StaffAny Hermes deployment; 3 for general workspace-agent design claims
- Privacy: private internal operational note; no `.env`, token, raw Slack transcript, raw query row, or employee-level data copied

## Context Caveat

This note describes the deployed `staffanydatabot` Hermes profile, not a universal product rule. Use it as high-confidence current-state evidence for StaffAny Hermes Data Bot and as weaker implementation guidance for future agent apps.

## Evidence Used

- Raw record: [Hermes StaffAny Data Bot Current Hardening State](../../raw/hermes-staffany-data-bot/current-hardening-state.md)

## What They Said

- The bot uses a dedicated Hermes profile for StaffAny Slack data-bot work, separating config, skills, scripts, logs, and memory from other Hermes usage.
- The StaffAny data-bot skill encodes product/source order, Slack plan-first gating, BigQuery safety rules, answer contracts, memory rules, and known metric caveats.
- Runtime health checks are necessary because a correct prompt does not guarantee live connector scopes, gateway restarts, or MCP availability.
- Slack status reactions require effective Slack bot scope `reactions:write`; manifest/code changes alone are insufficient until the Slack app is saved/reinstalled and the gateway is restarted.
- Slack file attachment hydration requires effective `files:read`; otherwise Slack private file URLs can return login/HTML responses instead of media.
- The StaffAny BigQuery MCP surface should remain read-only and limited to dataset listing, table listing, table info, and read-only SQL execution.
- A silent `no_agent` cron health check is preferred for operational checks because healthy runs produce no Slack message and consume no model tokens.
- The eval pack treats StaffAny-specific behaviours as regression-testable product behaviours: Slack plan-first, source order, confidence labels, sensitive-data refusal, organization names over IDs, and known metric caveats.
- Model routing is an operational invariant: `all@staffany` against the OpenAI endpoint caused `model_not_found`; the cleaned-up profile uses `custom` + `gpt-5.5` + `https://api.openai.com/v1`.
- A lightweight on-demand eval script can catch behaviour regressions without warehouse queries; it should not be run as the silent daily cron because it invokes Hermes/model calls.

## Evidence Trace

- Claim: The bot uses a dedicated Hermes profile. Evidence: source inventory lists the profile root plus config, logs, skill, eval pack, and script paths. Source: `research/raw/hermes-staffany-data-bot/current-hardening-state.md:20`.
- Claim: The StaffAny data-bot skill owns source order, Slack gating, BigQuery safety, and caveats. Evidence: source inventory lists the skill and eval pack paths. Source: `research/raw/hermes-staffany-data-bot/current-hardening-state.md:23`.
- Claim: Runtime health checks are necessary. Evidence: design observations say connector scopes, gateway restarts, and MCP availability can drift independently of prompt state. Source: `research/raw/hermes-staffany-data-bot/current-hardening-state.md:43`.
- Claim: Slack status reactions need `reactions:write`. Evidence: evidence extracts record recent gateway logs with `reactions:write`. Source: `research/raw/hermes-staffany-data-bot/current-hardening-state.md:32`.
- Claim: Slack file hydration needs `files:read`. Evidence: evidence extracts record recent gateway logs with `files:read`. Source: `research/raw/hermes-staffany-data-bot/current-hardening-state.md:32`.
- Claim: BigQuery MCP should expose only four read-only tools. Evidence: evidence extracts list `staffany_bigquery` and the four selected tools. Source: `research/raw/hermes-staffany-data-bot/current-hardening-state.md:33`.
- Claim: Silent `no_agent` cron is preferred for health checks. Evidence: evidence extracts record a silent healthy script and weekday `no_agent` cron. Source: `research/raw/hermes-staffany-data-bot/current-hardening-state.md:36`.
- Claim: The eval pack makes StaffAny behaviours regression-testable. Evidence: evidence extracts list covered behaviours such as plan-first, source order, confidence labels, refusal, and org-name preference. Source: `research/raw/hermes-staffany-data-bot/current-hardening-state.md:40`.
- Claim: Model route is an operational invariant. Evidence: evidence extracts record the cleaned-up `custom` + `gpt-5.5` + OpenAI base URL route and the prior `all@staffany` `model_not_found` failure. Source: `research/raw/hermes-staffany-data-bot/current-hardening-state.md:32`.
- Claim: Lightweight eval checks can catch non-warehouse behaviour regressions. Evidence: evidence extracts record `staffany_data_bot_eval_check.py` passing without querying the warehouse. Source: `research/raw/hermes-staffany-data-bot/current-hardening-state.md:42`.

## Learning Summary

- StaffAny Hermes Data Bot should be organized as an app packet plus a live runtime profile, with runtime drift promoted only after review.
- Operational health checks belong beside prompts and skills because Slack scopes, MCP auth, gateway state, and secret redaction can fail independently.
- Slack UX behaviours such as plan-first gating, approval nudges, and bounded follow-up corrections are product behaviours and need regression coverage.
- The BigQuery MCP contract should stay narrow, read-only, and explicitly allowlisted.
- Model routing belongs in the health/config verification surface; bad aliases can leave the bot working only because of fallback, hiding latency and reliability problems.
- Keep silent operational health checks separate from behavioural evals: health checks should use no-agent/no-token scripts, while evals can invoke Hermes/model calls on demand.

## Synthesis Gate

- Mode: autonomous_current_focus_synthesis
- Status: completed
- Focus source: `docs/product-compass.md`, `research/wiki/weights.md`, `research/wiki/syntheses/workspace-agent-abstraction-boundaries.md`
- Evidence weight check: weight 4 for StaffAny Hermes current state; weight 3 when generalized outside this deployment.
- Decision: use as primary current-state evidence for the app-first Hermes Data Bot packet and as supporting evidence for future agent-app operating patterns.

## Possible Agent Builder Relevance

- Agent-synthesized: Create `apps/hermes-data-bot/` as the canonical durable source packet for `staffanydatabot`.
- Agent-synthesized: Add app-level verification for manifest paths, secret-pattern checks, and MCP allowlist expectations.
- Agent-synthesized: Treat health checks and regression cases as first-class app artifacts, not deployment afterthoughts.
- Do-not-promote: Do not assume every future agent app needs Slack scopes, BigQuery, or GCE; these are StaffAny Hermes Data Bot specifics.

## Follow-Up Questions

- Which live `staffanydatabot` runtime learnings should be promoted into `apps/hermes-data-bot/` next?
- Should Customer 360 become a read-only customer-wiki source for Hermes Data Bot?
- Should the no-agent health check script be copied into the repo packet or kept only as a runtime artifact for now?
