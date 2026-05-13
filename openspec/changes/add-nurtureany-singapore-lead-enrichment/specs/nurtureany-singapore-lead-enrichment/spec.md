# Specification: NurtureAny Singapore Lead Enrichment

## ADDED Requirements

### Requirement: SG Lead Enrichment Orchestrator

The system SHALL provide a read-only HubSpot MCP tool named `build_singapore_lead_enrichment_plan`.

#### Scenario: Default SG target-account pool

- GIVEN a scoped caller with Singapore access
- WHEN the caller omits `company_ids`
- THEN the tool SHALL search HubSpot companies where `company_country=Singapore` and `hs_is_target_account=true`
- AND SHALL optionally narrow the pool by `owner_email`
- AND SHALL return an account-level enrichment plan without mutating HubSpot.

#### Scenario: Explicit SG HubSpot companies

- GIVEN a scoped caller with Singapore access
- WHEN the caller supplies `company_ids`
- THEN the tool SHALL allow scoped Singapore HubSpot companies even when `hs_is_target_account` is not true
- AND SHALL exclude non-Singapore or outside-owner-scope companies with explicit skip reasons.

### Requirement: Stakeholder Coverage

The system SHALL evaluate stakeholder readiness per account.

#### Scenario: Verified decision maker

- GIVEN an associated contact with `hs_buying_role=DECISION_MAKER`
- WHEN the tool evaluates the account
- THEN the decision-maker slot SHALL count as verified.

#### Scenario: Title-only candidate

- GIVEN an associated contact whose title suggests owner/founder/director/CEO/GM but `hs_buying_role` is not `DECISION_MAKER`
- WHEN the tool evaluates the account
- THEN the contact SHALL be returned as a needs-check candidate
- AND SHALL NOT count as a verified decision maker.

#### Scenario: Champion or influencer

- GIVEN associated contacts with HR, Ops, Area, Outlet, Finance, Payroll, or Admin manager/director titles or `CHAMPION` / `INFLUENCER` buying roles
- WHEN the tool evaluates the account
- THEN it SHALL return the best `champion_influencer` / `operating_contact` slot where possible.

### Requirement: Phone Verification

The system SHALL recognize NurtureAny phone-verification fields and redact raw phone numbers from Slack-facing output.

#### Scenario: Fresh verified phone

- GIVEN a contact with `nurtureany_phone_verification_status=called_connected`
- WHEN the verification date is within `phone_stale_after_days`
- THEN the account SHALL count that contact as verified-phone coverage.

#### Scenario: Stale or missing phone verification

- GIVEN associated contacts with missing, stale, or non-connected phone verification statuses
- WHEN the tool evaluates the account
- THEN the account SHALL appear in a phone gap bucket
- AND SHALL return a writeback preview for the phone-verification fields.

#### Scenario: Manual Truecaller evidence

- GIVEN a contact with `nurtureany_phone_verification_source=truecaller_manual_lookup`
- AND the contact does not have `nurtureany_phone_verification_status=called_connected`
- WHEN the tool evaluates the account
- THEN the contact SHALL remain needs-check
- AND the account SHALL be eligible for `needs_manual_truecaller_check`.

### Requirement: HubSpot Field Diagnostics

The system SHALL return exact field-level mismatch reasons.

#### Scenario: Decision-maker rollup mismatch

- GIVEN `hs_num_decision_makers > 0`
- AND no returned associated contact has `hs_buying_role=DECISION_MAKER`
- WHEN the tool evaluates the account
- THEN the account SHALL be bucketed under `hubspot_rollup_mismatch`
- AND SHALL explain the field-level reason.

#### Scenario: Buying-role rollup mismatch

- GIVEN `hs_num_contacts_with_buying_roles > 0`
- AND no returned associated contact has `hs_buying_role=DECISION_MAKER`
- WHEN the tool evaluates the account
- THEN the account SHALL flag likely persona/buying-role mismatch
- AND SHALL tell the rep whether to fix HubSpot or keep prospecting.

### Requirement: WhatsApp Readiness

The system SHALL return WhatsApp readiness as draft-only talking points.

#### Scenario: Ready batch

- GIVEN accounts with associated contact, verified decision maker, and verified phone coverage
- WHEN the tool builds `ready_for_whatsapp_batch`
- THEN it SHALL select up to `batch_size` accounts
- AND SHALL return KNS-safe talking points using `Knowledge / Network / Support`
- AND SHALL NOT send WhatsApp/Eazybe messages.

### Requirement: Paid Provider Guardrails

The system SHALL preserve paid-tool and provider guardrails.

#### Scenario: Paid reveal needed

- GIVEN an account that needs a callable number from paid enrichment
- WHEN the tool recommends Lusha or Prospeo as a paid-provider step
- THEN it SHALL return only a `needs_paid_reveal` signal or writeback preview
- AND SHALL NOT call reveal or expose raw phone numbers.

#### Scenario: Clay, Apollo, Prospeo, or Truecaller automation

- GIVEN a provider without an approved API contract and approval gate in repo
- WHEN the tool builds the enrichment plan
- THEN it SHALL treat the provider as a manual/future source only.

### Requirement: Cost-Effective Provider Waterfall

The system SHALL optimize for capped effectiveness and return provider-waterfall guidance.

#### Scenario: Tavily before Exa for contact discovery

- GIVEN a scoped Singapore account with no associated contact coverage
- WHEN the tool builds the enrichment plan
- THEN the recommended next source SHALL be `tavily_public_company_job_board_research`
- AND the provider policy SHALL NOT allow a paid provider step yet.

#### Scenario: Exa for people candidate discovery

- GIVEN a scoped Singapore account with associated contact context but no verified decision maker
- WHEN the tool builds the enrichment plan
- THEN the recommended next source SHALL be `exa_people_candidate_discovery`
- AND Exa output SHALL remain candidate evidence only.

#### Scenario: Lusha and Prospeo controlled parallel pilot

- GIVEN a scoped Singapore account with a verified decision-maker path but missing verified/callable phone coverage
- AND no stale or candidate phone exists for manual callability check
- WHEN the tool builds the enrichment plan
- THEN the recommended next source SHALL be `lusha_prospeo_parallel_search_pilot`
- AND paid parallel provider policy SHALL list Lusha and Prospeo as controlled pilot candidates
- AND reveal SHALL still require explicit approval, cost/credit reporting, selected contacts, and raw-phone redaction.

#### Scenario: Ready account stops paid provider work

- GIVEN a scoped Singapore account with minimum readiness met
- WHEN the tool builds the enrichment plan
- THEN the recommended next source SHALL be `whatsapp_batch_draft`
- AND paid provider work SHALL be marked unnecessary.

#### Scenario: Provider candidates do not verify fields

- GIVEN a contact candidate from Prospeo, Lusha, Exa, or any other enrichment provider
- WHEN HubSpot/call verification fields do not prove the decision-maker role or connected phone outcome
- THEN the provider result SHALL NOT count as verified decision-maker coverage or verified-phone coverage.
