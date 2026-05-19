# Jira Field Contract

The PSM Ops bot writes PS/customer-ops work to PCO Jira Service Management and RevOps/BD Ops/NYSS work directly to ROI Jira Service Management.

## Project

- Project key: `PCO`
- Project name: `PCO - PSM Customer Ops`
- Source of truth: Jira Service Management

## ROI Direct Project

- Project key: configured by `PSM_OPS_ROI_JIRA_PROJECT_KEY`
- Source of truth: Jira Service Management ROI board
- Idempotency key: source Slack thread permalink
- No duplicate PCO execution wrapper for ROI-direct work
- Linked PCO customer-loop tracker: allowed for PS-facing customer follow-up visibility, default for resolved PS Team billing/invoice asks, label `ps-wee-roi-tracker`, status `Waiting Internal`

## Preconfigured Runtime Values

The live profile must configure these environment variables before the gateway is healthy:

| Purpose | Environment variable |
| --- | --- |
| Jira base URL | `JIRA_BASE_URL` |
| Jira API user email | `JIRA_EMAIL` |
| Jira API token | `JIRA_API_TOKEN` |
| PCO service desk ID | `PSM_OPS_JIRA_SERVICE_DESK_ID` |
| Slack/Jira access policy | `PSM_OPS_ACCESS_POLICY_PATH` |
| Customer Next Action request type | `PSM_OPS_JIRA_REQUEST_TYPE_CUSTOMER_NEXT_ACTION` |
| Onboarding Task request type | `PSM_OPS_JIRA_REQUEST_TYPE_ONBOARDING_TASK` |
| Data Hygiene request type | `PSM_OPS_JIRA_REQUEST_TYPE_DATA_HYGIENE` |
| Handoff Package request type | `PSM_OPS_JIRA_REQUEST_TYPE_HANDOFF_PACKAGE` |
| Adhoc Ops request type (Event AA) | `PSM_OPS_JIRA_REQUEST_TYPE_ADHOC_OPS` (live PCO ID `118`) |
| REV Cross Sell request type (Event AA) | `PSM_OPS_JIRA_REQUEST_TYPE_REV_CROSS_SELL` (live PCO ID `120`) |
| Feedback request type (Event AA) | `PSM_OPS_JIRA_REQUEST_TYPE_FEEDBACK` (live PCO ID `122`) |
| PS Follow Up request type (Event AA) | `PSM_OPS_JIRA_REQUEST_TYPE_PS_FOLLOW_UP` (live PCO ID `123`) |
| CS Follow Up request type (Event AA) | `PSM_OPS_JIRA_REQUEST_TYPE_CS_FOLLOW_UP` (live PCO ID `124`) |
| PDT Discovery request type (Event AA) | `PSM_OPS_JIRA_REQUEST_TYPE_PDT_DISCOVERY` (live PCO ID `125`) |
| MKT ClubAny Interest request type (Event AA) | `PSM_OPS_JIRA_REQUEST_TYPE_MKT_CLUBANY` (live PCO ID `126`) |
| Event AA Slack channel ID | `PSM_OPS_AA_CHANNEL_ID` (live channel `C0B5H2YE5T2`) |
| Event AA selfie Drive folder | `PSM_OPS_AA_SELFIE_DRIVE_FOLDER_ID` (defaults to live folder `1hxeLDkyLLoVwuKCBPTjLK7ypnZTB9xHc`) |
| Event AA Drive OAuth token file | `PSM_OPS_DRIVE_TOKEN_FILE` (path to the OAuth refresh-token JSON minted via `InstalledAppFlow`; user-account credential with the `https://www.googleapis.com/auth/drive.file` scope; defaults to `~/.hermes/profiles/psmopsbot/drive-token.json`) |
| Event AA Drive OAuth client secret file | `PSM_OPS_DRIVE_CLIENT_SECRET_FILE` (path to the OAuth desktop-client JSON downloaded from Google Cloud Console; defaults to `~/.hermes/profiles/psmopsbot/drive-client-secret.json`; see `deploy/gce-onboarding-runbook.md` for the one-time setup) |
| Creator field | `PSM_OPS_JIRA_FIELD_CREATOR`; in thin POC this defaults to `customfield_10914` |
| Customer field | `PSM_OPS_JIRA_FIELD_CUSTOMER` |
| StaffAny Org(s) field | `PSM_OPS_JIRA_FIELD_STAFFANY_ORGS` |
| Owner PSM field | `PSM_OPS_JIRA_FIELD_OWNER_PSM` |
| Contributor CSE field | `PSM_OPS_JIRA_FIELD_CONTRIBUTOR_CSE` |
| Action type field | `PSM_OPS_JIRA_FIELD_ACTION_TYPE` |
| Risk reason field | `PSM_OPS_JIRA_FIELD_RISK_REASON` |
| Source links field | `PSM_OPS_JIRA_FIELD_SOURCE_LINKS` |
| Reminder at field | `PSM_OPS_JIRA_FIELD_REMINDER_AT` only if a separate reminder field is introduced later |
| PS Team field | `PSM_OPS_JIRA_FIELD_PS_TEAM`; in thin POC this defaults to `customfield_10876` |
| ROI project key | `PSM_OPS_ROI_JIRA_PROJECT_KEY` |
| ROI service desk ID | `PSM_OPS_ROI_JIRA_SERVICE_DESK_ID` |
| ROI request type ID | `PSM_OPS_ROI_JIRA_REQUEST_TYPE_ID` |
| ROI customer/org field | `PSM_OPS_ROI_JIRA_FIELD_CUSTOMER` |
| ROI StaffAny Organization object field | `PSM_OPS_ROI_JIRA_FIELD_STAFFANY_ORGS` |
| ROI request category field | `PSM_OPS_ROI_JIRA_FIELD_REQUEST_CATEGORY` |
| ROI source links field | `PSM_OPS_ROI_JIRA_FIELD_SOURCE_LINKS` |
| ROI requester field | `PSM_OPS_ROI_JIRA_FIELD_REQUESTER` |
| ROI requester Slack field | `PSM_OPS_ROI_JIRA_FIELD_REQUESTER_SLACK` |
| ROI original channel field | `PSM_OPS_ROI_JIRA_FIELD_ORIGINAL_CHANNEL` |
| ROI priority/urgency field | `PSM_OPS_ROI_JIRA_FIELD_PRIORITY` |

Do not guess these environment-configured IDs at answer time. `validate_jira_configuration` must fail closed when required PCO values are missing.

For ROI, `validate_roi_jira_configuration` must discover required request fields from JSM request-type metadata at runtime. If a required field cannot be mapped deterministically, or if multiple ROI request types / ambiguous field mappings are configured, fail closed.

ROI ticket quality requires the text company/customer field and the object-backed StaffAny Organization field when the request type exposes both fields. Do not treat `Company Name` alone as enough when Jira shows an empty `StaffAny Organization` object slot.

ROI requester is mandatory. Explicit `requested by` / `reported by` wins; otherwise use the current Slack sender. Do not fall back to a bot, team, or `team@staffany.com` requester.

For ROI urgency fields, match the field's configured options exactly. If the required field is `Urgent?` with Yes/No options and the Slack request does not state urgency, use `No`; do not send `Normal`, `Medium`, or boolean values.

## PS Team Routing

- Jira `PS Team` is the task-owner source of truth for "my tasks" and scoped reminders.
- Thin POC fetches Slack users, canonicalizes profile email/name, and auto-matches the caller to the configured `PS Team` option.
- Do not trust model-guessed email spelling; use Slack profile data before matching Jira.
- Use `resolve_slack_user_identity` to resolve one Slack mention, email, or exact name before asking who an abbreviated owner such as `Jo`, `Jos`, or `Josica` means.
- If no `PS Team` option matches the caller, fail closed with `Confidence: blocked`.
- `CS duty`, `cs duty`, and equivalent spelling variants mean Jira `PS Team = CS Duty`.
- `Eng duty` means Jira `PS Team = Eng Duty`.
- These are PS Team values, not Jira person assignees. Do not ask who is on duty when the user asked for `CS duty`.

## Event AA Intake Routing

- The Event AA Slack channel is configured by `PSM_OPS_AA_CHANNEL_ID`. The live channel ID is `C0B5H2YE5T2`.
- Allowed request type keys for Event AA intake tickets: `ps_follow_up`, `cs_follow_up`, `adhoc_ops`, `rev_cross_sell`, `pdt_discovery`, `mkt_clubany`, `feedback`. The old `cross_sell` and `churn_revival` keys are no longer wired through the bot.
- The Event AA Jira queue filters by Request Type in (PS Follow Up, CS Follow Up, Adhoc Ops, REV Cross Sell, PDT Discovery, MKT ClubAny Interest, Feedback) and by label `AA-SG-2026`.
- When `create_ps_wee_intake_ticket` is called with a `slack_thread_url` whose channel matches `PSM_OPS_AA_CHANNEL_ID`:
  - If `request_type_key` is one of the 7 allowed keys, use it as-is.
  - Otherwise, default `request_type_key` to `feedback` so the ticket still lands in the Event AA queue. Triage can retag.
  - The literal label `AA-SG-2026` is added to every AA ticket via Jira's standard `labels` field (best-effort post-create; failure surfaces as a warning, not a block).
  - The `Creator` single-select field (`PSM_OPS_JIRA_FIELD_CREATOR`; thin POC default `customfield_10914`) is best-effort. The matcher resolves the Slack tagger (or the optional `creator_slack_user_email` override) and normalizes the display name against the field's options (substring tolerant, case-insensitive). When no option matches, the field is omitted and the ticket still creates — never blocked on creator resolution.
  - `pic` is the person-in-charge name the PSM met. The MCP stores it in the internal metadata comment and uses it in the selfie filename.
  - Multiple categories in one Slack message: the agent calls `create_ps_wee_intake_ticket` once per category. Idempotency is scoped to `(slack_thread_url, request_type)` so different categories in the same thread do not collide.
  - Link-to-existing: when the PSM mentions an issue the customer has likely raised before, the agent calls `search_pco_tickets` for that customer to look for an open PCO ticket on the same topic. The per-category AA ticket is still created (event-trace record), then linked to the prior issue via `link_pco_to_pco_issue(source_issue_key=<new AA key>, target_issue_key=<existing PCO key>)`. The link is always `Relates`. No linking when no clear match exists.
- Outside the AA channel, the 7 Event AA request types stay available for explicit asks; do not auto-route to them and do not enforce the creator field or the `AA-SG-2026` label.
- Routing cues from the PSM's Slack message:
  - `deep dive`, `advanced`, `PS follow up` → `ps_follow_up`
  - `troubleshooting`, `bug`, `lag`, `negative feedback`, `CS follow up` → `cs_follow_up`
  - `re-training`, `retraining`, `webinar`, `basic training`, `adhoc ops` → `adhoc_ops`
  - `cross sell`, `upsell`, `expansion`, `PayrollAny`, `EngageAny`, `HRAny` → `rev_cross_sell`
  - `ATS`, `AI agents`, `PDT`, `discovery` → `pdt_discovery`
  - `ClubAny`, `club any`, `MKT` → `mkt_clubany`
  - anything else (or unclear) → `feedback`
- PS Team auto-route by category (AA only): `cs_follow_up` → `Ega`; `adhoc_ops` → `PS Ops`; all other categories → the Slack tagger. Explicit `ps_team` overrides the auto-route.
- Company name lands in **both** the text customer field and the StaffAny Organisation object field (`PSM_OPS_JIRA_FIELD_STAFFANY_ORGS`; thin POC default `customfield_10667`) when the company resolves through the reviewed customer-channel map. `customfield_10667` is a Jira Assets (CMDB) object reference, so the wire shape is an **array of `{"key": "<objectKey>"}` objects** (Jira rejects raw strings with `"expected Object"`). The MCP resolves each supplied org name to its Assets `objectKey` by running progressively more permissive AQL queries against the Assets workspace, stopping at the first unique match: (1) `Name = "<supplied>"` exact, (2) `Name = "<stripped>"` after dropping trailing legal-entity tokens like `Pte Ltd` / `Sdn Bhd` / `Pty Ltd` / `Inc` / `Ltd` (handles the common C360-canonicalised "Acme Pte Ltd" → Assets "Acme" case), (3) `Name like "<supplied>"` substring, (4) `Name like "<stripped>"` substring. Substring matches are accepted only when they return exactly one Assets object, so an ambiguous lookup never picks the wrong customer. Names that still don't resolve uniquely are dropped from the payload and surfaced as a warning so triage can assign manually; the ticket still lands. Agents should prefer to call `search_c360_customers` first and pass the canonical `orgMatches[].matchedValue` as `staffany_orgs` to maximize the asset match rate.
- For Event AA intakes only, the MCP fetches `image/*` files attached to the trigger Slack message and uploads them to the configured Google Drive folder (`PSM_OPS_AA_SELFIE_DRIVE_FOLDER_ID`) with filename `{slugified_company}_{slugified_pic}{ext}`. Selfies are **not** attached to the Jira ticket. Non-image files are skipped. The download+upload is best-effort: per-file errors are silently dropped, and the Slack reply mentions the saved count when at least one selfie was uploaded. When the Drive folder or OAuth files are not configured, the upload is a silent no-op. Implemented by `_download_slack_images_for_drive` + `upload_aa_selfies` (`aa_selfie_drive.py`).
- Filename slugify rules (`aa_selfie_drive._slugify`): runs of non-alphanumeric ASCII characters (whitespace, punctuation, Unicode) are replaced with a single `-`, leading/trailing dashes are stripped, and the result is lowercased. Empty results fall back to `unknown`. Example: `Kopi Janji (SG) Pte Ltd` → `kopi-janji-sg-pte-ltd`. The extension comes from the original Slack filename when present, otherwise from the mime-type map (`image/jpeg`→`.jpg`, `image/png`→`.png`, etc.; fallback `.jpg`). When the same `(company, pic)` has multiple selfies in one message, a `-{n}` suffix (`-2`, `-3`, …) is appended before the extension. No length capping is applied — Drive accepts long names.
- Bahasa-to-English translation applies only to Event AA intakes. When the trigger Slack message is fully or partially in Indonesian, the agent (not the MCP) writes the Jira `summary` and `description` in clear English before calling `create_ps_wee_intake_ticket`. Customer names, outlet names, dates, numbers, and product terms are preserved verbatim. The untranslated original is appended to the description under an `**Original (Bahasa):**` heading so the team can verify the translation. Mixed-language messages translate Indonesian portions only and leave English/product terms as-is. Outside the AA channel, both the Jira `summary` and `description` remain in the language the PSM used (no auto-translation).

## Customer Channel Routing

- `PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH` points to the reviewed Slack channel map in runtime/profile storage.
- Each reviewed mapping must include `channel_id`, `channel_name`, `customer_key`, `customer_name`, `staffany_orgs`, and `status=reviewed`.
- Use `resolve_customer_channel_org` for customer-specific Slack channels before creating a PS WEE intake ticket.
- If the message names a different customer from the reviewed channel mapping, fail closed and ask for confirmation before creating the ticket.
- Unmapped general Slack channels keep the existing needs-info intake behavior.

## Jira Assignee

- Jira assignee is still available for explicit person-assignment requests such as `assign PCO-135 to @Alya`.
- Use `set_pco_assignee` for existing issues. Resolve the target through Slack profile data or Jira user search, then call Jira Cloud's issue assignee API.
- Do not use assignee for "my tasks", reminders, or duty routing; those remain scoped by Jira `PS Team`.
- The assignment hygiene cron treats missing Jira assignee as a PS lead triage gap, not as task ownership truth.

## Engineering Issue Links

- Use `find_engineering_issue` for natural-language KER/SCHE lookup before linking. Search only allowlisted `KER` and `SCHE` projects and return only key, summary, status, issue type, updated timestamp, and URL.
- Use `link_pco_to_engineering_issue` only for existing `PCO-*` issues that need release tracking against `KER-*` or `SCHE-*`.
- Default link type is `Blocks`; the tool creates the link so the PCO shows as blocked by the engineering issue.
- `Relates` is allowed as a fallback only when Jira does not support the standard Blocks link type.
- Reject non-PCO source issues and non-KER/non-SCHE targets.
- Do not expose raw engineering issue descriptions, comments, attachments, or Jira bulk exports.

## PCO-to-PCO Issue Links

- Use `link_pco_to_pco_issue(source_issue_key, target_issue_key)` when an AA event ticket should reference a previously-tracked PCO ticket for the same customer issue. The link type is always `Relates`.
- Both keys must match `PCO-\d+`; mismatched or identical keys are blocked.
- The link is idempotent: re-running the tool returns `already_exists=true` instead of duplicating the link or surfacing the raw Jira error.
- Use this primarily for the AA link-to-existing flow; do not link speculatively.

## ROI Customer-Loop Tracker Links

- Use `create_or_link_pco_roi_tracker` only after an ROI ticket has been created or reused.
- The PCO tracker must be a Customer Success Work issue, labelled `ps-wee-roi-tracker`, linked so the ROI issue blocks the PCO issue, and transitioned to `Waiting Internal`.
- The Slack thread permalink is the idempotency key for the PCO tracker. Reuse an existing same-thread `ps-wee-roi-tracker` issue instead of creating duplicates.
- ROI remains execution source of truth. The PCO tracker exists only so PS can see pending billing/internal-team work and close the customer loop.

## Statuses

Allowed target statuses:

- Open
- Waiting Customer
- Waiting Internal
- Scheduled
- Done
- Cancelled

The MCP adapter must retrieve available transitions for the issue and choose the transition whose name or target status matches the requested status.

## Comment Policy

- Internal comments: allowed.
- Public customer-visible comments: blocked unless `PSM_OPS_JIRA_PUBLIC_COMMENTS_ENABLED=true`.

## Reminder Policy

- Use Jira `duedate` as the thin POC reminder source of truth.
- The weekday 09:00 SGT central digest queries tasks due tomorrow, due today, and overdue tasks until they are Done.
- The weekday 17:00 SGT EOD catch-up digest queries due-today and overdue tasks until they are Done.
- The weekday 09:15 SGT assignment hygiene digest queries active PCO issues missing Jira assignee, `PS Team`, or `duedate`.
- Missing assignee or missing `PS Team` appears under `Needs PS lead triage` for Josica. Missing `duedate` with a known `PS Team` appears under that `PS Team`, including `CS Duty`.
- Do not store reminders in files, memory, cron prompts, Slack messages, or local databases.
