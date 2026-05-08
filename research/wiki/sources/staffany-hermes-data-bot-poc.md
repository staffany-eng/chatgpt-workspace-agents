# StaffAny Hermes Data Bot POC

## Summary

The `staffanydatabot` Hermes profile is a working StaffAny Slack data-bot deployment pattern. It combines a platform-specific Slack gateway, a local StaffAny skill/registry layer, read-only BigQuery MCP access, persistent memory, and deterministic cron health checks.

This note is current-state evidence, not a universal product decision. It should guide future ChatGPT workspace-agent design where the same requirements apply: team-facing data answers, strict source order, Slack UX, connector safety, and production reliability.

## What They Said

- The bot uses a dedicated Hermes profile for StaffAny Slack data-bot work, separating config, skills, scripts, logs, and memory from other Hermes usage.
- The StaffAny data-bot skill encodes product/source order, Slack plan-first gating, BigQuery safety rules, answer contracts, memory rules, and known metric caveats.
- Runtime health checks are necessary because a correct prompt does not guarantee live connector scopes, gateway restarts, or MCP availability.
- Slack status reactions require effective Slack bot scope `reactions:write`; manifest/code changes alone are insufficient until the Slack app is saved/reinstalled and the gateway is restarted.
- Slack file attachment hydration requires effective `files:read`; otherwise Slack private file URLs can return login/HTML responses instead of media.
- The StaffAny BigQuery MCP surface should remain read-only and limited to dataset listing, table listing, table info, and read-only SQL execution.
- A silent `no_agent` cron health check is preferred for operational checks because healthy runs produce no Slack message and consume no model tokens.
- The eval pack treats StaffAny-specific behaviours as regression-testable product behaviours: Slack plan-first, source order, confidence labels, sensitive-data refusal, organization names over IDs, and known metric caveats.

## Why It Matters

A team data bot fails in ways that normal chatbots do not: stale connector scopes, missing warehouse auth, ambiguous metric definitions, unsafe detail exposure, or accidental overconfidence. This POC shows that the operating model needs four layers:

1. **Instruction layer**: role, source order, confidence labels, safety boundaries.
2. **Skill/reference layer**: metric registry, product lookup registry, runbooks, eval pack.
3. **Connector/tool layer**: read-only MCP, bounded BigQuery usage, Slack gateway scopes.
4. **Operational layer**: secret redaction, health checks, cron, gateway restart verification.

## Current Reusable Pattern

For a StaffAny-like data bot:

- Use a dedicated runtime profile.
- Keep product/package lookups in local references and query the warehouse only for metrics.
- Require plan-first behaviour on first Slack mentions that need tools or app-backed work.
- Prefer one focused clarification over broad warehouse discovery when an organization or metric scope is ambiguous.
- Use exact confidence labels: `verified`, `needs-check`, `blocked`.
- Hide SQL and raw IDs by default; prefer organization names.
- Refuse secrets, private tokens, raw PII, and employee-level payroll/bank/NRIC details.
- Add a no-agent health check that verifies gateway active state, secret redaction config, read-only MCP connectivity, and Slack effective scopes.
- Keep a regression/eval pack for behaviours that should not drift after runtime or prompt changes.

## Open Follow-Ups

- Decide where the canonical StaffAny data-bot skill and eval pack should live long term: Hermes profile, internal repo, or generated deployment package.
- Convert the most common StaffAny metrics into owner-confirmed registry entries so more answers can move from `needs-check` to `verified`.
- Reduce private-channel `groups:read` log noise if least-privilege Slack setup intentionally avoids private-channel enumeration.
- Add an automated eval runner if we want behavioural checks beyond deterministic setup checks.

## Evidence Trace

- Dedicated profile and gateway: `research/raw/hermes-staffany-data-bot/current-hardening-state.md` observed `staffanydatabot` and `hermes-gateway-staffanydatabot.service`.
- Skill behaviours: local `staffany-data-bot/SKILL.md` and eval pack paths listed in the raw current-state note.
- Runtime health necessity: raw current-state note records gateway scopes, MCP test, secret-redaction config, and health-check script results.
- Slack scope requirements: gateway logs in the raw note show effective `reactions:write` and `files:read` scopes as runtime evidence.
- MCP read-only surface: raw current-state note records the four selected `staffany_bigquery` MCP tools.
- Silent cron pattern: raw current-state note records the no-agent weekday health-check cron and silent script result.
