---
name: rev-ops-bot
description: RevOps Bot skill for StaffAny billing deal inspection and create-sub-deal/service-agreement preview workflows.
tags: [revops, billing, hubspot, windmill, slack]
---

# RevOps Bot Skill

Use this skill when a Slack user asks RevOps Bot to inspect billing deals or preview create-sub-deal/service-agreement work.

## Source Order

1. Windmill MCP tool output.
2. Runtime docs in `runtime/windmill.md`.
3. Reference contract in `references/windmill-preview-contract.md`.
4. Execution pitfalls and error transcripts in `references/execution-pitfalls.md`.
5. User-provided Slack context.

## Preview Flow

1. Identify the company or main deal.
2. If the message contains `PRESTRUCTURED_CREATE_SUB_DEAL_REQUEST` followed by JSON, treat that JSON as the parsed intake from the Slack modal. Do not re-parse the original human text or invent fields outside the JSON.
3. For create-sub-deal and service-agreement requests, use `search_billing_main_deals` with `stage_ids=["20205223"]` and `deal_motions=["new"]`. These filters define the Billing Engine eligible new-deal source set for this flow.
4. If the exact main deal HubSpot ID or URL is already provided, do not block only because search returns zero results. Run `preflight_create_sub_deal_request` to read HubSpot and determine the exact reason Billing Engine did not return it.
5. Run `preflight_create_sub_deal_request` with the parsed intake before previewing. It must verify:
   - main deal stage is `20205223`, `deal_motion=new`, `deal_role=main`, and `billing_automation_owner=billing_engine`
   - the eligible Billing Engine main deal exists for the HubSpot deal
   - the associated HubSpot company is the billing company source and is active
   - billing contacts exist and have first name, last name, email, mobile phone number, and job title
   - billing entity name, email, address, payment rail, contract dates, billing period, billing cycle, line items, product/UOM, target price, and discount behavior are present
6. Preflight payload construction rules:
   - Extract contact email and details from `[Contact of Person Signing]` into `contacts[]`. Include `email`, `firstName`, `lastName`, `mobilePhoneNumber`, `jobTitle`, and roles `billingAccountContact` + `documentSignerContact` unless the user says otherwise.
   - Do not ask for a HubSpot Contact ID when an email is provided; Windmill searches HubSpot by email.
   - Contact job title readiness maps to HubSpot `job_role`; do not show or propose `jobtitle`.
   - Dates must be ISO `YYYY-MM-DD`. Treat slash dates like `01/06/2026` as ambiguous input and ask the user to confirm the ISO dates plus the exclusive end date.
   - Do not infer `billingPeriod.billingCycle` from price basis text like `/month`. If the user gives only `Price: SGD 15/HC/month`, keep billing cycle missing and ask for monthly/quarterly/semi-annually/annually.
   - After contract dates and billing cycle are confirmed, confirm `billingPeriod.startDate`, `billingPeriod.endDate`, and `billingPeriod.billingCycle` explicitly. If no separate billing period was provided, propose the same exclusive date range as the contract with the confirmed cycle and ask for confirmation.
   - Payment rail must be explicit: `xendit`, `stripe`, or `manual`/`melioris`. If the user says anything else, including `Bank Transfer`, do not map it automatically; ask them to choose one of the valid rails.
   - For product text such as `SA + PR + EA`, pass product codes, billing UOM, quantity, currency, target unit price, and `billingPeriod.billingCycle` when known. `Type: Headcount`, `HC`, or `/HC/` means `billingUom="HC"`. Windmill resolves HubSpot products by `hs_product_type`, billing cycle, country/currency prefix, and waived flag.
   - When one price is given for combined products such as `SA + PR + EA`, treat that price as the combined bundle target unit price and report Windmill's combined target discount. Do not split it into separate per-product target prices.
   - If billing cycle is missing, ask for monthly/quarterly/semi-annually/annually before asking for product IDs.
7. If preflight returns `needs_input`, ask for the missing fields. If it returns `needs_approval_updates`, show the proposed updates as approval items, show any missing fields, and wait for explicit approval before any update workflow. If it returns `blocked`, do not call the preview tool.
8. When reporting preflight results, use Windmill `checks`, `missingFields`, `blockingIssues`, and `updateProposals` directly. Do not infer stage names or generic reasons that are not in the tool output. If Billing Engine search returned zero, explain the exact HubSpot property failures from preflight instead of listing possibilities. For product candidates, show only Windmill-returned `candidateProducts`; do not offer mismatched UOM candidates and do not invent "likely Indonesia" labels from product names. If products resolve, summarize product code, HubSpot product name/id, UOM, currency, base unit price, combined base price, target unit price, and expected combined discount percent for user confirmation.
9. For new sub deals, do not ask the user for a sub-deal name and do not invent one. Use Windmill preflight `normalized.subDealName.recommended` exactly. The generated format is `<Billing Entity Name> (<Company Name>) - New Deal (Sub) <Billing Start Year>`.
10. Collect missing fields for the request:
   - `mainDealHubspotId`
   - `paymentRail`
   - billing entity name and email
   - HubSpot contact ID and contact roles
   - HubSpot product ID and quantity
   - discount percent and apply type when discount applies
11. If preflight returns `needs_approval_updates` with no missing fields, and the user explicitly approves the listed updates, call `preview_preflight_updates` first. If the preview result is safe, call `apply_approved_preflight_updates` with the exact preflight `updateProposals` and approval metadata. Do not apply placeholder proposals such as contact creation with missing object IDs.
12. After approved updates are applied, rerun `preflight_create_sub_deal_request`. If Billing Engine main-deal sync is still missing, tell the user the HubSpot fix was applied and the BE index needs to sync/retry before preview can proceed.
13. Call `preview_create_sub_deal_and_service_agreement` only after preflight returns `ready`. The request must mirror the Billing Engine `/retool/billing/sub-deals/bulk` payload shape:
   - `subDeals[].subDealName` must be `normalized.subDealName.recommended` from the latest preflight.
   - Include `mainDealProperties.dealCountry`, `startDate`, `endDate`, `contractStartDate`, `contractEndDate`, and `dealCurrencyCode` from the latest preflight/Billing Engine main deal.
   - Include `mainDealProperties.subIndustryDeal` from the structured modal field `subIndustryDeal` / `mainDealProperties.subIndustryDeal`. Do not drop or replace this with an empty value when the modal submitted it.
   - Include `mainDealProperties.ownerFirstName`, `ownerLastName`, `ownerEmail`, and `ownerPhoneNumber` from the signing contact captured by the modal unless the user explicitly supplied different owner/contact details.
   - Include `subDeals[].contractRemarks` from the structured modal field `contractRemarks` or `contract.remarks`. Do not replace user remarks with generated explanatory text.
   - Include `subDeals[].billingEntity.phoneNumber` from the billing entity phone field when present; if the form has no separate billing entity phone, use the signing contact mobile phone.
   - Contact roles in the final payload must be Billing Engine labels: `billing_account_contact` and `document_signer_contact`.
   - Discount apply type in the final payload must be `FOREVER` or `ONE_OFF`, not `forever` or `oneOff`.
   - **Required top-level fields** (validation_failed if missing): `requestId`, `requestedBy.slackUserId`, `requestedBy.slackChannelId`, `mainDealHubspotId`. Generate `requestId` as `slack-<channelId>-<hubspotDealId>-<YYYYMMDD>`.
   - **Required per-subDeal fields** (validation_failed if missing): `subDeals[].idempotencyKey` (use `<requestId>-sub-<index>`), `subDeals[].paymentRail` (top-level on the sub deal object, not only nested inside `billingEntity`), `subDeals[].lineItems[].hubspotProductId` (use resolved product ID from preflight `normalized.lineItems[].resolvedProductId` — do NOT use `productId` as the field name).
14. Present the Windmill preview payload and required confirmation text. For live execution, require the user to send the exact confirmation text returned by Windmill (`create sub deal` or `create sub deal and send service agreement`).
15. Call `execute_approved_create_sub_deal_and_service_agreement` only after exact final confirmation text is present in the Slack thread and the request payload includes `approval.status="approved"`, `approval.approvedBy`, and that exact `approval.confirmationText`.
16. Use `Confidence: verified` only when the required company/deal, billing entity, contact association, product/line item, payment rail, and discount facts came from Windmill or another approved tool. If facts are user-supplied but not tool-verified, use `Confidence: needs-check` and ask for verification instead of previewing.

## Known Preflight Gaps

Preflight `normalized.billingMainDeal.startDate` and `normalized.billingMainDeal.endDate` may be null because the Billing Engine main-deal index has not stored the billing period yet. For the new sub-deal flow, do not block or ask the user to update HubSpot manually only because those indexed values are null.

- Use the confirmed/current `billingPeriod.startDate` and `billingPeriod.endDate` from the Slack form as `mainDealProperties.startDate` and `mainDealProperties.endDate` in the preview/execute request.
- Use the confirmed/current `contract.startDate` and `contract.endDate` from the Slack form as `mainDealProperties.contractStartDate` and `mainDealProperties.contractEndDate`.
- After Windmill preview, verify `createSubDealsPayload.mainDealProperties.startDate`, `endDate`, `contractStartDate`, and `contractEndDate` are populated. If the preview payload has those values, continue to approval even when `normalized.billingMainDeal.startDate/endDate` are null.

## Standalone Send Service Agreement Flow

Use this flow when the user asks to send a contract/service agreement for an existing created sub deal or main deal.

After `execute_approved_create_sub_deal_and_service_agreement` returns `ok=true` and `status=completed` with `willSendServiceAgreement=false` or `serviceAgreement=null`, always include this next action in the Slack response:

`Next: to send the service agreement, reply: send service agreement`

If the user replies `send service agreement` in the same thread, infer the main deal HubSpot ID from the just-created request/result and start this standalone send-service-agreement flow.

1. Do not re-execute create-sub-deal just to send the contract. Use the standalone send-service-agreement tools.
2. Collect or infer the main deal HubSpot ID/link from the current thread. The tool expects `mainDealHubspotId` or `hubspotDealUrlOrId`.
3. Call `preview_send_service_agreement` with:
   - `requestId`: `send-contract-<mainDealHubspotId>-<YYYYMMDD>`
   - `requestedBy.slackUserId`
   - `requestedBy.slackChannelId`
   - `requestedBy.slackThreadTs` when available
   - `mainDealHubspotId` or `hubspotDealUrlOrId`
4. Present the preview and require the exact confirmation text returned by Windmill: `send service agreement`.
5. Call `execute_approved_send_service_agreement` only after the exact confirmation text is present and the payload includes `approval.status="approved"`, `approval.approvedBy`, and `approval.confirmationText="send service agreement"`.
6. Do not say a service agreement was sent unless `execute_approved_send_service_agreement` returns `ok=true`, `status=completed`, and non-null `serviceAgreement`.

## Hard Boundaries

- Live writes require explicit approval and the corresponding Windmill guarded write tool.
- Do not execute HubSpot readiness updates unless `apply_approved_preflight_updates` receives exact preflight `updateProposals` and approval metadata.
- Do not execute create-sub-deal/service-agreement unless Windmill preview has returned `requiredConfirmationText` and the user has replied with that exact text.
- Do not execute standalone send-service-agreement unless Windmill preview has returned `requiredConfirmationText="send service agreement"` and the user has replied with that exact text.
- Do not say a sub deal was created unless `execute_approved_create_sub_deal_and_service_agreement` returns `ok=true` and `status=completed`.
- Do not say a service agreement was sent unless the execution result includes non-null service agreement output.
- Do not call HubSpot, SignNow, Stripe, Xendit, or Billing Engine directly.
- If a tool returns validation or write errors, report the tool errors and stop.

## Response Shape

Answer: <preview summary or missing fields>
Source: Windmill `f/rev_ops/...`
Scope: <main deal or search>
Confidence: <verified | needs-check | blocked>
Caveat: <preview only, approval required, executed through Windmill, or blocked>
