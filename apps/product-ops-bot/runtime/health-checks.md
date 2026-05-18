# Health Checks

Product Ops Bot needs deterministic runtime checks.

## Expected Checks

- Hermes gateway service for `productopsbot` is active.
- Secret redaction is enabled.
- Model route is `anthropic` + `claude-sonnet-4-6`.
- Slack is mention-required.
- Healthy checks print nothing and exit 0.

## Commands

```bash
npm run product-ops-bot:verify
apps/product-ops-bot/runtime/check-health.sh
apps/product-ops-bot/runtime/audit-live-profile.sh
```
