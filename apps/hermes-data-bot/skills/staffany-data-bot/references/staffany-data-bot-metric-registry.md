# StaffAny Data Bot Metric Registry

Use this file before answering known Da Ta Bot POC metrics. This registry is a contract of metric status, not proof that every definition is production-ready.

## Confidence Rules

- Use `confidence: verified` only when the metric definition is confirmed by a source/dashboard owner and the query succeeds.
- Use `confidence: needs-check` when the query uses candidate logic, inferred source fields, unvalidated dashboard parity, or a table that still needs owner confirmation.
- Use `confidence: blocked` when BigQuery auth/tooling fails, required Slack context is unreadable, or the source tables needed to answer cannot be inspected.
- Always state source table(s), filters/time window, and caveat.
- Hide SQL unless the user asks for it.

## Metric: THR Pay Run Usage

- Common questions:
  - How many customers are using THR pay run?
  - Which organizations have THR pay runs?
- Product terminology:
  - Treat THR pay run as a pay run type question.
  - Do not infer THR pay run usage from THR pay item names or `Tunjangan Hari Raya` pay item labels.
- Status: corrected POC definition, source-field still needs schema verification.
- Confidence to return: `needs-check` until the pay run type field and customer exclusion logic are owner-verified.
- Candidate source path:
  - Start with `staffany-warehouse.analytics.stg_kraken__payruns` or a better payroll mart if schema inspection exposes one.
  - Join organization/customer dimensions only after identifying the actual pay run type field and accepted status values.
- Important rule:
  - Inspect pay run schema for type-like fields and discover actual values before filtering for THR.
  - If `periodtype` does not contain THR, do not conclude that no THR pay run type exists; inspect other pay run type columns or return `blocked` if no source field can be identified.
  - Do not substitute pay item name matching for pay run type matching.
- Required discovery:
  - Inspect schema first.
  - Discover actual pay run type values before applying the THR filter.
  - Discover successful/completed pay run status values before counting usage.
  - Apply explicit customer/non-customer exclusion logic and state it.
- Default caveat:
  - "THR pay run source field and customer exclusion logic are not owner-verified; pay item names were not used as the pay run type definition."

## Metric: Active New Joiner Form Usage

- Common questions:
  - Which StaffAny organizations have active new joiner forms?
  - How many organizations are using new joiner forms?
- Product terminology:
  - Treat "new joiner form" as the HRAny Onboarding feature in user-facing interpretation and final wording.
  - Pantheon product copy says HRAny covers Onboarding, and new joiner forms are part of the onboarding flow.
  - Warehouse/source tables may still use Kraken NewJoiner or FormBuilder names; do not expose that as a separate product unless needed for source transparency.
- Status: candidate, not owner-verified.
- Confidence to return: `needs-check` until confirmed by product/dashboard owner.
- Candidate source path:
  - Prefer an analytics mart or modeled table if one exists in `staffany-warehouse.analytics`.
  - If no mart exists, inspect warehouse tables that expose Kraken new joiner form data.
  - Pantheon implementation evidence references New Joiner form entities such as `NewJoinerForms`, `NewJoinerFormFields`, `NewJoinerEntries`, and `NewJoinerDocumentUploads`, plus FormBuilder entities for custom onboarding fields; do not assume these exact source names exist in analytics.
- Required discovery:
  - Inspect schemas first.
  - Discover actual status/enabled/published/deleted columns before filtering.
  - Confirm whether "active" means enabled, published, has at least one active form, has recent entries, or matches a dashboard filter.
- Default caveat:
  - "Definition of active new joiner form is not owner-verified; treating this as candidate usage."

## Metric: PPH On Us

- Common questions:
  - Which Indonesia payroll accounts have PPH on us?
  - How many ID payroll organizations use PPH on us?
- Status: candidate, not owner-verified.
- Confidence to return: `needs-check` until Abel or another payroll metric owner confirms the definition.
- Candidate source path:
  - Start with `staffany-warehouse.analytics.fct_payroll_report` for generated payroll evidence.
  - Relevant candidate fields include `id_pph21_method`, `id_pph21_allowance`, `id_pph21_deduction`, `id_taxable_income`, and payroll run fields after schema inspection.
- Important rule:
  - Do not define PPH on us as `id_pph21_method = NETTO`.
  - `id_pph21_method = NETTO` is only a candidate signal and may be wrong on its own.
  - Prefer actual generated payroll behavior and broader PPH setup logic once confirmed by Abel/metric owner.
- Required discovery:
  - Inspect schema and latest available payroll periods.
  - Check whether the question asks for configured accounts, payrolls already generated, or organizations with any historical payroll using candidate PPH-on-us signals.
  - If using candidate logic, explain which generated payroll fields were used.
- Default caveat:
  - "PPH-on-us definition is not owner-verified; `id_pph21_method = NETTO` alone is not treated as definitive."

## Metric: IR8A Submitted

- Common questions:
  - Which organizations submitted IR8A?
  - How many IR8A submissions were completed for a tax year?
- Status: candidate, not owner-verified.
- Confidence to return: `needs-check` until confirmed against source/dashboard owner.
- Candidate source path:
  - Prefer an analytics mart or modeled table if one exists.
  - If no mart exists, inspect warehouse tables for IR8A submission data.
  - Pantheon implementation evidence references IR8A submission entities with organization, business entity, year, status, and submitted timestamp fields; do not assume exact analytics table or column names without schema inspection.
- Required discovery:
  - Inspect schema for status values.
  - Discover submitted/completed status values before filtering.
  - Ask for tax year if absent and materially affects the answer.
- Default caveat:
  - "IR8A submitted status mapping is not owner-verified; treating discovered submitted/completed statuses as candidate logic."

## Metric: Red Accounts

- Common questions:
  - List red accounts.
  - Which customer accounts are red?
- Status: candidate, not owner-verified.
- Confidence to return: `needs-check` until confirmed by RevOps/CS/dashboard owner.
- Candidate source path:
  - Start with revenue/customer usage marts such as `staffany-warehouse.analytics.fct_company_org_mrr` and related company/org dimensions after schema inspection.
  - Candidate fields include `company_usage_status`, `company_usage_next_step`, and `company_low_usage_reason` if present.
- Required discovery:
  - Discover actual status/category values before filtering for "red".
  - Confirm whether "red" means health status, usage status, renewal risk, CS risk, or dashboard color.
  - Return organization/company display names rather than raw IDs where possible.
- Default caveat:
  - "Red-account definition is not owner-verified; using discovered customer usage status values as candidate logic."

## Metric: Fitness Customers

- Common questions:
  - List fitness customers.
  - Which StaffAny customers are in the fitness segment?
- Status: candidate, not owner-verified.
- Confidence to return: `needs-check` until confirmed by RevOps/CS/dashboard owner.
- Candidate source path:
  - Start with company/org revenue and usage marts such as `dim_companies`, `fct_company_org_mrr`, or linked-org revenue marts after schema inspection.
  - Candidate fields include `company_industry`, `company_industry_staffany`, `industry_group`, or equivalent industry/segment fields if present.
- Required discovery:
  - Discover actual industry/segment values before filtering.
  - Match only discovered values that clearly represent fitness, gym, wellness, sports, or closely related segments.
  - Explain included value mappings if the match is fuzzy.
- Default caveat:
  - "Fitness customer segment is not owner-verified; using discovered industry/segment values as candidate logic."

## Metric: ATS Applicant Leaderboard

- Metric key: `ats_applicant_leaderboard`
- Common questions:
  - Which F&B organizations are the top ATS users by number of applicants?
  - How many applicants or job openings does an organization have in ATS?
  - Pull ATS JDs or safe job-opening context for an organization.
- Product terminology:
  - Treat ATS applicants as hiring applications in StaffAny ATS/HireAny.
  - A job opening is the StaffAny ATS `JobOpening` record.
  - Candidate resumes, candidate names, phone numbers, emails, CV URLs, and raw application answers are PII and must not be surfaced in casual Slack answers.
- Status: candidate, not owner-verified.
- Confidence to return: `needs-check` until a product/data owner verifies the ATS leaderboard definition and F&B source mapping.
- Candidate source path:
  - Applicant facts: `staffany-warehouse.kraken_rds.JobApplication`.
  - Job-opening facts: `staffany-warehouse.kraken_rds.JobOpening`.
  - Organization display and selected org filtering: `staffany-warehouse.analytics.dim_organisations` and `staffany-warehouse.analytics.dim_org_company` after schema inspection.
  - F&B filtering: HubSpot/company fields such as `stg_hubspot__companies.company_industry_staffAny`, `dim_companies.company_industry_staffany`, `dim_companies.company_industry`, or `dim_companies.industry_group` after discovering actual values.
- Required grain rule:
  - Aggregate ATS measures at `organisationid` first.
  - Applicant count is `COUNT(DISTINCT JobApplication.id)`.
  - Job-opening count is `COUNT(DISTINCT JobOpening.id)`, joined or aggregated by `JobOpening.organisationid`.
  - Build industry/company filters as a deduped org set before joining to org-grain ATS facts.
  - Do not sum org-level applicant/opening counts after joining raw `dim_org_company`, `stg_hubspot__companies`, or other company bridge rows.
- Fan-out guard:
  - Before answering a company/industry-scoped leaderboard, check whether bridge rows exceed distinct org IDs.
  - If a bridge fans out, dedupe to one row per org before returning counts and include the fan-out caveat.
  - Stripes Australia sanity check: org `-LgO1Np3HFBryRmdDrXQ` must not be reported as 2,048 applicants across 64 openings from the F&B leaderboard path. The reviewed sanity result is 32 applicants across 1 job opening.
- Safe JD / PII handling:
  - A scoped JD pull from `JobOpening.name` / `JobOpening.description` is allowed when it does not expose candidate PII.
  - Candidate resumes, candidate details, `JobApplication.email`, `phonenumber`, `cvurl`, names, and raw `questionsandanswers` are blocked unless an approved PII workflow exists outside this bot.
  - If a request combines JD plus resumes/application details, execute the safe JD slice when scope is clear and block only the candidate PII slice.
- Default caveat:
  - "ATS leaderboard definition and F&B tagging are not owner-verified; ATS measures were aggregated at organisation grain first and company/industry bridge fan-out was deduped."

## Metric: Club Blue Redemption Usage

- Metric key: `club_blue_redemption_usage`
- Release-feature mapping status: track with a current proxy source.
- Common questions:
  - How many organizations are using Club Blue?
  - How many Club Blue perks have been redeemed?
  - Which organizations have Club Blue redemption activity?
- Product terminology:
  - Treat Club Blue / ClubAny as the Pixie employee perks catalog and redemption flow.
  - Pantheon implementation evidence references Club Blue brands, perks, and redemptions.
- Status: candidate current-source mapping; not owner-verified as a dedicated Club Blue source.
- Confidence to return: `needs-check`.
- Candidate source path:
  - Current source: `staffany-warehouse.kraken_prod.engagement_reward_redemption`.
  - Filter to `event_text = 'Engagement Reward Redemption'` or `event = 'engagement_reward_redemption'`.
  - Use `_PARTITIONTIME` as the bounded scan filter and `timestamp` or `original_timestamp` as the event time.
  - Count `COUNT(*)` as redemption events, `COUNT(DISTINCT organisation_id)` as organizations with redemption activity, and `COUNT(DISTINCT user_id)` as users with redemption activity.
  - Preferred durable source remains a modeled analytics table for Club Blue redemptions, or a raw Kraken table equivalent to `ClubBlueRedemptions` with `organisationId`, `userId`, `perkId`, `status`, and `redeemedAt`.
- Evidence from mapping review:
  - Pantheon code has `ClubBlueBrands`, `ClubBluePerks`, and `ClubBlueRedemptions` models, plus `/club-blue/catalog/perks/{id}/redeem`.
  - BigQuery table-name scan across `staffany-warehouse` found no `club_blue`, `clubblue`, `club_any`, or `clubany` table names.
  - Bounded checks of `pixie_segment.screen`, `pixie_segment.track`, and `kraken_prod.tracks` did not expose a reviewed Club Blue usage event.
  - Current-source sanity check on 2026-05-11: the last 180 days in `kraken_prod.engagement_reward_redemption` returned 1,629 redemption events, 11 organizations, and 354 users.
  - Current-source weekly sanity check on 2026-05-11: 2026-05-04 to 2026-05-10 returned 25 redemption events, 3 organizations, and 13 users.
- Required discovery before changing confidence to `verified`:
  - Confirm with the product or data owner that `engagement_reward_redemption` is the intended v1 proxy for Club Blue / ClubAny redemption usage.
  - Confirm whether `reward_id` needs to be filtered to a Club Blue reward subset once reward metadata is queryable.
  - Confirm whether the adoption grain should be organizations, unique users, redemptions, or active perks.
- Default caveat:
  - "Using current Engagement Reward Redemption events as a Club Blue usage proxy; this is not a dedicated Club Blue source and needs owner confirmation."

## Metric: Gryphon Avatar Size Standardization Usage

- Metric key: `gryphon_avatar_size_standardization_usage`
- Release-feature mapping status: blocked.
- Common questions:
  - How much is the standardized Gryphon avatar size feature being used?
  - Which customers adopted standardized Gryphon avatars?
- Product terminology:
  - Treat this as a Gryphon design-system and UI consistency change, not a customer workflow feature.
  - Do not treat generic page views of avatar-bearing screens as adoption of the avatar-size standardization itself.
- Status: blocked because there is no safe usage/adoption metric.
- Confidence to return: `blocked`.
- Candidate source path:
  - None for usage actuals.
  - Code/design evidence can show where the Avatar component is used, but it does not measure customer adoption.
- Evidence from mapping review:
  - Pantheon Gryphon code defines Avatar sizes and guidance under `apps/gryphon/src/common/design-any/Avatar/`.
  - Gryphon Segment events are page/action oriented; no dedicated avatar-size standardization event was found.
  - Querying broad Gryphon Segment history for `avatar` is not a safe digest metric and can be expensive.
- Required discovery before changing to `track`:
  - Product or design owner must define a user-facing adoption metric, or engineering must add explicit instrumentation for avatar standardization exposure/interaction.
  - The metric must be queryable via `staffany_bigquery` with a bounded source table.
- Default caveat:
  - "Avatar size standardization has no reviewed usage metric; generic page views are not a valid adoption proxy."
