# Honcho Memory Runtime

Hermes Data Bot uses Honcho as an external memory provider for confirmed reusable learning only.

## Contract

- Provider: `honcho`
- Base URL: `http://127.0.0.1:8000` for the current self-hosted local pilot
- Workspace: `staffany-hermes-data-bot`
- AI peer: `staffanydatabot`
- User peer: `kaiyi`
- Recall mode: `tools`
- Session strategy: `per-session`

Honcho is not a source of truth for StaffAny data. It is a recall layer for reusable preferences, metric clarifications, terminology corrections, and repeated feedback patterns.

## What Belongs In Honcho

- Confirmed metric-definition preferences, for example how Kai Yi wants ambiguous terms interpreted.
- StaffAny terminology mappings that help the bot ask better questions.
- Preferred answer formats and caveat styles.
- Repeated feedback patterns that should influence future responses.
- Scoped follow-up preferences. Do not store broad reminder preferences that could override the Slack data-answer rule: final data answers are terminal, and `ok` / `done` acknowledgements close silently.

## What Does Not Belong In Honcho

- Secrets, API keys, access tokens, OAuth credentials, private keys, or env-file contents.
- Raw Slack transcripts, raw Slack files, or raw screenshots.
- Raw BigQuery query rows or one-off customer/org facts.
- PII, NRIC/FIN, phone numbers, bank details, payroll details, or employee-level sensitive data.
- Canonical product or metric definitions that should live in the repo registries.

## Promotion Rule

Honcho memory is runtime learning. If a memory becomes durable StaffAny product or metric truth, promote it into the relevant repo registry or skill reference after review. Do not leave canonical definitions only in Honcho.

## Runtime Setup

Profile-local Honcho config lives outside the repo:

```text
~/.hermes/profiles/staffanydatabot/honcho.json
```

Expected non-secret shape:

```json
{
  "baseUrl": "http://127.0.0.1:8000",
  "timeout": 10,
  "hosts": {
    "hermes.staffanydatabot": {
      "enabled": true,
      "workspace": "staffany-hermes-data-bot",
      "peerName": "kaiyi",
      "pinPeerName": true,
      "aiPeer": "staffanydatabot",
      "recallMode": "tools",
      "saveMessages": false,
      "writeFrequency": "session",
      "sessionStrategy": "per-session"
    }
  }
}
```

Honcho server provider keys stay in the self-hosted Honcho `.env` or Secret Manager, never in this repo.

## Backup

Use the local backup script for the self-hosted Postgres volume:

```bash
apps/hermes-data-bot/runtime/backup-honcho.sh
```

It writes compressed dumps under `~/.hermes/backups/honcho/`, keeps 14 days by default, and prints nothing when healthy.

## Verification

```bash
curl -fsS http://localhost:8000/health
hermes -p staffanydatabot memory status
```

Expected memory status includes `Provider: honcho` and `Status: available`.

Use a safe synthetic memory smoke only:

```text
Search Honcho for "Honcho smoke test for staffanydatabot".
```

Do not use customer data, Slack transcripts, query rows, or sensitive employee details in memory smoke tests.

## Review

Use the local review script when checking what Honcho has learned:

```bash
apps/hermes-data-bot/runtime/review-honcho-memory.sh --ids-only --limit 20
apps/hermes-data-bot/runtime/review-honcho-memory.sh --limit 20
```

The second command prints memory contents for operator review. Keep that output local. Do not redirect it into repo files, paste raw dumps into docs, or commit it as evidence.

Delete or promote memories by policy:

- Delete memories that contain secrets, PII, raw Slack transcript text, raw BigQuery rows, or one-off customer facts.
- Promote durable StaffAny product or metric truth into the relevant registry or skill reference.
- Leave preference and clarification memories in Honcho when they are reusable but not canonical product truth.
