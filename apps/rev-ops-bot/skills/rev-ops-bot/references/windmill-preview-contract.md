# Windmill Approval-Gated Contract

Hermes calls Windmill, not Kraken Billing Engine directly.

## Search Tool

Windmill script:

```text
f/rev_ops/search_billing_main_deals
```

Arguments:

```json
{
  "search": "company or deal text",
  "stage_ids": [],
  "deal_motions": [],
  "limit": 20,
  "offset": 0
}
```

For create-sub-deal and service-agreement preparation, Hermes must search eligible new main deals with:

```json
{
  "stage_ids": ["20205223"],
  "deal_motions": ["new"]
}
```

If a user provides the main deal HubSpot ID or URL, Hermes must still search
that ID with these filters, but must not stop only because the search returns
zero results. It must run preflight to read HubSpot and report the exact failed
properties (`dealstage`, `deal_motion`, `deal_role`, `billing_automation_owner`)
or the exact missing data.

Do not apply these filters to unrelated broad deal-count or company-history questions unless the user asks for eligible new deals.

## Preflight Tool

Windmill script:

```text
f/rev_ops/preflight_create_sub_deal_request
```

Hermes MCP sends:

```json
{
  "request": {
    "hubspotDealUrlOrId": "316899066558",
    "contacts": [],
    "billingEntity": {},
    "contract": {},
    "billingPeriod": {},
    "lineItems": []
  }
}
```

Run this before the preview tool. Only continue to preview when `status` is
`ready`. For `needs_input`, ask for `missingFields`. For
`needs_approval_updates`, show `updateProposals` and wait for explicit approval
before any update workflow. For `blocked`, do not preview.

Preflight resolves HubSpot contacts by email. Hermes should pass contact
details from Slack into `contacts[]` and should not ask for a HubSpot Contact ID
when an email is present.

Contact job title readiness uses HubSpot `job_role`.

Contract and billing period dates must be ISO `YYYY-MM-DD`; end dates are
exclusive. Slash dates such as `01/06/2026` must be treated as ambiguous and
sent back for confirmation rather than silently converted.

Price basis text such as `/month` is not the same as
`billingPeriod.billingCycle`. If billing cycle is missing, ask for it before
resolving products.

If the contract dates and billing cycle are known but no separate billing
period is provided, Hermes should propose using the same exclusive date range as
the contract and ask for confirmation before previewing. Example:
`billingPeriod: 2026-06-01 -> 2027-06-01, annually`.

Payment rail must be explicit before preview. Valid values are `xendit`,
`stripe`, or `manual`/`melioris`. If the user says anything else, including
`Bank Transfer`, Hermes must ask them to choose one of the valid rails instead
of mapping it automatically.

Preflight resolves product codes such as `SA`, `PR`, `EA`, `claims`, `HRAny`,
and `Disbursement` by HubSpot product type. It also filters by billing UOM,
currency/country prefix, billing cycle, and waived flag. If billing cycle is
missing, ask for billing cycle before asking for exact product IDs.

For headcount/HC requests, Hermes must pass `billingUom="HC"` and must not show
SECTION candidates. Product candidates shown to users must come from Windmill
`normalized.lineItems[].candidateProducts` only.

When one price is supplied for a combined product bundle such as `SA + PR + EA`,
the price is a combined target unit price. Use Windmill's combined target
discount check instead of calculating separate per-product target discounts.
When products resolve, present the product IDs/names and combined discount math
for user confirmation before previewing.

The preview tool validates payload shape only. Do not treat user-supplied billing entity, contact, product, payment rail, or discount facts as verified unless they were returned by Windmill preflight or another approved read-only source.

## Preview And Execution Tools

Windmill script:

```text
f/rev_ops/create_sub_deal_and_service_agreement
```

Hermes MCP always sends:

```json
{
  "dry_run": true,
  "request": {}
}
```

The response is a preview. It does not create sub deals or send service
agreements, and it must return the required confirmation text before Hermes can
execute.

For approved execution, Hermes may call the matching execution tool only after
the Slack thread contains the exact confirmation text returned by preview:

```json
{
  "dry_run": false,
  "request": {
    "approval": {
      "status": "approved",
      "approvedBy": "U123",
      "confirmationText": "create sub deal"
    }
  }
}
```

Standalone service-agreement sending uses `f/rev_ops/send_service_agreement`.
It follows the same preview-then-exact-confirmation pattern, with required
confirmation text `send service agreement`.

HubSpot readiness updates use `f/rev_ops/apply_preflight_updates`. The update
payload must contain exact `updateProposals` returned by preflight plus approval
metadata. Do not apply placeholder proposals with missing object IDs.

## Required Request Fields

- `requestId`
- `requestedBy.slackUserId`
- `requestedBy.slackChannelId`
- `mainDealHubspotId`
- at least one `subDeals[]` item

Each sub deal needs:

- `idempotencyKey`
- `subDealName`
- `paymentRail`
- `billingEntity.name`
- `billingEntity.email`
- at least one contact
- at least one line item
