# RevOps Windmill MCP

This MCP exposes Windmill-backed read, preview, and approval-gated execution tools.

## Tools

- `check_windmill_revops_config`
- `search_billing_main_deals`
- `preflight_create_sub_deal_request`
- `preview_create_sub_deal_and_service_agreement`
- `preview_preflight_updates`
- `apply_approved_preflight_updates`
- `execute_approved_create_sub_deal_and_service_agreement`
- `preview_send_service_agreement`
- `execute_approved_send_service_agreement`

The preflight tool is read-only and checks readiness before preview.
Preview tools force `dry_run=true` before calling Windmill. Execution tools set
`dry_run=false` only after the bot has collected Windmill's required exact
confirmation text and approval metadata.
