# GCP VM Bot Topology

Last verified: 2026-05-13 SGT.

This file is the source-controlled map of live Hermes bot placement in GCP. Use it before answering "where is this bot deployed?", restarting a gateway, or deciding whether a new VM is needed.

## Current GCP Project

- Project: `staffany-warehouse`
- Region: `asia-southeast1`
- Zone: `asia-southeast1-a`
- Access path: IAP SSH is the supported operator path.
- Public SSH: blocked by firewall for Hermes bot VMs.

## Live VM Ownership

| VM | Machine | Internal IP | Running gateway service | Active profile | Slack surface | Purpose |
| --- | --- | --- | --- | --- | --- | --- |
| `hermes-data-bot-poc` | `e2-small` | `10.148.0.3` | `hermes-gateway-staffanydatabot.service` | `staffanydatabot` | `#da-ta-hermz-testing` (`C0AU19E6T0C`) | StaffAny Hermes Data Bot POC. |
| `hermes-data-bot-poc` | `e2-small` | `10.148.0.3` | `hermes-gateway-launchbot.service` | `launchbot` | `#launch-bot-testing` (`C0B32M34J3W`); read-only KER lookup in `#all-product-questions` (`C01RZ7SHC8K`) | LaunchBot Slack runtime. |
| `hermes-psm-ops-bot-poc` | `e2-small` | `10.148.0.4` | `hermes-gateway-psmopsbot.service` | `psmopsbot` | PSM ops bot Slack surface | PSM Ops Bot POC. |
| `nurtureany-sales-bot-prod` | `e2-standard-2` | `10.148.0.5` | `hermes-gateway-nurtureanysalesbot.service` | `nurtureanysalesbot` | NurtureAny sales bot Slack surface | Production NurtureAny Sales Bot. |

Important: a profile directory is not deployment proof. Treat a bot as deployed on a VM only when the matching `hermes-gateway-<profile>.service` is active or intentionally installed there. For example, `nurtureanysalesbot` may exist as a profile folder on `hermes-data-bot-poc`, but the live production gateway service is on `nurtureany-sales-bot-prod`.

## LaunchBot Runtime Facts

- VM: `hermes-data-bot-poc`
- Profile: `launchbot`
- Service: `hermes-gateway-launchbot.service`
- Service mode: user systemd service
- Expected state: `active` and `enabled`
- Slack bot user id: `U0ASVD79UT1`
- Slack bot id: `B0ATPPEGBCH`
- Slack app user: `codexlaunchbot`
- Test channel: `#launch-bot-testing` (`C0B32M34J3W`)
- Token source for read checks: deployed `launchbot` profile `.env` or approved secret store only.

LaunchBot currently shares the `hermes-data-bot-poc` VM with `staffanydatabot`. Do not create a separate LaunchBot VM unless there is a concrete isolation reason such as resource contention, distinct IAM boundary, or different availability requirement.

## Verify Placement

List the VM topology:

```bash
gcloud compute instances list \
  --project=staffany-warehouse \
  --format='table(name,zone,status,machineType.basename(),networkInterfaces[0].networkIP)' \
  | rg 'hermes|nurtureany|launch'
```

Check services on the shared Hermes/Data/LaunchBot VM:

```bash
gcloud compute ssh hermes-data-bot-poc \
  --project=staffany-warehouse \
  --zone=asia-southeast1-a \
  --tunnel-through-iap \
  --command 'systemctl --user list-units --type=service --all --no-pager | grep hermes-gateway'
```

Expected active services on `hermes-data-bot-poc`:

```text
hermes-gateway-launchbot.service
hermes-gateway-staffanydatabot.service
```

Check LaunchBot directly:

```bash
gcloud compute ssh hermes-data-bot-poc \
  --project=staffany-warehouse \
  --zone=asia-southeast1-a \
  --tunnel-through-iap \
  --command 'systemctl --user is-active hermes-gateway-launchbot.service && systemctl --user is-enabled hermes-gateway-launchbot.service'
```

Expected output:

```text
active
enabled
```

## Live Slack Smoke Contract

Use a real Slack UI mention for trigger-path smoke tests, then read the resulting thread back with the LaunchBot bot token. Do not use the Slack connector or Kai Yi's user token for bot-side inspection when the LaunchBot bot token exists.

Minimal smoke:

1. In `#launch-bot-testing`, send a timestamped human-authored mention to `@Launch Bot`.
2. Poll the thread with `SLACK_BOT_TOKEN` from the deployed `launchbot` profile or approved secret store.
3. Confirm the reply comes from user `U0ASVD79UT1` or bot id `B0ATPPEGBCH`.
4. If there is no reply, check `journalctl --user -u hermes-gateway-launchbot.service` on `hermes-data-bot-poc` before changing repo code.

Do not commit Slack tokens, `.env` values, raw Slack transcripts, or private channel exports.

## Restart Contract

Restart LaunchBot only on its current VM:

```bash
gcloud compute ssh hermes-data-bot-poc \
  --project=staffany-warehouse \
  --zone=asia-southeast1-a \
  --tunnel-through-iap \
  --command 'systemctl --user restart hermes-gateway-launchbot.service && systemctl --user status hermes-gateway-launchbot.service --no-pager'
```

After restart, perform the live Slack smoke above. A service restart without a Slack reply is not enough to call the runtime healthy.
