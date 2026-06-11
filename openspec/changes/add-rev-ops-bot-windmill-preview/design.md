# Design: RevOps Bot Windmill Approval Mode

## Runtime Primitive

Use a Hermes MCP server because the bot needs a narrow external-system boundary to Windmill. The MCP talks only to Windmill; Windmill remains the workflow executor and the only component that calls Kraken Billing Engine.

## Tool Surface

- `check_windmill_revops_config`: validates local profile configuration without printing secrets.
- `search_billing_main_deals`: calls Windmill script `f/rev_ops/search_billing_main_deals`.
- `preview_create_sub_deal_and_service_agreement`: calls Windmill script `f/rev_ops/create_sub_deal_and_service_agreement` with `dry_run=true` enforced by the MCP.
- `preview_preflight_updates`: calls Windmill script `f/rev_ops/apply_preflight_updates` with `dry_run=true`.
- `apply_approved_preflight_updates`: calls Windmill script `f/rev_ops/apply_preflight_updates` with `dry_run=false` after exact approval.
- `execute_approved_create_sub_deal_and_service_agreement`: calls Windmill script `f/rev_ops/create_sub_deal_and_service_agreement` with `dry_run=false` after exact approval.
- `preview_send_service_agreement`: calls Windmill script `f/rev_ops/send_service_agreement` with `dry_run=true`.
- `execute_approved_send_service_agreement`: calls Windmill script `f/rev_ops/send_service_agreement` with `dry_run=false` after exact approval.

Preview tools always send `dry_run=true`. Execution tools send `dry_run=false` only after the request includes approval metadata and exact confirmation text returned by the corresponding preview.

## Credential Boundary

The Hermes profile owns:

- `REVOPS_WINDMILL_BASE_URL`
- `REVOPS_WINDMILL_WORKSPACE_ID`
- `REVOPS_WINDMILL_TOKEN`

Those are runtime-only values in the live profile `.env` or Secret Manager. The repo stores only templates and docs.

## Windmill API

The MCP uses Windmill's script-by-path wait endpoint:

```text
POST /api/w/{workspace}/jobs/run_wait_result/p/{path}
```

This keeps Hermes synchronous for preview and approval-gated execution, while Windmill remains the only workflow executor and audit boundary.
