# PCO Jira Request Types

PCO is the Jira Service Management project for PSM customer-ops work (`PCO - PSM Customer Ops`). These request types share the Jira work type `Task`, use the `PCO: Jira Service Management default workflow`, and are restricted in the customer portal.

This page defines the request types visible in the Jira admin request-type list captured on 2026-05-29. It was cross-checked against live Jira JQL reads from the `PCO` JSM project on 2026-05-29. Bot routing details come from the PSM Ops app packet and runtime config; request types marked "not wired" are visible in Jira but are not currently exposed as `create_ps_wee_intake_ticket` keys.

## Operating Rules

- PCO is the PS/customer-ops task source of truth.
- Jira ROI remains the source of truth for RevOps, BD Ops, NYSS, and ROI-board execution; only create a linked PCO customer-loop tracker when PS needs customer follow-up visibility.
- Portal group is Jira portal UI grouping, not necessarily queue membership. Event AA queue membership is filtered by Request Type plus label `AA-SG-2026`.
- For Event AA intake, `photo_follow_up` is image-triggered only. Do not use it for text-bullet keyword routing.
- When Jira request type IDs differ from thin POC defaults, runtime env vars are the source of truth. Do not guess IDs.

## Request Type Matrix

| Request type | Portal group | Bot key / ID | Definition | Use when | Do not use when |
| --- | --- | --- | --- | --- | --- |
| Adhoc Ops | General | `adhoc_ops` / `118` | Miscellaneous PS/event operational work that does not fit a specialist follow-up category. | Event AA wording mentions re-training, webinar, basic training, or another operational follow-up that PS Ops should triage. | The ask is a product discovery, revenue expansion, customer support issue, or pure feedback; use the more specific request type. |
| API Access Request | General | Not wired | Portal request type for API access, credentials, or integration enablement. Live Jira validation found no visible issues with this request type, so treat this as an intended category rather than observed usage. | A customer needs API access provisioned, changed, clarified, or followed up by the owning team, and the portal type is available to the human creating the issue. | The current bot should not guess this type. Observed API-access-related PCO tickets currently appear under PS Follow Up or PDT Discovery. |
| CS Follow Up | Used in 2 groups | `cs_follow_up` / `124` | Customer-facing support or CS follow-up, especially issue/bug follow-up from an event conversation. | Event AA wording mentions troubleshooting, bug, lag, negative feedback, or CS follow-up. In AA, PS Team auto-routes to `Ega`. | The action is PS-led deep dive/training or account expansion; use PS Follow Up, Adhoc Ops, or REV Cross Sell. |
| Customer Success Work | General | `customer_next_action` / `81` | General PS/customer success next action and default non-AA PCO intake type. | PS needs to track a customer follow-up, customer-loop tracker, or non-AA customer-ops task that does not belong to onboarding or data setup. | The source of truth should be ROI, KER, SCHE, or another board; link or create the right source-of-truth issue instead of making a duplicate PCO execution wrapper. |
| Data Setup | Onboarding | `data_hygiene` / `83` | Customer data setup, hygiene, import, cleanup, or data readiness work. | The task is about preparing, correcting, importing, or cleaning customer setup data. | The task is general onboarding coordination without data setup work; use Onboarding. |
| Event Ops | General | Not wired | Event operations, logistics, and event-administration work that is not a customer-specific follow-up category. | The request is about event invitations, event collateral, sponsorship outreach, payments, or event logistics. | The Slack request is Event AA customer follow-up; use the Event AA request types already wired through the bot. |
| Feedback | Event | `feedback` / `122` | General feedback or unclear event note that still needs a PCO event-trace ticket. | Event AA wording is unclear, broad, or does not map cleanly to another category. This is the Event AA safe default. | A clearer specialist category is present, such as bug follow-up, expansion interest, product discovery, or ClubAny interest. |
| MKT ClubAny Interest | Event | `mkt_clubany` / `126` | Marketing follow-up for ClubAny interest. | Event AA wording mentions ClubAny, `club any`, or MKT follow-up. | The customer is interested in revenue products like PayrollAny, EngageAny, or HRAny; use REV Cross Sell. |
| Onboarding | Onboarding | `onboarding_task` / `201` | General onboarding work for customer rollout, activation, or implementation coordination. | The task belongs to onboarding but is not specifically data setup or a training request type handled directly in Jira portal. | The task is data import/hygiene/readiness; use Data Setup. |
| PDT Discovery | Event | `pdt_discovery` / `125` | Product discovery or product-team learning opportunity from customer feedback. | Event AA wording mentions ATS, AI agents, PDT, discovery, feature, or features. | The customer is reporting a bug or lag; use CS Follow Up. |
| Photo Follow Up | Event | `photo_follow_up` / `127` | Event AA photo/selfie evidence tracking ticket. | The Event AA trigger Slack message has at least one `image/*` attachment; create this in addition to any per-bullet tickets for the same customer/PIC. | Text-only bullets, follow-up reply images after AA tickets already exist, or non-AA channels. The MCP blocks `photo_follow_up` outside the AA channel. |
| PS Follow Up | Used in 2 groups | `ps_follow_up` / `123` | PS-led follow-up such as advanced workflow help or deep-dive customer conversation. | Event AA wording mentions deep dive, advanced, or explicit PS follow-up. | The customer is reporting troubleshooting/bug/lag/negative feedback; use CS Follow Up. |
| REV Cross Sell | Event | `rev_cross_sell` / `120` | Revenue expansion or cross-sell opportunity. | Event AA wording mentions cross sell, upsell, expansion, PayrollAny, EngageAny, HRAny, or similar revenue opportunity. | The request is a billing/invoice/RevOps execution ask; create or reuse ROI as source of truth and only add a PCO tracker when PS needs customer-loop visibility. |
| Training | Onboarding | Not wired | Customer training or enablement session request visible in the PCO portal. Live PCO usage includes payroll and StaffAny training tasks. | A customer needs onboarding or enablement training tracked directly in Jira. | Event AA wording mentions re-training, webinar, or basic training; current bot routing maps those to Adhoc Ops unless Jira wiring changes. |

## Live Jira Validation Notes

The Atlassian connector can read Jira projects and issues, but it does not expose the JSM request-type admin endpoint directly. Validation therefore used JQL against live PCO issues, for example:

```jql
project = PCO AND "Request Type" = "<request type>" ORDER BY created DESC
```

Live reads confirmed:

| Request type | Live evidence from PCO JQL | Definition confidence |
| --- | --- | --- |
| Adhoc Ops | Recent issues include general feedback input, workshop invitations, service agreement follow-up, and training-style follow-up. | Observed as broad/general event or ops follow-up; definition should stay broad. |
| API Access Request | No visible issues returned for this request type. API access topics were seen under PS Follow Up and PDT Discovery instead. | Portal existence confirmed by screenshot only; usage not observed through JQL. |
| CS Follow Up | Recent issues include app-usage feedback, BI handover/checking, finding/restarting customer conversations, pricing read-back, and payroll follow-up. | Observed as customer-facing follow-up, not only bugs. Keep broader than pure support-defect follow-up. |
| Customer Success Work | Recent issues include payroll errors, formula changes, voucher or usage check-ins, attendance comparisons, and payroll checking. | Observed as the general non-AA customer-success work bucket. |
| Data Setup | Recent issues include payroll setup, org creation, past payroll import, onboarding participation, and import/setup work. | Observed as setup/import/data-readiness work, sometimes overlapping onboarding. |
| Event Ops | Recent issues include AA invitations, name tags, sponsorship outreach, and payment checks. | Observed as event logistics and event operations. |
| Feedback | Recent issues include payroll-page feedback, supplier/resource feedback, positive event feedback, and general non-user/customer feedback. | Observed as general feedback or unclear event notes. |
| MKT ClubAny Interest | One visible issue returned, a ClubAny follow-up. | Observed as ClubAny marketing-interest follow-up. |
| Onboarding | Recent issues include payroll setup, EngageAny training, onboarding tasks, and setup for newly onboarded customers. | Observed as broader customer rollout/setup work. |
| PDT Discovery | Recent issues include AI adoption discovery, feature requests, API workshop interest, and API/open-data topics. | Observed as product discovery and feature/API exploration. |
| Photo Follow Up | Recent issues are consistently `Photo follow up` records with `AA-SG-2026` labels. | Observed as the AA photo evidence tracker. |
| PS Follow Up | Recent issues include follow-up for other entities, API access follow-up, finding customer contacts, and PS-owned conversation follow-up. | Observed as PS-owned customer follow-up, including some API access follow-up. |
| REV Cross Sell | Recent issues include AI workshop follow-up, payroll cross-sell, migration/cross-sell, and payroll outsourcing link-up. | Observed as revenue expansion/cross-sell follow-up. |
| Training | Recent issues include StaffAny and payroll training. | Observed as active portal type even though the bot is not wired to create it directly. |

## Event AA Routing Summary

`create_ps_wee_intake_ticket` accepts these Event AA keys:

| Wording cue | Request type |
| --- | --- |
| `deep dive`, `advanced`, `PS follow up` | PS Follow Up |
| `troubleshooting`, `bug`, `lag`, `negative feedback`, `CS follow up` | CS Follow Up |
| `re-training`, `retraining`, `webinar`, `basic training`, `adhoc ops` | Adhoc Ops |
| `cross sell`, `upsell`, `expansion`, `PayrollAny`, `EngageAny`, `HRAny` | REV Cross Sell |
| `ATS`, `AI agents`, `PDT`, `discovery`, `feature`, `features` | PDT Discovery |
| `ClubAny`, `club any`, `MKT` | MKT ClubAny Interest |
| Anything else or unclear | Feedback |
| Initial AA trigger message includes image attachment | Photo Follow Up, in addition to per-bullet tickets |

## Jira Admin Snapshot

| Request type | Work type | Workflow | Portal group | Restrictions |
| --- | --- | --- | --- | --- |
| Adhoc Ops | Task | PCO: Jira Service Management default workflow | General | Locked |
| API Access Request | Task | PCO: Jira Service Management default workflow | General | Locked |
| CS Follow Up | Task | PCO: Jira Service Management default workflow | Used in 2 groups | Locked |
| Customer Success Work | Task | PCO: Jira Service Management default workflow | General | Locked |
| Data Setup | Task | PCO: Jira Service Management default workflow | Onboarding | Locked |
| Event Ops | Task | PCO: Jira Service Management default workflow | General | Locked |
| Feedback | Task | PCO: Jira Service Management default workflow | Event | Locked |
| MKT ClubAny Interest | Task | PCO: Jira Service Management default workflow | Event | Locked |
| Onboarding | Task | PCO: Jira Service Management default workflow | Onboarding | Locked |
| PDT Discovery | Task | PCO: Jira Service Management default workflow | Event | Locked |
| Photo Follow Up | Task | PCO: Jira Service Management default workflow | Event | Locked |
| PS Follow Up | Task | PCO: Jira Service Management default workflow | Used in 2 groups | Locked |
| REV Cross Sell | Task | PCO: Jira Service Management default workflow | Event | Locked |
| Training | Task | PCO: Jira Service Management default workflow | Onboarding | Locked |

## Source Trace

- Jira admin screenshot supplied in the Codex thread on 2026-05-29.
- PSM Ops app packet: `apps/psm-ops-bot/runtime/jira.md`.
- PSM Ops Jira field contract: `apps/psm-ops-bot/skills/psm-ops-bot/references/jira-field-contract.md`.
- PSM Ops Event AA workflow: `apps/psm-ops-bot/skills/psm-ops-bot/workflows/aa-intake.md`.
- Runtime constants: `apps/psm-ops-bot/runtime/mcp/psm_jira_server.py`.
