# RevOps Bot Windmill Runtime

RevOps Bot uses Windmill as the workflow boundary.

## Runtime Env

- `REVOPS_WINDMILL_BASE_URL`
- `REVOPS_WINDMILL_WORKSPACE_ID`
- `REVOPS_WINDMILL_TOKEN`

## Scripts

- `f/rev_ops/search_billing_main_deals`
- `f/rev_ops/preflight_create_sub_deal_request`
- `f/rev_ops/apply_preflight_updates`
- `f/rev_ops/create_sub_deal_and_service_agreement`
- `f/rev_ops/send_service_agreement`

## Safety Contract

The Hermes MCP uses preflight as a readiness gate before previewing. Preview
tools force `dry_run=true`. Execution tools are exposed only for explicitly
approved Windmill flows and must include approval metadata plus the exact
confirmation text returned by the preview.

## API Endpoint

The MCP runs scripts by path through:

```text
POST /api/w/{workspace}/jobs/run_wait_result/p/{path}
```

The request body is the script argument object.
