---
name: help-article-screenshot-troubleshooter
description: Troubleshoot Launchbot help article screenshot capture on StaffAny staging by checking Playwright, creating a runtime-only authenticated storage state from approved staging credentials, running the screenshot plan, and returning safe blocker diagnostics without blocking the article workflow.
---

# Help Article Screenshot Troubleshooter

Use this skill when Launchbot screenshot capture is blocked, flaky, missing Playwright, missing authenticated staging access, timing out on StaffAny staging, or needs a repeatable test with approved staging credentials.

This is a troubleshooting lane for the optional screenshot asset workflow. It must not block help article drafting, Google Docs review, Slack approval, or Intercom draft/staging for otherwise valid article text. If troubleshooting fails, keep screenshot placeholders and return the exact blocker.

## Safety Contract

- Use only approved StaffAny staging or DEV demo/test organisations.
- Credentials must come from Secret Manager, the live Hermes profile `.env`, or an approved secure runtime environment.
- Never ask users to paste passwords, OTPs, cookies, localStorage, storage-state JSON, browser profile archives, or session tokens into Slack.
- Never save Playwright storage-state in this repo. Use `/tmp`, `.cache/launchbot/`, or `~/.hermes/profiles/launchbot/runtime/`.
- Never print credential values. Command output may list env names and artifact paths only.
- Do not insert screenshots unless redaction is verified.

## Troubleshooting Order

1. Confirm Playwright can load:

```bash
node -e 'import("playwright").then(() => console.log("playwright:ok")).catch((error) => { console.error(error.message); process.exit(1); })'
```

If Playwright is missing on the Hermes VM, install the runtime/browser through the approved VM setup path, then rerun the check. Prefer the real Playwright runner over the Chrome DevTools fallback for staging troubleshooting.

2. Confirm staging credentials are available without printing values:

```bash
node scripts/launchbot-with-secrets.mjs --check --only staging
```

Expected env names:

- `LAUNCHBOT_STAGING_URL`
- `LAUNCHBOT_STAGING_EMAIL`
- `LAUNCHBOT_STAGING_PASSWORD`

If the staging secret group is not configured yet, use equivalent env vars from the live Launchbot profile only. Do not copy them into the worktree.

3. Create a runtime-only Playwright storage state:

```bash
node scripts/launchbot-with-secrets.mjs --only staging -- \
  node apps/launchbot/runtime/help-article-staging-auth-state.mjs \
    --source-url "$LAUNCHBOT_STAGING_URL" \
    --output /tmp/launchbot-staging-storage-state.json \
    --validate-route /payroll/payroll-list \
    --wait-for-text Payroll
```

If login selectors changed, pass explicit selectors:

```bash
node scripts/launchbot-with-secrets.mjs --only staging -- \
  node apps/launchbot/runtime/help-article-staging-auth-state.mjs \
    --source-url "$LAUNCHBOT_STAGING_URL" \
    --output /tmp/launchbot-staging-storage-state.json \
    --email-selector 'input[name="email"]' \
    --password-selector 'input[name="password"]' \
    --submit-selector 'button[type="submit"]' \
    --validate-route /payroll/payroll-list \
    --wait-for-text Payroll
```

If MFA or OTP blocks login, return `blocked: staging_login_requires_human_otp_or_mfa` and keep placeholders.

4. Dry-run the screenshot plan:

```bash
node apps/launchbot/runtime/help-article-screenshot-runner.mjs \
  --browser playwright \
  --plan apps/launchbot/output/help-articles/screenshot-plans/<article-slug>.json \
  --source-url "$LAUNCHBOT_STAGING_URL" \
  --storage-state /tmp/launchbot-staging-storage-state.json \
  --dry-run \
  --output-dir apps/launchbot/output/help-articles/assets/<article-slug>
```

5. Capture with Playwright:

```bash
node apps/launchbot/runtime/help-article-screenshot-runner.mjs \
  --browser playwright \
  --plan apps/launchbot/output/help-articles/screenshot-plans/<article-slug>.json \
  --source-url "$LAUNCHBOT_STAGING_URL" \
  --storage-state /tmp/launchbot-staging-storage-state.json \
  --timeout-ms 60000 \
  --allow-blocked \
  --output-dir apps/launchbot/output/help-articles/assets/<article-slug>
```

6. Inspect the manifest:

```bash
node -e 'const manifest = JSON.parse(require("fs").readFileSync("apps/launchbot/output/help-articles/assets/<article-slug>/screenshot-manifest.json", "utf8")); console.log(JSON.stringify({ status: manifest.status, blocker: manifest.blocker, shots: manifest.shots.map((shot) => ({ id: shot.id, status: shot.status, waitForText: shot.waitForText })) }, null, 2));'
```

## Common Blockers

- `Playwright is not installed`: install Playwright/Chromium on the Hermes VM or use the approved runtime image.
- `Staging target host is not allowlisted`: use an approved StaffAny staging/DEV host only.
- `Missing LAUNCHBOT_STAGING_EMAIL` or `Missing LAUNCHBOT_STAGING_PASSWORD`: hydrate staging credentials from Secret Manager or the live profile.
- `Timed out waiting for text`: route, feature flag, demo data, or wait text is wrong. Update the screenshot plan rather than forcing capture.
- `Storage state not found`: regenerate runtime-only storage state.
- `staging_login_requires_human_otp_or_mfa`: stop and request an approved non-MFA test account or existing secure runtime auth path.
- Redaction uncertainty: do not insert the screenshot; keep placeholders.

## Output

Return:

1. Playwright status.
2. Credential source status with env names only, never values.
3. Storage-state path if created.
4. Screenshot manifest path.
5. Captured screenshots or exact blockers.
6. Whether article placeholders remain unchanged.
