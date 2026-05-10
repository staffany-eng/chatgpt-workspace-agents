-- NurtureAny known-area near-me outlet memory table.
--
-- This is a provisioning/migration script for a BigQuery admin or deployment
-- job. Do not run through staffany_bigquery.execute_sql_readonly.
--
-- Default runtime table:
--   staffany-warehouse.analytics.nurtureany_near_me_outlet_matches

CREATE TABLE IF NOT EXISTS `staffany-warehouse.analytics.nurtureany_near_me_outlet_matches` (
  outlet_match_id STRING NOT NULL OPTIONS(description = "Stable generated ID for this outlet match row."),
  area_id STRING NOT NULL OPTIONS(description = "Known area ID, for example sg_raffles_place."),
  area_name STRING OPTIONS(description = "Known area display name."),
  outlet_name STRING NOT NULL OPTIONS(description = "Human-readable outlet or branch name."),
  google_place_id STRING OPTIONS(description = "Google Places place ID used as primary map dedupe key."),
  formatted_address STRING OPTIONS(description = "Google or reviewed outlet address."),
  latitude FLOAT64 OPTIONS(description = "Outlet latitude when known."),
  longitude FLOAT64 OPTIONS(description = "Outlet longitude when known."),
  google_maps_uri STRING OPTIONS(description = "Google Maps URI from Places API when available."),
  hubspot_company_id STRING OPTIONS(description = "Associated HubSpot Company ID when matched."),
  hubspot_company_name STRING OPTIONS(description = "Snapshot display name for quick Slack output; HubSpot remains CRM truth."),
  hubspot_owner_id STRING OPTIONS(description = "Snapshot owner ID for quick Slack output; refresh from HubSpot/C360 as needed."),
  organisation_id STRING OPTIONS(description = "StaffAny organisation_id for C360 joins when known."),
  account_status STRING NOT NULL OPTIONS(description = "customer, prospect, or unknown."),
  match_status STRING NOT NULL OPTIONS(description = "confirmed, candidate, or rejected."),
  confidence STRING NOT NULL OPTIONS(description = "verified, needs-check, or blocked."),
  source STRING NOT NULL OPTIONS(description = "manual, google_places, import, or workflow."),
  source_note STRING OPTIONS(description = "Short review note; no raw Slack transcript or unnecessary PII."),
  last_checked_at TIMESTAMP OPTIONS(description = "Last review or live refresh timestamp."),
  reviewed_by STRING OPTIONS(description = "Reviewer email or system actor, if manually reviewed."),
  created_at TIMESTAMP NOT NULL OPTIONS(description = "Row creation timestamp."),
  updated_at TIMESTAMP NOT NULL OPTIONS(description = "Row update timestamp.")
)
CLUSTER BY area_id, google_place_id, hubspot_company_id, organisation_id
OPTIONS (
  description = "Curated outlet/account matches for NurtureAny known-area near-me flow. Google-only restaurants are not auto-stored."
);

-- Recommended constraints in workflow code:
-- - match_status in ('confirmed', 'candidate', 'rejected')
-- - account_status in ('customer', 'prospect', 'unknown')
-- - confidence in ('verified', 'needs-check', 'blocked')
-- - store Google Places results only after review/approval
-- - never store raw employee GPS, raw Slack transcripts, phone exports, or secrets
