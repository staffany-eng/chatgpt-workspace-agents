# RevOps Bot

RevOps Bot is a Hermes Slack app packet for StaffAny RevOps and BDOps billing workflows.

## MVP Scope

Preflight, preview, and execute explicitly approved create-sub-deal and service-agreement requests from Slack by calling Windmill.

```text
Slack -> Hermes revopsbot -> Windmill preflight -> Windmill preview -> exact Slack approval -> Windmill guarded execution
```

Hermes does not call HubSpot, SignNow, Stripe, Xendit, Kraken, or Billing Engine directly. Business writes are exposed only through Windmill guarded tools that require preview output, approval metadata, and exact confirmation text.

Structured create-sub-deal intake is handled inside the Hermes Slack gateway:

```text
/revops-create-sub-deal -> Hermes Slack modal -> structured request -> Hermes revopsbot -> Windmill preflight
```

The modal handler only collects structured input and hands it back to Hermes. It does not call HubSpot, Windmill, Billing Engine, SignNow, Stripe, or Xendit directly.

## Runtime Systems

- Slack: conversation, preview, and exact approval surface.
- Windmill: workflow validator and executor.
- Kraken Billing Engine: business source of truth behind Windmill.

## Required Runtime Secrets

The live Hermes profile must provide:

- `SLACK_APP_TOKEN`
- `SLACK_BOT_TOKEN`
- `REVOPS_CREATE_SUB_DEAL_MODAL_ENABLED`
- `REVOPS_BOT_USER_ID`
- `REVOPS_CREATE_SUB_DEAL_COMMAND`
- `REVOPS_CREATE_SUB_DEAL_ALLOWED_CHANNEL_IDS` optional
- `REVOPS_WINDMILL_BASE_URL`
- `REVOPS_WINDMILL_WORKSPACE_ID`
- `REVOPS_WINDMILL_TOKEN`

Do not commit live values.

## Verification

```bash
npm run rev-ops-bot:verify
```

## Deploy Flow

Routine deploys use the exact-ref wrapper from the repo root:

```bash
npm run rev-ops-bot:deploy
npm run rev-ops-bot:deploy -- --apply --ref origin/main
```

Without `--apply`, the wrapper verifies locally and prints the target SHA. With
`--apply`, it uploads an exact git archive to `hermes-psm-ops-bot-poc`, syncs
RevOps source into `/home/leekaiyi/chatgpt-workspace-agents`, syncs the
`revopsbot` profile-owned source/runtime files, restarts only
`hermes-gateway-revopsbot.service`, then runs audit and health checks.

The deploy script must not use `/home/leekaiyi/agent-builder`; that path remains
reserved for Customer 360 / PSM Ops on the shared VM.

If `gcloud compute ssh` cannot update VM metadata from the operator machine,
use the raw SSH-over-IAP transport with an already-authorized key:

```bash
npm run rev-ops-bot:deploy -- --apply --ref origin/main --transport iap-ssh --ssh-user eric --ssh-key-file ~/.ssh/id_rsa
```
