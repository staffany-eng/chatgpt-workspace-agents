# Spec: PSM Ops Churn Reporting

## ADDED Requirements

### Requirement: Bot-Owned Weekly Churn Chase

The PSM Ops Bot SHALL run the weekly churn reporting chase from the existing `psmopsbot` Hermes profile.

#### Scenario: Weekly cron is installed

- GIVEN the cloud profile is deployed
- WHEN Hermes cron metadata is inspected
- THEN a no-agent cron named `psmopsbot churn reporting chase` SHALL exist
- AND it SHALL run at `0 1 * * 1`
- AND it SHALL deliver to `slack:#team-rev-account-management`.

### Requirement: BigQuery Source Of Truth

The churn chase SHALL read renewal/churn reporting data from BigQuery directly.

#### Scenario: Core Meeting sheet is not read

- GIVEN the churn chase script runs
- WHEN it builds source data
- THEN it SHALL NOT call Google Sheets APIs
- AND it SHALL NOT reference the Core Meeting spreadsheet ID
- AND it SHALL use repo-owned Dashboard 292 SQL plus `staffany-warehouse.analytics.fct_upcoming_renewal_cycles`.

### Requirement: Dashboard 292 Churn Risk Chase

The churn chase SHALL use the repo-owned Dashboard 292 SQL for churn-risk classification.

#### Scenario: Actualized churn row is missing company churn fields

- GIVEN a Dashboard 292 row has `churn_class = '1-Actualized'`
- AND `company_churn_reason` or `company_churn_reason_bucket` is blank, unknown, or generic
- WHEN the weekly chase is formatted
- THEN the row SHALL be included
- AND the output SHALL ask for the missing company churn reason fields.

#### Scenario: Non-actualized churn row is missing renewal assessment fields

- GIVEN a Dashboard 292 row has a non-null `churn_class` other than `1-Actualized`
- AND `renewal_assessment` or `renewal_assessment_reason` is blank, unknown, or generic
- WHEN the weekly chase is formatted
- THEN the row SHALL be included
- AND the output SHALL ask for the missing renewal assessment fields.

#### Scenario: Dashboard row has no churn class

- GIVEN a Dashboard 292 source row has `churn_class IS NULL`
- WHEN the weekly chase is formatted
- THEN the row SHALL NOT be included in the Dashboard 292 chase section.

### Requirement: Upcoming Renewal Exception Chase

The churn chase SHALL use upcoming renewal cycles only as a risky/overdue exception safety net.

#### Scenario: Risky upcoming renewal is not in Dashboard 292

- GIVEN an upcoming renewal row is inside the reporting window
- AND its status, bucket, billing status, or stage indicates overdue, unpaid, delinquent, late payment, not started, no renewal deal yet, or at risk
- AND its canonical company ID and raw company ID do not match a Dashboard 292 row with non-null `churn_class`
- WHEN the weekly chase is formatted
- THEN the row SHALL be included in the Upcoming renewal exceptions section.

#### Scenario: Upcoming renewal is already in Dashboard 292

- GIVEN an upcoming renewal row matches a Dashboard 292 company by canonical company ID or raw company ID
- WHEN the weekly chase is formatted
- THEN it SHALL be suppressed from the Upcoming renewal exceptions section.

### Requirement: Rolling Quarter Window

The churn chase SHALL report current quarter plus the next two quarters.

#### Scenario: Run date is 2026-05-25

- GIVEN the run date is `2026-05-25` in `Asia/Singapore`
- WHEN the script computes the reporting window
- THEN it SHALL include `26Q2`, `26Q3`, and `26Q4`
- AND it SHALL exclude `27Q1`.

### Requirement: Owner-Based Chase Output

The churn chase SHALL group action items by quarter and renewal owner.

#### Scenario: Owner is missing

- GIVEN an included Dashboard 292 or upcoming exception row has no `deal_psm_name`
- WHEN the row needs chase
- THEN it SHALL be grouped under `Owner missing`
- AND the output SHALL ask account management to confirm the owner.

### Requirement: Slack Automation Identity

The churn chase SHALL produce Slack-safe automation output.

#### Scenario: Chase rows exist

- GIVEN one or more rows need cleanup
- WHEN the script formats output
- THEN the first visible line SHALL start with `PSM Ops automation:`
- AND the message SHALL ask for renewal status, churn reason/category, evidence link, and source-field update confirmation.

### Requirement: Dry Run

The churn chase SHALL support a dry-run mode.

#### Scenario: Dry-run is requested

- GIVEN `--dry-run` is passed
- WHEN the script formats output
- THEN the output SHALL include a dry-run marker
- AND no Slack API, Jira API, or BigQuery mutation SHALL be attempted.
