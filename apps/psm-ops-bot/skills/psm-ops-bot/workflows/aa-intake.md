# Event AA Intake Workflow

**Applies when** the Slack thread permalink contains `/archives/C0B5H2YE5T2/`. The router in `SKILL.md` sends AA-channel turns here. Rules in this file are load-bearing and override anything else in `SKILL.md` when the channel matches.

## Must do (positive contract)

1. **Always ticket-first.** Inside the AA channel, never reply with create-ready offers, `Reply "create ticket"` prompts, clarifying questions, or pre-create disambiguation. Call `create_ps_wee_intake_ticket` for every action bullet before composing the Slack reply. **Perceived message intent is never a reason to block** — phrasings like "find out X", "let them know", "check who/what", "who is the …", "look up the …" are ticket asks (route to `cs_follow_up` if customer-facing follow-up, otherwise `feedback`), not C360 wiki Q&A. Every AA-channel trigger message is, by definition, a ticket ask.
2. **Parse the header (company + PIC), then emit one ticket per action bullet.** See the canonical message format and header parsing rules below.
3. **Pass the bare customer name as written** when C360 returns zero-match, multi-match, or any error — omit `staffany_orgs`. Triage handles disambiguation after the ticket exists.
4. **Never pass `due_date`.** Date phrases in the message body are context, leave them in `known_details`. The MCP defensively strips any `due_date` supplied on AA creates.
5. **When the trigger Slack message has ≥1 `image/*` attachment**, also call `create_ps_wee_intake_ticket` with `request_type_key="photo_follow_up"` once for the same `(customer, pic)`. The MCP may skip this via the LLM classifier — treat `status:"skipped"` as success.

## Routing — keyword → request_type_key

`create_ps_wee_intake_ticket` must use `request_type_key` from {`ps_follow_up`, `cs_follow_up`, `adhoc_ops`, `rev_cross_sell`, `pdt_discovery`, `mkt_clubany`, `feedback`, `photo_follow_up`}. Map PSM wording:

- `deep dive` / `advanced` → `ps_follow_up`
- `troubleshooting` / `bug` / `lag` / `negative feedback` → `cs_follow_up`
- `re-training` / `webinar` / `basic training` → `adhoc_ops`
- `cross sell` / `upsell` / `expansion` / `PayrollAny` / `EngageAny` / `HRAny` → `rev_cross_sell`
- `ATS` / `AI agents` / `PDT` / `discovery` / `feature` / `features` → `pdt_discovery`
- `ClubAny` / `MKT` → `mkt_clubany`
- anything else or unclear → `feedback`

Do not block to ask; default to `feedback`. The MCP enforces this default defensively when the AA channel matches. `photo_follow_up` (PCO request type id `127`) is reserved for the image-trigger rule and is never selected by keyword matching.

## Canonical message format and header parsing

The trigger Slack message in the AA channel follows this shape — (1) a header that names the company and PIC, and (2) every remaining bullet is one ticket the user wants opened (typically `Follow up on …`, `Want to …`, `Interested in …`, etc.). Map each ticket bullet to a `request_type_key` per the routing list above. Lines that name a known customer or look like a person name are header context, not ticket categories — even when they sit on their own bullet level.

Header shapes — treat **every bullet/line before the first action-verb bullet** as part of the header:

- Single bullet with `/` separator, either order: `Dandy Collection / Rohit` or `Rohit / Dandy Collection`.
- Labeled keys: `company: dandy collection` + `pic: Rohit` on separate lines.
- Free-form context line after the company+PIC bullet (e.g. `flagged timesheet save lag + a payroll export bug`).
- **Shorthand: company and PIC split across two single-token bullets with no separator.** When two consecutive header bullets each carry one short phrase, pair them as (company, PIC). The one that looks like a person name is the PIC; the other is the company — order is not load-bearing. Example: `• qiqi` / `• Lo and Behold` / `• Want to expand more outlets` resolves to company=`Lo and Behold`, pic=`qiqi`, one `rev_cross_sell` ticket from the `Want to expand more outlets` bullet. Do **not** ticket each header bullet as a separate customer.

## Multi-ticket per message

When a single tagged Slack message describes multiple follow-up categories for the same customer, call `create_ps_wee_intake_ticket` once per category. Idempotency is scoped to `(slack_thread_url, request_type, customer)`, so different categories — and different customers in the same thread+category — do not collide. When the PSM legitimately logs two customers in one message (e.g. two booth meetings back-to-back), pass the distinct `customer` value on each call and both tickets will create.

## PS Team auto-route

- `cs_follow_up` → `Ega`
- `adhoc_ops` → `PS Ops`
- all other categories → the Slack tagger

Explicit `ps_team` overrides the auto-route.

## Creator requirement

On AA-channel intakes the MCP re-derives the Slack tagger from `slack_thread_url` via `conversations.history` and uses that verified user ID for both Creator and PS Team — any `slack_user_email` or `creator_slack_user_email` supplied by the agent is overridden. This is defensive — agents have hallucinated invalid Slack IDs in both fields (e.g. `U07UTFE8U3X` on PCO-291/293, `U07N3TH1CJK` on PCO-298-300) which silently dropped both Creator and PS Team because nothing matched the access policy or dropdowns. The thread permalink IS the source of truth for "who tagged the bot" on AA. If Slack is unreachable, the agent-supplied value is used as fallback rather than blocking.

The resolved display name is matched against the Jira `Creator` single-select dropdown (`PSM_OPS_JIRA_FIELD_CREATOR`; thin POC default `customfield_10914`). Allowed options: `Josica`, `Izzat`, `Damba`, `Priska`, `May`, `Lucky`, `Ega`, `Alya`, `Jason`, `Kai Yi`, `Albert`, `Jan-E`, `Jeffrey`, `Wong Man Zhong`, `Jolene`, `Siti`, `Jeremy`, `Edeline`, `Kerren`, `Will`, `Vanessa`, `Janson`, `Eugene`. Matching is case-insensitive and substring-tolerant against the Slack display name (e.g. `Josica Lim` → `Josica`, `Jeremy Wong` → `Jeremy`, `Kai Yi Lee` → `Kai Yi`). When no option matches, the Creator field is silently omitted and the ticket still creates — triage assigns it. Ask PCO admin to add the option when a new PSM is onboarded.

## StaffAny Org resolution

Before calling `create_ps_wee_intake_ticket`, call `search_c360_customers(customer_name)` (or `get_c360_account_context(<customer_key>)` for the long form). Pass the resolved org identifier to `staffany_orgs=[<id>]` — prefer an explicit org/asset ID field when C360 returns one (e.g. a `staffany_org_key`, `orgId`, `customerKey`); otherwise pass the canonical `orgMatches[].matchedValue` (the StaffAny Org name) as the fallback.

When C360 returns no match, **returns multiple matches with no obvious tiebreaker**, **errors (HTTP 4xx/5xx, network/timeout, missing token), or returns an empty `answer: []`**, omit `staffany_orgs` entirely and pass the bare customer name as written in the Slack message — the MCP will best-effort try the supplied customer name, and if Jira's asset field rejects it the ticket still creates with the org left unassigned for triage. Disambiguation between multi-match entities is handled by triage (or by a follow-up Slack reply *after* the ticket exists), never by blocking the create.

**Do not call `ask_c360_customer_context` in AA flows** — it is the wiki Q&A endpoint and the MCP returns an `aa_channel_redirect` payload from that tool when the Slack thread URL is an AA-channel permalink. Use `search_c360_customers` / `get_c360_account_context` for AA org resolution only.

## C360 redirect hint

Inside the AA channel, `search_c360_customers` and `get_c360_account_context` still execute and may return a match — but on **zero-match, multi-match, or any C360 error**, the response now carries `aa_channel_redirect: true` and `next_action: "create_ps_wee_intake_ticket"` alongside the usual `confidence: needs-check`. Treat that flag as a deterministic instruction: do not ask the user to confirm the company name, do not compose a "please clarify" Slack reply, and do not skip the create. Call `create_ps_wee_intake_ticket` immediately with the bare customer name as written in Slack and `staffany_orgs` omitted; triage handles disambiguation after the ticket exists. Outside the AA channel these tools behave unchanged.

## Photo follow-up — image-trigger rule

When the AA trigger Slack message has at least one `image/*` attachment, after creating the per-bullet tickets you MUST also call `create_ps_wee_intake_ticket` once with `request_type_key="photo_follow_up"` for the same `(customer, pic)`. This is an additional ticket, not a replacement — bullet routing is unchanged. Use a short summary like `Photo follow up — <company>` (and a description that names the PIC and references the source Slack thread). The standard AA Drive + Jira selfie pipeline runs for this call too, so the image lands on the `photo_follow_up` ticket as well as on the bullet tickets. If the trigger Slack message has no images, do **not** create a `photo_follow_up` ticket. Reply-thread selfies sent via `attach_aa_selfie_to_thread` do not trigger a new `photo_follow_up` ticket — that tool keeps attaching to the already-opened AA tickets.

## Photo follow-up — skip signal

The MCP defensively skips `photo_follow_up` creation when an LLM intent classifier (Claude Haiku, run server-side from `create_ps_wee_intake_ticket`) judges the AA trigger Slack message as an explicit "no follow-up needed" message. The classifier reads the trigger message text and outputs a structured `{skip_photo_follow_up: bool, reason: str}` payload via tool-use; the MCP forwards the boolean as the skip decision and surfaces the reason in `answer.classifier_reason` and the audit log. Because this is LLM-based, the detector handles English, Indonesian, mixed-language, and arbitrary phrasings (e.g. `kindly disregard`, `for archive only`, `abaikan saja`) without a hardcoded phrase list.

On skip, the tool returns `{status: "skipped", reason: "no_follow_up_signal_detected", classifier_reason: "<one-line>", skipped_request_type: "photo_follow_up", slack_reply: "<one-line note>"}` with `confidence: verified`. Treat the response as success — quote the returned `slack_reply` and do not retry, do not block, do not interpret the skip as an error. Per-bullet AA tickets created via earlier calls are unaffected.

When the classifier is unavailable (missing `ANTHROPIC_API_KEY`, network failure, malformed response, ambiguous text), the MCP defaults to **NOT skip** — the ticket still creates so an LLM outage cannot silently drop a real follow-up. Skip is scoped to `photo_follow_up` only; other AA request types do not invoke the classifier and create normally regardless of the trigger message wording.

## Selfie ingest — initial

For Event AA intakes only, the MCP fetches `image/*` files attached to the trigger Slack message via `conversations.history` (`SLACK_BOT_TOKEN` auth), uploads each to the configured Google Drive folder (`PSM_OPS_AA_SELFIE_DRIVE_FOLDER_ID`, default folder `1hxeLDkyLLoVwuKCBPTjLK7ypnZTB9xHc`) with filename `{slugified_company}_{slugified_pic}__{slack_file_id}{ext}`, **and** attaches the same image(s) to the newly-created Jira ticket so the selfie lives on the ticket itself. Non-image files are skipped.

Failures are best-effort and never block ticket creation; the response carries `drive_status` (`ok` / `missing_folder_id` / `missing_token` / `auth_failed` / `upload_failed` / `no_downloads`) plus `drive_reason`, and the Slack reply lists the Drive saved count and Jira attached count separately. When the Drive folder or OAuth files are not wired up, the agent must quote `drive_reason` verbatim and never invent an environment-variable cause.

## Selfie ingest — follow-up reply

When a selfie is added as a *reply* in an existing AA thread (after `create_ps_wee_intake_ticket` has already run), call `attach_aa_selfie_to_thread(slack_thread_url, customer, pic)`. Pass the permalink of the *specific message* that holds the new selfie attachment — the tool only reads that one message, it does not scan the rest of the thread or fetch past images from Drive. The tool uploads to Drive **and** attaches the image to every AA ticket already opened for the thread (so a follow-up selfie reaches all of them). Each Drive upload's filename is `{slugified_company}_{slugified_pic}__{slack_file_id}{ext}`. Re-uploads of the same Slack file are allowed; "duplicate selfie in Drive" is preferable to "missing selfie".

The tool returns a structured `drive_status` (`ok` / `missing_folder_id` / `missing_token` / `upload_failed` / `auth_failed`) plus `saved_count`, `jira_attached_count`, `jira_ticket_count`, and a `caveat` describing the outcome (including partial-ingest cases such as Slack download failures) — quote the caveat verbatim when reporting back to Slack instead of guessing the cause.

## Drive diagnostics

When an intake or follow-up selfie call reports `drive_status` other than `ok`, call `verify_drive_oauth` (read-only) before guessing the cause. The tool returns `drive_status` ∈ {`ok`, `missing_folder_id`, `missing_token`, `refresh_failed`, `api_unauthorized`, `api_failed`} plus `drive_reason` and `last_error`. Quote `drive_reason`/`last_error` verbatim back to the thread. `refresh_failed` means the Drive OAuth must be re-set up on the host (mint a new refresh_token); `api_unauthorized` means scope/account problem; `api_failed` is a transient network/5xx. The ticket itself is unaffected — these checks only diagnose the selfie path.

## Label

Every AA ticket is tagged with the Jira label `AA-SG-2026` post-create (Jira labels cannot contain spaces). No agent action required.

## Link to existing

When an AA tag mentions an issue the customer has likely raised before (e.g. recurring bug, lingering pricing concern, prior feature ask), call `search_pco_tickets` for the customer to look for an open PCO ticket covering the same topic. Still create the per-category AA ticket so KY has the event-trace record, then call `link_pco_to_pco_issue(source_issue_key=<new AA key>, target_issue_key=<existing PCO key>)` — the link is always `Relates`. Skip the linking step when no clear match exists — do not link speculatively.

## Bahasa translation

When the trigger Slack message is fully or partially in Indonesian, the agent writes the Jira `summary` and `description` passed into `create_ps_wee_intake_ticket` in clear English. Preserve customer names, outlet names, dates, numbers, and product terms verbatim. Append the untranslated original at the end of `description` under an `**Original (Bahasa):**` heading for team sanity-check. Mixed-language messages translate Indonesian portions only. Do not translate outside the AA channel.

## Never pass `due_date`

AA intakes must never carry a Jira `duedate`. Any date phrase in the trigger message (e.g. `2 June`, `2/6`, `EOM`, `next Tuesday`) belongs in `known_details` / description as context, not the Jira `duedate` field. Triage owns deadlines for AA tickets. The MCP defensively strips any `due_date` supplied on AA creates.
