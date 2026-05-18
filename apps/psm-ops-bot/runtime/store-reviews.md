# Store Reviews Runtime

Direct Google Play Developer API and App Store Connect API are the PSM Ops
review sources of truth for App Store and Google Play review metadata.

Slack remains the triage surface. Jira PCO is used only when an internal
StaffAny follow-up task is needed; do not turn every review into a Jira ticket.

## Access Contract

- MCP server: `psm_store_reviews`
- Tools:
  - `list_store_review_apps`
  - `list_store_reviews`
  - `get_store_review`
  - `draft_store_review_reply`
  - `suggest_store_review_identity_candidates`
  - `confirm_store_review_identity`
- State key: `store + app_ref + review_id`
- Google Play package: `com.staffany.pixie`
- App Store app id: `1360658903`

Google Play auth uses a service account JSON with the Android Publisher scope:

```text
https://www.googleapis.com/auth/androidpublisher
```

Expose it through `GOOGLE_PLAY_SERVICE_ACCOUNT_FILE` or
`GOOGLE_PLAY_SERVICE_ACCOUNT_JSON`. The Play Console service account must have
app-level review access, including `Reply to reviews`, even though V1 does not
publish replies.

App Store Connect auth uses an API key with `issuer_id`, `key_id`, and the
`.p8` private key exposed through `APP_STORE_CONNECT_CONFIG_FILE`,
`APP_STORE_CONNECT_CONFIG_JSON`, or the separate `APP_STORE_CONNECT_*` env vars.
The API key role should be `Customer Support` or `Admin`.

The runtime needs `openssl` for App Store Connect and Google service-account JWT
signing. Health checks must fail if the signer is unavailable.

## Polling Flow

Install `psm_ops_store_review_poll.py` as an hourly no-agent cron:

```bash
cp apps/psm-ops-bot/runtime/scripts/psm_ops_store_review_poll.py \
  ~/.hermes/profiles/psmopsbot/scripts/psm_ops_store_review_poll.py
chmod 755 ~/.hermes/profiles/psmopsbot/scripts/psm_ops_store_review_poll.py

hermes -p psmopsbot cron create "0 * * * *" \
  --name "psmopsbot store review poll" \
  --script psm_ops_store_review_poll.py \
  --no-agent \
  --deliver "slack:#ps-weeman-bot-test"
```

The poller lists recent reviews with a 7-day lookback, classifies theme and
severity, emits `PSM Ops automation: Store review triage` only for new or
meaningfully changed reviews, and stores runtime state outside git. If there are
no new reviews, it prints `[SILENT]`.

Manual dry-run:

```bash
~/.hermes/profiles/psmopsbot/scripts/psm_ops_store_review_poll.py \
  --store app_store \
  --limit 5
```

Apply/persist mode:

```bash
~/.hermes/profiles/psmopsbot/scripts/psm_ops_store_review_poll.py \
  --store google_play \
  --limit 5 \
  --apply
```

## Public Reply Guard

V1 is draft-only. `draft_store_review_reply` may generate suggested public copy,
but no public reply publish tool is exposed.

Default public reply copy asks the reviewer to email `support@staffany.com`
privately with their StaffAny account email or phone number plus company/outlet.
Do not ask the reviewer to post email or phone in the public App Store / Play
Store review, and do not make a `REV-<review_id>` reference code the main
customer action.

## Reviewer Identity Follow-up

Reviewer names from App Store / Google Play are not enough to identify a
StaffAny customer, org, or contact.

- Public reply CTA: ask the reviewer to email `support@staffany.com` with their
  StaffAny account email or phone number plus company/outlet.
- Internal correlation stays on `store + app_ref + review_id`.
- Internal runtime labels are `identity_unknown`, `identity_requested_private`,
  `identity_candidate`, and `identity_confirmed`.
- Use `suggest_store_review_identity_candidates` only after a private support
  follow-up or internal evidence provides email, phone, company/outlet, or
  Customer 360 candidates.
- Exact email match against Customer 360 or HubSpot candidate evidence can be
  treated as verified.
- Phone-only or company/outlet-only matches are candidates and need human
  confirmation.
- Use `confirm_store_review_identity` only after PS confirms the customer/contact;
  it stores a redacted runtime mapping outside git.

## State

Runtime idempotency state is outside git:

```text
PSM_OPS_STORE_REVIEWS_STATE_PATH
```

Default:

```text
~/.hermes/profiles/psmopsbot/state/store_reviews.json
```

The state key is:

```text
store + app_ref + review_id
```

Do not store raw Slack transcripts, private keys, service-account JSON, API keys,
or raw phone/email in this state file.
