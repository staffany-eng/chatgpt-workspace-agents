# Hermes Bot Deploy Access

Use this runbook to onboard a StaffAny Google user to deploy the cloud-hosted Hermes bots from this repo.

Source-code access is separate from VM deploy access. GitHub access lets someone read or push this repo, but the deploy wrappers still need GCP IAM to upload an archive, SSH through IAP, write VM SSH metadata, and act as the VM service account.

Runtime secrets are not part of this onboarding script. Do not grant Secret Manager access, copy `.env` files, or share Slack, Jira, Intercom, Customer 360, OAuth, or GitHub deploy-key material through this flow.

## Tool

Dry-run first:

```bash
npm run hermes-bot:onboard-access -- --email jason@staffany.com --bot psm-ops-bot
```

Apply after reviewing the planned grants:

```bash
npm run hermes-bot:onboard-access -- --email jason@staffany.com --bot all --apply
```

Supported bot names are:

- `hermes-data-bot`
- `nurtureany-sales-bot`
- `psm-ops-bot`
- `launchbot`
- `all`

Use `--json` for machine-readable output and `--verbose` to print every read-only check and applied `gcloud` command.

## Grants

The tool grants only the IAM required for GCP VM deploy/SSH access:

- Project `staffany-warehouse`: `roles/compute.viewer`
- Project `staffany-warehouse`: `roles/iap.tunnelResourceAccessor`
- Project `staffany-warehouse`: `roles/compute.osLogin`
- Target VM instance: `roles/compute.osAdminLogin`
- Target VM instance: `projects/staffany-warehouse/roles/hermesBotVmSshMetadataWriter`
- Target VM service account: `roles/iam.serviceAccountUser`

The custom role `hermesBotVmSshMetadataWriter` contains only `compute.instances.setMetadata`. If the role is missing, `--apply` creates it. If the role exists with any other permission set, the script blocks instead of widening access.

Do not replace this with broad roles such as `roles/compute.admin`, `roles/compute.instanceAdmin`, `roles/editor`, or `roles/owner`. Do not add Secret Manager roles in this onboarding path.

## Why These Grants Exist

The repo deploy wrappers use `gcloud compute scp` and `gcloud compute ssh --tunnel-through-iap`. When OS Login does not cover the complete key path, `gcloud` writes the operator SSH key into VM metadata; that needs `compute.instances.setMetadata`.

The deploy wrappers also run remote commands as the runtime owner and use the VM's attached service account. The operator therefore needs `roles/iam.serviceAccountUser` scoped to the VM service account, not project-wide editor/admin access.

## Current Bot Registry

| Bot | VM | Profile | VM service account |
| --- | --- | --- | --- |
| `hermes-data-bot` | `hermes-data-bot-poc` | `staffanydatabot` | `hermes-data-bot@staffany-warehouse.iam.gserviceaccount.com` |
| `nurtureany-sales-bot` | `nurtureany-sales-bot-prod` | `nurtureanysalesbot` | `hermes-data-bot@staffany-warehouse.iam.gserviceaccount.com` |
| `psm-ops-bot` | `hermes-psm-ops-bot-poc` | `psmopsbot` | `hermes-psm-ops-bot@staffany-warehouse.iam.gserviceaccount.com` |
| `launchbot` | `hermes-data-bot-poc` | `launchbot` | `hermes-data-bot@staffany-warehouse.iam.gserviceaccount.com` |

All current VMs are in project `staffany-warehouse`, zone `asia-southeast1-a`.

## Verification

After `--apply`, the tool runs read-only IAM checks with `gcloud policy-troubleshoot iam` for:

- `compute.instances.setMetadata` on each selected VM.
- `iam.serviceAccounts.actAs` on each selected VM service account.

For full repo verification:

```bash
npm run hermes-bot:onboard-access:test
npm run hermes-bot:onboard-access:verify
```
