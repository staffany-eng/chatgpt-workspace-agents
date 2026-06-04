#standardSQL
CREATE OR REPLACE TABLE `staffany-warehouse.analytics.support_watch_whatsapp_ticket_logs`
PARTITION BY reported_date
OPTIONS(
  description = "Native Launchbot support-watch mirror of WhatsApp CS ticket logs. Runtime scans this table instead of Drive-backed gsheets external tables."
)
AS
SELECT
  source_year,
  source_table,
  eng_duty,
  ops_support,
  cs_duty,
  reported_date,
  reported_date_raw,
  reported_customer,
  organisation,
  organisation_name,
  organisation_id,
  category,
  issue_description,
  ticket_type,
  ticket_status,
  resolved_date,
  resolved_date_raw,
  channel,
  is_whatsapp,
  time_taken_minutes,
  time_taken_minutes_raw,
  remarks_resolution_ps,
  week,
  week_raw,
  slack_link,
  investigation_ticket,
  bug_ticket,
  priority,
  bug_status,
  fix_versions,
  resolve_reported,
  month_of_reported_date,
  time_to_resolution_days,
  time_to_resolution_days_raw
FROM `staffany-warehouse.gsheets.cs_tickets_logs_all_view`;
