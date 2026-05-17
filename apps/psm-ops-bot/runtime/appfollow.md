# AppFollow Runtime

AppFollow is the PSM Ops source of truth for App Store and Google Play review metadata, internal review tags, and public review replies.

Slack remains the triage and approval surface. Jira PCO is used only when an internal StaffAny follow-up task is needed; do not turn every review into a Jira ticket.

## Access Contract

- API base: `https://api.appfollow.io/api/v2`
- Auth header: `X-AppFollow-API-Token`
- Token env: `APPFOLLOW_API_TOKEN`
- Secret Manager secret name: `psm-ops-bot-appfollow-api-token`
- MCP server: `psm_appfollow`
- Tools:
  - `list_appfollow_apps`
  - `get_appfollow_review`
  - `tag_appfollow_review`
  - `draft_appfollow_reply`
  - `suggest_appfollow_review_identity_candidates`
  - `confirm_appfollow_review_identity`
  - `publish_appfollow_reply_after_approval`

The API token must live in Secret Manager or the live profile `.env`. Never commit or paste it into this repo.

Use a v2 API token from AppFollow Account > API Dashboard > Token list > Add new token. Do not use the API access `api_secret` value from the dashboard sidebar as `APPFOLLOW_API_TOKEN`; AppFollow v2 expects the token in the `X-AppFollow-API-Token` header and returns HTTP 401 when the value is not an API token.

## Credit Policy

The Free plan is event-driven only. Do not create a constant review polling cron.

- `GET /account/apps` costs 1 credit and is used for setup verification.
- `GET /reviews` costs 10 credits and should run only after a Slack review alert or a direct human review lookup.
- `POST /reviews/tags` costs 10 credits and starts as a dry-run preview; use a harmless internal tag first.
- `POST /reviews/reply` costs 10 credits and is blocked unless reply publishing is explicitly enabled and same-thread approval says `post reply` or `publish reply`.

## Slack Alert Flow

On a new `#all-reviews` Slack alert:

1. Extract the AppFollow review URL and `review_id`.
2. Resolve the AppFollow `ext_id` from `PSM_OPS_APPFOLLOW_APP_EXT_IDS` or `PSM_OPS_APPFOLLOW_DEFAULT_EXT_ID`. If AppFollow only exposes a collection in `/account/apps`, resolve `collection_name` from `PSM_OPS_APPFOLLOW_COLLECTION_NAMES` or `PSM_OPS_APPFOLLOW_DEFAULT_COLLECTION_NAME` instead.
3. Fetch the canonical review from AppFollow only when `ext_id` or `collection_name` is available.
4. Classify severity and theme.
5. Reply in the same Slack thread with `PSM Ops automation:` triage and action options.
6. Store runtime state keyed by `store + ext_id + review_id` so the same alert is not triaged twice.

The no-agent adapter is:

```bash
~/.hermes/profiles/psmopsbot/scripts/psm_ops_appfollow_review_triage.py \
  --slack-thread-url "https://staffany.slack.com/archives/<channel>/p<ts>" \
  --apply
```

Use `--dry-run` behavior by omitting `--apply`. Use `--force` only when intentionally re-triaging an already recorded review.

## Public Reply Guard

Public review replies are human-approved by default.

`draft_appfollow_reply` may generate a suggested reply, but the default public CTA must ask the reviewer to email `support@staffany.com` privately with their StaffAny account email or phone number plus company/outlet. Do not ask the reviewer to post email or phone in the public App Store / Play Store review, and do not make a `REV-<review_id>` reference code the main customer action.

`publish_appfollow_reply_after_approval` must remain blocked unless:

- the approving Slack thread says `post reply` or `publish reply`;
- `PSM_OPS_APPFOLLOW_REPLY_PUBLISH_ENABLED=true` is set after one approved smoke test;
- the reply text is the final reviewed copy.

Until that smoke test is complete, use AppFollow tagging and Slack triage only.

## Reviewer Identity Follow-up

Reviewer names from App Store / Google Play are not enough to identify a StaffAny customer, org, or contact.

- Public reply CTA: ask the reviewer to email `support@staffany.com` with their StaffAny account email or phone number plus company/outlet.
- Internal correlation stays on the review key: `store + ext_id + review_id`.
- Use AppFollow tags `identity_unknown`, `identity_requested_private`, `identity_candidate`, and `identity_confirmed` for the review identity workflow.
- Use `suggest_appfollow_review_identity_candidates` only after a private support follow-up or internal evidence provides email, phone, company/outlet, or Customer 360 candidates.
- Exact email match against Customer 360 or HubSpot candidate evidence can be treated as verified.
- Phone-only or company/outlet-only matches are candidates and need human confirmation.
- Use `confirm_appfollow_review_identity` only after PS confirms the customer/contact; it stores a redacted runtime mapping outside git.

## State

Runtime idempotency state is outside git:

```text
PSM_OPS_APPFOLLOW_STATE_PATH
```

Default:

```text
~/.hermes/profiles/psmopsbot/state/appfollow_reviews.json
```

The state key is:

```text
store + ext_id + review_id
```

Do not store raw Slack transcripts or AppFollow API tokens in this state file.
