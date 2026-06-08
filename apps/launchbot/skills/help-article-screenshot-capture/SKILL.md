---
name: help-article-screenshot-capture
description: Plan and capture StaffAny product screenshots for Launchbot help article drafts using a narrow Playwright runner, demo-safe data, redaction checks, and review-ready screenshot manifests.
---

# Help Article Screenshot Capture

Use this skill when Launchbot needs real StaffAny product screenshots for a help article draft or update.

Screenshot capture is an optional asset lane. If this skill or the runner is unavailable, blocked, or fails, keep screenshot placeholders plus a precise blocker note; do not block the help article draft, Google Docs review, Slack approval, or Intercom draft/staging workflow for otherwise valid article text.

If capture fails on StaffAny staging because of Playwright, login, storage-state, route, wait text, or feature-flag issues, use `help-article-screenshot-troubleshooter` before retrying the same plan.

## Source Order

1. Authenticated StaffAny DEV/staging with a demo or approved test organisation.
2. Local Gryphon with safe seeded data when the UI state is enough.
3. Existing screenshot files supplied by a reviewer.

If none are available, do not fabricate screenshots. Generate a blocked screenshot manifest and keep placeholders in the article.

## Workflow

1. Build a shot list before capture:
   - Article heading and placement.
   - Route or navigation path.
   - UI state and selectors/text to wait for.
   - Required data, feature flags, and permissions.
   - Redaction selectors or notes.
2. Preview with the screenshot runner in dry-run mode.
3. Capture only after the user has approved the shot list or explicitly requested capture.
4. Use demo or test data. Do not use production customer data unless explicitly approved and redacted.
5. Save screenshots under `apps/launchbot/output/help-articles/assets/<article-slug>/`.
6. Save the runner manifest beside the screenshots as `screenshot-manifest.json`.
7. Insert images immediately after the step they support, or leave placeholders with the blocked reason.

## Runner

Use the repo runner:

```bash
node apps/launchbot/runtime/help-article-screenshot-runner.mjs \
  --plan apps/launchbot/output/help-articles/screenshot-plans/<article-slug>.json \
  --source-url https://<approved-staging-url> \
  --param paymentId=<demo-payment-id> \
  --param disbursementId=<demo-disbursement-id> \
  --output-dir apps/launchbot/output/help-articles/assets/<article-slug>
```

If Playwright is unavailable on an operator machine but Google Chrome is installed, use the same runner with the Chrome DevTools fallback:

```bash
node apps/launchbot/runtime/help-article-screenshot-runner.mjs \
  --browser chrome-cdp \
  --plan apps/launchbot/output/help-articles/screenshot-plans/<article-slug>.json \
  --source-url https://<approved-staging-url> \
  --storage-state <runtime-only-staging-storage-state.json> \
  --param paymentId=<demo-payment-id> \
  --param disbursementId=<demo-disbursement-id> \
  --output-dir apps/launchbot/output/help-articles/assets/<article-slug>
```

For planning only:

```bash
node apps/launchbot/runtime/help-article-screenshot-runner.mjs \
  --plan apps/launchbot/output/help-articles/screenshot-plans/<article-slug>.json \
  --dry-run \
  --output-dir apps/launchbot/output/help-articles/assets/<article-slug>
```

If the runner reports `blocked`, return the exact blocker and shot list, then leave the article placeholders unchanged. Never ask users to paste passwords, OTPs, cookies, localStorage, session tokens, or browser profile archives into Slack.

## Redaction Rules

Redact or avoid screenshots that show employee names, phone numbers, emails, NRIC/FIN, NPWP/KTP, passport numbers, bank account numbers, payment IDs, salaries, payroll amounts, tax/statutory amounts, customer org names, or non-demo organisation data.

If redaction cannot be verified, do not insert the screenshot.
