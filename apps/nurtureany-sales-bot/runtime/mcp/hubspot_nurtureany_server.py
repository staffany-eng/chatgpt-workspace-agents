#!/usr/bin/env python3
"""HubSpot MCP adapter for NurtureAny Sales Bot.

This server is intentionally V1-safe: read tools, previews, selected paid
enrichment, and narrow approval-gated HubSpot Task primitives only.
"""

from __future__ import annotations

import html
import hashlib
import ipaddress
import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mcp.server.fastmcp import FastMCP

from nurtureany_common.c360 import (
    c360_company_url_template as _shared_c360_company_url_template,
    c360_org_url_template as _shared_c360_org_url_template,
    c360_route_key_map as _shared_c360_route_key_map,
    customer360_route_key as _shared_customer360_route_key,
    encode_url_value as _shared_encode_url_value,
    render_c360_url as _shared_render_c360_url,
)
from nurtureany_common.luma_filters import (
    canonical_country as _shared_canonical_country,
    canonical_event_type as _shared_canonical_event_type,
    canonical_location as _shared_canonical_location,
    event_tag_filters as _shared_event_tag_filters,
    resolved_event_filters as _shared_resolved_event_filters,
)
from nurtureany_common import public_research as _public_research
from nurtureany_common.responses import blocked_response
from nurtureany_common.text import (
    clean_domain as _shared_clean_domain,
    email_domain as _shared_email_domain,
    hash_email as _shared_hash_email,
    normalize_email as _shared_normalize_email,
    normalized_words as _shared_normalized_words,
    unique_text as _shared_unique_text,
)
from nurtureany_hubspot.workflows import sg_lead_enrichment as _sg_lead_enrichment


HUBSPOT_BASE_URL = "https://api.hubapi.com"
SUPPORTED_COUNTRIES = ("Singapore", "Malaysia", "Indonesia")
OVERALL_ADMINS = {"eugene@staffany.com", "kaiyi@staffany.com", "kai.yi@staffany.com"}
BUILT_IN_EMAIL_ALIASES = {
    "kai.yi@staffany.com": "kaiyi@staffany.com",
    "leekai.yi@staffany.com": "kaiyi@staffany.com",
}
TEAM_READ_SCOPE_KINDS = {"admin", "manager", "partnerships_viewer"}
MANAGER_ADMIN_SCOPE_KINDS = {"admin", "manager"}
REGIONAL_MANAGERS = {
    "kerren.fong@staffany.com": ("Singapore", "Malaysia"),
    "sarah@staffany.com": ("Indonesia",),
    "sarah.ayutania@staffany.com": ("Indonesia",),
}
EVENT_OPERATOR_ACCESS_PROFILE = "regional_events_read_only"
EVENT_OPERATOR_BLOCK_MESSAGE = (
    "Regional event operators can use read-only event sourcing only. "
    "Manager/admin workflows, AE coaching, revenue metrics, HubSpot writes, and generic account context are blocked."
)

COMPANY_PROPERTIES = [
    "name",
    "domain",
    "website",
    "hs_is_target_account",
    "hubspot_owner_id",
    "company_country",
    "numberofemployees",
    "industry",
    "lifecyclestage",
    "type",
    "contract_end_date",
    "current_tool_renewal_date",
    "current_tools",
    "notes_last_updated",
    "hs_num_decision_makers",
    "hs_num_contacts_with_buying_roles",
    "prospecting_account",
    "nurtureany_status",
    "nurtureany_priority_score",
    "nurtureany_segment",
    "nurtureany_next_action",
    "nurtureany_next_trigger_at",
    "nurtureany_last_reviewed_at",
    "nurtureany_last_nurtured_at",
    "nurtureany_enrichment_status",
    "nurtureany_contact_coverage",
]

CONTACT_PROPERTIES = [
    "email",
    "firstname",
    "lastname",
    "jobtitle",
    "job_role",
    "phone",
    "mobilephone",
    "hs_buying_role",
    "hs_email_optout",
    "hubspot_owner_id",
    "lastmodifieddate",
    "nurtureany_persona",
    "nurtureany_channel_fit",
    "nurtureany_contact_confidence",
    "nurtureany_last_verified_at",
    "nurtureany_phone_verification_status",
    "nurtureany_phone_verified_at",
    "nurtureany_phone_verified_by",
    "nurtureany_phone_verification_source",
    "nurtureany_phone_verification_notes",
]

DEAL_PROPERTIES = [
    "dealname",
    "dealstage",
    "pipeline",
    "amount",
    "createdate",
    "closedate",
    "hs_lastmodifieddate",
    "hubspot_owner_id",
    "contract_end_date",
]

TASK_PROPERTIES = [
    "hs_timestamp",
    "hs_task_subject",
    "hubspot_owner_id",
    "hs_task_status",
    "hs_task_priority",
    "hs_task_type",
    "hs_task_reminders",
    "hs_lastmodifieddate",
]

MARKETING_CONTACT_PROPERTIES = [
    "email",
    "firstname",
    "lastname",
    "jobtitle",
    "hs_buying_role",
    "hubspot_owner_id",
    "createdate",
    "lastmodifieddate",
    "lifecyclestage",
    "hs_analytics_source",
    "hs_analytics_source_data_1",
    "hs_analytics_source_data_2",
    "hs_latest_source",
    "hs_latest_source_data_1",
    "hs_latest_source_data_2",
    "first_conversion_event_name",
    "first_conversion_date",
    "recent_conversion_event_name",
    "recent_conversion_date",
    "abm_campaign_tag",
    "ad_interaction",
    "utm_campaign",
]

MARKETING_COMPANY_PROPERTIES = sorted(
    set(
        COMPANY_PROPERTIES
        + [
            "campaign",
            "abm_campaign_tag",
            "ad_interaction",
            "utm_campaign",
            "hs_analytics_source",
            "hs_analytics_source_data_1",
            "hs_analytics_source_data_2",
            "hs_latest_source",
            "hs_latest_source_data_1",
            "hs_latest_source_data_2",
        ]
    )
)

CAMPAIGN_PROPERTIES = [
    "hs_name",
    "hs_campaign_status",
    "hs_start_date",
    "hs_end_date",
    "hs_notes",
    "hs_audience",
    "hs_utm",
    "hs_owner",
    "hs_object_id",
    "hs_budget_items_sum_amount",
    "hs_spend_items_sum_amount",
]

MARKETING_CAMPAIGN_ASSET_TYPES = (
    "FORM",
    "LANDING_PAGE",
    "SITE_PAGE",
    "MARKETING_EMAIL",
    "MARKETING_SMS",
    "SOCIAL_BROADCAST",
    "PODCAST_EPISODE",
)

NO_METRIC_CAMPAIGN_ASSET_TYPES = {"PODCAST_EPISODE", "AD_CAMPAIGN", "MEDIA", "PLAYBOOK", "SALES_DOCUMENT", "EMAIL", "SEQUENCE"}

SOCIAL_CLICK_METRIC_KEYS = {
    "facebook": "FACEBOOK_CLICKS",
    "linkedin": "LINKEDIN_CLICKS",
    "twitter": "TWITTER_CLICKS",
}

MARKETING_ATTRIBUTION_SEARCH_PROPERTIES = (
    "utm_campaign",
    "abm_campaign_tag",
    "first_conversion_event_name",
    "recent_conversion_event_name",
    "hs_analytics_source_data_1",
    "hs_analytics_source_data_2",
    "hs_latest_source_data_1",
    "hs_latest_source_data_2",
)

COMMUNICATION_PROPERTIES = [
    "hs_timestamp",
    "hubspot_owner_id",
    "hs_communication_channel_type",
    "hs_communication_logged_from",
    "hs_lastmodifieddate",
]
COMMUNICATION_EVENT_PROPERTIES = [*COMMUNICATION_PROPERTIES, "hs_communication_body"]
WHATSAPP_KNS_AUDIT_DEFAULT_LIMIT = 500
KNS_KNOWLEDGE_TERMS = (
    "insight",
    "benchmark",
    "case study",
    "article",
    "guide",
    "data",
    "trend",
    "playbook",
    "resource",
    "learning",
    "sharing",
    "industry",
    "workforce",
    "manpower",
    "scheduling",
    "payroll",
    "attendance",
    "roster",
)
KNS_NETWORK_SPEAKER_SOURCING_TERMS = (
    "anyone u wanna hear from",
    "anyone you wanna hear from",
    "anyone you want to hear from",
    "who u want to hear from",
    "who you want to hear from",
    "who they want to hear from",
    "hear from the industry",
    "invite relevant future speakers",
    "future speaker",
)
KNS_NETWORK_TERMS = (
    "community",
    "network",
    "intro",
    "introduction",
    "connect",
    "peer",
    "industry peer",
    "peer matching",
    "retail hr leaders",
    "hr leaders solving",
    "similar operators",
    "similar business challenges",
    "similar manpower challenges",
    "founder",
    "operator",
    "referral",
    "matchmake",
    "match make",
    "talent matching",
    "looking to hire",
    "hire any role",
    "recommend talent",
    *KNS_NETWORK_SPEAKER_SOURCING_TERMS,
    "role similarity",
    "industry vertical",
    "growth stage",
    "hiring priorities",
    "expansion plans",
    "active supporters",
    "product adoption",
    "collaboration",
    "collaborate",
    "cross-brand",
    "partnership",
    "joint case study",
    "case study collaboration",
    "employer branding",
    "joint event",
    "operational learning",
    "permission before intro",
    "mutual value",
)
KNS_NETWORK_EVENT_TERMS = (
    "event",
    "upcoming event",
    "hhh",
    "hr happy hour",
    "happy hr hour",
    "leaders lounge",
    "leader lounge",
    "overseas ll",
    "cozy dinner",
    "cosy dinner",
    "invite",
    "session",
    "fireside",
    "webinar",
    "lunch",
    "coffee",
)
KNS_SUPPORT_OPPORTUNITY_TERMS = (
    "be our speaker",
    "open to be our speaker",
    "speaker opportunity",
    "venue opportunity",
    "fireside opportunity",
    "speaker for upcoming",
    "support their venue",
    "support your venue",
    "host at your venue",
    "host at his venue",
    "host at her venue",
    "host a simple meal",
    "simple meal at",
    "buy their product",
    "buy your product",
    "support their product",
    "support your product",
    "walk past their shop",
    "walk past your shop",
    "long queue",
)
KNS_SUPPORT_TERMS = (
    "help",
    "support",
    "can i",
    "are we able to support",
    "would it be useful",
    "happy to",
    "chat",
    "call",
    "demo",
    "share",
    "show",
    "next step",
    "discuss",
    "follow up",
    "workshop",
)

NOTE_PROPERTIES = [
    "hs_timestamp",
    "hubspot_owner_id",
    "hs_lastmodifieddate",
]

CALL_PROPERTIES = [
    "hs_timestamp",
    "hubspot_owner_id",
    "hs_call_title",
    "hs_call_status",
    "hs_call_duration",
    "hs_call_external_id",
    "hs_call_unique_external_id",
    "hs_call_source",
    "hs_call_app_id",
    "hs_object_source_detail_1",
    "hs_object_source_label",
    "hs_lastmodifieddate",
]

MEETING_PROPERTIES = [
    "hs_timestamp",
    "hubspot_owner_id",
    "hs_meeting_title",
    "hs_meeting_outcome",
    "hs_activity_type",
    "hs_lastmodifieddate",
]

FREE_SEARCH_SOURCE_TYPES = _public_research.FREE_SEARCH_SOURCE_TYPES
FETCHABLE_PUBLIC_SOURCE_TYPES = _public_research.FETCHABLE_PUBLIC_SOURCE_TYPES
MANUAL_ONLY_HOST_MARKERS = _public_research.MANUAL_ONLY_HOST_MARKERS
PUBLIC_FETCH_TIMEOUT_SECONDS = _public_research.PUBLIC_FETCH_TIMEOUT_SECONDS
PUBLIC_FETCH_MAX_BYTES = _public_research.PUBLIC_FETCH_MAX_BYTES
PUBLIC_EVIDENCE_ITEM_LIMIT = _public_research.PUBLIC_EVIDENCE_ITEM_LIMIT
PUBLIC_TASK_ACCOUNT_LIMIT = 25
PRE_DEMO_GAME_PLAN_ACCOUNT_LIMIT = 5
CASE_STUDY_MATCH_LIMIT = 3
CASE_STUDY_MIN_MATCH_SCORE = 8
CASE_STUDY_CATALOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "case-studies.json")
SINGAPORE_LEAD_ENRICHMENT_DEFAULT_LIMIT = 30
SINGAPORE_LEAD_ENRICHMENT_MAX_LIMIT = 250
SINGAPORE_LEAD_ENRICHMENT_DEFAULT_BATCH_SIZE = 30
SINGAPORE_LEAD_ENRICHMENT_COUNTRY = "Singapore"
PHONE_VERIFICATION_DEFAULT_STALE_AFTER_DAYS = 90
PHONE_VERIFICATION_STATUSES = {
    "not_checked",
    "candidate",
    "called_connected",
    "wrong_number",
    "unreachable",
    "no_answer",
    "do_not_contact",
    "stale",
}
PHONE_VERIFICATION_VERIFIED_STATUSES = {"called_connected"}
PHONE_VERIFICATION_SOURCES = {
    "hubspot_existing",
    "manual_call",
    "lusha_reveal",
    "truecaller_manual_lookup",
    "apollo_manual",
    "prospeo_manual",
}
SINGAPORE_LEAD_ENRICHMENT_BUCKETS = (
    "nurture_ready",
    "missing_associated_contact",
    "missing_decision_maker",
    "missing_verified_phone",
    "hubspot_rollup_mismatch",
    "needs_paid_reveal",
    "needs_manual_truecaller_check",
    "ready_for_whatsapp_batch",
)
SINGAPORE_LEAD_ENRICHMENT_SOURCE_LADDER = (
    "hubspot",
    "hubspot_notes_tasks_history",
    "tavily_public_company_job_board_research",
    "exa_people_candidate_discovery",
    "lusha_prospeo_parallel_search_pilot",
    "approved_lusha_or_prospeo_reveal",
    "manual_truecaller_call_outcome",
    "hubspot_writeback_preview",
)
SINGAPORE_LEAD_ENRICHMENT_PROVIDER_JOBS = (
    {
        "provider": "tavily_public_research",
        "job": "public company, company-site, careers, and SG job-board signal research",
        "cost_policy": "use before paid contact reveal; requires scoped HubSpot company input and cost_report",
    },
    {
        "provider": "exa_people_search",
        "job": "public people/profile candidate discovery",
        "cost_policy": "use after public company research when decision-maker or champion candidates are still missing",
    },
    {
        "provider": "lusha",
        "job": "selected contact lookup or reveal",
        "cost_policy": "pilot only for real gaps; approval marker and credit_report required before reveal",
    },
    {
        "provider": "prospeo",
        "job": "parallel paid-provider candidate for email/mobile yield comparison",
        "cost_policy": "V1.1 candidate only; no adapter, no auto-write, and same approval/cost guardrails as Lusha",
    },
    {
        "provider": "truecaller",
        "job": "manual callability lookup and call outcome evidence",
        "cost_policy": "manual only; never automated reverse lookup, scraping, or bulk enrichment",
    },
)
SINGAPORE_LEAD_ENRICHMENT_PILOT_METRICS = (
    "cost_per_account_moved_out_of_gap_bucket",
    "cost_per_usable_contact",
    "cost_per_verified_or_callable_phone",
    "ae_validation_valid_wrong_person_left_company_no_response",
    "activities_to_qo_follow_through",
)
HUBSPOT_SEARCH_PAGE_LIMIT = 100
HUBSPOT_SEARCH_RESULT_LIMIT = 1000
HUBSPOT_SEARCH_TOTAL_LIMIT = 10_000
T90_MISSING_CONTRACT_END_DATE_DEFAULT_LIMIT = 250
TASK_ASSOCIATION_LIMIT = 100
TASK_RETURN_LIMIT = 100
LUMA_MATCH_DOMAIN_LIMIT = 100
LUMA_MATCH_NAME_LIMIT = 100
LUMA_MATCH_RETURN_LIMIT = 75
LUMA_MATCH_SCAN_LIMIT = HUBSPOT_SEARCH_TOTAL_LIMIT
LUMA_MATCH_CANDIDATE_FIELDS = (
    "company_id",
    "hubspot_scoped",
    "scope_source",
    "name",
    "domain",
    "country",
    "owner_id",
    "owner_email",
    "owner_name",
    "account_status",
    "account_status_source",
    "luma_match_reasons",
    "luma_match_key_kinds",
    "luma_match_key_count",
    "luma_match_confidence",
)
TASK_SEARCH_RESULT_LIMIT = 300
TASK_SEARCH_AIRTIGHT_RESULT_LIMIT = 10_000
TASK_CREATE_APPROVAL_MARKERS = {"create task", "confirm task"}
TASK_RESCHEDULE_APPROVAL_MARKERS = {"update task", "confirm reminder"}
TASK_COMPLETE_APPROVAL_MARKERS = {"mark done", "complete task"}
TASK_ASSOCIATION_TYPE_IDS = {
    "company": 192,
    "contact": 204,
    "deal": 216,
}
TASK_DEFAULT_DUE_HOUR_LOCAL = 10
TASK_DUPLICATE_WINDOW_DAYS = 1
HUBSPOT_SOFT_TIMEOUT_SECONDS_ENV_VAR = "NURTUREANY_HUBSPOT_SOFT_TIMEOUT_SECONDS"
HUBSPOT_SOFT_TIMEOUT_SECONDS_DEFAULT = 270
HUBSPOT_SOFT_TIMEOUT_SECONDS_MAX = 300
FOLLOWUP_ASSOCIATION_LIMIT = 100
FOLLOWUP_RETURN_LIMIT = 100
INBOUND_THREAD_RETURN_LIMIT = 50
INBOUND_MESSAGE_RETURN_LIMIT = 100
INBOUND_SLA_ALERT_RETURN_LIMIT = 100
INBOUND_SLA_DEFAULT_ACK_MINUTES = 5
INBOUND_SLA_DEFAULT_FIRST_TOUCH_MINUTES = 15
INBOUND_SLA_DEFAULT_DUPLICATE_WINDOW_MINUTES = 120
MARKETING_CAMPAIGN_RETURN_LIMIT = 100
CAMPAIGN_ASSET_RETURN_LIMIT = 100
CAMPAIGN_SOCIAL_ASSET_RETURN_LIMIT = 1000
SOCIAL_TOP_POST_RETURN_LIMIT = 10
MARKETING_ATTRIBUTION_RETURN_LIMIT = 100
MARKETING_ATTRIBUTION_DETAIL_RETURN_LIMIT = 15
MARKETING_ATTRIBUTION_TERM_LIMIT = 10
MESSAGE_TEXT_LIMIT = 4000
PRIORITY_ACCOUNT_RETURN_LIMIT = 1000
PRIORITY_ACCOUNT_LOCKED_POOL_BASELINE = 150
PRIORITY_ACCOUNT_WEEKLY_WORKED_TARGET = 120
MANAGER_CHASE_RETURN_LIMIT = 20
MANAGER_CHASE_COVERAGE_LIMIT = 150
ACTIVE_DEAL_HYGIENE_RETURN_LIMIT = 100
REVENUE_FUNNEL_RETURN_LIMIT = 250
REVENUE_FUNNEL_DEAL_SCAN_LIMIT = 1000
EVENT_SOURCING_DEFAULT_LIMIT = 10
EVENT_SOURCING_RETURN_LIMIT = 50
EVENT_SOURCING_SCAN_LIMIT = 1000
EVENT_SOURCING_DEFAULT_DEAL_BUCKET = "open_or_none"
EVENT_SOURCING_CONTACT_ROLE_FILTERS = {"owner_or_hr", "owner", "hr", "any"}
REVENUE_FUNNEL_NEW_BUSINESS_PIPELINE_IDS_ENV_VAR = "NURTUREANY_REVENUE_NEW_BUSINESS_PIPELINE_IDS"
REVENUE_FUNNEL_RENEWAL_PIPELINE_IDS_ENV_VAR = "NURTUREANY_REVENUE_RENEWAL_PIPELINE_IDS"
REVENUE_FUNNEL_CHANNEL_PROPERTIES = (
    "appointment_set_channel",
    "appointment_setter_channel",
    "appointment_source",
    "sales_channel",
    "lead_source",
    "hs_analytics_source",
    "hs_analytics_source_data_1",
    "hs_latest_source",
    "hs_latest_source_data_1",
)
REVENUE_FUNNEL_BUSINESS_TYPE_PROPERTIES = (
    "dealtype",
    "deal_type",
    "business_type",
    "new_existing_business",
    "new_or_existing_business",
)
REVENUE_FUNNEL_DEAL_PROPERTIES = sorted(
    set(DEAL_PROPERTIES + list(REVENUE_FUNNEL_CHANNEL_PROPERTIES) + list(REVENUE_FUNNEL_BUSINESS_TYPE_PROPERTIES))
)
REVENUE_FUNNEL_SALES_OUTBOUND_VALUES = {"sales outbound"}
REVENUE_FUNNEL_ALL_OUTBOUND_MARKERS = ("outbound", "cold call", "cold email", "linkedin", "whatsapp outbound")
AE_COACHING_QO_WEEKLY_TARGET = 3
AE_COACHING_MORNING_START_HOUR = 6
AE_COACHING_MORNING_END_HOUR = 12
AE_COACHING_DEFAULT_WINDOW_START = "06:00"
AE_COACHING_DEFAULT_WINDOW_END = "12:00"
DAILY_NURTURE_PLAN_TIME_LOCAL = "09:00"
AE_COACHING_LONG_CALL_MIN_DURATION_MS = 60_000
AE_COACHING_DEFAULT_LIMIT = PRIORITY_ACCOUNT_LOCKED_POOL_BASELINE
AE_COACHING_DEFAULT_SOFT_TIMEOUT_SECONDS = 240
SALES_NAVIGATOR_ROLE_PRIORITY = (
    ("DECISION_MAKER", 100),
    ("founder", 95),
    ("owner", 90),
    ("chief", 88),
    ("director", 84),
    ("head of hr", 82),
    ("hr manager", 76),
    ("ops manager", 72),
    ("operations manager", 72),
    ("hr executive", 55),
)
FNB_RETAIL_MARKERS = ("food", "beverage", "restaurant", "f&b", "fnb", "retail", "cafe", "bakery", "hospitality")
_CASE_STUDY_CATALOG_CACHE: list[dict[str, Any]] | None = None
_DEAL_PROPERTY_NAMES_CACHE: set[str] | None = None
CONNECTED_CALL_WEEKLY_TARGET = 40
CONNECTED_CALL_MIN_DURATION_MS = 120_000
SALES_CALL_DEFAULT_SCAN_LIMIT = 1_000
SALES_CALL_ASSOCIATION_MODES = {"owner_level", "target_account_associated", "selected_company_associated"}
STALE_ACCOUNT_DAYS = 18
FRIDAY_REVIEW_DETAIL_LIMIT = 25
QO_PIPELINE_IDS_ENV_VAR = "NURTUREANY_QO_PIPELINE_IDS"
QO_STAGE_IDS_ENV_VAR = "NURTUREANY_QO_STAGE_IDS"
QO_MET_STAGE_IDS_ENV_VAR = "NURTUREANY_QO_MET_STAGE_IDS"
CLOSED_WON_STAGE_IDS_ENV_VAR = "NURTUREANY_CLOSED_WON_STAGE_IDS"
WARM_ACTIVITY_LABELS_ENV_VAR = "NURTUREANY_WARM_ACTIVITY_LABELS"
DEFAULT_WARM_ACTIVITY_LABELS = (
    "HHH",
    "LL",
    "coffee",
    "lunch",
    "dinner",
    "cosy",
    "ABM",
    "event",
    "appreciation afternoon",
    "sports",
)
ACCESS_POLICY_ENV_VAR = "NURTUREANY_ACCESS_POLICY_PATH"
SCOPE_SOURCE = "hubspot_nurtureany"
BIGQUERY_EXECUTION_TOOL = "staffany_bigquery.execute_sql_readonly"
SALES_METRIC_SOURCE_CLASS = "C360 BigQuery/Manticore actuals"
SALES_METRIC_SQL_SOURCE = "NurtureAny sales metric BigQuery SQL builder"
SALES_METRIC_TABLES = {
    "qo_set": "staffany-warehouse.analytics.fct_sales_points",
    "signed_converted_arr": "staffany-warehouse.analytics.fct_deal_metrics_with_pilot_conversion",
    "paid_converted_arr": "staffany-warehouse.analytics.fct_deal_metrics_with_pilot_conversion",
    "new_mrr_movement_arr": "staffany-warehouse.analytics.fct_mrr_movements",
    "net_mrr_movement_arr": "staffany-warehouse.analytics.fct_mrr_movements",
    "current_arr": "staffany-warehouse.analytics.fct_company_revenue_snapshot",
    "current_mrr": "staffany-warehouse.analytics.fct_company_revenue_snapshot",
}
SALES_METRIC_DEFINITIONS = {
    "qo_set": "Qualified Opportunity sales point from appointment-owner, ICP employee-size, appointment-date, and new-business deal filters.",
    "signed_converted_arr": "ARR from signed converted deals, including pilot conversion logic.",
    "paid_converted_arr": "ARR from paid converted deals only, including pilot conversion logic.",
    "new_mrr_movement_arr": "New MRR movement annualized to ARR from the MRR movement ledger.",
    "net_mrr_movement_arr": "Net MRR movement annualized to ARR across movement types.",
    "current_arr": "Current ARR from the latest or requested company revenue snapshot month.",
    "current_mrr": "Current MRR from the latest or requested company revenue snapshot month.",
}
AMBIGUOUS_NEW_ARR_OPTIONS = ["signed_converted_arr", "paid_converted_arr", "new_mrr_movement_arr"]
RENEWAL_SOURCE_OF_TRUTH_PROPERTY = "contract_end_date"
CURRENT_TOOLS_SOURCE_OF_TRUTH_PROPERTY = "current_tools"
RENEWAL_DATE_PROPERTIES = (RENEWAL_SOURCE_OF_TRUTH_PROPERTY,)
C360_COMPANY_URL_TEMPLATE_ENV = "NURTUREANY_C360_COMPANY_URL_TEMPLATE"
C360_ORG_URL_TEMPLATE_ENV = "NURTUREANY_C360_ORG_URL_TEMPLATE"
C360_ROUTE_KEY_BY_COMPANY_ID_ENV = "NURTUREANY_C360_ROUTE_KEY_BY_COMPANY_ID"
C360_SALES_PACKET_URL_TEMPLATE_ENV = "NURTUREANY_C360_SALES_PACKET_URL_TEMPLATE"
C360_INTERNAL_API_TOKEN_ENV = "NURTUREANY_C360_INTERNAL_API_TOKEN"
DEFAULT_C360_COMPANY_URL_TEMPLATE = "https://customer-360-qv4r5xkisq-as.a.run.app/companies/{customer360_route_key}"
DEFAULT_C360_ORG_URL_TEMPLATE = (
    "https://customer-360-qv4r5xkisq-as.a.run.app/companies/{customer360_route_key}/orgs/{organisation_id}"
)
DEFAULT_C360_SALES_PACKET_URL_TEMPLATE = (
    "https://customer-360-qv4r5xkisq-as.a.run.app/api/companies/{customer360_route_key}/sales-packet"
)
C360_SALES_PACKET_UNAVAILABLE_CAVEAT = (
    "C360 sales packet unavailable; StaffAny Payroll/product truth could not be confirmed from Customer 360."
)
C360_SALES_PACKET_TIMEOUT_SECONDS = 10
DEFAULT_C360_ROUTE_KEY_BY_COMPANY_ID = {
    # Customer 360's canonical Fei Siong route is slug-keyed. The numeric
    # HubSpot route is accepted by the app but renders fallback demo orgs.
    "1991281569": "fei-siong-group",
}
DRIVE_ALL_RANDOM_FOLDER_ID = "1qXlFnr5TKFtsYNWk7ZywBBctDaae3RY-"
PHOTO_SCAN_LIMIT = 50
PHOTO_MATCH_LIMIT = 5
PHOTO_LUMA_EVENT_CANDIDATE_LIMIT = 3
PHOTO_SOURCE_TYPES = {"drive", "slack"}
PHOTO_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")
PHOTO_CUSTOM_OBJECT_TYPES = {
    "event": "nurture_event",
    "photo": "nurture_event_photo",
    "appearance": "nurture_person_appearance",
}
SINGAPORE_TIMEZONE = timezone(timedelta(hours=8))
DAILY_NURTURE_DEFAULT_ACCOUNT_COUNT = 30
DAILY_NURTURE_PROTECTED_POOL_SIZE = 150
DAILY_NURTURE_WORKWEEK_DAYS = 5
DAILY_NURTURE_MATERIAL_TABS = (
    "Materials",
    "Playbooks",
    "Peer Intros",
    "Speaker/Venue Opportunities",
    "Events",
    "Review Log",
)
DAILY_NURTURE_MATERIAL_FIELDS = (
    "material_id",
    "category",
    "title",
    "url",
    "status",
    "country_scope",
    "industry_tags",
    "concept_tags",
    "persona_tags",
    "valid_from",
    "valid_until",
    "template_name",
    "template_params_schema",
    "message_hook",
    "owner",
)
DAILY_NURTURE_DEFAULT_TEMPLATE_NAME = "nurture_material_share_v1"
DAILY_NURTURE_DEFAULT_TEMPLATE_SCHEMA = ("first_name", "account_name", "material_title", "material_url")
DAILY_NURTURE_DO_NOT_CONTACT_MARKERS = (
    "do not contact",
    "dont contact",
    "do-not-contact",
    "dnc",
    "opt out",
    "opted out",
    "unsubscribe",
    "unsubscribed",
    "blacklist",
)
DAILY_NURTURE_ACTIVE_MATERIAL_STATUSES = {"active", "approved", "live"}
DAILY_NURTURE_RUNS_DIR_ENV = "NURTUREANY_DAILY_RUNS_DIR"
OPERATION_LEDGER_DIR_ENV = "NURTUREANY_OPERATION_LEDGER_DIR"
OPERATION_LEDGER_DEFAULT_PROFILE = "nurtureanysalesbot"
LESSON_CANDIDATES_DIR_ENV = "NURTUREANY_LESSON_CANDIDATES_DIR"
LESSON_CANDIDATE_STATUSES = {"pending_review", "approved_for_repo_promotion", "rejected", "promoted"}
LESSON_CANDIDATE_RISK_CLASSES = {"low", "medium", "high"}
LESSON_CANDIDATE_TARGET_SURFACES = {
    "skill_reference",
    "soul",
    "mcp_contract",
    "config_template",
    "regression_case",
    "runbook",
    "research_wiki",
    "app_manifest",
}
LUMA_BASE_URL = "https://public-api.luma.com"
LUMA_USER_AGENT = "StaffAny-NurtureAny/1.0 (+https://staffany.com)"
LUMA_TIMEOUT_SECONDS = 15
LUMA_PAGE_LIMIT = 50
LUMA_EVENT_LOOKBACK_DAYS = 180
LUMA_EVENT_LOOKAHEAD_DAYS = 1
LUMA_MAX_EVENTS_FOR_FOLLOWUP = 50
LUMA_MAX_GUESTS_PER_EVENT = 250
EVENT_TYPE_ALIASES = {
    "hhh": "HR Happy Hour",
    "hr happy hour": "HR Happy Hour",
    "happy hour": "HR Happy Hour",
    "ll": "Leaders Lounge",
    "leaders lounge": "Leaders Lounge",
    "leader lounge": "Leaders Lounge",
    "appreciation afternoon": "Appreciation Afternoon",
    "appreciation": "Appreciation Afternoon",
    "sports": "Sports",
    "sport": "Sports",
}
LOCATION_ALIASES = {
    "singapore": "Singapore",
    "sg": "Singapore",
    "jakarta": "Jakarta",
    "jkt": "Jakarta",
    "bali": "Bali",
    "kuala lumpur": "Kuala Lumpur",
    "kl": "Kuala Lumpur",
}
LOCATION_COUNTRY_MAP = {
    "Singapore": "Singapore",
    "Jakarta": "Indonesia",
    "Bali": "Indonesia",
    "Kuala Lumpur": "Malaysia",
}
GENERIC_EMAIL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "me.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
}
EVENT_FOLLOWUP_PHRASES = (
    "thank you",
    "thanks",
    "thanks for attending",
    "terima kasih",
    "makasih",
    "sudah datang",
    "sudah hadir",
    "telah datang",
    "telah hadir",
    "for coming",
    "for joining",
    "attending",
    "hadir",
    "datang",
    "follow up",
    "follow-up",
)


mcp = FastMCP(
    "hubspot_nurtureany",
    instructions=(
        "HubSpot target-account tools for NurtureAny. Generic mutation tools are disabled; "
        "only preview-first, exact-approval HubSpot Task primitives may mutate tasks."
    ),
)


class HubSpotError(RuntimeError):
    pass


class LumaEventError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ScopeError(RuntimeError):
    pass


class AccessPolicyError(RuntimeError):
    pass


class MetricClarification(RuntimeError):
    pass


def _token() -> str:
    token = os.environ.get("HUBSPOT_PRIVATE_APP_TOKEN", "").strip()
    if not token:
        raise HubSpotError("Missing HUBSPOT_PRIVATE_APP_TOKEN.")
    return token


def _luma_token() -> str:
    token = os.environ.get("LUMA_API_KEY", "").strip()
    if not token:
        raise LumaEventError("Missing LUMA_API_KEY.")
    return token


def _normalize_email(email: str) -> str:
    return _shared_normalize_email(email)


def _normalize_countries(countries: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    selected = []
    for country in countries or SUPPORTED_COUNTRIES:
        if country in SUPPORTED_COUNTRIES and country not in selected:
            selected.append(country)
    return tuple(selected)


def _string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _entry_email(entry: Any, *keys: str) -> str:
    if isinstance(entry, str):
        return _normalize_email(entry)
    if isinstance(entry, dict):
        for key in keys:
            value = _normalize_email(str(entry.get(key) or ""))
            if value:
                return value
    return ""


def _register_email_alias(aliases: dict[str, str], alias_email: Any, canonical_email: Any) -> None:
    alias = _normalize_email(str(alias_email or ""))
    canonical = _normalize_email(str(canonical_email or ""))
    if alias and canonical and alias != canonical:
        aliases[alias] = canonical


def _register_policy_alias_entry(aliases: dict[str, str], entry: Any) -> None:
    if isinstance(entry, dict):
        alias = _entry_email(entry, "email", "slack_email", "alias")
        canonical = _entry_email(entry, "alias_for", "canonical_email", "canonical_slack_email", "target_email")
        _register_email_alias(aliases, alias, canonical)
        return
    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
        _register_email_alias(aliases, entry[0], entry[1])


def _canonical_policy_email(email: str, policy: dict[str, Any]) -> str:
    aliases = policy.get("aliases", {})
    current = _normalize_email(email)
    seen: set[str] = set()
    while current and current in aliases and current not in seen:
        seen.add(current)
        next_email = _normalize_email(str(aliases.get(current) or ""))
        if not next_email:
            break
        current = next_email
    return current


def _access_policy_path() -> str:
    return os.environ.get(ACCESS_POLICY_ENV_VAR, "").strip()


def _load_access_policy_file() -> dict[str, Any]:
    path = _access_policy_path()
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as error:
        raise AccessPolicyError(f"{ACCESS_POLICY_ENV_VAR} file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise AccessPolicyError(f"{ACCESS_POLICY_ENV_VAR} is invalid JSON: {error}") from error
    if not isinstance(data, dict):
        raise AccessPolicyError(f"{ACCESS_POLICY_ENV_VAR} must point to a JSON object.")
    return data


def _access_policy() -> dict[str, Any]:
    raw = _load_access_policy_file()
    admins = set(OVERALL_ADMINS)
    managers: dict[str, tuple[str, ...]] = {
        email: _normalize_countries(countries) for email, countries in REGIONAL_MANAGERS.items()
    }
    partnerships_viewers: dict[str, tuple[str, ...]] = {}
    event_operators: dict[str, dict[str, Any]] = {}
    sales_reps: dict[str, dict[str, Any]] = {}
    disabled: set[str] = set()
    aliases: dict[str, str] = dict(BUILT_IN_EMAIL_ALIASES)

    raw_aliases = raw.get("aliases", raw.get("email_aliases", []))
    if isinstance(raw_aliases, dict):
        for alias, canonical in raw_aliases.items():
            _register_email_alias(aliases, alias, canonical)
    elif isinstance(raw_aliases, list):
        for entry in raw_aliases:
            _register_policy_alias_entry(aliases, entry)

    for entry in raw.get("admins", []):
        email = _entry_email(entry, "email", "slack_email")
        alias_for = _entry_email(entry, "alias_for", "canonical_email", "canonical_slack_email")
        if email:
            if alias_for:
                _register_email_alias(aliases, email, alias_for)
                admins.add(alias_for)
            else:
                admins.add(email)

    for entry in raw.get("managers", []):
        email = _entry_email(entry, "email", "slack_email")
        if not email:
            continue
        countries = entry.get("countries") if isinstance(entry, dict) else None
        alias_for = _entry_email(entry, "alias_for", "canonical_email", "canonical_slack_email")
        manager_email = alias_for or email
        if alias_for:
            _register_email_alias(aliases, email, alias_for)
        managers[manager_email] = _normalize_countries(_string_list(countries))

    for key in ("partnerships_viewers",):
        for entry in raw.get(key, []):
            if not isinstance(entry, dict) or entry.get("active") is False:
                continue
            email = _entry_email(entry, "email", "slack_email")
            if not email:
                continue
            countries = entry.get("countries")
            alias_for = _entry_email(entry, "alias_for", "canonical_email", "canonical_slack_email")
            viewer_email = alias_for or email
            if alias_for:
                _register_email_alias(aliases, email, alias_for)
            partnerships_viewers[viewer_email] = _normalize_countries(_string_list(countries))

    for key in ("event_operators", "regional_event_operators"):
        for entry in raw.get(key, []):
            if isinstance(entry, dict) and entry.get("active") is False:
                continue
            email = _entry_email(entry, "email", "slack_email")
            if not email:
                continue
            countries = entry.get("countries") if isinstance(entry, dict) else None
            alias_for = _entry_email(entry, "alias_for", "canonical_email", "canonical_slack_email")
            operator_email = alias_for or email
            if alias_for:
                _register_email_alias(aliases, email, alias_for)
            event_operators[operator_email] = {
                "countries": _normalize_countries(_string_list(countries)),
                "purpose": str(entry.get("purpose") or entry.get("role") or "regional_events").strip()
                if isinstance(entry, dict)
                else "regional_events",
                "access_profile": EVENT_OPERATOR_ACCESS_PROFILE,
            }

    for entry in raw.get("sales_reps", []):
        if not isinstance(entry, dict) or entry.get("active") is False:
            continue
        slack_email = _normalize_email(str(entry.get("slack_email") or entry.get("email") or ""))
        canonical_slack_email = _entry_email(entry, "alias_for", "canonical_email", "canonical_slack_email") or slack_email
        owner_email = _normalize_email(str(entry.get("hubspot_owner_email") or ""))
        if slack_email and canonical_slack_email and canonical_slack_email != slack_email:
            _register_email_alias(aliases, slack_email, canonical_slack_email)
        for alias in _string_list(entry.get("slack_email_aliases")) + _string_list(entry.get("aliases")):
            _register_email_alias(aliases, alias, canonical_slack_email)
        if canonical_slack_email and owner_email:
            sales_reps[canonical_slack_email] = {
                "hubspot_owner_email": owner_email,
                "countries": _normalize_countries(_string_list(entry.get("countries"))),
                "timezone": str(entry.get("timezone") or entry.get("time_zone") or "").strip(),
            }

    for key in ("disabled", "unclassified"):
        for entry in raw.get(key, []):
            email = _entry_email(entry, "email", "slack_email", "hubspot_owner_email")
            if email:
                disabled.add(email)

    return {
        "source": _access_policy_path() or "built-in-admin-manager-defaults",
        "admins": admins - disabled,
        "managers": {email: countries for email, countries in managers.items() if email not in disabled},
        "partnerships_viewers": {
            email: countries for email, countries in partnerships_viewers.items() if email not in disabled
        },
        "event_operators": {email: data for email, data in event_operators.items() if email not in disabled},
        "sales_reps": {
            email: data
            for email, data in sales_reps.items()
            if email not in disabled and data["hubspot_owner_email"] not in disabled
        },
        "disabled": disabled,
        "aliases": aliases,
    }


def _request_json(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    url = urllib.parse.urljoin(HUBSPOT_BASE_URL, path)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "authorization": f"Bearer {_token()}",
        "accept": "application/json",
    }
    if data is not None:
        headers["content-type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)

    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            if error.code == 429 and attempt < 3:
                time.sleep(1.5 * (attempt + 1))
                continue
            detail = error.read().decode("utf-8", errors="replace")
            raise HubSpotError(f"HubSpot API failed: {error.code} {detail[:300]}") from error
        except urllib.error.URLError as error:
            raise HubSpotError(f"HubSpot API failed: {error.reason}") from error

    raise HubSpotError("HubSpot API rate-limited after retries.")


def _luma_request_json(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    query = urllib.parse.urlencode({key: value for key, value in (params or {}).items() if value not in (None, "")})
    url = urllib.parse.urljoin(LUMA_BASE_URL, path)
    if query:
        url = f"{url}?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "x-luma-api-key": _luma_token(),
            "accept": "application/json",
            "user-agent": LUMA_USER_AGENT,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=LUMA_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        token = os.environ.get("LUMA_API_KEY", "").strip()
        safe_detail = detail.replace(token, "[REDACTED_LUMA_API_KEY]") if token else detail
        raise LumaEventError(f"Luma API failed: {error.code} {safe_detail[:300]}", error.code) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise LumaEventError(f"Luma API request timed out or failed: {reason}") from error


def _get(path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    query = urllib.parse.urlencode(params or {})
    return _request_json("GET", f"{path}?{query}" if query else path)


def _post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", path, body)


def _patch(path: str, body: dict[str, Any]) -> dict[str, Any]:
    return _request_json("PATCH", path, body)


def _blocked(message: str, scope: dict[str, Any] | None = None) -> dict[str, Any]:
    return blocked_response(message, "HubSpot", scope)


def _owner_by_email(email: str) -> dict[str, Any] | None:
    normalized = _normalize_email(email)
    if not normalized:
        return None
    data = _get("/crm/v3/owners/", {"email": normalized, "archived": "false", "limit": "100"})
    for owner in data.get("results", []):
        if _normalize_email(owner.get("email", "")) == normalized:
            return owner
    return None


def _list_owners(limit: int = 500) -> list[dict[str, Any]]:
    owners: list[dict[str, Any]] = []
    after = ""
    while len(owners) < _bounded_int(limit, default=500, maximum=1000):
        params = {"archived": "false", "limit": "100"}
        if after:
            params["after"] = after
        data = _get("/crm/v3/owners/", params)
        owners.extend(data.get("results", []))
        after = str(data.get("paging", {}).get("next", {}).get("after") or "")
        if not after:
            break
    return owners[: _bounded_int(limit, default=500, maximum=1000)]


_OWNER_EMAIL_BY_ID_CACHE: dict[str, str] = {}
_OWNER_BY_ID_CACHE: dict[str, dict[str, Any]] = {}


def _owner_email_by_id(owner_id: Any) -> str:
    normalized_owner_id = str(owner_id or "").strip()
    if not normalized_owner_id:
        return ""
    if normalized_owner_id in _OWNER_EMAIL_BY_ID_CACHE:
        return _OWNER_EMAIL_BY_ID_CACHE[normalized_owner_id]
    owner = _owner_by_id(normalized_owner_id)
    if owner:
        email = _normalize_email(str(owner.get("email") or ""))
        if email:
            _OWNER_EMAIL_BY_ID_CACHE[normalized_owner_id] = email
            return email
    return ""


def _owner_by_id(owner_id: Any) -> dict[str, Any]:
    normalized_owner_id = str(owner_id or "").strip()
    if not normalized_owner_id:
        return {}
    if normalized_owner_id in _OWNER_BY_ID_CACHE:
        return _OWNER_BY_ID_CACHE[normalized_owner_id]
    try:
        owner = _get(f"/crm/v3/owners/{urllib.parse.quote(normalized_owner_id, safe='')}", {"archived": "false"})
    except HubSpotError:
        owner = {}
    if owner and str(owner.get("id") or "").strip() == normalized_owner_id:
        _OWNER_BY_ID_CACHE[normalized_owner_id] = owner
        email = _normalize_email(str(owner.get("email") or ""))
        if email:
            _OWNER_EMAIL_BY_ID_CACHE[normalized_owner_id] = email
        return owner
    try:
        for candidate in _list_owners():
            candidate_id = str(candidate.get("id") or "").strip()
            if candidate_id:
                _OWNER_BY_ID_CACHE[candidate_id] = candidate
                email = _normalize_email(str(candidate.get("email") or ""))
                if email:
                    _OWNER_EMAIL_BY_ID_CACHE[candidate_id] = email
    except HubSpotError:
        return {}
    return _OWNER_BY_ID_CACHE.get(normalized_owner_id, {})


def _owner_name_by_id(owner_id: Any) -> str:
    owner = _owner_by_id(owner_id)
    return _owner_name(owner) if owner else ""


def _caller_scope(slack_user_email: str) -> dict[str, Any]:
    requested_email = _normalize_email(slack_user_email)
    if not requested_email:
        return {"kind": "blocked", "email": "", "countries": (), "owner_id": None}
    try:
        policy = _access_policy()
    except AccessPolicyError as error:
        return {"kind": "blocked", "email": requested_email, "countries": (), "owner_id": None, "blocked_reason": str(error)}
    email = _canonical_policy_email(requested_email, policy)
    alias_context = {"requested_email": requested_email} if requested_email and requested_email != email else {}
    if requested_email in policy["disabled"] or email in policy["disabled"]:
        return {"kind": "blocked", "email": email, "countries": (), "owner_id": None, **alias_context}
    if email in policy["admins"]:
        return {"kind": "admin", "email": email, "countries": SUPPORTED_COUNTRIES, "owner_id": None, **alias_context}
    if email in policy["managers"]:
        return {"kind": "manager", "email": email, "countries": policy["managers"][email], "owner_id": None, **alias_context}
    if email in policy.get("event_operators", {}):
        operator = policy["event_operators"][email]
        return {
            "kind": "event_operator",
            "email": email,
            "countries": operator.get("countries", ()),
            "owner_id": None,
            "purpose": operator.get("purpose") or "regional_events",
            "access_profile": operator.get("access_profile") or EVENT_OPERATOR_ACCESS_PROFILE,
            **alias_context,
        }
    if email in policy["partnerships_viewers"]:
        return {
            "kind": "partnerships_viewer",
            "email": email,
            "countries": policy["partnerships_viewers"][email],
            "owner_id": None,
            "read_only": True,
            **alias_context,
        }
    rep = policy["sales_reps"].get(email)
    if not rep:
        return {"kind": "blocked", "email": email, "countries": (), "owner_id": None, **alias_context}
    owner = _owner_by_email(rep["hubspot_owner_email"])
    if not owner:
        return {"kind": "blocked", "email": email, "countries": (), "owner_id": None, **alias_context}
    return {
        "kind": "ae",
        "email": email,
        "countries": rep["countries"],
        "owner_id": str(owner["id"]),
        "hubspot_owner_email": rep["hubspot_owner_email"],
        **alias_context,
    }


def _safe_countries(countries: list[str] | None, allowed: tuple[str, ...]) -> list[str]:
    requested = countries or list(allowed)
    return [country for country in requested if country in allowed]


def _bounded_int(value: Any, default: int, minimum: int = 1, maximum: int = HUBSPOT_SEARCH_RESULT_LIMIT) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(number, maximum))


def _hubspot_soft_timeout_seconds(value: Any = 0) -> int:
    requested = value or os.environ.get(HUBSPOT_SOFT_TIMEOUT_SECONDS_ENV_VAR)
    return _bounded_int(
        requested,
        default=HUBSPOT_SOFT_TIMEOUT_SECONDS_DEFAULT,
        minimum=30,
        maximum=HUBSPOT_SOFT_TIMEOUT_SECONDS_MAX,
    )


def _hubspot_soft_deadline(value: Any = 0) -> float:
    return time.monotonic() + _hubspot_soft_timeout_seconds(value)


def _deadline_exceeded(deadline: float | None) -> bool:
    return bool(deadline and time.monotonic() >= deadline)


def _soft_timeout_metadata(partial: bool, seconds: Any = 0) -> dict[str, Any]:
    if not partial:
        return {"partial_due_to_soft_timeout": False}
    return {
        "partial_due_to_soft_timeout": True,
        "soft_timeout_seconds": _hubspot_soft_timeout_seconds(seconds),
    }


def _company_id_from_ref(ref: Any) -> str:
    text = str(ref or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"\d+", text):
        return text
    for pattern in (
        r"/record/0-2/(\d+)",
        r"/companies/(\d+)",
        r"(?:companyId|company_id)=([0-9]+)",
    ):
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""


def _normalized_company_ids(refs: list[str] | None) -> list[str]:
    company_ids: list[str] = []
    for ref in refs or []:
        company_id = _company_id_from_ref(ref)
        if company_id and company_id not in company_ids:
            company_ids.append(company_id)
    return company_ids


_COMPANY_NAME_STOP_WORDS = {
    "and",
    "co",
    "company",
    "group",
    "inc",
    "incorporated",
    "llc",
    "limited",
    "llp",
    "ltd",
    "pte",
    "pt",
    "sdn",
    "bhd",
    "the",
}


def _company_name_ref(ref: Any) -> str:
    text = str(ref or "").strip()
    if not text or _company_id_from_ref(text):
        return ""
    parsed = urllib.parse.urlparse(text)
    if parsed.scheme and parsed.netloc:
        return ""
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _normalize_company_match_text(value: Any) -> str:
    text = html.unescape(str(value or "")).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    words = [word for word in text.split() if word not in _COMPANY_NAME_STOP_WORDS]
    return " ".join(words)


def _compact_company_match_text(value: Any) -> str:
    return _normalize_company_match_text(value).replace(" ", "")


def _company_search_token(name: str) -> str:
    words = _normalize_company_match_text(name).split()
    useful = [word for word in words if len(word) >= 3]
    return max(useful, key=len) if useful else ""


def _company_search_terms(name: str) -> list[str]:
    normalized = _normalize_company_match_text(name)
    compact = _compact_company_match_text(name)
    terms: list[str] = []
    for term in [compact, *_company_search_token(name).split(), *normalized.split()]:
        if len(term) >= 3 and term not in terms:
            terms.append(term)
    return terms[:5]


def _company_match_candidate(company: dict[str, Any]) -> dict[str, Any]:
    summary = _summarize_company(company)
    return {
        "company_id": summary["company_id"],
        "hubspot_scoped": True,
        "scope_source": SCOPE_SOURCE,
        "name": summary["name"],
        "domain": summary["domain"],
        "country": summary["country"],
        "owner_id": summary["owner_id"],
        "headcount": summary["headcount"],
        "industry": summary["industry"],
        "current_tools": summary["current_tools"],
        "contract_end_date": summary["contract_end_date"],
    }


def _company_name_match_strength(query: str, company: dict[str, Any]) -> str:
    query_text = _normalize_company_match_text(query)
    candidate_text = _normalize_company_match_text(company.get("properties", {}).get("name") or "")
    if not query_text or not candidate_text:
        return "weak"
    if candidate_text == query_text:
        return "exact"
    query_compact = query_text.replace(" ", "")
    candidate_compact = candidate_text.replace(" ", "")
    if query_compact and query_compact == candidate_compact:
        return "compact_exact"
    query_words = set(query_text.split())
    candidate_words = set(candidate_text.split())
    if query_words and query_words.issubset(candidate_words):
        return "token"
    if query_text in candidate_text or candidate_text in query_text:
        return "contains"
    if query_compact and (query_compact in candidate_compact or candidate_compact in query_compact):
        return "compact_contains"
    return "weak"


def _unique_company_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for company in results:
        company_id = str(company.get("id") or "")
        if company_id and company_id not in unique:
            unique[company_id] = company
    return list(unique.values())


def _resolve_scoped_company_name(name: str, scope: dict[str, Any], limit: int = 10) -> dict[str, Any]:
    selected = list(scope.get("countries", ()))
    owner_id = str(scope.get("owner_id") or "") if scope.get("kind") == "ae" else None
    if not selected:
        return {"status": "not_found", "input": name, "candidates": []}

    searches: list[dict[str, Any]] = []
    exact_data = _company_search(
        [
            *_target_filters(selected, owner_id),
            {"propertyName": "name", "operator": "EQ", "value": name},
        ],
        limit=limit,
        maximum=limit,
        sorts=[{"propertyName": "name", "direction": "ASCENDING"}],
    )
    searches.append(exact_data)

    for term in _company_search_terms(name):
        token_data = _company_search(
            [
                *_target_filters(selected, owner_id),
                {"propertyName": "name", "operator": "CONTAINS_TOKEN", "value": term},
            ],
            limit=limit,
            maximum=limit,
            sorts=[{"propertyName": "name", "direction": "ASCENDING"}],
        )
        searches.append(token_data)

    companies = _unique_company_results([company for data in searches for company in data.get("results", [])])
    if not companies:
        return {"status": "not_found", "input": name, "candidates": []}

    strong_matches = [
        company
        for company in companies
        if _company_name_match_strength(name, company) in {"exact", "compact_exact"}
    ]
    if len(strong_matches) == 1:
        return {
            "status": "resolved",
            "input": name,
            "company_id": str(strong_matches[0]["id"]),
            "match_type": _company_name_match_strength(name, strong_matches[0]),
        }

    token_matches = [
        company
        for company in companies
        if _company_name_match_strength(name, company) in {"token", "contains", "compact_contains"}
    ]
    if not strong_matches and len(token_matches) == 1:
        return {
            "status": "resolved",
            "input": name,
            "company_id": str(token_matches[0]["id"]),
            "match_type": _company_name_match_strength(name, token_matches[0]),
        }

    candidates = [_company_match_candidate(company) for company in (strong_matches or token_matches or companies)]
    return {
        "status": "ambiguous",
        "input": name,
        "candidates": candidates[:limit],
        "candidate_count": len(candidates),
    }


def _company_in_event_scope(company: dict[str, Any], scope: dict[str, Any], countries: list[str], owner_id: str | None) -> bool:
    if not _has_company_access(company, scope):
        return False
    props = company.get("properties", {})
    if countries and props.get("company_country") not in countries:
        return False
    if owner_id and str(props.get("hubspot_owner_id") or "") != str(owner_id):
        return False
    return True


def _contact_search_by_email(email: str, limit: int = 10) -> list[dict[str, Any]]:
    normalized = _normalize_email(email)
    if not normalized:
        return []
    data = _post(
        "/crm/v3/objects/contacts/search",
        {
            "filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": normalized}]}],
            "properties": CONTACT_PROPERTIES,
            "limit": max(1, min(limit, 10)),
        },
    )
    return data.get("results", [])


def _event_match_record(company: dict[str, Any], reason: str, confidence: str) -> dict[str, Any]:
    props = company.get("properties", {})
    return {
        "company": company,
        "company_id": str(company.get("id") or ""),
        "match_reason": reason,
        "match_confidence": confidence,
        "owner_id": str(props.get("hubspot_owner_id") or ""),
    }


def _match_luma_guest_to_company(
    guest: dict[str, Any],
    scope: dict[str, Any],
    countries: list[str],
    owner_id: str | None,
) -> dict[str, Any] | None:
    email = _luma_guest_email(guest)
    if email:
        for contact in _contact_search_by_email(email):
            contact_id = str(contact.get("id") or "")
            for company_id in _association_ids("contacts", contact_id, "companies", 10):
                company = _get_company(company_id)
                if _company_in_event_scope(company, scope, countries, owner_id):
                    return _event_match_record(company, "exact_hubspot_contact_email", "verified")

    domain = _email_domain(email)
    if domain and domain not in GENERIC_EMAIL_DOMAINS:
        data = _company_search(
            [
                *_target_filters(countries, owner_id),
                {"propertyName": "domain", "operator": "EQ", "value": domain},
            ],
            limit=10,
            maximum=10,
            sorts=[{"propertyName": "name", "direction": "ASCENDING"}],
        )
        for company in data.get("results", []):
            if _company_in_event_scope(company, scope, countries, owner_id):
                return _event_match_record(company, "exact_email_domain", "verified")

    for company_name in _luma_guest_company_candidates(guest):
        resolved = _resolve_scoped_company_name(company_name, {**scope, "countries": tuple(countries)}, limit=5)
        if resolved.get("status") != "resolved":
            continue
        company = _get_company(str(resolved.get("company_id") or ""))
        if _company_in_event_scope(company, scope, countries, owner_id):
            return _event_match_record(company, "company_name_candidate", "needs-check")
    return None


def _matched_event_companies(
    guests: list[dict[str, Any]],
    scope: dict[str, Any],
    countries: list[str],
    owner_id: str | None,
) -> dict[str, Any]:
    attended_guests = [guest for guest in guests if _luma_checked_in_at(guest)]
    matches: dict[str, dict[str, Any]] = {}
    verified_match_count = 0
    candidate_match_count = 0
    for guest in attended_guests:
        match = _match_luma_guest_to_company(guest, scope, countries, owner_id)
        if not match:
            continue
        company_id = match["company_id"]
        existing = matches.get(company_id)
        if match["match_confidence"] == "verified":
            verified_match_count += 1
        else:
            candidate_match_count += 1
        if existing:
            existing["attended_match_count"] += 1
            if match["match_reason"] not in existing["match_reasons"]:
                existing["match_reasons"].append(match["match_reason"])
            if existing["match_confidence"] != "verified" and match["match_confidence"] == "verified":
                existing["match_confidence"] = "verified"
                existing["company"] = match["company"]
            continue
        matches[company_id] = {
            "company": match["company"],
            "company_id": company_id,
            "match_confidence": match["match_confidence"],
            "match_reasons": [match["match_reason"]],
            "attended_match_count": 1,
        }
    return {
        "matches": matches,
        "attended_guest_count": len(attended_guests),
        "matched_guest_count": sum(item["attended_match_count"] for item in matches.values()),
        "unmatched_attended_guest_count": max(0, len(attended_guests) - sum(item["attended_match_count"] for item in matches.values())),
        "verified_match_count": verified_match_count,
        "candidate_match_count": candidate_match_count,
    }


def _resolve_pre_demo_company_refs(
    refs: list[str] | None,
    scope: dict[str, Any],
    limit: int,
) -> dict[str, Any]:
    selected_refs = list(refs or [])
    selected_refs = selected_refs[:limit]
    resolved_ids: list[str] = []
    resolved_matches: list[dict[str, Any]] = []
    ambiguous_matches: list[dict[str, Any]] = []
    not_found: list[dict[str, Any]] = []

    for ref in selected_refs:
        company_id = _company_id_from_ref(ref)
        if company_id:
            if company_id not in resolved_ids:
                resolved_ids.append(company_id)
            resolved_matches.append({"input": str(ref), "company_id": company_id, "match_type": "id_or_link"})
            continue

        company_name = _company_name_ref(ref)
        if not company_name:
            not_found.append({"input": str(ref), "reason": "not a HubSpot company ID, company link, or usable company name"})
            continue

        match = _resolve_scoped_company_name(company_name, scope)
        if match["status"] == "resolved":
            company_id = str(match["company_id"])
            if company_id not in resolved_ids:
                resolved_ids.append(company_id)
            resolved_matches.append(match)
        elif match["status"] == "ambiguous":
            ambiguous_matches.append(match)
        else:
            not_found.append({"input": company_name, "reason": "no scoped HubSpot target-account match"})

    return {
        "company_ids": resolved_ids,
        "resolved_matches": resolved_matches,
        "ambiguous_matches": ambiguous_matches,
        "not_found": not_found,
        "input_count": len(refs or []),
        "processed_count": len(selected_refs),
        "truncated": len(refs or []) > limit,
    }


def _company_search(
    filters: list[dict[str, Any]],
    limit: int = 20,
    after: str | None = None,
    maximum: int = HUBSPOT_SEARCH_RESULT_LIMIT,
    sorts: list[dict[str, str]] | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    requested_limit = _bounded_int(limit, default=20, maximum=maximum)
    cleaned_query = str(query or "").strip()
    results: list[dict[str, Any]] = []
    total: int | None = None
    next_after = after

    while len(results) < requested_limit:
        page_limit = min(HUBSPOT_SEARCH_PAGE_LIMIT, requested_limit - len(results))
        body: dict[str, Any] = {
            "filterGroups": [{"filters": filters}],
            "properties": COMPANY_PROPERTIES,
            "limit": page_limit,
            "sorts": sorts or [{"propertyName": "notes_last_updated", "direction": "DESCENDING"}],
        }
        if cleaned_query:
            body["query"] = cleaned_query
        if next_after:
            body["after"] = next_after

        page = _post("/crm/v3/objects/companies/search", body)
        if total is None and page.get("total") is not None:
            total = _int_value(page.get("total"))

        page_results = page.get("results", [])
        results.extend(page_results)
        next_after = page.get("paging", {}).get("next", {}).get("after")
        if not page_results or not next_after:
            break

    returned_count = len(results)
    has_more = bool(next_after) or (total is not None and returned_count < total)
    return {
        "results": results,
        "total": total,
        "requested_limit": requested_limit,
        "returned_count": returned_count,
        "has_more": has_more,
        "truncated": has_more,
    }


def _deal_property_names() -> set[str]:
    global _DEAL_PROPERTY_NAMES_CACHE
    if _DEAL_PROPERTY_NAMES_CACHE is not None:
        return _DEAL_PROPERTY_NAMES_CACHE
    try:
        data = _get("/crm/v3/properties/deals")
        _DEAL_PROPERTY_NAMES_CACHE = {
            str(item.get("name") or "").strip()
            for item in data.get("results", [])
            if str(item.get("name") or "").strip()
        }
    except HubSpotError:
        _DEAL_PROPERTY_NAMES_CACHE = set(DEAL_PROPERTIES)
    return _DEAL_PROPERTY_NAMES_CACHE


def _available_deal_properties(properties: list[str] | tuple[str, ...]) -> list[str]:
    available = _deal_property_names()
    selected = [name for name in properties if name in available]
    for name in DEAL_PROPERTIES:
        if name not in selected:
            selected.append(name)
    return selected


def _deal_search(
    filters: list[dict[str, Any]],
    limit: int = 100,
    maximum: int = REVENUE_FUNNEL_DEAL_SCAN_LIMIT,
    properties: list[str] | None = None,
    sorts: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    requested_limit = _bounded_int(limit, default=100, maximum=maximum)
    results: list[dict[str, Any]] = []
    total: int | None = None
    next_after = ""
    read_properties = _available_deal_properties(properties or REVENUE_FUNNEL_DEAL_PROPERTIES)

    while len(results) < requested_limit:
        page_limit = min(HUBSPOT_SEARCH_PAGE_LIMIT, requested_limit - len(results))
        body: dict[str, Any] = {
            "filterGroups": [{"filters": filters}],
            "properties": read_properties,
            "limit": page_limit,
            "sorts": sorts or [{"propertyName": "createdate", "direction": "ASCENDING"}],
        }
        if next_after:
            body["after"] = next_after
        page = _post("/crm/v3/objects/deals/search", body)
        if total is None and page.get("total") is not None:
            total = _int_value(page.get("total"))
        page_results = page.get("results", [])
        results.extend(page_results)
        next_after = str(page.get("paging", {}).get("next", {}).get("after") or "")
        if not page_results or not next_after:
            break

    returned_count = len(results)
    has_more = bool(next_after) or (total is not None and returned_count < total)
    return {
        "results": results,
        "total": total,
        "requested_limit": requested_limit,
        "returned_count": returned_count,
        "has_more": has_more,
        "truncated": has_more,
        "properties": read_properties,
    }


def _object_search(
    object_type: str,
    filters: list[dict[str, Any]],
    properties: list[str],
    limit: int = 100,
    maximum: int = 500,
    sorts: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    requested_limit = _bounded_int(limit, default=100, maximum=maximum)
    results: list[dict[str, Any]] = []
    total: int | None = None
    next_after = ""

    while len(results) < requested_limit:
        page_limit = min(HUBSPOT_SEARCH_PAGE_LIMIT, requested_limit - len(results))
        body: dict[str, Any] = {
            "filterGroups": [{"filters": filters}],
            "properties": properties,
            "limit": page_limit,
            "sorts": sorts or [{"propertyName": "hs_timestamp", "direction": "ASCENDING"}],
        }
        if next_after:
            body["after"] = next_after
        page = _post(f"/crm/v3/objects/{object_type}/search", body)
        if total is None and page.get("total") is not None:
            total = _int_value(page.get("total"))
        page_results = page.get("results", [])
        results.extend(page_results)
        next_after = str(page.get("paging", {}).get("next", {}).get("after") or "")
        if not page_results or not next_after:
            break

    returned_count = len(results)
    has_more = bool(next_after) or (total is not None and returned_count < total)
    return {
        "results": results,
        "total": total,
        "requested_limit": requested_limit,
        "returned_count": returned_count,
        "has_more": has_more,
        "truncated": has_more,
    }


def _hubspot_date_filter_value(value: date, end_of_day: bool = False) -> str:
    day_time = datetime.max.time() if end_of_day else datetime.min.time()
    return str(int(datetime.combine(value, day_time, tzinfo=timezone.utc).timestamp() * 1000))


def _company_search_by_renewal_window(
    countries: list[str],
    owner_id: str | None,
    start_date: date,
    end_date: date,
    limit: int = HUBSPOT_SEARCH_TOTAL_LIMIT,
) -> dict[str, Any]:
    requested_limit = _bounded_int(limit, default=HUBSPOT_SEARCH_TOTAL_LIMIT, maximum=HUBSPOT_SEARCH_TOTAL_LIMIT)
    merged: dict[str, dict[str, Any]] = {}
    source_totals: dict[str, int | None] = {}
    source_returned_counts: dict[str, int] = {}
    source_truncated = False
    start_value = _hubspot_date_filter_value(start_date)
    end_value = _hubspot_date_filter_value(end_date)

    for property_name in RENEWAL_DATE_PROPERTIES:
        filters = [
            *_target_filters(countries, owner_id),
            {"propertyName": property_name, "operator": "GTE", "value": start_value},
            {"propertyName": property_name, "operator": "LTE", "value": end_value},
        ]
        data = _company_search(
            filters,
            requested_limit,
            maximum=HUBSPOT_SEARCH_TOTAL_LIMIT,
            sorts=[{"propertyName": property_name, "direction": "ASCENDING"}],
        )
        source_totals[property_name] = data.get("total")
        source_returned_counts[property_name] = data.get("returned_count", len(data.get("results", [])))
        source_truncated = source_truncated or bool(data.get("truncated"))

        for company in data.get("results", []):
            company_id = str(company.get("id") or "")
            if not company_id:
                continue
            if company_id not in merged:
                copied = dict(company)
                copied["_renewal_match_fields"] = []
                merged[company_id] = copied
            match_fields = merged[company_id].setdefault("_renewal_match_fields", [])
            if property_name not in match_fields:
                match_fields.append(property_name)

    results = list(merged.values())
    returned_results = results[:requested_limit]
    has_more = source_truncated or len(results) > requested_limit
    return {
        "results": returned_results,
        "total": None if has_more else len(results),
        "requested_limit": requested_limit,
        "returned_count": len(returned_results),
        "has_more": has_more,
        "truncated": has_more,
        "source_totals": source_totals,
        "source_returned_counts": source_returned_counts,
    }


def _company_search_missing_renewal_dates(
    countries: list[str],
    owner_id: str | None,
    limit: int = HUBSPOT_SEARCH_TOTAL_LIMIT,
) -> dict[str, Any]:
    requested_limit = _bounded_int(limit, default=HUBSPOT_SEARCH_TOTAL_LIMIT, maximum=HUBSPOT_SEARCH_TOTAL_LIMIT)
    filters = [
        *_target_filters(countries, owner_id),
        {"propertyName": RENEWAL_SOURCE_OF_TRUTH_PROPERTY, "operator": "NOT_HAS_PROPERTY"},
    ]
    return _company_search(filters, requested_limit, maximum=HUBSPOT_SEARCH_TOTAL_LIMIT)


def _task_search(
    filters: list[dict[str, Any]],
    limit: int = 50,
    after: str | None = None,
    maximum: int = TASK_SEARCH_RESULT_LIMIT,
) -> dict[str, Any]:
    requested_limit = _bounded_int(limit, default=50, maximum=maximum)
    results: list[dict[str, Any]] = []
    total: int | None = None
    next_after = after

    while len(results) < requested_limit:
        page_limit = min(HUBSPOT_SEARCH_PAGE_LIMIT, requested_limit - len(results))
        body: dict[str, Any] = {
            "filterGroups": [{"filters": filters}],
            "properties": TASK_PROPERTIES,
            "limit": page_limit,
            "sorts": [{"propertyName": "hs_timestamp", "direction": "ASCENDING"}],
        }
        if next_after:
            body["after"] = next_after

        page = _post("/crm/v3/objects/tasks/search", body)
        if total is None and page.get("total") is not None:
            total = _int_value(page.get("total"))

        page_results = page.get("results", [])
        results.extend(page_results)
        next_after = page.get("paging", {}).get("next", {}).get("after")
        if not page_results or not next_after:
            break

    returned_count = len(results)
    has_more = bool(next_after) or (total is not None and returned_count < total)
    return {
        "results": results,
        "total": total,
        "requested_limit": requested_limit,
        "returned_count": returned_count,
        "has_more": has_more,
        "truncated": has_more,
    }


def _task_datetime_filter_value(value: str, end_of_day: bool = False) -> str:
    parsed = _date_value(value)
    if not parsed:
        return value
    if "T" in value:
        return value
    suffix = "T23:59:59Z" if end_of_day else "T00:00:00Z"
    return f"{parsed.isoformat()}{suffix}"


def _task_search_filters(owner_id: str | None = None, due_start: str = "", due_end: str = "") -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = [
        {"propertyName": "hs_task_status", "operator": "NEQ", "value": "COMPLETED"},
    ]
    if owner_id:
        filters.append({"propertyName": "hubspot_owner_id", "operator": "EQ", "value": owner_id})
    if due_start:
        filters.append(
            {"propertyName": "hs_timestamp", "operator": "GTE", "value": _task_datetime_filter_value(due_start)}
        )
    if due_end:
        filters.append(
            {"propertyName": "hs_timestamp", "operator": "LTE", "value": _task_datetime_filter_value(due_end, True)}
        )
    return filters


def _target_filters(countries: list[str], owner_id: str | None = None) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = [
        {"propertyName": "hs_is_target_account", "operator": "EQ", "value": "true"},
        {"propertyName": "company_country", "operator": "IN", "values": countries},
    ]
    if owner_id:
        filters.append({"propertyName": "hubspot_owner_id", "operator": "EQ", "value": owner_id})
    return filters


def _normalize_domain_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    for prefix in ("https://", "http://"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text.split("/")[0]


def _normalize_company_name_key(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text or len(text) < 3 or len(text) > 80:
        return ""
    return text


def _unique_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value and value not in seen:
            unique.append(value)
            seen.add(value)
    return unique


def _add_luma_candidate(
    candidates: dict[str, dict[str, Any]],
    company: dict[str, Any],
    match_reason: str,
    match_key: str,
    confidence: str,
) -> None:
    company_id = str(company.get("id") or company.get("company_id") or "")
    if not company_id:
        return
    summary = candidates.setdefault(company_id, _summarize_luma_candidate_company(company))
    reasons = summary.setdefault("luma_match_reasons", [])
    if match_reason not in reasons:
        reasons.append(match_reason)
    key_kinds = summary.setdefault("luma_match_key_kinds", [])
    if match_reason not in key_kinds:
        key_kinds.append(match_reason)
    summary["luma_match_key_count"] = int(summary.get("luma_match_key_count") or 0) + 1
    if confidence == "needs-check":
        summary["luma_match_confidence"] = "needs-check"
    else:
        summary.setdefault("luma_match_confidence", "verified")
    candidates[company_id] = _compact_luma_candidate_summary(summary)


def _summarize_luma_candidate_company(company: dict[str, Any]) -> dict[str, Any]:
    props = company.get("properties", {})
    owner_id = props.get("hubspot_owner_id") or company.get("owner_id") or company.get("hubspot_owner_id") or ""
    account_status = _account_status_from_props(props)
    return {
        "company_id": company.get("id") or company.get("company_id") or "",
        "hubspot_scoped": True,
        "scope_source": SCOPE_SOURCE,
        "name": props.get("name") or company.get("name") or "",
        "domain": props.get("domain") or company.get("domain") or "",
        "country": props.get("company_country") or company.get("country") or company.get("company_country") or "",
        "owner_id": owner_id,
        "owner_email": company.get("owner_email") or _owner_email_by_id(owner_id),
        "owner_name": company.get("owner_name") or _owner_name_by_id(owner_id),
        **account_status,
    }


def _compact_luma_candidate_summary(summary: dict[str, Any]) -> dict[str, Any]:
    compact = {key: summary.get(key) for key in LUMA_MATCH_CANDIDATE_FIELDS}
    compact["hubspot_scoped"] = bool(compact.get("hubspot_scoped", True))
    compact["scope_source"] = compact.get("scope_source") or SCOPE_SOURCE
    compact["luma_match_reasons"] = list(compact.get("luma_match_reasons") or [])
    compact["luma_match_key_kinds"] = list(compact.get("luma_match_key_kinds") or [])
    compact["luma_match_key_count"] = int(compact.get("luma_match_key_count") or 0)
    compact["luma_match_confidence"] = compact.get("luma_match_confidence") or "verified"
    return compact


def _event_sourcing_owner_scope(
    scope: dict[str, Any],
    countries: list[str],
    owner_emails: list[str] | None = None,
    owner_names: list[str] | None = None,
) -> tuple[list[str], list[dict[str, str]], list[str]]:
    if scope.get("kind") not in {"admin", "manager", "event_operator"}:
        raise ScopeError("Event sourcing across AE accounts requires manager/admin or regional event-operator scope.")

    policy_owner_emails = _policy_owner_emails_for_countries(countries)
    if not policy_owner_emails:
        raise ScopeError("No classified sales-rep owners are available for the requested countries in the runtime access policy.")

    requested_emails = _normalize_owner_email_list(owner_emails)
    unresolved: list[str] = []
    selected_owner_emails: list[str] = []

    for owner_name in owner_names or []:
        try:
            identity = _owner_by_name(str(owner_name or ""))
            owner_email = _normalize_email(identity.get("email") or "")
        except MetricClarification:
            unresolved.append(str(owner_name or ""))
            continue
        if owner_email:
            requested_emails.append(owner_email)

    if requested_emails:
        allowed = set(policy_owner_emails)
        for owner_email in requested_emails:
            if owner_email not in allowed:
                unresolved.append(owner_email)
                continue
            if owner_email not in selected_owner_emails:
                selected_owner_emails.append(owner_email)
    else:
        selected_owner_emails = list(policy_owner_emails)

    owner_ids: list[str] = []
    owner_rows: list[dict[str, str]] = []
    for owner_email in selected_owner_emails:
        owner = _owner_by_email(owner_email)
        owner_id = str((owner or {}).get("id") or "").strip()
        if not owner_id:
            unresolved.append(owner_email)
            continue
        if owner_id not in owner_ids:
            owner_ids.append(owner_id)
            owner_rows.append(
                {
                    "owner_id": owner_id,
                    "owner_email": owner_email,
                    "owner_name": _owner_name(owner or {}),
                }
            )

    return owner_ids, owner_rows, unresolved


def _event_sourcing_target_filters(
    countries: list[str],
    owner_ids: list[str],
    headcount_min: int,
    headcount_max: int,
) -> list[dict[str, Any]]:
    filters = _target_filters(countries)
    if owner_ids:
        filters.append(
            {"propertyName": "hubspot_owner_id", "operator": "IN", "values": owner_ids}
            if len(owner_ids) > 1
            else {"propertyName": "hubspot_owner_id", "operator": "EQ", "value": owner_ids[0]}
        )
    if headcount_min > 0:
        filters.append({"propertyName": "numberofemployees", "operator": "GTE", "value": str(headcount_min)})
    if headcount_max > 0:
        filters.append({"propertyName": "numberofemployees", "operator": "LTE", "value": str(headcount_max)})
    return filters


def _event_industry_matches(company: dict[str, Any], industry: str) -> bool:
    requested = _normalized_words(industry)
    if not requested:
        return True
    if requested in {"f b", "fnb", "food beverage", "food and beverage", "food beverages"}:
        return _fnb_retail_company(company)
    props = company.get("properties", {})
    text = _normalized_words(" ".join([str(props.get("industry") or ""), str(props.get("name") or "")]))
    return requested in text or all(token in text for token in requested.split())


def _event_headcount_matches(company: dict[str, Any], headcount_min: int, headcount_max: int) -> bool:
    if headcount_min <= 0 and headcount_max <= 0:
        return True
    value = _int_value(company.get("properties", {}).get("numberofemployees"))
    if value <= 0:
        return False
    if headcount_min > 0 and value < headcount_min:
        return False
    if headcount_max > 0 and value > headcount_max:
        return False
    return True


def _event_deal_bucket(deals: list[dict[str, Any]]) -> dict[str, Any]:
    active = [deal for deal in deals if _deal_is_active_for_hygiene(deal)]
    return {
        "deal_bucket": "open_deal" if active else "no_open_deal",
        "open_deal_count": len(active),
        "associated_deal_count": len(deals),
    }


def _normalized_event_deal_bucket(value: str) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "": EVENT_SOURCING_DEFAULT_DEAL_BUCKET,
        "any": "any",
        "all": "any",
        "open": "open_deal",
        "ongoing": "open_deal",
        "open_deals": "open_deal",
        "ongoing_deals": "open_deal",
        "no_open": "no_open_deal",
        "none": "no_open_deal",
        "no_ongoing": "no_open_deal",
        "no_deal": "no_open_deal",
        "no_open_deal": "no_open_deal",
        "open_or_none": "open_or_none",
        "ongoing_or_no_ongoing": "open_or_none",
        "open_or_no_open": "open_or_none",
    }
    return aliases.get(normalized, EVENT_SOURCING_DEFAULT_DEAL_BUCKET)


def _event_deal_bucket_allowed(actual_bucket: str, requested_bucket: str) -> bool:
    if requested_bucket in {"any", "open_or_none"}:
        return actual_bucket in {"open_deal", "no_open_deal"}
    return actual_bucket == requested_bucket


def _event_contact_role_summary(contacts: list[dict[str, Any]]) -> dict[str, Any]:
    owner_contacts = []
    hr_contacts = []
    verified_decision_makers = []
    for contact in contacts:
        role_text = _normalized_words(" ".join([str(contact.get("persona") or ""), str(contact.get("buying_role") or "")]))
        padded = f" {role_text} "
        is_verified_dm = bool(contact.get("is_verified_decision_maker"))
        is_owner = is_verified_dm or _role_is_decision_maker(str(contact.get("persona") or ""))
        is_hr = any(
            marker in padded
            for marker in (
                " hr ",
                " human resource ",
                " human resources ",
                " people ",
                " talent ",
                " payroll ",
                " admin ",
            )
        )
        if is_owner:
            owner_contacts.append(contact)
        if is_hr:
            hr_contacts.append(contact)
        if is_verified_dm:
            verified_decision_makers.append(contact)
    return {
        "owner_contact_count": len(owner_contacts),
        "hr_contact_count": len(hr_contacts),
        "verified_decision_maker_count": len(verified_decision_makers),
        "associated_contact_count": len(contacts),
        "safe_contact_role_samples": [
            {
                "display_name": contact.get("display_name"),
                "persona": contact.get("persona"),
                "buying_role": contact.get("buying_role"),
                "decision_maker_confidence": contact.get("decision_maker_confidence"),
            }
            for contact in (owner_contacts + [item for item in hr_contacts if item not in owner_contacts])[:3]
        ],
    }


def _event_contact_role_allowed(summary: dict[str, Any], contact_role_filter: str) -> bool:
    normalized = str(contact_role_filter or "owner_or_hr").strip().lower()
    if normalized not in EVENT_SOURCING_CONTACT_ROLE_FILTERS:
        normalized = "owner_or_hr"
    if normalized == "any":
        return True
    if normalized == "owner":
        return int(summary.get("owner_contact_count") or 0) > 0
    if normalized == "hr":
        return int(summary.get("hr_contact_count") or 0) > 0
    return int(summary.get("owner_contact_count") or 0) > 0 or int(summary.get("hr_contact_count") or 0) > 0


def _luma_company_name_matches(company_name: str, candidate_name: str) -> bool:
    company_norm = _normalize_name(company_name)
    candidate_norm = _normalize_name(candidate_name)
    if not company_norm or not candidate_norm:
        return False
    if company_norm == candidate_norm:
        return True
    if len(candidate_norm) >= 5 and candidate_norm in company_norm:
        return True
    if len(company_norm) >= 5 and company_norm in candidate_norm:
        return True
    return False


def _target_owner_id_for_scope(scope: dict[str, Any], owner_email: str | None = None) -> tuple[str | None, str]:
    target_email = _normalize_email(owner_email or "")
    if scope.get("kind") == "event_operator":
        raise ScopeError(EVENT_OPERATOR_BLOCK_MESSAGE)
    if not target_email:
        return (str(scope["owner_id"]), scope["email"]) if scope["kind"] == "ae" and scope.get("owner_id") else (None, "")

    owner = _owner_by_email(target_email)
    if not owner:
        raise ScopeError(f"HubSpot owner not found for {target_email}.")

    owner_id = str(owner["id"])
    if scope["kind"] == "ae" and owner_id != scope.get("owner_id"):
        raise ScopeError("Caller is not authorized to inspect another owner's target accounts.")
    if scope["kind"] not in TEAM_READ_SCOPE_KINDS | {"ae"}:
        raise ScopeError("Caller identity is not mapped to an allowed scope.")
    return owner_id, target_email


def _target_owner_id_for_luma_match_scope(
    scope: dict[str, Any],
    countries: list[str],
    owner_email: str | None = None,
) -> tuple[str | None, str]:
    if scope.get("kind") != "event_operator":
        return _target_owner_id_for_scope(scope, owner_email)

    target_email = _normalize_email(owner_email or "")
    if not target_email:
        return None, ""

    allowed_owner_emails = set(_policy_owner_emails_for_countries(countries))
    if target_email not in allowed_owner_emails:
        raise ScopeError("Regional event operators may filter only to classified in-country AE owners.")

    owner = _owner_by_email(target_email)
    if not owner:
        raise ScopeError(f"HubSpot owner not found for {target_email}.")
    return str(owner["id"]), target_email


def _metric_needs_check(message: str, scope: dict[str, Any] | None = None, metric: str = "") -> dict[str, Any]:
    answer: dict[str, Any] = {
        "requires_clarification": True,
        "sql": "",
        "execute_with": BIGQUERY_EXECUTION_TOOL,
    }
    if metric:
        answer["metric"] = metric
    if metric in {"new_arr", "new ARR"}:
        answer["clarification_options"] = AMBIGUOUS_NEW_ARR_OPTIONS
    return {
        "answer": answer,
        "source": SALES_METRIC_SQL_SOURCE,
        "scope": scope or {},
        "confidence": "needs-check",
        "caveat": message,
    }


def _sql_string(value: Any) -> str:
    return "'" + str(value or "").replace("'", "''") + "'"


def _sql_string_list(values: list[Any]) -> str:
    return ", ".join(_sql_string(value) for value in values)


def _iso_date(value: str, field_name: str) -> str:
    parsed = _date_value(value)
    if not parsed:
        raise MetricClarification(f"{field_name} must be an ISO date, for example 2026-04-01.")
    return parsed.isoformat()


def _date_range(start_date: str, end_date: str) -> tuple[str, str]:
    start_iso = _iso_date(start_date, "start_date")
    end_iso = _iso_date(end_date, "end_date")
    if date.fromisoformat(start_iso) > date.fromisoformat(end_iso):
        raise MetricClarification("start_date must be on or before end_date.")
    return start_iso, end_iso


def _safe_metric(metric: str) -> str:
    normalized = str(metric or "").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "qo": "qo_set",
        "qualified_opportunity": "qo_set",
        "new_arr": "new_arr",
    }
    return aliases.get(normalized, normalized)


def _safe_grain(grain: str) -> str:
    normalized = str(grain or "total").strip().lower()
    if normalized not in {"total", "daily", "weekly", "monthly"}:
        raise MetricClarification("grain must be one of total, daily, weekly, or monthly.")
    return normalized


def _period_expression(date_expression: str, grain: str, start_iso: str) -> str:
    if grain == "daily":
        return date_expression
    if grain == "weekly":
        return f"DATE_TRUNC({date_expression}, WEEK(MONDAY))"
    if grain == "monthly":
        return f"DATE_TRUNC({date_expression}, MONTH)"
    return f"DATE '{start_iso}'"


def _owner_identity(owner: dict[str, Any]) -> dict[str, str]:
    return {
        "owner_id": str(owner.get("id") or "").strip(),
        "owner_email": _normalize_email(str(owner.get("email") or "")),
        "owner_name": _owner_name(owner),
    }


def _owner_by_name(owner_name: str) -> dict[str, Any]:
    target = str(owner_name or "").strip().lower()
    if not target:
        raise MetricClarification("owner_name was empty.")
    exact_matches = []
    partial_matches = []
    for owner in _list_owners():
        owner_identity = _owner_identity(owner)
        haystacks = {
            owner_identity["owner_name"].lower(),
            owner_identity["owner_email"].lower(),
            owner_identity["owner_email"].split("@")[0].replace(".", " ").lower(),
        }
        if target in haystacks:
            exact_matches.append(owner)
        elif any(target in value for value in haystacks if value):
            partial_matches.append(owner)
    matches = exact_matches or partial_matches
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        candidates = ", ".join(
            _owner_identity(owner)["owner_email"] or _owner_identity(owner)["owner_name"] for owner in matches[:5]
        )
        raise MetricClarification(f"Owner name is ambiguous. Use owner_email. Candidate matches: {candidates}.")
    raise MetricClarification(f"HubSpot owner not found for owner_name={owner_name}. Use owner_email if possible.")


def _policy_owner_emails_for_countries(countries: list[str]) -> list[str]:
    policy = _access_policy()
    selected = set(countries)
    emails: list[str] = []
    for rep in policy["sales_reps"].values():
        rep_countries = set(rep.get("countries") or ())
        owner_email = _normalize_email(rep.get("hubspot_owner_email") or "")
        if owner_email and rep_countries.intersection(selected) and owner_email not in emails:
            emails.append(owner_email)
    return emails


def _owner_ids_for_policy_countries(countries: list[str]) -> list[str]:
    owner_ids: list[str] = []
    for owner_email in _policy_owner_emails_for_countries(countries):
        owner = _owner_by_email(owner_email)
        owner_id = str((owner or {}).get("id") or "").strip()
        if owner_id and owner_id not in owner_ids:
            owner_ids.append(owner_id)
    return owner_ids


def _manager_can_query_owner(scope: dict[str, Any], owner_email: str, countries: list[str]) -> bool:
    if scope.get("kind") not in {"manager", "partnerships_viewer"}:
        return True
    return _normalize_email(owner_email) in _policy_owner_emails_for_countries(countries)


def _resolve_requested_owner(
    scope: dict[str, Any],
    countries: list[str],
    owner_email: str | None,
    owner_name: str | None,
) -> dict[str, str] | None:
    if scope.get("kind") == "event_operator":
        raise ScopeError(EVENT_OPERATOR_BLOCK_MESSAGE)
    if owner_email and owner_name:
        raise MetricClarification("Provide only one owner selector: owner_email or owner_name.")
    if owner_email:
        owner = _owner_by_email(owner_email)
        if not owner:
            raise MetricClarification(f"HubSpot owner not found for {owner_email}.")
    elif owner_name:
        owner = _owner_by_name(owner_name)
    elif scope.get("kind") == "ae" and scope.get("owner_id"):
        owner = _owner_by_id(scope["owner_id"])
        if not owner:
            raise MetricClarification("Caller owner ID could not be resolved to a HubSpot owner.")
    else:
        return None

    identity = _owner_identity(owner)
    if scope.get("kind") == "ae" and identity["owner_id"] != str(scope.get("owner_id") or ""):
        raise ScopeError("Caller is not authorized to inspect another owner's revenue metrics.")
    if not _manager_can_query_owner(scope, identity["owner_email"], countries):
        raise ScopeError("Requested owner is outside the manager's runtime access-policy country scope.")
    return identity


def _qo_sql(start_iso: str, end_iso: str, grain: str, owner_ids: list[str] | None = None) -> str:
    period = _period_expression("activity_date", grain, start_iso)
    filters = [f"activity_date BETWEEN DATE '{start_iso}' AND DATE '{end_iso}'"]
    if owner_ids:
        filters.append(f"CAST(hubspot_owner_id AS STRING) IN ({_sql_string_list(owner_ids)})")
    where_sql = "\n  AND ".join(filters)
    return f"""SELECT
  'qo_set' AS metric,
  {period} AS period_start,
  SUM(qo_set) AS metric_value,
  COUNT(DISTINCT CAST(hubspot_owner_id AS STRING)) AS owner_count
FROM `staffany-warehouse.analytics.fct_sales_points`
WHERE {where_sql}
GROUP BY metric, period_start
ORDER BY period_start"""


def _converted_arr_sql(
    metric: str,
    start_iso: str,
    end_iso: str,
    grain: str,
    countries: list[str],
    owner_names: list[str] | None = None,
) -> str:
    date_expr = "DATE(deal_contract_signed_date)" if metric == "signed_converted_arr" else "DATE(deal_paid_date)"
    period = _period_expression(date_expr, grain, start_iso)
    filters = [
        f"{date_expr} BETWEEN DATE '{start_iso}' AND DATE '{end_iso}'",
        f"company_country IN ({_sql_string_list(countries)})",
    ]
    if owner_names:
        filters.append(f"LOWER(deal_owner_name) IN ({_sql_string_list([name.lower() for name in owner_names])})")
    where_sql = "\n  AND ".join(filters)
    return f"""SELECT
  {_sql_string(metric)} AS metric,
  {period} AS period_start,
  SUM({metric}) AS metric_value,
  COUNT(DISTINCT deal_id) AS deal_count
FROM `staffany-warehouse.analytics.fct_deal_metrics_with_pilot_conversion`
WHERE {where_sql}
GROUP BY metric, period_start
ORDER BY period_start"""


def _movement_arr_sql(metric: str, start_iso: str, end_iso: str, grain: str, countries: list[str]) -> str:
    period = _period_expression("event_date", grain, start_iso)
    filters = [
        f"event_date BETWEEN DATE '{start_iso}' AND DATE '{end_iso}'",
        f"company_country IN ({_sql_string_list(countries)})",
    ]
    if metric == "new_mrr_movement_arr":
        filters.append("movement_type = 'New'")
    where_sql = "\n  AND ".join(filters)
    return f"""SELECT
  {_sql_string(metric)} AS metric,
  {period} AS period_start,
  SUM(mrr_change_amount * 12) AS metric_value,
  COUNT(DISTINCT company_id) AS company_count
FROM `staffany-warehouse.analytics.fct_mrr_movements`
WHERE {where_sql}
GROUP BY metric, period_start
ORDER BY period_start"""


def _snapshot_sql(metric: str, snapshot_month: str, countries: list[str]) -> str:
    metric_column = "total_arr" if metric == "current_arr" else "total_mrr"
    country_filter = f"company_country IN ({_sql_string_list(countries)})"
    if snapshot_month:
        snapshot_iso = _iso_date(snapshot_month, "snapshot_month")
        snapshot_predicate = f"snapshot_month = DATE '{snapshot_iso}'"
    else:
        snapshot_predicate = (
            "snapshot_month = "
            "(SELECT MAX(snapshot_month) FROM `staffany-warehouse.analytics.fct_company_revenue_snapshot`)"
        )
    return f"""SELECT
  {_sql_string(metric)} AS metric,
  snapshot_month AS period_start,
  SUM({metric_column}) AS metric_value,
  COUNT(DISTINCT company_id) AS company_count
FROM `staffany-warehouse.analytics.fct_company_revenue_snapshot`
WHERE {snapshot_predicate}
  AND {country_filter}
GROUP BY metric, period_start
ORDER BY period_start"""


def _metric_query_package(
    metric: str,
    sql: str,
    scope_response: dict[str, Any],
    grain: str,
    start_date: str = "",
    end_date: str = "",
    snapshot_month: str = "",
) -> dict[str, Any]:
    return {
        "metric": metric,
        "metric_definition": SALES_METRIC_DEFINITIONS[metric],
        "source_table": SALES_METRIC_TABLES[metric],
        "source_class": SALES_METRIC_SOURCE_CLASS,
        "execute_with": BIGQUERY_EXECUTION_TOOL,
        "sql": sql,
        "expected_output": "Aggregate metric rows only; no raw deal, contact, attendee, or company rows.",
        "time_grain": grain,
        "start_date": start_date,
        "end_date": end_date,
        "snapshot_month": snapshot_month,
        "scope": scope_response,
    }


def _period_range(start_date: str, end_date: str, field_name: str = "start_date") -> tuple[date, date]:
    start = _date_value(start_date)
    end = _date_value(end_date)
    if not start or not end:
        raise ScopeError(f"{field_name} and end_date must be ISO dates.")
    if start > end:
        raise ScopeError("start_date must be on or before end_date.")
    return start, end


def _deal_prop(deal: dict[str, Any], names: tuple[str, ...] | list[str]) -> str:
    props = deal.get("properties", {})
    for name in names:
        value = props.get(name)
        if value not in (None, ""):
            return str(value)
    return ""


def _deal_created_date(deal: dict[str, Any]) -> date | None:
    return _date_value(str(deal.get("properties", {}).get("createdate") or ""))


def _deal_amount(deal: dict[str, Any]) -> float:
    return _number_value(deal.get("properties", {}).get("amount"))


def _manual_correction_index(manual_corrections: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    corrections: dict[str, dict[str, Any]] = {}
    for item in manual_corrections or []:
        if not isinstance(item, dict):
            continue
        deal_id = str(item.get("deal_id") or "").strip()
        if deal_id:
            corrections[deal_id] = item
    return corrections


def _normal_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "hit"}


def _selected_revenue_channels(appointment_set_channel: str, include_all_outbound: bool) -> set[str]:
    normalized = _normalized_words(appointment_set_channel)
    if include_all_outbound or normalized in {"all outbound", "outbound", "all_outbound"}:
        return {"all_outbound"}
    if not normalized or normalized in {"sales outbound", "sales_outbound"}:
        return set(REVENUE_FUNNEL_SALES_OUTBOUND_VALUES)
    return {normalized}


def _deal_channel_matches(deal: dict[str, Any], selected_channels: set[str]) -> tuple[bool, str, str]:
    channel = _deal_prop(deal, REVENUE_FUNNEL_CHANNEL_PROPERTIES)
    normalized = _normalized_words(channel)
    if not selected_channels:
        return True, channel, ""
    if not normalized:
        return False, channel, "missing appointment-set channel property"
    if "all_outbound" in selected_channels:
        return any(marker in normalized for marker in REVENUE_FUNNEL_ALL_OUTBOUND_MARKERS), channel, ""
    return normalized in selected_channels, channel, ""


def _deal_is_renewal(deal: dict[str, Any]) -> bool:
    props = deal.get("properties", {})
    pipeline = str(props.get("pipeline") or "")
    if pipeline and pipeline in _env_csv(REVENUE_FUNNEL_RENEWAL_PIPELINE_IDS_ENV_VAR):
        return True
    text = _normalized_words(
        " ".join(
            [
                str(props.get("dealname") or ""),
                _deal_prop(deal, REVENUE_FUNNEL_BUSINESS_TYPE_PROPERTIES),
            ]
        )
    )
    return any(marker in text for marker in ("renewal", "renew", "upsell renewal"))


def _deal_is_new_business(deal: dict[str, Any]) -> tuple[bool, str]:
    props = deal.get("properties", {})
    pipeline = str(props.get("pipeline") or "")
    new_business_pipelines = _env_csv(REVENUE_FUNNEL_NEW_BUSINESS_PIPELINE_IDS_ENV_VAR)
    if new_business_pipelines:
        return pipeline in new_business_pipelines, ""
    business_type = _normalized_words(_deal_prop(deal, REVENUE_FUNNEL_BUSINESS_TYPE_PROPERTIES))
    if business_type:
        return "new" in business_type and "renew" not in business_type, ""
    return not _deal_is_renewal(deal), "new-business pipeline env missing; used renewal exclusion only"


def _company_headcount(company: dict[str, Any] | None) -> int:
    if not company:
        return 0
    return _int_value(company.get("properties", {}).get("numberofemployees"))


def _headcount_range_bounds(headcount_range: str, headcount_min: int, headcount_max: int) -> tuple[int, int]:
    text = str(headcount_range or "").strip().lower()
    if text in {">20", "20+", "gt20", "above20", "over20"}:
        return 21, 0
    if text in {"20-50", "20 to 50"}:
        return 20, 50
    if text in {"50+", ">50", "above50", "over50"}:
        return 51, 0
    if "-" in text:
        left, right = text.split("-", 1)
        return _int_value(left), _int_value(right)
    return _int_value(headcount_min), _int_value(headcount_max)


def _headcount_matches(company: dict[str, Any] | None, headcount_range: str, headcount_min: int, headcount_max: int) -> tuple[bool, str]:
    lower, upper = _headcount_range_bounds(headcount_range, headcount_min, headcount_max)
    if lower <= 0 and upper <= 0:
        return True, ""
    headcount = _company_headcount(company)
    if headcount <= 0:
        return False, "missing company headcount"
    if lower > 0 and headcount < lower:
        return False, ""
    if upper > 0 and headcount > upper:
        return False, ""
    return True, ""


def _industry_matches(company: dict[str, Any] | None, industries: list[str] | None) -> bool:
    selected = [_normalized_words(industry) for industry in (industries or []) if _normalized_words(industry)]
    if not selected:
        return True
    text = _normalized_words((company or {}).get("properties", {}).get("industry") or "")
    return bool(text and any(industry in text or text in industry for industry in selected))


def _deal_counted_as_qo(deal: dict[str, Any], stage_config: dict[str, Any], correction: dict[str, Any] | None = None) -> bool:
    if correction and "count_as_qo" in correction:
        return _normal_bool(correction.get("count_as_qo"), False)
    stage = str(deal.get("properties", {}).get("dealstage") or "")
    return bool(
        stage
        and (
            stage in stage_config.get("qo_stage_ids", set())
            or stage in stage_config.get("qo_met_stage_ids", set())
            or stage in stage_config.get("closed_won_stage_ids", set())
        )
    )


def _deal_counted_as_qo_met(deal: dict[str, Any], stage_config: dict[str, Any], correction: dict[str, Any] | None = None) -> bool:
    if correction and "count_as_qo_met" in correction:
        return _normal_bool(correction.get("count_as_qo_met"), False)
    stage = str(deal.get("properties", {}).get("dealstage") or "")
    return bool(stage and (stage in stage_config.get("qo_met_stage_ids", set()) or stage in stage_config.get("closed_won_stage_ids", set())))


def _deal_counted_as_signed(deal: dict[str, Any], stage_config: dict[str, Any], correction: dict[str, Any] | None = None) -> bool:
    if correction and "count_as_signed" in correction:
        return _normal_bool(correction.get("count_as_signed"), False)
    stage = str(deal.get("properties", {}).get("dealstage") or "")
    return bool(stage and stage in stage_config.get("closed_won_stage_ids", set()))


def _days_to_signed(deal: dict[str, Any]) -> int | None:
    created = _date_value(str(deal.get("properties", {}).get("createdate") or ""))
    closed = _date_value(str(deal.get("properties", {}).get("closedate") or ""))
    if not created or not closed or closed < created:
        return None
    return (closed - created).days


def _pct(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round((numerator / denominator) * 100, 1)


def _safe_revenue_deal_audit_row(
    deal: dict[str, Any],
    company: dict[str, Any] | None,
    stage_config: dict[str, Any],
    correction: dict[str, Any] | None,
    channel: str,
    caveats: list[str],
) -> dict[str, Any]:
    props = deal.get("properties", {})
    company_props = (company or {}).get("properties", {})
    signed_amount = correction.get("signed_amount") if correction and correction.get("signed_amount") not in (None, "") else _deal_amount(deal)
    return {
        "deal_id": str(deal.get("id") or ""),
        "deal_name": _safe_activity_label(props.get("dealname"), 120),
        "createdate": props.get("createdate") or "",
        "closedate": props.get("closedate") or "",
        "pipeline": props.get("pipeline") or "",
        "dealstage": props.get("dealstage") or "",
        "owner_id": props.get("hubspot_owner_id") or "",
        "company_id": str((company or {}).get("id") or ""),
        "company_name": company_props.get("name") or "",
        "country": company_props.get("company_country") or "",
        "headcount": company_props.get("numberofemployees") or "",
        "industry": company_props.get("industry") or "",
        "appointment_set_channel": channel,
        "count_as_qo": _deal_counted_as_qo(deal, stage_config, correction),
        "count_as_qo_met": _deal_counted_as_qo_met(deal, stage_config, correction),
        "count_as_signed": _deal_counted_as_signed(deal, stage_config, correction),
        "signed_amount": signed_amount if _deal_counted_as_signed(deal, stage_config, correction) else 0,
        "manual_correction_applied": bool(correction),
        "caveats": caveats,
    }


def _revenue_funnel_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    created = len(rows)
    qos = sum(1 for row in rows if row.get("count_as_qo"))
    qo_met = sum(1 for row in rows if row.get("count_as_qo_met"))
    signed = sum(1 for row in rows if row.get("count_as_signed"))
    signed_amount = round(sum(_number_value(row.get("signed_amount")) for row in rows), 2)
    return {
        "created_deal_count": created,
        "qo_count": qos,
        "qo_met_count": qo_met,
        "signed_deal_count": signed,
        "created_to_qo_pct": _pct(qos, created),
        "qo_to_qo_met_pct": _pct(qo_met, qos),
        "qo_to_signed_pct": _pct(signed, qos),
        "signed_amount": signed_amount,
    }


def _parse_local_time(value: Any, default: str) -> datetime_time:
    text = str(value or default).strip().lower().replace(" ", "")
    text = text.replace(".", "")
    if not text:
        text = default
    suffix = ""
    if text.endswith(("am", "pm")):
        suffix = text[-2:]
        text = text[:-2]
    if re.fullmatch(r"\d{3,4}", text):
        hour_text = text[:-2]
        minute_text = text[-2:]
    else:
        parts = text.split(":", 1)
        hour_text = parts[0]
        minute_text = parts[1] if len(parts) > 1 else "00"
    try:
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError as error:
        raise ScopeError(f"Invalid WhatsApp local window time: {value}") from error
    if suffix == "pm" and hour != 12:
        hour += 12
    if suffix == "am" and hour == 12:
        hour = 0
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ScopeError(f"Invalid WhatsApp local window time: {value}")
    return datetime_time(hour, minute)


def _time_label(value: datetime_time) -> str:
    return f"{value.hour:02d}:{value.minute:02d}"


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _coaching_timezone_overrides(overrides: dict[str, str] | None) -> dict[str, str]:
    if not isinstance(overrides, dict):
        return {}
    normalized: dict[str, str] = {}
    for owner_email, timezone_name in overrides.items():
        email = _normalize_email(str(owner_email or ""))
        tz_name = str(timezone_name or "").strip()
        if email and tz_name:
            normalized[email] = tz_name
    return normalized


def _policy_timezone_for_owner_email(owner_email: str) -> str:
    normalized_owner_email = _normalize_email(owner_email)
    if not normalized_owner_email:
        return ""
    try:
        policy = _access_policy()
    except AccessPolicyError:
        return ""
    for rep in policy.get("sales_reps", {}).values():
        if _normalize_email(rep.get("hubspot_owner_email") or "") == normalized_owner_email:
            return str(rep.get("timezone") or "").strip()
    return ""


def _coaching_timezone_for_owner(
    owner_email: str,
    timezone_override_by_owner_email: dict[str, str] | None = None,
) -> tuple[str, str]:
    normalized_owner_email = _normalize_email(owner_email)
    overrides = _coaching_timezone_overrides(timezone_override_by_owner_email)
    if normalized_owner_email in overrides:
        return overrides[normalized_owner_email], "override"
    policy_timezone = _policy_timezone_for_owner_email(normalized_owner_email)
    if policy_timezone:
        return policy_timezone, "access_policy"
    return "", "missing"


def _zoneinfo_or_none(timezone_name: str) -> ZoneInfo | None:
    if not timezone_name:
        return None
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return None


def _window_bounds_for_timestamp(
    timestamp: datetime,
    zone: ZoneInfo,
    start_time: datetime_time,
    end_time: datetime_time,
) -> tuple[datetime, datetime]:
    local = timestamp.astimezone(zone)
    start_local = datetime.combine(local.date(), start_time, tzinfo=zone)
    end_local = datetime.combine(local.date(), end_time, tzinfo=zone)
    if end_local <= start_local:
        if local < end_local:
            start_local -= timedelta(days=1)
        else:
            end_local += timedelta(days=1)
    return start_local, end_local


def _coaching_window_contract(
    owner_email: str,
    timezone_override_by_owner_email: dict[str, str] | None,
    whatsapp_window_start_local: str,
    whatsapp_window_end_local: str,
    reference_date: str = "",
) -> dict[str, Any]:
    start_time = _parse_local_time(whatsapp_window_start_local, AE_COACHING_DEFAULT_WINDOW_START)
    end_time = _parse_local_time(whatsapp_window_end_local, AE_COACHING_DEFAULT_WINDOW_END)
    timezone_name, timezone_source = _coaching_timezone_for_owner(owner_email, timezone_override_by_owner_email)
    zone = _zoneinfo_or_none(timezone_name)
    parsed_reference_date = _date_value(reference_date) or datetime.now(timezone.utc).date()
    local_window = {
        "start": _time_label(start_time),
        "end": _time_label(end_time),
        "timezone": timezone_name,
    }
    utc_window: dict[str, str] | None = None
    if zone:
        start_local = datetime.combine(parsed_reference_date, start_time, tzinfo=zone)
        end_local = datetime.combine(parsed_reference_date, end_time, tzinfo=zone)
        if end_local <= start_local:
            end_local += timedelta(days=1)
        utc_window = {"start": _utc_iso(start_local), "end": _utc_iso(end_local)}
    elif timezone_name:
        timezone_source = "invalid"
    return {
        "timezone": timezone_name,
        "timezone_source": timezone_source,
        "zone": zone,
        "start_time": start_time,
        "end_time": end_time,
        "local_window": local_window,
        "utc_window": utc_window,
        "daily_nurture_plan_time_local": DAILY_NURTURE_PLAN_TIME_LOCAL,
    }


def _coaching_window_label(window: dict[str, Any]) -> str:
    local_window = window.get("local_window") or {}
    timezone_name = local_window.get("timezone") or "timezone-missing"
    return f"{local_window.get('start')}-{local_window.get('end')} {timezone_name}"


def _whatsapp_window_metrics(evidence_items: list[dict[str, Any]], window: dict[str, Any]) -> dict[str, Any]:
    zone = window.get("zone")
    timestamps: list[datetime] = []
    for evidence in evidence_items:
        if evidence.get("object_type") != "communication":
            continue
        timestamp = _datetime_value(str(evidence.get("timestamp") or ""))
        if timestamp:
            timestamps.append(timestamp)
    timestamps.sort()
    if not zone:
        return {
            "first_message_local": None,
            "in_window_message_count": 0,
            "late_by_minutes": None,
        }

    start_time = window["start_time"]
    end_time = window["end_time"]
    in_window_count = 0
    first_after_window: tuple[datetime, datetime] | None = None
    for timestamp in timestamps:
        start_local, end_local = _window_bounds_for_timestamp(timestamp, zone, start_time, end_time)
        local = timestamp.astimezone(zone)
        if start_local <= local <= end_local:
            in_window_count += 1
        elif local > end_local and first_after_window is None:
            first_after_window = (local, end_local)
    first_message_local = timestamps[0].astimezone(zone).isoformat() if timestamps else None
    late_by_minutes = 0 if in_window_count > 0 else None
    if in_window_count == 0 and first_after_window is not None:
        late_by_minutes = max(0, int((first_after_window[0] - first_after_window[1]).total_seconds() // 60))
    return {
        "first_message_local": first_message_local,
        "in_window_message_count": in_window_count,
        "late_by_minutes": late_by_minutes,
    }


def _is_morning_whatsapp(evidence: dict[str, Any], window: dict[str, Any] | None = None) -> bool:
    if evidence.get("object_type") != "communication":
        return False
    timestamp = _datetime_value(str(evidence.get("timestamp") or ""))
    if not timestamp:
        return False
    if window:
        zone = window.get("zone")
        if not zone:
            return False
        start_local, end_local = _window_bounds_for_timestamp(timestamp, zone, window["start_time"], window["end_time"])
        local = timestamp.astimezone(zone)
        return start_local <= local <= end_local
    local = timestamp.astimezone(SINGAPORE_TIMEZONE)
    return AE_COACHING_MORNING_START_HOUR <= local.hour < AE_COACHING_MORNING_END_HOUR


def _long_call_candidates_without_appointment(owner_id: str, companies: list[dict[str, Any]], activity_index: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    company_by_id = {str(company.get("id") or ""): company for company in companies}
    candidates: list[dict[str, Any]] = []
    for company_id, account_activity in activity_index.items():
        evidence = account_activity.get("evidence", [])
        has_completed_meeting = any(item.get("object_type") == "meeting" for item in evidence)
        for item in evidence:
            if item.get("object_type") != "call":
                continue
            if owner_id and str(item.get("owner_id") or "") != str(owner_id):
                continue
            duration_ms = _int_value(item.get("duration_seconds")) * 1000
            if duration_ms <= AE_COACHING_LONG_CALL_MIN_DURATION_MS or has_completed_meeting:
                continue
            company = company_by_id.get(str(company_id), {})
            props = company.get("properties", {})
            candidates.append(
                {
                    "company_id": str(company_id),
                    "company_name": props.get("name") or "",
                    "call_id": item.get("object_id"),
                    **({"aircall_call_id": item.get("aircall_call_id")} if item.get("aircall_call_id") else {}),
                    "call_at": item.get("timestamp"),
                    "duration_seconds": item.get("duration_seconds"),
                    "status": "needs-check",
                    "reason": "call >60s with no completed appointment/meeting evidence on this account in the audited week",
                    "call_content_status": "metadata-only",
                }
            )
    return candidates[:FRIDAY_REVIEW_DETAIL_LIMIT]


def _contact_role_priority(contact: dict[str, Any]) -> tuple[int, str]:
    text = _normalized_words(" ".join([str(contact.get("persona") or ""), str(contact.get("buying_role") or "")]))
    for marker, score in SALES_NAVIGATOR_ROLE_PRIORITY:
        if _normalized_words(marker) in text:
            return score, marker
    return 0, ""


def _fnb_retail_company(company: dict[str, Any]) -> bool:
    props = company.get("properties", {})
    text = _normalized_words(" ".join([str(props.get("industry") or ""), str(props.get("name") or "")]))
    return any(marker in text for marker in FNB_RETAIL_MARKERS)


def _account_status_from_props(props: dict[str, Any]) -> dict[str, str]:
    company_type = str(props.get("type") or "").strip().upper()
    lifecycle_stage = str(props.get("lifecyclestage") or "").strip().lower()
    prospecting = str(props.get("prospecting_account") or "").strip().lower()
    if company_type == "CUSTOMER" or lifecycle_stage == "customer":
        return {
            "account_status": "customer",
            "account_status_source": "HubSpot company type=CUSTOMER or lifecyclestage=customer",
        }
    if company_type == "PROSPECT":
        return {
            "account_status": "prospect",
            "account_status_source": "HubSpot company type=PROSPECT",
        }
    if lifecycle_stage in {"subscriber", "lead", "marketingqualifiedlead", "salesqualifiedlead", "opportunity"}:
        return {
            "account_status": "prospect",
            "account_status_source": f"HubSpot company lifecyclestage={lifecycle_stage}",
        }
    if prospecting == "true":
        return {
            "account_status": "prospect",
            "account_status_source": "HubSpot company prospecting_account=true",
        }
    return {
        "account_status": "unknown",
        "account_status_source": "HubSpot company type/lifecyclestage/prospecting_account did not classify customer vs prospect",
    }


def _c360_company_url_template() -> str:
    return _shared_c360_company_url_template()


def _c360_org_url_template() -> str:
    return _shared_c360_org_url_template()


def _c360_route_key_map() -> dict[str, str]:
    return _shared_c360_route_key_map()


def _customer360_route_key(
    hubspot_company_id: Any,
    company_name: Any = "",
    customer360_route_key: Any = "",
) -> str:
    return _shared_customer360_route_key(hubspot_company_id, company_name, customer360_route_key)


def _encode_url_value(value: Any) -> str:
    return _shared_encode_url_value(value)


def _render_c360_url(
    hubspot_company_id: Any,
    organisation_id: Any = "",
    customer360_route_key: Any = "",
    company_name: Any = "",
) -> str:
    return _shared_render_c360_url(
        hubspot_company_id,
        organisation_id,
        customer360_route_key_value=customer360_route_key,
        company_name=company_name,
    )


def _c360_sales_packet_url_template() -> str:
    template = os.environ.get(C360_SALES_PACKET_URL_TEMPLATE_ENV, "").strip()
    if template.startswith("${") and template.endswith("}"):
        template = ""
    return template or DEFAULT_C360_SALES_PACKET_URL_TEMPLATE


def _render_c360_sales_packet_url(company_summary: dict[str, Any]) -> str:
    route_key = str(company_summary.get("customer360_route_key") or "").strip()
    company_id = str(company_summary.get("company_id") or "").strip()
    company_name = str(company_summary.get("name") or "").strip()
    customer_key = _customer360_route_key(company_id, company_name, route_key) or company_id
    if not customer_key:
        return ""
    return _c360_sales_packet_url_template().format(
        customer360_route_key=_encode_url_value(customer_key),
        hubspot_company_id=_encode_url_value(customer_key),
        hubspot_numeric_company_id=_encode_url_value(company_id),
    )


def _fetch_c360_sales_packet(company_summary: dict[str, Any]) -> dict[str, Any]:
    if company_summary.get("account_status") != "customer":
        return {"status": "skipped", "reason": "not_current_customer"}

    packet_url = _render_c360_sales_packet_url(company_summary)
    if not packet_url:
        return {
            "status": "unavailable",
            "reason": "missing_route_key",
            "caveat": "C360 sales packet unavailable because the Customer 360 company identifier is missing.",
        }

    token = os.environ.get(C360_INTERNAL_API_TOKEN_ENV, "").strip()
    if not token:
        return {
            "status": "unavailable",
            "reason": "missing_token",
            "url": packet_url,
            "caveat": C360_SALES_PACKET_UNAVAILABLE_CAVEAT,
        }

    request = urllib.request.Request(
        packet_url,
        headers={
            "authorization": f"Bearer {token}",
            "accept": "application/json",
            "user-agent": "StaffAny-NurtureAny/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=C360_SALES_PACKET_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return {
            "status": "unavailable",
            "reason": f"http_{error.code}",
            "url": packet_url,
            "caveat": C360_SALES_PACKET_UNAVAILABLE_CAVEAT,
            "diagnostic": {"http_status": error.code},
        }
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        return {
            "status": "unavailable",
            "reason": "request_failed",
            "url": packet_url,
            "caveat": C360_SALES_PACKET_UNAVAILABLE_CAVEAT,
            "diagnostic": {"error_type": type(reason).__name__},
        }

    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {
            "status": "unavailable",
            "reason": "invalid_json",
            "url": packet_url,
            "caveat": C360_SALES_PACKET_UNAVAILABLE_CAVEAT,
        }

    packet = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(packet, dict):
        return {
            "status": "unavailable",
            "reason": "invalid_payload",
            "url": packet_url,
            "caveat": C360_SALES_PACKET_UNAVAILABLE_CAVEAT,
        }

    return {
        "status": "ok",
        "url": packet_url,
        "packet": packet,
    }


def _apply_c360_packet_company_link(company_summary: dict[str, Any], c360_packet_result: dict[str, Any]) -> None:
    packet = c360_packet_result.get("packet") if c360_packet_result.get("status") == "ok" else None
    if not isinstance(packet, dict) or company_summary.get("c360_url"):
        return
    c360_url = str(packet.get("c360Url") or "").strip()
    if not c360_url:
        return
    company_summary["c360_url"] = c360_url
    company_summary["customer360_url"] = c360_url


def _decision_maker_count_source(props: dict[str, Any]) -> dict[str, str]:
    return {
        "decision_maker_count_source": (
            "HubSpot company property hs_num_decision_makers: HubSpot count of associated contacts with buying role DECISION_MAKER."
        ),
        "buying_role_contact_count_source": (
            "HubSpot company property hs_num_contacts_with_buying_roles: HubSpot count of associated contacts with any buying role."
        ),
        "eazybe_note": (
            "NurtureAny does not read Eazybe directly for this count; if Eazybe updates HubSpot contact buying roles, that is upstream HubSpot data hygiene."
        ),
    }


def _has_decision_maker_buying_role(value: Any) -> bool:
    roles = re.split(r"[;,]", str(value or ""))
    return any(role.strip().upper() == "DECISION_MAKER" for role in roles)


def _contact_role_text(contact: dict[str, Any]) -> str:
    props = contact.get("properties", {})
    return str(contact.get("persona") or props.get("job_role") or props.get("jobtitle") or "")


def _contact_buying_role_text(contact: dict[str, Any]) -> str:
    props = contact.get("properties", {})
    return str(contact.get("buying_role") or props.get("hs_buying_role") or "")


def _decision_maker_coverage(
    props: dict[str, Any],
    contacts: list[dict[str, Any]] | None = None,
    contact_count: int | None = None,
) -> dict[str, Any]:
    safe_contacts = contacts or []
    associated_contact_count = len(safe_contacts) if contact_count is None and contacts is not None else contact_count
    hubspot_direct_count = _int_value(props.get("hs_num_decision_makers"))
    buying_role_contact_count = _int_value(props.get("hs_num_contacts_with_buying_roles"))
    verified_contacts = [
        contact
        for contact in safe_contacts
        if contact.get("is_verified_decision_maker") or _has_decision_maker_buying_role(_contact_buying_role_text(contact))
    ]
    role_candidates = [
        contact
        for contact in safe_contacts
        if not (contact.get("is_verified_decision_maker") or _has_decision_maker_buying_role(_contact_buying_role_text(contact)))
        and (contact.get("is_role_inferred_decision_maker") or _role_is_decision_maker(_contact_role_text(contact)))
    ]
    verified_count = max(hubspot_direct_count, len(verified_contacts))
    issues: list[str] = []
    if associated_contact_count == 0 and verified_count > 0:
        issues.append("company_rollup_has_decision_maker_but_no_associated_contact_returned")
    if buying_role_contact_count > 0 and verified_count == 0:
        issues.append("buying_role_contacts_exist_but_none_are_decision_maker")

    if issues:
        status = "needs-check"
    elif verified_count > 0:
        status = "verified"
    elif role_candidates:
        status = "needs-check"
    else:
        status = "missing"

    return {
        "associated_contact_count": associated_contact_count if associated_contact_count is not None else None,
        "verified_decision_maker_count": verified_count,
        "decision_maker_count": verified_count,
        "decision_maker_count_from_hubspot_property": hubspot_direct_count,
        "decision_maker_count_from_contact_buying_role": len(verified_contacts),
        "buying_role_contact_count": buying_role_contact_count,
        "role_inferred_decision_maker_candidate_count": len(role_candidates),
        "status": status,
        "confidence": "verified" if status == "verified" else "needs-check",
        "issues": issues,
        "sources": _decision_maker_count_source(props),
    }


def _calendar_scan_instruction(company_summary: dict[str, Any]) -> dict[str, Any]:
    owner_email = _normalize_email(str(company_summary.get("owner_email") or ""))
    if owner_email:
        calendar_ids = [owner_email]
        confidence = "verified"
        caveat = "Scan the HubSpot company owner's calendar through the team@staffany.com OAuth account."
    else:
        calendar_ids = []
        confidence = "blocked"
        caveat = "HubSpot owner email is missing, so AE calendar coverage cannot be scanned reliably."
    return {
        "calendar_account_email": "team@staffany.com",
        "calendar_ids": calendar_ids,
        "owner_email": owner_email,
        "owner_name": company_summary.get("owner_name") or "",
        "confidence": confidence,
        "caveat": caveat,
    }


def _calendar_audit_contact(contact: dict[str, Any]) -> dict[str, Any]:
    safe = _safe_contact(contact)
    props = contact.get("properties", {})
    email = _normalize_email(str(props.get("email") or ""))
    return {
        "contact_id": safe.get("contact_id"),
        "display_name": safe.get("display_name"),
        "persona": safe.get("persona"),
        "buying_role": safe.get("buying_role"),
        "is_verified_decision_maker": safe.get("is_verified_decision_maker"),
        "is_role_inferred_decision_maker": safe.get("is_role_inferred_decision_maker"),
        "decision_maker_confidence": safe.get("decision_maker_confidence"),
        "email_domain": _email_domain(email),
        "email_hash": _hash_email(email),
    }


def _calendar_audit_readiness(company_summary: dict[str, Any]) -> dict[str, str]:
    missing = set(company_summary.get("missing_fields") or [])
    decision_coverage = company_summary.get("decision_maker_coverage") or {}
    return {
        "authority": str(decision_coverage.get("status") or "needs-check"),
        "current_tools": "missing" if "current tools" in missing else "verified",
        "timeline": "missing" if "contract end date" in missing else "verified",
        "stakeholder_map": "missing" if "associated contact" in missing else "verified",
        "need": "needs-check",
    }


def _calendar_audit_seed(company_summary: dict[str, Any], contacts: list[dict[str, Any]]) -> dict[str, Any]:
    clean_lead_field_labels = {
        "industry": "industry",
        "headcount": "headcount",
        "current tools": "current tools",
        "current_tools": "current tools",
        "contract end date": "contract end date",
        "contract_end_date": "contract end date",
        "associated contact": "associated contact",
        "associated_contact": "associated contact",
        "decision maker": "verified decision maker",
        "verified_decision_maker": "verified decision maker",
    }
    missing_clean_lead_fields: list[str] = []
    for field in company_summary.get("missing_fields", []):
        label = clean_lead_field_labels.get(field)
        if label and label not in missing_clean_lead_fields:
            missing_clean_lead_fields.append(label)
    return {
        "company_id": company_summary.get("company_id"),
        "company_name": company_summary.get("name") or "",
        "company_domain": _clean_domain(str(company_summary.get("domain") or "")),
        "owner_email": company_summary.get("owner_email") or "",
        "owner_name": company_summary.get("owner_name") or "",
        "calendar_account_email": "team@staffany.com",
        "calendar_ids": list((company_summary.get("calendar_scan_instruction") or {}).get("calendar_ids") or []),
        "missing_clean_lead_fields": missing_clean_lead_fields,
        "decision_maker_coverage": company_summary.get("decision_maker_coverage") or {},
        "ic_bant_readiness": _calendar_audit_readiness(company_summary),
        "contact_match_records": [_calendar_audit_contact(contact) for contact in contacts],
        "privacy": "Email hashes/domains only; raw HubSpot contact emails are not returned.",
    }


def _summarize_company(company: dict[str, Any]) -> dict[str, Any]:
    props = company.get("properties", {})
    decision_coverage = _decision_maker_coverage(props)
    contract_date = props.get(RENEWAL_SOURCE_OF_TRUTH_PROPERTY) or ""
    owner_id = props.get("hubspot_owner_id") or ""
    company_id = company.get("id")
    resolved_domain = _clean_domain(props.get("domain") or props.get("website") or "")
    domain_source = "domain" if _clean_domain(props.get("domain") or "") else "website" if resolved_domain else ""
    account_status = _account_status_from_props(props)
    customer360_route_key = _customer360_route_key(
        company_id,
        props.get("name") or "",
        props.get("customer360_route_key") or props.get("customer_slug") or "",
    )
    c360_url = (
        _render_c360_url(company_id, customer360_route_key=customer360_route_key, company_name=props.get("name") or "")
        if account_status["account_status"] == "customer"
        else ""
    )
    owner = {
        "owner_id": owner_id,
        "owner_email": _owner_email_by_id(owner_id),
        "owner_name": _owner_name_by_id(owner_id),
    }
    summary = {
        "company_id": company_id,
        "hubspot_scoped": True,
        "scope_source": SCOPE_SOURCE,
        "name": props.get("name") or "",
        "domain": resolved_domain,
        "domain_source": domain_source,
        "website": props.get("website") or "",
        "country": props.get("company_country") or "",
        **owner,
        "headcount": props.get("numberofemployees") or "",
        "industry": props.get("industry") or "",
        "company_type": props.get("type") or "",
        "lifecycle_stage": props.get("lifecyclestage") or "",
        **account_status,
        "contract_end_date": props.get("contract_end_date") or "",
        "current_tool_renewal_date": props.get("current_tool_renewal_date") or "",
        "current_tools": props.get(CURRENT_TOOLS_SOURCE_OF_TRUTH_PROPERTY) or "",
        "contract_or_renewal_date": contract_date,
        "renewal_source_of_truth": RENEWAL_SOURCE_OF_TRUTH_PROPERTY,
        "current_tools_source_of_truth": CURRENT_TOOLS_SOURCE_OF_TRUTH_PROPERTY,
        "last_activity_at": props.get("notes_last_updated") or "",
        "decision_maker_count": decision_coverage["verified_decision_maker_count"],
        "verified_decision_maker_count": decision_coverage["verified_decision_maker_count"],
        "buying_role_contact_count": decision_coverage["buying_role_contact_count"],
        "role_inferred_decision_maker_candidate_count": decision_coverage["role_inferred_decision_maker_candidate_count"],
        "decision_maker_coverage": decision_coverage,
        **_decision_maker_count_source(props),
        "prospecting_account": props.get("prospecting_account") or "",
        "enrichment_status": _enrichment_status(props, contact_count=None),
        "missing_fields": _missing_company_fields(props, contact_count=None),
    }
    if c360_url:
        summary["c360_url"] = c360_url
        summary["customer360_url"] = c360_url
        summary["customer360_route_key"] = customer360_route_key
    elif account_status["account_status"] == "customer":
        summary["c360_link_status"] = "needs-route-key"
        summary["c360_link_caveat"] = "C360 link missing because Customer 360 route key was unavailable."
    return summary


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _number_value(value: Any) -> float:
    if isinstance(value, dict):
        for key in ("value", "total", "count"):
            if key in value:
                return _number_value(value.get(key))
        return 0.0
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _date_value(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


def _datetime_value(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        parsed_date = _date_value(text)
        if not parsed_date:
            return None
        parsed = datetime.combine(parsed_date, datetime.min.time(), tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _unique_text(values: list[Any]) -> list[str]:
    return _shared_unique_text(values)


def _normalized_words(value: str) -> str:
    return _shared_normalized_words(value)


def _text_contains_term(text: str, term: str) -> bool:
    normalized_text = f" {_normalized_words(text)} "
    normalized_term = _normalized_words(term)
    if not normalized_text.strip() or not normalized_term:
        return False
    return f" {normalized_term} " in normalized_text or normalized_term in normalized_text


def _clean_domain(domain: str) -> str:
    return _shared_clean_domain(domain)


def _email_domain(email: str) -> str:
    return _shared_email_domain(email)


def _hash_email(email: str) -> str:
    return _shared_hash_email(email)


def _canonical_event_type(value: str) -> str:
    return _shared_canonical_event_type(value)


def _canonical_location(value: str) -> str:
    return _shared_canonical_location(value)


def _canonical_country(value: str) -> str:
    return _shared_canonical_country(value)


def _resolved_event_filters(country: str, event_type: str, location: str) -> dict[str, str]:
    return _shared_resolved_event_filters(country, event_type, location)


def _event_tag_filters(event_tags: Any, country: str = "", event_type: str = "", location: str = "") -> list[str]:
    return _shared_event_tag_filters(event_tags, country, event_type, location)


def _luma_entries(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("entries", "items", "events", "guests", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _luma_has_more(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    pagination = payload.get("pagination") if isinstance(payload.get("pagination"), dict) else {}
    return bool(payload.get("has_more") or payload.get("hasMore") or pagination.get("has_more"))


def _luma_next_cursor(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    pagination = payload.get("pagination") if isinstance(payload.get("pagination"), dict) else {}
    return str(payload.get("next_cursor") or payload.get("nextCursor") or pagination.get("next_cursor") or "").strip()


def _luma_event_payload(item: dict[str, Any]) -> dict[str, Any]:
    event = item.get("event")
    return event if isinstance(event, dict) else item


def _luma_guest_payload(item: dict[str, Any]) -> dict[str, Any]:
    for key in ("guest", "event_guest", "eventGuest"):
        guest = item.get(key)
        if isinstance(guest, dict):
            merged = dict(guest)
            for outer_key in ("approval_status", "checked_in_at", "registered_at", "created_at"):
                if outer_key in item and outer_key not in merged:
                    merged[outer_key] = item[outer_key]
            return merged
    return item


def _luma_event_id(event: dict[str, Any]) -> str:
    return str(event.get("event_id") or event.get("api_id") or event.get("id") or "").strip()


def _luma_event_metadata_text(event: dict[str, Any]) -> str:
    fields = [
        str(event.get("name") or event.get("title") or ""),
        str(event.get("url") or event.get("event_url") or event.get("eventUrl") or ""),
        str(event.get("timezone") or ""),
    ]
    location = event.get("geo_address_json") or event.get("address") or event.get("location")
    if isinstance(location, (dict, list)):
        fields.append(json.dumps(location, sort_keys=True))
    elif location:
        fields.append(str(location))
    return " ".join(field for field in fields if field)


def _luma_event_tag_names(event: dict[str, Any]) -> list[str]:
    raw_tags: list[Any] = []
    for field in ("event_tags", "eventTags", "tags", "tag_ids", "tagIds"):
        value = event.get(field)
        if isinstance(value, list):
            raw_tags.extend(value)
        elif value:
            raw_tags.append(value)
    names: list[str] = []
    for tag in raw_tags:
        if isinstance(tag, str):
            names.append(tag)
        elif isinstance(tag, dict):
            names.append(str(tag.get("name") or tag.get("title") or tag.get("api_id") or tag.get("id") or "").strip())
    return _unique_text(names)


def _inferred_luma_tags(event: dict[str, Any]) -> list[str]:
    text = _luma_event_metadata_text(event)
    names: list[str] = []
    event_type = _canonical_event_type(text)
    if event_type:
        names.append(event_type)
    lowered = text.lower()
    if "singapore" in lowered or "(sg)" in lowered or "asia/singapore" in lowered:
        names.append("Singapore")
    if "jakarta" in lowered or "(jkt)" in lowered or "asia/jakarta" in lowered:
        names.append("Jakarta")
    if "bali" in lowered:
        names.append("Bali")
    if "kuala lumpur" in lowered or "(kl)" in lowered or "malaysia" in lowered:
        names.append("Kuala Lumpur")
    return _unique_text(names)


def _safe_luma_event(item: dict[str, Any]) -> dict[str, Any]:
    event = _luma_event_payload(item)
    luma_tags = _luma_event_tag_names(event)
    inferred_tags = _inferred_luma_tags(event)
    classifiable_tags = _unique_text(luma_tags + inferred_tags)
    location_tags = _unique_text([location for tag in classifiable_tags if (location := _canonical_location(tag))])
    country_tags = _unique_text([country for tag in classifiable_tags if (country := _canonical_country(tag))])
    event_type_tags = _unique_text([event_type for tag in classifiable_tags if (event_type := _canonical_event_type(tag))])
    return {
        "event_id": _luma_event_id(event),
        "name": event.get("name") or event.get("title") or "",
        "start_at": event.get("start_at") or event.get("startAt") or "",
        "end_at": event.get("end_at") or event.get("endAt") or "",
        "timezone": event.get("timezone") or "",
        "url": event.get("url") or event.get("event_url") or event.get("eventUrl") or "",
        "tags": luma_tags or inferred_tags,
        "location_tags": location_tags,
        "country_tags": country_tags,
        "event_type_tags": event_type_tags,
        "tag_match_source": "luma_event_tags" if luma_tags else ("inferred_from_event_metadata" if inferred_tags else "none"),
    }


def _event_matches_filters(event: dict[str, Any], query: str, country: str, event_type: str, location: str, event_tags: Any) -> bool:
    haystack_values = [str(event.get(key) or "") for key in ("name", "url", "event_id")]
    for key in ("tags", "location_tags", "country_tags", "event_type_tags"):
        value = event.get(key)
        if isinstance(value, list):
            haystack_values.extend(str(item) for item in value)
    haystack = " ".join(haystack_values).lower()
    if query.strip() and query.strip().lower() not in haystack:
        return False
    requested_tags = _event_tag_filters(event_tags, country, event_type, location)
    if requested_tags:
        event_tag_set = {str(tag).strip().lower() for tag in event.get("tags", []) if str(tag or "").strip()}
        if not all(tag.lower() in event_tag_set for tag in requested_tags):
            return False
    filters = _resolved_event_filters(country, event_type, location)
    if filters["location"] and filters["location"] not in event.get("location_tags", []):
        return False
    if filters["country"] and filters["country"] not in event.get("country_tags", []):
        return False
    if filters["event_type"] and filters["event_type"] not in event.get("event_type_tags", []):
        return False
    return True


def _rfc3339_or_default(value: str, default: datetime) -> str:
    text = str(value or "").strip()
    if not text:
        return default.isoformat().replace("+00:00", "Z")
    if "T" not in text:
        return f"{text}T00:00:00Z"
    if text.endswith("Z"):
        return text
    tail = text[10:]
    if "+" in tail or "-" in tail:
        return text
    return f"{text}Z"


def _list_luma_events_for_followup(
    query: str,
    start: str,
    end: str,
    country: str,
    event_type: str,
    location: str,
    event_tags: Any,
) -> tuple[list[dict[str, Any]], bool, bool]:
    now = datetime.now(timezone.utc)
    after = _rfc3339_or_default(start, now - timedelta(days=LUMA_EVENT_LOOKBACK_DAYS))
    before = _rfc3339_or_default(end, now + timedelta(days=LUMA_EVENT_LOOKAHEAD_DAYS))
    events: list[dict[str, Any]] = []
    cursor = ""
    has_more = False
    while len(events) < LUMA_MAX_EVENTS_FOR_FOLLOWUP:
        payload = _luma_request_json(
            "/v1/calendar/list-events",
            {
                "after": after,
                "before": before,
                "pagination_cursor": cursor,
                "pagination_limit": LUMA_PAGE_LIMIT,
                "sort_column": "start_at",
                "sort_direction": "asc",
                "status": "approved",
            },
        )
        page_events = [_safe_luma_event(item) for item in _luma_entries(payload)]
        events.extend(event for event in page_events if _event_matches_filters(event, query, country, event_type, location, event_tags))
        has_more = _luma_has_more(payload)
        cursor = _luma_next_cursor(payload)
        if not has_more or not cursor:
            break
    truncated = len(events) > LUMA_MAX_EVENTS_FOR_FOLLOWUP or (has_more and len(events) >= LUMA_MAX_EVENTS_FOR_FOLLOWUP)
    return events[:LUMA_MAX_EVENTS_FOR_FOLLOWUP], has_more, truncated


def _single_luma_event(event_id: str) -> dict[str, Any]:
    try:
        payload = _luma_request_json("/v1/event/get", {"id": event_id})
    except LumaEventError as error:
        if error.status_code != 400:
            raise
        payload = _luma_request_json("/v1/event/get", {"event_id": event_id})
    event = _safe_luma_event(payload)
    if not event["event_id"]:
        event["event_id"] = event_id
    return event


def _latest_luma_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not events:
        return None
    now = datetime.now(timezone.utc)
    past_events = [event for event in events if (_datetime_value(str(event.get("start_at") or "")) or now) <= now]
    candidates = past_events or events
    return sorted(
        candidates,
        key=lambda event: _datetime_value(str(event.get("start_at") or "")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )[0]


def _luma_checked_in_at(guest: dict[str, Any]) -> str:
    return str(guest.get("checked_in_at") or guest.get("checkedInAt") or "").strip()


def _luma_guest_email(guest: dict[str, Any]) -> str:
    return _normalize_email(str(guest.get("email") or guest.get("guest_email") or guest.get("email_address") or ""))


def _registration_texts(value: Any) -> list[str]:
    texts: list[str] = []
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            texts.append(stripped)
    elif isinstance(value, dict):
        for item in value.values():
            texts.extend(_registration_texts(item))
    elif isinstance(value, list):
        for item in value:
            texts.extend(_registration_texts(item))
    return texts


def _luma_guest_company_candidates(guest: dict[str, Any]) -> list[str]:
    fields = [
        str(guest.get("company") or ""),
        str(guest.get("company_name") or guest.get("companyName") or ""),
        str(guest.get("organization") or guest.get("organisation") or ""),
    ]
    fields.extend(_registration_texts(guest.get("registration_answers")))
    fields.extend(_registration_texts(guest.get("registrationAnswers")))
    return _unique_text([field for field in fields if field.strip()])


def _list_luma_guests(event_id: str, max_guests: int = LUMA_MAX_GUESTS_PER_EVENT) -> tuple[list[dict[str, Any]], bool, bool]:
    limit = max(1, min(int(max_guests or LUMA_MAX_GUESTS_PER_EVENT), LUMA_MAX_GUESTS_PER_EVENT))
    guests: list[dict[str, Any]] = []
    cursor = ""
    has_more = False
    while len(guests) < limit:
        page_limit = min(LUMA_PAGE_LIMIT, limit - len(guests))
        payload = _luma_request_json(
            "/v1/event/get-guests",
            {
                "event_id": event_id,
                "pagination_cursor": cursor,
                "pagination_limit": page_limit,
                "sort_column": "registered_at",
                "sort_direction": "asc",
            },
        )
        guests.extend(_luma_guest_payload(item) for item in _luma_entries(payload))
        has_more = _luma_has_more(payload)
        cursor = _luma_next_cursor(payload)
        if not has_more or not cursor:
            break
    truncated = has_more and len(guests) >= limit
    return guests[:limit], has_more, truncated


def _renewal_matches_in_window(company: dict[str, Any], start_date: date, end_date: date) -> list[dict[str, Any]]:
    props = company.get("properties", {})
    matches: list[dict[str, Any]] = []
    for property_name in RENEWAL_DATE_PROPERTIES:
        raw_value = str(props.get(property_name) or "")
        parsed = _date_value(raw_value)
        if parsed and start_date <= parsed <= end_date:
            matches.append(
                {
                    "property_name": property_name,
                    "value": raw_value,
                    "date": parsed,
                }
            )
    return sorted(
        matches,
        key=lambda item: (
            item["date"],
            RENEWAL_DATE_PROPERTIES.index(str(item["property_name"])),
        ),
    )


def _contact_detail_missing_fields(contacts: list[dict[str, Any]]) -> list[str]:
    if not contacts:
        return []
    missing: list[str] = []
    if not any(contact.get("persona") for contact in contacts):
        missing.append("persona")
    if not any(contact.get("channel_fit") for contact in contacts):
        missing.append("channel fit")
    return missing


def _missing_company_fields(
    props: dict[str, Any],
    contact_count: int | None,
    contacts: list[dict[str, Any]] | None = None,
) -> list[str]:
    missing: list[str] = []
    if not props.get("hubspot_owner_id"):
        missing.append("company owner")
    if not props.get("company_country"):
        missing.append("country")
    if not props.get("numberofemployees"):
        missing.append("headcount")
    if not props.get("industry"):
        missing.append("industry")
    if not props.get(RENEWAL_SOURCE_OF_TRUTH_PROPERTY):
        missing.append("contract end date")
    if not props.get(CURRENT_TOOLS_SOURCE_OF_TRUTH_PROPERTY):
        missing.append("current tools")
    if contact_count == 0:
        missing.append("associated contact")
    coverage = _decision_maker_coverage(props, contacts, contact_count)
    if coverage["verified_decision_maker_count"] < 1:
        missing.append("decision maker")
    return missing


def _enrichment_status(
    props: dict[str, Any],
    contact_count: int | None,
    contacts: list[dict[str, Any]] | None = None,
) -> str:
    missing = _missing_company_fields(props, contact_count, contacts)
    if missing:
        return "not_enriched"
    if contacts is not None and _contact_detail_missing_fields(contacts):
        return "minimum_enriched"
    if props.get("nurtureany_channel_fit") or props.get("nurtureany_contact_coverage"):
        return "nurture_ready"
    return "minimum_enriched"


def _association_ids_with_metadata(from_type: str, object_id: str, to_type: str, limit: int = 20) -> dict[str, Any]:
    requested_limit = _bounded_int(limit, default=20, maximum=TASK_ASSOCIATION_LIMIT)
    data = _get(
        f"/crm/v4/objects/{from_type}/{object_id}/associations/{to_type}",
        {"limit": str(requested_limit)},
    )
    ids = [str(item["toObjectId"]) for item in data.get("results", []) if item.get("toObjectId")]
    has_more = bool(data.get("paging", {}).get("next", {}).get("after"))
    return {"ids": ids, "has_more": has_more, "truncated": has_more, "requested_limit": requested_limit}


def _association_ids(from_type: str, object_id: str, to_type: str, limit: int = 20) -> list[str]:
    data = _association_ids_with_metadata(from_type, object_id, to_type, limit)
    return data["ids"]


def _batch_read(
    object_type: str,
    ids: list[str],
    properties: list[str],
    deadline: float | None = None,
) -> list[dict[str, Any]]:
    if not ids:
        return []
    results: list[dict[str, Any]] = []
    for index in range(0, len(ids), 100):
        if _deadline_exceeded(deadline):
            break
        chunk = ids[index : index + 100]
        data = _post(
            f"/crm/v3/objects/{object_type}/batch/read",
            {
                "properties": properties,
                "inputs": [{"id": object_id} for object_id in chunk],
            },
        )
        results.extend(data.get("results", []))
    return results


def _batch_association_ids(
    from_type: str,
    to_type: str,
    ids: list[str],
    deadline: float | None = None,
) -> dict[str, list[str]]:
    if not ids:
        return {}
    associations: dict[str, list[str]] = {}
    for index in range(0, len(ids), 100):
        if _deadline_exceeded(deadline):
            break
        chunk = ids[index : index + 100]
        data = _post(
            f"/crm/v4/associations/{from_type}/{to_type}/batch/read",
            {"inputs": [{"id": object_id} for object_id in chunk]},
        )
        for object_id in chunk:
            associations.setdefault(str(object_id), [])
        for result in data.get("results", []):
            from_id = str(result.get("from", {}).get("id") or "")
            if not from_id:
                continue
            associations.setdefault(from_id, [])
            for target in result.get("to", []):
                to_id = str(target.get("toObjectId") or "")
                if to_id and to_id not in associations[from_id]:
                    associations[from_id].append(to_id)
    return associations


def _batch_read_until(
    object_type: str,
    ids: list[str],
    properties: list[str],
    deadline: float | None,
) -> list[dict[str, Any]]:
    try:
        return _batch_read(object_type, ids, properties, deadline=deadline)
    except TypeError as error:
        if "deadline" not in str(error):
            raise
        return _batch_read(object_type, ids, properties)


def _batch_association_ids_until(
    from_type: str,
    to_type: str,
    ids: list[str],
    deadline: float | None,
) -> dict[str, list[str]]:
    try:
        return _batch_association_ids(from_type, to_type, ids, deadline=deadline)
    except TypeError as error:
        if "deadline" not in str(error):
            raise
        return _batch_association_ids(from_type, to_type, ids)


def _add_task_sources(
    task_sources: dict[str, list[dict[str, str]]],
    task_ids: list[str],
    source_type: str,
    source_id: str,
) -> None:
    for task_id in task_ids:
        sources = task_sources.setdefault(task_id, [])
        source = {"object_type": source_type, "object_id": str(source_id)}
        if source not in sources:
            sources.append(source)


def _collect_task_associations(company_id: str, contact_ids: list[str], deal_ids: list[str]) -> dict[str, Any]:
    task_sources: dict[str, list[dict[str, str]]] = {}
    truncated = False

    company_tasks = _association_ids_with_metadata("companies", company_id, "tasks", TASK_ASSOCIATION_LIMIT)
    _add_task_sources(task_sources, company_tasks["ids"], "company", company_id)
    truncated = truncated or company_tasks["truncated"]

    for contact_id in contact_ids:
        contact_tasks = _association_ids_with_metadata("contacts", contact_id, "tasks", TASK_ASSOCIATION_LIMIT)
        _add_task_sources(task_sources, contact_tasks["ids"], "contact", contact_id)
        truncated = truncated or contact_tasks["truncated"]

    for deal_id in deal_ids:
        deal_tasks = _association_ids_with_metadata("deals", deal_id, "tasks", TASK_ASSOCIATION_LIMIT)
        _add_task_sources(task_sources, deal_tasks["ids"], "deal", deal_id)
        truncated = truncated or deal_tasks["truncated"]

    return {"task_ids": list(task_sources.keys()), "task_sources": task_sources, "truncated": truncated}


def _add_activity_sources(
    activity_sources: dict[str, list[dict[str, str]]],
    activity_ids: list[str],
    source_type: str,
    source_id: str,
) -> None:
    for activity_id in activity_ids:
        sources = activity_sources.setdefault(activity_id, [])
        source = {"object_type": source_type, "object_id": str(source_id)}
        if source not in sources:
            sources.append(source)


def _collect_activity_associations(
    company_id: str,
    contact_ids: list[str],
    deal_ids: list[str],
    object_type: str,
) -> dict[str, Any]:
    activity_sources: dict[str, list[dict[str, str]]] = {}
    truncated = False

    company_activities = _association_ids_with_metadata("companies", company_id, object_type, FOLLOWUP_ASSOCIATION_LIMIT)
    _add_activity_sources(activity_sources, company_activities["ids"], "company", company_id)
    truncated = truncated or company_activities["truncated"]

    for contact_id in contact_ids:
        contact_activities = _association_ids_with_metadata("contacts", contact_id, object_type, FOLLOWUP_ASSOCIATION_LIMIT)
        _add_activity_sources(activity_sources, contact_activities["ids"], "contact", contact_id)
        truncated = truncated or contact_activities["truncated"]

    for deal_id in deal_ids:
        deal_activities = _association_ids_with_metadata("deals", deal_id, object_type, FOLLOWUP_ASSOCIATION_LIMIT)
        _add_activity_sources(activity_sources, deal_activities["ids"], "deal", deal_id)
        truncated = truncated or deal_activities["truncated"]

    return {
        "activity_ids": list(activity_sources.keys()),
        "activity_sources": activity_sources,
        "truncated": truncated,
    }


def _activity_timestamp(activity: dict[str, Any]) -> str:
    props = activity.get("properties", {})
    return str(props.get("hs_timestamp") or props.get("hs_lastmodifieddate") or "")


def _is_activity_in_window(activity: dict[str, Any], since_dt: datetime, until_dt: datetime | None) -> bool:
    timestamp = _datetime_value(_activity_timestamp(activity))
    if not timestamp:
        return False
    if timestamp < since_dt:
        return False
    if until_dt and timestamp > until_dt:
        return False
    return True


def _is_whatsapp_communication(activity: dict[str, Any]) -> bool:
    props = activity.get("properties", {})
    channel = str(props.get("hs_communication_channel_type") or "").strip().upper().replace("-", "_").replace(" ", "_")
    return channel in {"WHATS_APP", "WHATSAPP"}


def _clean_activity_body_for_internal_checks(value: Any) -> str:
    text = html.unescape(str(value or ""))
    return re.sub(r"<[^>]+>", " ", text)


def _kns_component_present(text: str, terms: tuple[str, ...]) -> bool:
    return any(_text_contains_term(text, term) for term in terms)


def _whatsapp_kns_audit_from_body(body: Any) -> dict[str, Any]:
    text = _clean_activity_body_for_internal_checks(body).strip()
    if not text:
        return {
            "body_available": False,
            "has_knowledge": False,
            "has_network": False,
            "has_support": False,
            "missing_kns_components": ["knowledge", "network", "support"],
            "kns_status": "body_unavailable",
            "confidence": "needs-check",
            "body_policy": "raw_body_read_internal_only_omitted_from_response",
        }

    has_knowledge = _kns_component_present(text, KNS_KNOWLEDGE_TERMS)
    has_support_opportunity = _kns_component_present(text, KNS_SUPPORT_OPPORTUNITY_TERMS)
    has_network_speaker_sourcing = _kns_component_present(text, KNS_NETWORK_SPEAKER_SOURCING_TERMS)
    has_network = _kns_component_present(text, KNS_NETWORK_TERMS)
    if not has_support_opportunity:
        has_network = has_network or _kns_component_present(text, KNS_NETWORK_EVENT_TERMS)
    has_support = has_support_opportunity or (
        not has_network_speaker_sourcing and _kns_component_present(text, KNS_SUPPORT_TERMS)
    )
    missing = []
    if not has_knowledge:
        missing.append("knowledge")
    if not has_network:
        missing.append("network")
    if not has_support:
        missing.append("support")
    return {
        "body_available": True,
        "has_knowledge": has_knowledge,
        "has_network": has_network,
        "has_support": has_support,
        "missing_kns_components": missing,
        "kns_status": "pass" if not missing else "missing_component",
        "confidence": "needs-check",
        "body_policy": "raw_body_read_internal_only_omitted_from_response",
    }


def _event_followup_terms(event_context: dict[str, Any] | None) -> list[str]:
    if not event_context:
        return []
    raw_terms: list[Any] = []
    event = event_context.get("event") if isinstance(event_context.get("event"), dict) else {}
    raw_terms.append(event.get("name"))
    for key in ("tags", "location_tags", "event_type_tags"):
        value = event.get(key)
        if isinstance(value, list):
            raw_terms.extend(value)
    raw_terms.extend(event_context.get("event_tags") or [])
    for term in list(raw_terms):
        canonical = _canonical_event_type(str(term)) or _canonical_location(str(term))
        if canonical:
            raw_terms.append(canonical)
    if any(_canonical_event_type(str(term)) == "HR Happy Hour" for term in raw_terms):
        raw_terms.extend(["HHH", "HR Happy Hour", "Happy Hour"])
    if any(_canonical_event_type(str(term)) == "Leaders Lounge" for term in raw_terms):
        raw_terms.extend(["LL", "Leaders Lounge"])
    blocked = {"staffany", "singapore", "malaysia", "indonesia"}
    terms = [
        term
        for term in _unique_text(raw_terms)
        if len(_normalized_words(term)) >= 3 and _normalized_words(term) not in blocked
    ]
    return terms


def _event_specific_match(
    evidence_type: str,
    activity: dict[str, Any],
    event_context: dict[str, Any] | None,
) -> dict[str, str]:
    if not event_context:
        return {"event_match": "not_checked", "match_reason": ""}
    props = activity.get("properties", {})
    if evidence_type == "communication":
        text = str(props.get("hs_communication_body") or "")
    elif evidence_type == "task":
        text = str(props.get("hs_task_subject") or "")
    else:
        return {"event_match": "weak", "match_reason": "event_body_not_read"}
    event_terms = _event_followup_terms(event_context)
    has_event_term = any(_text_contains_term(text, term) for term in event_terms)
    has_followup_phrase = any(_text_contains_term(text, phrase) for phrase in EVENT_FOLLOWUP_PHRASES)
    strong_followup_phrase = any(
        _text_contains_term(text, phrase)
        for phrase in ("thanks for attending", "terima kasih", "makasih", "sudah datang", "sudah hadir", "for coming", "for joining")
    )
    if has_event_term and has_followup_phrase:
        return {"event_match": "strong", "match_reason": "event_keyword_and_followup_phrase"}
    if strong_followup_phrase:
        return {"event_match": "strong", "match_reason": "event_followup_phrase"}
    if has_event_term or has_followup_phrase:
        return {"event_match": "weak", "match_reason": "partial_event_followup_signal"}
    return {"event_match": "generic", "match_reason": "no_event_followup_signal"}


def _safe_followup_evidence(
    object_type: str,
    activity: dict[str, Any],
    activity_sources: dict[str, list[dict[str, str]]],
    event_match: dict[str, str] | None = None,
) -> dict[str, Any]:
    props = activity.get("properties", {})
    object_id = str(activity.get("id") or "")
    evidence = {
        "object_type": object_type,
        "object_id": object_id,
        "timestamp": _activity_timestamp(activity),
        "owner_id": props.get("hubspot_owner_id") or "",
        "associated_via": activity_sources.get(object_id, []),
    }
    if object_type == "communication":
        evidence["channel"] = props.get("hs_communication_channel_type") or ""
        evidence["logged_from"] = props.get("hs_communication_logged_from") or ""
    if object_type == "task":
        evidence["status"] = props.get("hs_task_status") or ""
    if object_type == "meeting":
        evidence["title"] = _safe_activity_label(props.get("hs_meeting_title"))
        evidence["outcome"] = props.get("hs_meeting_outcome") or ""
        evidence["activity_type"] = _safe_activity_label(props.get("hs_activity_type"))
    if event_match:
        evidence["event_match"] = event_match.get("event_match") or ""
        evidence["match_reason"] = event_match.get("match_reason") or ""
    return evidence


def _sort_followup_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(item: dict[str, Any]) -> datetime:
        return _datetime_value(str(item.get("timestamp") or "")) or datetime.min.replace(tzinfo=timezone.utc)

    return sorted(evidence, key=key, reverse=True)


def _account_followup_status(
    company: dict[str, Any],
    contact_ids: list[str],
    deal_ids: list[str],
    since_dt: datetime,
    until_dt: datetime | None,
    event_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    company_id = str(company.get("id") or "")
    props = company.get("properties", {})
    company_owner_id = str(props.get("hubspot_owner_id") or "")
    counts = {
        "whatsapp_communications": 0,
        "notes": 0,
        "completed_tasks": 0,
        "open_tasks": 0,
        "completed_meetings": 0,
    }
    event_mode = event_context is not None
    if event_mode:
        counts.update(
            {
                "event_specific_whatsapp_communications": 0,
                "generic_whatsapp_communications": 0,
                "event_specific_completed_tasks": 0,
                "generic_completed_tasks": 0,
                "event_specific_open_tasks": 0,
                "generic_open_tasks": 0,
                "completed_meeting_logs": 0,
                "weak_followup_evidence": 0,
            }
        )
    evidence: list[dict[str, Any]] = []
    truncated = False
    owner_mismatch = False
    weak_evidence = False

    activity_specs = [
        ("communications", "communication", COMMUNICATION_EVENT_PROPERTIES if event_mode else COMMUNICATION_PROPERTIES),
        ("notes", "note", NOTE_PROPERTIES),
        ("tasks", "task", TASK_PROPERTIES),
        ("meetings", "meeting", MEETING_PROPERTIES),
    ]
    for hubspot_type, evidence_type, properties in activity_specs:
        association_data = _collect_activity_associations(company_id, contact_ids, deal_ids, hubspot_type)
        activity_ids = association_data["activity_ids"]
        read_ids = activity_ids[:FOLLOWUP_RETURN_LIMIT]
        raw_activities = _batch_read(hubspot_type, read_ids, properties)
        truncated = bool(truncated or association_data["truncated"] or len(activity_ids) > len(read_ids))

        for activity in raw_activities:
            if not _activity_timestamp(activity):
                weak_evidence = True
                continue
            if not _is_activity_in_window(activity, since_dt, until_dt):
                continue
            if evidence_type == "communication" and not _is_whatsapp_communication(activity):
                continue
            if evidence_type == "meeting" and not _is_completed_meeting(activity):
                continue

            event_match = _event_specific_match(evidence_type, activity, event_context) if event_mode else None
            safe_evidence = _safe_followup_evidence(evidence_type, activity, association_data["activity_sources"], event_match)
            evidence_owner_id = str(safe_evidence.get("owner_id") or "")
            if evidence_owner_id and company_owner_id and evidence_owner_id != company_owner_id:
                owner_mismatch = True

            if evidence_type == "communication":
                counts["whatsapp_communications"] += 1
                if event_mode and event_match and event_match.get("event_match") == "strong":
                    counts["event_specific_whatsapp_communications"] += 1
                elif event_mode:
                    counts["generic_whatsapp_communications"] += 1
                    counts["weak_followup_evidence"] += 1
                evidence.append(safe_evidence)
            elif evidence_type == "note":
                counts["notes"] += 1
                if event_mode:
                    counts["weak_followup_evidence"] += 1
                evidence.append(safe_evidence)
            elif evidence_type == "meeting":
                counts["completed_meetings"] += 1
                if event_mode:
                    counts["completed_meeting_logs"] += 1
                    counts["weak_followup_evidence"] += 1
                evidence.append(safe_evidence)
            elif _is_incomplete_task(activity):
                counts["open_tasks"] += 1
                if event_mode and event_match and event_match.get("event_match") == "strong":
                    counts["event_specific_open_tasks"] += 1
                elif event_mode:
                    counts["generic_open_tasks"] += 1
                    counts["weak_followup_evidence"] += 1
                evidence.append(safe_evidence)
            else:
                counts["completed_tasks"] += 1
                if event_mode and event_match and event_match.get("event_match") == "strong":
                    counts["event_specific_completed_tasks"] += 1
                elif event_mode:
                    counts["generic_completed_tasks"] += 1
                    counts["weak_followup_evidence"] += 1
                evidence.append(safe_evidence)

    sorted_evidence = _sort_followup_evidence(evidence)
    if event_mode:
        completed_count = counts["event_specific_whatsapp_communications"] + counts["event_specific_completed_tasks"]
        weak_count = counts["weak_followup_evidence"]
        scheduled_count = counts["event_specific_open_tasks"]
    else:
        completed_count = counts["whatsapp_communications"] + counts["notes"] + counts["completed_tasks"]
        weak_count = 0
        scheduled_count = counts["open_tasks"]
    if truncated or owner_mismatch or weak_evidence:
        status = "needs_check"
    elif completed_count:
        status = "followed_up"
    elif scheduled_count:
        status = "scheduled"
    elif event_mode and weak_count:
        status = "needs_check"
    else:
        status = "not_found"

    summary = _summarize_company(company)
    return {
        "company_id": summary.get("company_id"),
        "company_name": summary.get("name"),
        "owner_id": summary.get("owner_id"),
        "owner_email": summary.get("owner_email"),
        "owner_name": summary.get("owner_name"),
        "account_status": summary.get("account_status"),
        "account_status_source": summary.get("account_status_source"),
        "country": summary.get("country"),
        "followup_status": status,
        "latest_followup_at": sorted_evidence[0]["timestamp"] if sorted_evidence else "",
        "activity_counts": counts,
        "evidence": sorted_evidence[:10],
        "activity_truncated": truncated,
        "owner_mismatch": owner_mismatch,
        "weak_evidence": weak_evidence,
        "confidence": "needs-check" if status == "needs_check" else "verified",
        "caveat": (
            "Safe HubSpot follow-up evidence only; raw WhatsApp bodies, note bodies, task bodies, phone numbers, and bulk PII are omitted."
        ),
    }


def _empty_followup_activity() -> dict[str, Any]:
    return {
        "counts": {
            "whatsapp_communications": 0,
            "notes": 0,
            "completed_tasks": 0,
            "open_tasks": 0,
            "completed_meetings": 0,
        },
        "latest_followup_at": "",
        "evidence": [],
        "activity_truncated": False,
        "owner_mismatch": False,
        "weak_evidence": False,
    }


def _count_indexed_followup_activity(
    account_activity: dict[str, Any],
    company_owner_id: str,
    evidence_type: str,
    activity: dict[str, Any],
    sources: list[dict[str, str]],
) -> None:
    if evidence_type == "communication" and not _is_whatsapp_communication(activity):
        return
    if evidence_type == "meeting" and not _is_completed_meeting(activity):
        return

    activity_id = str(activity.get("id") or "")
    safe_evidence = _safe_followup_evidence(evidence_type, activity, {activity_id: sources})
    evidence_owner_id = str(safe_evidence.get("owner_id") or "")
    if evidence_owner_id and company_owner_id and evidence_owner_id != company_owner_id:
        account_activity["owner_mismatch"] = True

    counts = account_activity["counts"]
    if evidence_type == "communication":
        counts["whatsapp_communications"] += 1
    elif evidence_type == "note":
        counts["notes"] += 1
    elif evidence_type == "meeting":
        counts["completed_meetings"] += 1
    elif _is_incomplete_task(activity):
        counts["open_tasks"] += 1
    else:
        counts["completed_tasks"] += 1
    account_activity["evidence"].append(safe_evidence)


def _followup_activity_index_for_companies(
    companies: list[dict[str, Any]],
    contact_index: dict[str, list[str]],
    deal_index: dict[str, list[str]],
    since_dt: datetime,
    until_dt: datetime | None,
    deadline: float | None = None,
) -> dict[str, dict[str, Any]]:
    company_ids = [str(company.get("id") or "") for company in companies if company.get("id")]
    if not company_ids:
        return {}

    activity_by_company = {company_id: _empty_followup_activity() for company_id in company_ids}
    company_owner_ids = {
        str(company.get("id") or ""): str(company.get("properties", {}).get("hubspot_owner_id") or "")
        for company in companies
        if company.get("id")
    }
    contact_to_companies = _reverse_company_association_index(contact_index)
    deal_to_companies = _reverse_company_association_index(deal_index)
    contact_ids = list(contact_to_companies.keys())
    deal_ids = list(deal_to_companies.keys())
    activity_specs = [
        ("communications", "communication", COMMUNICATION_PROPERTIES),
        ("notes", "note", NOTE_PROPERTIES),
        ("tasks", "task", TASK_PROPERTIES),
        ("meetings", "meeting", MEETING_PROPERTIES),
    ]

    for hubspot_type, evidence_type, properties in activity_specs:
        if _deadline_exceeded(deadline):
            for account_activity in activity_by_company.values():
                account_activity["activity_truncated"] = True
            break
        company_activity_sources: dict[str, dict[str, list[dict[str, str]]]] = {}

        for company_id, activity_ids in _batch_association_ids_until("companies", hubspot_type, company_ids, deadline).items():
            for activity_id in activity_ids:
                _add_indexed_activity_source(company_activity_sources, company_id, activity_id, "company", company_id)

        for contact_id, activity_ids in _batch_association_ids_until("contacts", hubspot_type, contact_ids, deadline).items():
            for company_id in contact_to_companies.get(str(contact_id), []):
                for activity_id in activity_ids:
                    _add_indexed_activity_source(company_activity_sources, company_id, activity_id, "contact", contact_id)

        for deal_id, activity_ids in _batch_association_ids_until("deals", hubspot_type, deal_ids, deadline).items():
            for company_id in deal_to_companies.get(str(deal_id), []):
                for activity_id in activity_ids:
                    _add_indexed_activity_source(company_activity_sources, company_id, activity_id, "deal", deal_id)

        activity_to_company_sources: dict[str, dict[str, list[dict[str, str]]]] = {}
        for company_id, activity_sources in company_activity_sources.items():
            for activity_id, sources in activity_sources.items():
                activity_to_company_sources.setdefault(activity_id, {})[company_id] = sources

        activity_ids = sorted(activity_to_company_sources.keys())
        if not activity_ids:
            continue

        read_limit = FOLLOWUP_RETURN_LIMIT * max(1, len(company_ids))
        read_ids = activity_ids[:read_limit]
        omitted_ids = set(activity_ids[read_limit:])
        for activity_id in omitted_ids:
            for company_id in activity_to_company_sources.get(activity_id, {}):
                activity_by_company[company_id]["activity_truncated"] = True

        raw_activities = _batch_read_until(hubspot_type, read_ids, properties, deadline)
        if _deadline_exceeded(deadline) and len(raw_activities) < len(read_ids):
            for activity_id in read_ids[len(raw_activities) :]:
                for company_id in activity_to_company_sources.get(activity_id, {}):
                    activity_by_company[company_id]["activity_truncated"] = True
        for activity in raw_activities:
            activity_id = str(activity.get("id") or "")
            if not activity_id:
                continue
            associated_companies = activity_to_company_sources.get(activity_id, {})
            if not _activity_timestamp(activity):
                for company_id in associated_companies:
                    activity_by_company[company_id]["weak_evidence"] = True
                continue
            if not _is_activity_in_window(activity, since_dt, until_dt):
                continue
            for company_id, sources in associated_companies.items():
                _count_indexed_followup_activity(
                    activity_by_company[company_id],
                    company_owner_ids.get(company_id, ""),
                    evidence_type,
                    activity,
                    sources,
                )

    for account_activity in activity_by_company.values():
        sorted_evidence = _sort_followup_evidence(account_activity["evidence"])
        account_activity["latest_followup_at"] = sorted_evidence[0]["timestamp"] if sorted_evidence else ""
        account_activity["evidence"] = sorted_evidence[:10]
    return activity_by_company


def _account_followup_status_from_index(company: dict[str, Any], account_activity: dict[str, Any]) -> dict[str, Any]:
    counts = dict(_empty_followup_activity()["counts"])
    counts.update(account_activity.get("counts") or {})
    truncated = bool(account_activity.get("activity_truncated") or account_activity.get("truncated"))
    owner_mismatch = bool(account_activity.get("owner_mismatch"))
    weak_evidence = bool(account_activity.get("weak_evidence"))
    completed_count = counts["whatsapp_communications"] + counts["notes"] + counts["completed_tasks"]
    scheduled_count = counts["open_tasks"]

    if truncated or owner_mismatch or weak_evidence:
        status = "needs_check"
    elif completed_count:
        status = "followed_up"
    elif scheduled_count:
        status = "scheduled"
    else:
        status = "not_found"

    summary = _summarize_company(company)
    return {
        "company_id": summary.get("company_id"),
        "company_name": summary.get("name"),
        "owner_id": summary.get("owner_id"),
        "owner_email": summary.get("owner_email"),
        "owner_name": summary.get("owner_name"),
        "account_status": summary.get("account_status"),
        "account_status_source": summary.get("account_status_source"),
        "country": summary.get("country"),
        "followup_status": status,
        "latest_followup_at": account_activity.get("latest_followup_at") or "",
        "activity_counts": counts,
        "evidence": account_activity.get("evidence") or [],
        "activity_truncated": truncated,
        "owner_mismatch": owner_mismatch,
        "weak_evidence": weak_evidence,
        "confidence": "needs-check" if status == "needs_check" else "verified",
        "caveat": (
            "Safe HubSpot follow-up evidence only; raw WhatsApp bodies, note bodies, task bodies, phone numbers, and bulk PII are omitted."
        ),
    }


def _add_company_task_source(
    company_sources: dict[str, list[dict[str, str]]],
    company_id: str,
    source_type: str,
    source_id: str,
) -> None:
    sources = company_sources.setdefault(str(company_id), [])
    source = {"object_type": source_type, "object_id": str(source_id)}
    if source not in sources:
        sources.append(source)


def _task_company_links_for_tasks(task_ids: list[str]) -> dict[str, dict[str, Any]]:
    normalized_task_ids = [str(task_id) for task_id in task_ids if str(task_id)]
    links_by_task = {
        task_id: {"company_ids": [], "company_sources": {}, "truncated": False}
        for task_id in normalized_task_ids
    }

    direct_companies = _batch_association_ids("tasks", "companies", normalized_task_ids)
    task_contacts = _batch_association_ids("tasks", "contacts", normalized_task_ids)
    task_deals = _batch_association_ids("tasks", "deals", normalized_task_ids)

    contact_to_tasks: dict[str, list[str]] = {}
    deal_to_tasks: dict[str, list[str]] = {}

    for task_id, company_ids in direct_companies.items():
        for company_id in company_ids:
            _add_company_task_source(links_by_task[task_id]["company_sources"], company_id, "company", company_id)

    for task_id, contact_ids in task_contacts.items():
        for contact_id in contact_ids:
            contact_to_tasks.setdefault(contact_id, []).append(task_id)

    for task_id, deal_ids in task_deals.items():
        for deal_id in deal_ids:
            deal_to_tasks.setdefault(deal_id, []).append(task_id)

    contact_companies = _batch_association_ids("contacts", "companies", list(contact_to_tasks.keys()))
    for contact_id, company_ids in contact_companies.items():
        for task_id in contact_to_tasks.get(contact_id, []):
            for company_id in company_ids:
                _add_company_task_source(links_by_task[task_id]["company_sources"], company_id, "contact", contact_id)

    deal_companies = _batch_association_ids("deals", "companies", list(deal_to_tasks.keys()))
    for deal_id, company_ids in deal_companies.items():
        for task_id in deal_to_tasks.get(deal_id, []):
            for company_id in company_ids:
                _add_company_task_source(links_by_task[task_id]["company_sources"], company_id, "deal", deal_id)

    for link in links_by_task.values():
        link["company_ids"] = list(link["company_sources"].keys())

    return links_by_task


def _is_incomplete_task(task: dict[str, Any]) -> bool:
    status = str(task.get("properties", {}).get("hs_task_status") or "").strip().upper()
    return status != "COMPLETED"


def _safe_task_summary(task: dict[str, Any], task_sources: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    props = task.get("properties", {})
    task_id = str(task.get("id") or "")
    return {
        "task_id": task_id,
        "due_at": props.get("hs_timestamp") or "",
        "subject": _short_text(str(props.get("hs_task_subject") or ""), 160),
        "owner_id": props.get("hubspot_owner_id") or "",
        "status": props.get("hs_task_status") or "",
        "priority": props.get("hs_task_priority") or "",
        "type": props.get("hs_task_type") or "",
        "native_reminder_at": props.get("hs_task_reminders") or "",
        "last_modified_at": props.get("hs_lastmodifieddate") or "",
        "associated_via": task_sources.get(task_id, []),
    }


def _sort_tasks_by_due_at(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(task: dict[str, Any]) -> tuple[int, str]:
        due_at = task.get("due_at") or ""
        return (0 if due_at else 1, due_at)

    return sorted(tasks, key=key)


def _sales_followup_signals(tasks: list[dict[str, Any]], truncated: bool) -> dict[str, Any]:
    today = datetime.now(timezone.utc).date()
    dated_tasks = [(task, _date_value(task.get("due_at"))) for task in tasks]
    overdue_count = len([task for task, due in dated_tasks if due and due < today])
    due_dates = [task.get("due_at") for task, due in dated_tasks if due and task.get("due_at")]
    return {
        "sales_followup_task_count": len(tasks),
        "overdue_sales_followup_task_count": overdue_count,
        "next_sales_followup_due_at": min(due_dates) if due_dates else "",
        "sales_followup_task_truncated": bool(truncated),
        "existing_sales_followup_open": bool(tasks),
    }


def _sales_followup_task_context(
    company: dict[str, Any],
    contact_ids: list[str] | None = None,
    deal_ids: list[str] | None = None,
    task_limit: int = 20,
) -> dict[str, Any]:
    company_id = str(company.get("id") or "")
    company_owner_id = str(company.get("properties", {}).get("hubspot_owner_id") or "")
    if not company_id or not company_owner_id:
        return {"tasks": [], "signals": _sales_followup_signals([], False)}

    contact_ids = contact_ids if contact_ids is not None else _association_ids("companies", company_id, "contacts", 50)
    deal_ids = deal_ids if deal_ids is not None else _association_ids("companies", company_id, "deals", 20)
    association_data = _collect_task_associations(company_id, contact_ids, deal_ids)
    task_ids = association_data["task_ids"]
    task_read_ids = task_ids[:TASK_RETURN_LIMIT]
    raw_tasks = _batch_read("tasks", task_read_ids, TASK_PROPERTIES)
    truncated = bool(association_data["truncated"] or len(task_ids) > len(task_read_ids))

    sales_owned_tasks = []
    for task in raw_tasks:
        props = task.get("properties", {})
        if not _is_incomplete_task(task):
            continue
        if str(props.get("hubspot_owner_id") or "") != company_owner_id:
            continue
        sales_owned_tasks.append(_safe_task_summary(task, association_data["task_sources"]))

    sorted_tasks = _sort_tasks_by_due_at(sales_owned_tasks)
    requested_limit = _bounded_int(task_limit, default=20, maximum=TASK_RETURN_LIMIT)
    returned_tasks = sorted_tasks[:requested_limit]
    truncated = truncated or len(sorted_tasks) > requested_limit
    return {"tasks": returned_tasks, "signals": _sales_followup_signals(sorted_tasks, truncated)}


def _sales_followup_task_index_for_companies(
    companies: list[dict[str, Any]],
    owner_id: str | None,
    task_limit: int = TASK_SEARCH_RESULT_LIMIT,
) -> dict[str, Any]:
    company_ids = [str(company.get("id") or "") for company in companies if company.get("id")]
    if not company_ids or not owner_id:
        return {"tasks_by_company": {}, "metadata": {}, "truncated": False}

    company_id_set = set(company_ids)
    owner_by_company = {
        str(company.get("id")): str(company.get("properties", {}).get("hubspot_owner_id") or "")
        for company in companies
        if company.get("id")
    }
    task_data = _task_search(
        _task_search_filters(owner_id),
        task_limit,
        maximum=max(TASK_SEARCH_RESULT_LIMIT, task_limit),
    )
    task_ids = [str(task.get("id") or "") for task in task_data.get("results", []) if task.get("id")]
    task_links = _task_company_links_for_tasks(task_ids)
    tasks_by_company: dict[str, list[dict[str, Any]]] = {company_id: [] for company_id in company_ids}
    association_truncated = False

    for task in task_data.get("results", []):
        task_id = str(task.get("id") or "")
        if not task_id or not _is_incomplete_task(task):
            continue
        task_owner_id = str(task.get("properties", {}).get("hubspot_owner_id") or "")
        links = task_links.get(task_id, {})
        association_truncated = association_truncated or bool(links.get("truncated"))
        for company_id in links.get("company_ids", []):
            if company_id not in company_id_set:
                continue
            if task_owner_id and owner_by_company.get(company_id) != task_owner_id:
                continue
            task_summary = _safe_task_summary(
                task,
                {task_id: links.get("company_sources", {}).get(str(company_id), [])},
            )
            tasks_by_company.setdefault(company_id, []).append(task_summary)

    for company_id, tasks in tasks_by_company.items():
        tasks_by_company[company_id] = _sort_tasks_by_due_at(tasks)

    metadata = _search_metadata(task_data)
    return {
        "tasks_by_company": tasks_by_company,
        "metadata": metadata,
        "truncated": bool(metadata.get("truncated") or association_truncated),
    }


def _sales_followup_task_index_for_company_associations(
    companies: list[dict[str, Any]],
    contact_index: dict[str, list[str]],
    deal_index: dict[str, list[str]],
    task_limit: int = TASK_SEARCH_AIRTIGHT_RESULT_LIMIT,
    deadline: float | None = None,
) -> dict[str, Any]:
    company_ids = [str(company.get("id") or "") for company in companies if company.get("id")]
    if not company_ids:
        return {
            "tasks_by_company": {},
            "metadata": {"total": 0, "requested_limit": 0, "returned_count": 0, "has_more": False, "truncated": False},
            "truncated": False,
        }

    owner_by_company = {
        str(company.get("id")): str(company.get("properties", {}).get("hubspot_owner_id") or "")
        for company in companies
        if company.get("id")
    }
    company_task_sources: dict[str, dict[str, list[dict[str, str]]]] = {company_id: {} for company_id in company_ids}
    partial_due_to_deadline = False

    for company_id, task_ids in _batch_association_ids_until("companies", "tasks", company_ids, deadline).items():
        for task_id in task_ids:
            _add_indexed_activity_source(company_task_sources, company_id, task_id, "company", company_id)

    contact_to_companies = _reverse_company_association_index(contact_index)
    if _deadline_exceeded(deadline):
        partial_due_to_deadline = True
    else:
        for contact_id, task_ids in _batch_association_ids_until("contacts", "tasks", list(contact_to_companies.keys()), deadline).items():
            for company_id in contact_to_companies.get(str(contact_id), []):
                for task_id in task_ids:
                    _add_indexed_activity_source(company_task_sources, company_id, task_id, "contact", contact_id)

    deal_to_companies = _reverse_company_association_index(deal_index)
    if _deadline_exceeded(deadline):
        partial_due_to_deadline = True
    else:
        for deal_id, task_ids in _batch_association_ids_until("deals", "tasks", list(deal_to_companies.keys()), deadline).items():
            for company_id in deal_to_companies.get(str(deal_id), []):
                for task_id in task_ids:
                    _add_indexed_activity_source(company_task_sources, company_id, task_id, "deal", deal_id)

    task_company_sources: dict[str, dict[str, list[dict[str, str]]]] = {}
    for company_id, task_sources in company_task_sources.items():
        for task_id, sources in task_sources.items():
            task_company_sources.setdefault(str(task_id), {})[str(company_id)] = sources

    task_ids = sorted(task_company_sources.keys())
    requested_limit = _bounded_int(task_limit, default=TASK_SEARCH_AIRTIGHT_RESULT_LIMIT, maximum=TASK_SEARCH_AIRTIGHT_RESULT_LIMIT)
    task_read_ids = task_ids[:requested_limit]
    raw_tasks = [] if _deadline_exceeded(deadline) else _batch_read_until("tasks", task_read_ids, TASK_PROPERTIES, deadline)
    partial_due_to_deadline = bool(partial_due_to_deadline or _deadline_exceeded(deadline))
    truncated = bool(len(task_ids) > len(task_read_ids) or partial_due_to_deadline)
    tasks_by_company: dict[str, list[dict[str, Any]]] = {company_id: [] for company_id in company_ids}

    for task in raw_tasks:
        task_id = str(task.get("id") or "")
        if not task_id or not _is_incomplete_task(task):
            continue
        task_owner_id = str(task.get("properties", {}).get("hubspot_owner_id") or "")
        for company_id, sources in task_company_sources.get(task_id, {}).items():
            if task_owner_id and owner_by_company.get(company_id) != task_owner_id:
                continue
            tasks_by_company.setdefault(company_id, []).append(_safe_task_summary(task, {task_id: sources}))

    for company_id, tasks in tasks_by_company.items():
        tasks_by_company[company_id] = _sort_tasks_by_due_at(tasks)

    metadata = {
        "total": len(task_ids),
        "requested_limit": requested_limit,
        "returned_count": len(raw_tasks),
        "has_more": truncated,
        "truncated": truncated,
        **_soft_timeout_metadata(partial_due_to_deadline),
    }
    return {
        "tasks_by_company": tasks_by_company,
        "metadata": metadata,
        "truncated": truncated,
        "partial_due_to_soft_timeout": partial_due_to_deadline,
    }


def _env_csv(name: str) -> set[str]:
    raw = os.environ.get(name, "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def _warm_activity_labels() -> tuple[str, ...]:
    configured = _env_csv(WARM_ACTIVITY_LABELS_ENV_VAR)
    if configured:
        return tuple(sorted(configured, key=str.lower))
    return DEFAULT_WARM_ACTIVITY_LABELS


def _friday_review_stage_config() -> dict[str, Any]:
    pipeline_ids = _env_csv(QO_PIPELINE_IDS_ENV_VAR)
    qo_stage_ids = _env_csv(QO_STAGE_IDS_ENV_VAR)
    qo_met_stage_ids = _env_csv(QO_MET_STAGE_IDS_ENV_VAR)
    closed_won_stage_ids = _env_csv(CLOSED_WON_STAGE_IDS_ENV_VAR)
    return {
        "pipeline_ids": pipeline_ids,
        "qo_stage_ids": qo_stage_ids,
        "qo_met_stage_ids": qo_met_stage_ids,
        "closed_won_stage_ids": closed_won_stage_ids,
        "configured": bool(pipeline_ids and qo_stage_ids and qo_met_stage_ids and closed_won_stage_ids),
        "required_env": [
            QO_PIPELINE_IDS_ENV_VAR,
            QO_STAGE_IDS_ENV_VAR,
            QO_MET_STAGE_IDS_ENV_VAR,
            CLOSED_WON_STAGE_IDS_ENV_VAR,
        ],
    }


def _week_window(week_start: str = "", week_end: str = "") -> dict[str, Any]:
    local_now = datetime.now(timezone.utc).astimezone(SINGAPORE_TIMEZONE)
    default_start = local_now.date() - timedelta(days=local_now.weekday())
    default_end = default_start + timedelta(days=6)
    start_date = _date_value(week_start) or default_start
    end_date = _date_value(week_end) or default_end
    if end_date < start_date:
        raise ScopeError("week_end must be on or after week_start.")
    start_local = datetime.combine(start_date, datetime_time(0, 0, 0), tzinfo=SINGAPORE_TIMEZONE)
    end_local = datetime.combine(end_date, datetime_time(23, 59, 59), tzinfo=SINGAPORE_TIMEZONE)
    return {
        "week_start": start_date.isoformat(),
        "week_end": end_date.isoformat(),
        "start_dt": start_local.astimezone(timezone.utc),
        "end_dt": end_local.astimezone(timezone.utc),
        "timezone": "Asia/Singapore",
    }


def _singapore_day_window(value: str = "") -> dict[str, Any]:
    local_date = _date_value(value) or datetime.now(timezone.utc).astimezone(SINGAPORE_TIMEZONE).date()
    start_local = datetime.combine(local_date, datetime_time(0, 0, 0), tzinfo=SINGAPORE_TIMEZONE)
    end_local = datetime.combine(local_date, datetime_time(23, 59, 59), tzinfo=SINGAPORE_TIMEZONE)
    return {
        "date": local_date.isoformat(),
        "start_dt": start_local.astimezone(timezone.utc),
        "end_dt": end_local.astimezone(timezone.utc),
        "timezone": "Asia/Singapore",
    }


def _safe_activity_label(value: Any, limit: int = 120) -> str:
    text = re.sub(r"(?<!\d)\+?\d[\d\s().-]{6,}\d(?!\d)", "[phone omitted]", str(value or ""))
    return _short_text(text, limit)


def _call_duration_ms(activity: dict[str, Any]) -> int:
    return _int_value(activity.get("properties", {}).get("hs_call_duration"))


def _is_completed_call(activity: dict[str, Any]) -> bool:
    status = str(activity.get("properties", {}).get("hs_call_status") or "").strip().upper()
    return status in {"COMPLETED", "DONE"}


def _is_connected_call(activity: dict[str, Any]) -> bool:
    return _is_completed_call(activity) and _call_duration_ms(activity) >= CONNECTED_CALL_MIN_DURATION_MS


def _aircall_call_id_from_hubspot_call(activity: dict[str, Any]) -> str:
    props = activity.get("properties", {})
    source_text = " ".join(
        str(props.get(key) or "")
        for key in (
            "hs_call_source",
            "hs_call_app_id",
            "hs_object_source_detail_1",
            "hs_object_source_label",
        )
    ).lower()
    if "aircall" not in source_text and str(props.get("hs_call_app_id") or "") != "36503":
        return ""
    call_id = str(props.get("hs_call_external_id") or "").strip()
    if re.fullmatch(r"\d+", call_id):
        return call_id
    return ""


def _is_completed_meeting(activity: dict[str, Any]) -> bool:
    outcome = str(activity.get("properties", {}).get("hs_meeting_outcome") or "").strip().upper()
    return outcome == "COMPLETED"


def _matching_warm_activity_label(activity: dict[str, Any]) -> str:
    props = activity.get("properties", {})
    text = " ".join(
        [
            str(props.get("hs_meeting_title") or ""),
            str(props.get("hs_activity_type") or ""),
        ]
    ).lower()
    for label in _warm_activity_labels():
        if label.lower() in text:
            return label
    return ""


def _safe_friday_activity_evidence(
    evidence_type: str,
    activity: dict[str, Any],
    activity_sources: dict[str, list[dict[str, str]]],
) -> dict[str, Any]:
    props = activity.get("properties", {})
    object_id = str(activity.get("id") or "")
    evidence: dict[str, Any] = {
        "object_type": evidence_type,
        "object_id": object_id,
        "timestamp": _activity_timestamp(activity),
        "owner_id": props.get("hubspot_owner_id") or "",
        "associated_via": activity_sources.get(object_id, []),
    }
    if evidence_type == "communication":
        evidence["channel"] = props.get("hs_communication_channel_type") or ""
    elif evidence_type == "task":
        evidence["status"] = props.get("hs_task_status") or ""
        evidence["subject"] = _safe_activity_label(props.get("hs_task_subject"))
    elif evidence_type == "call":
        evidence["title"] = _safe_activity_label(props.get("hs_call_title"))
        evidence["status"] = props.get("hs_call_status") or ""
        evidence["duration_seconds"] = round(_call_duration_ms(activity) / 1000)
        evidence["connected_call"] = _is_connected_call(activity)
        aircall_call_id = _aircall_call_id_from_hubspot_call(activity)
        if aircall_call_id:
            evidence["aircall_call_id"] = aircall_call_id
    elif evidence_type == "meeting":
        warm_label = _matching_warm_activity_label(activity)
        evidence["title"] = _safe_activity_label(props.get("hs_meeting_title"))
        evidence["outcome"] = props.get("hs_meeting_outcome") or ""
        evidence["activity_type"] = _safe_activity_label(props.get("hs_activity_type"))
        evidence["warm_activity_label"] = warm_label
    return evidence


def _account_week_activity(
    company: dict[str, Any],
    contact_ids: list[str],
    deal_ids: list[str],
    since_dt: datetime,
    until_dt: datetime,
) -> dict[str, Any]:
    company_id = str(company.get("id") or "")
    counts = {
        "whatsapp_communications": 0,
        "notes": 0,
        "completed_tasks": 0,
        "open_tasks": 0,
        "completed_calls": 0,
        "connected_calls": 0,
        "completed_meetings": 0,
        "warm_activity_points": 0,
        "touches": 0,
    }
    evidence: list[dict[str, Any]] = []
    truncated = False
    weak_evidence = False
    activity_specs = [
        ("communications", "communication", COMMUNICATION_PROPERTIES),
        ("notes", "note", NOTE_PROPERTIES),
        ("tasks", "task", TASK_PROPERTIES),
        ("calls", "call", CALL_PROPERTIES),
        ("meetings", "meeting", MEETING_PROPERTIES),
    ]

    for hubspot_type, evidence_type, properties in activity_specs:
        association_data = _collect_activity_associations(company_id, contact_ids, deal_ids, hubspot_type)
        activity_ids = association_data["activity_ids"]
        read_ids = activity_ids[:FOLLOWUP_RETURN_LIMIT]
        raw_activities = _batch_read(hubspot_type, read_ids, properties)
        truncated = bool(truncated or association_data["truncated"] or len(activity_ids) > len(read_ids))

        for activity in raw_activities:
            if not _activity_timestamp(activity):
                weak_evidence = True
                continue
            if not _is_activity_in_window(activity, since_dt, until_dt):
                continue

            safe_evidence = _safe_friday_activity_evidence(evidence_type, activity, association_data["activity_sources"])
            if evidence_type == "communication":
                if not _is_whatsapp_communication(activity):
                    continue
                counts["whatsapp_communications"] += 1
                counts["touches"] += 1
                evidence.append(safe_evidence)
            elif evidence_type == "note":
                counts["notes"] += 1
                counts["touches"] += 1
                evidence.append(safe_evidence)
            elif evidence_type == "task":
                if _is_incomplete_task(activity):
                    counts["open_tasks"] += 1
                    evidence.append(safe_evidence)
                else:
                    counts["completed_tasks"] += 1
                    counts["touches"] += 1
                    evidence.append(safe_evidence)
            elif evidence_type == "call":
                if not _is_completed_call(activity):
                    continue
                counts["completed_calls"] += 1
                counts["touches"] += 1
                if _is_connected_call(activity):
                    counts["connected_calls"] += 1
                evidence.append(safe_evidence)
            elif evidence_type == "meeting":
                if not _is_completed_meeting(activity):
                    continue
                counts["completed_meetings"] += 1
                counts["touches"] += 1
                if safe_evidence.get("warm_activity_label"):
                    counts["warm_activity_points"] += 1
                evidence.append(safe_evidence)

    sorted_evidence = _sort_followup_evidence(evidence)
    return {
        "counts": counts,
        "latest_activity_at": sorted_evidence[0]["timestamp"] if sorted_evidence else "",
        "evidence": sorted_evidence[:10],
        "truncated": truncated,
        "weak_evidence": weak_evidence,
        "confidence": "needs-check" if truncated or weak_evidence else "verified",
    }


def _empty_week_activity() -> dict[str, Any]:
    return {
        "counts": {
            "whatsapp_communications": 0,
            "notes": 0,
            "completed_tasks": 0,
            "open_tasks": 0,
            "completed_calls": 0,
            "connected_calls": 0,
            "completed_meetings": 0,
            "warm_activity_points": 0,
            "touches": 0,
        },
        "latest_activity_at": "",
        "evidence": [],
        "truncated": False,
        "weak_evidence": False,
        "confidence": "verified",
    }


def _reverse_company_association_index(index: dict[str, list[str]]) -> dict[str, list[str]]:
    reverse: dict[str, list[str]] = {}
    for company_id, associated_ids in index.items():
        for associated_id in associated_ids:
            reverse.setdefault(str(associated_id), []).append(str(company_id))
    return reverse


def _add_indexed_activity_source(
    company_activity_sources: dict[str, dict[str, list[dict[str, str]]]],
    company_id: str,
    activity_id: str,
    source_type: str,
    source_id: str,
) -> None:
    if not company_id or not activity_id:
        return
    activity_sources = company_activity_sources.setdefault(str(company_id), {})
    sources = activity_sources.setdefault(str(activity_id), [])
    source = {"object_type": source_type, "object_id": str(source_id)}
    if source not in sources:
        sources.append(source)


def _count_indexed_activity(
    account_activity: dict[str, Any],
    evidence_type: str,
    activity: dict[str, Any],
    sources: list[dict[str, str]],
) -> None:
    counts = account_activity["counts"]
    activity_id = str(activity.get("id") or "")
    safe_evidence = _safe_friday_activity_evidence(evidence_type, activity, {activity_id: sources})
    if evidence_type == "communication":
        if not _is_whatsapp_communication(activity):
            return
        counts["whatsapp_communications"] += 1
        counts["touches"] += 1
        account_activity["evidence"].append(safe_evidence)
    elif evidence_type == "note":
        counts["notes"] += 1
        counts["touches"] += 1
        account_activity["evidence"].append(safe_evidence)
    elif evidence_type == "task":
        if _is_incomplete_task(activity):
            counts["open_tasks"] += 1
            account_activity["evidence"].append(safe_evidence)
        else:
            counts["completed_tasks"] += 1
            counts["touches"] += 1
            account_activity["evidence"].append(safe_evidence)
    elif evidence_type == "call":
        if not _is_completed_call(activity):
            return
        counts["completed_calls"] += 1
        counts["touches"] += 1
        if _is_connected_call(activity):
            counts["connected_calls"] += 1
        account_activity["evidence"].append(safe_evidence)
    elif evidence_type == "meeting":
        if not _is_completed_meeting(activity):
            return
        counts["completed_meetings"] += 1
        counts["touches"] += 1
        if safe_evidence.get("warm_activity_label"):
            counts["warm_activity_points"] += 1
        account_activity["evidence"].append(safe_evidence)


def _week_activity_index_for_companies(
    companies: list[dict[str, Any]],
    contact_index: dict[str, list[str]],
    deal_index: dict[str, list[str]],
    since_dt: datetime,
    until_dt: datetime,
    deadline: float | None = None,
) -> dict[str, dict[str, Any]]:
    company_ids = [str(company.get("id") or "") for company in companies if company.get("id")]
    if not company_ids:
        return {}

    activity_by_company = {company_id: _empty_week_activity() for company_id in company_ids}
    contact_to_companies = _reverse_company_association_index(contact_index)
    deal_to_companies = _reverse_company_association_index(deal_index)
    contact_ids = list(contact_to_companies.keys())
    deal_ids = list(deal_to_companies.keys())
    activity_specs = [
        ("communications", "communication", COMMUNICATION_PROPERTIES),
        ("notes", "note", NOTE_PROPERTIES),
        ("tasks", "task", TASK_PROPERTIES),
        ("calls", "call", CALL_PROPERTIES),
        ("meetings", "meeting", MEETING_PROPERTIES),
    ]

    for hubspot_type, evidence_type, properties in activity_specs:
        if _deadline_exceeded(deadline):
            for account_activity in activity_by_company.values():
                account_activity["truncated"] = True
                account_activity["confidence"] = "needs-check"
            break
        company_activity_sources: dict[str, dict[str, list[dict[str, str]]]] = {}

        for company_id, activity_ids in _batch_association_ids_until("companies", hubspot_type, company_ids, deadline).items():
            for activity_id in activity_ids:
                _add_indexed_activity_source(company_activity_sources, company_id, activity_id, "company", company_id)

        if _deadline_exceeded(deadline):
            for account_activity in activity_by_company.values():
                account_activity["truncated"] = True
            break
        for contact_id, activity_ids in _batch_association_ids_until("contacts", hubspot_type, contact_ids, deadline).items():
            for company_id in contact_to_companies.get(str(contact_id), []):
                for activity_id in activity_ids:
                    _add_indexed_activity_source(company_activity_sources, company_id, activity_id, "contact", contact_id)

        if _deadline_exceeded(deadline):
            for account_activity in activity_by_company.values():
                account_activity["truncated"] = True
            break
        for deal_id, activity_ids in _batch_association_ids_until("deals", hubspot_type, deal_ids, deadline).items():
            for company_id in deal_to_companies.get(str(deal_id), []):
                for activity_id in activity_ids:
                    _add_indexed_activity_source(company_activity_sources, company_id, activity_id, "deal", deal_id)

        activity_ids = sorted(
            {
                activity_id
                for activity_sources in company_activity_sources.values()
                for activity_id in activity_sources.keys()
            }
        )
        if not activity_ids:
            continue

        raw_activities = [] if _deadline_exceeded(deadline) else _batch_read_until(hubspot_type, activity_ids, properties, deadline)
        if _deadline_exceeded(deadline):
            for account_activity in activity_by_company.values():
                account_activity["truncated"] = True
        for activity in raw_activities:
            activity_id = str(activity.get("id") or "")
            if not activity_id:
                continue
            associated_companies = [
                company_id
                for company_id, activity_sources in company_activity_sources.items()
                if activity_id in activity_sources
            ]
            if not _activity_timestamp(activity):
                for company_id in associated_companies:
                    activity_by_company[company_id]["weak_evidence"] = True
                continue
            if not _is_activity_in_window(activity, since_dt, until_dt):
                continue
            for company_id in associated_companies:
                _count_indexed_activity(
                    activity_by_company[company_id],
                    evidence_type,
                    activity,
                    company_activity_sources[company_id][activity_id],
                )

    for account_activity in activity_by_company.values():
        sorted_evidence = _sort_followup_evidence(account_activity["evidence"])
        account_activity["latest_activity_at"] = sorted_evidence[0]["timestamp"] if sorted_evidence else ""
        account_activity["evidence"] = sorted_evidence[:10]
        account_activity["confidence"] = "needs-check" if account_activity.get("weak_evidence") else "verified"
    return activity_by_company


def _safe_contact_index(contact_index: dict[str, list[str]]) -> dict[str, list[dict[str, Any]]]:
    contact_ids = sorted({contact_id for contact_ids in contact_index.values() for contact_id in contact_ids})
    contacts_by_id = {
        str(contact.get("id") or ""): _safe_contact(contact)
        for contact in _batch_read("contacts", contact_ids, CONTACT_PROPERTIES)
        if contact.get("id")
    }
    return {
        str(company_id): [contacts_by_id[contact_id] for contact_id in contact_ids if contact_id in contacts_by_id]
        for company_id, contact_ids in contact_index.items()
    }


def _clean_lead_missing_fields(
    company: dict[str, Any],
    contact_count: int,
    contacts: list[dict[str, Any]] | None = None,
) -> list[str]:
    props = company.get("properties", {})
    missing: list[str] = []
    if not props.get("industry"):
        missing.append("industry")
    if not props.get("numberofemployees"):
        missing.append("headcount")
    if not props.get(CURRENT_TOOLS_SOURCE_OF_TRUTH_PROPERTY):
        missing.append("current tools")
    if not props.get(RENEWAL_SOURCE_OF_TRUTH_PROPERTY):
        missing.append("contract end date")
    if contact_count < 1:
        missing.append("associated contact")
    if _decision_maker_coverage(props, contacts, contact_count)["verified_decision_maker_count"] < 1:
        missing.append("decision maker")
    return missing


def _company_latest_safe_activity_at(company: dict[str, Any], account_activity: dict[str, Any]) -> str:
    props = company.get("properties", {})
    candidates = [
        account_activity.get("latest_activity_at") or "",
        props.get("notes_last_updated") or "",
        props.get("nurtureany_last_nurtured_at") or "",
        props.get("nurtureany_last_reviewed_at") or "",
    ]
    dated = [_datetime_value(str(value)) for value in candidates if value]
    dated = [value for value in dated if value]
    if not dated:
        return ""
    return max(dated).isoformat()


def _is_stale_account(company: dict[str, Any], account_activity: dict[str, Any], cutoff_dt: datetime) -> bool:
    latest = _datetime_value(_company_latest_safe_activity_at(company, account_activity))
    return not latest or latest < cutoff_dt


def _owner_lookup_by_id() -> dict[str, dict[str, Any]]:
    try:
        return {str(owner.get("id") or ""): owner for owner in _list_owners()}
    except HubSpotError:
        return {}


def _owner_display(owner_id: str, owner_lookup: dict[str, dict[str, Any]]) -> dict[str, str]:
    owner = owner_lookup.get(str(owner_id), {})
    return {
        "owner_id": str(owner_id),
        "owner_email": _normalize_email(str(owner.get("email") or "")),
        "owner_name": _owner_name(owner) if owner else "",
    }


def _display_for_owner_id(owner_id: str, owner_lookup: dict[str, dict[str, Any]]) -> dict[str, str]:
    display = _owner_display(owner_id, owner_lookup)
    if not display["owner_email"]:
        display["owner_email"] = _owner_email_by_id(owner_id)
    if not display["owner_name"]:
        display["owner_name"] = _owner_name_by_id(owner_id)
    return display


def _parse_sales_local_datetime(value: str, tz: ZoneInfo, field_name: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise MetricClarification(f"{field_name} is required.")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise MetricClarification(f"{field_name} must be ISO-like, for example 2026-05-14 14:00.") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def _sales_call_window(start_local: str, end_local: str, timezone_name: str) -> dict[str, str]:
    tz_name = str(timezone_name or "Asia/Singapore").strip() or "Asia/Singapore"
    tz = _zoneinfo_or_none(tz_name)
    if not tz:
        raise MetricClarification(f"timezone is invalid: {tz_name}.")
    start = _parse_sales_local_datetime(start_local, tz, "start_local")
    end = _parse_sales_local_datetime(end_local, tz, "end_local")
    if end <= start:
        raise MetricClarification("end_local must be after start_local.")
    return {
        "timezone": tz_name,
        "start_local": start.isoformat(),
        "end_local": end.isoformat(),
        "start_utc": _utc_iso(start),
        "end_utc": _utc_iso(end),
    }


def _normalize_owner_id_list(owner_ids: list[str] | None) -> list[str]:
    selected: list[str] = []
    for owner_id in owner_ids or []:
        text = str(owner_id or "").strip()
        if text and text not in selected:
            selected.append(text)
    return selected


def _normalize_owner_email_list(owner_emails: list[str] | None, owner_email: str | None = None) -> list[str]:
    selected: list[str] = []
    for value in (owner_emails or []) + ([owner_email] if owner_email else []):
        email = _normalize_email(str(value or ""))
        if email and email not in selected:
            selected.append(email)
    return selected


def _sales_owner_rows_for_scope(
    scope: dict[str, Any],
    countries: list[str],
    owner_ids: list[str] | None = None,
    owner_emails: list[str] | None = None,
    owner_name: str | None = None,
    classified_sales_reps_only: bool = True,
    limit: int = 500,
) -> tuple[list[dict[str, Any]], list[str]]:
    if scope.get("kind") == "event_operator":
        raise ScopeError(EVENT_OPERATOR_BLOCK_MESSAGE)
    selected_countries = set(countries)
    requested_ids = _normalize_owner_id_list(owner_ids)
    requested_emails = _normalize_owner_email_list(owner_emails)
    unresolved: list[str] = []

    if owner_name:
        identity = _resolve_requested_owner(scope, countries, None, owner_name)
        if identity:
            requested_ids.append(identity["owner_id"])
            requested_emails.append(identity["owner_email"])

    for owner_email in list(requested_emails):
        identity = _resolve_requested_owner(scope, countries, owner_email, None)
        if identity and identity["owner_id"] not in requested_ids:
            requested_ids.append(identity["owner_id"])

    if scope.get("kind") == "ae":
        scope_owner_id = str(scope.get("owner_id") or "").strip()
        if requested_ids and any(owner_id != scope_owner_id for owner_id in requested_ids):
            raise ScopeError("Caller is not authorized to inspect another owner's sales activity.")
        if not requested_ids and not requested_emails:
            requested_ids = [scope_owner_id] if scope_owner_id else []
            if scope.get("hubspot_owner_email"):
                requested_emails = [_normalize_email(str(scope.get("hubspot_owner_email") or ""))]

    requested_limit = _bounded_int(limit, default=500, maximum=HUBSPOT_SEARCH_TOTAL_LIMIT)
    policy = _access_policy()
    rows_by_id: dict[str, dict[str, Any]] = {}
    seen_owner_emails: set[str] = set()

    for slack_email, rep in policy.get("sales_reps", {}).items():
        rep_countries = list(rep.get("countries") or ())
        country_overlap = [country for country in rep_countries if country in selected_countries]
        if countries and not country_overlap:
            continue
        owner_email = _normalize_email(str(rep.get("hubspot_owner_email") or ""))
        if requested_emails and owner_email not in requested_emails and _normalize_email(slack_email) not in requested_emails:
            continue
        if not owner_email or owner_email in seen_owner_emails:
            continue
        seen_owner_emails.add(owner_email)
        owner = _owner_by_email(owner_email)
        owner_id = str((owner or {}).get("id") or "").strip()
        if not owner_id:
            unresolved.append(owner_email)
            continue
        if requested_ids and owner_id not in requested_ids:
            continue
        if scope.get("kind") == "ae" and owner_id != str(scope.get("owner_id") or ""):
            continue
        rows_by_id[owner_id] = {
            "owner_id": owner_id,
            "owner_email": owner_email,
            "owner_name": _owner_name(owner or {}),
            "countries": country_overlap or rep_countries,
            "timezone": str(rep.get("timezone") or "").strip(),
            "classification": "sales_rep",
            "slack_email": slack_email,
        }
        if len(rows_by_id) >= requested_limit:
            break

    if not classified_sales_reps_only:
        for owner_id in requested_ids:
            if owner_id in rows_by_id:
                continue
            owner = _owner_by_id(owner_id)
            identity = _owner_identity(owner) if owner else {"owner_id": owner_id, "owner_email": "", "owner_name": ""}
            if scope.get("kind") in {"manager", "partnerships_viewer"} and not _manager_can_query_owner(
                scope, identity["owner_email"], countries
            ):
                continue
            rows_by_id[owner_id] = {
                **identity,
                "countries": countries,
                "timezone": _policy_timezone_for_owner_email(identity["owner_email"]),
                "classification": _policy_classification(identity["owner_email"], policy) if identity["owner_email"] else "provided_owner_id",
            }

    if requested_ids:
        missing_ids = [owner_id for owner_id in requested_ids if owner_id and owner_id not in rows_by_id]
        unresolved.extend(missing_ids)

    rows = sorted(
        rows_by_id.values(),
        key=lambda row: (",".join(row.get("countries") or []), row.get("owner_name") or row.get("owner_email") or row.get("owner_id")),
    )
    return rows[:requested_limit], _unique_text(unresolved)


def _resolve_sales_owner_ids_for_activity(
    scope: dict[str, Any],
    countries: list[str],
    owner_ids: list[str] | None = None,
    owner_emails: list[str] | None = None,
    owner_email: str | None = None,
    owner_name: str | None = None,
    classified_sales_reps_only: bool = True,
) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    requested_emails = _normalize_owner_email_list(owner_emails, owner_email)
    rows, unresolved = _sales_owner_rows_for_scope(
        scope,
        countries,
        owner_ids=owner_ids,
        owner_emails=requested_emails,
        owner_name=owner_name,
        classified_sales_reps_only=classified_sales_reps_only,
        limit=HUBSPOT_SEARCH_TOTAL_LIMIT,
    )
    resolved_ids = [str(row.get("owner_id") or "").strip() for row in rows if str(row.get("owner_id") or "").strip()]
    if not resolved_ids:
        raise MetricClarification("No scoped sales owners resolved. Use resolve_sales_owners first or pass a scoped owner email.")
    return resolved_ids, rows, unresolved


def _target_company_ids_for_sales_calls(
    countries: list[str],
    owner_ids: list[str],
    scan_limit: int,
) -> tuple[list[str], bool]:
    company_ids: list[str] = []
    truncated = False
    per_owner_limit = _bounded_int(scan_limit, default=SALES_CALL_DEFAULT_SCAN_LIMIT, maximum=HUBSPOT_SEARCH_TOTAL_LIMIT)
    for owner_id in owner_ids:
        data = _company_search(
            _target_filters(countries, owner_id),
            per_owner_limit,
            maximum=HUBSPOT_SEARCH_TOTAL_LIMIT,
            sorts=[{"propertyName": "hubspot_owner_id", "direction": "ASCENDING"}],
        )
        truncated = truncated or bool(data.get("truncated"))
        for company in data.get("results", []):
            company_id = str(company.get("id") or "").strip()
            if company_id and company_id not in company_ids:
                company_ids.append(company_id)
    return company_ids, truncated


def _scoped_selected_company_ids(company_ids: list[str] | None, scope: dict[str, Any]) -> list[str]:
    selected: list[str] = []
    for company_id in company_ids or []:
        normalized = str(company_id or "").strip()
        if not normalized:
            continue
        _assert_company_access(normalized, scope)
        if normalized not in selected:
            selected.append(normalized)
    return selected


def _associated_call_company_ids(
    call_ids: list[str],
    selected_company_ids: list[str],
    deadline: float | None = None,
) -> tuple[dict[str, list[str]], dict[str, dict[str, list[str]]]]:
    if not call_ids or not selected_company_ids:
        return {}, {}
    selected_companies = set(selected_company_ids)
    direct_company_ids = _batch_association_ids_until("calls", "companies", call_ids, deadline)
    call_contact_ids = _batch_association_ids_until("calls", "contacts", call_ids, deadline)
    call_deal_ids = _batch_association_ids_until("calls", "deals", call_ids, deadline)
    company_contact_ids = _batch_association_ids_until("companies", "contacts", selected_company_ids, deadline)
    company_deal_ids = _batch_association_ids_until("companies", "deals", selected_company_ids, deadline)

    contact_to_companies: dict[str, list[str]] = {}
    for company_id, contact_ids in company_contact_ids.items():
        for contact_id in contact_ids:
            contact_to_companies.setdefault(contact_id, []).append(company_id)
    deal_to_companies: dict[str, list[str]] = {}
    for company_id, deal_ids in company_deal_ids.items():
        for deal_id in deal_ids:
            deal_to_companies.setdefault(deal_id, []).append(company_id)

    matched_company_ids: dict[str, list[str]] = {}
    association_details: dict[str, dict[str, list[str]]] = {}
    for call_id in call_ids:
        companies = set(direct_company_ids.get(call_id, [])).intersection(selected_companies)
        matched_contacts = []
        matched_deals = []
        for contact_id in call_contact_ids.get(call_id, []):
            contact_companies = set(contact_to_companies.get(contact_id, [])).intersection(selected_companies)
            if contact_companies:
                companies.update(contact_companies)
                matched_contacts.append(contact_id)
        for deal_id in call_deal_ids.get(call_id, []):
            deal_companies = set(deal_to_companies.get(deal_id, [])).intersection(selected_companies)
            if deal_companies:
                companies.update(deal_companies)
                matched_deals.append(deal_id)
        if companies:
            matched_company_ids[call_id] = sorted(companies)
            association_details[call_id] = {
                "associated_company_ids": sorted(companies),
                "associated_contact_ids": _unique_text(matched_contacts),
                "associated_deal_ids": _unique_text(matched_deals),
            }
    return matched_company_ids, association_details


def _call_status_matches(call: dict[str, Any], status: str) -> bool:
    normalized = str(status or "ANY").strip().upper()
    if normalized in {"", "ANY", "ALL"}:
        return True
    if normalized == "COMPLETED":
        return _is_completed_call(call)
    call_status = str(call.get("properties", {}).get("hs_call_status") or "").strip().upper()
    return call_status == normalized


def _safe_sales_call_event(
    call: dict[str, Any],
    owner_lookup: dict[str, dict[str, Any]],
    association_mode: str,
    associations: dict[str, list[str]] | None = None,
    association_details: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    props = call.get("properties", {})
    owner_id = str(props.get("hubspot_owner_id") or "").strip()
    display = _display_for_owner_id(owner_id, owner_lookup)
    duration_ms = _call_duration_ms(call)
    details = association_details or {}
    return {
        "event_type": "call",
        "object_id": str(call.get("id") or "").strip(),
        "timestamp_utc": props.get("hs_timestamp") or props.get("hs_lastmodifieddate") or "",
        "owner_id": owner_id,
        "owner_email": display.get("owner_email") or "",
        "owner_name": display.get("owner_name") or "",
        "status": str(props.get("hs_call_status") or "").strip(),
        "duration_seconds": round(duration_ms / 1000, 3),
        "completed": _is_completed_call(call),
        "completed_gt_60s": _is_completed_call(call) and duration_ms > AE_COACHING_LONG_CALL_MIN_DURATION_MS,
        "connected_call_120s_guardrail": _is_connected_call(call),
        "channel": str(props.get("hs_call_source") or props.get("hs_object_source_label") or "").strip(),
        "association_mode": association_mode,
        "associated_company_ids": details.get("associated_company_ids") or associations or [],
        "associated_contact_ids": details.get("associated_contact_ids") or [],
        "associated_deal_ids": details.get("associated_deal_ids") or [],
        "aircall_call_id": _aircall_call_id_from_hubspot_call(call),
        "raw_body_returned": False,
    }


def _list_sales_call_events_core(
    scope: dict[str, Any],
    countries: list[str],
    owner_ids: list[str],
    start_local: str,
    end_local: str,
    timezone_name: str,
    status: str,
    association_mode: str,
    company_ids: list[str] | None = None,
    limit: int = SALES_CALL_DEFAULT_SCAN_LIMIT,
    deadline: float | None = None,
) -> dict[str, Any]:
    mode = str(association_mode or "owner_level").strip()
    if mode not in SALES_CALL_ASSOCIATION_MODES:
        raise MetricClarification(
            "association_mode must be one of owner_level, target_account_associated, or selected_company_associated."
        )
    scan_limit = _bounded_int(limit, default=SALES_CALL_DEFAULT_SCAN_LIMIT, maximum=HUBSPOT_SEARCH_TOTAL_LIMIT)
    window = _sales_call_window(start_local, end_local, timezone_name)
    owner_lookup = _owner_lookup_by_id()

    raw_calls: list[dict[str, Any]] = []
    source_totals: dict[str, int | None] = {}
    source_returned: dict[str, int] = {}
    truncated = False
    for owner_id in owner_ids:
        if _deadline_exceeded(deadline):
            truncated = True
            break
        filters = [
            {"propertyName": "hubspot_owner_id", "operator": "EQ", "value": owner_id},
            {"propertyName": "hs_timestamp", "operator": "GTE", "value": window["start_utc"]},
            {"propertyName": "hs_timestamp", "operator": "LTE", "value": window["end_utc"]},
        ]
        data = _object_search("calls", filters, CALL_PROPERTIES, limit=scan_limit, maximum=HUBSPOT_SEARCH_TOTAL_LIMIT)
        source_totals[owner_id] = data.get("total")
        source_returned[owner_id] = len(data.get("results", []))
        truncated = truncated or bool(data.get("truncated"))
        raw_calls.extend(data.get("results", []))

    filtered_calls = [call for call in raw_calls if _call_status_matches(call, status)]
    selected_company_ids: list[str] = []
    company_pool_truncated = False
    matched_company_ids: dict[str, list[str]] = {}
    association_details: dict[str, dict[str, list[str]]] = {}
    if mode == "target_account_associated":
        selected_company_ids, company_pool_truncated = _target_company_ids_for_sales_calls(countries, owner_ids, scan_limit)
    elif mode == "selected_company_associated":
        selected_company_ids = _scoped_selected_company_ids(company_ids, scope)
        if not selected_company_ids:
            raise MetricClarification("company_ids is required for selected_company_associated.")
    if selected_company_ids:
        call_ids = [str(call.get("id") or "").strip() for call in filtered_calls if str(call.get("id") or "").strip()]
        matched_company_ids, association_details = _associated_call_company_ids(call_ids, selected_company_ids, deadline)
        filtered_calls = [
            call for call in filtered_calls if str(call.get("id") or "").strip() in matched_company_ids
        ]
    elif mode != "owner_level":
        filtered_calls = []

    events = []
    for call in filtered_calls:
        call_id = str(call.get("id") or "").strip()
        events.append(
            _safe_sales_call_event(
                call,
                owner_lookup,
                mode,
                associations=matched_company_ids.get(call_id, []),
                association_details=association_details.get(call_id, {}),
            )
        )

    return {
        "events": events,
        "window": window,
        "association_mode": mode,
        "status_filter": str(status or "ANY").strip().upper() or "ANY",
        "source_call_total_before_status_filter_by_owner": source_totals,
        "source_call_returned_before_status_filter_by_owner": source_returned,
        "selected_company_count": len(selected_company_ids),
        "company_pool_truncated": company_pool_truncated,
        "requested_limit_per_owner": scan_limit,
        "returned_count": len(events),
        "has_more": bool(truncated or company_pool_truncated),
        "truncated": bool(truncated or company_pool_truncated),
    }


def _empty_call_metrics() -> dict[str, int]:
    return {
        "total_calls": 0,
        "completed_calls": 0,
        "completed_calls_gt_60s": 0,
        "connected_calls_120s_guardrail": 0,
        "completed_calls_exactly_60s_excluded_from_gt_60s": 0,
    }


def _add_call_metrics(metrics: dict[str, int], event: dict[str, Any]) -> None:
    metrics["total_calls"] += 1
    if event.get("completed"):
        metrics["completed_calls"] += 1
        duration_ms = int(round(float(event.get("duration_seconds") or 0) * 1000))
        if duration_ms > AE_COACHING_LONG_CALL_MIN_DURATION_MS:
            metrics["completed_calls_gt_60s"] += 1
        elif duration_ms == AE_COACHING_LONG_CALL_MIN_DURATION_MS:
            metrics["completed_calls_exactly_60s_excluded_from_gt_60s"] += 1
    if event.get("connected_call_120s_guardrail"):
        metrics["connected_calls_120s_guardrail"] += 1


def _summarize_sales_call_events(events: list[dict[str, Any]], owner_rows: list[dict[str, Any]]) -> dict[str, Any]:
    owner_metadata = {str(row.get("owner_id") or ""): row for row in owner_rows}
    owners: dict[str, dict[str, Any]] = {}
    totals = _empty_call_metrics()
    for row in owner_rows:
        owner_id = str(row.get("owner_id") or "").strip()
        if not owner_id:
            continue
        owners[owner_id] = {
            "owner_id": owner_id,
            "owner_email": row.get("owner_email") or "",
            "owner_name": row.get("owner_name") or "",
            "countries": row.get("countries") or [],
            "timezone": row.get("timezone") or "",
            **_empty_call_metrics(),
        }
    for event in events:
        owner_id = str(event.get("owner_id") or "").strip()
        if owner_id not in owners:
            meta = owner_metadata.get(owner_id, {})
            owners[owner_id] = {
                "owner_id": owner_id,
                "owner_email": event.get("owner_email") or meta.get("owner_email") or "",
                "owner_name": event.get("owner_name") or meta.get("owner_name") or "",
                "countries": meta.get("countries") or [],
                "timezone": meta.get("timezone") or "",
                **_empty_call_metrics(),
            }
        _add_call_metrics(owners[owner_id], event)
        _add_call_metrics(totals, event)
    return {"owners": list(owners.values()), "totals": totals}


@mcp.tool()
def resolve_nurture_scope(
    slack_user_email: str,
    countries: list[str] | None = None,
    owner_email: str | None = None,
) -> dict[str, Any]:
    """Resolve caller scope and allowed countries without returning business metrics."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked(scope.get("blocked_reason") or "Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        selected = _safe_countries(countries, scope["countries"])
        if not selected:
            return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))
        target_owner_id = None
        target_owner_email = ""
        if owner_email:
            target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)
        answer = {
            **_scope_response(scope, selected, target_owner_id, target_owner_email),
            "allowed_countries": list(scope.get("countries", ())),
            "canonical_email": scope.get("email"),
            "caller_role": scope.get("kind"),
            "timezone": "Asia/Singapore",
            "access_caveats": [
                "No business metrics returned.",
                "HubSpot ownership and country access still apply to downstream source tools.",
            ],
        }
        return {
            "answer": answer,
            "source": "NurtureAny runtime access policy plus HubSpot owner lookup when owner_email is supplied",
            "scope": _scope_response(scope, selected, target_owner_id, target_owner_email),
            "confidence": "verified",
            "caveat": "Scope resolver only. It does not read calls, companies, contacts, deals, tasks, notes, or campaign metrics.",
        }
    except (AccessPolicyError, ScopeError, MetricClarification) as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})


@mcp.tool()
def resolve_sales_owners(
    slack_user_email: str,
    countries: list[str] | None = None,
    owner_email: str | None = None,
    owner_name: str | None = None,
    owner_ids: list[str] | None = None,
    classified_sales_reps_only: bool = True,
    limit: int = 500,
) -> dict[str, Any]:
    """Resolve scoped HubSpot sales owners before owner/team metrics."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked(scope.get("blocked_reason") or "Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        selected = _safe_countries(countries, scope["countries"])
        if not selected:
            return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))
        rows, unresolved = _sales_owner_rows_for_scope(
            scope,
            selected,
            owner_ids=owner_ids,
            owner_emails=_normalize_owner_email_list(None, owner_email),
            owner_name=owner_name,
            classified_sales_reps_only=classified_sales_reps_only,
            limit=limit,
        )
        return {
            "answer": {
                "owners": rows,
                "owner_count": len(rows),
                "unresolved": unresolved,
                "classified_sales_reps_only": classified_sales_reps_only,
            },
            "source": "NurtureAny runtime access policy and HubSpot owners API",
            "scope": _scope_response(scope, selected),
            "total": len(rows),
            "requested_limit": _bounded_int(limit, default=500, maximum=HUBSPOT_SEARCH_TOTAL_LIMIT),
            "returned_count": len(rows),
            "has_more": len(rows) >= _bounded_int(limit, default=500, maximum=HUBSPOT_SEARCH_TOTAL_LIMIT),
            "truncated": len(rows) >= _bounded_int(limit, default=500, maximum=HUBSPOT_SEARCH_TOTAL_LIMIT),
            "will_mutate_hubspot": False,
            "confidence": "needs-check" if unresolved else "verified",
            "caveat": "Owner resolver only. Use the returned owner_id values for scoped rep/team metric tools.",
        }
    except (AccessPolicyError, ScopeError, MetricClarification) as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email, "owner_name": owner_name})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def list_sales_call_events(
    slack_user_email: str,
    countries: list[str] | None = None,
    owner_ids: list[str] | None = None,
    owner_emails: list[str] | None = None,
    owner_email: str | None = None,
    owner_name: str | None = None,
    company_ids: list[str] | None = None,
    start_local: str = "",
    end_local: str = "",
    timezone: str = "Asia/Singapore",
    status: str = "ANY",
    association_mode: str = "owner_level",
    classified_sales_reps_only: bool = True,
    limit: int = SALES_CALL_DEFAULT_SCAN_LIMIT,
) -> dict[str, Any]:
    """List normalized safe HubSpot call events for scoped owners and a local-time window."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked(scope.get("blocked_reason") or "Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        selected = _safe_countries(countries, scope["countries"])
        if not selected:
            return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))
        resolved_owner_ids, owner_rows, unresolved = _resolve_sales_owner_ids_for_activity(
            scope,
            selected,
            owner_ids=owner_ids,
            owner_emails=owner_emails,
            owner_email=owner_email,
            owner_name=owner_name,
            classified_sales_reps_only=classified_sales_reps_only,
        )
        data = _list_sales_call_events_core(
            scope,
            selected,
            resolved_owner_ids,
            start_local,
            end_local,
            timezone,
            status,
            association_mode,
            company_ids=company_ids,
            limit=limit,
        )
        return {
            "answer": {
                "events": data["events"],
                "event_count": len(data["events"]),
                "owners": owner_rows,
                "unresolved_owners": unresolved,
                "association_mode": data["association_mode"],
                "status_filter": data["status_filter"],
                "raw_body_returned": False,
            },
            "source": "HubSpot calls metadata via scoped owner/time-window search",
            "scope": {
                **_scope_response(scope, selected),
                "owner_ids": resolved_owner_ids,
                "window": data["window"],
                "association_mode": data["association_mode"],
            },
            "requested_limit": data["requested_limit_per_owner"],
            "returned_count": data["returned_count"],
            "has_more": data["has_more"],
            "truncated": data["truncated"],
            "will_mutate_hubspot": False,
            "confidence": "needs-check" if data["truncated"] or unresolved else "verified",
            "caveat": "Safe call metadata only. No call bodies, transcripts, recordings, raw HubSpot rows, phone numbers, or HubSpot mutation.",
        }
    except (AccessPolicyError, ScopeError, MetricClarification) as error:
        return _blocked(str(error), {"caller_email": slack_user_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def summarize_sales_call_stats(
    slack_user_email: str,
    countries: list[str] | None = None,
    owner_ids: list[str] | None = None,
    owner_emails: list[str] | None = None,
    owner_email: str | None = None,
    owner_name: str | None = None,
    company_ids: list[str] | None = None,
    start_local: str = "",
    end_local: str = "",
    timezone: str = "Asia/Singapore",
    status: str = "ANY",
    thresholds: list[int] | None = None,
    association_mode: str = "owner_level",
    classified_sales_reps_only: bool = True,
    limit: int = SALES_CALL_DEFAULT_SCAN_LIMIT,
) -> dict[str, Any]:
    """Summarize deterministic call counts by owner using the shared call primitive."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked(scope.get("blocked_reason") or "Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        selected = _safe_countries(countries, scope["countries"])
        if not selected:
            return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))
        resolved_owner_ids, owner_rows, unresolved = _resolve_sales_owner_ids_for_activity(
            scope,
            selected,
            owner_ids=owner_ids,
            owner_emails=owner_emails,
            owner_email=owner_email,
            owner_name=owner_name,
            classified_sales_reps_only=classified_sales_reps_only,
        )
        data = _list_sales_call_events_core(
            scope,
            selected,
            resolved_owner_ids,
            start_local,
            end_local,
            timezone,
            status,
            association_mode,
            company_ids=company_ids,
            limit=limit,
        )
        summary = _summarize_sales_call_events(data["events"], owner_rows)
        threshold_values = sorted({int(value) for value in (thresholds or [60, 120]) if int(value) > 0})
        return {
            "answer": {
                "totals": summary["totals"],
                "owners": summary["owners"],
                "thresholds_seconds": {
                    "completed_calls_gt_60s": 60,
                    "connected_calls_120s_guardrail": 120,
                    "requested": threshold_values,
                },
                "association_mode": data["association_mode"],
                "status_filter": data["status_filter"],
                "source_call_total_before_status_filter_by_owner": data["source_call_total_before_status_filter_by_owner"],
                "source_call_returned_before_status_filter_by_owner": data["source_call_returned_before_status_filter_by_owner"],
                "selected_company_count": data["selected_company_count"],
                "raw_body_returned": False,
                "used_long_call_without_appointment_candidates": False,
                "will_mutate_hubspot": False,
            },
            "source": "HubSpot calls metadata via list_sales_call_events primitive plus deterministic reducer",
            "scope": {
                **_scope_response(scope, selected),
                "owner_ids": resolved_owner_ids,
                "window": data["window"],
                "association_mode": data["association_mode"],
            },
            "requested_limit": data["requested_limit_per_owner"],
            "returned_count": data["returned_count"],
            "has_more": data["has_more"],
            "truncated": data["truncated"],
            "will_mutate_hubspot": False,
            "confidence": "needs-check" if data["truncated"] or unresolved else "verified",
            "caveat": "Call stats are deterministic counts over safe HubSpot call metadata. `completed_calls_gt_60s` is strictly duration_seconds > 60; exactly 60s is excluded. `connected_calls_120s_guardrail` is completed calls with duration_seconds >= 120. No coaching candidate caps are used.",
        }
    except (AccessPolicyError, ScopeError, MetricClarification, ValueError) as error:
        return _blocked(str(error), {"caller_email": slack_user_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


def _detail_account_row(
    company: dict[str, Any],
    account_activity: dict[str, Any],
    missing_clean_lead_fields: list[str],
    open_followup_tasks: list[dict[str, Any]],
    decision_maker_coverage: dict[str, Any],
) -> dict[str, Any]:
    summary = _summarize_company(company)
    counts = account_activity.get("counts", {})
    return {
        "company_id": summary.get("company_id"),
        "name": summary.get("name"),
        "country": summary.get("country"),
        "owner_id": summary.get("owner_id"),
        "touch_count": counts.get("touches", 0),
        "latest_activity_at": _company_latest_safe_activity_at(company, account_activity),
        "connected_call_count": counts.get("connected_calls", 0),
        "warm_activity_points": counts.get("warm_activity_points", 0),
        "open_followup_task_count": len(open_followup_tasks),
        "missing_clean_lead_fields": missing_clean_lead_fields,
        "decision_maker_coverage": decision_maker_coverage,
        "decision_maker_coverage_status": decision_maker_coverage.get("status"),
        "decision_maker_count": decision_maker_coverage.get("verified_decision_maker_count", 0),
        "buying_role_contact_count": decision_maker_coverage.get("buying_role_contact_count", 0),
        "role_inferred_decision_maker_candidate_count": decision_maker_coverage.get(
            "role_inferred_decision_maker_candidate_count",
            0,
        ),
    }


def _main_priority_issue(row: dict[str, Any]) -> str:
    if row["worked_account_count"] < row["weekly_account_target"]:
        return "weak account coverage against 120/150 weekly baseline"
    if row["connected_call_count"] < CONNECTED_CALL_WEEKLY_TARGET:
        return "connected calls below 40-call guardrail"
    if row["single_touch_account_count"]:
        return "worked accounts lack double tap"
    if row["dirty_account_count"]:
        return "clean-lead fields incomplete"
    if row["warm_activity_points"] == 0:
        return "no warm activity proof logged"
    return "operating rhythm on track"


def _priority_owner_row(
    owner_id: str,
    companies: list[dict[str, Any]],
    owner_lookup: dict[str, dict[str, Any]],
    contact_index: dict[str, list[str]],
    contact_detail_index: dict[str, list[dict[str, Any]]],
    deal_index: dict[str, list[str]],
    task_index: dict[str, list[dict[str, Any]]],
    activity_index: dict[str, dict[str, Any]],
    since_dt: datetime,
    until_dt: datetime,
    stale_cutoff_dt: datetime,
) -> dict[str, Any]:
    worked_accounts = []
    double_tapped_accounts = []
    untouched_accounts = []
    stale_accounts = []
    dirty_accounts = []
    open_followup_account_rows = []
    missing_contact_account_count = 0
    missing_decision_maker_account_count = 0
    role_only_decision_maker_account_count = 0
    decision_maker_needs_check_account_count = 0
    connected_call_count = 0
    warm_activity_points = 0
    whatsapp_communications = 0
    activity_truncated = False
    weak_evidence = False

    for company in companies:
        company_id = str(company.get("id") or "")
        contact_ids = contact_index.get(company_id, [])
        deal_ids = deal_index.get(company_id, [])
        safe_contacts = contact_detail_index.get(company_id, [])
        account_activity = activity_index.get(company_id) or _account_week_activity(
            company,
            contact_ids,
            deal_ids,
            since_dt,
            until_dt,
        )
        counts = account_activity.get("counts", {})
        open_followup_tasks = task_index.get(company_id, [])
        decision_maker_coverage = _decision_maker_coverage(company.get("properties", {}), safe_contacts, len(contact_ids))
        missing_clean_lead_fields = _clean_lead_missing_fields(company, len(contact_ids), safe_contacts)
        detail = _detail_account_row(
            company,
            account_activity,
            missing_clean_lead_fields,
            open_followup_tasks,
            decision_maker_coverage,
        )

        if counts.get("touches", 0) > 0:
            worked_accounts.append(detail)
        else:
            untouched_accounts.append(detail)
        if counts.get("touches", 0) >= 2:
            double_tapped_accounts.append(detail)
        if _is_stale_account(company, account_activity, stale_cutoff_dt):
            stale_accounts.append(detail)
        if missing_clean_lead_fields:
            dirty_accounts.append(detail)
        if open_followup_tasks:
            open_followup_account_rows.append(detail)
        if "associated contact" in missing_clean_lead_fields:
            missing_contact_account_count += 1
        if "decision maker" in missing_clean_lead_fields:
            missing_decision_maker_account_count += 1
        if (
            decision_maker_coverage.get("verified_decision_maker_count", 0) < 1
            and decision_maker_coverage.get("role_inferred_decision_maker_candidate_count", 0) > 0
        ):
            role_only_decision_maker_account_count += 1
        if decision_maker_coverage.get("status") == "needs-check":
            decision_maker_needs_check_account_count += 1

        connected_call_count += counts.get("connected_calls", 0)
        warm_activity_points += counts.get("warm_activity_points", 0)
        whatsapp_communications += counts.get("whatsapp_communications", 0)
        activity_truncated = bool(activity_truncated or account_activity.get("truncated"))
        weak_evidence = bool(weak_evidence or account_activity.get("weak_evidence"))

    locked_pool_count = len(companies)
    weekly_target = min(PRIORITY_ACCOUNT_WEEKLY_WORKED_TARGET, locked_pool_count)
    worked_account_count = len(worked_accounts)
    owner_data = _owner_display(owner_id, owner_lookup)
    row: dict[str, Any] = {
        **owner_data,
        "locked_pool_count": locked_pool_count,
        "weekly_account_target": weekly_target,
        "worked_account_count": worked_account_count,
        "120_150_accounts_worked": f"{worked_account_count}/{locked_pool_count} worked; target {weekly_target}/{PRIORITY_ACCOUNT_LOCKED_POOL_BASELINE}",
        "coverage_hit_miss": "hit" if worked_account_count >= weekly_target else "miss",
        "double_tapped_account_count": len(double_tapped_accounts),
        "single_touch_account_count": max(worked_account_count - len(double_tapped_accounts), 0),
        "untouched_account_count": len(untouched_accounts),
        "stale_account_count": len(stale_accounts),
        "dirty_account_count": len(dirty_accounts),
        "missing_contact_account_count": missing_contact_account_count,
        "missing_decision_maker_account_count": missing_decision_maker_account_count,
        "role_only_decision_maker_account_count": role_only_decision_maker_account_count,
        "decision_maker_needs_check_account_count": decision_maker_needs_check_account_count,
        "open_followup_account_count": len(open_followup_account_rows),
        "connected_call_count": connected_call_count,
        "40_connected_calls": f"{connected_call_count}/{CONNECTED_CALL_WEEKLY_TARGET}",
        "connected_call_hit_miss": "hit" if connected_call_count >= CONNECTED_CALL_WEEKLY_TARGET else "miss",
        "warm_activity_points": warm_activity_points,
        "whatsapp_communications": whatsapp_communications,
        "friday_correction_needed": bool(
            worked_account_count < weekly_target
            or connected_call_count < CONNECTED_CALL_WEEKLY_TARGET
            or untouched_accounts
            or stale_accounts
            or dirty_accounts
        ),
        "untouched_accounts": untouched_accounts[:FRIDAY_REVIEW_DETAIL_LIMIT],
        "stale_accounts": stale_accounts[:FRIDAY_REVIEW_DETAIL_LIMIT],
        "dirty_accounts": dirty_accounts[:FRIDAY_REVIEW_DETAIL_LIMIT],
        "open_followup_accounts": open_followup_account_rows[:FRIDAY_REVIEW_DETAIL_LIMIT],
        "evidence_completeness": "needs-check" if activity_truncated or weak_evidence else "complete",
        "activity_truncated": activity_truncated,
        "weak_activity_evidence": weak_evidence,
    }
    row["main_issue"] = _main_priority_issue(row)
    return row


def _priority_account_coverage(
    slack_user_email: str,
    countries: list[str] | None = None,
    owner_email: str | None = None,
    week_start: str = "",
    week_end: str = "",
    limit: int = PRIORITY_ACCOUNT_RETURN_LIMIT,
    manager_only: bool = False,
    include_internal: bool = False,
    soft_timeout_seconds: int = 0,
    deadline: float | None = None,
) -> dict[str, Any]:
    deadline = deadline or _hubspot_soft_deadline(soft_timeout_seconds)
    scope = _caller_scope(slack_user_email)
    if scope["kind"] == "blocked":
        return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
    if scope["kind"] not in MANAGER_ADMIN_SCOPE_KINDS | {"ae"}:
        return _blocked(
            "Priority-account coverage is available only to managers/admins or AE self-audits.",
            _scope_response(scope, list(scope.get("countries", ()))),
        )
    if manager_only and scope["kind"] not in {"admin", "manager"}:
        return _blocked("Friday sales review is manager/admin only by default.", _scope_response(scope, list(scope.get("countries", ()))))

    selected = _safe_countries(countries, scope["countries"])
    if not selected:
        return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))

    target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)
    requested_limit = _bounded_int(limit, default=PRIORITY_ACCOUNT_RETURN_LIMIT, maximum=PRIORITY_ACCOUNT_RETURN_LIMIT)
    week = _week_window(week_start, week_end)
    data = _company_search(
        _target_filters(selected, target_owner_id),
        requested_limit,
        maximum=PRIORITY_ACCOUNT_RETURN_LIMIT,
        sorts=[{"propertyName": "hubspot_owner_id", "direction": "ASCENDING"}],
    )
    companies = data.get("results", [])
    company_ids = [str(company.get("id") or "") for company in companies if company.get("id")]
    contact_index = _batch_association_ids_until("companies", "contacts", company_ids, deadline)
    contact_detail_index = {} if _deadline_exceeded(deadline) else _safe_contact_index(contact_index)
    deal_index = {} if _deadline_exceeded(deadline) else _batch_association_ids_until("companies", "deals", company_ids, deadline)
    activity_index = (
        {}
        if _deadline_exceeded(deadline)
        else _week_activity_index_for_companies(companies, contact_index, deal_index, week["start_dt"], week["end_dt"], deadline)
    )
    partial_due_to_soft_timeout = _deadline_exceeded(deadline)
    if partial_due_to_soft_timeout:
        activity_index = {}
        for company_id in company_ids:
            partial_activity = _empty_week_activity()
            partial_activity["truncated"] = True
            partial_activity["confidence"] = "needs-check"
            activity_index[company_id] = partial_activity

    by_owner: dict[str, list[dict[str, Any]]] = {}
    for company in companies:
        owner_id = str(company.get("properties", {}).get("hubspot_owner_id") or "")
        by_owner.setdefault(owner_id, []).append(company)

    owner_lookup = {} if _deadline_exceeded(deadline) else _owner_lookup_by_id()
    stale_cutoff_dt = week["end_dt"] - timedelta(days=STALE_ACCOUNT_DAYS)
    owner_rows = []
    task_context = (
        {
            "tasks_by_company": {},
            "metadata": {
                "total": 0,
                "requested_limit": 0,
                "returned_count": 0,
                "has_more": True,
                "truncated": True,
                **_soft_timeout_metadata(True, soft_timeout_seconds),
            },
            "truncated": True,
            "partial_due_to_soft_timeout": True,
        }
        if _deadline_exceeded(deadline)
        else _sales_followup_task_index_for_company_associations(
            companies,
            contact_index,
            deal_index,
            TASK_SEARCH_AIRTIGHT_RESULT_LIMIT,
            deadline,
        )
    )
    partial_due_to_soft_timeout = bool(partial_due_to_soft_timeout or task_context.get("partial_due_to_soft_timeout"))
    task_index = task_context.get("tasks_by_company", {})
    task_truncated = bool(task_context.get("truncated"))
    task_indexes_by_owner: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for owner_id, owner_companies in by_owner.items():
        if _deadline_exceeded(deadline):
            partial_due_to_soft_timeout = True
            break
        owner_task_index = {
            str(company.get("id") or ""): task_index.get(str(company.get("id") or ""), [])
            for company in owner_companies
            if company.get("id")
        }
        task_indexes_by_owner[owner_id] = owner_task_index
        owner_rows.append(
            _priority_owner_row(
                owner_id,
                owner_companies,
                owner_lookup,
                contact_index,
                contact_detail_index,
                deal_index,
                owner_task_index,
                activity_index,
                week["start_dt"],
                week["end_dt"],
                stale_cutoff_dt,
            )
        )

    owner_rows.sort(key=lambda row: (str(row.get("owner_email") or row.get("owner_id") or ""), str(row.get("owner_id") or "")))
    metadata = _search_metadata(data)
    activity_truncated = any(row.get("activity_truncated") for row in owner_rows)
    weak_evidence = any(row.get("weak_activity_evidence") for row in owner_rows)
    result_truncated = bool(metadata.get("truncated") or task_truncated or activity_truncated or partial_due_to_soft_timeout)
    scope_response = _scope_response(scope, selected, target_owner_id, target_owner_email)
    scope_response.update(
        {
            "week_start": week["week_start"],
            "week_end": week["week_end"],
            "timezone": week["timezone"],
        }
    )
    response: dict[str, Any] = {
        "answer": {
            "owners": owner_rows,
            "summary": {
                "owner_count": len(owner_rows),
                "locked_pool_count": sum(row.get("locked_pool_count", 0) for row in owner_rows),
                "worked_account_count": sum(row.get("worked_account_count", 0) for row in owner_rows),
                "untouched_account_count": sum(row.get("untouched_account_count", 0) for row in owner_rows),
                "stale_account_count": sum(row.get("stale_account_count", 0) for row in owner_rows),
                "dirty_account_count": sum(row.get("dirty_account_count", 0) for row in owner_rows),
                "missing_contact_account_count": sum(row.get("missing_contact_account_count", 0) for row in owner_rows),
                "missing_decision_maker_account_count": sum(
                    row.get("missing_decision_maker_account_count", 0) for row in owner_rows
                ),
                "role_only_decision_maker_account_count": sum(
                    row.get("role_only_decision_maker_account_count", 0) for row in owner_rows
                ),
                "decision_maker_needs_check_account_count": sum(
                    row.get("decision_maker_needs_check_account_count", 0) for row in owner_rows
                ),
                "connected_call_count": sum(row.get("connected_call_count", 0) for row in owner_rows),
                "warm_activity_points": sum(row.get("warm_activity_points", 0) for row in owner_rows),
                "friday_correction_owner_count": len([row for row in owner_rows if row.get("friday_correction_needed")]),
            },
        },
        "source": "HubSpot target-account companies plus safe calls, meetings, communications, notes, tasks, and associations",
        "scope": scope_response,
        **metadata,
        **_soft_timeout_metadata(partial_due_to_soft_timeout, soft_timeout_seconds),
        "confidence": "needs-check" if result_truncated or weak_evidence else "verified",
        "caveat": _coverage_caveat(
            {**metadata, "truncated": result_truncated},
            "Read-only priority account coverage audit. Raw call bodies, meeting bodies, recordings, phone numbers, note bodies, task bodies, attachments, and exports are omitted.",
        ),
    }
    if include_internal:
        response["_internal"] = {
            "companies": companies,
            "company_contact_ids": contact_index,
            "company_deal_ids": deal_index,
            "activity_index": activity_index,
            "task_indexes_by_owner": task_indexes_by_owner,
            "week": week,
        }
    return response


def _date_in_week(value: str, week: dict[str, Any]) -> bool:
    parsed = _datetime_value(value)
    return bool(parsed and week["start_dt"] <= parsed <= week["end_dt"])


def _deal_counts_for_friday(
    companies: list[dict[str, Any]],
    company_deal_ids: dict[str, list[str]],
    week: dict[str, Any],
    stage_config: dict[str, Any],
    deadline: float | None = None,
) -> dict[str, Any]:
    deal_ids: list[str] = []
    company_owner_by_deal: dict[str, str] = {}
    for company in companies:
        owner_id = str(company.get("properties", {}).get("hubspot_owner_id") or "")
        company_id = str(company.get("id") or "")
        for deal_id in company_deal_ids.get(company_id, []):
            if deal_id not in deal_ids:
                deal_ids.append(deal_id)
                company_owner_by_deal[deal_id] = owner_id

    if not stage_config.get("configured"):
        return {
            "configured": False,
            "by_owner": {},
            "totals": {"qos": None, "qo_met": None, "qo_met_pct": None, "deals_closed": None},
            "confidence": "needs-check",
            "caveat": "QO, QO Met, and closed-won stage IDs are not fully configured; hygiene and activity counts are still returned.",
        }

    partial_due_to_deadline = _deadline_exceeded(deadline)
    raw_deals = [] if partial_due_to_deadline else _batch_read_until("deals", deal_ids, DEAL_PROPERTIES, deadline)
    partial_due_to_deadline = bool(partial_due_to_deadline or _deadline_exceeded(deadline))
    by_owner: dict[str, dict[str, Any]] = {}
    totals = {"qos": 0, "qo_met": 0, "deals_closed": 0}
    weak_dates = False
    for deal in raw_deals:
        props = deal.get("properties", {})
        if stage_config["pipeline_ids"] and str(props.get("pipeline") or "") not in stage_config["pipeline_ids"]:
            continue
        deal_id = str(deal.get("id") or "")
        owner_id = str(props.get("hubspot_owner_id") or company_owner_by_deal.get(deal_id) or "")
        owner_counts = by_owner.setdefault(owner_id, {"qos": 0, "qo_met": 0, "deals_closed": 0})
        stage = str(props.get("dealstage") or "")
        createdate = str(props.get("createdate") or props.get("hs_lastmodifieddate") or "")
        closedate = str(props.get("closedate") or "")

        if stage in stage_config["qo_stage_ids"]:
            if _date_in_week(createdate, week):
                totals["qos"] += 1
                owner_counts["qos"] += 1
            elif not createdate:
                weak_dates = True
        if stage in stage_config["qo_met_stage_ids"]:
            if _date_in_week(createdate, week):
                totals["qo_met"] += 1
                owner_counts["qo_met"] += 1
            elif not createdate:
                weak_dates = True
        if stage in stage_config["closed_won_stage_ids"]:
            if _date_in_week(closedate, week):
                totals["deals_closed"] += 1
                owner_counts["deals_closed"] += 1
            elif not closedate:
                weak_dates = True

    totals["qo_met_pct"] = round((totals["qo_met"] / totals["qos"]) * 100, 1) if totals["qos"] else None
    for owner_counts in by_owner.values():
        owner_counts["qo_met_pct"] = round((owner_counts["qo_met"] / owner_counts["qos"]) * 100, 1) if owner_counts["qos"] else None
    return {
        "configured": True,
        "by_owner": by_owner,
        "totals": totals,
        **_soft_timeout_metadata(partial_due_to_deadline),
        "confidence": "needs-check" if weak_dates or partial_due_to_deadline else "verified",
        "caveat": "Deal funnel counts use configured HubSpot pipeline/stage IDs and safe deal dates; no deal bodies or attachments are exported.",
    }


def _friday_hygiene_summary(owner_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in owner_rows:
        rows.append(
            {
                "ae": row.get("owner_email") or row.get("owner_name") or row.get("owner_id"),
                "owner_id": row.get("owner_id"),
                "120_150_accounts_worked": row.get("120_150_accounts_worked"),
                "40_connected_calls": row.get("40_connected_calls"),
                "hit_miss": "hit"
                if row.get("coverage_hit_miss") == "hit" and row.get("connected_call_hit_miss") == "hit"
                else "miss",
                "friday_correction_needed": row.get("friday_correction_needed"),
                "main_issue": row.get("main_issue"),
                "locked_pool_count": row.get("locked_pool_count"),
                "worked_account_count": row.get("worked_account_count"),
                "double_tapped_account_count": row.get("double_tapped_account_count"),
                "untouched_account_count": row.get("untouched_account_count"),
                "stale_account_count": row.get("stale_account_count"),
                "dirty_account_count": row.get("dirty_account_count"),
                "missing_contact_account_count": row.get("missing_contact_account_count"),
                "missing_decision_maker_account_count": row.get("missing_decision_maker_account_count"),
                "role_only_decision_maker_account_count": row.get("role_only_decision_maker_account_count"),
                "decision_maker_needs_check_account_count": row.get("decision_maker_needs_check_account_count"),
                "warm_activity_points": row.get("warm_activity_points"),
            }
        )
    return rows


def _friday_funnel_snapshot(owner_rows: list[dict[str, Any]], deal_counts: dict[str, Any]) -> dict[str, Any]:
    by_ae = []
    for row in owner_rows:
        owner_id = str(row.get("owner_id") or "")
        owner_deals = deal_counts.get("by_owner", {}).get(owner_id, {})
        by_ae.append(
            {
                "ae": row.get("owner_email") or row.get("owner_name") or owner_id,
                "owner_id": owner_id,
                "accounts_worked": row.get("worked_account_count", 0),
                "connected_calls": row.get("connected_call_count", 0),
                "qos": owner_deals.get("qos") if deal_counts.get("configured") else None,
                "qo_met": owner_deals.get("qo_met") if deal_counts.get("configured") else None,
                "qo_met_pct": owner_deals.get("qo_met_pct") if deal_counts.get("configured") else None,
                "deals_closed": owner_deals.get("deals_closed") if deal_counts.get("configured") else None,
                "warm_activity_points": row.get("warm_activity_points", 0),
                "caveats": [
                    caveat
                    for caveat in [
                        "activity evidence truncated" if row.get("activity_truncated") else "",
                        "activity timestamp evidence incomplete" if row.get("weak_activity_evidence") else "",
                    ]
                    if caveat
                ],
            }
        )

    team_totals = {
        "accounts_worked": sum(row.get("worked_account_count", 0) for row in owner_rows),
        "connected_calls": sum(row.get("connected_call_count", 0) for row in owner_rows),
        "qos": deal_counts.get("totals", {}).get("qos"),
        "qo_met": deal_counts.get("totals", {}).get("qo_met"),
        "qo_met_pct": deal_counts.get("totals", {}).get("qo_met_pct"),
        "deals_closed": deal_counts.get("totals", {}).get("deals_closed"),
        "warm_activity_points": sum(row.get("warm_activity_points", 0) for row in owner_rows),
    }
    return {"team_totals": team_totals, "by_ae": by_ae, "caveats": [deal_counts.get("caveat")]}


def _coaching_observations(owner_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observations = []
    for row in owner_rows:
        ae = row.get("owner_email") or row.get("owner_name") or row.get("owner_id")
        if row.get("worked_account_count", 0) < row.get("weekly_account_target", 0):
            observations.append(
                {
                    "ae": ae,
                    "observation": "Account coverage missed the 120/150 weekly rhythm.",
                    "evidence": row.get("120_150_accounts_worked"),
                }
            )
        if row.get("single_touch_account_count", 0):
            observations.append(
                {
                    "ae": ae,
                    "observation": "Double tap is incomplete; worked accounts have only one logged touch.",
                    "evidence": f"{row.get('single_touch_account_count')} single-touch account(s)",
                }
            )
        if row.get("connected_call_count", 0) < CONNECTED_CALL_WEEKLY_TARGET:
            observations.append(
                {
                    "ae": ae,
                    "observation": "Connected-call volume is below the 40-call weekly guardrail.",
                    "evidence": row.get("40_connected_calls"),
                }
            )
        if row.get("dirty_account_count", 0):
            observations.append(
                {
                    "ae": ae,
                    "observation": "Clean-lead coverage is weak for part of the locked pool.",
                    "evidence": (
                        f"{row.get('dirty_account_count')} dirty/unworkable account(s); "
                        f"{row.get('missing_contact_account_count', 0)} missing contact, "
                        f"{row.get('missing_decision_maker_account_count', 0)} missing decision maker"
                    ),
                }
            )
        if row.get("warm_activity_points", 0) == 0:
            observations.append(
                {
                    "ae": ae,
                    "observation": "No warm activity proof was found in completed meetings.",
                    "evidence": "0 warm activity points",
                }
            )
    return observations[:20]


def _next_week_actions(owner_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions = []
    for row in owner_rows:
        ae = row.get("owner_email") or row.get("owner_name") or row.get("owner_id")
        if row.get("untouched_account_count", 0):
            actions.append(
                {
                    "ae": ae,
                    "action": "Start Monday by clearing untouched locked accounts until 120/150 coverage is back on pace.",
                    "accounts": row.get("untouched_accounts", [])[:10],
                }
            )
        if row.get("single_touch_account_count", 0):
            actions.append(
                {
                    "ae": ae,
                    "action": "Double tap the single-touch accounts before Friday correction; use WhatsApp plus a call or meeting ask.",
                    "count": row.get("single_touch_account_count"),
                }
            )
        if row.get("connected_call_count", 0) < CONNECTED_CALL_WEEKLY_TARGET:
            actions.append(
                {
                    "ae": ae,
                    "action": "Plan call blocks to reach 40 connected calls, counting only completed HubSpot calls of at least 120 seconds.",
                    "current": row.get("connected_call_count"),
                    "target": CONNECTED_CALL_WEEKLY_TARGET,
                }
            )
        if row.get("dirty_account_count", 0):
            actions.append(
                {
                    "ae": ae,
                    "action": "Clean dirty accounts before pushing them through nurture: industry, headcount, current tools, contract end date, associated contact, and verified decision maker.",
                    "accounts": row.get("dirty_accounts", [])[:10],
                }
            )
        if row.get("warm_activity_points", 0) == 0:
            actions.append(
                {
                    "ae": ae,
                    "action": "Book and log one warm activity with a completed meeting title/type such as HHH, LL, coffee, lunch, dinner, cosy, ABM, event, appreciation afternoon, or sports.",
                }
            )
    return actions[:30]


def _support_needed(coverage: dict[str, Any], deal_counts: dict[str, Any]) -> list[str]:
    support = []
    if coverage.get("truncated"):
        support.append("Increase or narrow the scoped account limit before presenting exact team counts.")
    if coverage.get("confidence") == "needs-check":
        support.append("Review accounts with truncated or weak activity evidence before using the report in coaching.")
    if not deal_counts.get("configured"):
        support.append(
            "Configure HubSpot pipeline/stage IDs for QO, QO Met, and closed-won counts before treating funnel numbers as verified."
        )
    elif deal_counts.get("confidence") == "needs-check":
        support.append("Review deal date completeness for QO/QO Met/closed-won attribution.")
    return support


def _manager_chase_rep(row: dict[str, Any]) -> dict[str, str]:
    return {
        "owner_id": str(row.get("owner_id") or ""),
        "owner_email": _normalize_email(str(row.get("owner_email") or "")),
        "owner_name": str(row.get("owner_name") or ""),
    }


def _manager_chase_rep_label(rep: dict[str, str]) -> str:
    return rep.get("owner_email") or rep.get("owner_name") or rep.get("owner_id") or "rep"


def _manager_chase_account(detail: dict[str, Any] | None) -> dict[str, Any]:
    if not detail:
        return {}
    return {
        "company_id": detail.get("company_id") or "",
        "name": detail.get("name") or detail.get("company_name") or "",
        "country": detail.get("country") or "",
        "latest_activity_at": detail.get("latest_activity_at") or "",
    }


def _manager_chase_sentence(text: str, limit: int = 260) -> str:
    return _short_text(re.sub(r"\s+", " ", str(text or "")).strip(), limit)


def _manager_chase_draft(
    rep: dict[str, str],
    ask: str,
    deadline: str,
    fallback_action: str,
    account: dict[str, Any] | None = None,
) -> str:
    rep_label = _manager_chase_rep_label(rep)
    account_name = str((account or {}).get("name") or "").strip()
    topic = f" for {account_name}" if account_name else ""
    return _manager_chase_sentence(
        f"{rep_label} give us timeline{topic}: {ask} {deadline}. "
        f"If blocked, {fallback_action}"
    )


def _manager_chase_row(
    *,
    rep: dict[str, str],
    trigger: str,
    evidence: str,
    ask: str,
    deadline: str,
    fallback_action: str,
    source: str,
    account: dict[str, Any] | None = None,
    source_permalink: str = "",
    confidence: str = "needs-check",
    caveat: str = "",
) -> dict[str, Any]:
    safe_account = account or {}
    row = {
        "rep": rep,
        "account": safe_account,
        "trigger": trigger,
        "evidence": _manager_chase_sentence(evidence),
        "ask": _manager_chase_sentence(ask),
        "deadline": deadline,
        "fallback_action": _manager_chase_sentence(fallback_action),
        "manager_draft_text": _manager_chase_draft(rep, ask, deadline, fallback_action, safe_account),
        "source": source,
        "confidence": confidence,
        "caveat": caveat or "Manager draft only; no Slack tag, external message, or HubSpot mutation was performed.",
    }
    if source_permalink:
        row["source_permalink"] = source_permalink
    return row


def _manager_chase_rows_from_owner(
    owner_row: dict[str, Any],
    slack_context_summary: str = "",
    slack_source_permalink: str = "",
) -> list[dict[str, Any]]:
    rep = _manager_chase_rep(owner_row)
    source = "HubSpot priority-account coverage and selected Slack context" if slack_context_summary else "HubSpot priority-account coverage"
    rows: list[dict[str, Any]] = []

    if slack_context_summary:
        rows.append(
            _manager_chase_row(
                rep=rep,
                trigger="selected_slack_blocker",
                evidence=(
                    f"Selected Slack context: {_manager_chase_sentence(slack_context_summary)}. "
                    f"HubSpot rhythm: {owner_row.get('120_150_accounts_worked')}; calls {owner_row.get('40_connected_calls')}."
                ),
                ask="turn the blocker into a dated next step and log the outcome in HubSpot",
                deadline="by EOD today",
                fallback_action="call the stakeholder once, propose the closest concrete option, and log yes/no/next date.",
                source=source,
                source_permalink=slack_source_permalink,
            )
        )

    for detail in owner_row.get("open_followup_accounts", [])[:3]:
        account = _manager_chase_account(detail)
        rows.append(
            _manager_chase_row(
                rep=rep,
                account=account,
                trigger="open_followup_task",
                evidence=(
                    f"{detail.get('open_followup_task_count', 0)} open sales-owned follow-up task(s); "
                    f"latest safe activity {detail.get('latest_activity_at') or 'not found'}."
                ),
                ask="confirm the next step, due date, and whether this account is still live",
                deadline="by EOD today",
                fallback_action="close the loop with one call or WhatsApp, then update the open HubSpot task.",
                source=source,
            )
        )

    for detail in owner_row.get("untouched_accounts", [])[:3]:
        account = _manager_chase_account(detail)
        rows.append(
            _manager_chase_row(
                rep=rep,
                account=account,
                trigger="untouched_account",
                evidence="0 logged touches in the selected week; this blocks the 120/150 coverage rhythm.",
                ask="send the first relevant touch and log it, or state why the account is not workable",
                deadline="before tomorrow morning nurture block",
                fallback_action="ask manager for a deliberate swap instead of leaving the account untouched.",
                source=source,
            )
        )

    for detail in owner_row.get("stale_accounts", [])[:2]:
        account = _manager_chase_account(detail)
        rows.append(
            _manager_chase_row(
                rep=rep,
                account=account,
                trigger="stale_account",
                evidence=f"Latest safe activity is {detail.get('latest_activity_at') or 'missing'}; stale cutoff is {STALE_ACCOUNT_DAYS} days.",
                ask="give a concrete next touch and date, or mark the real blocker",
                deadline="by EOD today",
                fallback_action="use a go/no-go ask and log the reason if the account should pause.",
                source=source,
            )
        )

    for detail in owner_row.get("dirty_accounts", [])[:2]:
        account = _manager_chase_account(detail)
        missing = detail.get("missing_clean_lead_fields") or []
        rows.append(
            _manager_chase_row(
                rep=rep,
                account=account,
                trigger="dirty_clean_lead",
                evidence=f"Missing clean-lead fields: {', '.join(missing) if missing else 'needs-check'}.",
                ask="clean the missing HubSpot fields or state what evidence is needed",
                deadline="by tomorrow 12pm",
                fallback_action="send the specific missing field back to manager instead of treating the account as nurture-ready.",
                source=source,
            )
        )

    if owner_row.get("single_touch_account_count", 0):
        rows.append(
            _manager_chase_row(
                rep=rep,
                trigger="double_tap_gap",
                evidence=f"{owner_row.get('single_touch_account_count')} worked account(s) have only one logged touch.",
                ask="list the accounts that will get the second touch and the channel you will use",
                deadline="by EOD today",
                fallback_action="prioritize accounts with live reply, event, demo, or contract-timing signals first.",
                source=source,
            )
        )

    if owner_row.get("connected_call_count", 0) < CONNECTED_CALL_WEEKLY_TARGET:
        rows.append(
            _manager_chase_row(
                rep=rep,
                trigger="connected_call_gap",
                evidence=f"{owner_row.get('connected_call_count', 0)}/{CONNECTED_CALL_WEEKLY_TARGET} connected calls logged.",
                ask="give the call-block plan to close the connected-call gap",
                deadline="before next call block",
                fallback_action="name the non-call channel being used and why it is stronger for this market/account set.",
                source=source,
            )
        )

    if owner_row.get("warm_activity_points", 0) == 0:
        rows.append(
            _manager_chase_row(
                rep=rep,
                trigger="warm_activity_missing",
                evidence="0 completed warm activity meetings found for HHH, LL, coffee, lunch, dinner, cosy, ABM, event, appreciation afternoon, or sports.",
                ask="name one warm activity to book or log and which target account it supports",
                deadline="by Friday correction",
                fallback_action="explain what manager support is needed to create the warm activity.",
                source=source,
            )
        )

    return rows


def _manager_chase_rows_from_context(
    context: dict[str, Any],
    slack_context_summary: str = "",
    slack_source_permalink: str = "",
) -> list[dict[str, Any]]:
    company = context.get("company", {})
    rep = {
        "owner_id": str(company.get("owner_id") or ""),
        "owner_email": _normalize_email(str(company.get("owner_email") or "")),
        "owner_name": str(company.get("owner_name") or ""),
    }
    account = _manager_chase_account(company)
    rows: list[dict[str, Any]] = []
    source = "HubSpot account context and selected Slack context" if slack_context_summary else "HubSpot account context"

    if slack_context_summary:
        rows.append(
            _manager_chase_row(
                rep=rep,
                account=account,
                trigger="selected_slack_blocker",
                evidence=f"Selected Slack context: {_manager_chase_sentence(slack_context_summary)}.",
                ask="turn the blocker into a dated next step and log the outcome in HubSpot",
                deadline="by EOD today",
                fallback_action="call the stakeholder once, propose the closest concrete option, and log yes/no/next date.",
                source=source,
                source_permalink=slack_source_permalink,
            )
        )

    tasks = context.get("sales_followup_tasks", [])
    if tasks:
        next_task = _sort_tasks_by_due_at(tasks)[0]
        rows.append(
            _manager_chase_row(
                rep=rep,
                account=account,
                trigger="open_followup_task",
                evidence=(
                    f"Open task due {next_task.get('due_at') or 'needs-check'}: "
                    f"{next_task.get('subject') or 'follow-up task'}."
                ),
                ask="confirm whether the task is done, blocked, or needs a revised next date",
                deadline="by EOD today",
                fallback_action="close or update the HubSpot task with the real next step.",
                source=source,
            )
        )

    missing_fields = company.get("missing_fields") or []
    if missing_fields:
        rows.append(
            _manager_chase_row(
                rep=rep,
                account=account,
                trigger="dirty_clean_lead",
                evidence=f"Missing fields: {', '.join(missing_fields)}.",
                ask="clean the missing fields or state which item is genuinely unavailable",
                deadline="by tomorrow 12pm",
                fallback_action="ask manager to decide whether this should stay in the locked pool.",
                source=source,
            )
        )

    if not rows:
        rows.append(
            _manager_chase_row(
                rep=rep,
                account=account,
                trigger="next_step_needed",
                evidence="Scoped HubSpot target account selected, but no sharper blocker was found in safe summary fields.",
                ask="give the next action, owner, and date",
                deadline="by EOD today",
                fallback_action="mark the account needs-check with the blocker instead of leaving it open-ended.",
                source=source,
            )
        )
    return rows


def _rank_manager_chase_rows(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    priority = {
        "selected_slack_blocker": 0,
        "open_followup_task": 1,
        "untouched_account": 2,
        "stale_account": 3,
        "dirty_clean_lead": 4,
        "double_tap_gap": 5,
        "connected_call_gap": 6,
        "warm_activity_missing": 7,
        "next_step_needed": 8,
    }
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            priority.get(str(row.get("trigger") or ""), 99),
            str(row.get("rep", {}).get("owner_email") or row.get("rep", {}).get("owner_id") or ""),
            str(row.get("account", {}).get("name") or ""),
        ),
    )
    ranked = []
    for index, row in enumerate(sorted_rows[:limit], start=1):
        ranked_row = dict(row)
        ranked_row["rank"] = index
        ranked.append(ranked_row)
    return ranked


def _task_due_in_window(task: dict[str, Any], due_start: str = "", due_end: str = "") -> bool:
    due = _date_value(task.get("due_at"))
    start = _date_value(due_start)
    end = _date_value(due_end)
    if (start or end) and not due:
        return False
    if start and due and due < start:
        return False
    if end and due and due > end:
        return False
    return True


def _list_sales_followup_tasks_from_task_search(
    scope: dict[str, Any],
    selected: list[str],
    requested_limit: int,
    target_owner_id: str | None,
    target_owner_email: str,
    due_start: str = "",
    due_end: str = "",
) -> dict[str, Any]:
    search_limit = min(TASK_SEARCH_RESULT_LIMIT, max(requested_limit * 5, 20))
    task_data = _task_search(_task_search_filters(target_owner_id, due_start, due_end), search_limit)
    task_ids = [str(task.get("id") or "") for task in task_data.get("results", []) if task.get("id")]
    task_links = _task_company_links_for_tasks(task_ids)
    candidate_company_ids: list[str] = []
    association_truncated = False

    for links in task_links.values():
        association_truncated = association_truncated or bool(links.get("truncated"))
        for company_id in links.get("company_ids", []):
            if company_id not in candidate_company_ids:
                candidate_company_ids.append(company_id)

    companies = {
        str(company.get("id")): company
        for company in _batch_read("companies", candidate_company_ids, COMPANY_PROPERTIES)
        if company.get("id")
    }
    rows: list[dict[str, Any]] = []
    seen_task_ids: set[str] = set()

    for task in task_data.get("results", []):
        task_id = str(task.get("id") or "")
        if not task_id or task_id in seen_task_ids or not _is_incomplete_task(task):
            continue
        task_owner_id = str(task.get("properties", {}).get("hubspot_owner_id") or "")
        links = task_links.get(task_id, {})
        for company_id in links.get("company_ids", []):
            company = companies.get(str(company_id))
            if not company or not _has_company_access(company, scope):
                continue
            props = company.get("properties", {})
            company_owner_id = str(props.get("hubspot_owner_id") or "")
            if props.get("company_country") not in selected:
                continue
            if target_owner_id and company_owner_id != str(target_owner_id):
                continue
            if task_owner_id and company_owner_id != task_owner_id:
                continue

            summary = _summarize_company(company)
            task_summary = _safe_task_summary(
                task,
                {task_id: links.get("company_sources", {}).get(str(company_id), [])},
            )
            rows.append(
                {
                    "company_id": summary.get("company_id"),
                    "company_name": summary.get("name"),
                    "country": summary.get("country"),
                    **task_summary,
                }
            )
            seen_task_ids.add(task_id)
            break

    sorted_tasks = _sort_tasks_by_due_at(rows)
    returned_tasks = sorted_tasks[:requested_limit]
    metadata = _search_metadata(task_data)
    task_truncated = bool(metadata.get("truncated") or association_truncated or len(sorted_tasks) > requested_limit)
    scope_response = _scope_response(scope, selected, target_owner_id, target_owner_email)
    if due_start:
        scope_response["due_start"] = due_start
    if due_end:
        scope_response["due_end"] = due_end
    return {
        "answer": returned_tasks,
        "source": "HubSpot task search plus scoped sales-owned task associations",
        "scope": scope_response,
        **metadata,
        "task_count": len(sorted_tasks),
        "returned_task_count": len(returned_tasks),
        "task_truncated": task_truncated,
        "confidence": "needs-check" if task_truncated else "verified",
        "caveat": (
            "Existing incomplete sales-owned HubSpot tasks only. Safe task summaries omit task body and do not create or mutate tasks."
        ),
    }


def _get_company(company_id: str) -> dict[str, Any]:
    props = ",".join(COMPANY_PROPERTIES)
    return _get(f"/crm/v3/objects/companies/{company_id}", {"properties": props})


def _has_company_access(company: dict[str, Any], scope: dict[str, Any]) -> bool:
    props = company.get("properties", {})
    if str(props.get("hs_is_target_account") or "").lower() != "true":
        return False
    if props.get("company_country") not in scope.get("countries", ()):
        return False
    if scope["kind"] in TEAM_READ_SCOPE_KINDS:
        return True
    return scope["kind"] == "ae" and props.get("hubspot_owner_id") == scope.get("owner_id")


def _company_context(company_id: str, scope: dict[str, Any], task_limit: int = 20) -> dict[str, Any] | None:
    company = _get_company(company_id)
    if not _has_company_access(company, scope):
        return None
    contact_ids = _association_ids("companies", company_id, "contacts", 50)
    deal_ids = _association_ids("companies", company_id, "deals", 20)
    contacts = _batch_read("contacts", contact_ids, CONTACT_PROPERTIES)
    deals = _batch_read("deals", deal_ids, DEAL_PROPERTIES)
    props = company.get("properties", {})
    safe_contacts = [_safe_contact(contact) for contact in contacts]
    task_context = _sales_followup_task_context(company, contact_ids, deal_ids, task_limit)
    company_summary = _summarize_company_with_contacts(company, safe_contacts)
    company_summary.update(task_context["signals"])
    company_summary["calendar_audit_seed"] = _calendar_audit_seed(company_summary, contacts)
    context = {
        "company": company_summary,
        "contacts": safe_contacts,
        "deals": [_safe_deal(deal) for deal in deals],
        "sales_followup_tasks": task_context["tasks"],
        "coverage": _coverage(props, safe_contacts),
    }
    c360_sales_packet = _fetch_c360_sales_packet(company_summary)
    _apply_c360_packet_company_link(company_summary, c360_sales_packet)
    context["c360_sales_packet"] = c360_sales_packet
    context["account_packet"] = _build_account_packet(context, c360_sales_packet)
    return context


def _assert_company_access(company_id: str, scope: dict[str, Any]) -> dict[str, Any]:
    company = _get_company(company_id)
    if not _has_company_access(company, scope):
        raise ScopeError("Company is outside caller scope or is not a HubSpot target account.")
    return company


def _task_marker(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _is_task_approval_marker(value: Any, allowed: set[str]) -> bool:
    return _task_marker(value) in allowed


def _task_local_timezone() -> ZoneInfo | timezone:
    try:
        return ZoneInfo("Asia/Singapore")
    except ZoneInfoNotFoundError:
        return SINGAPORE_TIMEZONE


def _parse_task_due_datetime(value: Any) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ScopeError("Task due_at is required.")
    local_tz = _task_local_timezone()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        try:
            due_date = date.fromisoformat(raw)
        except ValueError as error:
            raise ScopeError("Task due_at must be an ISO date or timestamp.") from error
        parsed = datetime.combine(due_date, datetime_time(TASK_DEFAULT_DUE_HOUR_LOCAL, 0), tzinfo=local_tz)
        return parsed.astimezone(timezone.utc)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise ScopeError("Task due_at must be an ISO date or timestamp.") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=local_tz)
    return parsed.astimezone(timezone.utc)


def _task_due_iso(value: Any) -> str:
    return _parse_task_due_datetime(value).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _assert_not_past_task_due(due_dt: datetime) -> None:
    local_due = due_dt.astimezone(_task_local_timezone()).date()
    today = datetime.now(_task_local_timezone()).date()
    if local_due < today:
        raise ScopeError("Task due_at cannot be in the past.")


def _task_native_reminder_ms(due_dt: datetime) -> str:
    reminder_dt = due_dt - timedelta(days=1)
    if reminder_dt <= datetime.now(timezone.utc):
        return ""
    return str(int(reminder_dt.timestamp() * 1000))


def _normalize_task_subject(value: Any) -> str:
    text = html.unescape(str(value or "")).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _safe_slack_permalink(value: Any) -> str:
    permalink = str(value or "").strip()
    if not permalink:
        return ""
    parsed = urllib.parse.urlparse(permalink)
    if parsed.scheme != "https" or parsed.netloc != "staffany.slack.com" or not parsed.path.startswith("/archives/"):
        raise ScopeError("Slack permalink must be a staffany.slack.com /archives/ URL.")
    return permalink


def _safe_task_body(source_summary: Any = "", slack_permalink: Any = "") -> str:
    lines: list[str] = []
    summary = _short_text(str(source_summary or ""), 1000)
    permalink = _safe_slack_permalink(slack_permalink)
    if summary:
        lines.append(f"NurtureAny source summary: {summary}")
    if permalink:
        lines.append(f"Slack source: {permalink}")
    lines.append("Created by NurtureAny after explicit Slack task approval.")
    return "\n".join(lines)[:4000]


def _hubspot_task_association(object_type: str, object_id: Any) -> dict[str, Any]:
    association_type_id = TASK_ASSOCIATION_TYPE_IDS[object_type]
    return {
        "to": {"id": str(object_id)},
        "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": association_type_id}],
    }


def _assert_object_associated_to_company(object_type: str, object_id: Any, company_id: str) -> None:
    normalized_id = str(object_id or "").strip()
    if not normalized_id:
        return
    from_type = "contacts" if object_type == "contact" else "deals"
    company_ids = _association_ids(from_type, normalized_id, "companies", 20)
    if str(company_id) not in [str(candidate) for candidate in company_ids]:
        raise ScopeError(f"Selected {object_type}_id is not associated to the scoped HubSpot company.")


def _task_account_ref(company: dict[str, Any]) -> dict[str, Any]:
    summary = _summarize_company(company)
    return {
        "company_id": summary.get("company_id"),
        "company_name": summary.get("name"),
        "country": summary.get("country"),
        "owner_id": summary.get("owner_id"),
        "owner_email": summary.get("owner_email"),
    }


def _resolve_scoped_task_company(company_id: Any, company_name: Any, scope: dict[str, Any]) -> dict[str, Any]:
    normalized_company_id = _company_id_from_ref(company_id)
    if normalized_company_id:
        return _assert_company_access(normalized_company_id, scope)
    name = _company_name_ref(company_name)
    if not name:
        raise ScopeError("Provide a scoped HubSpot company_id or exact company_name.")
    resolved = _resolve_scoped_company_name(name, scope, limit=5)
    if resolved.get("status") == "resolved" and resolved.get("company_id"):
        return _assert_company_access(str(resolved["company_id"]), scope)
    if resolved.get("status") == "ambiguous":
        raise ScopeError("Company name is ambiguous; provide the exact scoped HubSpot company_id.")
    raise ScopeError("Scoped HubSpot target account was not found.")


def _sales_task_owner_for_company(company: dict[str, Any], scope: dict[str, Any], owner_email: Any = "") -> tuple[str, str]:
    company_owner_id = str(company.get("properties", {}).get("hubspot_owner_id") or "")
    if not company_owner_id:
        raise ScopeError("Scoped HubSpot company has no owner; cannot create a sales-owned task.")
    company_owner_email = _owner_email_by_id(company_owner_id)
    target_email = _normalize_email(str(owner_email or ""))
    if target_email:
        target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, target_email)
        if str(target_owner_id or "") != company_owner_id:
            raise ScopeError(
                "Task owner must match the scoped HubSpot company owner. Fix HubSpot ownership before assigning a different AE."
            )
        return company_owner_id, target_owner_email or company_owner_email
    if scope.get("kind") == "ae" and str(scope.get("owner_id") or "") != company_owner_id:
        raise ScopeError("Caller is not authorized to create tasks for another owner's account.")
    return company_owner_id, company_owner_email


def _task_duplicate_window(due_dt: datetime) -> tuple[str, str]:
    local_due = due_dt.astimezone(_task_local_timezone()).date()
    start = local_due - timedelta(days=TASK_DUPLICATE_WINDOW_DAYS)
    end = local_due + timedelta(days=TASK_DUPLICATE_WINDOW_DAYS)
    return start.isoformat(), end.isoformat()


def _task_sources_include_selected(
    sources: list[dict[str, str]],
    contact_id: str = "",
    deal_id: str = "",
) -> bool:
    if contact_id:
        return any(source.get("object_type") == "contact" and str(source.get("object_id")) == str(contact_id) for source in sources)
    if deal_id:
        return any(source.get("object_type") == "deal" and str(source.get("object_id")) == str(deal_id) for source in sources)
    return True


def _find_duplicate_sales_tasks(
    company: dict[str, Any],
    owner_id: str,
    subject: str,
    due_dt: datetime,
    contact_id: str = "",
    deal_id: str = "",
) -> list[dict[str, Any]]:
    company_id = str(company.get("id") or "")
    if not company_id:
        return []
    due_start, due_end = _task_duplicate_window(due_dt)
    task_data = _task_search(_task_search_filters(owner_id, due_start, due_end), limit=100)
    task_ids = [str(task.get("id") or "") for task in task_data.get("results", []) if task.get("id")]
    task_links = _task_company_links_for_tasks(task_ids)
    subject_key = _normalize_task_subject(subject)
    duplicates: list[dict[str, Any]] = []
    for task in task_data.get("results", []):
        task_id = str(task.get("id") or "")
        if not task_id or not _is_incomplete_task(task):
            continue
        props = task.get("properties", {})
        if str(props.get("hubspot_owner_id") or "") != str(owner_id):
            continue
        if _normalize_task_subject(props.get("hs_task_subject")) != subject_key:
            continue
        links = task_links.get(task_id, {})
        if company_id not in [str(candidate) for candidate in links.get("company_ids", [])]:
            continue
        sources = links.get("company_sources", {}).get(company_id, [])
        if not _task_sources_include_selected(sources, contact_id, deal_id):
            continue
        duplicates.append(_safe_task_summary(task, {task_id: sources}))
    return _sort_tasks_by_due_at(duplicates)


def _build_sales_task_preview(
    slack_user_email: str,
    company_id: Any = "",
    company_name: Any = "",
    subject: Any = "",
    due_at: Any = "",
    contact_id: Any = "",
    deal_id: Any = "",
    owner_email: Any = "",
    source_summary: Any = "",
    slack_permalink: Any = "",
    priority: str = "HIGH",
    task_type: str = "TODO",
) -> dict[str, Any]:
    scope = _caller_scope(slack_user_email)
    if scope["kind"] == "blocked":
        raise ScopeError("Caller identity is not mapped to an allowed scope.")
    if scope["kind"] == "partnerships_viewer":
        raise ScopeError("Partnerships viewer scope is read-only and cannot preview or create HubSpot Tasks.")
    company = _resolve_scoped_task_company(company_id, company_name, scope)
    normalized_company_id = str(company.get("id") or "")
    normalized_contact_id = str(contact_id or "").strip()
    normalized_deal_id = str(deal_id or "").strip()
    _assert_object_associated_to_company("contact", normalized_contact_id, normalized_company_id)
    _assert_object_associated_to_company("deal", normalized_deal_id, normalized_company_id)

    due_dt = _parse_task_due_datetime(due_at)
    _assert_not_past_task_due(due_dt)
    due_iso = due_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    owner_id, resolved_owner_email = _sales_task_owner_for_company(company, scope, owner_email)
    safe_subject = _short_text(str(subject or "").strip(), 180)
    if not safe_subject:
        raise ScopeError("Task subject is required.")
    safe_priority = str(priority or "HIGH").strip().upper()
    if safe_priority not in {"LOW", "MEDIUM", "HIGH"}:
        safe_priority = "HIGH"
    safe_type = str(task_type or "TODO").strip().upper()
    if safe_type not in {"TODO", "CALL", "EMAIL"}:
        safe_type = "TODO"

    body = _safe_task_body(source_summary, slack_permalink)
    properties = {
        "hs_timestamp": due_iso,
        "hs_task_body": body,
        "hubspot_owner_id": owner_id,
        "hs_task_subject": safe_subject,
        "hs_task_status": "NOT_STARTED",
        "hs_task_priority": safe_priority,
        "hs_task_type": safe_type,
    }
    reminder_ms = _task_native_reminder_ms(due_dt)
    if reminder_ms:
        properties["hs_task_reminders"] = reminder_ms

    associations = [_hubspot_task_association("company", normalized_company_id)]
    if normalized_contact_id:
        associations.append(_hubspot_task_association("contact", normalized_contact_id))
    if normalized_deal_id:
        associations.append(_hubspot_task_association("deal", normalized_deal_id))

    duplicates = _find_duplicate_sales_tasks(
        company,
        owner_id,
        safe_subject,
        due_dt,
        contact_id=normalized_contact_id,
        deal_id=normalized_deal_id,
    )
    preview_properties = {key: value for key, value in properties.items() if key != "hs_task_body"}
    preview_properties["hs_task_body_summary"] = _short_text(body, 260)
    return {
        "scope": scope,
        "company": company,
        "owner_id": owner_id,
        "owner_email": resolved_owner_email,
        "properties": properties,
        "preview_properties": preview_properties,
        "associations": associations,
        "duplicate_active_tasks": duplicates,
        "contact_id": normalized_contact_id,
        "deal_id": normalized_deal_id,
    }


def _task_access_context(task_id: Any, scope: dict[str, Any], company_id: Any = "") -> dict[str, Any]:
    normalized_task_id = str(task_id or "").strip()
    if not normalized_task_id:
        raise ScopeError("Task ID is required.")
    task = _get(
        f"/crm/v3/objects/tasks/{urllib.parse.quote(normalized_task_id, safe='')}",
        {"properties": ",".join(TASK_PROPERTIES)},
    )
    links = _task_company_links_for_tasks([normalized_task_id]).get(
        normalized_task_id, {"company_ids": [], "company_sources": {}, "truncated": False}
    )
    requested_company_id = _company_id_from_ref(company_id)
    if requested_company_id:
        company = _assert_company_access(requested_company_id, scope)
        if requested_company_id not in [str(candidate) for candidate in links.get("company_ids", [])]:
            raise ScopeError("Task is not associated to the requested scoped HubSpot company.")
        return {"task": task, "company": company, "links": links}

    companies = _batch_read("companies", [str(candidate) for candidate in links.get("company_ids", [])], COMPANY_PROPERTIES)
    accessible = [company for company in companies if _has_company_access(company, scope)]
    if not accessible:
        raise ScopeError("Task is outside caller scope or is not associated to a scoped HubSpot target account.")
    return {"task": task, "company": accessible[0], "links": links}


def _task_update_preview_properties(action: Any, due_at: Any = "") -> tuple[str, dict[str, str], list[str]]:
    normalized_action = _task_marker(action or "reschedule")
    if normalized_action in {"complete", "mark done", "done", "completed"}:
        return "complete", {"hs_task_status": "COMPLETED"}, sorted(TASK_COMPLETE_APPROVAL_MARKERS)
    if normalized_action in {"reschedule", "update", "update task", "reminder", "due", "due date", "due-date"}:
        due_dt = _parse_task_due_datetime(due_at)
        _assert_not_past_task_due(due_dt)
        properties = {"hs_timestamp": due_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")}
        reminder_ms = _task_native_reminder_ms(due_dt)
        if reminder_ms:
            properties["hs_task_reminders"] = reminder_ms
        return "reschedule", properties, sorted(TASK_RESCHEDULE_APPROVAL_MARKERS)
    raise ScopeError("Task update action must be reschedule or complete.")


def _parse_task_reminder_as_of(value: Any) -> datetime:
    raw = str(value or "").strip()
    local_tz = _task_local_timezone()
    if not raw:
        return datetime.now(local_tz)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return datetime.combine(date.fromisoformat(raw), datetime.min.time(), tzinfo=local_tz)
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=local_tz)
    return parsed.astimezone(local_tz)


def _task_due_bucket(due_at: Any, today: date, include_tomorrow: bool) -> str:
    due_date = _date_value(str(due_at or ""))
    if not due_date:
        return ""
    if due_date < today:
        return "overdue"
    if due_date == today:
        return "due_today"
    if include_tomorrow and due_date == today + timedelta(days=1):
        return "due_tomorrow"
    return ""


def _summarize_company_with_contacts(
    company: dict[str, Any],
    contacts: list[dict[str, Any]],
    contact_count: int | None = None,
) -> dict[str, Any]:
    summary = _summarize_company(company)
    props = company.get("properties", {})
    associated_contact_count = len(contacts) if contact_count is None else contact_count
    decision_coverage = _decision_maker_coverage(props, contacts, associated_contact_count)
    contact_detail_missing = _contact_detail_missing_fields(contacts)
    summary["contact_count"] = associated_contact_count
    summary["associated_contact_count"] = associated_contact_count
    summary["verified_decision_maker_count"] = decision_coverage["verified_decision_maker_count"]
    summary["decision_maker_count"] = decision_coverage["verified_decision_maker_count"]
    summary["role_inferred_decision_maker_count"] = decision_coverage["role_inferred_decision_maker_candidate_count"]
    summary["role_inferred_decision_maker_candidate_count"] = decision_coverage["role_inferred_decision_maker_candidate_count"]
    summary["decision_maker_coverage"] = decision_coverage
    summary["enrichment_status"] = _enrichment_status(props, associated_contact_count, contacts)
    summary["missing_fields"] = _missing_company_fields(props, associated_contact_count, contacts) + contact_detail_missing
    summary["calendar_scan_instruction"] = _calendar_scan_instruction(summary)
    return summary


def _phone_verification_status(props: dict[str, Any], stale_after_days: int = PHONE_VERIFICATION_DEFAULT_STALE_AFTER_DAYS) -> dict[str, Any]:
    raw_status = str(props.get("nurtureany_phone_verification_status") or "").strip().lower()
    raw_source = str(props.get("nurtureany_phone_verification_source") or "").strip().lower()
    verified_at = str(props.get("nurtureany_phone_verified_at") or "").strip()
    has_phone_candidate = bool(
        str(props.get("phone") or "").strip()
        or str(props.get("mobilephone") or "").strip()
        or raw_source in PHONE_VERIFICATION_SOURCES
        or raw_status in PHONE_VERIFICATION_STATUSES - {"not_checked"}
    )
    status = raw_status if raw_status in PHONE_VERIFICATION_STATUSES else ("candidate" if has_phone_candidate else "not_checked")
    source = raw_source if raw_source in PHONE_VERIFICATION_SOURCES else ""
    verified_date = _date_value(verified_at)
    stale_after = max(1, _bounded_int(stale_after_days, default=PHONE_VERIFICATION_DEFAULT_STALE_AFTER_DAYS, maximum=3650))
    stale_cutoff = datetime.now(timezone.utc).date() - timedelta(days=stale_after)
    is_stale = bool(status in PHONE_VERIFICATION_VERIFIED_STATUSES and verified_date and verified_date < stale_cutoff)
    effective_status = "stale" if is_stale else status
    is_verified = effective_status in PHONE_VERIFICATION_VERIFIED_STATUSES
    notes = _safe_activity_label(props.get("nurtureany_phone_verification_notes") or "", 180)
    verified_by = _safe_activity_label(props.get("nurtureany_phone_verified_by") or "", 80)
    return {
        "status": effective_status,
        "raw_status": raw_status,
        "source": source,
        "verified_at": verified_at,
        "verified_by": verified_by,
        "notes": notes,
        "has_phone_candidate": has_phone_candidate,
        "is_verified": is_verified,
        "is_stale": is_stale,
        "stale_after_days": stale_after,
        "confidence": "verified" if is_verified else "needs-check",
    }


def _safe_contact(
    contact: dict[str, Any],
    phone_stale_after_days: int = PHONE_VERIFICATION_DEFAULT_STALE_AFTER_DAYS,
) -> dict[str, Any]:
    props = contact.get("properties", {})
    first = props.get("firstname") or ""
    last = props.get("lastname") or ""
    role = props.get("job_role") or props.get("jobtitle") or ""
    buying_role = props.get("hs_buying_role") or ""
    has_verified_decision_maker_role = _has_decision_maker_buying_role(buying_role)
    has_role_inferred_decision_maker = _role_is_decision_maker(role)
    contact_confidence = props.get("nurtureany_contact_confidence") or ""
    channel_fit = props.get("nurtureany_channel_fit") or ""
    block_text = _normalized_words(
        f"{first} {last} {props.get('email') or ''} {role} {buying_role} {channel_fit} {contact_confidence}"
    )
    email_optout = str(props.get("hs_email_optout") or "").strip().lower() in {"true", "1", "yes"}
    do_not_contact = email_optout or any(marker in block_text for marker in DAILY_NURTURE_DO_NOT_CONTACT_MARKERS)
    phone_status = _phone_verification_status(props, phone_stale_after_days)
    return {
        "contact_id": contact.get("id"),
        "display_name": " ".join(part for part in [first, last[:1] + "." if last else ""] if part).strip(),
        "persona": role,
        "buying_role": buying_role,
        "is_verified_decision_maker": has_verified_decision_maker_role,
        "is_role_inferred_decision_maker": has_role_inferred_decision_maker,
        "is_decision_maker": has_verified_decision_maker_role or has_role_inferred_decision_maker,
        "decision_maker_confidence": "verified" if has_verified_decision_maker_role else "needs-check" if has_role_inferred_decision_maker else "",
        "last_verified_at": props.get("nurtureany_last_verified_at") or props.get("lastmodifieddate") or "",
        "channel_fit": channel_fit,
        "contact_confidence": contact_confidence,
        "do_not_contact": do_not_contact,
        "do_not_contact_basis": "HubSpot hs_email_optout, contact name, or NurtureAny contact field marker"
        if do_not_contact
        else "",
        "phone_available": phone_status["has_phone_candidate"],
        "phone_verification_status": phone_status["status"],
        "phone_verification_source": phone_status["source"],
        "phone_verified_at": phone_status["verified_at"],
        "phone_verified_by": phone_status["verified_by"],
        "phone_verification_notes": phone_status["notes"],
        "is_phone_verified": phone_status["is_verified"],
        "phone_verification_confidence": phone_status["confidence"],
    }


def _role_is_decision_maker(role: str) -> bool:
    text = role.lower()
    if "executive" in text:
        return False
    markers = ("founder", "owner", "director", "ceo", "chief", "boss")
    return any(marker in text for marker in markers)


def _usable_contact_count(contacts: list[dict[str, Any]]) -> int:
    usable = 0
    for contact in contacts:
        if contact.get("do_not_contact"):
            continue
        if contact.get("display_name") and (
            contact.get("is_phone_verified")
            or contact.get("phone_available")
            or contact.get("channel_fit")
            or contact.get("buying_role")
            or contact.get("persona")
        ):
            usable += 1
    return usable


def _safe_deal(deal: dict[str, Any]) -> dict[str, Any]:
    props = deal.get("properties", {})
    return {
        "deal_id": deal.get("id"),
        "dealname": props.get("dealname") or "",
        "stage": props.get("dealstage") or "",
        "amount": props.get("amount") or "",
        "close_date": props.get("closedate") or "",
        "contract_end_date": props.get("contract_end_date") or "",
        "owner_id": props.get("hubspot_owner_id") or "",
    }


def _deal_is_active_for_hygiene(deal: dict[str, Any]) -> bool:
    props = deal.get("properties", {})
    stage = _normalized_words(props.get("dealstage"))
    if not stage:
        return True
    closed_markers = ("closed lost", "closedlost", "lost", "closed won", "closedwon", "won")
    return not any(marker in stage for marker in closed_markers)


def _safe_active_deal_hygiene_row(
    deal: dict[str, Any],
    company: dict[str, Any],
    meeting_truncated: bool,
) -> dict[str, Any]:
    company_summary = _summarize_company(company)
    safe_deal = _safe_deal(deal)
    return {
        "company_id": company_summary.get("company_id"),
        "company_name": company_summary.get("name"),
        "country": company_summary.get("country"),
        "company_owner_id": company_summary.get("owner_id"),
        **safe_deal,
        "next_meeting_status": "not_found" if not meeting_truncated else "needs-check",
        "confidence": "needs-check" if meeting_truncated else "verified",
    }


def _future_meeting_index_for_deals(
    deal_ids: list[str],
    deadline: float | None = None,
) -> dict[str, Any]:
    if not deal_ids:
        return {"future_meeting_at_by_deal": {}, "truncated": False, "partial_due_to_soft_timeout": False}

    deal_meeting_ids = _batch_association_ids_until("deals", "meetings", deal_ids, deadline)
    partial_due_to_deadline = _deadline_exceeded(deadline)
    meeting_to_deals: dict[str, list[str]] = {}
    for deal_id, meeting_ids in deal_meeting_ids.items():
        for meeting_id in meeting_ids:
            meeting_to_deals.setdefault(str(meeting_id), []).append(str(deal_id))

    unique_meeting_ids = sorted(meeting_to_deals.keys())
    read_limit = FOLLOWUP_RETURN_LIMIT * max(1, min(len(deal_ids), 10))
    read_ids = unique_meeting_ids[:read_limit]
    truncated = len(unique_meeting_ids) > len(read_ids)
    raw_meetings = [] if partial_due_to_deadline else _batch_read_until("meetings", read_ids, MEETING_PROPERTIES, deadline)
    partial_due_to_deadline = bool(partial_due_to_deadline or _deadline_exceeded(deadline))

    now = datetime.now(timezone.utc)
    future_meeting_at_by_deal: dict[str, str] = {}
    for meeting in raw_meetings:
        meeting_id = str(meeting.get("id") or "")
        timestamp_text = _activity_timestamp(meeting)
        timestamp = _datetime_value(timestamp_text)
        if not timestamp or timestamp < now:
            continue
        for deal_id in meeting_to_deals.get(meeting_id, []):
            current = future_meeting_at_by_deal.get(deal_id)
            if not current or timestamp_text < current:
                future_meeting_at_by_deal[deal_id] = timestamp_text

    return {
        "future_meeting_at_by_deal": future_meeting_at_by_deal,
        "truncated": bool(truncated or partial_due_to_deadline),
        **_soft_timeout_metadata(partial_due_to_deadline),
    }


def _build_account_packet(context: dict[str, Any], c360_packet_result: dict[str, Any] | None = None) -> dict[str, Any]:
    company = context.get("company", {})
    c360_packet_result = c360_packet_result or {}
    c360_packet = c360_packet_result.get("packet") if c360_packet_result.get("status") == "ok" else None
    if isinstance(c360_packet, dict):
        segment = str(c360_packet.get("segment") or "")
        if segment == "customer_on_staffany_payroll":
            return _build_payroll_customer_packet(company, c360_packet)
        if segment == "customer_not_on_staffany_payroll":
            return _build_non_payroll_customer_packet(company, c360_packet)
        return _build_prospect_account_packet(company, c360_packet)

    if company.get("account_status") == "customer":
        caveat = str(
            c360_packet_result.get("caveat")
            or "C360 sales packet was unavailable, so StaffAny Payroll classification was not inferred."
        )
        return {
            "format": "slim_account_packet_v1",
            "segment": "customer_c360_unavailable",
            "company": {
                "name": company.get("name") or "",
                "c360_url": company.get("c360_url") or "",
                "linked_name": _slack_link(company.get("name") or "", company.get("c360_url") or ""),
            },
            "lines": [
                "Segment: current customer, but StaffAny Payroll status needs C360 check",
                f"Owner: {_first_non_empty(company.get('owner_name'), company.get('owner_email'), 'needs-check')}",
                "Missing / needs-check: C360 sales packet unavailable; do not use stale HubSpot current-tool or contract-end fields as Payroll truth.",
            ],
            "slack_markdown": "\n".join(
                [
                    f"*{_slack_link(company.get('name') or 'Account', company.get('c360_url') or '')}*",
                    "• Segment: current customer, but StaffAny Payroll status needs C360 check",
                    f"• Owner: {_first_non_empty(company.get('owner_name'), company.get('owner_email'), 'needs-check')}",
                    "• Missing / needs-check: C360 sales packet unavailable; do not use stale HubSpot current-tool or contract-end fields as Payroll truth.",
                ]
            ),
            "minimal_gaps": ["C360 sales packet unavailable."],
            "suppressed_by_default": _default_account_packet_suppression(),
            "source": "Scoped HubSpot account resolution; Customer 360 sales packet unavailable",
            "confidence": "needs-check",
            "caveat": caveat,
        }

    return _build_prospect_account_packet(company, None)


def _build_payroll_customer_packet(company: dict[str, Any], c360_packet: dict[str, Any]) -> dict[str, Any]:
    account = _dict_value(c360_packet.get("account"))
    staffany = _dict_value(c360_packet.get("staffany"))
    active_usage = _dict_value(staffany.get("activeUsage"))
    owned_products = _string_values(staffany.get("ownedProducts"))
    missing_products = [product for product in _string_values(staffany.get("missingProducts")) if product.lower() != "payroll"]
    cross_sell = [
        signal
        for signal in _string_values(c360_packet.get("crossSellSignals"))
        if "payroll conversion" not in signal.lower()
    ]
    verified_pics = _format_verified_pics(c360_packet.get("verifiedPics"))
    gaps = _one_gap_line(c360_packet.get("minimalGaps"), fallback="No major packet gap from C360.")
    company_name = str(account.get("companyName") or company.get("name") or "")
    c360_url = str(c360_packet.get("c360Url") or company.get("c360_url") or "")
    lines = [
        "Segment: current customer on StaffAny Payroll",
        f"Owner / PSM: {_owner_psm_line(company, account)}",
        f"Active StaffAny usage: {_first_non_empty(active_usage.get('summary'), 'needs-check')}",
        f"Owned products: {_join_or(owned_products, 'needs-check')}",
        f"Missing modules to consider: {_join_or(missing_products, 'none obvious in C360')}",
        f"Likely cross-sell angle: {_join_or(cross_sell, 'missing StaffAny modules only')}",
        f"Verified PICs: {_join_or(verified_pics, 'none verified in C360')}",
        f"Missing / needs-check: {gaps}",
    ]
    return _account_packet_response(
        segment="customer_on_staffany_payroll",
        company_name=company_name,
        c360_url=c360_url,
        lines=lines,
        minimal_gaps=[gaps],
        source="Customer 360 sales packet + scoped HubSpot account resolution",
        confidence="needs-check" if "none verified" in lines[-2].lower() else "verified",
        caveat="Uses C360 as Payroll/customer-product truth. HubSpot current_tools, contract_end_date, last activity, deals, open tasks, and full IC-BANT are suppressed by default.",
    )


def _build_non_payroll_customer_packet(company: dict[str, Any], c360_packet: dict[str, Any]) -> dict[str, Any]:
    account = _dict_value(c360_packet.get("account"))
    staffany = _dict_value(c360_packet.get("staffany"))
    owned_products = _string_values(staffany.get("ownedProducts"))
    external_tool = _external_tool_line(company, c360_packet, allow_hubspot=True)
    verified_pics = _format_verified_pics(c360_packet.get("verifiedPics"))
    gaps = _one_gap_line(c360_packet.get("minimalGaps"), fallback="Confirm external HRIS/payroll and Payroll buying process.")
    company_name = str(account.get("companyName") or company.get("name") or "")
    c360_url = str(c360_packet.get("c360Url") or company.get("c360_url") or "")
    lines = [
        "Segment: current customer not on StaffAny Payroll",
        f"Owner / PSM: {_owner_psm_line(company, account)}",
        f"Owned StaffAny products: {_join_or(owned_products, 'needs-check')}",
        f"Current external HRIS/payroll: {external_tool}",
        "Payroll conversion hook: C360 shows no StaffAny Payroll evidence; qualify payroll pain, incumbent lock-in, payroll volume, and migration window.",
        f"Verified PICs: {_join_or(verified_pics, 'none verified in C360')}",
        f"Missing / needs-check: {gaps}",
    ]
    return _account_packet_response(
        segment="customer_not_on_staffany_payroll",
        company_name=company_name,
        c360_url=c360_url,
        lines=lines,
        minimal_gaps=[gaps],
        source="Customer 360 sales packet + scoped HubSpot account resolution",
        confidence="needs-check" if "none verified" in lines[-2].lower() else "verified",
        caveat="Uses C360 as customer-product truth. External HRIS/payroll is shown only when sourced; deals, open tasks, last activity, and full IC-BANT are suppressed by default.",
    )


def _build_prospect_account_packet(company: dict[str, Any], c360_packet: dict[str, Any] | None) -> dict[str, Any]:
    packet = c360_packet if isinstance(c360_packet, dict) else {}
    company_name = str(_dict_value(packet.get("account")).get("companyName") or company.get("name") or "")
    c360_url = str(packet.get("c360Url") or company.get("c360_url") or "")
    icp = _join_or(
        [
            value
            for value in [
                f"{company.get('industry')} industry" if company.get("industry") else "",
                f"{company.get('headcount')} headcount" if company.get("headcount") else "",
                company.get("country") or "",
            ]
            if value
        ],
        "needs qualification",
    )
    external_tool = _external_tool_line(company, packet, allow_hubspot=True)
    timing = company.get("contract_end_date") or company.get("current_tool_renewal_date") or ""
    missing = _prospect_gap_line(company)
    lines = [
        "Segment: prospect",
        f"ICP fit: {icp}",
        f"Current HRIS/payroll: {external_tool}",
        f"Timing: {timing or 'needs-check'}",
        "Verified contacts: none shown unless verified by C360 PIC evidence",
        f"Missing / needs-check: {missing}",
        "Next discovery ask: confirm current HRIS/payroll, payroll pain, decision owner, and migration timing.",
    ]
    return _account_packet_response(
        segment="prospect",
        company_name=company_name,
        c360_url=c360_url,
        lines=lines,
        minimal_gaps=[missing],
        source="Scoped HubSpot account resolution; C360 used only if available",
        confidence="needs-check",
        caveat="Prospect packet is a qualification brief. HubSpot contacts are not treated as verified PICs unless C360 verification exists.",
    )


def _account_packet_response(
    *,
    segment: str,
    company_name: str,
    c360_url: str,
    lines: list[str],
    minimal_gaps: list[str],
    source: str,
    confidence: str,
    caveat: str,
) -> dict[str, Any]:
    linked_name = _slack_link(company_name or "Account", c360_url)
    return {
        "format": "slim_account_packet_v1",
        "segment": segment,
        "company": {
            "name": company_name,
            "c360_url": c360_url,
            "linked_name": linked_name,
        },
        "lines": lines,
        "slack_markdown": "\n".join([f"*{linked_name}*", *[f"• {line}" for line in lines]]),
        "minimal_gaps": minimal_gaps[:1],
        "suppressed_by_default": _default_account_packet_suppression(),
        "source": source,
        "confidence": confidence,
        "caveat": caveat,
    }


def _default_account_packet_suppression() -> list[str]:
    return [
        "last_activity",
        "deals",
        "open_followup_tasks",
        "full_ic_bant_block",
        "hubspot_only_contacts",
        "role_inferred_decision_maker_candidates",
        "other_contacts",
        "hubspot_current_tools_contract_line_for_staffany_payroll_customers",
    ]


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_values(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def _join_or(values: list[str], fallback: str) -> str:
    clean = _unique_text(values)
    return ", ".join(clean) if clean else fallback


def _first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _slack_link(label: str, url: str) -> str:
    text = str(label or "").strip() or "Account"
    href = str(url or "").strip()
    return f"<{href}|{text}>" if href else text


def _slack_thread_source(source_slack_thread_url: str = "", source_url: str = "") -> dict[str, Any]:
    raw_url = str(source_slack_thread_url or source_url or "").strip()
    if not raw_url:
        return {}
    parsed = urllib.parse.urlparse(raw_url)
    if parsed.scheme not in {"http", "https"}:
        return {}
    hostname = (parsed.hostname or "").lower()
    if not hostname.endswith("slack.com") or "/archives/" not in parsed.path:
        return {}
    return {
        "source_type": "slack_thread",
        "url": raw_url,
        "label": "Source thread",
        "provenance_policy": "Link only; raw Slack transcript was not copied into HubSpot.",
    }


def _owner_psm_line(company: dict[str, Any], account: dict[str, Any]) -> str:
    owner = _first_non_empty(account.get("accountOwner"), company.get("owner_name"), company.get("owner_email"), "needs-check")
    psm = _first_non_empty(account.get("psmOwner"), "needs-check")
    return f"{owner} / {psm}"


def _format_verified_pics(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    pics = []
    for pic in value:
        if not isinstance(pic, dict):
            continue
        name = str(pic.get("name") or "").strip()
        title = str(pic.get("title") or "").strip()
        basis = _string_values(pic.get("verificationBasis"))
        if not name:
            continue
        role = f" - {title}" if title else ""
        proof = f" ({'; '.join(basis)})" if basis else ""
        pics.append(f"{name}{role}{proof}")
    return pics


def _one_gap_line(value: Any, fallback: str) -> str:
    gaps = _string_values(value)
    return "; ".join(gaps[:2]) if gaps else fallback


def _external_tool_line(company: dict[str, Any], c360_packet: dict[str, Any], allow_hubspot: bool) -> str:
    external = c360_packet.get("externalHrisOrPayroll") if isinstance(c360_packet, dict) else None
    if isinstance(external, dict) and external.get("value"):
        source = str(external.get("source") or "C360").strip()
        return f"{external.get('value')} (Source: {source})"
    if allow_hubspot and company.get("current_tools"):
        return f"{company.get('current_tools')} (Source: HubSpot current_tools)"
    return "needs-check"


def _prospect_gap_line(company: dict[str, Any]) -> str:
    missing = _string_values(company.get("missing_fields"))
    relevant = []
    for field in ("current tools", "contract end date", "decision maker", "associated contact"):
        if field in missing:
            relevant.append(field)
    return _join_or(relevant[:3], "confirm HRIS/payroll, timeline, and buyer")


def _coverage(props: dict[str, Any], contacts: list[dict[str, Any]]) -> dict[str, Any]:
    decision_coverage = _decision_maker_coverage(props, contacts, len(contacts))
    verified_decision_makers = [contact for contact in contacts if contact.get("is_verified_decision_maker")]
    role_inferred_decision_makers = [contact for contact in contacts if contact.get("is_role_inferred_decision_maker")]
    channel_known = [contact for contact in contacts if contact.get("channel_fit")]
    phone_candidates = [contact for contact in contacts if contact.get("phone_available")]
    verified_phone_contacts = [contact for contact in contacts if contact.get("is_phone_verified")]
    stale_phone_contacts = [contact for contact in contacts if contact.get("phone_verification_status") == "stale"]
    return {
        "contact_count": len(contacts),
        "associated_contact_count": len(contacts),
        "decision_maker_count": decision_coverage["verified_decision_maker_count"],
        "verified_decision_maker_count": decision_coverage["verified_decision_maker_count"],
        "decision_maker_count_from_hubspot_property": decision_coverage["decision_maker_count_from_hubspot_property"],
        "decision_maker_count_from_contact_roles": len(verified_decision_makers),
        "decision_maker_count_from_contact_buying_role": len(verified_decision_makers),
        "buying_role_contact_count": decision_coverage["buying_role_contact_count"],
        "role_inferred_decision_maker_count": len(role_inferred_decision_makers),
        "role_inferred_decision_maker_candidate_count": decision_coverage["role_inferred_decision_maker_candidate_count"],
        "channel_fit_known_count": len(channel_known),
        "phone_candidate_count": len(phone_candidates),
        "verified_phone_count": len(verified_phone_contacts),
        "stale_phone_count": len(stale_phone_contacts),
        "usable_contact_count": _usable_contact_count(contacts),
        "decision_maker_coverage": decision_coverage,
        "sources": _decision_maker_count_source(props),
        "summary": (
            "nurture-ready"
            if contacts and decision_coverage["verified_decision_maker_count"] and channel_known and verified_phone_contacts
            else "minimum coverage" if contacts and decision_coverage["verified_decision_maker_count"] else "needs enrichment"
        ),
    }


def _score_company(summary: dict[str, Any]) -> dict[str, Any]:
    score = 0
    reasons: list[str] = []
    missing = summary.get("missing_fields", [])
    renewal = _date_value(summary.get("contract_or_renewal_date"))
    today = datetime.now(timezone.utc).date()

    if renewal:
        days = (renewal - today).days
        if 0 <= days <= 90:
            score += 35
            reasons.append(f"contract end in {days} days")
        elif 91 <= days <= 180:
            score += 20
            reasons.append(f"contract end in {days} days")
    else:
        score += 10
        reasons.append("missing contract end date")

    decision_count = summary.get("decision_maker_count", 0) or summary.get("buying_role_contact_count", 0)
    if decision_count:
        score += 20
        reasons.append("direct decision-maker coverage exists")
    else:
        score += 15
        reasons.append("missing decision-maker coverage")

    if summary.get("prospecting_account") == "true":
        score += 10
        reasons.append("marked as prospecting account")

    if summary.get("last_activity_at"):
        activity_date = _date_value(summary.get("last_activity_at"))
        if activity_date:
            age = (today - activity_date).days
            if age >= 21:
                score += 15
                reasons.append(f"no recent sales note for {age} days")
    else:
        score += 8
        reasons.append("missing recent activity date")

    overdue_tasks = _int_value(summary.get("overdue_sales_followup_task_count"))
    open_tasks = _int_value(summary.get("sales_followup_task_count"))
    next_task_due = _date_value(summary.get("next_sales_followup_due_at"))
    if overdue_tasks:
        score += 20
        reasons.append(f"{overdue_tasks} overdue sales follow-up task(s)")
    elif next_task_due:
        days_until_due = (next_task_due - today).days
        if 0 <= days_until_due <= 7:
            score += 12
            reasons.append(f"sales follow-up due in {days_until_due} days")
        elif open_tasks:
            score += 4
            reasons.append("open sales follow-up already scheduled")
    elif open_tasks:
        score += 4
        reasons.append("open sales follow-up already scheduled")

    score -= min(len(missing) * 3, 18)
    return {
        "priority_score": max(score, 0),
        "priority_reasons": reasons[:5],
        "segment": _segment(summary, reasons),
    }


def _segment(summary: dict[str, Any], reasons: list[str]) -> str:
    if _int_value(summary.get("overdue_sales_followup_task_count")):
        return "Overdue sales follow-up"
    if any("contract end" in reason for reason in reasons):
        return "Renewal / contract-end alert"
    if "decision maker" in " ".join(summary.get("missing_fields", [])).lower():
        return "Missing direct contact"
    if summary.get("prospecting_account") == "true":
        return "Pre-demo target account"
    return "High-value dormant account"


def _pre_demo_stakeholder_text(contacts: list[dict[str, Any]]) -> str:
    if not contacts:
        return "meeting attendee needed"
    selected = next((contact for contact in contacts if contact.get("is_decision_maker")), contacts[0])
    display_name = selected.get("display_name") or "HubSpot contact"
    persona = selected.get("persona") or selected.get("buying_role") or "persona needed"
    return f"not confirmed; HubSpot contact: {display_name} ({persona})"


def _pre_demo_role_bucket(contacts: list[dict[str, Any]]) -> str:
    text = " ".join(str(contact.get("persona") or contact.get("buying_role") or "") for contact in contacts).lower()
    if any(marker in text for marker in ("founder", "owner", "ceo", "chief", "boss")):
        return "owner"
    if any(marker in text for marker in ("ops", "operation", "gm", "general manager", "coo")):
        return "ops"
    if any(marker in text for marker in ("hr", "people", "human resource", "talent")):
        return "hr"
    if any(marker in text for marker in ("finance", "payroll", "account")):
        return "finance"
    return "unknown"


def _pre_demo_industry_bucket(company: dict[str, Any]) -> str:
    industry = str(company.get("industry") or "").lower()
    if any(marker in industry for marker in ("f&b", "food", "restaurant", "cafe", "beverage")):
        return "fnb"
    if any(marker in industry for marker in ("hospitality", "hotel", "resort", "villa")):
        return "hospitality"
    if "retail" in industry:
        return "retail"
    return "general"


def _load_case_study_catalog() -> list[dict[str, Any]]:
    global _CASE_STUDY_CATALOG_CACHE
    if _CASE_STUDY_CATALOG_CACHE is not None:
        return _CASE_STUDY_CATALOG_CACHE
    try:
        with open(CASE_STUDY_CATALOG_PATH, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        _CASE_STUDY_CATALOG_CACHE = []
        return _CASE_STUDY_CATALOG_CACHE
    cases = payload.get("cases") if isinstance(payload, dict) else []
    _CASE_STUDY_CATALOG_CACHE = [case for case in cases if isinstance(case, dict)]
    return _CASE_STUDY_CATALOG_CACHE


def _case_study_terms(context: dict[str, Any]) -> set[str]:
    company = context.get("company", {})
    values = [
        company.get("name"),
        company.get("country"),
        company.get("industry"),
        company.get("current_tools"),
        company.get("account_status"),
    ]
    terms = set(_normalized_words(" ".join(str(value or "") for value in values)).split())
    bucket = _pre_demo_industry_bucket(company)
    if bucket != "general":
        terms.add(bucket)
    if bucket == "fnb":
        terms.update({"fnb", "food", "restaurant", "cafe", "beverage", "shift-work"})
    if bucket == "retail":
        terms.update({"retail", "outlet", "shift-work"})
    headcount = _int_value(company.get("headcount"))
    if headcount >= 50:
        terms.add("multi-outlet")
    if headcount >= 100:
        terms.add("large-team")
    return terms


def _case_study_score(case: dict[str, Any], context: dict[str, Any]) -> tuple[int, list[str]]:
    company = context.get("company", {})
    country = str(company.get("country") or "")
    bucket = _pre_demo_industry_bucket(company)
    terms = _case_study_terms(context)
    tags = set(str(tag or "").lower() for tag in case.get("match_tags", []))
    score = 0
    reasons: list[str] = []

    if country and country == case.get("country"):
        score += 8
        reasons.append(f"same market: {country}")
    if bucket != "general" and bucket in tags:
        score += 8
        reasons.append(f"same industry bucket: {bucket}")

    tag_hits = sorted(tags.intersection(terms))
    if tag_hits:
        score += min(len(tag_hits) * 2, 12)
        reasons.append("matched tags: " + ", ".join(tag_hits[:5]))

    if not company.get("industry") and not company.get("current_tools") and not _int_value(company.get("headcount")):
        return 0, []
    return score, reasons[:3]


def _pre_demo_case_study_matches(context: dict[str, Any]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for case in _load_case_study_catalog():
        if case.get("approved_for_name_drops") is not True:
            continue
        score, reasons = _case_study_score(case, context)
        if score < CASE_STUDY_MIN_MATCH_SCORE:
            continue
        matches.append(
            {
                "customer": case.get("customer"),
                "country": case.get("country"),
                "industry": case.get("industry"),
                "summary": case.get("name_drop"),
                "source_url": case.get("primary_url"),
                "video_url": case.get("video_url"),
                "video_id": case.get("video_id"),
                "transcript_source": case.get("transcript_source"),
                "transcript_status": case.get("transcript_status"),
                "video_evidence_path": case.get("video_evidence_path"),
                "knowledge_hooks": case.get("knowledge_hooks") if isinstance(case.get("knowledge_hooks"), list) else [],
                "kns_material": case.get("kns_material") if isinstance(case.get("kns_material"), dict) else {},
                "match_score": score,
                "match_reasons": reasons,
            }
        )
    matches.sort(key=lambda match: (-_int_value(match.get("match_score")), str(match.get("customer") or "")))
    return matches[:CASE_STUDY_MATCH_LIMIT]


def _pre_demo_kns_knowledge_hooks(context: dict[str, Any]) -> list[dict[str, Any]]:
    hooks: list[dict[str, Any]] = []
    for case in _load_case_study_catalog():
        if case.get("approved_for_name_drops") is not True:
            continue
        score, reasons = _case_study_score(case, context)
        if score < CASE_STUDY_MIN_MATCH_SCORE:
            continue
        case_hooks = case.get("knowledge_hooks")
        if not isinstance(case_hooks, list):
            continue
        for hook in case_hooks:
            if not isinstance(hook, dict) or not hook.get("hook"):
                continue
            confidence = str(hook.get("confidence") or "needs-check")
            rank_score = score if confidence == "verified_public_video" else score - 100
            hooks.append(
                {
                    "customer": case.get("customer"),
                    "hook": hook.get("hook"),
                    "pain": hook.get("pain"),
                    "outcome": hook.get("outcome"),
                    "best_fit_prospect_pattern": hook.get("best_fit_prospect_pattern"),
                    "source_timestamp": hook.get("source_timestamp"),
                    "source_url": hook.get("source_url") or case.get("primary_url"),
                    "video_url": hook.get("video_url") or case.get("video_url"),
                    "video_id": case.get("video_id"),
                    "transcript_status": case.get("transcript_status"),
                    "video_evidence_path": case.get("video_evidence_path"),
                    "confidence": confidence,
                    "match_score": score,
                    "match_reasons": reasons,
                    "_rank_score": rank_score,
                }
            )
    hooks.sort(key=lambda hook: (-_int_value(hook.get("_rank_score")), str(hook.get("customer") or "")))
    for hook in hooks:
        hook.pop("_rank_score", None)
    return hooks[:CASE_STUDY_MATCH_LIMIT]


def _case_study_sales_moment_allowed(case: dict[str, Any], sales_moment: str) -> bool:
    if not sales_moment:
        return True
    moments = {str(moment or "").strip().lower() for moment in case.get("best_use_sales_moments", [])}
    return sales_moment.strip().lower() in moments


def _case_study_evidence_refs(case: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for ref in case.get("evidence_refs", []):
        if not isinstance(ref, dict):
            continue
        refs.append(
            {
                "timestamp": ref.get("timestamp") or "",
                "claim": ref.get("claim") or "",
                "source_path": ref.get("source_path") or "",
                "line": ref.get("line"),
            }
        )
    return refs


def _sales_case_study_matches(context: dict[str, Any], sales_moment: str = "", limit: int = CASE_STUDY_MATCH_LIMIT) -> list[dict[str, Any]]:
    requested_limit = _bounded_int(limit, default=CASE_STUDY_MATCH_LIMIT, maximum=10)
    matches: list[dict[str, Any]] = []
    for case in _load_case_study_catalog():
        if case.get("approved_for_name_drops") is not True:
            continue
        if not _case_study_sales_moment_allowed(case, sales_moment):
            continue
        score, reasons = _case_study_score(case, context)
        if score < CASE_STUDY_MIN_MATCH_SCORE:
            continue
        full_video_review = case.get("full_video_review") if isinstance(case.get("full_video_review"), dict) else {}
        matches.append(
            {
                "id": case.get("id"),
                "customer": case.get("customer"),
                "country": case.get("country"),
                "market": case.get("market"),
                "industry": case.get("industry"),
                "size": case.get("size"),
                "summary": case.get("name_drop"),
                "pain": case.get("pain"),
                "outcome": case.get("outcome"),
                "source_url": case.get("primary_url"),
                "video_url": case.get("video_url"),
                "video_id": case.get("video_id"),
                "transcript_source": case.get("transcript_source"),
                "transcript_status": case.get("transcript_status"),
                "video_evidence_path": case.get("video_evidence_path"),
                "knowledge_hooks": case.get("knowledge_hooks") if isinstance(case.get("knowledge_hooks"), list) else [],
                "kns_material": case.get("kns_material") if isinstance(case.get("kns_material"), dict) else {},
                "source_type": case.get("source_type") or "published_customer_story",
                "approval_basis": case.get("approval_basis"),
                "best_use_sales_moments": case.get("best_use_sales_moments", []),
                "do_not_claim": case.get("do_not_claim", []),
                "full_video_review": full_video_review,
                "evidence_refs": _case_study_evidence_refs(case),
                "match_score": score,
                "match_reasons": reasons,
            }
        )
    matches.sort(key=lambda match: (-_int_value(match.get("match_score")), str(match.get("customer") or "")))
    return matches[:requested_limit]


def _daily_nurture_for_date(value: str = "") -> date:
    parsed = _date_value(value)
    if parsed:
        return parsed
    return datetime.now(SINGAPORE_TIMEZONE).date()


def _daily_nurture_bucket_index(for_date: date) -> int:
    return min(for_date.weekday(), DAILY_NURTURE_WORKWEEK_DAYS - 1)


def _company_sort_key(company: dict[str, Any]) -> tuple[str, str]:
    props = company.get("properties") if isinstance(company.get("properties"), dict) else {}
    return (
        str(props.get("name") or company.get("name") or "").strip().lower(),
        str(company.get("id") or company.get("company_id") or ""),
    )


def _daily_nurture_company_bucket(
    companies: list[dict[str, Any]],
    for_date: date,
    daily_account_count: int,
) -> dict[str, Any]:
    capped_daily_count = max(1, min(int(daily_account_count or DAILY_NURTURE_DEFAULT_ACCOUNT_COUNT), DAILY_NURTURE_PROTECTED_POOL_SIZE))
    sorted_companies = sorted(companies, key=_company_sort_key)
    bucket_index = _daily_nurture_bucket_index(for_date)
    start = bucket_index * capped_daily_count
    end = start + capped_daily_count
    return {
        "bucket_index": bucket_index,
        "bucket_label": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"][bucket_index],
        "daily_account_count": capped_daily_count,
        "start_index": start,
        "end_index": end,
        "companies": sorted_companies[start:end],
        "sorted_company_ids": [str(company.get("id") or company.get("company_id") or "") for company in sorted_companies],
    }


def _split_material_tags(value: Any) -> list[str]:
    if isinstance(value, list):
        raw_values = value
    else:
        raw_values = re.split(r"[,;|]", str(value or ""))
    tags = []
    for raw in raw_values:
        tag = _normalized_words(str(raw or "")).strip()
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def _material_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    return _date_value(text)


def _material_registry_contract() -> dict[str, Any]:
    return {
        "source": "read-only Google Sheet",
        "tabs": list(DAILY_NURTURE_MATERIAL_TABS),
        "minimum_fields": list(DAILY_NURTURE_MATERIAL_FIELDS),
        "status_policy": "Only active, approved, or live rows are eligible. Expired/future rows are ignored.",
    }


def _safe_material_rows(rows: list[dict[str, Any]] | None, for_date: date) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    active: list[dict[str, Any]] = []
    ignored: list[dict[str, Any]] = []
    for index, row in enumerate(rows or []):
        if not isinstance(row, dict):
            ignored.append({"row_index": index, "reason": "not an object"})
            continue
        status = str(row.get("status") or "").strip().lower()
        if status and status not in DAILY_NURTURE_ACTIVE_MATERIAL_STATUSES:
            ignored.append({"material_id": row.get("material_id") or "", "reason": f"inactive status {status}"})
            continue
        valid_from = _material_date(row.get("valid_from"))
        valid_until = _material_date(row.get("valid_until"))
        if valid_from and valid_from > for_date:
            ignored.append({"material_id": row.get("material_id") or "", "reason": "not yet valid"})
            continue
        if valid_until and valid_until < for_date:
            ignored.append({"material_id": row.get("material_id") or "", "reason": "expired"})
            continue
        active.append(dict(row))
    return active, ignored


def _material_country_matches(material: dict[str, Any], country: str) -> bool:
    scopes = _split_material_tags(material.get("country_scope"))
    if not scopes:
        return True
    normalized_country = _normalized_words(country)
    return "all" in scopes or normalized_country in scopes or any(scope in normalized_country for scope in scopes)


def _contact_role_text(contact: dict[str, Any]) -> str:
    return _normalized_words(
        " ".join(
            [
                str(contact.get("persona") or ""),
                str(contact.get("buying_role") or ""),
                str(contact.get("channel_fit") or ""),
                str(contact.get("contact_confidence") or ""),
            ]
        )
    )


def _stakeholder_roles_for_contact(contact: dict[str, Any]) -> list[dict[str, str]]:
    roles: list[dict[str, str]] = []
    buying_role = str(contact.get("buying_role") or "")
    role_text = _contact_role_text(contact)
    persona_text = _normalized_words(str(contact.get("persona") or ""))
    warm_text = _normalized_words(f"{contact.get('channel_fit') or ''} {contact.get('contact_confidence') or ''}")

    if contact.get("is_verified_decision_maker") or _has_decision_maker_buying_role(buying_role):
        roles.append({"role": "decision_maker", "confidence": "verified", "basis": "HubSpot hs_buying_role=DECISION_MAKER"})
    elif contact.get("is_role_inferred_decision_maker"):
        roles.append({"role": "decision_maker", "confidence": "needs-check", "basis": "title-only decision-maker candidate"})

    if "champion" in role_text or "advocate" in role_text:
        confidence = "verified" if "champion" in _normalized_words(buying_role) else "needs-check"
        roles.append({"role": "champion", "confidence": confidence, "basis": "HubSpot champion/persona signal" if confidence == "verified" else "warm activity/persona candidate"})
    elif any(marker in warm_text for marker in ("warm", "reply", "replied", "responsive", "friend", "friendly")):
        roles.append({"role": "champion", "confidence": "needs-check", "basis": "prior warm activity or reply evidence"})

    influencer_markers = (
        "hr",
        "human resource",
        "people",
        "ops",
        "operation",
        "finance",
        "payroll",
        "area",
        "outlet",
        "manager",
        "admin",
        "talent",
    )
    if "influencer" in role_text or any(marker in persona_text for marker in influencer_markers):
        confidence = "verified" if "influencer" in _normalized_words(buying_role) else "needs-check"
        roles.append({"role": "influencer", "confidence": confidence, "basis": "HubSpot buying role/persona" if confidence == "verified" else "HR/Ops/Finance/Area/Outlet title candidate"})

    seen = set()
    unique_roles = []
    for role in roles:
        key = role["role"]
        if key in seen:
            continue
        seen.add(key)
        unique_roles.append(role)
    return unique_roles


def _daily_nurture_stakeholders(context: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    stakeholders: list[dict[str, Any]] = []
    present_roles: set[str] = set()
    for contact in context.get("contacts", []):
        if not isinstance(contact, dict):
            continue
        for role in _stakeholder_roles_for_contact(contact):
            present_roles.add(role["role"])
            stakeholders.append(
                {
                    "contact_id": contact.get("contact_id") or "",
                    "display_name": contact.get("display_name") or "HubSpot contact",
                    "persona": contact.get("persona") or "",
                    "buying_role": contact.get("buying_role") or "",
                    "stakeholder_role": role["role"],
                    "role_confidence": role["confidence"],
                    "role_basis": role["basis"],
                    "channel_fit": contact.get("channel_fit") or "",
                    "contact_confidence": contact.get("contact_confidence") or "",
                    "do_not_contact": bool(contact.get("do_not_contact")),
                    "do_not_contact_basis": contact.get("do_not_contact_basis") or "",
                }
            )
    gaps = []
    for required_role in ("decision_maker", "influencer", "champion"):
        if required_role not in present_roles:
            gaps.append({"role": required_role, "reason": f"no {required_role} identified from HubSpot contacts"})
    return stakeholders, gaps


def _material_schema_names(value: Any) -> list[str]:
    if isinstance(value, list):
        names = [str(item or "").strip() for item in value]
    else:
        text = str(value or "").strip()
        if not text:
            return list(DAILY_NURTURE_DEFAULT_TEMPLATE_SCHEMA)
        try:
            payload = json.loads(text)
            if isinstance(payload, list):
                names = [str(item or "").strip() for item in payload]
            else:
                names = [part.strip() for part in re.split(r"[,;|]", text)]
        except json.JSONDecodeError:
            names = [part.strip() for part in re.split(r"[,;|]", text)]
    cleaned = [name for name in names if name]
    return cleaned or list(DAILY_NURTURE_DEFAULT_TEMPLATE_SCHEMA)


def _first_name(display_name: str) -> str:
    return str(display_name or "").strip().split(" ")[0] or "there"


def _template_params(schema_names: list[str], context: dict[str, Any], stakeholder: dict[str, Any], material: dict[str, Any]) -> list[str]:
    company = context.get("company", {})
    mapping = {
        "first_name": _first_name(stakeholder.get("display_name") or ""),
        "account_name": str(company.get("name") or ""),
        "company_name": str(company.get("name") or ""),
        "material_title": str(material.get("title") or ""),
        "material_url": str(material.get("url") or ""),
        "message_hook": str(material.get("message_hook") or material.get("hook") or ""),
        "hook": str(material.get("message_hook") or material.get("hook") or ""),
        "industry": str(company.get("industry") or ""),
        "current_tools": str(company.get("current_tools") or ""),
        "country": str(company.get("country") or ""),
        "stakeholder_role": str(stakeholder.get("stakeholder_role") or ""),
        "persona": str(stakeholder.get("persona") or ""),
        "ae_name": str(company.get("owner_name") or company.get("owner_email") or ""),
    }
    return [mapping.get(_normalized_words(name).replace(" ", "_"), "") for name in schema_names]


def _case_study_materials(context: dict[str, Any]) -> list[dict[str, Any]]:
    materials = []
    for match in _pre_demo_case_study_matches(context):
        title = str(match.get("customer") or "case study").strip()
        hooks = [hook for hook in (match.get("knowledge_hooks") or []) if isinstance(hook, dict) and hook.get("hook")]
        hook = hooks[0] if hooks else {}
        kns_material = match.get("kns_material") if isinstance(match.get("kns_material"), dict) else {}
        message_hook = hook.get("hook") or match.get("summary") or ""
        materials.append(
            {
                "material_id": kns_material.get("material_id")
                or f"case-study:{_normalize_name(title) or hashlib.sha256(title.encode('utf-8')).hexdigest()[:8]}",
                "category": "case_study",
                "title": title,
                "url": match.get("video_url") or match.get("source_url") or "",
                "status": "approved",
                "country_scope": match.get("country") or "",
                "industry_tags": match.get("industry") or "",
                "concept_tags": "case study, same industry, knowledge",
                "persona_tags": "",
                "template_name": DAILY_NURTURE_DEFAULT_TEMPLATE_NAME,
                "template_params_schema": list(DAILY_NURTURE_DEFAULT_TEMPLATE_SCHEMA),
                "message_hook": message_hook,
                "owner": "repo_case_study_catalog",
                "kns_pillar": "Knowledge",
                "pillar_summary": message_hook,
                "buyer_value": hook.get("outcome") or match.get("summary") or "",
                "ae_use_case": "knowledge_touch, pre_demo, nurture, case_study_proof",
                "source_evidence_url": match.get("video_evidence_path") or match.get("source_url") or "",
                "asset_url": match.get("video_url") or match.get("source_url") or "",
                "talk_track": hook.get("best_fit_prospect_pattern") or "Use as a source-backed Knowledge proof point.",
                "transcript_status": match.get("transcript_status") or "",
                "match_reasons": match.get("match_reasons") or [],
                "match_score": match.get("match_score") or 0,
            }
        )
    return materials


def _material_score(material: dict[str, Any], context: dict[str, Any], stakeholder: dict[str, Any]) -> tuple[int, list[str]]:
    company = context.get("company", {})
    score = 0
    reasons: list[str] = []
    if _material_country_matches(material, str(company.get("country") or "")):
        score += 4
        if material.get("country_scope"):
            reasons.append("country_scope match")
    else:
        return -100, []

    industry_terms = set(_split_material_tags(company.get("industry")))
    industry_terms.update(_normalized_words(str(company.get("industry") or "")).split())
    industry_hits = sorted(set(_split_material_tags(material.get("industry_tags"))).intersection(industry_terms))
    if industry_hits:
        score += 20 + min(len(industry_hits) * 3, 9)
        reasons.append("same industry: " + ", ".join(industry_hits[:3]))

    context_terms = set(
        _normalized_words(
            " ".join(
                [
                    str(company.get("name") or ""),
                    str(company.get("industry") or ""),
                    str(company.get("current_tools") or ""),
                    str(company.get("account_status") or ""),
                ]
            )
        ).split()
    )
    bucket = _pre_demo_industry_bucket(company)
    if bucket != "general":
        context_terms.add(bucket)
    concept_hits = sorted(set(_split_material_tags(material.get("concept_tags"))).intersection(context_terms))
    if concept_hits:
        score += 16 + min(len(concept_hits) * 3, 9)
        reasons.append("same concept: " + ", ".join(concept_hits[:3]))

    persona_terms = set(_contact_role_text(stakeholder).split())
    stakeholder_role = str(stakeholder.get("stakeholder_role") or "")
    persona_terms.add(stakeholder_role)
    persona_terms.add(stakeholder_role.replace("_", " "))
    persona_hits = sorted(set(_split_material_tags(material.get("persona_tags"))).intersection(persona_terms))
    if persona_hits:
        score += 10
        reasons.append("persona match: " + ", ".join(persona_hits[:3]))

    category = str(material.get("category") or "").lower()
    if category in {"peer_intro", "warm_intro"}:
        score += 6
    elif category in {"event", "event_invite", "speaking_opportunity", "venue_opportunity"}:
        score += 5
    elif category in {"case_study", "podcast"}:
        score += 4
    if not reasons and category:
        score += 1
        reasons.append(f"generic {category}")
    score += _int_value(material.get("match_score"))
    if material.get("match_reasons"):
        reasons.extend([str(reason) for reason in material.get("match_reasons")[:3]])
    return score, reasons[:5]


def _match_nurture_material(
    context: dict[str, Any],
    stakeholder: dict[str, Any],
    material_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    candidates = list(material_rows) + _case_study_materials(context)
    scored = []
    for material in candidates:
        score, reasons = _material_score(material, context, stakeholder)
        if score < 0:
            continue
        scored.append((score, str(material.get("material_id") or material.get("title") or ""), material, reasons))
    if not scored:
        return {
            "material_id": "",
            "category": "material_needed",
            "title": "Material match needed",
            "url": "",
            "template_name": "",
            "template_params_schema": [],
            "message_hook": "Pick a podcast, case study, event invite, salary benchmark, fireside learning, venue ask, speaker ask, or warm peer intro.",
            "match_score": 0,
            "match_reasons": ["no active same-industry/concept/persona material found"],
        }
    scored.sort(key=lambda item: (-item[0], item[1]))
    score, _, selected, reasons = scored[0]
    material = dict(selected)
    material["match_score"] = score
    material["match_reasons"] = reasons
    return material


def _daily_nurture_message_id(run_id: str, company_id: str, contact_id: str, stakeholder_role: str) -> str:
    payload = f"{run_id}:{company_id}:{contact_id}:{stakeholder_role}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _daily_nurture_draft(context: dict[str, Any], stakeholder: dict[str, Any], material: dict[str, Any]) -> str:
    company = context.get("company", {})
    first_name = _first_name(stakeholder.get("display_name") or "")
    company_name = str(company.get("name") or "your team")
    hook = str(material.get("message_hook") or "").strip()
    title = str(material.get("title") or "this").strip()
    url = str(material.get("url") or "").strip()
    if hook:
        body = f"Hi {first_name}, thought of {company_name} because {hook}"
    else:
        body = f"Hi {first_name}, thought this might be useful for {company_name}: {title}"
    if url:
        body = f"{body}\n{url}"
    return body[:900]


def _daily_nurture_message(
    run_id: str,
    context: dict[str, Any],
    stakeholder: dict[str, Any],
    material_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    company = context.get("company", {})
    company_id = str(company.get("company_id") or "")
    contact_id = str(stakeholder.get("contact_id") or "")
    role = str(stakeholder.get("stakeholder_role") or "")
    material = _match_nurture_material(context, stakeholder, material_rows)
    schema_names = _material_schema_names(material.get("template_params_schema"))
    template_name = str(material.get("template_name") or "").strip()
    template_params = _template_params(schema_names, context, stakeholder, material)
    do_not_contact = bool(stakeholder.get("do_not_contact"))
    eazybe_ready = bool(template_name and contact_id and material.get("category") != "material_needed" and not do_not_contact)
    if do_not_contact:
        send_status = "blocked_do_not_contact"
    elif eazybe_ready:
        send_status = "pending_approval"
    else:
        send_status = "needs_material_or_template"
    return {
        "message_id": _daily_nurture_message_id(run_id, company_id, contact_id, role),
        "run_id": run_id,
        "company_id": company_id,
        "company_name": company.get("name") or "",
        "contact_id": contact_id,
        "stakeholder_name": stakeholder.get("display_name") or "HubSpot contact",
        "stakeholder_role": role,
        "role_confidence": stakeholder.get("role_confidence") or "needs-check",
        "role_basis": stakeholder.get("role_basis") or "",
        "persona": stakeholder.get("persona") or "",
        "do_not_contact": do_not_contact,
        "do_not_contact_basis": stakeholder.get("do_not_contact_basis") or "",
        "material": {
            "material_id": material.get("material_id") or "",
            "category": material.get("category") or "",
            "title": material.get("title") or "",
            "url": material.get("url") or "",
            "message_hook": material.get("message_hook") or "",
            "match_score": material.get("match_score") or 0,
            "match_reasons": material.get("match_reasons") or [],
        },
        "draft_preview": _daily_nurture_draft(context, stakeholder, material),
        "template_payload": {
            "template_name": template_name,
            "template_params_schema": schema_names,
            "template_params": template_params,
        },
        "eazybe_ready": eazybe_ready,
        "send_status": send_status,
        "safe_for_slack": True,
    }


def _daily_nurture_run_id(owner_email: str, for_date: date, bucket_index: int, company_ids: list[str]) -> str:
    digest = hashlib.sha256("|".join(company_ids).encode("utf-8")).hexdigest()[:8]
    owner_key = _normalize_name(owner_email or "owner") or "owner"
    return f"daily-nurture:{owner_key}:{for_date.isoformat()}:bucket-{bucket_index + 1}:{digest}"


def _daily_nurture_contexts(companies: list[dict[str, Any]], scope: dict[str, Any]) -> dict[str, dict[str, Any]]:
    company_ids = [
        str(company.get("id") or company.get("company_id") or "").strip()
        for company in companies
        if str(company.get("id") or company.get("company_id") or "").strip()
    ]
    contact_index = _batch_association_ids("companies", "contacts", company_ids)
    contact_detail_index = _safe_contact_index(contact_index)
    contexts: dict[str, dict[str, Any]] = {}

    for company in companies:
        company_id = str(company.get("id") or company.get("company_id") or "").strip()
        if not company_id or not _has_company_access(company, scope):
            continue
        contacts = contact_detail_index.get(company_id, [])
        props = company.get("properties", {})
        company_summary = _summarize_company_with_contacts(
            company,
            contacts,
            contact_count=len(contact_index.get(company_id, [])),
        )
        contexts[company_id] = {
            "company": company_summary,
            "contacts": contacts,
            "deals": [],
            "sales_followup_tasks": [],
            "coverage": _coverage(props, contacts),
        }

    return contexts


def _daily_nurture_runs_dir() -> Path | None:
    raw = os.environ.get(DAILY_NURTURE_RUNS_DIR_ENV, "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def _profile_runtime_dir() -> Path:
    raw = os.environ.get("HERMES_HOME", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".hermes" / "profiles" / OPERATION_LEDGER_DEFAULT_PROFILE


def _operation_ledger_dir() -> Path:
    raw = os.environ.get(OPERATION_LEDGER_DIR_ENV, "").strip()
    if raw:
        return Path(raw).expanduser()
    return _profile_runtime_dir() / "operation-ledger"


def _lesson_candidates_dir() -> Path:
    raw = os.environ.get(LESSON_CANDIDATES_DIR_ENV, "").strip()
    if raw:
        return Path(raw).expanduser()
    return _profile_runtime_dir() / "lesson-candidates"


def _safe_file_stem(value: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9_.:-]+", "_", value or "").strip("._")
    if safe_name:
        return safe_name[:120]
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _ledger_path(operation_id: str) -> Path:
    return _operation_ledger_dir() / f"{_safe_file_stem(operation_id)}.json"


def _lesson_candidate_path(lesson_id: str) -> Path:
    return _lesson_candidates_dir() / f"{_safe_file_stem(lesson_id)}.json"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def _load_operation_record(operation_id: str) -> dict[str, Any]:
    path = _ledger_path(operation_id)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_lesson_candidate(lesson_id: str) -> dict[str, Any]:
    path = _lesson_candidate_path(lesson_id)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _iter_lesson_candidates() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    directory = _lesson_candidates_dir()
    try:
        paths = sorted(directory.glob("*.json"))
    except OSError:
        return candidates
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(payload, dict):
            candidates.append(payload)
    return candidates


def _compact_ledger_record(record: dict[str, Any]) -> dict[str, Any]:
    history = record.get("history") if isinstance(record.get("history"), list) else []
    return {
        "operation_id": record.get("operation_id") or "",
        "slack_thread": record.get("slack_thread") or "",
        "phase": record.get("phase") or "",
        "last_checkpoint": record.get("last_checkpoint") or "",
        "approval_marker_present": bool(record.get("approval_marker")),
        "idempotency_key": record.get("idempotency_key") or "",
        "side_effect": record.get("side_effect") or "none",
        "compact_error": record.get("compact_error") or "",
        "updated_at": record.get("updated_at") or "",
        "history_count": len(history),
    }


def _compact_lesson_candidate(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "lesson_id": record.get("lesson_id") or "",
        "created_at": record.get("created_at") or "",
        "source_thread_permalink": record.get("source_thread_permalink") or "",
        "source_summary": record.get("source_summary") or "",
        "proposed_rule": record.get("proposed_rule") or "",
        "applies_to": record.get("applies_to") or "",
        "target_repo_surface": record.get("target_repo_surface") or "",
        "risk_class": record.get("risk_class") or "",
        "status": record.get("status") or "pending_review",
        "reviewer": record.get("reviewer") or "",
        "review_notes": record.get("review_notes") or "",
    }


def _clean_lesson_text(value: str, *, max_length: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text[:max_length]


def _lesson_payload_unsafe(*values: str) -> str:
    combined = "\n".join(str(value or "") for value in values)
    secret_patterns = (
        r"xox[baprs]-",
        r"sk-[A-Za-z0-9_-]{20,}",
        r"(?i)(api[_ -]?key|private[_ -]?app[_ -]?token|oauth[_ -]?token|client[_ -]?secret)\s*[:=]",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    )
    for pattern in secret_patterns:
        if re.search(pattern, combined):
            return "unsafe_payload:secret_or_token"
    if re.search(r"(?im)^\s*(user|assistant|bot|<@U[A-Z0-9]+|[A-Za-z .'-]{1,40}):\s+.+\n\s*(user|assistant|bot|<@U[A-Z0-9]+|[A-Za-z .'-]{1,40}):", combined):
        return "unsafe_payload:raw_transcript_shape"
    if re.search(r"(?i)\b(user|assistant|bot|<@U[A-Z0-9]+)\s*:\s+.{1,500}\b(user|assistant|bot|<@U[A-Z0-9]+)\s*:", combined):
        return "unsafe_payload:raw_transcript_shape"
    if re.search(r'(?i)"properties"\s*:\s*\{|"hs_communication_body"\s*:|"mobilephone"\s*:|"phone"\s*:', combined):
        return "unsafe_payload:raw_hubspot_row_or_pii_field"
    pii_text = "\n".join(str(value or "") for value in values[1:])
    phone_like = r"(?:\+?\d[\s().-]*){8,}"
    if re.search(rf"(?i)(phone|mobile|whatsapp|sms|contact number|number)\D{{0,40}}{phone_like}", pii_text) or re.search(
        rf"(?<!\w)\+\d[\d\s().-]{{7,}}", pii_text
    ):
        return "unsafe_payload:phone_number_like_text"
    return ""


def _persist_daily_nurture_run(run_id: str, payload: dict[str, Any]) -> dict[str, str | bool]:
    runs_dir = _daily_nurture_runs_dir()
    if not runs_dir:
        return {"persisted": False, "reason": f"{DAILY_NURTURE_RUNS_DIR_ENV} not configured"}
    safe_name = re.sub(r"[^A-Za-z0-9_.:-]+", "_", run_id or "")
    if not safe_name:
        return {"persisted": False, "reason": "missing run_id"}
    try:
        path = runs_dir / f"{safe_name}.json"
        _atomic_write_json(path, payload)
    except OSError as error:
        return {"persisted": False, "reason": f"write failed: {error.__class__.__name__}"}
    return {"persisted": True, "path": str(path)}


def _count_rows_by_key(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown").strip() or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _render_daily_nurture_slack_packet(answer: dict[str, Any], source: str, scope: dict[str, Any], confidence: str, caveat: str) -> str:
    rotation = answer.get("account_rotation") if isinstance(answer.get("account_rotation"), dict) else {}
    lines = [
        f"Daily nurture pack: {answer.get('for_date')} ({answer.get('bucket_label')})",
        f"run_id: {answer.get('run_id')}",
        f"payload_mode: {answer.get('payload_mode')}",
        f"returned_pool_count: {rotation.get('returned_pool_count')}",
        f"selected_account_count: {answer.get('selected_account_count')}",
        f"stakeholder_count: {answer.get('stakeholder_count')}",
        f"message_count: {answer.get('message_count')}",
        f"eazybe_ready_message_count: {answer.get('eazybe_ready_message_count')}",
        "",
        "5 sample accounts:",
    ]
    for index, account in enumerate(answer.get("sample_accounts") or [], start=1):
        lines.append(
            f"{index}. {account.get('company_name')} ({account.get('country') or 'country n/a'}; "
            f"{account.get('industry') or 'industry n/a'}) - stakeholders {account.get('stakeholder_row_count')}"
        )
        for row in (account.get("stakeholder_rows") or [])[:1]:
            blocked = " BLOCKED do-not-contact" if row.get("do_not_contact") else ""
            lines.append(
                f"   - {row.get('stakeholder_name')} | {row.get('stakeholder_role')} | {row.get('role_confidence')}{blocked} | "
                f"material: {row.get('material_title') or row.get('material_category') or 'material needed'} | "
                f"msg_id: {row.get('message_id')}"
            )
            draft = re.sub(r"https?://\S+", "[link]", str(row.get("draft_preview") or "").replace("\n", " "))[:120]
            if draft:
                lines.append(f"     draft: {draft}")
        extra_count = max(0, int(account.get("stakeholder_row_count") or 0) - 1)
        if extra_count:
            lines.append(f"     + {extra_count} more stakeholder row(s) in persisted run")
    role_summary = ", ".join(f"{role}: {count}" for role, count in (answer.get("role_gap_summary") or {}).items()) or "none"
    material_summary = ", ".join(f"{reason}: {count}" for reason, count in (answer.get("material_gap_summary") or {}).items()) or "none"
    lines.extend(
        [
            "",
            f"role_gap_count: {answer.get('role_gap_count')} ({role_summary})",
            f"material_gap_count: {answer.get('material_gap_count')} ({material_summary})",
            f"do_not_contact_blocked_count: {answer.get('do_not_contact_blocked_count')}",
            "Source: HubSpot + read-only Sheet registry + approved repo case studies",
            f"Scope: target_owner={scope.get('target_owner_email') or scope.get('hubspot_owner_email') or scope.get('email')}; countries={', '.join(scope.get('countries') or [])}",
            f"Confidence: {confidence}",
            f"Caveat: {str(caveat or '')[:220]}",
            "No WhatsApp sent; no HubSpot mutated.",
        ]
    )
    return "\n".join(lines)


def _compact_daily_nurture_response(
    response: dict[str, Any],
    sample_account_count: int = 5,
    max_gap_rows: int = 10,
    max_message_index: int = 30,
) -> dict[str, Any]:
    answer = response.get("answer") if isinstance(response.get("answer"), dict) else {}
    messages = [message for message in answer.get("messages", []) if isinstance(message, dict)]
    selected_accounts = [account for account in answer.get("selected_accounts", []) if isinstance(account, dict)]
    role_gaps = [gap for gap in answer.get("role_gaps", []) if isinstance(gap, dict)]
    material_gaps = [gap for gap in answer.get("material_gaps", []) if isinstance(gap, dict)]
    inaccessible_accounts = [account for account in answer.get("inaccessible_accounts", []) if isinstance(account, dict)]

    messages_by_company: dict[str, list[dict[str, Any]]] = {}
    for message in messages:
        company_id = str(message.get("company_id") or "")
        messages_by_company.setdefault(company_id, []).append(message)

    sample_accounts = []
    for account in selected_accounts[: max(0, sample_account_count)]:
        company_id = str(account.get("company_id") or "")
        account_messages = messages_by_company.get(company_id, [])
        stakeholder_rows = []
        for message in account_messages[:3]:
            material = message.get("material") if isinstance(message.get("material"), dict) else {}
            stakeholder_rows.append(
                {
                    "message_id": message.get("message_id") or "",
                    "stakeholder_name": message.get("stakeholder_name") or "",
                    "stakeholder_role": message.get("stakeholder_role") or "",
                    "role_confidence": message.get("role_confidence") or "",
                    "role_basis": message.get("role_basis") or "",
                    "material_id": material.get("material_id") or "",
                    "material_category": material.get("category") or "",
                    "material_title": material.get("title") or "",
                    "material_match_reasons": (material.get("match_reasons") or [])[:3],
                    "draft_preview": str(message.get("draft_preview") or "")[:360],
                    "eazybe_ready": bool(message.get("eazybe_ready")),
                    "send_status": message.get("send_status") or "",
                    "do_not_contact": bool(message.get("do_not_contact")),
                }
            )
        sample_accounts.append(
            {
                **account,
                "stakeholder_rows": stakeholder_rows,
                "stakeholder_row_count": len(account_messages),
                "stakeholder_rows_truncated": len(account_messages) > len(stakeholder_rows),
            }
        )

    selected_account_summaries = [
        {
            "company_id": account.get("company_id") or "",
            "company_name": account.get("company_name") or "",
            "country": account.get("country") or "",
            "industry": account.get("industry") or "",
            "current_tools": account.get("current_tools") or "",
            "stakeholder_count": account.get("stakeholder_count") or 0,
            "message_count": account.get("message_count") or 0,
            "role_gap_count": len(account.get("role_gaps") or []),
        }
        for account in selected_accounts
    ]

    message_index_sample = []
    for message in messages[: max(0, max_message_index)]:
        material = message.get("material") if isinstance(message.get("material"), dict) else {}
        message_index_sample.append(
            {
                "message_id": message.get("message_id") or "",
                "company_id": message.get("company_id") or "",
                "company_name": message.get("company_name") or "",
                "stakeholder_name": message.get("stakeholder_name") or "",
                "stakeholder_role": message.get("stakeholder_role") or "",
                "role_confidence": message.get("role_confidence") or "",
                "material_id": material.get("material_id") or "",
                "material_title": material.get("title") or "",
                "eazybe_ready": bool(message.get("eazybe_ready")),
                "send_status": message.get("send_status") or "",
                "do_not_contact": bool(message.get("do_not_contact")),
            }
        )

    compact_answer = {
        "payload_mode": "compact_slack_packet",
        "full_payload_location": "run_persistence.path when persisted=true",
        "run_id": answer.get("run_id") or "",
        "for_date": answer.get("for_date") or "",
        "timezone": answer.get("timezone") or "Asia/Singapore",
        "working_day_policy": answer.get("working_day_policy") or "",
        "bucket_index": answer.get("bucket_index"),
        "bucket_label": answer.get("bucket_label") or "",
        "account_rotation": answer.get("account_rotation") or {},
        "material_registry": answer.get("material_registry") or {},
        "selected_account_summaries": selected_account_summaries,
        "selected_account_count": len(selected_accounts),
        "stakeholder_count": sum(_int_value(account.get("stakeholder_count")) for account in selected_accounts),
        "message_count": answer.get("message_count") if answer.get("message_count") is not None else len(messages),
        "eazybe_ready_message_count": answer.get("eazybe_ready_message_count")
        if answer.get("eazybe_ready_message_count") is not None
        else sum(1 for message in messages if message.get("eazybe_ready")),
        "sample_accounts": sample_accounts,
        "sample_account_count": len(sample_accounts),
        "message_index_sample": message_index_sample,
        "message_index_sample_count": len(message_index_sample),
        "message_index_truncated": len(messages) > len(message_index_sample),
        "role_gap_count": len(role_gaps),
        "role_gap_summary": _count_rows_by_key(role_gaps, "role"),
        "role_gaps_sample": role_gaps[:max_gap_rows],
        "role_gaps_truncated": len(role_gaps) > max_gap_rows,
        "material_gap_count": len(material_gaps),
        "material_gap_summary": _count_rows_by_key(material_gaps, "reason"),
        "material_gaps_sample": material_gaps[:max_gap_rows],
        "material_gaps_truncated": len(material_gaps) > max_gap_rows,
        "do_not_contact_blocked_count": sum(1 for message in messages if message.get("do_not_contact")),
        "inaccessible_account_count": len(inaccessible_accounts),
        "inaccessible_accounts_sample": inaccessible_accounts[:max_gap_rows],
        "run_persistence": answer.get("run_persistence") or {},
        "approval_instructions": answer.get("approval_instructions") or "",
        "twelve_pm_sent_definition": answer.get("twelve_pm_sent_definition") or "",
        "whatsapp_auto_send": bool(answer.get("whatsapp_auto_send")),
    }
    compact_answer["slack_review_packet"] = _render_daily_nurture_slack_packet(
        compact_answer,
        response.get("source") or "",
        response.get("scope") or {},
        response.get("confidence") or "needs-check",
        response.get("caveat") or "",
    )
    return {
        "answer": compact_answer,
        "source": response.get("source") or "",
        "scope": response.get("scope") or {},
        "confidence": response.get("confidence") or "needs-check",
        "caveat": response.get("caveat") or "",
    }


def _pre_demo_case_study_name_drops(context: dict[str, Any]) -> list[str]:
    drops = [
        f"{match.get('summary')} Source: {match.get('source_url')}"
        for match in _pre_demo_case_study_matches(context)
        if match.get("summary") and match.get("source_url")
    ]
    while len(drops) < CASE_STUDY_MATCH_LIMIT:
        drops.append("case-study match needed")
    return drops[:CASE_STUDY_MATCH_LIMIT]


def _pre_demo_renewal_text(company: dict[str, Any]) -> str:
    contract = company.get("contract_end_date") or ""
    renewal = company.get("current_tool_renewal_date") or ""
    if contract:
        return str(contract)
    if renewal:
        return f"contract end date needed; current tool renewal context {renewal}"
    return "contract end date needed"


def _pre_demo_missing_evidence(context: dict[str, Any]) -> list[str]:
    company = context.get("company", {})
    contacts = context.get("contacts", [])
    missing = []
    field_checks = [
        ("number of employees", company.get("headcount")),
        ("industry", company.get("industry")),
        ("confirmed meeting attendees", contacts),
        ("current tools", company.get("current_tools")),
        ("contract end date", company.get("contract_end_date")),
    ]
    for label, value in field_checks:
        if not value:
            missing.append(label)
    for label in ["lead source", "meeting reason", "pricing"]:
        if label not in missing:
            missing.append(label)
    if len(_pre_demo_case_study_matches(context)) < CASE_STUDY_MATCH_LIMIT:
        missing.append("3 case-study matches")
    return missing


def _pre_demo_known_signals(context: dict[str, Any]) -> list[str]:
    company = context.get("company", {})
    coverage = context.get("coverage", {})
    signals = []
    if company.get("account_status"):
        signals.append(f"account status: {company.get('account_status')} ({company.get('account_status_source')})")
    if company.get("owner_email") or company.get("owner_name"):
        signals.append(f"HubSpot owner: {company.get('owner_name') or company.get('owner_email')} ({company.get('owner_email') or company.get('owner_id')})")
    if company.get("industry"):
        signals.append(f"industry: {company.get('industry')}")
    if company.get("headcount"):
        signals.append(f"headcount: {company.get('headcount')}")
    if company.get("current_tools"):
        signals.append(f"current tools: {company.get('current_tools')}")
    if company.get("contract_end_date"):
        signals.append(f"contract end date: {_pre_demo_renewal_text(company)}")
    if coverage.get("decision_maker_count"):
        signals.append(
            "decision-maker coverage exists in HubSpot "
            f"(hs_num_decision_makers={coverage.get('decision_maker_count_from_hubspot_property')}, "
            f"role-inferred candidates={coverage.get('role_inferred_decision_maker_candidate_count')})"
        )
    if company.get("sales_followup_task_count"):
        signals.append(f"{company.get('sales_followup_task_count')} open sales-owned follow-up task(s)")
    if company.get("overdue_sales_followup_task_count"):
        signals.append(f"{company.get('overdue_sales_followup_task_count')} overdue sales-owned follow-up task(s)")
    return signals or ["HubSpot has limited commercial context; use IC-BANT before demo depth"]


def _pre_demo_hypothesized_interest(context: dict[str, Any]) -> list[str]:
    company = context.get("company", {})
    contacts = context.get("contacts", [])
    industry_bucket = _pre_demo_industry_bucket(company)
    role_bucket = _pre_demo_role_bucket(contacts)
    interests: list[str] = []
    renewal = _date_value(company.get("contract_end_date"))
    today = datetime.now(timezone.utc).date()
    if renewal:
        days = (renewal - today).days
        if 0 <= days <= 180:
            if company.get("account_status") == "customer":
                interests.append(f"customer contract end timing is active ({days} days out), so StaffAny renewal/retention risk is likely")
            else:
                interests.append(
                    f"contract timing is active ({days} days out), but account status is {company.get('account_status') or 'unknown'}; treat this as prospect/incumbent-tool timing until customer status is verified"
                )
    if company.get("decision_maker_count") or company.get("buying_role_contact_count"):
        interests.append("there is some decision-maker coverage, so use the call to confirm authority and decision process")
    else:
        interests.append("decision-maker coverage is weak, so the first job is to map authority before over-demoing")
    if industry_bucket in {"fnb", "hospitality", "retail"}:
        interests.append("shift-based workforce likely makes scheduling, attendance, timesheet, and payroll handoff commercially relevant")
    if role_bucket == "owner":
        interests.append("owner/founder persona likely cares about ROI, labour leakage, and operational control")
    elif role_bucket == "ops":
        interests.append("ops persona likely cares about roster changes, attendance visibility, and outlet execution")
    elif role_bucket == "hr":
        interests.append("HR persona likely cares about payroll accuracy, compliance, adoption, and support")
    elif role_bucket == "finance":
        interests.append("finance/payroll persona likely cares about clean timesheet-to-payroll controls and error reduction")
    if company.get("overdue_sales_followup_task_count"):
        interests.append("existing overdue sales follow-up means the account needs a crisp next step, not a generic nurture touch")
    return interests[:5]


def _pre_demo_alternatives(context: dict[str, Any]) -> list[str]:
    company = context.get("company", {})
    alternatives = [
        "current tool needed before naming exact competitor",
        "status quo/manual process if the pain is not quantified",
    ]
    if company.get("contract_end_date"):
        alternatives.append(
            "StaffAny renewal/no-change risk" if company.get("account_status") == "customer" else "incumbent-tool renewal/no-change risk"
        )
    alternatives.append("cheaper HRIS/payroll option if the conversation becomes price-led")
    return alternatives


def _pre_demo_show_to_win(context: dict[str, Any]) -> list[str]:
    company = context.get("company", {})
    contacts = context.get("contacts", [])
    industry_bucket = _pre_demo_industry_bucket(company)
    role_bucket = _pre_demo_role_bucket(contacts)
    show = []
    if industry_bucket in {"fnb", "hospitality", "retail"}:
        show.extend(
            [
                "schedule to attendance to timesheet to payroll flow, because shift-based work creates leakage before payroll",
                "CICO controls and late/no-show visibility, because frontline execution needs proof instead of trust-only tracking",
            ]
        )
    else:
        show.append("simple end-to-end workforce workflow, because the confirmed pain is still incomplete")
    if role_bucket == "owner":
        show.append("labour cost visibility and ROI framing, because owner personas need the commercial reason to change")
    elif role_bucket == "ops":
        show.append("live roster changes and manager workflow, because ops needs day-to-day control")
    elif role_bucket == "hr":
        show.append("payroll accuracy, compliance, and support flow, because HR needs confidence after go-live")
    else:
        show.append("IC-BANT discovery first, because stakeholder persona is not confirmed")
    if company.get("contract_end_date"):
        if company.get("account_status") == "customer":
            show.append("StaffAny renewal timeline and retention path, because verified customer status makes renewal the right motion")
        else:
            show.append("incumbent-tool contract timeline and migration path, because prospect/unknown status means this is not a confirmed StaffAny renewal")
    return show[:5]


def _pre_demo_game_plan(context: dict[str, Any], plan: str) -> dict[str, Any]:
    company = context.get("company", {})
    show_to_win = _pre_demo_show_to_win(context)
    if plan == "A":
        return {
            "route": "Primary route: prove the most likely operational pain with a tailored StaffAny flow.",
            "package_or_pricing": "pricing needed",
            "talk_track": [
                show_to_win[0],
                "Tie each feature to a commercial outcome: less admin rework, fewer errors, cleaner labour control.",
                "Ask what would make them confident enough to move to the next step.",
            ],
            "commercial_next_step": "propose the package only after pain, authority, and timeline are confirmed",
        }
    fallback = "pilot/proof-of-value"
    if company.get("contract_end_date"):
        fallback = "customer renewal path" if company.get("account_status") == "customer" else "contract-timed pilot or phased migration"
    return {
        "route": f"Fallback route: {fallback} if price, adoption risk, or incumbent inertia dominates.",
        "package_or_pricing": "pricing needed",
        "talk_track": [
            "Use a lighter scope, pilot, or proof-of-value rather than forcing the full pitch.",
            "Do not offer buyback or renewal displacement until current tool, contract terms, and approval path are confirmed.",
            "Anchor on value-vs-price if they compare against a cheaper HRIS/payroll option.",
        ],
        "commercial_next_step": "agree the smallest proof that would de-risk the decision",
    }


def _pre_demo_ic_bant_prompts(context: dict[str, Any]) -> dict[str, list[str]]:
    company = context.get("company", {})
    interest = _pre_demo_hypothesized_interest(context)[0]
    timeline_prompt = (
        "Is this a StaffAny renewal timeline, an incumbent-tool contract end, or a fresh buying process?"
        if company.get("account_status") != "customer"
        else "Is there a renewal deadline, payroll cycle, or internal target pushing this timeline?"
    )
    return {
        "intro_connect": [
            f"I saw {company.get('name') or 'your team'} is in {company.get('industry') or 'this space'}; what made this worth exploring now?",
            "Before I show product, can I understand how your team runs scheduling, attendance, and payroll today?",
        ],
        "budget": [
            f"If we solve this properly - {interest} - would it be fair to pay a slight premium for the better outcome?",
            "What is the cost today when this process breaks or needs manual correction?",
        ],
        "authority": [
            "Who owns this problem day to day, and who signs off if the team likes the solution?",
            "Last time you bought or renewed a workforce tool, who needed to be in the room?",
        ],
        "need": [
            "What are the top three annoying parts of scheduling, attendance, timesheet, or payroll right now?",
            "Where do managers or HR still need to double-check manually?",
        ],
        "timeline": [
            timeline_prompt,
            "If this saves labour leakage or admin time, do you want to compound that from this month or wait until later?",
        ],
    }


def _public_research_company_input(context: dict[str, Any]) -> dict[str, Any]:
    company = context.get("company", {})
    return {
        "company_id": str(company.get("company_id") or ""),
        "name": str(company.get("name") or ""),
        "domain": str(company.get("domain") or ""),
        "country": str(company.get("country") or ""),
        "hubspot_scoped": True,
        "scope_source": SCOPE_SOURCE,
    }


def _public_research_for_game_plan_contexts(
    contexts: list[dict[str, Any]],
    include_public_research: bool,
    research_mode: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any] | None, list[str]]:
    if not include_public_research:
        return {}, None, []

    token = os.environ.get("TAVILY_API_KEY", "").strip()
    if not token:
        message = "public research blocked: Missing TAVILY_API_KEY."
        return {}, _public_research.research_cost_report([], message, research_mode), [message]

    companies = [_public_research_company_input(context) for context in contexts[: _public_research.MAX_RESEARCH_COMPANIES]]
    try:
        result = _public_research.research_public_company_signals(companies, token, research_mode)
    except _public_research.TavilyError as error:
        message = f"public research blocked: {str(error)}"
        return {}, _public_research.research_cost_report([], message, research_mode), [message]

    by_company = {
        str(item.get("input_company", {}).get("company_id") or ""): item
        for item in result.get("answer", [])
        if isinstance(item, dict)
    }
    return by_company, result.get("cost_report"), list(result.get("missing_evidence", []))


def _build_pre_demo_game_plan_row(
    context: dict[str, Any],
    public_research: dict[str, Any] | None = None,
    source_thread: dict[str, Any] | None = None,
) -> dict[str, Any]:
    company = context.get("company", {})
    return {
        "company_id": str(company.get("company_id") or ""),
        "name": str(company.get("name") or ""),
        "domain": str(company.get("domain") or ""),
        "country": str(company.get("country") or ""),
        "hubspot_scoped": True,
        "scope_source": SCOPE_SOURCE,
    }


def _public_research_for_game_plan_contexts(
    contexts: list[dict[str, Any]],
    include_public_research: bool,
    research_mode: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any] | None, list[str]]:
    if not include_public_research:
        return {}, None, []

    token = os.environ.get("TAVILY_API_KEY", "").strip()
    if not token:
        message = "public research blocked: Missing TAVILY_API_KEY."
        return {}, _public_research.research_cost_report([], message, research_mode), [message]

    companies = [_public_research_company_input(context) for context in contexts[: _public_research.MAX_RESEARCH_COMPANIES]]
    try:
        result = _public_research.research_public_company_signals(companies, token, research_mode)
    except _public_research.TavilyError as error:
        message = f"public research blocked: {str(error)}"
        return {}, _public_research.research_cost_report([], message, research_mode), [message]

    by_company = {
        str(item.get("input_company", {}).get("company_id") or ""): item
        for item in result.get("answer", [])
        if isinstance(item, dict)
    }
    return by_company, result.get("cost_report"), list(result.get("missing_evidence", []))


def _build_pre_demo_game_plan_row(
    context: dict[str, Any],
    public_research: dict[str, Any] | None = None,
    source_thread: dict[str, Any] | None = None,
) -> dict[str, Any]:
    company = context.get("company", {})
    contacts = context.get("contacts", [])
    coverage = context.get("coverage", {})
    missing = _pre_demo_missing_evidence(context)
    research_stalking_signal = {
        "known_hubspot_signals": _pre_demo_known_signals(context),
        "contact_coverage_source": coverage.get("sources") or _decision_maker_count_source({}),
        "calendar_scan_instruction": company.get("calendar_scan_instruction") or _calendar_scan_instruction(company),
        "manual_checks_needed": [
            "LinkedIn company/person profile manual check",
            "Instagram/Facebook/TikTok manual check where relevant",
            "news/search check for openings, awards, hiring, closures, or expansion",
        ],
        "rule": "Social/gated sources are manual-check only unless the user provides snippets.",
    }
    if public_research:
        game_inputs = public_research.get("game_plan_inputs") or {}
        research_stalking_signal["public_research_signals"] = game_inputs.get("public_signals", [])
        research_stalking_signal["public_source_evidence"] = game_inputs.get("source_evidence_refs", [])
        research_stalking_signal["public_outreach_angles"] = game_inputs.get("outreach_angles", [])
        research_stalking_signal["public_research_manual_checks"] = game_inputs.get("manual_checks_needed", [])
        recommended_next_tool = game_inputs.get("recommended_next_tool") or public_research.get("recommended_next_tool") or ""
        if recommended_next_tool:
            research_stalking_signal["recommended_next_tool"] = recommended_next_tool
        missing = sorted(set(missing + list(public_research.get("missing_evidence", []))))
    row = {
        "company_id": company.get("company_id"),
        "hubspot_scoped": True,
        "scope_source": SCOPE_SOURCE,
        "company_name": company.get("name"),
        "static_information": {
            "number_of_employees": company.get("headcount") or "number of employees needed",
            "industry": company.get("industry") or "industry needed",
            "account_status": company.get("account_status") or "account status needed",
            "account_status_source": company.get("account_status_source") or "customer/prospect source needed",
            "hubspot_owner": company.get("owner_name") or company.get("owner_email") or company.get("owner_id") or "owner needed",
            "hubspot_owner_email": company.get("owner_email") or "owner email needed",
            "how_did_they_hear_about_us": "lead source needed",
            "why_do_they_want_to_meet_with_us": "meeting reason needed",
            "who_will_i_be_meeting_with": _pre_demo_stakeholder_text(contacts),
            "current_tools": company.get("current_tools") or "current tool needed",
            "contract_end_date": _pre_demo_renewal_text(company),
        },
        "research_stalking_signal": research_stalking_signal,
        "hypothesized_interest_and_why": _pre_demo_hypothesized_interest(context),
        "alternatives_they_may_consider": _pre_demo_alternatives(context),
        "what_to_show_to_win": _pre_demo_show_to_win(context),
        "relevant_name_drops": _pre_demo_case_study_name_drops(context),
        "case_study_matches": _pre_demo_case_study_matches(context),
        "kns_knowledge_hooks": _pre_demo_kns_knowledge_hooks(context),
        "game_plan_a": _pre_demo_game_plan(context, "A"),
        "game_plan_b": _pre_demo_game_plan(context, "B"),
        "ic_bant_prompts": _pre_demo_ic_bant_prompts(context),
        "missing_evidence": missing,
        "confidence": "needs-check" if missing else "verified",
    }
    if source_thread:
        row["source_thread"] = source_thread
        row["writeback_source_evidence"] = {
            "source_type": source_thread.get("source_type"),
            "source_url": source_thread.get("url"),
            "provenance_policy": source_thread.get("provenance_policy"),
        }
    return row


def _scope_response(
    scope: dict[str, Any],
    countries: list[str],
    target_owner_id: str | None = None,
    target_owner_email: str = "",
) -> dict[str, Any]:
    response = {
        "caller_email": scope.get("email"),
        "scope_kind": scope.get("kind"),
        "countries": countries,
        "owner_id": scope.get("owner_id"),
    }
    if scope.get("requested_email") and scope.get("requested_email") != scope.get("email"):
        response["requested_caller_email"] = scope["requested_email"]
    if scope.get("hubspot_owner_email"):
        response["hubspot_owner_email"] = scope["hubspot_owner_email"]
    if scope.get("access_profile"):
        response["access_profile"] = scope["access_profile"]
    if scope.get("purpose"):
        response["purpose"] = scope["purpose"]
    if target_owner_id:
        response["target_owner_id"] = target_owner_id
    if target_owner_email:
        response["target_owner_email"] = target_owner_email
    return response


def _search_metadata(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "total": data.get("total"),
        "requested_limit": data.get("requested_limit"),
        "returned_count": data.get("returned_count", len(data.get("results", []))),
        "has_more": bool(data.get("has_more")),
        "truncated": bool(data.get("truncated")),
    }


def _coverage_caveat(data: dict[str, Any], base: str) -> str:
    if data.get("truncated"):
        total = data.get("total")
        returned = data.get("returned_count", len(data.get("results", [])))
        if total is not None:
            return f"{base} Only {returned} of {total} scoped accounts were returned; do not present counts as complete."
        return f"{base} Returned records are truncated; do not present counts as complete."
    return f"{base} Full scoped result set was returned."


def _safe_free_source_types(source_types: list[str] | None) -> list[str]:
    requested = source_types or list(FREE_SEARCH_SOURCE_TYPES)
    selected: list[str] = []
    for source_type in requested:
        normalized = str(source_type or "").strip().lower()
        if normalized in FREE_SEARCH_SOURCE_TYPES and normalized not in selected:
            selected.append(normalized)
    return selected


def _search_url(query: str) -> str:
    return "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)


def _job_board_query(company: dict[str, Any]) -> str:
    name = company.get("name", "")
    country = company.get("country", "")
    if country == "Singapore":
        return f'"{name}" hiring OR jobs site:mycareersfuture.gov.sg OR site:jobstreet.com.sg'
    if country == "Malaysia":
        return f'"{name}" hiring OR jobs site:myfuturejobs.gov.my OR site:jobstreet.com.my'
    if country == "Indonesia":
        return f'"{name}" hiring OR jobs site:jobstreet.co.id OR site:kalibrr.com'
    return f'"{name}" hiring OR jobs'


def _free_search_tasks_for_company(company: dict[str, Any], source_types: list[str]) -> list[dict[str, Any]]:
    name = company.get("name", "")
    country = company.get("country", "")
    domain = company.get("domain", "")
    missing = ", ".join(company.get("missing_fields", [])) or "public enrichment"
    task_templates = {
        "company_website": {
            "label": "Find official company website",
            "query": f'"{name}" official website {country}'.strip(),
            "reason": "Confirm official domain, outlet context, and public contact route.",
        },
        "company_careers": {
            "label": "Check official careers or hiring page",
            "query": f'"{name}" careers hiring jobs HR {country}'.strip(),
            "reason": "Hiring pages often expose HR routes and current manpower pain.",
        },
        "public_job_board": {
            "label": "Check public job boards",
            "query": _job_board_query(company),
            "reason": "Job listings can reveal active hiring, role pressure, and HR contacts.",
        },
        "news_article": {
            "label": "Check public news and announcements",
            "query": f'"{name}" news expansion hiring outlet launch {country}'.strip(),
            "reason": "News and announcements can reveal expansion, leadership, and timing context.",
        },
        "general_web": {
            "label": "Search for decision makers and HR context",
            "query": f'"{name}" "HR" OR founder OR owner OR "operations director" {country}'.strip(),
            "reason": "General search can surface public profiles, articles, and company context.",
        },
        "linkedin_manual": {
            "label": "Manual LinkedIn people search",
            "query": f'site:linkedin.com "{name}" HR founder owner director {country}'.strip(),
            "reason": "Manual-only check for likely decision makers; do not scrape LinkedIn.",
        },
        "google_maps_manual": {
            "label": "Manual Google Maps and reviews check",
            "query": f'"{name}" {country} Google Maps owner manager reviews'.strip(),
            "reason": "Manual-only check for outlet count, owner replies, and operating signals.",
        },
        "instagram_tiktok_manual": {
            "label": "Manual Instagram/TikTok social check",
            "query": f'"{name}" Instagram TikTok hiring opening outlet'.strip(),
            "reason": "Manual-only check for openings, hiring posts, and outreach angles.",
        },
        "facebook_manual": {
            "label": "Manual Facebook public page check",
            "query": f'"{name}" Facebook hiring outlet opening'.strip(),
            "reason": "Manual-only check for public posts, outlet activity, and local context.",
        },
        "review_site": {
            "label": "Check public employee/customer review context",
            "query": f'"{name}" Glassdoor reviews hiring manpower HR'.strip(),
            "reason": "Review context can suggest pain angles but must be verified by AE.",
        },
    }
    tasks = []
    for source_type in source_types:
        template = task_templates.get(source_type)
        if template is None:
            continue
        query = template["query"]
        tasks.append(
            {
                "source_type": source_type,
                "label": template["label"],
                "query": query,
                "url": _search_url(query),
                "reason": template["reason"],
                "gap_context": missing,
                "domain_hint": domain,
                "will_fetch_automatically": False,
                "requires_manual_review": True,
            }
        )
    return tasks


def _is_public_url(url: str) -> bool:
    return _public_research.is_public_url(url)


def _is_manual_only_host(url: str) -> bool:
    return _public_research._is_manual_only_host(url)


def _html_to_text(raw: str) -> str:
    return _public_research.html_to_text(raw)


def _fetch_public_evidence_text(source_type: str, url: str) -> tuple[str, str]:
    return _public_research.fetch_public_evidence_text(source_type, url)


def _raw_contacts_for_company(company_id: str) -> list[dict[str, Any]]:
    contact_ids = _association_ids("companies", company_id, "contacts", 100)
    return _batch_read("contacts", contact_ids, CONTACT_PROPERTIES)


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _safe_email(value: str) -> str:
    email = (value or "").strip().lower()
    if not email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return ""
    return email


def _dedup_append(values: list[str], value: Any, limit: int = 80) -> None:
    text = _short_text(str(value or ""), limit)
    if text and text not in values:
        values.append(text)


def _country_hint(value: str) -> str:
    normalized = (value or "").strip().lower()
    for country in SUPPORTED_COUNTRIES:
        if normalized == country.lower():
            return country
    text = f" {normalized} "
    aliases = {
        " sg ": "Singapore",
        " singapore ": "Singapore",
        " my ": "Malaysia",
        " malaysia ": "Malaysia",
        " id ": "Indonesia",
        " indonesia ": "Indonesia",
        " jakarta ": "Indonesia",
        " bali ": "Indonesia",
        " kuala lumpur ": "Malaysia",
    }
    for marker, country in aliases.items():
        if marker in text:
            return country
    return ""


def _as_hint_items(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _add_structured_photo_hints(hints: dict[str, list[str]], item: Any) -> None:
    if isinstance(item, dict):
        _dedup_append(hints["contact_names"], item.get("name") or item.get("person") or item.get("contact_name"))
        _dedup_append(hints["company_names"], item.get("company") or item.get("company_name") or item.get("account"))
        _dedup_append(hints["roles"], item.get("title") or item.get("jobtitle") or item.get("role"))
        _dedup_append(hints["event_names"], item.get("event") or item.get("event_name"))
        country = _country_hint(str(item.get("country") or item.get("location") or ""))
        if country:
            _dedup_append(hints["countries"], country)
        return
    _dedup_append(hints["contact_names"], item)


def _photo_matching_hints(
    context_text: str,
    vision_clues: dict[str, Any] | None,
    explicit_contact_name: str,
    explicit_company_name: str,
    event_name: str,
    country: str,
    luma_event_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hints: dict[str, list[str]] = {
        "contact_names": [],
        "company_names": [],
        "event_names": [],
        "roles": [],
        "countries": [],
        "text_evidence": [],
    }
    _dedup_append(hints["contact_names"], explicit_contact_name)
    _dedup_append(hints["company_names"], explicit_company_name)
    _dedup_append(hints["event_names"], event_name)
    selected_country = _country_hint(country)
    if selected_country:
        _dedup_append(hints["countries"], selected_country)
    event_context = luma_event_context if isinstance(luma_event_context, dict) else {}
    use_luma_hints = event_context.get("auto_event_tag_status") == "verified"
    if use_luma_hints and event_context.get("event_name"):
        _dedup_append(hints["event_names"], event_context.get("event_name"))
    if use_luma_hints and event_context.get("country"):
        _dedup_append(hints["countries"], event_context.get("country"))
    selected_event = event_context.get("selected_event") if isinstance(event_context.get("selected_event"), dict) else {}
    if use_luma_hints:
        for key in ("tags", "location_tags", "event_type_tags"):
            for item in _as_hint_items(selected_event.get(key)):
                _dedup_append(hints["text_evidence"], item, 120)

    context = _short_text(context_text or "", 1000)
    if context:
        _dedup_append(hints["text_evidence"], context, 500)
        country_from_context = _country_hint(context)
        if country_from_context:
            _dedup_append(hints["countries"], country_from_context)
        person_company = re.search(
            r"(?:this is|meet|met|with)\s+([A-Za-z][A-Za-z'.-]*(?:\s+[A-Za-z][A-Za-z'.-]*){0,3})\s+(?:from|at)\s+([A-Za-z0-9][A-Za-z0-9&'. -]{1,70})",
            context,
            flags=re.IGNORECASE,
        )
        if person_company:
            _dedup_append(hints["contact_names"], person_company.group(1).strip())
            _dedup_append(hints["company_names"], person_company.group(2).strip(" .,:;"))

    clues = vision_clues if isinstance(vision_clues, dict) else {}
    for key in ("people", "persons", "faces", "badges"):
        for item in _as_hint_items(clues.get(key)):
            _add_structured_photo_hints(hints, item)
    for key in ("names", "person_names", "contact_names", "badge_names"):
        for item in _as_hint_items(clues.get(key)):
            _dedup_append(hints["contact_names"], item)
    for key in ("companies", "company_names", "accounts", "brands", "signage"):
        for item in _as_hint_items(clues.get(key)):
            if isinstance(item, dict):
                _add_structured_photo_hints(hints, item)
            else:
                _dedup_append(hints["company_names"], item)
    for key in ("roles", "titles", "job_titles"):
        for item in _as_hint_items(clues.get(key)):
            _dedup_append(hints["roles"], item)
    for key in ("event", "event_name", "events"):
        for item in _as_hint_items(clues.get(key)):
            _dedup_append(hints["event_names"], item)
    for key in ("country", "countries", "location", "locations"):
        for item in _as_hint_items(clues.get(key)):
            selected = _country_hint(str(item))
            if selected:
                _dedup_append(hints["countries"], selected)
    ocr_text = _short_text(str(clues.get("ocr_text") or clues.get("text") or ""), 1000)
    if ocr_text:
        _dedup_append(hints["text_evidence"], ocr_text, 500)
        selected = _country_hint(ocr_text)
        if selected:
            _dedup_append(hints["countries"], selected)

    return {key: value for key, value in hints.items() if value}


def _photo_source_type(value: str) -> str:
    source = (value or "").strip().lower()
    return source if source in PHOTO_SOURCE_TYPES else ""


def _metadata_value(metadata: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = metadata.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _parse_drive_photo_name(name: str) -> dict[str, str]:
    match = re.match(
        r"^(?P<source_timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)-(?P<slack_user_id>[UW][A-Z0-9]+)-(?P<original_filename>.+)$",
        name or "",
    )
    if not match:
        return {"source_timestamp": "", "slack_user_id": "", "original_filename": name or ""}
    return match.groupdict()


def _is_photo_file(metadata: dict[str, Any]) -> bool:
    mime_type = _metadata_value(metadata, "mimeType", "mime_type").lower()
    name = _metadata_value(metadata, "name", "filename", "title").lower()
    return mime_type.startswith("image/") or name.endswith(PHOTO_IMAGE_EXTENSIONS)


def _photo_source_pointer(photo_source: str, metadata: dict[str, Any]) -> dict[str, Any]:
    source = _photo_source_type(photo_source)
    if source == "drive":
        name = _metadata_value(metadata, "name", "filename", "title")
        parsed = _parse_drive_photo_name(name)
        return {
            "source_type": "drive",
            "drive_folder_id": _metadata_value(metadata, "folder_id", "folderId") or DRIVE_ALL_RANDOM_FOLDER_ID,
            "drive_file_id": _metadata_value(metadata, "id", "file_id", "fileId"),
            "drive_link": _metadata_value(metadata, "webViewLink", "web_view_link", "link"),
            "filename": name,
            "mime_type": _metadata_value(metadata, "mimeType", "mime_type"),
            "md5_checksum": _metadata_value(metadata, "md5Checksum", "md5_checksum"),
            "created_time": _metadata_value(metadata, "createdTime", "created_time"),
            "modified_time": _metadata_value(metadata, "modifiedTime", "modified_time"),
            "slack_uploader_name": _metadata_value(metadata, "slack_uploader_name", "uploader_name", "slackUploaderName"),
            **parsed,
        }
    if source == "slack":
        return {
            "source_type": "slack",
            "channel_id": _metadata_value(metadata, "channel_id", "channel", "channelId"),
            "message_ts": _metadata_value(metadata, "message_ts", "ts", "timestamp"),
            "file_id": _metadata_value(metadata, "file_id", "fileId", "id"),
            "permalink": _metadata_value(metadata, "permalink", "url_private", "url"),
            "filename": _metadata_value(metadata, "name", "filename", "title"),
            "uploader_user_id": _metadata_value(metadata, "user", "user_id", "uploader_user_id"),
            "slack_uploader_name": _metadata_value(metadata, "slack_uploader_name", "uploader_name", "slackUploaderName"),
            "mime_type": _metadata_value(metadata, "mimetype", "mimeType", "mime_type"),
            "created_time": _metadata_value(metadata, "created", "created_time", "timestamp"),
        }
    return {"source_type": source or "unknown"}


def _photo_key(source_pointer: dict[str, Any]) -> str:
    source = source_pointer.get("source_type")
    if source == "drive" and source_pointer.get("drive_file_id"):
        return f"drive:{source_pointer['drive_file_id']}"
    if source == "slack":
        parts = [source_pointer.get("channel_id"), source_pointer.get("message_ts"), source_pointer.get("file_id")]
        if all(parts):
            return "slack:" + ":".join(str(part) for part in parts)
    checksum = source_pointer.get("md5_checksum")
    if checksum:
        return f"hash:{checksum}"
    payload = json.dumps(source_pointer, sort_keys=True)
    return "photo:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _photo_custom_object_plan(
    photo_key: str,
    source_pointer: dict[str, Any],
    event_name: str = "",
    context_text: str = "",
    luma_event_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event_context = luma_event_context if isinstance(luma_event_context, dict) else {}
    selected_event = event_context.get("selected_event") if isinstance(event_context.get("selected_event"), dict) else {}
    verified_luma_event_name = event_context.get("event_name") if event_context.get("auto_event_tag_status") == "verified" else ""
    event_label = _short_text(event_name or verified_luma_event_name or "unclassified event photo", 120)
    return {
        "objects": PHOTO_CUSTOM_OBJECT_TYPES,
        "nurture_event": {
            "event_name": event_label,
            "source_context": _short_text(context_text or "", 240),
            "luma_event_id": selected_event.get("event_id") or "",
            "luma_event_url": selected_event.get("url") or "",
            "event_date_match_status": event_context.get("auto_event_tag_status") or "not_checked",
            "event_date_match_source": event_context.get("source") or "",
        },
        "nurture_event_photo": {
            "photo_key": photo_key,
            "source_pointer": source_pointer,
            "raw_image_copy": False,
        },
        "nurture_person_appearance": "created only after a human confirms the HubSpot contact/company match",
    }


def _photo_label(source_pointer: dict[str, Any]) -> str:
    return _short_text(
        str(
            source_pointer.get("original_filename")
            or source_pointer.get("filename")
            or source_pointer.get("drive_file_id")
            or source_pointer.get("file_id")
            or "this photo"
        ),
        120,
    )


def _photo_uploader_identity(source_pointer: dict[str, Any]) -> tuple[str, str]:
    user_id = str(source_pointer.get("slack_user_id") or source_pointer.get("uploader_user_id") or "").strip()
    name = str(source_pointer.get("slack_uploader_name") or source_pointer.get("uploader_name") or "").strip()
    return user_id, name


def _photo_confirmation_request(
    source_pointer: dict[str, Any],
    missing_clue_prompt: str = "",
    has_candidates: bool = False,
    luma_event_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    user_id, uploader_name = _photo_uploader_identity(source_pointer)
    label = _photo_label(source_pointer)
    recipient = f"<@{user_id}>" if user_id else (uploader_name or "the uploader")
    event_context = luma_event_context if isinstance(luma_event_context, dict) else {}
    event_suffix = (
        f" for {event_context.get('event_name')}"
        if event_context.get("event_name") and event_context.get("auto_event_tag_status") == "verified"
        else ""
    )
    if has_candidates:
        prompt = (
            f"{recipient} can you confirm the HubSpot contact/company for {label}{event_suffix}? "
            "Reply `confirm <contact> from <company>` or correct it."
        )
    else:
        clue = (missing_clue_prompt or "contact + company").strip()
        prompt = (
            f"{recipient} who is in {label}{event_suffix}? "
            f"Reply with {clue}, e.g. `Jane from Shake Shack`."
        )
    return {
        "required": True,
        "confirmation_owner": "slack_uploader" if user_id or uploader_name else "unknown_uploader",
        "delivery": "dm_or_thread_mention_uploader",
        "slack_user_id": user_id,
        "slack_uploader_name": uploader_name,
        "photo_label": label,
        "missing_clue_prompt": missing_clue_prompt,
        "luma_event_context": event_context,
        "prompt": prompt,
        "writes_blocked_until_confirmation": True,
    }


def _photo_confirmation_batches(photos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    batches: dict[str, dict[str, Any]] = {}
    for photo in photos:
        request = photo.get("confirmation_request") if isinstance(photo.get("confirmation_request"), dict) else {}
        user_id = str(request.get("slack_user_id") or "").strip()
        uploader_name = str(request.get("slack_uploader_name") or "").strip()
        key = user_id or uploader_name or "unknown_uploader"
        batch = batches.setdefault(
            key,
            {
                "confirmation_owner": request.get("confirmation_owner") or "unknown_uploader",
                "delivery": "dm_or_thread_mention_uploader",
                "slack_user_id": user_id,
                "slack_uploader_name": uploader_name,
                "photos": [],
                "writes_blocked_until_confirmation": True,
            },
        )
        batch["photos"].append(
            {
                "photo_key": photo.get("photo_key") or "",
                "photo_label": request.get("photo_label") or _photo_label(photo.get("source_pointer", {})),
                "source_timestamp": photo.get("source_timestamp") or "",
                "event_name": request.get("luma_event_context", {}).get("event_name")
                if isinstance(request.get("luma_event_context"), dict)
                else "",
            }
        )

    for batch in batches.values():
        recipient = f"<@{batch['slack_user_id']}>" if batch.get("slack_user_id") else (batch.get("slack_uploader_name") or "the uploader")
        count = len(batch["photos"])
        batch["prompt"] = (
            f"{recipient} can help identify these {count} photo(s)? "
            "Reply per filename with contact + company, e.g. `IMG_6194.jpg - Jane from Shake Shack`."
        )
    return list(batches.values())


def _luma_event_timezone(event: dict[str, Any]) -> timezone:
    text = str(event.get("timezone") or " ".join(str(tag) for tag in event.get("tags", []) if tag) or "").lower()
    if "jakarta" in text or "jkt" in text:
        return timezone(timedelta(hours=7))
    if "singapore" in text or "kuala_lumpur" in text or "kuala lumpur" in text or "bali" in text:
        return SINGAPORE_TIMEZONE
    return SINGAPORE_TIMEZONE


def _luma_event_country(event: dict[str, Any]) -> str:
    for country in event.get("country_tags", []) if isinstance(event.get("country_tags"), list) else []:
        selected = _country_hint(str(country))
        if selected:
            return selected
    for location in event.get("location_tags", []) if isinstance(event.get("location_tags"), list) else []:
        mapped = LOCATION_COUNTRY_MAP.get(str(location))
        if mapped:
            return mapped
    text_parts = [str(event.get("name") or ""), str(event.get("timezone") or "")]
    for key in ("tags", "event_type_tags"):
        if isinstance(event.get(key), list):
            text_parts.extend(str(item) for item in event[key])
    return _country_hint(" ".join(text_parts))


def _photo_source_datetime(source_pointer: dict[str, Any]) -> datetime | None:
    for key in ("source_timestamp", "created_time", "modified_time"):
        parsed = _datetime_value(str(source_pointer.get(key) or ""))
        if parsed:
            return parsed
    return None


def _event_date_delta_days(photo_dt: datetime, event: dict[str, Any]) -> int | None:
    start_dt = _datetime_value(str(event.get("start_at") or ""))
    if not start_dt:
        return None
    end_dt = _datetime_value(str(event.get("end_at") or "")) or start_dt
    event_timezone = _luma_event_timezone(event)
    photo_date = photo_dt.astimezone(event_timezone).date()
    start_date = start_dt.astimezone(event_timezone).date()
    end_date = end_dt.astimezone(event_timezone).date()
    if start_date <= photo_date <= end_date:
        return 0
    return min(abs((photo_date - start_date).days), abs((photo_date - end_date).days))


def _photo_luma_event_candidates(source_pointer: dict[str, Any], luma_events: Any, limit: int = PHOTO_LUMA_EVENT_CANDIDATE_LIMIT) -> list[dict[str, Any]]:
    if not isinstance(luma_events, list):
        return []
    photo_dt = _photo_source_datetime(source_pointer)
    if not photo_dt:
        return []

    candidates: list[dict[str, Any]] = []
    for event in luma_events:
        if not isinstance(event, dict):
            continue
        delta_days = _event_date_delta_days(photo_dt, event)
        if delta_days is None or delta_days > 1:
            continue
        score = 92 if delta_days == 0 else 70
        evidence = ["photo local date matches Luma event date" if delta_days == 0 else "photo local date is within one day of Luma event"]
        selected = {
            "event_id": str(event.get("event_id") or event.get("id") or "").strip(),
            "name": _short_text(str(event.get("name") or event.get("title") or ""), 160),
            "start_at": str(event.get("start_at") or ""),
            "end_at": str(event.get("end_at") or ""),
            "timezone": str(event.get("timezone") or ""),
            "url": str(event.get("url") or ""),
            "tags": event.get("tags") if isinstance(event.get("tags"), list) else [],
            "location_tags": event.get("location_tags") if isinstance(event.get("location_tags"), list) else [],
            "country_tags": event.get("country_tags") if isinstance(event.get("country_tags"), list) else [],
            "event_type_tags": event.get("event_type_tags") if isinstance(event.get("event_type_tags"), list) else [],
            "country": _luma_event_country(event),
            "confidence_score": score,
            "confidence_band": _confidence_band(score),
            "date_delta_days": delta_days,
            "evidence": evidence,
            "source": "luma_event_date",
        }
        if selected["name"]:
            candidates.append(selected)

    return sorted(candidates, key=lambda item: (item["confidence_score"], item.get("start_at", "")), reverse=True)[:limit]


def _photo_luma_event_context(source_pointer: dict[str, Any], luma_events: Any, auto_tag: bool = False) -> dict[str, Any]:
    candidates = _photo_luma_event_candidates(source_pointer, luma_events)
    if not candidates:
        return {
            "source": "luma_event_date",
            "auto_event_tag_status": "not_found",
            "candidates": [],
        }
    top = candidates[0]
    close = [candidate for candidate in candidates if top["confidence_score"] - candidate["confidence_score"] <= 5]
    status = "verified" if auto_tag and top["confidence_score"] >= 90 and len(close) == 1 else "needs-check"
    return {
        "source": "luma_event_date",
        "auto_event_tag_status": status,
        "auto_tag_enabled": bool(auto_tag),
        "event_name": top.get("name") or "",
        "country": top.get("country") or "",
        "selected_event": top,
        "candidates": candidates,
        "requires_person_confirmation": True,
        "caveat": "Luma date match can tag the event context only; HubSpot contact association still requires uploader confirmation.",
    }


def _photo_scope_countries(scope: dict[str, Any], hints: dict[str, Any]) -> list[str]:
    hinted = [_country_hint(country) for country in hints.get("countries", [])]
    hinted = [country for country in hinted if country]
    selected = _safe_countries(hinted, scope.get("countries", ())) if hinted else list(scope.get("countries", ()))
    return selected


def _company_search_by_text(query: str, scope: dict[str, Any], countries: list[str], limit: int) -> dict[str, Any]:
    tokens = [token for token in _normalize_name(query).split() if len(token) > 1]
    filters = _target_filters(countries, scope.get("owner_id") if scope.get("kind") == "ae" else None)
    if tokens:
        filters.append({"propertyName": "name", "operator": "CONTAINS_TOKEN", "value": tokens[0]})
    return _company_search(filters, limit)


def _contact_search_by_text(query: str, limit: int) -> dict[str, Any]:
    tokens = [token for token in _normalize_name(query).split() if len(token) > 1]
    if not tokens:
        return {"results": [], "total": 0, "requested_limit": limit, "returned_count": 0, "has_more": False, "truncated": False}
    filter_groups = []
    if len(tokens) >= 2:
        filter_groups.append(
            {
                "filters": [
                    {"propertyName": "firstname", "operator": "CONTAINS_TOKEN", "value": tokens[0]},
                    {"propertyName": "lastname", "operator": "CONTAINS_TOKEN", "value": tokens[-1]},
                ]
            }
        )
        filter_groups.append(
            {
                "filters": [
                    {"propertyName": "firstname", "operator": "CONTAINS_TOKEN", "value": tokens[-1]},
                    {"propertyName": "lastname", "operator": "CONTAINS_TOKEN", "value": tokens[0]},
                ]
            }
        )
    for token in tokens[:3]:
        filter_groups.append({"filters": [{"propertyName": "firstname", "operator": "CONTAINS_TOKEN", "value": token}]})
        filter_groups.append({"filters": [{"propertyName": "lastname", "operator": "CONTAINS_TOKEN", "value": token}]})
    requested_limit = _bounded_int(limit, default=PHOTO_MATCH_LIMIT, maximum=50)
    body = {
        "filterGroups": filter_groups[:8],
        "properties": CONTACT_PROPERTIES,
        "limit": requested_limit,
    }
    data = _post("/crm/v3/objects/contacts/search", body)
    return {
        "results": data.get("results", []),
        "total": data.get("total"),
        "requested_limit": requested_limit,
        "returned_count": len(data.get("results", [])),
        "has_more": bool(data.get("paging", {}).get("next", {}).get("after")),
        "truncated": bool(data.get("paging", {}).get("next", {}).get("after")),
    }


def _photo_company_candidates(scope: dict[str, Any], hints: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    countries = _photo_scope_countries(scope, hints)
    if not countries:
        return []
    by_id: dict[str, dict[str, Any]] = {}
    queries = hints.get("company_names", [])[:5]
    for query in queries:
        data = _company_search_by_text(query, scope, countries, limit)
        for company in data.get("results", []):
            if not _has_company_access(company, scope):
                continue
            summary = _summarize_company(company)
            company_id = str(summary.get("company_id") or "")
            if not company_id:
                continue
            score = 55
            normalized_query = _normalize_name(query)
            normalized_name = _normalize_name(summary.get("name", ""))
            evidence = ["HubSpot scoped target account"]
            if normalized_query and normalized_query == normalized_name:
                score += 25
                evidence.append("company name exact match")
            elif normalized_query and normalized_query in normalized_name:
                score += 15
                evidence.append("company name contains provided hint")
            if summary.get("country") in hints.get("countries", []):
                score += 5
                evidence.append("country hint matches")
            existing = by_id.get(company_id)
            candidate = {
                "company_id": company_id,
                "name": summary.get("name"),
                "country": summary.get("country"),
                "owner_id": summary.get("owner_id"),
                "confidence_score": min(score, 100),
                "evidence": evidence,
                "hubspot_scoped": True,
                "scope_source": SCOPE_SOURCE,
            }
            if not existing or candidate["confidence_score"] > existing["confidence_score"]:
                by_id[company_id] = candidate
    return sorted(by_id.values(), key=lambda item: item["confidence_score"], reverse=True)[:limit]


def _scoped_contact_companies(contact_id: str, scope: dict[str, Any]) -> list[dict[str, Any]]:
    company_ids = _association_ids("contacts", contact_id, "companies", 10)
    companies = _batch_read("companies", company_ids, COMPANY_PROPERTIES)
    summaries = []
    for company in companies:
        if _has_company_access(company, scope):
            summaries.append(_summarize_company(company))
    return summaries


def _photo_contact_score(
    contact: dict[str, Any],
    scoped_companies: list[dict[str, Any]],
    hints: dict[str, Any],
    company_candidates: list[dict[str, Any]],
) -> tuple[int, list[str]]:
    props = contact.get("properties", {})
    full_name = _contact_full_name(contact)
    normalized_full_name = _normalize_name(full_name)
    score = 20
    evidence = ["HubSpot contact associated to scoped target account"]
    for name in hints.get("contact_names", []):
        normalized_hint = _normalize_name(name)
        if normalized_hint and normalized_hint == normalized_full_name:
            score += 45
            evidence.append("contact name exact match")
            break
        if normalized_hint and normalized_hint in normalized_full_name:
            score += 30
            evidence.append("contact name partial match")
            break
    candidate_company_ids = {str(company.get("company_id") or "") for company in company_candidates}
    scoped_company_ids = {str(company.get("company_id") or "") for company in scoped_companies}
    if candidate_company_ids and scoped_company_ids & candidate_company_ids:
        score += 30
        evidence.append("associated company matches company hint")
    role_text = _normalize_name(" ".join([props.get("jobtitle") or "", props.get("job_role") or "", props.get("hs_buying_role") or ""]))
    for role in hints.get("roles", []):
        normalized_role = _normalize_name(role)
        if normalized_role and normalized_role in role_text:
            score += 10
            evidence.append("role/title clue matches")
            break
    hinted_countries = set(hints.get("countries", []))
    if hinted_countries and any(company.get("country") in hinted_countries for company in scoped_companies):
        score += 5
        evidence.append("associated company country matches")
    return min(score, 100), evidence


def _confidence_band(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def _photo_contact_candidates(
    scope: dict[str, Any],
    hints: dict[str, Any],
    company_candidates: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for name in hints.get("contact_names", [])[:5]:
        data = _contact_search_by_text(name, limit * 6)
        for contact in data.get("results", []):
            contact_id = str(contact.get("id") or "")
            if not contact_id:
                continue
            scoped_companies = _scoped_contact_companies(contact_id, scope)
            if not scoped_companies:
                continue
            score, evidence = _photo_contact_score(contact, scoped_companies, hints, company_candidates)
            safe = _safe_contact(contact)
            candidate = {
                "contact_id": contact_id,
                "display_name": safe.get("display_name"),
                "persona": safe.get("persona"),
                "buying_role": safe.get("buying_role"),
                "associated_companies": [
                    {
                        "company_id": company.get("company_id"),
                        "name": company.get("name"),
                        "country": company.get("country"),
                        "owner_id": company.get("owner_id"),
                    }
                    for company in scoped_companies
                ],
                "confidence_score": score,
                "confidence_band": _confidence_band(score),
                "evidence": evidence,
                "requires_human_confirmation": True,
                "hubspot_scoped": True,
                "scope_source": SCOPE_SOURCE,
            }
            existing = by_id.get(contact_id)
            if not existing or candidate["confidence_score"] > existing["confidence_score"]:
                by_id[contact_id] = candidate
    return sorted(by_id.values(), key=lambda item: item["confidence_score"], reverse=True)[:limit]


def _photo_missing_clue_prompt(hints: dict[str, Any], contact_candidates: list[dict[str, Any]], company_candidates: list[dict[str, Any]]) -> str:
    if contact_candidates:
        top_score = contact_candidates[0].get("confidence_score", 0)
        close = [candidate for candidate in contact_candidates if top_score - candidate.get("confidence_score", 0) <= 10]
        if len(close) > 1:
            return "Which contact should I use?"
        return "Reply confirm with this contact/company before I prepare the HubSpot note and WhatsApp follow-up task."
    if company_candidates:
        return f"Which person at {company_candidates[0].get('name')} should I match?"
    if not hints.get("company_names"):
        return "company name?"
    if not hints.get("contact_names"):
        return "contact name?"
    return "which contact/company?"


def _next_business_day_10_sg(now: datetime | None = None) -> str:
    local = (now or datetime.now(timezone.utc)).astimezone(SINGAPORE_TIMEZONE)
    target_date = local.date() + timedelta(days=1)
    while target_date.weekday() >= 5:
        target_date += timedelta(days=1)
    return datetime.combine(target_date, datetime_time(10, 0), tzinfo=SINGAPORE_TIMEZONE).isoformat()


def _selected_match_company_id(selected_match: dict[str, Any]) -> str:
    company_id = str(selected_match.get("company_id") or "").strip()
    if company_id:
        return company_id
    companies = selected_match.get("associated_companies")
    if isinstance(companies, list) and companies:
        return str(companies[0].get("company_id") or "").strip()
    company = selected_match.get("company") if isinstance(selected_match.get("company"), dict) else {}
    return str(company.get("company_id") or company.get("id") or "").strip()


def _selected_match_company_name(selected_match: dict[str, Any], company: dict[str, Any]) -> str:
    props = company.get("properties", {})
    if selected_match.get("company_name"):
        return str(selected_match.get("company_name"))
    companies = selected_match.get("associated_companies")
    if isinstance(companies, list) and companies and companies[0].get("name"):
        return str(companies[0].get("name"))
    return str(props.get("name") or "the account")


def _photo_followup_draft(contact_name: str, company_name: str, event_name: str) -> str:
    first = (contact_name or "").split(" ")[0] or "there"
    event_text = f" at {event_name}" if event_name else ""
    return (
        f"Hi {first}, good meeting you{event_text}. "
        f"Thought to follow up on how {company_name} is handling workforce ops. "
        "Would it be useful if I shared a few quick ideas?"
    )


def _candidate_from_evidence(item: dict[str, Any], source_type: str, source_url: str) -> dict[str, Any] | None:
    candidate = item.get("contact_candidate") if isinstance(item.get("contact_candidate"), dict) else item
    name = str(candidate.get("name") or candidate.get("contact_name") or candidate.get("inferred_name") or "").strip()
    title = str(
        candidate.get("jobtitle")
        or candidate.get("job_title")
        or candidate.get("inferred_title")
        or candidate.get("persona")
        or candidate.get("title")
        or ""
    ).strip()
    email = _safe_email(str(candidate.get("email") or ""))
    if not (name or email):
        return None
    result = {
        "display_name": name,
        "persona": title,
        "email": email,
        "source_type": source_type,
        "source_url": source_url,
        "is_decision_maker": _role_is_decision_maker(title),
        "confidence": "needs-check",
    }
    for key in ("confidence_band", "signal_count", "quality_signals", "supporting_signals", "quality_warnings", "quality_gate"):
        if key in candidate:
            result[key] = candidate[key]
    if candidate.get("phone") or candidate.get("phone_number"):
        result["omitted_fields"] = ["phone"]
    return result


def _public_evidence_source_type(source_type: str, source_url: str) -> str:
    normalized = (source_type or "").strip().lower()
    if normalized in FREE_SEARCH_SOURCE_TYPES:
        return normalized
    if normalized == "linkedin_manual_check":
        return "linkedin_manual"
    if normalized == "company_public_profile":
        return "company_website"
    if normalized == "social_or_gated_manual_check":
        host = urllib.parse.urlparse(source_url).netloc.lower()
        if "facebook.com" in host:
            return "facebook_manual"
        if "google." in host:
            return "google_maps_manual"
        return "instagram_tiktok_manual"
    return "general_web"


def _contact_full_name(contact: dict[str, Any]) -> str:
    props = contact.get("properties", {})
    return " ".join(part for part in [props.get("firstname") or "", props.get("lastname") or ""] if part).strip()


def _dedupe_candidate(candidate: dict[str, Any], existing_contacts: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_email = _safe_email(candidate.get("email", ""))
    candidate_name = _normalize_name(candidate.get("display_name", ""))
    for contact in existing_contacts:
        props = contact.get("properties", {})
        existing_email = _safe_email(props.get("email") or "")
        if candidate_email and existing_email and candidate_email == existing_email:
            return {
                "status": "likely_existing_contact",
                "matched_contact_id": contact.get("id"),
                "reason": "email exact match",
            }
    for contact in existing_contacts:
        existing_name = _normalize_name(_contact_full_name(contact))
        if candidate_name and existing_name and candidate_name == existing_name:
            return {
                "status": "possible_existing_contact",
                "matched_contact_id": contact.get("id"),
                "reason": "name exact match; review before write-back",
            }
    return {"status": "new_candidate", "matched_contact_id": "", "reason": "no HubSpot contact match found"}


def _short_text(value: str, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    return text[:limit].rstrip()


def _extract_company_signals(item: dict[str, Any], source_type: str, source_url: str, fetched_text: str) -> list[dict[str, Any]]:
    return _public_research.extract_company_signals(item, source_type, source_url, fetched_text)


def _outreach_angles(signals: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> list[str]:
    return _public_research.outreach_angles(signals, candidates)


def _policy_classification(email: str, policy: dict[str, Any]) -> str:
    requested = _normalize_email(email)
    normalized = _canonical_policy_email(requested, policy)
    if requested in policy["disabled"] or normalized in policy["disabled"]:
        return "disabled"
    if normalized in policy["admins"]:
        return "admin"
    if normalized in policy["managers"]:
        return "manager"
    if normalized in policy.get("event_operators", {}):
        return "event_operator"
    if normalized in policy.get("partnerships_viewers", {}):
        return "partnerships_viewer"
    if normalized in policy["sales_reps"]:
        return "sales_rep"
    for rep in policy["sales_reps"].values():
        if normalized == rep.get("hubspot_owner_email"):
            return "sales_rep_owner_email"
    return "unclassified"


def _owner_name(owner: dict[str, Any]) -> str:
    first = str(owner.get("firstName") or "").strip()
    last = str(owner.get("lastName") or "").strip()
    full = " ".join(part for part in [first, last] if part).strip()
    return full or str(owner.get("email") or "").strip()


def _target_counts_for_owner(owner_id: str, countries: list[str]) -> dict[str, Any]:
    by_country: dict[str, int | None] = {}
    total = 0
    for country in countries:
        data = _company_search(_target_filters([country], owner_id), limit=1)
        count = data.get("total")
        by_country[country] = count
        if isinstance(count, int):
            total += count
    return {"total": total, "by_country": by_country}


def _read_crm_object(object_type: str, object_id: str, properties: list[str]) -> dict[str, Any] | None:
    if not object_id:
        return None
    try:
        return _get(f"/crm/v3/objects/{object_type}/{object_id}", {"properties": ",".join(properties)})
    except HubSpotError as error:
        if "404" in str(error):
            return None
        raise


def _read_marketing_contact(contact_id: str) -> dict[str, Any] | None:
    return _read_crm_object("contacts", str(contact_id), MARKETING_CONTACT_PROPERTIES)


def _read_marketing_company(company_id: str) -> dict[str, Any] | None:
    return _read_crm_object("companies", str(company_id), MARKETING_COMPANY_PROPERTIES)


def _marketing_email_domain(value: str) -> str:
    email = _safe_email(value)
    return email.split("@", 1)[1] if "@" in email else ""


def _contact_display_name(contact: dict[str, Any] | None) -> str:
    if not contact:
        return ""
    props = contact.get("properties", {})
    first = str(props.get("firstname") or "").strip()
    last = str(props.get("lastname") or "").strip()
    full = " ".join(part for part in [first, last] if part).strip()
    return full or str(props.get("jobtitle") or "").strip()


def _safe_marketing_contact_summary(contact: dict[str, Any] | None) -> dict[str, Any]:
    if not contact:
        return {}
    props = contact.get("properties", {})
    return {
        "contact_id": str(contact.get("id") or ""),
        "display_name": _contact_display_name(contact),
        "jobtitle": props.get("jobtitle") or "",
        "owner_id": props.get("hubspot_owner_id") or "",
        "email_domain": _marketing_email_domain(str(props.get("email") or "")),
        "lifecycle_stage": props.get("lifecyclestage") or "",
        "created_at": props.get("createdate") or "",
        "last_modified_at": props.get("lastmodifieddate") or "",
    }


def _safe_marketing_company_summary(company: dict[str, Any] | None) -> dict[str, Any]:
    if not company:
        return {}
    props = company.get("properties", {})
    account_status = _account_status_from_props(props)
    return {
        "company_id": str(company.get("id") or ""),
        "hubspot_scoped": True,
        "scope_source": SCOPE_SOURCE,
        "name": props.get("name") or "",
        "domain": props.get("domain") or "",
        "country": props.get("company_country") or "",
        "owner_id": props.get("hubspot_owner_id") or "",
        "target_account": str(props.get("hs_is_target_account") or "").lower() == "true",
        "campaign": props.get("campaign") or "",
        **account_status,
    }


def _has_marketing_company_access(company: dict[str, Any], scope: dict[str, Any]) -> bool:
    props = company.get("properties", {})
    country = props.get("company_country") or ""
    owner_id = str(props.get("hubspot_owner_id") or "")
    if scope["kind"] == "admin":
        return True
    if scope["kind"] == "manager":
        return not country or country in scope.get("countries", ())
    if scope["kind"] == "ae":
        return bool(country and country in scope.get("countries", ()) and owner_id and owner_id == str(scope.get("owner_id") or ""))
    return False


def _marketing_companies_for_contact(contact_id: str) -> list[dict[str, Any]]:
    company_ids = _association_ids("contacts", str(contact_id), "companies", 20)
    return _batch_read("companies", company_ids, MARKETING_COMPANY_PROPERTIES)


def _marketing_access_context_for_contact(contact_id: str, scope: dict[str, Any]) -> dict[str, Any]:
    contact = _read_marketing_contact(str(contact_id))
    companies = _marketing_companies_for_contact(str(contact_id)) if contact else []
    accessible_companies = [company for company in companies if _has_marketing_company_access(company, scope)]
    if scope["kind"] == "admin":
        allowed = True
    elif accessible_companies:
        allowed = True
    elif scope["kind"] == "manager" and contact and not companies:
        allowed = True
    else:
        allowed = False
    return {
        "allowed": allowed,
        "contact": contact,
        "companies": accessible_companies if accessible_companies else ([] if scope["kind"] != "admin" else companies),
        "scope_status": "company_scoped" if accessible_companies else "unresolved_company_scope",
    }


def _marketing_access_context_for_thread(thread: dict[str, Any], scope: dict[str, Any]) -> dict[str, Any]:
    contact_id = str(thread.get("associatedContactId") or "")
    context = _marketing_access_context_for_contact(contact_id, scope) if contact_id else {
        "allowed": scope["kind"] in {"admin", "manager"},
        "contact": None,
        "companies": [],
        "scope_status": "unresolved_company_scope",
    }
    if contact_id and not context.get("contact") and not context.get("companies") and scope["kind"] in {"admin", "manager"}:
        context["allowed"] = True
        context["scope_status"] = "unresolved_company_scope"
    context["thread"] = thread
    context["associated_contact_id"] = contact_id
    context["associated_ticket_id"] = str(thread.get("threadAssociations", {}).get("associatedTicketId") or "")
    return context


def _default_latest_message_after() -> str:
    start = datetime.now(timezone.utc) - timedelta(days=30)
    return start.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _conversation_threads(params: dict[str, str], limit: int) -> dict[str, Any]:
    requested_limit = _bounded_int(limit, default=20, maximum=INBOUND_THREAD_RETURN_LIMIT)
    results: list[dict[str, Any]] = []
    next_after = params.get("after", "")
    while len(results) < requested_limit:
        page_params = {key: value for key, value in params.items() if value != ""}
        page_params["limit"] = str(min(100, requested_limit - len(results)))
        if next_after:
            page_params["after"] = str(next_after)
        page = _get("/conversations/v3/conversations/threads", page_params)
        page_results = page.get("results", [])
        results.extend(page_results)
        next_after = str(page.get("paging", {}).get("next", {}).get("after") or "")
        if not page_results or not next_after:
            break
    return {
        "results": results,
        "requested_limit": requested_limit,
        "returned_count": len(results),
        "has_more": bool(next_after),
        "truncated": bool(next_after),
    }


def _conversation_messages(thread_id: str, limit: int) -> dict[str, Any]:
    requested_limit = _bounded_int(limit, default=50, maximum=INBOUND_MESSAGE_RETURN_LIMIT)
    results: list[dict[str, Any]] = []
    next_after = ""
    while len(results) < requested_limit:
        page_params = {"limit": str(min(100, requested_limit - len(results)))}
        if next_after:
            page_params["after"] = next_after
        page = _get(f"/conversations/v3/conversations/threads/{thread_id}/messages", page_params)
        page_results = page.get("results", [])
        results.extend(page_results)
        next_after = str(page.get("paging", {}).get("next", {}).get("after") or "")
        if not page_results or not next_after:
            break
    return {
        "results": results,
        "requested_limit": requested_limit,
        "returned_count": len(results),
        "has_more": bool(next_after),
        "truncated": bool(next_after),
    }


def _thread_sort_value(thread: dict[str, Any]) -> str:
    return str(thread.get("latestMessageTimestamp") or thread.get("latestMessageReceivedTimestamp") or thread.get("createdAt") or "")


def _safe_thread_summary(thread: dict[str, Any], access_context: dict[str, Any]) -> dict[str, Any]:
    contact = _safe_marketing_contact_summary(access_context.get("contact"))
    companies = [_safe_marketing_company_summary(company) for company in access_context.get("companies", [])]
    return {
        "thread_id": str(thread.get("id") or ""),
        "status": thread.get("status") or "",
        "inbox_id": thread.get("inboxId") or "",
        "original_channel_id": thread.get("originalChannelId") or "",
        "original_channel_account_id": thread.get("originalChannelAccountId") or "",
        "assigned_to": thread.get("assignedTo") or "",
        "created_at": thread.get("createdAt") or "",
        "latest_message_at": thread.get("latestMessageTimestamp") or "",
        "latest_received_at": thread.get("latestMessageReceivedTimestamp") or "",
        "latest_sent_at": thread.get("latestMessageSentTimestamp") or "",
        "associated_contact_id": access_context.get("associated_contact_id") or "",
        "associated_ticket_id": access_context.get("associated_ticket_id") or "",
        "contact": contact,
        "companies": companies,
        "scope_status": access_context.get("scope_status") or "",
        "spam": bool(thread.get("spam")),
        "archived": bool(thread.get("archived")),
    }


def _message_text(message: dict[str, Any]) -> tuple[str, bool]:
    raw = str(message.get("text") or "")
    if not raw and message.get("richText"):
        raw = _html_to_text(str(message.get("richText") or ""))
    text = re.sub(r"\s+", " ", raw).strip()
    if len(text) > MESSAGE_TEXT_LIMIT:
        return text[:MESSAGE_TEXT_LIMIT].rstrip(), True
    return text, False


def _safe_thread_message(message: dict[str, Any]) -> dict[str, Any]:
    text, local_truncated = _message_text(message)
    truncation_status = str(message.get("truncationStatus") or "")
    return {
        "message_id": str(message.get("id") or ""),
        "type": message.get("type") or "",
        "direction": message.get("direction") or "",
        "status": message.get("status") or "",
        "created_at": message.get("createdAt") or message.get("created_at") or "",
        "sent_at": message.get("sentAt") or message.get("sent_at") or "",
        "sender_actor_id": message.get("senderActorId") or message.get("sender_actor_id") or "",
        "actor_id": message.get("actorId") or "",
        "recipients": message.get("recipients") or [],
        "text": text,
        "text_truncated": bool(local_truncated or truncation_status in {"TRUNCATED", "TRUNCATED_TO_MOST_RECENT_REPLY"}),
        "truncation_status": truncation_status,
        "attachment_count": len(message.get("attachments", []) or []),
    }


def _safe_datetime_string(value: datetime | str | None) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    parsed = _datetime_value(str(value or ""))
    return parsed.isoformat().replace("+00:00", "Z") if parsed else ""


def _message_timestamp(message: dict[str, Any]) -> datetime | None:
    for key in ("createdAt", "created_at", "sentAt", "sent_at"):
        parsed = _datetime_value(str(message.get(key) or ""))
        if parsed:
            return parsed
    return None


def _message_direction(message: dict[str, Any]) -> str:
    return str(message.get("direction") or message.get("type") or "").strip().upper()


def _thread_message_timing(messages: list[dict[str, Any]]) -> dict[str, Any]:
    inbound_times: list[datetime] = []
    outbound_times: list[datetime] = []
    sources: list[str] = []
    text_truncated = False
    for message in messages:
        timestamp = _message_timestamp(message)
        if not timestamp:
            continue
        direction = _message_direction(message)
        safe_message = _safe_thread_message(message)
        text_truncated = text_truncated or bool(safe_message.get("text_truncated"))
        source = _safe_inbound_source(safe_message.get("text"))
        if source != "other" and source not in sources:
            sources.append(source)
        if direction in {"INCOMING", "INBOUND", "RECEIVED"}:
            inbound_times.append(timestamp)
        elif direction in {"OUTGOING", "OUTBOUND", "SENT"}:
            outbound_times.append(timestamp)
    first_inbound = min(inbound_times) if inbound_times else None
    first_outbound = None
    if outbound_times:
        candidates = [timestamp for timestamp in outbound_times if not first_inbound or timestamp >= first_inbound]
        first_outbound = min(candidates or outbound_times)
    return {
        "first_inbound_at": _safe_datetime_string(first_inbound),
        "first_outbound_at": _safe_datetime_string(first_outbound),
        "message_source_candidates": sources,
        "text_truncated": text_truncated,
    }


def _safe_inbound_source(value: Any) -> str:
    text = _normalized_words(str(value or ""))
    if not text:
        return "other"
    if "rad" in text or "request a demo" in text or "new incoming rad" in text or "book a demo" in text:
        return "RaD"
    if "whatsapp" in text or "whats app" in text or "inbox message" in text:
        return "WhatsApp"
    if "payroll" in text and ("portal" in text or "current user" in text or "interest" in text):
        return "portal payroll interest"
    return "other"


def _inbound_alert_datetime(alert: dict[str, Any], *keys: str) -> datetime | None:
    for key in keys:
        raw_value = str(alert.get(key) or "").strip()
        parsed = _datetime_value(raw_value)
        if not parsed and re.fullmatch(r"\d{10}(?:\.\d{1,6})?", raw_value):
            try:
                parsed = datetime.fromtimestamp(float(raw_value), timezone.utc)
            except (TypeError, ValueError, OSError):
                parsed = None
        if parsed:
            return parsed
    return None


def _inbound_alert_string(alert: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = str(alert.get(key) or "").strip()
        if value:
            return value
    return ""


def _normalize_inbound_alert(raw_alert: dict[str, Any], index: int) -> dict[str, Any]:
    if not isinstance(raw_alert, dict):
        raw_alert = {}
    source = _safe_inbound_source(
        _inbound_alert_string(raw_alert, "source", "alert_source", "type", "text", "message_text")
    )
    company_ids = _string_list(raw_alert.get("company_ids"))
    for key in ("company_id", "associated_company_id", "hubspot_company_id"):
        company_id = str(raw_alert.get(key) or "").strip()
        if company_id and company_id not in company_ids:
            company_ids.append(company_id)
    return {
        "alert_id": _inbound_alert_string(
            raw_alert,
            "alert_id",
            "slack_message_ts",
            "message_ts",
            "permalink",
            "slack_permalink",
        )
        or f"alert-{index + 1}",
        "slack_thread_ts": _inbound_alert_string(raw_alert, "slack_thread_ts", "thread_ts"),
        "hubspot_thread_id": _inbound_alert_string(
            raw_alert,
            "hubspot_thread_id",
            "hubspot_conversation_thread_id",
            "conversation_thread_id",
            "thread_id",
        ),
        "associated_contact_id": _inbound_alert_string(raw_alert, "associated_contact_id", "contact_id", "hubspot_contact_id"),
        "associated_ticket_id": _inbound_alert_string(raw_alert, "associated_ticket_id", "ticket_id", "hubspot_ticket_id"),
        "company_ids": company_ids,
        "source": source,
        "alert_time": _inbound_alert_datetime(raw_alert, "alert_time", "created_at", "timestamp", "ts"),
        "owner_tagged_time": _inbound_alert_datetime(raw_alert, "owner_tagged_time", "tagged_time"),
        "owner_ack_time": _inbound_alert_datetime(raw_alert, "owner_ack_time", "ack_time", "acknowledged_at"),
        "first_customer_touch_time": _inbound_alert_datetime(
            raw_alert,
            "first_customer_touch_time",
            "first_touch_time",
            "customer_touch_time",
        ),
        "outcome_time": _inbound_alert_datetime(raw_alert, "outcome_time", "resolved_at", "set_at"),
        "assigned_owner": _inbound_alert_string(raw_alert, "assigned_owner", "owner", "owner_name", "owner_email"),
        "backup_owner_if_reassigned": _inbound_alert_string(raw_alert, "backup_owner_if_reassigned", "backup_owner"),
        "status": _inbound_alert_string(raw_alert, "status"),
        "next_step": _inbound_alert_string(raw_alert, "next_step"),
        "eta": _inbound_alert_string(raw_alert, "eta"),
        "outcome": _inbound_alert_string(raw_alert, "outcome") or "needs-check",
        "duplicate_group_hint": _inbound_alert_string(raw_alert, "duplicate_group", "duplicate_hint"),
        "permalink": _inbound_alert_string(raw_alert, "permalink", "slack_permalink"),
        "tagged_slack_user_ids": _string_list(raw_alert.get("tagged_slack_user_ids")),
        "lead_context": _safe_inbound_lead_context(raw_alert),
    }


def _minutes_between(start: datetime | None, end: datetime | None) -> float | None:
    if not start or not end:
        return None
    return round(max(0.0, (end - start).total_seconds() / 60), 1)


def _sla_status_for_minutes(minutes: float | None, target_minutes: int) -> str:
    if minutes is None:
        return "needs-check"
    return "pass" if minutes <= target_minutes else "miss"


def _combined_sla_status(ack_status: str, touch_status: str) -> str:
    statuses = [ack_status, touch_status]
    if "miss" in statuses:
        return "miss"
    if statuses == ["pass", "pass"]:
        return "pass"
    return "needs-check"


def _earliest_datetime(values: list[datetime | None], since: datetime | None = None) -> datetime | None:
    candidates = [value for value in values if value and (not since or value >= since)]
    return min(candidates) if candidates else None


def _thread_company_ids(thread_summary: dict[str, Any]) -> list[str]:
    return [str(company.get("company_id") or "") for company in thread_summary.get("companies", []) if company.get("company_id")]


def _alert_matches_thread(alert: dict[str, Any], thread_summary: dict[str, Any]) -> bool:
    if alert.get("hubspot_thread_id") and alert["hubspot_thread_id"] == thread_summary.get("thread_id"):
        return True
    if alert.get("associated_contact_id") and alert["associated_contact_id"] == thread_summary.get("associated_contact_id"):
        return True
    if alert.get("associated_ticket_id") and alert["associated_ticket_id"] == thread_summary.get("associated_ticket_id"):
        return True
    return bool(set(alert.get("company_ids", [])).intersection(_thread_company_ids(thread_summary)))


def _alert_has_hubspot_match_key(alert: dict[str, Any]) -> bool:
    return bool(
        alert.get("hubspot_thread_id")
        or alert.get("associated_contact_id")
        or alert.get("associated_ticket_id")
        or alert.get("company_ids")
    )


def _inbound_duplicate_group(alert: dict[str, Any] | None, thread_summary: dict[str, Any] | None) -> str:
    alert = alert or {}
    thread_summary = thread_summary or {}
    if alert.get("duplicate_group_hint"):
        return str(alert["duplicate_group_hint"])
    contact_id = alert.get("associated_contact_id") or thread_summary.get("associated_contact_id")
    if contact_id:
        return f"contact:{contact_id}"
    company_ids = alert.get("company_ids") or _thread_company_ids(thread_summary)
    if company_ids:
        return f"company:{company_ids[0]}"
    ticket_id = alert.get("associated_ticket_id") or thread_summary.get("associated_ticket_id")
    if ticket_id:
        return f"ticket:{ticket_id}"
    thread_id = alert.get("hubspot_thread_id") or thread_summary.get("thread_id")
    if thread_id:
        return f"thread:{thread_id}"
    return "needs-check"


def _safe_inbound_lead_context(raw_alert: dict[str, Any]) -> dict[str, Any]:
    """Keep inbound audit rows actionable without exposing phone numbers or raw bodies."""
    lead_hints = raw_alert.get("lead_hints") if isinstance(raw_alert.get("lead_hints"), dict) else {}
    contact_name = _inbound_alert_string(raw_alert, "contact_name", "lead_name", "name") or str(
        lead_hints.get("contact_name") or ""
    ).strip()
    company_name = _inbound_alert_string(raw_alert, "company_name", "company", "account_name", "lead_company") or str(
        lead_hints.get("company_name") or ""
    ).strip()
    role = _inbound_alert_string(raw_alert, "contact_role", "jobtitle", "job_title", "title", "persona") or str(
        lead_hints.get("contact_role") or ""
    ).strip()
    email_domain = _inbound_alert_string(raw_alert, "email_domain", "domain", "company_domain") or str(
        lead_hints.get("email_domain") or ""
    ).strip()
    summary = _safe_activity_label(
        _inbound_alert_string(raw_alert, "lead_context", "context", "summary", "safe_context", "lead_summary")
        or str(lead_hints.get("summary") or ""),
        180,
    )
    phone_status = (
        "redacted"
        if _inbound_alert_string(raw_alert, "phone", "phone_number", "mobile", "mobile_number", "whatsapp_number")
        or str(lead_hints.get("phone_hint") or raw_alert.get("phone_hint") or "").strip()
        else "not_supplied"
    )
    phone_hint = str(lead_hints.get("phone_hint") or raw_alert.get("phone_hint") or "").strip()
    has_context = bool(contact_name or company_name or role or email_domain or summary)
    return {
        "contact_name": contact_name,
        "company_name": company_name,
        "contact_role": role,
        "email_domain": email_domain,
        "summary": summary,
        "phone_hint": phone_hint if phone_hint.startswith("masked_last4:") else "",
        "phone_number_status": phone_status,
        "context_status": "provided" if has_context else "missing",
    }


def _thread_lead_context(thread_summary: dict[str, Any], fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    contact = thread_summary.get("contact", {}) if isinstance(thread_summary.get("contact"), dict) else {}
    companies = thread_summary.get("companies", []) if isinstance(thread_summary.get("companies"), list) else []
    first_company = companies[0] if companies and isinstance(companies[0], dict) else {}
    fallback_context = fallback or {}
    contact_name = contact.get("display_name") or fallback_context.get("contact_name") or ""
    company_name = first_company.get("name") or fallback_context.get("company_name") or ""
    role = contact.get("jobtitle") or fallback_context.get("contact_role") or ""
    email_domain = contact.get("email_domain") or first_company.get("domain") or fallback_context.get("email_domain") or ""
    summary_parts = []
    if first_company.get("country"):
        summary_parts.append(str(first_company["country"]))
    if first_company.get("lifecycle_stage"):
        summary_parts.append(f"lifecycle {first_company['lifecycle_stage']}")
    summary = fallback_context.get("summary") or "; ".join(summary_parts)
    has_context = bool(contact_name or company_name or role or email_domain or summary)
    return {
        "contact_name": contact_name,
        "company_name": company_name,
        "contact_role": role,
        "email_domain": email_domain,
        "summary": _safe_activity_label(summary, 180),
        "phone_number_status": fallback_context.get("phone_number_status") or "not_returned",
        "context_status": "provided" if has_context else "missing",
    }


def _marketing_has_source_signal(access_context: dict[str, Any]) -> bool:
    contact = access_context.get("contact") or {}
    if _marketing_signal_fields(contact.get("properties", {}) if isinstance(contact, dict) else {}):
        return True
    for company in access_context.get("companies", []):
        if _marketing_signal_fields(company.get("properties", {}) if isinstance(company, dict) else {}):
            return True
    return False


def _marketing_has_decision_maker(access_context: dict[str, Any]) -> bool:
    contact = access_context.get("contact") or {}
    contact_props = contact.get("properties", {}) if isinstance(contact, dict) else {}
    if _has_decision_maker_buying_role(str(contact_props.get("hs_buying_role") or "")):
        return True
    for company in access_context.get("companies", []):
        props = company.get("properties", {}) if isinstance(company, dict) else {}
        if _int_value(props.get("hs_num_decision_makers")) > 0:
            return True
    return False


def _inbound_activity_snapshot_for_thread(
    access_context: dict[str, Any],
    since_dt: datetime | None,
    until_dt: datetime | None = None,
) -> dict[str, Any]:
    counts = {"whatsapp_communications": 0, "completed_calls": 0, "notes": 0, "completed_tasks": 0, "meetings": 0}
    first_touch: datetime | None = None
    latest_activity: datetime | None = None
    deal_stage_known = False
    truncated = False
    if not since_dt:
        return {
            "first_customer_touch_at": "",
            "latest_activity_at": "",
            "activity_counts": counts,
            "deal_stage_status": "needs-check",
            "truncated": False,
        }

    for company in access_context.get("companies", [])[:3]:
        company_id = str(company.get("id") or "")
        if not company_id:
            continue
        contact_ids = _association_ids("companies", company_id, "contacts", 50)
        deal_ids = _association_ids("companies", company_id, "deals", 20)
        deals = _batch_read("deals", deal_ids, DEAL_PROPERTIES)
        deal_stage_known = deal_stage_known or any(str(deal.get("properties", {}).get("dealstage") or "").strip() for deal in deals)
        activity_specs = [
            ("communications", "communication", COMMUNICATION_PROPERTIES),
            ("calls", "call", CALL_PROPERTIES),
            ("notes", "note", NOTE_PROPERTIES),
            ("tasks", "task", TASK_PROPERTIES),
            ("meetings", "meeting", MEETING_PROPERTIES),
        ]
        for hubspot_type, evidence_type, properties in activity_specs:
            association_data = _collect_activity_associations(company_id, contact_ids, deal_ids, hubspot_type)
            activity_ids = association_data["activity_ids"]
            read_ids = activity_ids[:FOLLOWUP_RETURN_LIMIT]
            truncated = bool(truncated or association_data["truncated"] or len(activity_ids) > len(read_ids))
            for activity in _batch_read(hubspot_type, read_ids, properties):
                timestamp = _datetime_value(_activity_timestamp(activity))
                if not timestamp or timestamp < since_dt or (until_dt and timestamp > until_dt):
                    continue
                latest_activity = max(latest_activity, timestamp) if latest_activity else timestamp
                if evidence_type == "communication":
                    if not _is_whatsapp_communication(activity):
                        continue
                    counts["whatsapp_communications"] += 1
                    first_touch = _earliest_datetime([first_touch, timestamp], since_dt)
                elif evidence_type == "call":
                    if not _is_completed_call(activity):
                        continue
                    counts["completed_calls"] += 1
                    first_touch = _earliest_datetime([first_touch, timestamp], since_dt)
                elif evidence_type == "note":
                    counts["notes"] += 1
                elif evidence_type == "task":
                    if not _is_incomplete_task(activity):
                        counts["completed_tasks"] += 1
                elif evidence_type == "meeting" and _is_completed_meeting(activity):
                    counts["meetings"] += 1

    return {
        "first_customer_touch_at": _safe_datetime_string(first_touch),
        "latest_activity_at": _safe_datetime_string(latest_activity),
        "activity_counts": counts,
        "deal_stage_status": "verified" if deal_stage_known else "needs-check",
        "truncated": truncated,
    }


def _inbound_hubspot_gaps(
    access_context: dict[str, Any],
    activity_snapshot: dict[str, Any],
    first_outbound_at: str = "",
) -> list[str]:
    gaps: list[str] = []
    contact = access_context.get("contact")
    companies = access_context.get("companies", [])
    if not contact and not access_context.get("associated_contact_id"):
        gaps.append("missing contact")
    if not companies:
        gaps.append("missing company")
    if companies and not any(company.get("properties", {}).get(CURRENT_TOOLS_SOURCE_OF_TRUTH_PROPERTY) for company in companies):
        gaps.append("missing current tools")
    if not _marketing_has_decision_maker(access_context):
        gaps.append("missing buying role")
    if not _marketing_has_source_signal(access_context):
        gaps.append("missing lead source")
    if not (first_outbound_at or activity_snapshot.get("latest_activity_at")):
        gaps.append("missing activity log")
    if activity_snapshot.get("deal_stage_status") != "verified":
        gaps.append("deal stage needs-check")
    return gaps


def _inbound_row_status(alert: dict[str, Any] | None, activity_snapshot: dict[str, Any], first_outbound_at: str) -> str:
    if alert and alert.get("status"):
        return str(alert["status"])
    counts = activity_snapshot.get("activity_counts", {})
    if _int_value(counts.get("completed_calls")):
        return "called"
    if first_outbound_at or _int_value(counts.get("whatsapp_communications")):
        return "acknowledged"
    return "needs-check"


def _inbound_thread_audit_row(
    thread_summary: dict[str, Any],
    access_context: dict[str, Any],
    message_timing: dict[str, Any],
    activity_snapshot: dict[str, Any],
    alert: dict[str, Any] | None,
    ack_sla_minutes: int,
    first_touch_sla_minutes: int,
) -> dict[str, Any]:
    alert_time = (alert or {}).get("alert_time") or _datetime_value(
        message_timing.get("first_inbound_at")
        or thread_summary.get("latest_received_at")
        or thread_summary.get("created_at")
        or thread_summary.get("latest_message_at")
    )
    owner_ack_time = (alert or {}).get("owner_ack_time")
    first_touch_time = _earliest_datetime(
        [
            (alert or {}).get("first_customer_touch_time"),
            _datetime_value(message_timing.get("first_outbound_at")),
            _datetime_value(activity_snapshot.get("first_customer_touch_at")),
        ],
        alert_time,
    )
    ack_minutes = _minutes_between(alert_time, owner_ack_time)
    first_touch_minutes = _minutes_between(alert_time, first_touch_time)
    ack_status = _sla_status_for_minutes(ack_minutes, ack_sla_minutes)
    first_touch_status = _sla_status_for_minutes(first_touch_minutes, first_touch_sla_minutes)
    source_candidates = message_timing.get("message_source_candidates", [])
    source = (alert or {}).get("source") or (source_candidates[0] if source_candidates else "other")
    company_summaries = thread_summary.get("companies", [])
    fallback_context = (alert or {}).get("lead_context", {})
    owner_from_company = ""
    if company_summaries:
        owner_from_company = company_summaries[0].get("owner_email") or _owner_email_by_id(company_summaries[0].get("owner_id"))
    activity_counts = activity_snapshot.get("activity_counts", {})
    if (alert or {}).get("first_customer_touch_time"):
        first_touch_source = "slack_alert_metadata"
    elif activity_snapshot.get("first_customer_touch_at"):
        first_touch_source = "hubspot_activity"
    elif message_timing.get("first_outbound_at"):
        first_touch_source = "hubspot_conversations_outbound"
    else:
        first_touch_source = "missing"
    manual_ae_touch_status = (
        "verified"
        if (alert or {}).get("first_customer_touch_time")
        or _int_value(activity_counts.get("completed_calls"))
        or _int_value(activity_counts.get("meetings"))
        else "needs-check"
    )
    return {
        "alert_id": (alert or {}).get("alert_id") or f"hubspot:{thread_summary.get('thread_id')}",
        "hubspot_thread_id": thread_summary.get("thread_id") or "",
        "alert_time": _safe_datetime_string(alert_time),
        "owner_tagged_time": _safe_datetime_string((alert or {}).get("owner_tagged_time")),
        "owner_ack_time": _safe_datetime_string(owner_ack_time),
        "first_customer_touch_time": _safe_datetime_string(first_touch_time),
        "first_hubspot_outbound_at": message_timing.get("first_outbound_at") or "",
        "first_touch_source": first_touch_source,
        "manual_ae_touch_status": manual_ae_touch_status,
        "outcome_time": _safe_datetime_string((alert or {}).get("outcome_time")),
        "assigned_owner": (alert or {}).get("assigned_owner") or owner_from_company or str(thread_summary.get("assigned_to") or ""),
        "backup_owner_if_reassigned": (alert or {}).get("backup_owner_if_reassigned") or "",
        "source": source,
        "status": _inbound_row_status(alert, activity_snapshot, message_timing.get("first_outbound_at") or ""),
        "next_step": (alert or {}).get("next_step") or "",
        "eta": (alert or {}).get("eta") or "",
        "duplicate_group": _inbound_duplicate_group(alert, thread_summary),
        "outcome": (alert or {}).get("outcome") or "needs-check",
        "lead_context": _thread_lead_context(thread_summary, fallback_context),
        "sla_status": _combined_sla_status(ack_status, first_touch_status),
        "ack_sla_status": ack_status,
        "first_touch_sla_status": first_touch_status,
        "ack_minutes": ack_minutes,
        "first_touch_minutes": first_touch_minutes,
        "hubspot_gaps": _inbound_hubspot_gaps(access_context, activity_snapshot, message_timing.get("first_outbound_at") or ""),
        "hubspot_context": {
            "associated_contact_id": thread_summary.get("associated_contact_id") or "",
            "associated_ticket_id": thread_summary.get("associated_ticket_id") or "",
            "companies": company_summaries,
            "scope_status": thread_summary.get("scope_status") or "",
            "first_hubspot_received_at": message_timing.get("first_inbound_at") or "",
            "first_hubspot_outbound_at": message_timing.get("first_outbound_at") or "",
            "first_hubspot_activity_touch_at": activity_snapshot.get("first_customer_touch_at") or "",
            "activity_counts": activity_snapshot.get("activity_counts", {}),
            "deal_stage_status": activity_snapshot.get("deal_stage_status") or "needs-check",
        },
    }


def _inbound_alert_only_row(alert: dict[str, Any], ack_sla_minutes: int, first_touch_sla_minutes: int) -> dict[str, Any]:
    alert_time = alert.get("alert_time")
    ack_minutes = _minutes_between(alert_time, alert.get("owner_ack_time"))
    first_touch_minutes = _minutes_between(alert_time, alert.get("first_customer_touch_time"))
    ack_status = _sla_status_for_minutes(ack_minutes, ack_sla_minutes)
    first_touch_status = _sla_status_for_minutes(first_touch_minutes, first_touch_sla_minutes)
    return {
        "alert_id": alert.get("alert_id") or "",
        "hubspot_thread_id": alert.get("hubspot_thread_id") or "",
        "alert_time": _safe_datetime_string(alert_time),
        "owner_tagged_time": _safe_datetime_string(alert.get("owner_tagged_time")),
        "owner_ack_time": _safe_datetime_string(alert.get("owner_ack_time")),
        "first_customer_touch_time": _safe_datetime_string(alert.get("first_customer_touch_time")),
        "first_hubspot_outbound_at": "",
        "first_touch_source": "slack_alert_metadata" if alert.get("first_customer_touch_time") else "missing",
        "manual_ae_touch_status": "verified" if alert.get("first_customer_touch_time") else "needs-check",
        "outcome_time": _safe_datetime_string(alert.get("outcome_time")),
        "assigned_owner": alert.get("assigned_owner") or "",
        "backup_owner_if_reassigned": alert.get("backup_owner_if_reassigned") or "",
        "source": alert.get("source") or "other",
        "status": alert.get("status") or "needs-check",
        "next_step": alert.get("next_step") or "",
        "eta": alert.get("eta") or "",
        "duplicate_group": _inbound_duplicate_group(alert, None),
        "outcome": alert.get("outcome") or "needs-check",
        "lead_context": alert.get("lead_context") or _safe_inbound_lead_context({}),
        "sla_status": _combined_sla_status(ack_status, first_touch_status),
        "ack_sla_status": ack_status,
        "first_touch_sla_status": first_touch_status,
        "ack_minutes": ack_minutes,
        "first_touch_minutes": first_touch_minutes,
        "hubspot_gaps": ["HubSpot conversation match needs-check"],
        "hubspot_context": {},
    }


def _duplicate_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("duplicate_group") or "needs-check")
        item = grouped.setdefault(
            key,
            {
                "duplicate_group": key,
                "alert_count": 0,
                "sources": [],
                "hubspot_thread_ids": [],
                "company_names": [],
                "sla_statuses": [],
            },
        )
        item["alert_count"] += 1
        for field, value in (
            ("sources", row.get("source")),
            ("hubspot_thread_ids", row.get("hubspot_thread_id")),
            ("sla_statuses", row.get("sla_status")),
        ):
            if value and value not in item[field]:
                item[field].append(value)
        for company in row.get("hubspot_context", {}).get("companies", []):
            name = company.get("name")
            if name and name not in item["company_names"]:
                item["company_names"].append(name)
    return sorted(grouped.values(), key=lambda item: (-item["alert_count"], item["duplicate_group"]))


def _inbound_candidate_text_matches(alert: dict[str, Any], thread_summary: dict[str, Any]) -> list[str]:
    context = alert.get("lead_context") or {}
    reasons: list[str] = []
    contact = thread_summary.get("contact") or {}
    companies = thread_summary.get("companies") or []
    contact_name = _normalize_company_match_text(context.get("contact_name") or "")
    thread_contact_name = _normalize_company_match_text(contact.get("display_name") or "")
    if contact_name and thread_contact_name and (
        contact_name == thread_contact_name or contact_name in thread_contact_name or thread_contact_name in contact_name
    ):
        reasons.append("contact_name_hint")
    email_domain = _clean_domain(str(context.get("email_domain") or ""))
    thread_email_domain = _clean_domain(str(contact.get("email_domain") or ""))
    if email_domain and thread_email_domain and email_domain == thread_email_domain:
        reasons.append("email_domain_hint")
    company_hint = _normalize_company_match_text(context.get("company_name") or "")
    for company in companies:
        company_name = _normalize_company_match_text(company.get("name") or "")
        company_domain = _clean_domain(str(company.get("domain") or ""))
        if company_hint and company_name and (
            company_hint == company_name or company_hint in company_name or company_name in company_hint
        ):
            reasons.append("company_name_hint")
        if email_domain and company_domain and email_domain == company_domain:
            reasons.append("company_domain_hint")
    return sorted(set(reasons))


def _inbound_alert_near_thread(alert: dict[str, Any], thread_summary: dict[str, Any], window_minutes: int = 7 * 24 * 60) -> bool:
    alert_time = alert.get("alert_time")
    if not alert_time:
        return True
    thread_time = _datetime_value(
        thread_summary.get("latest_received_at")
        or thread_summary.get("created_at")
        or thread_summary.get("latest_message_at")
        or ""
    )
    if not thread_time:
        return True
    return abs((thread_time - alert_time).total_seconds()) <= window_minutes * 60


def _inbound_alert_record(
    alert: dict[str, Any],
    match_status: str,
    match_reason: str,
    thread_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    thread_summary = thread_summary or {}
    companies = thread_summary.get("companies") or []
    first_company = companies[0] if companies else {}
    customer_status = "excluded_existing_customer" if first_company.get("account_status") == "customer" else "included_or_needs_check"
    if match_status != "verified":
        customer_status = "needs-check"
    return {
        "alert_id": alert.get("alert_id") or "",
        "permalink": alert.get("permalink") or "",
        "alert_time": _safe_datetime_string(alert.get("alert_time")),
        "source": alert.get("source") or "other",
        "assigned_owner": alert.get("assigned_owner") or "",
        "tagged_slack_user_ids": list(alert.get("tagged_slack_user_ids") or []),
        "lead_context": alert.get("lead_context") or _safe_inbound_lead_context({}),
        "match_status": match_status,
        "match_reason": match_reason,
        "hubspot_thread_id": thread_summary.get("thread_id") or "",
        "associated_contact_id": thread_summary.get("associated_contact_id") or "",
        "associated_ticket_id": thread_summary.get("associated_ticket_id") or "",
        "company_ids": [company.get("company_id") for company in companies if company.get("company_id")],
        "company_name": first_company.get("name") or "",
        "account_status": first_company.get("account_status") or "unknown",
        "account_status_source": first_company.get("account_status_source") or "HubSpot company status unavailable",
        "customer_exclusion_status": customer_status,
    }


def _merge_verified_inbound_alert(alert: dict[str, Any], resolution: dict[str, Any]) -> dict[str, Any]:
    merged = dict(alert)
    if resolution.get("hubspot_thread_id"):
        merged["hubspot_thread_id"] = resolution["hubspot_thread_id"]
    if resolution.get("associated_contact_id"):
        merged["associated_contact_id"] = resolution["associated_contact_id"]
    if resolution.get("associated_ticket_id"):
        merged["associated_ticket_id"] = resolution["associated_ticket_id"]
    if resolution.get("company_ids"):
        merged["company_ids"] = resolution["company_ids"]
    return merged


def _resolve_inbound_alerts_with_threads(
    scope: dict[str, Any],
    normalized_alerts: list[dict[str, Any]],
    thread_status: str = "ANY",
    inbox_id: str = "",
    latest_message_after: str = "",
    limit: int = 20,
    exclude_existing_customers: bool = False,
) -> dict[str, Any]:
    params = {
        "association": "TICKET",
        "archived": "false",
        "sort": "latestMessageTimestamp",
        "latestMessageTimestampAfter": latest_message_after or _default_latest_message_after(),
        "inboxId": str(inbox_id or ""),
    }
    alert_limit = _bounded_int(limit, default=20, maximum=INBOUND_THREAD_RETURN_LIMIT)
    data = _conversation_threads(params, min(INBOUND_THREAD_RETURN_LIMIT, max(alert_limit, 20)))
    requested_status = str(thread_status or "").strip().upper()
    thread_summaries: list[dict[str, Any]] = []
    inaccessible_count = 0
    unresolved_scope_count = 0
    for thread in sorted(data.get("results", []), key=_thread_sort_value, reverse=True):
        if requested_status and requested_status != "ANY" and str(thread.get("status") or "").upper() != requested_status:
            continue
        access_context = _marketing_access_context_for_thread(thread, scope)
        if not access_context["allowed"]:
            inaccessible_count += 1
            continue
        if access_context.get("scope_status") == "unresolved_company_scope":
            unresolved_scope_count += 1
        thread_summaries.append(_safe_thread_summary(thread, access_context))

    resolved_alerts: list[dict[str, Any]] = []
    candidate_alerts: list[dict[str, Any]] = []
    unmatched_alerts: list[dict[str, Any]] = []
    excluded_existing_customer_alerts: list[dict[str, Any]] = []
    merged_alerts: list[dict[str, Any]] = []
    for alert in normalized_alerts:
        verified_summary = next((summary for summary in thread_summaries if _alert_matches_thread(alert, summary)), None)
        if verified_summary:
            record = _inbound_alert_record(alert, "verified", "safe_hubspot_id_match", verified_summary)
            if exclude_existing_customers and record.get("account_status") == "customer":
                excluded_existing_customer_alerts.append(record)
                continue
            resolved_alerts.append(record)
            merged_alerts.append(_merge_verified_inbound_alert(alert, record))
            continue

        candidate_records: list[dict[str, Any]] = []
        for summary in thread_summaries:
            reasons = _inbound_candidate_text_matches(alert, summary)
            if reasons and _inbound_alert_near_thread(alert, summary):
                candidate_records.append(_inbound_alert_record(alert, "candidate", ",".join(reasons), summary))
        if candidate_records:
            candidate_alerts.extend(candidate_records[:3])
            merged_alerts.append(alert)
            continue

        unmatched_alerts.append(_inbound_alert_record(alert, "unmatched", "no_safe_id_or_bounded_hint_match"))
        merged_alerts.append(alert)

    return {
        "resolved_alerts": resolved_alerts,
        "candidate_alerts": candidate_alerts,
        "unmatched_alerts": unmatched_alerts,
        "excluded_existing_customer_alerts": excluded_existing_customer_alerts,
        "merged_alerts": merged_alerts,
        "match_summary": {
            "input_alert_count": len(normalized_alerts),
            "verified_count": len(resolved_alerts),
            "candidate_count": len(candidate_alerts),
            "unmatched_count": len(unmatched_alerts),
            "excluded_existing_customer_count": len(excluded_existing_customer_alerts),
            "thread_scan_count": len(thread_summaries),
            "inaccessible_thread_count": inaccessible_count,
            "unresolved_scope_count": unresolved_scope_count,
            "truncated": bool(data.get("truncated")),
        },
        "thread_data": data,
        "latest_message_after": params["latestMessageTimestampAfter"],
    }


def _inbound_audit_rollup(rows: list[dict[str, Any]], truncated: bool) -> dict[str, Any]:
    return {
        "row_count": len(rows),
        "sla_pass_count": sum(1 for row in rows if row.get("sla_status") == "pass"),
        "sla_miss_count": sum(1 for row in rows if row.get("sla_status") == "miss"),
        "needs_check_count": sum(1 for row in rows if row.get("sla_status") == "needs-check"),
        "duplicate_group_count": len({row.get("duplicate_group") for row in rows if row.get("duplicate_group")}),
        "missing_hubspot_match_count": sum(
            1 for row in rows if "HubSpot conversation match needs-check" in row.get("hubspot_gaps", [])
        ),
        "truncated": truncated,
    }


def _marketing_signal_fields(props: dict[str, Any]) -> dict[str, str]:
    keys = [
        "campaign",
        "abm_campaign_tag",
        "ad_interaction",
        "utm_campaign",
        "hs_analytics_source",
        "hs_analytics_source_data_1",
        "hs_analytics_source_data_2",
        "hs_latest_source",
        "hs_latest_source_data_1",
        "hs_latest_source_data_2",
        "first_conversion_event_name",
        "first_conversion_date",
        "recent_conversion_event_name",
        "recent_conversion_date",
    ]
    return {key: str(props.get(key) or "") for key in keys if str(props.get(key) or "").strip()}


def _campaign_summary(campaign: dict[str, Any]) -> dict[str, Any]:
    props = campaign.get("properties", {})
    return {
        "campaign_id": str(campaign.get("id") or campaign.get("campaignGuid") or props.get("hs_object_id") or ""),
        "name": props.get("hs_name") or campaign.get("name") or "",
        "status": props.get("hs_campaign_status") or "",
        "start_date": props.get("hs_start_date") or "",
        "end_date": props.get("hs_end_date") or "",
        "audience": props.get("hs_audience") or "",
        "utm": props.get("hs_utm") or "",
        "owner_id": props.get("hs_owner") or "",
        "created_at": campaign.get("createdAt") or "",
        "updated_at": campaign.get("updatedAt") or "",
    }


def _campaign_matches_filters(campaign: dict[str, Any], status: str = "", start_date: str = "", end_date: str = "") -> bool:
    props = campaign.get("properties", {})
    if status and str(props.get("hs_campaign_status") or "").lower() != status.lower():
        return False
    campaign_start = str(props.get("hs_start_date") or "")
    campaign_end = str(props.get("hs_end_date") or "")
    if start_date and campaign_end and campaign_end < start_date:
        return False
    if end_date and campaign_start and campaign_start > end_date:
        return False
    return True


def _marketing_campaign_search(name: str = "", status: str = "", start_date: str = "", end_date: str = "", limit: int = 20) -> dict[str, Any]:
    requested_limit = _bounded_int(limit, default=20, maximum=MARKETING_CAMPAIGN_RETURN_LIMIT)
    params = {
        "limit": str(min(100, requested_limit)),
        "properties": ",".join(CAMPAIGN_PROPERTIES),
        "sort": "-updatedAt",
    }
    if name:
        params["name"] = name
    results: list[dict[str, Any]] = []
    next_after = ""
    while len(results) < requested_limit:
        page_params = dict(params)
        page_params["limit"] = str(min(100, requested_limit - len(results)))
        if next_after:
            page_params["after"] = next_after
        page = _get("/marketing/v3/campaigns", page_params)
        for campaign in page.get("results", []):
            if _campaign_matches_filters(campaign, status, start_date, end_date):
                results.append(campaign)
                if len(results) >= requested_limit:
                    break
        next_after = str(page.get("paging", {}).get("next", {}).get("after") or "")
        if not next_after or len(results) >= requested_limit:
            break
    return {
        "results": results,
        "requested_limit": requested_limit,
        "returned_count": len(results),
        "has_more": bool(next_after),
        "truncated": bool(next_after),
    }


def _get_campaign(campaign_id: str) -> dict[str, Any]:
    return _get(f"/marketing/v3/campaigns/{campaign_id}", {"properties": ",".join(CAMPAIGN_PROPERTIES)})


def _safe_asset_summary(asset_type: str, asset: dict[str, Any]) -> dict[str, Any]:
    props = asset.get("properties", {}) if isinstance(asset.get("properties"), dict) else {}
    metrics = asset.get("metrics") or asset.get("performanceMetrics") or props.get("metrics") or {}
    return {
        "asset_type": asset_type,
        "asset_id": str(asset.get("id") or asset.get("assetId") or props.get("hs_object_id") or ""),
        "name": asset.get("name") or asset.get("title") or props.get("hs_name") or props.get("name") or "",
        "url": asset.get("url") or props.get("url") or "",
        "metrics_available": asset_type not in NO_METRIC_CAMPAIGN_ASSET_TYPES and bool(metrics),
        "metrics": metrics if isinstance(metrics, dict) else {},
    }


def _campaign_assets(campaign_id: str, asset_types: list[str] | None = None, start_date: str = "", end_date: str = "", limit: int = 50) -> dict[str, Any]:
    requested_limit = _bounded_int(limit, default=50, maximum=CAMPAIGN_ASSET_RETURN_LIMIT)
    selected_types = []
    for asset_type in asset_types or list(MARKETING_CAMPAIGN_ASSET_TYPES):
        normalized = str(asset_type or "").strip().upper()
        if normalized in MARKETING_CAMPAIGN_ASSET_TYPES and normalized not in selected_types:
            selected_types.append(normalized)
    assets_by_type: dict[str, Any] = {}
    truncated = False
    for asset_type in selected_types:
        params = {"limit": str(requested_limit)}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        page = _get(f"/marketing/v3/campaigns/{campaign_id}/assets/{asset_type}", params)
        raw_assets = page.get("results", []) if isinstance(page.get("results"), list) else []
        has_more = bool(page.get("paging", {}).get("next", {}).get("after"))
        truncated = truncated or has_more or len(raw_assets) > requested_limit
        assets_by_type[asset_type] = {
            "assets": [_safe_asset_summary(asset_type, asset) for asset in raw_assets[:requested_limit]],
            "returned_count": min(len(raw_assets), requested_limit),
            "has_more": has_more,
            "truncated": has_more or len(raw_assets) > requested_limit,
            "metrics_caveat": "No metrics available for this HubSpot campaign asset type."
            if asset_type in NO_METRIC_CAMPAIGN_ASSET_TYPES
            else "",
        }
    return {
        "asset_types": selected_types,
        "assets_by_type": assets_by_type,
        "requested_limit": requested_limit,
        "has_more": truncated,
        "truncated": truncated,
    }


def _safe_social_channel(channel: dict[str, Any]) -> dict[str, str]:
    channel_key = str(channel.get("channelKey") or channel.get("channel") or "")
    network = channel_key.split(":", 1)[0] if channel_key else str(channel.get("network") or "")
    return {
        "name": str(channel.get("name") or ""),
        "network": network,
    }


def _hubspot_social_channels() -> dict[str, Any]:
    data = _get("/broadcast/v1/channels/setting/publish/current")
    channels = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []
    safe_channels = [_safe_social_channel(channel) for channel in channels if isinstance(channel, dict)]
    counts_by_network: dict[str, int] = {}
    for channel in safe_channels:
        network = channel.get("network") or "unknown"
        counts_by_network[network] = counts_by_network.get(network, 0) + 1
    return {
        "connected_count": len(safe_channels),
        "accounts": safe_channels,
        "counts_by_network": counts_by_network,
        "privacy": "Raw social channel IDs are intentionally not returned.",
    }


def _campaign_asset_metric_window(
    campaign: dict[str, Any],
    start_date: str = "",
    end_date: str = "",
    fallback_days: int = 730,
) -> dict[str, Any]:
    summary = _campaign_summary(campaign)
    today = datetime.now(timezone.utc).date()
    explicit_start = bool(str(start_date or "").strip())
    explicit_end = bool(str(end_date or "").strip())
    parsed_start = _date_value(start_date) if explicit_start else None
    parsed_end = _date_value(end_date) if explicit_end else None
    caveats: list[str] = []

    if explicit_start and not parsed_start:
        caveats.append("Provided start_date could not be parsed; campaign/default metric window was used.")
    if explicit_end and not parsed_end:
        caveats.append("Provided end_date could not be parsed; campaign/default metric window was used.")

    end = parsed_end or _date_value(summary.get("end_date")) or today
    start = parsed_start or _date_value(summary.get("start_date")) or _date_value(summary.get("created_at"))
    source = "explicit" if parsed_start or parsed_end else "campaign_dates"
    if not start:
        start = end - timedelta(days=fallback_days)
        source = "fallback_last_730_days"
        caveats.append("Campaign start/created date was missing; social metric window used the last 730 days.")
    if start > end:
        start = end
        caveats.append("Metric window start was after end; start was clamped to the end date.")
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "source": source,
        "confidence": "needs-check" if caveats else "verified",
        "caveat": " ".join(caveats),
    }


def _social_click_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    clicks_by_network = {
        network: int(_number_value(metrics.get(metric_key)))
        for network, metric_key in SOCIAL_CLICK_METRIC_KEYS.items()
    }
    return {
        "clicks_by_network": clicks_by_network,
        "total_clicks": sum(clicks_by_network.values()),
    }


def _safe_social_asset_summary(asset: dict[str, Any]) -> dict[str, Any]:
    props = asset.get("properties", {}) if isinstance(asset.get("properties"), dict) else {}
    metrics = asset.get("metrics") or asset.get("performanceMetrics") or props.get("metrics") or {}
    if not isinstance(metrics, dict):
        metrics = {}
    name = str(asset.get("name") or asset.get("title") or asset.get("messageText") or props.get("hs_name") or props.get("name") or "")
    name = re.sub(r"\s+", " ", name).strip()
    metric_summary = _social_click_metrics(metrics)
    return {
        "asset_id": str(asset.get("id") or asset.get("assetId") or props.get("hs_object_id") or ""),
        "name": name[:180],
        **metric_summary,
        "metrics_available": bool(metrics),
        "metrics_source": "HubSpot Campaigns assets API SOCIAL_BROADCAST metrics",
    }


def _campaign_social_assets(campaign_id: str, start_date: str, end_date: str, limit: int = CAMPAIGN_SOCIAL_ASSET_RETURN_LIMIT) -> dict[str, Any]:
    requested_limit = _bounded_int(
        limit,
        default=CAMPAIGN_SOCIAL_ASSET_RETURN_LIMIT,
        maximum=CAMPAIGN_SOCIAL_ASSET_RETURN_LIMIT,
    )
    assets: list[dict[str, Any]] = []
    next_after = ""
    while len(assets) < requested_limit:
        params = {
            "limit": str(min(100, requested_limit - len(assets))),
            "startDate": start_date,
            "endDate": end_date,
        }
        if next_after:
            params["after"] = next_after
        page = _get(f"/marketing/v3/campaigns/{campaign_id}/assets/SOCIAL_BROADCAST", params)
        raw_assets = page.get("results", []) if isinstance(page.get("results"), list) else []
        assets.extend(_safe_social_asset_summary(asset) for asset in raw_assets if isinstance(asset, dict))
        next_after = str(page.get("paging", {}).get("next", {}).get("after") or "")
        if not raw_assets or not next_after:
            break
    return {
        "assets": assets[:requested_limit],
        "requested_limit": requested_limit,
        "returned_count": min(len(assets), requested_limit),
        "has_more": bool(next_after),
        "truncated": bool(next_after),
    }


def _campaign_social_effectiveness_summary(asset_data: dict[str, Any]) -> dict[str, Any]:
    clicks_by_network = {network: 0 for network in SOCIAL_CLICK_METRIC_KEYS}
    posts_with_clicks = 0
    for asset in asset_data.get("assets", []):
        total_clicks = _int_value(asset.get("total_clicks"))
        if total_clicks > 0:
            posts_with_clicks += 1
        for network in clicks_by_network:
            clicks_by_network[network] += _int_value(asset.get("clicks_by_network", {}).get(network))
    top_posts = sorted(
        [asset for asset in asset_data.get("assets", []) if _int_value(asset.get("total_clicks")) > 0],
        key=lambda asset: _int_value(asset.get("total_clicks")),
        reverse=True,
    )[:SOCIAL_TOP_POST_RETURN_LIMIT]
    return {
        "asset_count": asset_data.get("returned_count", 0),
        "posts_with_clicks": posts_with_clicks,
        "clicks_by_network": clicks_by_network,
        "total_clicks": sum(clicks_by_network.values()),
        "top_posts": top_posts,
        "top_post_limit": SOCIAL_TOP_POST_RETURN_LIMIT,
        "metrics_source": "HubSpot Campaigns assets API SOCIAL_BROADCAST metrics",
        "has_more": bool(asset_data.get("has_more")),
        "truncated": bool(asset_data.get("truncated")),
        "privacy": "Aggregate social metrics only. Raw channel IDs and bulk post exports are intentionally not returned.",
    }


def _require_marketing_manager_or_admin(scope: dict[str, Any], slack_user_email: str) -> dict[str, Any] | None:
    if scope["kind"] in {"admin", "manager"}:
        return None
    return _blocked(
        "HubSpot marketing and campaign lookups require manager/admin scope unless a scoped company/contact context is supplied.",
        {"caller_email": slack_user_email},
    )


def _candidate_campaign_query(contact: dict[str, Any] | None, companies: list[dict[str, Any]], explicit_query: str = "") -> str:
    if explicit_query:
        return explicit_query
    if contact:
        props = contact.get("properties", {})
        for key in ("utm_campaign", "abm_campaign_tag", "recent_conversion_event_name", "first_conversion_event_name"):
            value = str(props.get(key) or "").strip()
            if value:
                return value
    for company in companies:
        props = company.get("properties", {})
        for key in ("campaign", "utm_campaign", "abm_campaign_tag"):
            value = str(props.get(key) or "").strip()
            if value:
                return value
    return ""


def _campaign_readable_text(value: str) -> str:
    text = re.sub(r"[_-]+", " ", str(value or ""))
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _add_marketing_attribution_term(terms: list[str], seen: set[str], value: Any) -> None:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        return
    key = _normalize_name(text)
    if not key or key in seen:
        return
    terms.append(text)
    seen.add(key)


def _campaign_attribution_terms(
    campaign: dict[str, Any],
    explicit_utm: str = "",
    explicit_name: str = "",
    asset_data: dict[str, Any] | None = None,
) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    seed_values = [
        explicit_utm,
        explicit_name,
        campaign.get("utm"),
        campaign.get("name"),
    ]
    for value in seed_values:
        text = str(value or "").strip()
        if not text:
            continue
        _add_marketing_attribution_term(terms, seen, text)
        stripped = re.sub(r"^\d+[-_]+", "", text)
        _add_marketing_attribution_term(terms, seen, stripped)
        _add_marketing_attribution_term(terms, seen, _campaign_readable_text(stripped))
        _add_marketing_attribution_term(terms, seen, _normalize_name(stripped))

    assets_by_type = (asset_data or {}).get("assets_by_type", {})
    for asset_type_data in assets_by_type.values():
        for asset in asset_type_data.get("assets", []) if isinstance(asset_type_data, dict) else []:
            _add_marketing_attribution_term(terms, seen, asset.get("name"))
            if len(terms) >= MARKETING_ATTRIBUTION_TERM_LIMIT:
                return terms[:MARKETING_ATTRIBUTION_TERM_LIMIT]

    for value in seed_values:
        for word in _normalize_name(str(value or "")).split():
            if len(word) >= 5 and not word.isdigit():
                _add_marketing_attribution_term(terms, seen, word)
            if len(terms) >= MARKETING_ATTRIBUTION_TERM_LIMIT:
                return terms[:MARKETING_ATTRIBUTION_TERM_LIMIT]
    return terms[:MARKETING_ATTRIBUTION_TERM_LIMIT]


def _marketing_contact_campaign_search(terms: list[str], limit: int = MARKETING_ATTRIBUTION_RETURN_LIMIT) -> dict[str, Any]:
    requested_limit = _bounded_int(limit, default=MARKETING_ATTRIBUTION_RETURN_LIMIT, maximum=MARKETING_ATTRIBUTION_RETURN_LIMIT)
    contacts_by_id: dict[str, dict[str, Any]] = {}
    search_runs: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    truncated = False

    for property_name in MARKETING_ATTRIBUTION_SEARCH_PROPERTIES:
        for term in terms:
            if len(contacts_by_id) >= requested_limit:
                truncated = True
                break
            remaining = requested_limit - len(contacts_by_id)
            body = {
                "filterGroups": [
                    {
                        "filters": [
                            {
                                "propertyName": property_name,
                                "operator": "CONTAINS_TOKEN",
                                "value": term,
                            }
                        ]
                    }
                ],
                "properties": MARKETING_CONTACT_PROPERTIES,
                "limit": min(HUBSPOT_SEARCH_PAGE_LIMIT, remaining),
            }
            try:
                data = _post("/crm/v3/objects/contacts/search", body)
            except HubSpotError as error:
                errors.append({"property": property_name, "term": term, "error": str(error)[:160]})
                continue

            results = data.get("results", [])
            has_more = bool(data.get("paging", {}).get("next", {}).get("after"))
            truncated = truncated or has_more
            search_runs.append(
                {
                    "property": property_name,
                    "term": term,
                    "returned_count": len(results),
                    "has_more": has_more,
                }
            )
            for contact in results:
                contact_id = str(contact.get("id") or "")
                if contact_id and contact_id not in contacts_by_id:
                    contacts_by_id[contact_id] = contact
                if len(contacts_by_id) >= requested_limit:
                    truncated = True
                    break
        if len(contacts_by_id) >= requested_limit:
            break

    return {
        "results": list(contacts_by_id.values())[:requested_limit],
        "searched_properties": list(MARKETING_ATTRIBUTION_SEARCH_PROPERTIES),
        "search_runs": search_runs,
        "search_run_count": len(search_runs),
        "errors": errors,
        "requested_limit": requested_limit,
        "returned_count": len(contacts_by_id),
        "has_more": truncated,
        "truncated": truncated,
    }


def _marketing_attribution_deal_counts(deals: list[dict[str, Any]], stage_config: dict[str, Any]) -> dict[str, Any]:
    counts = {
        "qos": 0,
        "qo_met": 0,
        "closed_won": 0,
        "classified_deal_count": 0,
        "stage_configured": bool(stage_config.get("configured")),
        "safe_deals": [],
    }
    if not stage_config.get("configured"):
        return counts

    pipeline_ids = set(stage_config.get("pipeline_ids", set()))
    qo_stage_ids = set(stage_config.get("qo_stage_ids", set()))
    qo_met_stage_ids = set(stage_config.get("qo_met_stage_ids", set()))
    closed_won_stage_ids = set(stage_config.get("closed_won_stage_ids", set()))

    for deal in deals:
        props = deal.get("properties", {})
        pipeline_id = str(props.get("pipeline") or "")
        stage_id = str(props.get("dealstage") or "")
        if pipeline_ids and pipeline_id not in pipeline_ids:
            continue
        classifications: list[str] = []
        if stage_id in qo_stage_ids:
            counts["qos"] += 1
            classifications.append("qo")
        if stage_id in qo_met_stage_ids:
            counts["qo_met"] += 1
            classifications.append("qo_met")
        if stage_id in closed_won_stage_ids:
            counts["closed_won"] += 1
            classifications.append("closed_won")
        if classifications:
            counts["classified_deal_count"] += 1
            safe_deal = _safe_deal(deal)
            safe_deal["pipeline"] = pipeline_id
            safe_deal["classifications"] = classifications
            if len(counts["safe_deals"]) < 20:
                counts["safe_deals"].append(safe_deal)
    return counts


@mcp.tool()
def list_inbound_threads(
    slack_user_email: str,
    thread_status: str = "OPEN",
    inbox_id: str = "",
    associated_contact_id: str = "",
    latest_message_after: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    """List recent HubSpot Conversations inbox threads with summaries only."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        params = {
            "association": "TICKET",
            "archived": "false",
            "sort": "latestMessageTimestamp",
            "latestMessageTimestampAfter": latest_message_after or _default_latest_message_after(),
            "inboxId": str(inbox_id or ""),
            "associatedContactId": str(associated_contact_id or ""),
        }
        fetch_limit = min(INBOUND_THREAD_RETURN_LIMIT, max(_bounded_int(limit, default=20), 20))
        data = _conversation_threads(params, fetch_limit)
        requested_status = str(thread_status or "").strip().upper()
        summaries = []
        inaccessible_count = 0
        unresolved_scope_count = 0
        for thread in sorted(data.get("results", []), key=_thread_sort_value, reverse=True):
            if requested_status and requested_status != "ANY" and str(thread.get("status") or "").upper() != requested_status:
                continue
            access_context = _marketing_access_context_for_thread(thread, scope)
            if not access_context["allowed"]:
                inaccessible_count += 1
                continue
            if access_context.get("scope_status") == "unresolved_company_scope":
                unresolved_scope_count += 1
            summaries.append(_safe_thread_summary(thread, access_context))
            if len(summaries) >= _bounded_int(limit, default=20, maximum=INBOUND_THREAD_RETURN_LIMIT):
                break
        return {
            "answer": summaries,
            "source": "HubSpot Conversations threads API",
            "scope": {
                **_scope_response(scope, list(scope.get("countries", ()))),
                "thread_status": requested_status or "ANY",
                "inbox_id": inbox_id,
                "associated_contact_id": associated_contact_id,
                "latest_message_after": params["latestMessageTimestampAfter"],
            },
            "requested_limit": _bounded_int(limit, default=20, maximum=INBOUND_THREAD_RETURN_LIMIT),
            "scanned_count": len(data.get("results", [])),
            "returned_count": len(summaries),
            "has_more": data.get("has_more"),
            "truncated": bool(data.get("truncated") or inaccessible_count or unresolved_scope_count),
            "confidence": "needs-check" if data.get("truncated") or unresolved_scope_count else "verified",
            "caveat": (
                "Summaries only. Use get_inbound_thread_context for one selected thread's full text; "
                "bulk full-thread exports and phone/contact exports are intentionally not returned."
            ),
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def get_inbound_thread_context(slack_user_email: str, thread_id: str, message_limit: int = 100) -> dict[str, Any]:
    """Read one selected HubSpot Conversations inbox thread, including full message text."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        thread = _get(f"/conversations/v3/conversations/threads/{thread_id}", {"association": "TICKET"})
        access_context = _marketing_access_context_for_thread(thread, scope)
        if not access_context["allowed"]:
            return _blocked("Thread is outside caller scope or has no scoped company context.", {"caller_email": slack_user_email, "thread_id": thread_id})
        message_data = _conversation_messages(str(thread_id), message_limit)
        messages = [_safe_thread_message(message) for message in message_data.get("results", [])]
        text_truncated = any(message.get("text_truncated") for message in messages)
        return {
            "answer": {
                "thread": _safe_thread_summary(thread, access_context),
                "messages": messages,
                "message_count": len(messages),
                "full_text_scope": "single_selected_thread_only",
                "will_mutate_hubspot": False,
            },
            "source": "HubSpot Conversations thread and messages API",
            "scope": {
                **_scope_response(scope, list(scope.get("countries", ()))),
                "thread_id": str(thread_id),
                "message_limit": _bounded_int(message_limit, default=100, maximum=INBOUND_MESSAGE_RETURN_LIMIT),
            },
            "requested_limit": message_data.get("requested_limit"),
            "returned_count": message_data.get("returned_count"),
            "has_more": message_data.get("has_more"),
            "truncated": bool(message_data.get("truncated") or text_truncated),
            "confidence": "needs-check" if message_data.get("truncated") or text_truncated else "verified",
            "caveat": "Full text is returned for this one selected thread only. Attachments are counted but not fetched, and no HubSpot mutation or external message send is performed.",
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "thread_id": thread_id})


@mcp.tool()
def resolve_inbound_slack_alerts_to_hubspot(
    slack_user_email: str,
    slack_alerts: list[dict[str, Any]],
    thread_status: str = "ANY",
    inbox_id: str = "",
    latest_message_after: str = "",
    limit: int = 20,
    exclude_existing_customers: bool = False,
) -> dict[str, Any]:
    """Resolve safe Slack inbound alert rows to HubSpot conversations, contacts, and companies."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        if not isinstance(slack_alerts, list):
            return _blocked("slack_alerts must be a list of safe Slack alert metadata objects.", _scope_response(scope, list(scope.get("countries", ()))))
        normalized_alerts = [
            _normalize_inbound_alert(alert, index)
            for index, alert in enumerate(slack_alerts[:INBOUND_SLA_ALERT_RETURN_LIMIT])
            if isinstance(alert, dict)
        ]
        resolution = _resolve_inbound_alerts_with_threads(
            scope,
            normalized_alerts,
            thread_status=thread_status,
            inbox_id=inbox_id,
            latest_message_after=latest_message_after,
            limit=limit,
            exclude_existing_customers=exclude_existing_customers,
        )
        summary = resolution["match_summary"]
        confidence = "needs-check" if summary["candidate_count"] or summary["unmatched_count"] or summary["truncated"] else "verified"
        return {
            "answer": {
                "resolved_alerts": resolution["resolved_alerts"],
                "candidate_alerts": resolution["candidate_alerts"],
                "unmatched_alerts": resolution["unmatched_alerts"],
                "excluded_existing_customer_alerts": resolution["excluded_existing_customer_alerts"],
                "match_summary": summary,
                "will_mutate_hubspot": False,
                "external_message_sending": False,
            },
            "source": "HubSpot Conversations, contacts, and companies matched from safe Slack alert metadata",
            "scope": {
                **_scope_response(scope, list(scope.get("countries", ()))),
                "thread_status": str(thread_status or "").strip().upper() or "ANY",
                "inbox_id": inbox_id,
                "latest_message_after": resolution["latest_message_after"],
                "exclude_existing_customers": bool(exclude_existing_customers),
            },
            "requested_limit": _bounded_int(limit, default=20, maximum=INBOUND_THREAD_RETURN_LIMIT),
            "returned_count": summary["verified_count"] + summary["candidate_count"] + summary["unmatched_count"],
            "has_more": resolution["thread_data"].get("has_more"),
            "truncated": bool(summary["truncated"]),
            "confidence": confidence,
            "caveat": "Verified requires safe HubSpot ID/thread evidence. Name, company, domain, and timestamp hints remain candidates; no HubSpot mutation or external message send was performed.",
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def audit_inbound_sla(
    slack_user_email: str,
    slack_alerts: list[dict[str, Any]] | None = None,
    thread_status: str = "ANY",
    inbox_id: str = "",
    latest_message_after: str = "",
    limit: int = 20,
    ack_sla_minutes: int = INBOUND_SLA_DEFAULT_ACK_MINUTES,
    first_touch_sla_minutes: int = INBOUND_SLA_DEFAULT_FIRST_TOUCH_MINUTES,
    duplicate_window_minutes: int = INBOUND_SLA_DEFAULT_DUPLICATE_WINDOW_MINUTES,
    resolve_slack_alerts: bool = True,
    exclude_existing_customers: bool = False,
) -> dict[str, Any]:
    """Audit inbound alert ownership, first touch SLA, and duplicate groups without mutating HubSpot."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        if slack_alerts is not None and not isinstance(slack_alerts, list):
            return _blocked("slack_alerts must be a list of safe Slack alert metadata objects.", _scope_response(scope, list(scope.get("countries", ()))))

        normalized_alerts = [
            _normalize_inbound_alert(alert, index)
            for index, alert in enumerate((slack_alerts or [])[:INBOUND_SLA_ALERT_RETURN_LIMIT])
            if isinstance(alert, dict)
        ]
        ack_sla = _bounded_int(ack_sla_minutes, default=INBOUND_SLA_DEFAULT_ACK_MINUTES, maximum=120)
        first_touch_sla = _bounded_int(first_touch_sla_minutes, default=INBOUND_SLA_DEFAULT_FIRST_TOUCH_MINUTES, maximum=240)
        duplicate_window = _bounded_int(
            duplicate_window_minutes,
            default=INBOUND_SLA_DEFAULT_DUPLICATE_WINDOW_MINUTES,
            maximum=24 * 60,
        )
        alert_limit = _bounded_int(limit, default=20, maximum=INBOUND_THREAD_RETURN_LIMIT)
        resolution = None
        if normalized_alerts and resolve_slack_alerts:
            resolution = _resolve_inbound_alerts_with_threads(
                scope,
                normalized_alerts,
                thread_status=thread_status,
                inbox_id=inbox_id,
                latest_message_after=latest_message_after,
                limit=alert_limit,
                exclude_existing_customers=exclude_existing_customers,
            )
            normalized_alerts = resolution["merged_alerts"]
            if not normalized_alerts and resolution["excluded_existing_customer_alerts"]:
                return {
                    "answer": {
                        "sla_policy": {
                            "ack_sla_minutes": ack_sla,
                            "first_touch_sla_minutes": first_touch_sla,
                            "backup_rule": "If the assigned owner is silent, says later, or cannot touch now, Eugene can manually reassign to a backup owner.",
                            "thread_response_format": "Owner: <name> | Status: acknowledged / called / reassigned / set / blocked | Next step: <action> | ETA: <time>",
                        },
                        "audit_rows": [],
                        "duplicate_summary": [],
                        "rollup": {
                            "row_count": 0,
                            "sla_pass_count": 0,
                            "sla_miss_count": 0,
                            "needs_check_count": 0,
                            "duplicate_group_count": 0,
                            "missing_hubspot_match_count": 0,
                            "truncated": False,
                            "excluded_existing_customer_count": len(resolution["excluded_existing_customer_alerts"]),
                        },
                        "resolved_inbound_alerts": resolution["resolved_alerts"],
                        "candidate_inbound_alerts": resolution["candidate_alerts"],
                        "unmatched_inbound_alerts": resolution["unmatched_alerts"],
                        "excluded_existing_customer_alerts": resolution["excluded_existing_customer_alerts"],
                        "match_summary": resolution["match_summary"],
                        "will_mutate_hubspot": False,
                        "external_message_sending": False,
                    },
                    "source": "HubSpot Conversations, HubSpot CRM activity, and supplied safe Slack alert metadata",
                    "scope": {
                        **_scope_response(scope, list(scope.get("countries", ()))),
                        "thread_status": str(thread_status or "").strip().upper() or "ANY",
                        "inbox_id": inbox_id,
                        "latest_message_after": resolution["latest_message_after"],
                        "slack_alert_count": len(slack_alerts or []),
                        "ack_sla_minutes": ack_sla,
                        "first_touch_sla_minutes": first_touch_sla,
                        "duplicate_window_minutes": duplicate_window,
                        "resolve_slack_alerts": True,
                        "exclude_existing_customers": bool(exclude_existing_customers),
                    },
                    "requested_limit": alert_limit,
                    "returned_count": 0,
                    "has_more": resolution["thread_data"].get("has_more"),
                    "truncated": bool(resolution["match_summary"].get("truncated")),
                    "confidence": "verified",
                    "caveat": "All supplied Slack alerts were verified HubSpot existing customers and excluded. No HubSpot mutation or external message send was performed.",
                }
        if normalized_alerts and not resolve_slack_alerts and not any(_alert_has_hubspot_match_key(alert) for alert in normalized_alerts):
            rows = [_inbound_alert_only_row(alert, ack_sla, first_touch_sla) for alert in normalized_alerts[:alert_limit]]
            rollup = _inbound_audit_rollup(rows, bool(len(normalized_alerts) > len(rows)))
            duplicate_summary = _duplicate_summary(rows)
            return {
                "answer": {
                    "sla_policy": {
                        "ack_sla_minutes": ack_sla,
                        "first_touch_sla_minutes": first_touch_sla,
                        "backup_rule": "If the assigned owner is silent, says later, or cannot touch now, Eugene can manually reassign to a backup owner.",
                        "thread_response_format": "Owner: <name> | Status: acknowledged / called / reassigned / set / blocked | Next step: <action> | ETA: <time>",
                    },
                    "audit_rows": rows,
                    "duplicate_summary": duplicate_summary,
                    "rollup": rollup,
                    "dedupe_rule": (
                        "Group duplicates by the same HubSpot conversation thread, contact, ticket, or company. "
                        f"Slack-only alerts without safe HubSpot IDs stay needs-check even inside the {duplicate_window}-minute review window."
                    ),
                    "will_mutate_hubspot": False,
                    "external_message_sending": False,
                },
                "source": "Supplied safe Slack alert metadata; HubSpot matching skipped because no safe HubSpot IDs were supplied.",
                "scope": {
                    **_scope_response(scope, list(scope.get("countries", ()))),
                    "thread_status": str(thread_status or "").strip().upper() or "ANY",
                    "inbox_id": inbox_id,
                    "latest_message_after": latest_message_after or "",
                    "slack_alert_count": len(normalized_alerts),
                    "ack_sla_minutes": ack_sla,
                    "first_touch_sla_minutes": first_touch_sla,
                    "duplicate_window_minutes": duplicate_window,
                    "hubspot_match_mode": "skipped_no_safe_ids",
                    "resolve_slack_alerts": False,
                    "exclude_existing_customers": bool(exclude_existing_customers),
                },
                "requested_limit": alert_limit,
                "returned_count": len(rows),
                "has_more": False,
                "truncated": bool(len(normalized_alerts) > len(rows)),
                "confidence": "needs-check",
                "caveat": (
                    "Read-only audit from safe Slack metadata only. HubSpot contact/company/activity/deal verification "
                    "needs safe HubSpot thread, contact, ticket, or company IDs. No HubSpot mutation or external message send was performed."
                ),
            }
        params = {
            "association": "TICKET",
            "archived": "false",
            "sort": "latestMessageTimestamp",
            "latestMessageTimestampAfter": latest_message_after or _default_latest_message_after(),
            "inboxId": str(inbox_id or ""),
        }
        fetch_limit = min(INBOUND_THREAD_RETURN_LIMIT, max(alert_limit, 20))
        data = _conversation_threads(params, fetch_limit)
        requested_status = str(thread_status or "").strip().upper()
        rows: list[dict[str, Any]] = []
        matched_alert_ids: set[str] = set()
        inaccessible_count = 0
        unresolved_scope_count = 0
        text_truncated = False
        activity_truncated = False

        for thread in sorted(data.get("results", []), key=_thread_sort_value, reverse=True):
            if requested_status and requested_status != "ANY" and str(thread.get("status") or "").upper() != requested_status:
                continue
            access_context = _marketing_access_context_for_thread(thread, scope)
            if not access_context["allowed"]:
                inaccessible_count += 1
                continue
            if access_context.get("scope_status") == "unresolved_company_scope":
                unresolved_scope_count += 1
            thread_summary = _safe_thread_summary(thread, access_context)
            message_data = _conversation_messages(str(thread_summary.get("thread_id") or thread.get("id") or ""), INBOUND_MESSAGE_RETURN_LIMIT)
            message_timing = _thread_message_timing(message_data.get("results", []))
            text_truncated = bool(text_truncated or message_data.get("truncated") or message_timing.get("text_truncated"))
            since_dt = _datetime_value(
                message_timing.get("first_inbound_at")
                or thread_summary.get("latest_received_at")
                or thread_summary.get("created_at")
                or thread_summary.get("latest_message_at")
            )
            activity_snapshot = _inbound_activity_snapshot_for_thread(access_context, since_dt)
            activity_truncated = bool(activity_truncated or activity_snapshot.get("truncated"))
            matching_alerts = [alert for alert in normalized_alerts if _alert_matches_thread(alert, thread_summary)]

            if not normalized_alerts:
                rows.append(
                    _inbound_thread_audit_row(
                        thread_summary,
                        access_context,
                        message_timing,
                        activity_snapshot,
                        None,
                        ack_sla,
                        first_touch_sla,
                    )
                )
                if len(rows) >= alert_limit:
                    break
                continue

            for alert in matching_alerts:
                matched_alert_ids.add(str(alert.get("alert_id") or ""))
                rows.append(
                    _inbound_thread_audit_row(
                        thread_summary,
                        access_context,
                        message_timing,
                        activity_snapshot,
                        alert,
                        ack_sla,
                        first_touch_sla,
                    )
                )
                if len(rows) >= alert_limit:
                    break
            if len(rows) >= alert_limit:
                break

        if normalized_alerts and len(rows) < alert_limit:
            for alert in normalized_alerts:
                if str(alert.get("alert_id") or "") in matched_alert_ids:
                    continue
                rows.append(_inbound_alert_only_row(alert, ack_sla, first_touch_sla))
                if len(rows) >= alert_limit:
                    break

        truncated = bool(
            data.get("truncated")
            or inaccessible_count
            or unresolved_scope_count
            or text_truncated
            or activity_truncated
            or (normalized_alerts and len(normalized_alerts) > len(matched_alert_ids))
        )
        rollup = _inbound_audit_rollup(rows, truncated)
        if resolution:
            rollup["excluded_existing_customer_count"] = len(resolution["excluded_existing_customer_alerts"])
        duplicate_summary = _duplicate_summary(rows)
        confidence = "needs-check" if truncated or rollup["needs_check_count"] or rollup["missing_hubspot_match_count"] else "verified"
        return {
            "answer": {
                "sla_policy": {
                    "ack_sla_minutes": ack_sla,
                    "first_touch_sla_minutes": first_touch_sla,
                    "backup_rule": "If the assigned owner is silent, says later, or cannot touch now, Eugene can manually reassign to a backup owner.",
                    "thread_response_format": "Owner: <name> | Status: acknowledged / called / reassigned / set / blocked | Next step: <action> | ETA: <time>",
                },
                "audit_rows": rows,
                "duplicate_summary": duplicate_summary,
                "rollup": rollup,
                "resolved_inbound_alerts": resolution["resolved_alerts"] if resolution else [],
                "candidate_inbound_alerts": resolution["candidate_alerts"] if resolution else [],
                "unmatched_inbound_alerts": resolution["unmatched_alerts"] if resolution else [],
                "excluded_existing_customer_alerts": resolution["excluded_existing_customer_alerts"] if resolution else [],
                "match_summary": resolution["match_summary"] if resolution else {},
                "dedupe_rule": (
                    "Group duplicates by the same HubSpot conversation thread, contact, ticket, or company. "
                    f"Slack-only alerts without safe HubSpot IDs stay needs-check even inside the {duplicate_window}-minute review window."
                ),
                "will_mutate_hubspot": False,
                "external_message_sending": False,
            },
            "source": "HubSpot Conversations, HubSpot CRM activity, and supplied safe Slack alert metadata",
            "scope": {
                **_scope_response(scope, list(scope.get("countries", ()))),
                "thread_status": requested_status or "ANY",
                "inbox_id": inbox_id,
                "latest_message_after": params["latestMessageTimestampAfter"],
                "slack_alert_count": len(normalized_alerts),
                "ack_sla_minutes": ack_sla,
                "first_touch_sla_minutes": first_touch_sla,
                "duplicate_window_minutes": duplicate_window,
                "resolve_slack_alerts": bool(resolve_slack_alerts),
                "exclude_existing_customers": bool(exclude_existing_customers),
            },
            "requested_limit": alert_limit,
            "returned_count": len(rows),
            "has_more": data.get("has_more"),
            "truncated": truncated,
            "confidence": confidence,
            "caveat": (
                "Read-only audit. Slack ack/reassignment fields require supplied safe Slack alert metadata; "
                "HubSpot Conversations and CRM activity verify customer touch where associated records exist. "
                "No HubSpot mutation or external message send was performed."
            ),
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def list_marketing_campaigns(
    slack_user_email: str,
    name: str = "",
    status: str = "",
    start_date: str = "",
    end_date: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    """List HubSpot marketing campaigns for manager/admin campaign triage."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        blocked = _require_marketing_manager_or_admin(scope, slack_user_email)
        if blocked:
            return blocked
        data = _marketing_campaign_search(name, status, start_date, end_date, limit)
        campaigns = [_campaign_summary(campaign) for campaign in data.get("results", [])]
        return {
            "answer": campaigns,
            "source": "HubSpot Marketing Campaigns API",
            "scope": {
                **_scope_response(scope, list(scope.get("countries", ()))),
                "name": name,
                "status": status,
                "start_date": start_date,
                "end_date": end_date,
            },
            **_search_metadata(data),
            "confidence": "needs-check" if data.get("truncated") else "verified",
            "caveat": "Read-only campaign metadata. Use get_campaign_assets for associated forms, pages, emails, SMS/social, and podcast episodes.",
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def get_campaign_assets(
    slack_user_email: str,
    campaign_id: str,
    asset_types: list[str] | None = None,
    start_date: str = "",
    end_date: str = "",
    limit: int = 50,
) -> dict[str, Any]:
    """Read HubSpot campaign assets and available metrics for selected asset types."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        blocked = _require_marketing_manager_or_admin(scope, slack_user_email)
        if blocked:
            return blocked
        campaign = _get_campaign(str(campaign_id))
        metric_window = _campaign_asset_metric_window(campaign, start_date, end_date)
        asset_data = _campaign_assets(str(campaign_id), asset_types, metric_window["start_date"], metric_window["end_date"], limit)
        includes_no_metric_assets = any(asset_type in NO_METRIC_CAMPAIGN_ASSET_TYPES for asset_type in asset_data.get("asset_types", []))
        caveats = []
        if includes_no_metric_assets:
            caveats.append("Podcast episodes and several HubSpot campaign asset types have no metrics available; association evidence is not proof of contact engagement.")
        if metric_window.get("caveat"):
            caveats.append(str(metric_window["caveat"]))
        return {
            "answer": {
                "campaign": _campaign_summary(campaign),
                "metric_window": metric_window,
                **asset_data,
                "will_mutate_hubspot": False,
            },
            "source": "HubSpot Marketing Campaigns assets API",
            "scope": {
                **_scope_response(scope, list(scope.get("countries", ()))),
                "campaign_id": str(campaign_id),
                "start_date": metric_window["start_date"],
                "end_date": metric_window["end_date"],
            },
            "confidence": "needs-check" if asset_data.get("truncated") or includes_no_metric_assets or metric_window.get("confidence") == "needs-check" else "verified",
            "caveat": " ".join(caveats) or "Read-only campaign assets with date-windowed metrics where HubSpot exposes them.",
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "campaign_id": campaign_id})


@mcp.tool()
def get_campaign_social_effectiveness(
    slack_user_email: str,
    campaign_id: str = "",
    campaign_name: str = "",
    start_date: str = "",
    end_date: str = "",
    asset_limit: int = CAMPAIGN_SOCIAL_ASSET_RETURN_LIMIT,
) -> dict[str, Any]:
    """Read HubSpot-connected social campaign performance for one marketing campaign."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        blocked = _require_marketing_manager_or_admin(scope, slack_user_email)
        if blocked:
            return blocked
        if not campaign_id and not campaign_name:
            return _blocked("Provide campaign_id or campaign_name for social campaign effectiveness.", _scope_response(scope, list(scope.get("countries", ()))))

        selected_campaign_id = str(campaign_id or "").strip()
        matched_campaigns: list[dict[str, Any]] = []
        campaign_match_caveat = ""
        if not selected_campaign_id:
            campaign_data = _marketing_campaign_search(campaign_name, limit=3)
            matched_campaigns = [_campaign_summary(campaign) for campaign in campaign_data.get("results", [])]
            if not matched_campaigns:
                return _blocked(
                    "No HubSpot marketing campaign matched the requested campaign_name.",
                    {**_scope_response(scope, list(scope.get("countries", ()))), "campaign_name": campaign_name},
                )
            selected_campaign_id = str(matched_campaigns[0].get("campaign_id") or "")
            if len(matched_campaigns) > 1:
                campaign_match_caveat = "Multiple campaigns matched the name; selected the first HubSpot result. Use campaign_id for exact rerun."

        requested_asset_limit = _bounded_int(
            asset_limit,
            default=CAMPAIGN_SOCIAL_ASSET_RETURN_LIMIT,
            maximum=CAMPAIGN_SOCIAL_ASSET_RETURN_LIMIT,
        )
        campaign = _get_campaign(selected_campaign_id)
        metric_window = _campaign_asset_metric_window(campaign, start_date, end_date)
        social_channels = _hubspot_social_channels()
        social_asset_data = _campaign_social_assets(
            selected_campaign_id,
            metric_window["start_date"],
            metric_window["end_date"],
            requested_asset_limit,
        )
        social_summary = _campaign_social_effectiveness_summary(social_asset_data)
        podcast_assets = _campaign_assets(
            selected_campaign_id,
            ["PODCAST_EPISODE"],
            metric_window["start_date"],
            metric_window["end_date"],
            CAMPAIGN_ASSET_RETURN_LIMIT,
        )
        podcast_bucket = podcast_assets.get("assets_by_type", {}).get("PODCAST_EPISODE", {})
        caveats = [
            "Social clicks are engagement evidence only, not QO or closed-won proof.",
            "Podcast episode assets expose association context only; they do not prove listens or engagement.",
        ]
        if campaign_match_caveat:
            caveats.append(campaign_match_caveat)
        if metric_window.get("caveat"):
            caveats.append(str(metric_window["caveat"]))
        if social_summary.get("truncated") or podcast_assets.get("truncated"):
            caveats.append("One or more social/podcast asset reads hit the configured limit; counts are partial.")
        confidence = "needs-check" if metric_window.get("confidence") == "needs-check" or social_summary.get("truncated") or podcast_assets.get("truncated") else "verified"

        return {
            "answer": {
                "campaign": _campaign_summary(campaign),
                "matched_campaigns": matched_campaigns,
                "metric_window": metric_window,
                "social_accounts": social_channels,
                "social": social_summary,
                "podcast_asset_count": len(podcast_bucket.get("assets", [])) if isinstance(podcast_bucket, dict) else 0,
                "podcast_asset_has_more": bool(podcast_bucket.get("has_more")) if isinstance(podcast_bucket, dict) else False,
                "privacy": "Aggregate social campaign metrics only. No raw channel IDs, bulk post export, native-platform scraping, or HubSpot mutation.",
                "will_mutate_hubspot": False,
            },
            "source": "HubSpot Social connected accounts and HubSpot Campaigns SOCIAL_BROADCAST assets API",
            "scope": {
                **_scope_response(scope, list(scope.get("countries", ()))),
                "campaign_id": selected_campaign_id,
                "campaign_name": campaign_name,
                "start_date": metric_window["start_date"],
                "end_date": metric_window["end_date"],
                "asset_limit": requested_asset_limit,
            },
            "requested_limit": requested_asset_limit,
            "returned_count": social_summary.get("asset_count", 0),
            "has_more": bool(social_summary.get("has_more") or podcast_assets.get("has_more")),
            "truncated": bool(social_summary.get("truncated") or podcast_assets.get("truncated")),
            "confidence": confidence,
            "caveat": " ".join(caveats),
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "campaign_id": campaign_id, "campaign_name": campaign_name})


@mcp.tool()
def get_marketing_touch_context(
    slack_user_email: str,
    thread_id: str = "",
    contact_id: str = "",
    company_id: str = "",
    campaign_id: str = "",
    campaign_name: str = "",
    include_recent_threads: bool = True,
) -> dict[str, Any]:
    """Combine scoped inbound, contact/company source fields, campaign, and podcast association context."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        if not any([thread_id, contact_id, company_id, campaign_id, campaign_name]):
            return _blocked("Provide a thread_id, contact_id, company_id, campaign_id, or campaign_name.", {"caller_email": slack_user_email})

        thread_summary: dict[str, Any] = {}
        contact: dict[str, Any] | None = None
        companies: list[dict[str, Any]] = []

        if thread_id:
            thread = _get(f"/conversations/v3/conversations/threads/{thread_id}", {"association": "TICKET"})
            access_context = _marketing_access_context_for_thread(thread, scope)
            if not access_context["allowed"]:
                return _blocked("Thread is outside caller scope or has no scoped company context.", {"caller_email": slack_user_email, "thread_id": thread_id})
            thread_summary = _safe_thread_summary(thread, access_context)
            contact = access_context.get("contact")
            companies = access_context.get("companies", [])
            contact_id = contact_id or str(access_context.get("associated_contact_id") or "")

        if contact_id and contact is None:
            contact_access = _marketing_access_context_for_contact(str(contact_id), scope)
            if not contact_access["allowed"]:
                return _blocked("Contact is outside caller scope or has no scoped company context.", {"caller_email": slack_user_email, "contact_id": contact_id})
            contact = contact_access.get("contact")
            companies = contact_access.get("companies", [])

        if company_id:
            company = _read_marketing_company(str(company_id))
            if not company or not _has_marketing_company_access(company, scope):
                return _blocked("Company is outside caller marketing scope.", {"caller_email": slack_user_email, "company_id": company_id})
            if str(company.get("id") or "") not in {str(item.get("id") or "") for item in companies}:
                companies.append(company)

        recent_threads = []
        if include_recent_threads and contact_id:
            recent_data = _conversation_threads(
                {
                    "associatedContactId": str(contact_id),
                    "association": "TICKET",
                    "archived": "false",
                    "sort": "latestMessageTimestamp",
                    "latestMessageTimestampAfter": _default_latest_message_after(),
                },
                5,
            )
            for recent_thread in sorted(recent_data.get("results", []), key=_thread_sort_value, reverse=True):
                recent_access = _marketing_access_context_for_thread(recent_thread, scope)
                if recent_access["allowed"]:
                    recent_threads.append(_safe_thread_summary(recent_thread, recent_access))

        contact_source_fields = _marketing_signal_fields(contact.get("properties", {})) if contact else {}
        company_source_fields = [
            {
                "company_id": str(company.get("id") or ""),
                "fields": _marketing_signal_fields(company.get("properties", {})),
            }
            for company in companies
        ]

        campaign_query = _candidate_campaign_query(contact, companies, campaign_name)
        campaigns = []
        podcast_assets = []
        selected_campaign_ids = [str(campaign_id)] if campaign_id else []
        if campaign_query and not selected_campaign_ids:
            campaign_data = _marketing_campaign_search(campaign_query, limit=3)
            selected_campaign_ids = [str(campaign.get("id") or "") for campaign in campaign_data.get("results", []) if campaign.get("id")]
            campaigns.extend([_campaign_summary(campaign) for campaign in campaign_data.get("results", [])])
        if campaign_id:
            campaign = _get_campaign(str(campaign_id))
            campaigns.append(_campaign_summary(campaign))
        for selected_campaign_id in selected_campaign_ids[:3]:
            asset_data = _campaign_assets(selected_campaign_id, ["PODCAST_EPISODE"], limit=20)
            podcast_assets.append(
                {
                    "campaign_id": selected_campaign_id,
                    "assets": asset_data.get("assets_by_type", {}).get("PODCAST_EPISODE", {}).get("assets", []),
                    "metrics_caveat": "HubSpot Campaigns API reports no metrics for PODCAST_EPISODE assets.",
                }
            )

        return {
            "answer": {
                "thread": thread_summary,
                "contact": _safe_marketing_contact_summary(contact),
                "companies": [_safe_marketing_company_summary(company) for company in companies],
                "contact_source_fields": contact_source_fields,
                "company_source_fields": company_source_fields,
                "recent_threads": recent_threads,
                "campaigns": campaigns,
                "podcast_campaign_evidence": podcast_assets,
                "will_mutate_hubspot": False,
            },
            "source": "HubSpot Conversations, CRM, and Marketing Campaigns APIs",
            "scope": {
                **_scope_response(scope, list(scope.get("countries", ()))),
                "thread_id": thread_id,
                "contact_id": contact_id,
                "company_id": company_id,
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
            },
            "confidence": "needs-check",
            "caveat": "Marketing source fields and podcast campaign assets are attribution signals. Podcast asset association is not proof of contact engagement, and no HubSpot mutation or external message send is performed.",
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def get_marketing_campaign_attribution(
    slack_user_email: str,
    campaign_id: str = "",
    campaign_name: str = "",
    campaign_utm: str = "",
    start_date: str = "",
    end_date: str = "",
    limit: int = MARKETING_ATTRIBUTION_RETURN_LIMIT,
) -> dict[str, Any]:
    """Search HubSpot source fields for campaign-touched contacts and scoped deal outcomes."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        blocked = _require_marketing_manager_or_admin(scope, slack_user_email)
        if blocked:
            return blocked
        if not any([campaign_id, campaign_name, campaign_utm]):
            return _blocked("Provide campaign_id, campaign_name, or campaign_utm.", {"caller_email": slack_user_email})

        campaign: dict[str, Any] | None = None
        candidate_campaigns: list[dict[str, Any]] = []
        campaign_search_truncated = False
        if campaign_id:
            campaign = _get_campaign(str(campaign_id))
        else:
            campaign_query = str(campaign_name or campaign_utm or "").strip()
            campaign_data = _marketing_campaign_search(campaign_query, start_date=start_date, end_date=end_date, limit=5)
            candidate_campaigns = [_campaign_summary(item) for item in campaign_data.get("results", [])]
            campaign_search_truncated = bool(campaign_data.get("truncated"))
            for item in campaign_data.get("results", []):
                summary = _campaign_summary(item)
                if campaign_utm and summary.get("utm") == campaign_utm:
                    campaign = item
                    break
                if campaign_name and _normalize_name(summary.get("name", "")) == _normalize_name(campaign_name):
                    campaign = item
                    break
            if campaign is None and len(campaign_data.get("results", [])) == 1:
                campaign = campaign_data["results"][0]

        selected_campaign = _campaign_summary(campaign) if campaign else {
            "campaign_id": str(campaign_id or ""),
            "name": str(campaign_name or ""),
            "status": "",
            "start_date": "",
            "end_date": "",
            "audience": "",
            "utm": str(campaign_utm or ""),
            "owner_id": "",
            "created_at": "",
            "updated_at": "",
        }

        selected_campaign_id = str(campaign_id or selected_campaign.get("campaign_id") or "")
        asset_data = {
            "asset_types": [],
            "assets_by_type": {},
            "requested_limit": _bounded_int(limit, default=MARKETING_ATTRIBUTION_RETURN_LIMIT, maximum=CAMPAIGN_ASSET_RETURN_LIMIT),
            "has_more": False,
            "truncated": False,
        }
        if selected_campaign_id:
            asset_data = _campaign_assets(selected_campaign_id, limit=min(_bounded_int(limit, default=MARKETING_ATTRIBUTION_RETURN_LIMIT), CAMPAIGN_ASSET_RETURN_LIMIT))

        terms = _campaign_attribution_terms(selected_campaign, campaign_utm, campaign_name, asset_data)
        if not terms:
            return _blocked(
                "No usable campaign name or UTM terms were available for attribution search.",
                {"caller_email": slack_user_email, "campaign_id": selected_campaign_id, "campaign_name": campaign_name, "campaign_utm": campaign_utm},
            )

        contact_data = _marketing_contact_campaign_search(terms, limit)
        contact_results = [contact for contact in contact_data.get("results", []) if str(contact.get("id") or "")]
        contact_ids = [str(contact.get("id") or "") for contact in contact_results]
        contact_by_id = {str(contact.get("id") or ""): contact for contact in contact_results}
        contact_company_ids = _batch_association_ids("contacts", "companies", contact_ids)
        all_company_ids = sorted(
            {
                str(company_id)
                for company_ids in contact_company_ids.values()
                for company_id in company_ids
                if str(company_id)
            }
        )
        companies_by_id = {
            str(company.get("id") or ""): company
            for company in _batch_read("companies", all_company_ids, MARKETING_COMPANY_PROPERTIES)
            if str(company.get("id") or "")
        }

        matched_contacts: list[dict[str, Any]] = []
        scoped_companies: dict[str, dict[str, Any]] = {}
        inaccessible_contact_count = 0
        unresolved_contact_count = 0

        for contact_id_value in contact_ids:
            contact = contact_by_id[contact_id_value]
            associated_companies = [
                companies_by_id[company_id]
                for company_id in contact_company_ids.get(contact_id_value, [])
                if company_id in companies_by_id
            ]
            accessible_companies = [company for company in associated_companies if _has_marketing_company_access(company, scope)]
            if not accessible_companies:
                if scope["kind"] in {"admin", "manager"} and not associated_companies:
                    unresolved_contact_count += 1
                else:
                    inaccessible_contact_count += 1
                    continue
            for company in accessible_companies:
                company_id_value = str(company.get("id") or "")
                if company_id_value and company_id_value not in scoped_companies:
                    scoped_companies[company_id_value] = company
            matched_contacts.append(
                {
                    **_safe_marketing_contact_summary(contact),
                    "source_fields": _marketing_signal_fields(contact.get("properties", {})),
                    "scoped_company_ids": [str(company.get("id") or "") for company in accessible_companies if company.get("id")],
                }
            )

        company_deal_ids = _batch_association_ids("companies", "deals", list(scoped_companies.keys()))
        deal_ids: list[str] = []
        deal_association_truncated = False
        for associated_deal_ids in company_deal_ids.values():
            for deal_id in associated_deal_ids:
                if deal_id not in deal_ids:
                    deal_ids.append(deal_id)

        deals = _batch_read("deals", deal_ids, DEAL_PROPERTIES)
        stage_config = _friday_review_stage_config()
        deal_counts = _marketing_attribution_deal_counts(deals, stage_config)

        needs_check = bool(
            campaign_search_truncated
            or asset_data.get("truncated")
            or contact_data.get("truncated")
            or contact_data.get("errors")
            or inaccessible_contact_count
            or unresolved_contact_count
            or deal_association_truncated
            or not stage_config.get("configured")
        )
        caveats = [
            "Bounded HubSpot source-field search only; this is not full multi-touch attribution or form-submission analytics.",
        ]
        if not stage_config.get("configured"):
            caveats.append("QO/QO Met/closed-won counts require configured HubSpot pipeline and stage IDs.")
        if not matched_contacts:
            caveats.append("No scoped contacts matched the searched campaign terms; do not turn this into proof that nobody submitted the form if HubSpot form metrics are unavailable.")
        if contact_data.get("truncated") or deal_association_truncated:
            caveats.append(
                "Deal-stage counts cover only the returned/scoped campaign matches; do not present QO/QO Met/closed-won counts as complete when truncated=true."
            )

        truncation_reasons: list[str] = []
        if campaign_search_truncated:
            truncation_reasons.append("campaign_search_truncated")
        if asset_data.get("truncated"):
            truncation_reasons.append("campaign_assets_truncated")
        if contact_data.get("truncated"):
            truncation_reasons.append("contact_source_search_truncated")
        if contact_data.get("errors"):
            truncation_reasons.append("contact_source_search_errors")
        if inaccessible_contact_count:
            truncation_reasons.append("contacts_outside_scope")
        if unresolved_contact_count:
            truncation_reasons.append("contacts_without_scoped_company")
        if deal_association_truncated:
            truncation_reasons.append("deal_associations_truncated")
        if not stage_config.get("configured"):
            truncation_reasons.append("stage_config_missing")

        detail_limit = MARKETING_ATTRIBUTION_DETAIL_RETURN_LIMIT
        matched_contact_samples = matched_contacts[:detail_limit]
        scoped_company_samples = [_safe_marketing_company_summary(company) for company in list(scoped_companies.values())[:detail_limit]]
        outcome_summary = {
            "campaign": selected_campaign,
            "matched_contact_count": len(matched_contacts),
            "matched_contact_sample_count": len(matched_contact_samples),
            "scoped_company_count": len(scoped_companies),
            "scoped_company_sample_count": len(scoped_company_samples),
            "deal_stage_counts": {
                "qos": deal_counts.get("qos"),
                "qo_met": deal_counts.get("qo_met"),
                "closed_won": deal_counts.get("closed_won"),
                "classified_deal_count": deal_counts.get("classified_deal_count"),
                "stage_configured": deal_counts.get("stage_configured"),
            },
            "result_completeness": "needs-check" if needs_check else "complete",
            "truncation_reasons": truncation_reasons,
        }

        return {
            "answer": {
                "outcome_summary": outcome_summary,
                "campaign": selected_campaign,
                "candidate_campaigns": candidate_campaigns,
                "deal_stage_counts": deal_counts,
                "deal_association_truncated": deal_association_truncated,
                "attribution_search": {
                    "terms": terms,
                    "searched_properties": contact_data.get("searched_properties", []),
                    "search_run_count": contact_data.get("search_run_count", 0),
                    "errors": contact_data.get("errors", []),
                    "truncated": bool(contact_data.get("truncated")),
                    "matched_contact_count": len(matched_contacts),
                    "scoped_company_count": len(scoped_companies),
                    "inaccessible_contact_count": inaccessible_contact_count,
                    "unresolved_contact_count": unresolved_contact_count,
                },
                "matched_contact_samples": matched_contact_samples,
                "scoped_company_samples": scoped_company_samples,
                "detail_sample_limit": detail_limit,
                "will_mutate_hubspot": False,
            },
            "source": "HubSpot Marketing Campaigns, CRM contacts, scoped companies, and deals APIs",
            "scope": {
                **_scope_response(scope, list(scope.get("countries", ()))),
                "campaign_id": selected_campaign_id,
                "campaign_name": campaign_name,
                "campaign_utm": campaign_utm,
                "start_date": start_date,
                "end_date": end_date,
                "requested_limit": _bounded_int(limit, default=MARKETING_ATTRIBUTION_RETURN_LIMIT, maximum=MARKETING_ATTRIBUTION_RETURN_LIMIT),
            },
            "requested_limit": contact_data.get("requested_limit"),
            "returned_count": len(matched_contacts),
            "has_more": bool(needs_check and (contact_data.get("truncated") or asset_data.get("truncated") or deal_association_truncated)),
            "truncated": bool(contact_data.get("truncated") or asset_data.get("truncated") or deal_association_truncated),
            "confidence": "needs-check" if needs_check else "verified",
            "caveat": " ".join(caveats),
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "campaign_id": campaign_id, "campaign_name": campaign_name, "campaign_utm": campaign_utm})


@mcp.tool()
def audit_hubspot_owner_roster(
    slack_user_email: str,
    countries: list[str] | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    """List active HubSpot owners and target-account counts for admin classification."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] != "admin":
            return _blocked("Only admins can audit the HubSpot owner roster for NurtureAny classification.", {"caller_email": slack_user_email})
        selected = _safe_countries(countries, scope["countries"])
        if not selected:
            return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))
        policy = _access_policy()
        owners = _list_owners(limit)
        roster = []
        for owner in owners:
            email = _normalize_email(str(owner.get("email") or ""))
            if not email:
                continue
            owner_id = str(owner.get("id") or "")
            counts = _target_counts_for_owner(owner_id, selected)
            roster.append(
                {
                    "owner_id": owner_id,
                    "email": email,
                    "name": _owner_name(owner),
                    "classification": _policy_classification(email, policy),
                    "target_account_counts": counts,
                }
            )
        unclassified_count = len([owner for owner in roster if owner["classification"] == "unclassified"])
        return {
            "answer": {
                "owners": roster,
                "owner_count": len(roster),
                "unclassified_count": unclassified_count,
                "policy_source": policy["source"],
            },
            "source": "HubSpot owners API and target-account counts",
            "scope": _scope_response(scope, selected),
            "confidence": "needs-check" if unclassified_count else "verified",
            "caveat": "Audit is admin-only and for classification; it does not grant access by itself.",
        }
    except AccessPolicyError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def list_my_target_accounts(slack_user_email: str, limit: int = 20, query: str | None = None) -> dict[str, Any]:
    """List target accounts owned by the requesting AE."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked" or not scope.get("owner_id"):
            return _blocked("Slack email is not mapped to a HubSpot owner.", {"caller_email": slack_user_email})
        countries = list(scope["countries"])
        data = _company_search(_target_filters(countries, scope["owner_id"]), limit, query=query)
        accounts = [_summarize_company(company) for company in data.get("results", [])]
        return {
            "answer": accounts,
            "source": "HubSpot companies search",
            "scope": _scope_response(scope, countries),
            **_search_metadata(data),
            "confidence": "needs-check" if data.get("truncated") else "verified",
            "caveat": _coverage_caveat(data, "HubSpot target-account list."),
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def list_team_target_accounts(
    slack_user_email: str,
    countries: list[str] | None = None,
    limit: int = 50,
    owner_email: str | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    """List target accounts for an authorized manager/admin regional scope."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] not in TEAM_READ_SCOPE_KINDS:
            return _blocked("Caller is not authorized for team read scope.", {"caller_email": slack_user_email})
        selected = _safe_countries(countries, scope["countries"])
        if not selected:
            return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))
        target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)
        data = _company_search(_target_filters(selected, target_owner_id), limit, query=query)
        accounts = [_summarize_company(company) for company in data.get("results", [])]
        return {
            "answer": accounts,
            "source": "HubSpot companies search",
            "scope": _scope_response(scope, selected, target_owner_id, target_owner_email),
            **_search_metadata(data),
            "confidence": "needs-check" if data.get("truncated") else "verified",
            "caveat": _coverage_caveat(data, "Team read scope is country-based."),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def find_event_sourcing_target_accounts(
    slack_user_email: str,
    countries: list[str] | None = None,
    industry: str = "Food & Beverage",
    headcount_min: int = 21,
    headcount_max: int = 50,
    contact_role_filter: str = "owner_or_hr",
    deal_bucket: str = EVENT_SOURCING_DEFAULT_DEAL_BUCKET,
    owner_emails: list[str] | None = None,
    owner_names: list[str] | None = None,
    limit: int = EVENT_SOURCING_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Find read-only in-country AE target accounts for regional event sourcing."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        if scope["kind"] not in {"admin", "manager", "event_operator"}:
            return _blocked(
                "Event sourcing across AE accounts requires manager/admin or regional event-operator scope.",
                _scope_response(scope, list(scope.get("countries", ()))),
            )
        selected = _safe_countries(countries, scope["countries"])
        if not selected:
            return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))

        requested_limit = _bounded_int(limit, default=EVENT_SOURCING_DEFAULT_LIMIT, maximum=EVENT_SOURCING_RETURN_LIMIT)
        owner_ids, owner_rows, unresolved_owners = _event_sourcing_owner_scope(scope, selected, owner_emails, owner_names)
        requested_deal_bucket = _normalized_event_deal_bucket(deal_bucket)
        normalized_contact_filter = str(contact_role_filter or "owner_or_hr").strip().lower()
        if normalized_contact_filter not in EVENT_SOURCING_CONTACT_ROLE_FILTERS:
            normalized_contact_filter = "owner_or_hr"

        data = _company_search(
            _event_sourcing_target_filters(selected, owner_ids, _bounded_int(headcount_min, default=0, minimum=0), _bounded_int(headcount_max, default=0, minimum=0)),
            limit=max(requested_limit * 20, 100),
            maximum=EVENT_SOURCING_SCAN_LIMIT,
            sorts=[{"propertyName": "notes_last_updated", "direction": "DESCENDING"}],
        )
        companies = [
            company
            for company in data.get("results", [])
            if _event_industry_matches(company, industry)
            and _event_headcount_matches(company, _bounded_int(headcount_min, default=0, minimum=0), _bounded_int(headcount_max, default=0, minimum=0))
        ]
        company_ids = [str(company.get("id") or "") for company in companies if company.get("id")]
        contact_index = _batch_association_ids("companies", "contacts", company_ids[:EVENT_SOURCING_SCAN_LIMIT])
        deal_index = _batch_association_ids("companies", "deals", company_ids[:EVENT_SOURCING_SCAN_LIMIT])
        contact_detail_index = _safe_contact_index(contact_index)
        all_deal_ids = sorted({deal_id for deal_ids in deal_index.values() for deal_id in deal_ids})
        deals_by_id = {
            str(deal.get("id") or ""): deal
            for deal in _batch_read("deals", all_deal_ids, DEAL_PROPERTIES)
            if deal.get("id")
        }

        rows: list[dict[str, Any]] = []
        for company in companies:
            company_id = str(company.get("id") or "")
            contacts = contact_detail_index.get(company_id, [])
            contact_summary = _event_contact_role_summary(contacts)
            if not _event_contact_role_allowed(contact_summary, normalized_contact_filter):
                continue
            deals = [deals_by_id[deal_id] for deal_id in deal_index.get(company_id, []) if deal_id in deals_by_id]
            deal_summary = _event_deal_bucket(deals)
            if not _event_deal_bucket_allowed(deal_summary["deal_bucket"], requested_deal_bucket):
                continue
            company_summary = _summarize_company(company)
            missing_fields = list(company_summary.get("missing_fields") or [])
            if not company_summary.get("owner_email"):
                missing_fields.append("owner email")
            rows.append(
                {
                    "company_id": company_summary.get("company_id"),
                    "hubspot_scoped": True,
                    "scope_source": SCOPE_SOURCE,
                    "name": company_summary.get("name"),
                    "domain": company_summary.get("domain"),
                    "country": company_summary.get("country"),
                    "owner_id": company_summary.get("owner_id"),
                    "owner_email": company_summary.get("owner_email"),
                    "owner_name": company_summary.get("owner_name"),
                    "headcount": company_summary.get("headcount"),
                    "industry": company_summary.get("industry"),
                    "account_status": company_summary.get("account_status"),
                    "account_status_source": company_summary.get("account_status_source"),
                    **deal_summary,
                    **contact_summary,
                    "missing_fields": sorted(set(missing_fields)),
                    "recommended_ae_ask": "Ask the AE to validate the owner/HR contact and decide whether to invite for the event.",
                }
            )
        rows.sort(
            key=lambda row: (
                -_int_value(row.get("open_deal_count")),
                -(_int_value(row.get("owner_contact_count")) + _int_value(row.get("hr_contact_count"))),
                str(row.get("name") or ""),
            )
        )
        returned_rows = rows[:requested_limit]
        truncated = bool(data.get("truncated") or len(rows) > requested_limit or unresolved_owners)
        return {
            "answer": returned_rows,
            "source": "HubSpot target-account companies, runtime access-policy AE roster, associated contacts, and associated deals",
            "scope": {
                **_scope_response(scope, selected),
                "industry": industry,
                "headcount_min": _bounded_int(headcount_min, default=0, minimum=0),
                "headcount_max": _bounded_int(headcount_max, default=0, minimum=0),
                "contact_role_filter": normalized_contact_filter,
                "deal_bucket": requested_deal_bucket,
                "owner_count": len(owner_rows),
                "owners": owner_rows,
                "unresolved_owners": unresolved_owners,
            },
            "total": len(rows),
            "requested_limit": requested_limit,
            "returned_count": len(returned_rows),
            "scanned_count": len(companies),
            "has_more": truncated,
            "truncated": truncated,
            "will_mutate_hubspot": False,
            "confidence": "needs-check" if truncated else "verified",
            "caveat": (
                "Read-only regional event sourcing. Event operators can inspect in-country AE target-account candidates only through this tool. "
                "No HubSpot mutation, raw contact emails, phone numbers, task bodies, note bodies, communication bodies, or bulk exports are returned."
            ),
        }
    except (AccessPolicyError, ScopeError, MetricClarification) as error:
        return _blocked(str(error), {"caller_email": slack_user_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def find_target_accounts_by_luma_match_keys(
    slack_user_email: str,
    email_domains: list[str] | None = None,
    company_name_candidates: list[str] | None = None,
    countries: list[str] | None = None,
    limit: int = LUMA_MATCH_RETURN_LIMIT,
    owner_email: str | None = None,
) -> dict[str, Any]:
    """Find scoped HubSpot target accounts from safe Luma attendee match keys.

    Use after get_luma_event_match_keys. This avoids paging every target account
    for event-wide questions while still enforcing HubSpot target-account,
    country, owner, and caller scope before any Luma guest details are shown.
    """

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        if scope["kind"] not in MANAGER_ADMIN_SCOPE_KINDS | {"ae", "event_operator"}:
            return _blocked(
                "Event match-key account resolution requires manager/admin, AE, or regional event-operator scope.",
                _scope_response(scope, list(scope.get("countries", ()))),
            )
        selected = _safe_countries(countries, scope["countries"])
        if not selected:
            return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))
        target_owner_id, target_owner_email = _target_owner_id_for_luma_match_scope(scope, selected, owner_email)
        requested_limit = _bounded_int(limit, default=LUMA_MATCH_RETURN_LIMIT, maximum=LUMA_MATCH_RETURN_LIMIT)
        raw_domains = [domain for value in (email_domains or []) if (domain := _normalize_domain_key(value))]
        raw_names = [name for value in (company_name_candidates or []) if (name := _normalize_company_name_key(value))]
        domains = _unique_values(raw_domains)[:LUMA_MATCH_DOMAIN_LIMIT]
        names = _unique_values(raw_names)[:LUMA_MATCH_NAME_LIMIT]
        if not domains and not names:
            return _blocked("No safe Luma match keys were provided.", _scope_response(scope, selected, target_owner_id, target_owner_email))

        any_truncated = len(_unique_values(raw_domains)) > len(domains) or len(_unique_values(raw_names)) > len(names)
        base_filters = _target_filters(selected, target_owner_id)

        scoped_accounts = _company_search(
            base_filters,
            limit=LUMA_MATCH_SCAN_LIMIT,
            maximum=HUBSPOT_SEARCH_TOTAL_LIMIT,
            sorts=[{"propertyName": "name", "direction": "ASCENDING"}],
        )
        any_truncated = any_truncated or bool(scoped_accounts.get("truncated"))
        domain_keys = set(domains)
        candidates: dict[str, dict[str, Any]] = {}

        for company in scoped_accounts.get("results", []):
            props = company.get("properties", {})
            company_domain = _normalize_domain_key(props.get("domain") or company.get("domain"))
            if company_domain and company_domain in domain_keys:
                _add_luma_candidate(candidates, company, "exact_email_domain", company_domain, "verified")

            company_name = str(props.get("name") or company.get("name") or "")
            for name in names:
                if _luma_company_name_matches(company_name, name):
                    _add_luma_candidate(candidates, company, "company_name_candidate", name, "needs-check")

            if len(candidates) >= requested_limit:
                any_truncated = True
                break

        answer = [_compact_luma_candidate_summary(candidate) for candidate in list(candidates.values())[:requested_limit]]
        return {
            "answer": answer,
            "source": "HubSpot target-account lookup from Luma safe match keys",
            "scope": {
                **_scope_response(scope, selected, target_owner_id, target_owner_email),
                "email_domain_key_count": len(domains),
                "company_name_candidate_count": len(names),
                "scanned_target_account_count": scoped_accounts.get("returned_count", len(scoped_accounts.get("results", []))),
                "requested_limit": requested_limit,
            },
            "total": len(answer),
            "requested_limit": requested_limit,
            "returned_count": len(answer),
            "has_more": any_truncated or len(candidates) > requested_limit,
            "truncated": any_truncated or len(candidates) > requested_limit,
            "confidence": "needs-check"
            if any_truncated or any(account.get("luma_match_confidence") == "needs-check" for account in answer)
            else "verified",
            "caveat": (
                "This is event-first HubSpot scoping from safe Luma match keys. "
                "Domain matches are stronger; company-name candidates need review. "
                "No raw Luma attendees, match-key values, emails, phone numbers, or registration answers are returned."
            ),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def audit_priority_account_coverage(
    slack_user_email: str,
    countries: list[str] | None = None,
    owner_email: str | None = None,
    week_start: str = "",
    week_end: str = "",
    limit: int = PRIORITY_ACCOUNT_RETURN_LIMIT,
    soft_timeout_seconds: int = 0,
) -> dict[str, Any]:
    """Audit locked target-account coverage, double tap, stale/dirty accounts, and open follow-up tasks."""

    try:
        return _priority_account_coverage(
            slack_user_email=slack_user_email,
            countries=countries,
            owner_email=owner_email,
            week_start=week_start,
            week_end=week_end,
            limit=limit,
            soft_timeout_seconds=soft_timeout_seconds,
        )
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def build_sales_metric_actuals_query(
    slack_user_email: str,
    metric: str,
    start_date: str = "",
    end_date: str = "",
    snapshot_month: str = "",
    owner_email: str | None = None,
    owner_name: str | None = None,
    countries: list[str] | None = None,
    grain: str = "total",
) -> dict[str, Any]:
    """Build scoped, read-only BigQuery SQL for NurtureAny revenue metric actuals."""

    metric_key = _safe_metric(metric)
    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        if scope["kind"] not in MANAGER_ADMIN_SCOPE_KINDS | {"ae"}:
            return _blocked("Revenue funnel metrics require manager/admin or AE scope.", _scope_response(scope, list(scope.get("countries", ()))))
        selected = _safe_countries(countries, scope["countries"])
        if not selected:
            return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))

        if metric_key == "new_arr":
            return _metric_needs_check(
                "new ARR is ambiguous. Choose signed_converted_arr, paid_converted_arr, or new_mrr_movement_arr before querying.",
                _scope_response(scope, selected),
                metric_key,
            )
        if metric_key not in SALES_METRIC_DEFINITIONS:
            return _metric_needs_check(f"Unsupported revenue metric: {metric}.", _scope_response(scope, selected), metric_key)

        grain_key = _safe_grain(grain)
        requested_owner = _resolve_requested_owner(scope, selected, owner_email, owner_name)
        target_owner_id = requested_owner["owner_id"] if requested_owner else None
        target_owner_email = requested_owner["owner_email"] if requested_owner else ""
        target_owner_name = requested_owner["owner_name"] if requested_owner else ""
        scope_response = _scope_response(scope, selected, target_owner_id, target_owner_email)
        if target_owner_name:
            scope_response["target_owner_name"] = target_owner_name
        scope_response["metric"] = metric_key
        scope_response["source_class"] = SALES_METRIC_SOURCE_CLASS

        if metric_key == "qo_set":
            start_iso, end_iso = _date_range(start_date, end_date)
            owner_ids: list[str] = []
            if requested_owner:
                owner_ids = [requested_owner["owner_id"]]
            elif scope["kind"] in {"admin", "manager"}:
                owner_ids = _owner_ids_for_policy_countries(selected)
                if not owner_ids:
                    return _metric_needs_check(
                        "Country-scoped QO needs classified owner IDs because fct_sales_points has owner ID but no country column.",
                        scope_response,
                        metric_key,
                    )
            sql = _qo_sql(start_iso, end_iso, grain_key, owner_ids)
            package = _metric_query_package(metric_key, sql, scope_response, grain_key, start_iso, end_iso)

        elif metric_key in {"signed_converted_arr", "paid_converted_arr"}:
            start_iso, end_iso = _date_range(start_date, end_date)
            owner_names = [requested_owner["owner_name"]] if requested_owner else []
            sql = _converted_arr_sql(metric_key, start_iso, end_iso, grain_key, selected, owner_names)
            package = _metric_query_package(metric_key, sql, scope_response, grain_key, start_iso, end_iso)
            if owner_names:
                package["owner_filter_note"] = "Converted ARR table exposes deal_owner_name, not HubSpot owner ID."

        elif metric_key in {"new_mrr_movement_arr", "net_mrr_movement_arr"}:
            if requested_owner or scope["kind"] == "ae":
                return _metric_needs_check(
                    "MRR movement tables expose company country, not HubSpot owner ID. Use manager/admin country scope for this v1 query.",
                    scope_response,
                    metric_key,
                )
            start_iso, end_iso = _date_range(start_date, end_date)
            sql = _movement_arr_sql(metric_key, start_iso, end_iso, grain_key, selected)
            package = _metric_query_package(metric_key, sql, scope_response, grain_key, start_iso, end_iso)

        else:
            if requested_owner or scope["kind"] == "ae":
                return _metric_needs_check(
                    "Revenue snapshot tables expose company country, not HubSpot owner ID. Use manager/admin country scope for this v1 query.",
                    scope_response,
                    metric_key,
                )
            sql = _snapshot_sql(metric_key, snapshot_month, selected)
            package = _metric_query_package(metric_key, sql, scope_response, grain_key, snapshot_month=snapshot_month)

        return {
            "answer": package,
            "source": SALES_METRIC_SQL_SOURCE,
            "scope": scope_response,
            "confidence": "verified",
            "caveat": "Run the returned SQL only through staffany_bigquery.execute_sql_readonly. Rev planning Sheets/Slides are targets and definitions, not actuals.",
        }
    except MetricClarification as error:
        return _metric_needs_check(str(error), {"caller_email": slack_user_email}, metric_key)
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email, "owner_name": owner_name})
    except (AccessPolicyError, HubSpotError) as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def build_friday_sales_review(
    slack_user_email: str,
    countries: list[str] | None = None,
    owner_email: str | None = None,
    week_start: str = "",
    week_end: str = "",
    limit: int = PRIORITY_ACCOUNT_RETURN_LIMIT,
    soft_timeout_seconds: int = 0,
) -> dict[str, Any]:
    """Build the manager Friday sales review for the tactical pause operating rhythm."""

    try:
        deadline = _hubspot_soft_deadline(soft_timeout_seconds)
        coverage = _priority_account_coverage(
            slack_user_email=slack_user_email,
            countries=countries,
            owner_email=owner_email,
            week_start=week_start,
            week_end=week_end,
            limit=limit,
            manager_only=True,
            include_internal=True,
            soft_timeout_seconds=soft_timeout_seconds,
            deadline=deadline,
        )
        if coverage.get("confidence") == "blocked":
            return coverage

        internal = coverage.pop("_internal", {})
        owner_rows = coverage.get("answer", {}).get("owners", [])
        stage_config = _friday_review_stage_config()
        deal_counts = _deal_counts_for_friday(
            internal.get("companies", []),
            internal.get("company_deal_ids", {}),
            internal.get("week", {}),
            stage_config,
            deadline,
        )
        week = internal.get("week", {})
        owner_ids = sorted(
            {
                str(company.get("properties", {}).get("hubspot_owner_id") or "")
                for company in internal.get("companies", [])
                if str(company.get("properties", {}).get("hubspot_owner_id") or "")
            }
        )
        warehouse_followups = []
        if owner_ids and week.get("week_start") and week.get("week_end"):
            followup_scope = dict(coverage.get("scope", {}))
            followup_scope.update({"metric": "qo_set", "source_class": SALES_METRIC_SOURCE_CLASS})
            warehouse_followups.append(
                _metric_query_package(
                    "qo_set",
                    _qo_sql(week["week_start"], week["week_end"], "total", owner_ids),
                    followup_scope,
                    "total",
                    week["week_start"],
                    week["week_end"],
                )
            )
        answer = {
            "hygiene_summary": _friday_hygiene_summary(owner_rows),
            "funnel_snapshot": _friday_funnel_snapshot(owner_rows, deal_counts),
            "warehouse_metric_followups": warehouse_followups,
            "coaching_observations": _coaching_observations(owner_rows),
            "next_week_actions": _next_week_actions(owner_rows),
            "support_needed": _support_needed(coverage, deal_counts),
        }
        confidence = "verified"
        partial_due_to_soft_timeout = bool(
            coverage.get("partial_due_to_soft_timeout") or deal_counts.get("partial_due_to_soft_timeout")
        )
        if coverage.get("confidence") == "needs-check" or deal_counts.get("confidence") == "needs-check" or partial_due_to_soft_timeout:
            confidence = "needs-check"
        return {
            "answer": answer,
            "source": "HubSpot target-account coverage, safe calls/meetings/activity evidence, configured deal funnel stages, and optional C360 BigQuery QO actuals follow-up SQL",
            "scope": coverage.get("scope", {}),
            "total": coverage.get("total"),
            "requested_limit": coverage.get("requested_limit"),
            "returned_count": coverage.get("returned_count"),
            "has_more": coverage.get("has_more"),
            "truncated": coverage.get("truncated"),
            **_soft_timeout_metadata(partial_due_to_soft_timeout, soft_timeout_seconds),
            "confidence": confidence,
            "caveat": (
                coverage.get("caveat", "")
                + " "
                + deal_counts.get("caveat", "")
                + " Friday report follows tactical pause guardrails: 120/150 account coverage, double tap, 40 connected calls, warm activity proof, QO/QO Met guardrail, and next-week correction. Warehouse QO actuals require executing returned SQL through staffany_bigquery.execute_sql_readonly."
            ).strip(),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def build_hubspot_revenue_funnel_metrics(
    slack_user_email: str,
    start_date: str,
    end_date: str,
    countries: list[str] | None = None,
    owner_email: str | None = None,
    hubspot_team: str = "",
    business_type: str = "new_business",
    headcount_range: str = "",
    headcount_min: int = 0,
    headcount_max: int = 0,
    industries: list[str] | None = None,
    appointment_set_channel: str = "Sales Outbound",
    include_all_outbound: bool = False,
    manual_corrections: list[dict[str, Any]] | None = None,
    limit: int = REVENUE_FUNNEL_RETURN_LIMIT,
) -> dict[str, Any]:
    """Build read-only HubSpot created-cohort revenue funnel metrics with deal audit rows."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        if scope["kind"] not in MANAGER_ADMIN_SCOPE_KINDS | {"ae"}:
            return _blocked(
                "Revenue funnel metrics require manager/admin or AE scope.",
                _scope_response(scope, list(scope.get("countries", ()))),
            )
        selected = _safe_countries(countries, scope["countries"])
        if not selected:
            return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))
        start, end = _period_range(start_date, end_date)
        target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)
        requested_limit = _bounded_int(limit, default=REVENUE_FUNNEL_RETURN_LIMIT, maximum=REVENUE_FUNNEL_DEAL_SCAN_LIMIT)
        stage_config = _friday_review_stage_config()
        selected_channels = _selected_revenue_channels(appointment_set_channel, include_all_outbound)
        corrections = _manual_correction_index(manual_corrections)

        filters = [
            {"propertyName": "createdate", "operator": "GTE", "value": _hubspot_date_filter_value(start)},
            {"propertyName": "createdate", "operator": "LTE", "value": _hubspot_date_filter_value(end, end_of_day=True)},
        ]
        if target_owner_id:
            filters.append({"propertyName": "hubspot_owner_id", "operator": "EQ", "value": target_owner_id})
        new_business_pipelines = _env_csv(REVENUE_FUNNEL_NEW_BUSINESS_PIPELINE_IDS_ENV_VAR)
        if business_type.strip().lower().replace("-", "_").replace(" ", "_") in {"new_business", "new"} and new_business_pipelines:
            filters.append({"propertyName": "pipeline", "operator": "IN", "values": sorted(new_business_pipelines)})

        deal_data = _deal_search(filters, requested_limit, maximum=REVENUE_FUNNEL_DEAL_SCAN_LIMIT)
        raw_deals = deal_data.get("results", [])
        deal_ids = [str(deal.get("id") or "") for deal in raw_deals if deal.get("id")]
        deal_company_ids = _batch_association_ids("deals", "companies", deal_ids)
        company_ids = sorted({company_id for ids in deal_company_ids.values() for company_id in ids})
        companies = _batch_read("companies", company_ids, COMPANY_PROPERTIES)
        company_by_id = {str(company.get("id") or ""): company for company in companies}
        caveats: list[str] = []
        audit_rows: list[dict[str, Any]] = []
        excluded_counts = {
            "country": 0,
            "headcount": 0,
            "industry": 0,
            "channel": 0,
            "renewal": 0,
            "business_type": 0,
            "missing_company": 0,
        }

        if hubspot_team:
            caveats.append("hubspot_team filter is recorded in scope but not applied in V1 because HubSpot owner team metadata is not exposed consistently.")
        if not stage_config.get("configured"):
            caveats.append("QO, QO Met, and signed-deal counting need configured HubSpot stage IDs.")

        for deal in raw_deals:
            deal_id = str(deal.get("id") or "")
            company = None
            for company_id in deal_company_ids.get(deal_id, []):
                candidate = company_by_id.get(str(company_id))
                if candidate:
                    company = candidate
                    break
            company_props = (company or {}).get("properties", {})
            if company is None:
                excluded_counts["missing_company"] += 1
                continue
            if company_props.get("company_country") not in selected:
                excluded_counts["country"] += 1
                continue
            headcount_ok, headcount_caveat = _headcount_matches(company, headcount_range, headcount_min, headcount_max)
            if not headcount_ok:
                excluded_counts["headcount"] += 1
                if headcount_caveat and headcount_caveat not in caveats:
                    caveats.append(headcount_caveat)
                continue
            if not _industry_matches(company, industries):
                excluded_counts["industry"] += 1
                continue
            channel_ok, channel, channel_caveat = _deal_channel_matches(deal, selected_channels)
            if not channel_ok:
                excluded_counts["channel"] += 1
                if channel_caveat and channel_caveat not in caveats:
                    caveats.append(channel_caveat)
                continue
            if _deal_is_renewal(deal):
                excluded_counts["renewal"] += 1
                continue
            if business_type.strip().lower().replace("-", "_").replace(" ", "_") in {"new_business", "new"}:
                new_business, new_business_caveat = _deal_is_new_business(deal)
                if new_business_caveat and new_business_caveat not in caveats:
                    caveats.append(new_business_caveat)
                if not new_business:
                    excluded_counts["business_type"] += 1
                    continue

            row_caveats = []
            if deal_id in corrections:
                row_caveats.append("manual correction applied in this analysis only; HubSpot was not edited")
            audit_rows.append(
                _safe_revenue_deal_audit_row(
                    deal,
                    company,
                    stage_config,
                    corrections.get(deal_id),
                    channel,
                    row_caveats,
                )
            )

        summary = _revenue_funnel_summary(audit_rows)
        signed_days = [_days_to_signed(deal) for deal in raw_deals if _days_to_signed(deal) is not None]
        summary["avg_days_to_signed"] = round(sum(signed_days) / len(signed_days), 1) if signed_days else None
        summary["manual_correction_count"] = len(corrections)
        return {
            "answer": {
                "summary": summary,
                "deal_audit_rows": audit_rows[:REVENUE_FUNNEL_RETURN_LIMIT],
                "excluded_counts": excluded_counts,
                "rules_applied": {
                    "cohort": "HubSpot deal createdate between start_date and end_date",
                    "sales_outbound": "appointment-set channel must be Sales Outbound unless include_all_outbound=true",
                    "all_outbound": "all outbound uses outbound/cold-call/cold-email/LinkedIn/WhatsApp-outbound channel markers",
                    "headcount": "HubSpot company numberofemployees; >20 means at least 21 employees",
                    "new_business": "configured new-business pipeline IDs when present, otherwise renewal exclusion",
                    "renewal_exclusion": "configured renewal pipelines plus renewal markers in deal name/type",
                    "signed_deal": "configured closed-won stage IDs or manual correction",
                    "manual_corrections": "analysis-only overrides; no HubSpot mutation",
                },
            },
            "source": "HubSpot deals created-date cohort plus associated HubSpot companies; read-only",
            "scope": {
                **_scope_response(scope, selected, target_owner_id, target_owner_email),
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "hubspot_team": hubspot_team,
                "business_type": business_type,
                "headcount_range": headcount_range,
                "headcount_min": headcount_min,
                "headcount_max": headcount_max,
                "industries": industries or [],
                "appointment_set_channel": appointment_set_channel,
                "include_all_outbound": include_all_outbound,
            },
            **_search_metadata(deal_data),
            "will_mutate_hubspot": False,
            "confidence": "needs-check" if caveats or deal_data.get("truncated") else "verified",
            "caveat": " ".join(caveats) or "Read-only funnel metrics. No HubSpot edits, raw rows, communication bodies, or PII exports.",
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


def _ae_owner_fast_coaching_audit(
    slack_user_email: str,
    countries: list[str] | None,
    owner_email: str,
    week_start: str,
    week_end: str,
    include_call_content: bool,
    limit: int,
    soft_timeout_seconds: int,
    whatsapp_window_start_local: str,
    whatsapp_window_end_local: str,
    timezone_override_by_owner_email: dict[str, str] | None = None,
) -> dict[str, Any]:
    scope = _caller_scope(slack_user_email)
    if scope["kind"] == "blocked":
        return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
    if scope["kind"] not in {"admin", "manager"}:
        return _blocked("AE coaching audit is manager/admin only by default.", _scope_response(scope, list(scope.get("countries", ()))))
    selected = _safe_countries(countries, scope["countries"])
    if not selected:
        return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))

    target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)
    week = _week_window(week_start, week_end)
    company_data = _company_search(
        _target_filters(selected, target_owner_id),
        limit,
        maximum=AE_COACHING_DEFAULT_LIMIT,
        sorts=[{"propertyName": "hubspot_owner_id", "direction": "ASCENDING"}],
    )
    companies = company_data.get("results", [])
    owner_lookup = _owner_lookup_by_id()
    owner_display = _owner_display(target_owner_id or "", owner_lookup)
    if target_owner_email and not owner_display.get("owner_email"):
        owner_display["owner_email"] = target_owner_email
    row_owner_email = owner_display.get("owner_email") or target_owner_email or owner_email
    window = _coaching_window_contract(
        row_owner_email,
        timezone_override_by_owner_email,
        whatsapp_window_start_local,
        whatsapp_window_end_local,
        week["week_start"],
    )

    call_data = _list_sales_call_events_core(
        scope,
        selected,
        [str(target_owner_id or "")],
        week["start_dt"].astimezone(SINGAPORE_TIMEZONE).isoformat(),
        week["end_dt"].astimezone(SINGAPORE_TIMEZONE).isoformat(),
        week["timezone"],
        "ANY",
        "owner_level",
        limit=500,
    )
    calls = call_data.get("events", [])
    connected_call_count = sum(1 for call in calls if call.get("connected_call_120s_guardrail"))
    long_call_candidates = []
    for call in calls:
        if not call.get("completed_gt_60s"):
            continue
        candidate = {
            "call_id": str(call.get("object_id") or ""),
            "timestamp": call.get("timestamp_utc") or "",
            "duration_seconds": call.get("duration_seconds"),
            "appointment_evidence_status": "needs-check",
        }
        aircall_call_id = call.get("aircall_call_id") or ""
        if aircall_call_id:
            candidate["aircall_call_id"] = aircall_call_id
        long_call_candidates.append(candidate)

    time_filters = [
        {"propertyName": "hubspot_owner_id", "operator": "EQ", "value": target_owner_id},
        {"propertyName": "hs_timestamp", "operator": "GTE", "value": _task_datetime_filter_value(week["week_start"])},
        {"propertyName": "hs_timestamp", "operator": "LTE", "value": _task_datetime_filter_value(week["week_end"], True)},
    ]
    communication_data = _object_search("communications", time_filters, COMMUNICATION_PROPERTIES, limit=500, maximum=500)
    communication_evidence = []
    for communication in communication_data.get("results", []):
        if not _is_whatsapp_communication(communication):
            continue
        props = communication.get("properties", {})
        communication_evidence.append({"object_type": "communication", "timestamp": props.get("hs_timestamp") or ""})
    window_metrics = _whatsapp_window_metrics(communication_evidence, window)
    morning_message_count = window_metrics["in_window_message_count"]

    stage_config = _friday_review_stage_config()
    qo_set = None
    if stage_config.get("configured"):
        qo_filters = [
            {"propertyName": "hubspot_owner_id", "operator": "EQ", "value": target_owner_id},
            {"propertyName": "createdate", "operator": "GTE", "value": _hubspot_date_filter_value(_date_value(week["week_start"]) or date.today())},
            {"propertyName": "createdate", "operator": "LTE", "value": _hubspot_date_filter_value(_date_value(week["week_end"]) or date.today(), True)},
            {"propertyName": "dealstage", "operator": "IN", "values": sorted(stage_config["qo_stage_ids"])},
        ]
        if stage_config["pipeline_ids"]:
            qo_filters.append({"propertyName": "pipeline", "operator": "IN", "values": sorted(stage_config["pipeline_ids"])})
        qo_set = len(_deal_search(qo_filters, limit=500, maximum=500, properties=DEAL_PROPERTIES).get("results", []))

    focus = []
    if qo_set is None or qo_set < AE_COACHING_QO_WEEKLY_TARGET:
        focus.append("QO set below 3/week or stage config needs-check")
    if connected_call_count < CONNECTED_CALL_WEEKLY_TARGET:
        focus.append("connected calls below 40/week")
    if window["timezone_source"] in {"missing", "invalid"}:
        focus.append("rep timezone missing or invalid; local WhatsApp window audit needs-check")
    if morning_message_count < min(AE_COACHING_DEFAULT_LIMIT, len(companies)):
        focus.append("morning target-account message coverage needs-check")
    if long_call_candidates:
        focus.append("calls >60s need appointment-evidence review")

    row = {
        "ae_owner_id": target_owner_id,
        "ae_email": row_owner_email,
        "ae_name": owner_display.get("owner_name") or "",
        "week_start": week["week_start"],
        "week_end": week["week_end"],
        "qo_set": qo_set,
        "qo_weekly_target": AE_COACHING_QO_WEEKLY_TARGET,
        "qo_target_hit": bool(qo_set is not None and qo_set >= AE_COACHING_QO_WEEKLY_TARGET),
        "morning_message_account_count": "needs-check",
        "morning_whatsapp_metadata_count": morning_message_count,
        "morning_message_window": _coaching_window_label(window),
        "timezone": window["timezone"],
        "local_window": window["local_window"],
        "utc_window": window["utc_window"],
        "first_message_local": window_metrics["first_message_local"],
        "in_window_message_count": window_metrics["in_window_message_count"],
        "late_by_minutes": window_metrics["late_by_minutes"],
        "timezone_source": window["timezone_source"],
        "daily_nurture_plan_time_local": window["daily_nurture_plan_time_local"],
        "target_account_weekly_coverage": f"needs-check; locked pool {len(companies)}/{AE_COACHING_DEFAULT_LIMIT}",
        "connected_call_count": connected_call_count,
        "connected_call_target": CONNECTED_CALL_WEEKLY_TARGET,
        "connected_call_hit": connected_call_count >= CONNECTED_CALL_WEEKLY_TARGET,
        "long_call_without_appointment_candidates": long_call_candidates[:10],
        "call_content_status": "metadata-only needs-check" if include_call_content else "metadata-only",
        "coaching_focus": focus or ["operating rhythm on track"],
    }
    preview = {
        "AE": row["ae_email"] or row["ae_owner_id"],
        "Week": f"{row['week_start']} to {row['week_end']}",
        "QO set": row["qo_set"] if row["qo_set"] is not None else "needs-check",
        "Morning 150 coverage": f"needs-check ({morning_message_count} morning WhatsApp metadata)",
        "WhatsApp local window": row["morning_message_window"],
        "First WhatsApp local": row["first_message_local"] or "none",
        "In-window WhatsApp": row["in_window_message_count"],
        "Late by minutes": row["late_by_minutes"] if row["late_by_minutes"] is not None else "needs-check",
        "Connected calls": row["connected_call_count"],
        ">60s calls no appointment": len(long_call_candidates),
        "Coaching focus": "; ".join(row["coaching_focus"]),
    }
    truncated = bool(company_data.get("truncated") or call_data.get("truncated") or communication_data.get("truncated"))
    return {
        "answer": {
            "ae_weekly_checks": [row],
            "one_on_one_sheet_preview_rows": [preview],
            "will_mutate_google_sheets": False,
        },
        "source": "HubSpot target-account companies plus owner-level call and WhatsApp communication metadata",
        "scope": {
            **_scope_response(scope, selected, target_owner_id, target_owner_email),
            "week_start": week["week_start"],
            "week_end": week["week_end"],
            "timezone": week["timezone"],
            "whatsapp_local_window": window["local_window"],
            "whatsapp_utc_window": window["utc_window"],
            "owner_scoped_fast_path": True,
        },
        "total": 1,
        "requested_limit": limit,
        "returned_count": 1,
        "has_more": truncated,
        "truncated": truncated,
        "partial_due_to_soft_timeout": False,
        "soft_timeout_seconds": soft_timeout_seconds,
        "confidence": "needs-check",
        "caveat": "Owner-scoped fast path. It avoids account-association fanout by using owner-level activity metadata, so morning target-account coverage and appointment evidence remain needs-check. No call bodies, transcripts, recordings, Sheets writes, or HubSpot mutation.",
    }


@mcp.tool()
def build_ae_coaching_audit(
    slack_user_email: str,
    countries: list[str] | None = None,
    owner_email: str | None = None,
    week_start: str = "",
    week_end: str = "",
    include_call_content: bool = False,
    whatsapp_window_start_local: str = AE_COACHING_DEFAULT_WINDOW_START,
    whatsapp_window_end_local: str = AE_COACHING_DEFAULT_WINDOW_END,
    timezone_override_by_owner_email: dict[str, str] | None = None,
    limit: int = AE_COACHING_DEFAULT_LIMIT,
    soft_timeout_seconds: int = AE_COACHING_DEFAULT_SOFT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Build metadata-only AE weekly coaching rows without mutating Sheets."""

    try:
        effective_limit = _bounded_int(limit, default=AE_COACHING_DEFAULT_LIMIT, maximum=AE_COACHING_DEFAULT_LIMIT)
        effective_soft_timeout_seconds = _hubspot_soft_timeout_seconds(
            soft_timeout_seconds or AE_COACHING_DEFAULT_SOFT_TIMEOUT_SECONDS
        )
        if owner_email:
            return _ae_owner_fast_coaching_audit(
                slack_user_email,
                countries,
                owner_email,
                week_start,
                week_end,
                include_call_content,
                effective_limit,
                effective_soft_timeout_seconds,
                whatsapp_window_start_local,
                whatsapp_window_end_local,
                timezone_override_by_owner_email,
            )
        coverage = _priority_account_coverage(
            slack_user_email=slack_user_email,
            countries=countries,
            owner_email=owner_email,
            week_start=week_start,
            week_end=week_end,
            limit=effective_limit,
            manager_only=True,
            include_internal=True,
            soft_timeout_seconds=effective_soft_timeout_seconds,
        )
        if coverage.get("confidence") == "blocked":
            return coverage
        internal = coverage.pop("_internal", {})
        stage_config = _friday_review_stage_config()
        deal_counts = _deal_counts_for_friday(
            internal.get("companies", []),
            internal.get("company_deal_ids", {}),
            internal.get("week", {}),
            stage_config,
        )
        activity_index = internal.get("activity_index", {})
        companies = internal.get("companies", [])
        companies_by_owner: dict[str, list[dict[str, Any]]] = {}
        for company in companies:
            owner_id = str(company.get("properties", {}).get("hubspot_owner_id") or "")
            companies_by_owner.setdefault(owner_id, []).append(company)

        rows = []
        one_on_one_rows = []
        for owner_row in coverage.get("answer", {}).get("owners", []):
            owner_id = str(owner_row.get("owner_id") or "")
            owner_deals = deal_counts.get("by_owner", {}).get(owner_id, {})
            qo_set = owner_deals.get("qos") if deal_counts.get("configured") else None
            owner_companies = companies_by_owner.get(owner_id, [])
            row_owner_email = owner_row.get("owner_email") or _owner_email_by_id(owner_id)
            window = _coaching_window_contract(
                row_owner_email,
                timezone_override_by_owner_email,
                whatsapp_window_start_local,
                whatsapp_window_end_local,
                coverage.get("scope", {}).get("week_start") or "",
            )
            morning_account_count = 0
            owner_communication_evidence: list[dict[str, Any]] = []
            for company in owner_companies:
                company_id = str(company.get("id") or "")
                evidence = activity_index.get(company_id, {}).get("evidence", [])
                owner_communication_evidence.extend(
                    item for item in evidence if item.get("object_type") == "communication"
                )
                if any(_is_morning_whatsapp(item, window) for item in evidence):
                    morning_account_count += 1
            window_metrics = _whatsapp_window_metrics(owner_communication_evidence, window)
            call_candidates = _long_call_candidates_without_appointment(owner_id, owner_companies, activity_index)
            focus = []
            if qo_set is None or qo_set < AE_COACHING_QO_WEEKLY_TARGET:
                focus.append("QO set below 3/week or stage config needs-check")
            if owner_row.get("connected_call_count", 0) < CONNECTED_CALL_WEEKLY_TARGET:
                focus.append("connected calls below 40/week")
            if window["timezone_source"] in {"missing", "invalid"}:
                focus.append("rep timezone missing or invalid; local WhatsApp window audit needs-check")
            if morning_account_count < owner_row.get("weekly_account_target", 0):
                focus.append("morning target-account message coverage gap")
            if call_candidates:
                focus.append("calls >60s without appointment evidence")
            row = {
                "ae_owner_id": owner_id,
                "ae_email": owner_row.get("owner_email") or "",
                "ae_name": owner_row.get("owner_name") or "",
                "week_start": coverage.get("scope", {}).get("week_start"),
                "week_end": coverage.get("scope", {}).get("week_end"),
                "qo_set": qo_set,
                "qo_weekly_target": AE_COACHING_QO_WEEKLY_TARGET,
                "qo_target_hit": bool(qo_set is not None and qo_set >= AE_COACHING_QO_WEEKLY_TARGET),
                "morning_message_account_count": morning_account_count,
                "morning_message_window": _coaching_window_label(window),
                "timezone": window["timezone"],
                "local_window": window["local_window"],
                "utc_window": window["utc_window"],
                "first_message_local": window_metrics["first_message_local"],
                "in_window_message_count": window_metrics["in_window_message_count"],
                "late_by_minutes": window_metrics["late_by_minutes"],
                "timezone_source": window["timezone_source"],
                "daily_nurture_plan_time_local": window["daily_nurture_plan_time_local"],
                "target_account_weekly_coverage": owner_row.get("120_150_accounts_worked"),
                "connected_call_count": owner_row.get("connected_call_count", 0),
                "connected_call_target": CONNECTED_CALL_WEEKLY_TARGET,
                "connected_call_hit": owner_row.get("connected_call_count", 0) >= CONNECTED_CALL_WEEKLY_TARGET,
                "long_call_without_appointment_candidates": call_candidates,
                "call_content_status": "metadata-only needs-check" if include_call_content else "metadata-only",
                "coaching_focus": focus or ["operating rhythm on track"],
            }
            rows.append(row)
            one_on_one_rows.append(
                {
                    "AE": row["ae_email"] or row["ae_owner_id"],
                    "Week": f"{row['week_start']} to {row['week_end']}",
                    "QO set": row["qo_set"] if row["qo_set"] is not None else "needs-check",
                    "Morning 150 coverage": row["morning_message_account_count"],
                    "WhatsApp local window": row["morning_message_window"],
                    "First WhatsApp local": row["first_message_local"] or "none",
                    "In-window WhatsApp": row["in_window_message_count"],
                    "Late by minutes": row["late_by_minutes"] if row["late_by_minutes"] is not None else "needs-check",
                    "Connected calls": row["connected_call_count"],
                    ">60s calls no appointment": len(call_candidates),
                    "Coaching focus": "; ".join(row["coaching_focus"]),
                }
            )

        caveats = [
            "No Google Sheet mutation; rows are preview-only.",
            "Call content/transcripts/bodies are not read. Metadata-only candidates are needs-check until manager reviews call notes or recordings in approved systems.",
        ]
        if not deal_counts.get("configured"):
            caveats.append("QO set count needs configured HubSpot QO/QO Met stage IDs.")
        timezone_needs_check = any(row.get("timezone_source") in {"missing", "invalid"} for row in rows)
        if timezone_needs_check:
            caveats.append("One or more reps are missing a valid timezone; local WhatsApp timing remains needs-check.")
        return {
            "answer": {
                "ae_weekly_checks": rows,
                "one_on_one_sheet_preview_rows": one_on_one_rows,
                "will_mutate_google_sheets": False,
            },
            "source": "HubSpot target-account coverage, deals, calls, meetings, and WhatsApp communication metadata",
            "scope": {
                **coverage.get("scope", {}),
                "whatsapp_window_start_local": _time_label(
                    _parse_local_time(whatsapp_window_start_local, AE_COACHING_DEFAULT_WINDOW_START)
                ),
                "whatsapp_window_end_local": _time_label(
                    _parse_local_time(whatsapp_window_end_local, AE_COACHING_DEFAULT_WINDOW_END)
                ),
            },
            "total": len(rows),
            "requested_limit": coverage.get("requested_limit"),
            "returned_count": len(rows),
            "has_more": coverage.get("has_more"),
            "truncated": coverage.get("truncated"),
            "confidence": "needs-check"
            if include_call_content
            or coverage.get("confidence") == "needs-check"
            or not deal_counts.get("configured")
            or timezone_needs_check
            else "verified",
            "caveat": " ".join(caveats),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def prepare_sales_navigator_decision_maker_queue(
    slack_user_email: str,
    mode: str,
    countries: list[str] | None = None,
    owner_email: str | None = None,
    company_ids: list[str] | None = None,
    event_name: str = "",
    limit: int = 10,
) -> dict[str, Any]:
    """Prepare a safe manual Sales Navigator decision-maker handoff queue."""

    normalized_mode = str(mode or "").strip().lower()
    if normalized_mode not in {"pre_demo_150", "post_event_top10"}:
        return _blocked("mode must be pre_demo_150 or post_event_top10.", {"caller_email": slack_user_email, "mode": mode})
    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        selected = _safe_countries(countries, scope["countries"])
        if not selected:
            return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))
        target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)
        requested_limit = 10 if normalized_mode == "post_event_top10" else _bounded_int(limit, default=25, maximum=150)

        companies: list[dict[str, Any]] = []
        if company_ids:
            for company_id in company_ids[:150]:
                company = _assert_company_access(str(company_id), scope)
                if company.get("properties", {}).get("company_country") in selected:
                    companies.append(company)
        elif normalized_mode == "post_event_top10":
            return _blocked(
                "post_event_top10 requires attendee-linked scoped HubSpot company_ids from Luma/Sheet/event context.",
                _scope_response(scope, selected, target_owner_id, target_owner_email),
            )
        else:
            data = _company_search(
                _target_filters(selected, target_owner_id),
                requested_limit,
                maximum=150,
                sorts=[{"propertyName": "notes_last_updated", "direction": "DESCENDING"}],
            )
            companies = data.get("results", [])

        if normalized_mode == "post_event_top10":
            companies = [company for company in companies if _fnb_retail_company(company)]

        queue = []
        for company in companies:
            if len(queue) >= requested_limit:
                break
            company_id = str(company.get("id") or "")
            contact_ids = _association_ids("companies", company_id, "contacts", 50)
            contacts = [_safe_contact(contact) for contact in _batch_read("contacts", contact_ids, CONTACT_PROPERTIES)]
            ranked_contacts = []
            for contact in contacts:
                score, reason = _contact_role_priority(contact)
                if score <= 0:
                    continue
                ranked_contacts.append((score, reason, contact))
            ranked_contacts.sort(key=lambda item: (-item[0], str(item[2].get("display_name") or "")))
            props = company.get("properties", {})
            if ranked_contacts:
                for score, reason, contact in ranked_contacts[:3]:
                    queue.append(
                        {
                            "company_id": company_id,
                            "company_name": props.get("name") or "",
                            "country": props.get("company_country") or "",
                            "industry": props.get("industry") or "",
                            "owner_id": props.get("hubspot_owner_id") or "",
                            "contact_id": contact.get("contact_id"),
                            "display_name": contact.get("display_name") or "HubSpot contact",
                            "persona": contact.get("persona") or "",
                            "buying_role": contact.get("buying_role") or "",
                            "priority_score": score,
                            "priority_reason": reason,
                            "handoff_action": "Manually review this person/company in Sales Navigator; do not automate LinkedIn browsing.",
                            "next_enrichment": "Use search_exa_people_candidates or selected Lusha lookup only after scoped approval if HubSpot coverage is insufficient.",
                        }
                    )
                    if len(queue) >= requested_limit:
                        break
            else:
                queue.append(
                    {
                        "company_id": company_id,
                        "company_name": props.get("name") or "",
                        "country": props.get("company_country") or "",
                        "industry": props.get("industry") or "",
                        "owner_id": props.get("hubspot_owner_id") or "",
                        "contact_id": "",
                        "display_name": "decision-maker candidate needed",
                        "persona": "",
                        "buying_role": "",
                        "priority_score": 10,
                        "priority_reason": "no HubSpot role candidate found",
                        "handoff_action": "Use Sales Navigator manually to identify likely HR/Ops/Owner stakeholders.",
                        "next_enrichment": "Approved Exa People Search first; Lusha only for selected candidates with credit report.",
                    }
                )

        return {
            "answer": {
                "mode": normalized_mode,
                "event_name": event_name,
                "queue": queue[:requested_limit],
                "linkedin_scraping": False,
                "sales_navigator_browser_actions": False,
                "exa_cost_report": {"status": "not_called", "reason": "handoff queue only; use approved Exa tool for public candidate discovery"},
                "lusha_credit_report": {"status": "not_called", "reason": "handoff queue only; use approved Lusha tool for selected lookup/reveal"},
            },
            "source": "HubSpot scoped companies and contacts; Sales Navigator is manual handoff only",
            "scope": {
                **_scope_response(scope, selected, target_owner_id, target_owner_email),
                "mode": normalized_mode,
                "input_company_count": len(company_ids or []),
            },
            "total": len(queue[:requested_limit]),
            "requested_limit": requested_limit,
            "returned_count": len(queue[:requested_limit]),
            "has_more": len(queue) > requested_limit,
            "truncated": len(queue) > requested_limit,
            "will_mutate_hubspot": False,
            "confidence": "needs-check" if not queue or len(queue) > requested_limit else "verified",
            "caveat": "No LinkedIn scraping, no automated Sales Navigator browser action, no contact PII reveal, and no HubSpot mutation. Exa/Lusha/Prospeo are separate approved cost/credit-reporting flows.",
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def build_manager_chase_plan(
    slack_user_email: str,
    countries: list[str] | None = None,
    owner_email: str | None = None,
    company_ids: list[str] | None = None,
    week_start: str = "",
    week_end: str = "",
    slack_context_summary: str = "",
    slack_source_permalink: str = "",
    limit: int = MANAGER_CHASE_RETURN_LIMIT,
) -> dict[str, Any]:
    """Build copy-ready manager chase drafts from HubSpot evidence and selected Slack context."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] not in {"admin", "manager"}:
            return _blocked("Manager chase drafts require manager/admin scope.", {"caller_email": slack_user_email})

        requested_limit = _bounded_int(limit, default=MANAGER_CHASE_RETURN_LIMIT, maximum=MANAGER_CHASE_RETURN_LIMIT)
        safe_slack_context = _manager_chase_sentence(slack_context_summary, 500)
        safe_slack_permalink = str(slack_source_permalink or "").strip()
        rows: list[dict[str, Any]] = []
        selected_countries: list[str] = []
        metadata: dict[str, Any] = {
            "total": 0,
            "requested_limit": requested_limit,
            "returned_count": 0,
            "has_more": False,
            "truncated": False,
        }

        normalized_company_ids = _normalized_company_ids(company_ids)
        if normalized_company_ids:
            selected_company_ids = normalized_company_ids[:requested_limit]
            for company_id in selected_company_ids:
                context = _company_context(company_id, scope, task_limit=TASK_RETURN_LIMIT)
                if context is None:
                    raise ScopeError("One or more requested companies are outside caller scope or are not HubSpot target accounts.")
                country = context.get("company", {}).get("country") or ""
                if country and country not in selected_countries:
                    selected_countries.append(country)
                rows.extend(_manager_chase_rows_from_context(context, safe_slack_context, safe_slack_permalink))
            metadata = {
                "total": len(normalized_company_ids),
                "requested_limit": requested_limit,
                "returned_count": len(selected_company_ids),
                "has_more": len(normalized_company_ids) > requested_limit,
                "truncated": len(normalized_company_ids) > requested_limit,
            }
            scope_response = _scope_response(scope, selected_countries or list(scope.get("countries", ())))
        elif safe_slack_context and owner_email:
            selected_countries = _safe_countries(countries, scope["countries"]) or list(scope.get("countries", ()))
            target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)
            rep = {
                "owner_id": str(target_owner_id or ""),
                "owner_email": target_owner_email or _normalize_email(owner_email),
                "owner_name": "",
            }
            rows.append(
                _manager_chase_row(
                    rep=rep,
                    trigger="selected_slack_blocker",
                    evidence=(
                        f"Selected Slack context: {safe_slack_context}. "
                        f"HubSpot owner scope verified for {target_owner_email or owner_email}."
                    ),
                    ask="turn the selected blocker into a dated next step and log the outcome in HubSpot",
                    deadline="by EOD today",
                    fallback_action="use the selected Slack fallback action, call the stakeholder, and log yes/no/next date.",
                    source="HubSpot owner scope and selected Slack context",
                    source_permalink=safe_slack_permalink,
                )
            )
            scope_response = _scope_response(scope, selected_countries, target_owner_id, target_owner_email)
            metadata = {
                "total": len(rows),
                "requested_limit": requested_limit,
                "returned_count": len(rows),
                "has_more": False,
                "truncated": False,
            }
        else:
            coverage = _priority_account_coverage(
                slack_user_email=slack_user_email,
                countries=countries,
                owner_email=owner_email,
                week_start=week_start,
                week_end=week_end,
                limit=MANAGER_CHASE_COVERAGE_LIMIT,
                manager_only=True,
                include_internal=False,
            )
            if coverage.get("confidence") == "blocked":
                return coverage
            owner_rows = coverage.get("answer", {}).get("owners", [])
            for owner_row in owner_rows:
                rows.extend(_manager_chase_rows_from_owner(owner_row, safe_slack_context, safe_slack_permalink))
            scope_response = coverage.get("scope", _scope_response(scope, list(scope.get("countries", ()))))
            metadata = {
                "total": len(rows),
                "requested_limit": requested_limit,
                "returned_count": min(len(rows), requested_limit),
                "has_more": bool(coverage.get("has_more") or len(rows) > requested_limit),
                "truncated": bool(coverage.get("truncated") or len(rows) > requested_limit),
            }

        ranked_rows = _rank_manager_chase_rows(rows, requested_limit)
        confidence = "verified"
        if metadata.get("truncated") or any(row.get("confidence") == "needs-check" for row in ranked_rows):
            confidence = "needs-check"
        if not ranked_rows:
            confidence = "needs-check"

        return {
            "answer": {
                "chase_drafts": ranked_rows,
                "draft_count": len(ranked_rows),
                "delivery_mode": "manager_draft_only",
                "will_tag_reps": False,
                "will_send_external_messages": False,
                "will_mutate_hubspot": False,
            },
            "source": (
                "HubSpot priority-account coverage, sales-owned task/activity evidence, and selected Slack context pointer"
                if safe_slack_context
                else "HubSpot priority-account coverage and sales-owned task/activity evidence"
            ),
            "scope": scope_response,
            **metadata,
            "returned_count": len(ranked_rows),
            "confidence": confidence,
            "caveat": (
                "Manager draft only. HubSpot remains source of truth; selected Slack context shapes wording only. "
                "No raw Slack message dump, HubSpot body fields, external send, rep tag, or HubSpot mutation is performed."
            ),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email, "company_ids": company_ids})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def get_account_context(slack_user_email: str, company_id: str) -> dict[str, Any]:
    """Get safe account context for one scoped HubSpot company."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        context = _company_context(str(company_id), scope)
        if context is None:
            return _blocked("Company is outside caller scope.", {"caller_email": slack_user_email, "company_id": company_id})
        decision_status = context.get("coverage", {}).get("decision_maker_coverage", {}).get("status")
        account_packet = context.get("account_packet") or {}
        c360_sales_packet_status = (context.get("c360_sales_packet") or {}).get("status")
        source = "HubSpot company, contact, deal, and sales-owned task associations"
        if c360_sales_packet_status == "ok":
            source += " + Customer 360 sales packet"
        elif context["company"].get("c360_url"):
            source += " + Customer 360 link"
        confidence = "verified" if decision_status == "verified" and not context["company"].get("missing_fields") else "needs-check"
        if account_packet.get("confidence") == "needs-check":
            confidence = "needs-check"
        return {
            "answer": context,
            "source": source,
            "scope": _scope_response(scope, [context["company"]["country"]]),
            "confidence": confidence,
            "caveat": (
                account_packet.get("caveat")
                or "Contact details and sales-owned follow-up tasks are summarized; raw phone numbers, task bodies, and exports are omitted."
            ),
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "company_id": company_id})


@mcp.tool()
def build_pre_demo_game_plans(
    slack_user_email: str,
    company_ids: list[str],
    limit: int = PRE_DEMO_GAME_PLAN_ACCOUNT_LIMIT,
    source_slack_thread_url: str = "",
    source_url: str = "",
    include_public_research: bool = False,
    research_mode: str = "standard",
) -> dict[str, Any]:
    """Build game plans for selected HubSpot IDs, links, or exact company names."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})

        requested_limit = _bounded_int(limit, default=PRE_DEMO_GAME_PLAN_ACCOUNT_LIMIT, maximum=PRE_DEMO_GAME_PLAN_ACCOUNT_LIMIT)
        resolution = _resolve_pre_demo_company_refs(company_ids, scope, requested_limit)
        normalized_ids = resolution["company_ids"]
        if not normalized_ids and not resolution["ambiguous_matches"] and not resolution["not_found"]:
            return _blocked(
                "Provide selected HubSpot company IDs, company links, or exact company names before building pre-demo game plans.",
                {"caller_email": slack_user_email},
            )

        if resolution["ambiguous_matches"] or resolution["not_found"]:
            return {
                "answer": {
                    "message": "I could not safely resolve every selected account. Pick one of the scoped HubSpot company IDs below, or send a HubSpot company link.",
                    "resolved_matches": resolution["resolved_matches"],
                    "ambiguous_matches": resolution["ambiguous_matches"],
                    "not_found": resolution["not_found"],
                },
                "source": "HubSpot scoped target-account name search",
                "scope": _scope_response(scope, list(scope.get("countries", ()))),
                "total": resolution["input_count"],
                "requested_limit": requested_limit,
                "returned_count": 0,
                "has_more": resolution["truncated"],
                "truncated": resolution["truncated"],
                "missing_evidence": ["unresolved company selection"],
                "confidence": "blocked",
                "caveat": "Company-name matching is scoped to HubSpot target accounts and will not guess when the name is ambiguous or missing.",
            }

        selected_ids = normalized_ids[:requested_limit]
        contexts = []
        countries: list[str] = []
        source_thread = _slack_thread_source(source_slack_thread_url, source_url)
        for company_id in selected_ids:
            context = _company_context(company_id, scope)
            if context is None:
                raise ScopeError("One or more requested companies are outside caller scope or are not HubSpot target accounts.")
            country = context.get("company", {}).get("country")
            if country and country not in countries:
                countries.append(country)
            contexts.append(context)

        public_research_by_company, public_research_cost_report, public_research_missing = _public_research_for_game_plan_contexts(
            contexts,
            include_public_research,
            research_mode,
        )
        plans = [
            _build_pre_demo_game_plan_row(
                context,
                public_research_by_company.get(str(context.get("company", {}).get("company_id") or "")),
                source_thread=source_thread,
            )
            for context in contexts
        ]

        truncated = bool(resolution["truncated"])
        missing_evidence = sorted({item for plan in plans for item in plan.get("missing_evidence", [])} | set(public_research_missing))
        response = {
            "answer": plans,
            "source": "HubSpot scoped account context and NurtureAny pre-demo game-plan playbook",
            "scope": _scope_response(scope, countries or list(scope.get("countries", ()))),
            "total": resolution["input_count"],
            "requested_limit": requested_limit,
            "returned_count": len(plans),
            "has_more": truncated,
            "truncated": truncated,
            "resolved_matches": resolution["resolved_matches"],
            "missing_evidence": missing_evidence,
            "confidence": "needs-check" if truncated or missing_evidence else "verified",
            "will_mutate_hubspot": False,
            "caveat": (
                "On-demand Slack-first game plans only. Company names are resolved only against scoped HubSpot target accounts; ambiguous names require a pick. Pricing, current tool, lead source, meeting reason, and case studies are not invented; "
                "social/gated research stays manual-check unless user snippets are provided."
            ),
        }
        if source_thread:
            response["source_thread"] = source_thread
        if include_public_research:
            response["public_research"] = {
                "included": True,
                "research_mode": research_mode,
                "cost_report": public_research_cost_report,
                "will_mutate_hubspot": False,
                "caveat": "Public evidence only enriches the Research / stalking signal section and never overrides HubSpot fields.",
            }
        return response
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "company_ids": company_ids})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "company_ids": company_ids})


@mcp.tool()
def find_sales_case_studies(
    slack_user_email: str,
    company_ids: list[str] | None = None,
    sales_moment: str = "pre_demo",
    query: str = "",
    limit: int = CASE_STUDY_MATCH_LIMIT,
) -> dict[str, Any]:
    """Find approved case-study matches for scoped HubSpot accounts or a supplied brainstorm query."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})

        allowed_moments = {"knowledge_touch", "pre_demo", "demo", "post_demo_followup"}
        normalized_moment = str(sales_moment or "").strip().lower()
        if normalized_moment and normalized_moment not in allowed_moments:
            return _blocked(
                "sales_moment must be one of knowledge_touch, pre_demo, demo, or post_demo_followup.",
                {"sales_moment": sales_moment},
            )

        requested_limit = _bounded_int(limit, default=CASE_STUDY_MATCH_LIMIT, maximum=10)
        requested_company_ids = [str(company_id or "").strip() for company_id in (company_ids or []) if str(company_id or "").strip()]
        contexts: list[dict[str, Any]] = []
        countries: list[str] = []
        scoped_companies: list[dict[str, Any]] = []

        for company_id in requested_company_ids[:PRE_DEMO_GAME_PLAN_ACCOUNT_LIMIT]:
            context = _company_context(company_id, scope)
            if context is None:
                raise ScopeError("One or more requested companies are outside caller scope or are not HubSpot target accounts.")
            company = context.get("company", {})
            country = company.get("country")
            if country and country not in countries:
                countries.append(country)
            scoped_companies.append(
                {
                    "company_id": company.get("company_id"),
                    "name": company.get("name"),
                    "country": company.get("country"),
                    "industry": company.get("industry"),
                    "current_tools": company.get("current_tools"),
                }
            )
            contexts.append(context)

        if query.strip():
            contexts.append(
                {
                    "company": {
                        "name": query.strip(),
                        "country": "",
                        "industry": query.strip(),
                        "current_tools": query.strip(),
                        "account_status": "brainstorm",
                    }
                }
            )

        if not contexts:
            return _blocked(
                "Provide scoped HubSpot company_ids or a query before finding sales case studies.",
                {"caller_email": slack_user_email},
            )

        by_id: dict[str, dict[str, Any]] = {}
        for context in contexts:
            for match in _sales_case_study_matches(context, normalized_moment, requested_limit):
                match_id = str(match.get("id") or match.get("customer") or "")
                existing = by_id.get(match_id)
                if existing is None or _int_value(match.get("match_score")) > _int_value(existing.get("match_score")):
                    by_id[match_id] = match

        matches = sorted(by_id.values(), key=lambda match: (-_int_value(match.get("match_score")), str(match.get("customer") or "")))[:requested_limit]
        missing_evidence = [] if matches else ["case-study match needed"]
        return {
            "answer": {
                "case_study_matches": matches,
                "relevant_name_drops": [match.get("summary") for match in matches] if matches else ["case-study match needed"],
                "scoped_companies": scoped_companies,
                "sales_moment": normalized_moment or "any",
            },
            "source": "NurtureAny approved case-study catalog, including full-video-reviewed BMC podcast cards with bmc_podcast_full_video_review approval basis",
            "scope": _scope_response(scope, countries or list(scope.get("countries", ()))),
            "requested_limit": requested_limit,
            "returned_count": len(matches),
            "missing_evidence": missing_evidence,
            "confidence": "verified" if matches else "needs-check",
            "will_mutate_hubspot": False,
            "caveat": (
                "Read-only enrichment. HubSpot remains the source of truth for account facts; podcast cards are case-study analogies only. "
                "No strong match returns `case-study match needed`."
            ),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "company_ids": company_ids or []})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "company_ids": company_ids or []})


@mcp.tool()
def list_active_deals_missing_next_meeting(
    slack_user_email: str,
    countries: list[str] | None = None,
    owner_email: str | None = None,
    limit: int = ACTIVE_DEAL_HYGIENE_RETURN_LIMIT,
    soft_timeout_seconds: int = 0,
) -> dict[str, Any]:
    """List active scoped HubSpot target-account deals with no future meeting found."""

    try:
        deadline = _hubspot_soft_deadline(soft_timeout_seconds)
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})

        selected = _safe_countries(countries, scope["countries"])
        if not selected:
            return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))

        target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)
        requested_limit = _bounded_int(limit, default=ACTIVE_DEAL_HYGIENE_RETURN_LIMIT, maximum=ACTIVE_DEAL_HYGIENE_RETURN_LIMIT)
        company_scan_limit = min(PRIORITY_ACCOUNT_RETURN_LIMIT, max(requested_limit * 5, 100))
        data = _company_search(
            _target_filters(selected, target_owner_id),
            company_scan_limit,
            maximum=PRIORITY_ACCOUNT_RETURN_LIMIT,
            sorts=[{"propertyName": "hubspot_owner_id", "direction": "ASCENDING"}],
        )
        companies = data.get("results", [])
        company_by_id = {str(company.get("id") or ""): company for company in companies if company.get("id")}
        company_ids = list(company_by_id.keys())
        company_deal_ids = _batch_association_ids_until("companies", "deals", company_ids, deadline)
        partial_due_to_soft_timeout = _deadline_exceeded(deadline)

        deal_to_company_id: dict[str, str] = {}
        deal_ids: list[str] = []
        for company_id, associated_deal_ids in company_deal_ids.items():
            for deal_id in associated_deal_ids:
                if deal_id in deal_to_company_id:
                    continue
                deal_to_company_id[deal_id] = company_id
                deal_ids.append(deal_id)

        raw_deals = [] if partial_due_to_soft_timeout else _batch_read_until("deals", deal_ids, DEAL_PROPERTIES, deadline)
        partial_due_to_soft_timeout = bool(partial_due_to_soft_timeout or _deadline_exceeded(deadline))
        active_deals = [deal for deal in raw_deals if _deal_is_active_for_hygiene(deal)]
        active_deal_ids = [str(deal.get("id") or "") for deal in active_deals if deal.get("id")]
        meeting_index = (
            {"future_meeting_at_by_deal": {}, "truncated": True, "partial_due_to_soft_timeout": True}
            if partial_due_to_soft_timeout
            else _future_meeting_index_for_deals(active_deal_ids, deadline)
        )
        partial_due_to_soft_timeout = bool(partial_due_to_soft_timeout or meeting_index.get("partial_due_to_soft_timeout"))
        future_meeting_at_by_deal = meeting_index.get("future_meeting_at_by_deal", {})
        meeting_truncated = bool(meeting_index.get("truncated"))

        missing_rows: list[dict[str, Any]] = []
        for deal in active_deals:
            deal_id = str(deal.get("id") or "")
            if not deal_id or future_meeting_at_by_deal.get(deal_id):
                continue
            company = company_by_id.get(deal_to_company_id.get(deal_id, ""))
            if not company:
                continue
            missing_rows.append(_safe_active_deal_hygiene_row(deal, company, meeting_truncated))

        returned_rows = missing_rows[:requested_limit]
        metadata = _search_metadata(data)
        result_truncated = bool(
            metadata.get("truncated")
            or len(missing_rows) > requested_limit
            or meeting_truncated
            or partial_due_to_soft_timeout
        )
        return {
            "answer": returned_rows,
            "source": "HubSpot scoped target-account companies, associated deals, and associated future meetings",
            "scope": _scope_response(scope, selected, target_owner_id, target_owner_email),
            **metadata,
            "scanned_company_count": len(companies),
            "active_deal_count": len(active_deals),
            "missing_next_meeting_count": len(missing_rows),
            "returned_count": len(returned_rows),
            "has_more": result_truncated,
            "truncated": result_truncated,
            **_soft_timeout_metadata(partial_due_to_soft_timeout, soft_timeout_seconds),
            "confidence": "needs-check" if result_truncated else "verified",
            "caveat": (
                "Read-only deal hygiene. Active deal filtering excludes obvious closed-won/lost stage names only; "
                "future meeting evidence comes from HubSpot meeting associations and may need review when truncated."
            ),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def list_sales_followup_tasks(
    slack_user_email: str,
    company_ids: list[str] | None = None,
    countries: list[str] | None = None,
    limit: int = 50,
    owner_email: str | None = None,
    due_start: str = "",
    due_end: str = "",
) -> dict[str, Any]:
    """List existing incomplete sales-owned follow-up tasks for scoped HubSpot target accounts."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})

        requested_limit = _bounded_int(limit, default=50, maximum=TASK_RETURN_LIMIT)
        contexts: list[dict[str, Any]] = []
        metadata: dict[str, Any]
        selected = _safe_countries(countries, scope["countries"])
        target_owner_id = ""
        target_owner_email = ""

        if company_ids:
            account_limit = _bounded_int(requested_limit, default=50, maximum=50)
            for company_id in company_ids[:account_limit]:
                context = _company_context(str(company_id), scope, task_limit=TASK_RETURN_LIMIT)
                if context is None:
                    raise ScopeError("One or more requested companies are outside caller scope or are not HubSpot target accounts.")
                contexts.append(context)
            metadata = {
                "total": len(company_ids),
                "requested_limit": account_limit,
                "returned_count": len(contexts),
                "has_more": len(company_ids) > account_limit,
                "truncated": len(company_ids) > account_limit,
            }
        else:
            if not selected:
                return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))
            target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)
            return _list_sales_followup_tasks_from_task_search(
                scope,
                selected,
                requested_limit,
                target_owner_id,
                target_owner_email,
                due_start,
                due_end,
            )

        tasks = []
        task_truncated = bool(metadata.get("truncated"))
        for context in contexts:
            company = context["company"]
            task_truncated = task_truncated or bool(company.get("sales_followup_task_truncated"))
            for task in context.get("sales_followup_tasks", []):
                if not _task_due_in_window(task, due_start, due_end):
                    continue
                tasks.append(
                    {
                        "company_id": company.get("company_id"),
                        "company_name": company.get("name"),
                        "country": company.get("country"),
                        **task,
                    }
                )

        sorted_tasks = _sort_tasks_by_due_at(tasks)
        returned_tasks = sorted_tasks[:requested_limit]
        task_truncated = task_truncated or len(sorted_tasks) > requested_limit
        scope_response = _scope_response(scope, selected, target_owner_id, target_owner_email)
        if due_start:
            scope_response["due_start"] = due_start
        if due_end:
            scope_response["due_end"] = due_end
        return {
            "answer": returned_tasks,
            "source": "HubSpot sales-owned task associations",
            "scope": scope_response,
            **metadata,
            "task_count": len(sorted_tasks),
            "returned_task_count": len(returned_tasks),
            "task_truncated": task_truncated,
            "confidence": "needs-check" if task_truncated else "verified",
            "caveat": (
                "Existing incomplete sales-owned HubSpot tasks only. Safe task summaries omit task body and do not create or mutate tasks."
            ),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def preview_hubspot_sales_task(
    slack_user_email: str,
    company_id: str = "",
    company_name: str = "",
    subject: str = "",
    due_at: str = "",
    contact_id: str = "",
    deal_id: str = "",
    owner_email: str = "",
    source_summary: str = "",
    slack_permalink: str = "",
    priority: str = "HIGH",
    task_type: str = "TODO",
    approval_marker: str = "",
) -> dict[str, Any]:
    """Preview a scoped HubSpot sales task create payload. This tool does not mutate HubSpot."""

    try:
        preview = _build_sales_task_preview(
            slack_user_email=slack_user_email,
            company_id=company_id,
            company_name=company_name,
            subject=subject,
            due_at=due_at,
            contact_id=contact_id,
            deal_id=deal_id,
            owner_email=owner_email,
            source_summary=source_summary,
            slack_permalink=slack_permalink,
            priority=priority,
            task_type=task_type,
        )
        scope = preview["scope"]
        marker_ok = _is_task_approval_marker(approval_marker, TASK_CREATE_APPROVAL_MARKERS)
        return {
            "answer": {
                "operation": "create_hubspot_task",
                "will_mutate_hubspot": False,
                "company": _task_account_ref(preview["company"]),
                "contact_id": preview["contact_id"],
                "deal_id": preview["deal_id"],
                "owner_id": preview["owner_id"],
                "owner_email": preview["owner_email"],
                "properties": preview["preview_properties"],
                "association_type_ids": TASK_ASSOCIATION_TYPE_IDS,
                "duplicate_active_tasks": preview["duplicate_active_tasks"],
                "duplicate_suppressed": bool(preview["duplicate_active_tasks"]),
                "required_approval_markers": sorted(TASK_CREATE_APPROVAL_MARKERS),
                "approval_marker_received": _task_marker(approval_marker),
                "approval_ready": marker_ok and not preview["duplicate_active_tasks"],
            },
            "source": "NurtureAny HubSpot task create preview over scoped HubSpot target account",
            "scope": _scope_response(scope, list(scope.get("countries", ()))),
            "confidence": "needs-check" if preview["duplicate_active_tasks"] else "verified",
            "caveat": (
                "Preview only. HubSpot Task hs_timestamp is the due/reminder source; raw task bodies are not returned. "
                "Reply exactly `create task` or `confirm task` to approve creation."
            ),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "company_id": company_id, "company_name": company_name})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def create_approved_hubspot_sales_task(
    slack_user_email: str,
    company_id: str = "",
    company_name: str = "",
    subject: str = "",
    due_at: str = "",
    approval_marker: str = "",
    contact_id: str = "",
    deal_id: str = "",
    owner_email: str = "",
    source_summary: str = "",
    slack_permalink: str = "",
    priority: str = "HIGH",
    task_type: str = "TODO",
) -> dict[str, Any]:
    """Create one scoped HubSpot sales task after exact preview approval."""

    try:
        if not _is_task_approval_marker(approval_marker, TASK_CREATE_APPROVAL_MARKERS):
            return _blocked(
                "HubSpot task creation requires exact approval marker: create task or confirm task.",
                {"caller_email": slack_user_email, "approval_marker": _task_marker(approval_marker)},
            )
        preview = _build_sales_task_preview(
            slack_user_email=slack_user_email,
            company_id=company_id,
            company_name=company_name,
            subject=subject,
            due_at=due_at,
            contact_id=contact_id,
            deal_id=deal_id,
            owner_email=owner_email,
            source_summary=source_summary,
            slack_permalink=slack_permalink,
            priority=priority,
            task_type=task_type,
        )
        if preview["duplicate_active_tasks"]:
            return _blocked(
                "Duplicate active HubSpot task found for this scoped account, owner, subject, and due window.",
                {
                    "caller_email": slack_user_email,
                    "company": _task_account_ref(preview["company"]),
                    "duplicate_active_tasks": preview["duplicate_active_tasks"],
                },
            )
        created = _post(
            "/crm/v3/objects/tasks",
            {"properties": preview["properties"], "associations": preview["associations"]},
        )
        created_task = created if created.get("properties") else {"id": created.get("id"), "properties": preview["properties"]}
        created_task_id = str(created_task.get("id") or "")
        source_map = {created_task_id: [{"object_type": "company", "object_id": str(preview["company"].get("id") or "")}]}
        return {
            "answer": {
                "operation": "create_hubspot_task",
                "will_mutate_hubspot": True,
                "created_task": _safe_task_summary(created_task, source_map),
                "company": _task_account_ref(preview["company"]),
                "contact_id": preview["contact_id"],
                "deal_id": preview["deal_id"],
                "approval_marker": _task_marker(approval_marker),
            },
            "source": "HubSpot Tasks API POST /crm/v3/objects/tasks",
            "scope": _scope_response(preview["scope"], list(preview["scope"].get("countries", ()))),
            "confidence": "verified",
            "caveat": "Created one approved HubSpot Task. Task body was written as safe summary/provenance only and is not returned.",
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "company_id": company_id, "company_name": company_name})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def preview_hubspot_task_update(
    slack_user_email: str,
    task_id: str,
    action: str = "reschedule",
    due_at: str = "",
    company_id: str = "",
    approval_marker: str = "",
) -> dict[str, Any]:
    """Preview a scoped HubSpot task reschedule/reminder update or completion."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        context = _task_access_context(task_id, scope, company_id)
        normalized_action, properties, markers = _task_update_preview_properties(action, due_at)
        if normalized_action == "complete":
            marker_ok = _is_task_approval_marker(approval_marker, TASK_COMPLETE_APPROVAL_MARKERS)
        else:
            marker_ok = _is_task_approval_marker(approval_marker, TASK_RESCHEDULE_APPROVAL_MARKERS)
        links = context["links"]
        return {
            "answer": {
                "operation": f"{normalized_action}_hubspot_task",
                "will_mutate_hubspot": False,
                "task": _safe_task_summary(context["task"], {str(task_id): links.get("company_sources", {}).get(str(context["company"].get("id")), [])}),
                "company": _task_account_ref(context["company"]),
                "properties": properties,
                "required_approval_markers": markers,
                "approval_marker_received": _task_marker(approval_marker),
                "approval_ready": marker_ok,
            },
            "source": "NurtureAny HubSpot task update preview over scoped HubSpot target account",
            "scope": _scope_response(scope, list(scope.get("countries", ()))),
            "confidence": "verified",
            "caveat": "Preview only. Use exact approval marker before PATCH. `run`, `ok`, `yes`, `+1`, and `^` do not approve HubSpot task writes.",
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "task_id": task_id})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "task_id": task_id})


@mcp.tool()
def apply_approved_hubspot_task_update(
    slack_user_email: str,
    task_id: str,
    action: str = "reschedule",
    approval_marker: str = "",
    due_at: str = "",
    company_id: str = "",
) -> dict[str, Any]:
    """Apply an approved scoped HubSpot task reschedule/reminder update or completion."""

    try:
        normalized_action, properties, _markers = _task_update_preview_properties(action, due_at)
        if normalized_action == "complete":
            allowed = TASK_COMPLETE_APPROVAL_MARKERS
            marker_label = "mark done or complete task"
        else:
            allowed = TASK_RESCHEDULE_APPROVAL_MARKERS
            marker_label = "update task or confirm reminder"
        if not _is_task_approval_marker(approval_marker, allowed):
            return _blocked(
                f"HubSpot task {normalized_action} requires exact approval marker: {marker_label}.",
                {"caller_email": slack_user_email, "task_id": task_id, "approval_marker": _task_marker(approval_marker)},
            )
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        context = _task_access_context(task_id, scope, company_id)
        updated = _patch(
            f"/crm/v3/objects/tasks/{urllib.parse.quote(str(task_id), safe='')}",
            {"properties": properties},
        )
        updated_task = updated if updated.get("properties") else {
            "id": str(task_id),
            "properties": {**context["task"].get("properties", {}), **properties},
        }
        links = context["links"]
        return {
            "answer": {
                "operation": f"{normalized_action}_hubspot_task",
                "will_mutate_hubspot": True,
                "updated_task": _safe_task_summary(updated_task, {str(task_id): links.get("company_sources", {}).get(str(context["company"].get("id")), [])}),
                "company": _task_account_ref(context["company"]),
                "approval_marker": _task_marker(approval_marker),
                "updated_properties": properties,
            },
            "source": "HubSpot Tasks API PATCH /crm/v3/objects/tasks/{taskId}",
            "scope": _scope_response(scope, list(scope.get("countries", ()))),
            "confidence": "verified",
            "caveat": "Updated only approved HubSpot Task fields. Raw task body was not read or returned.",
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "task_id": task_id})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "task_id": task_id})


@mcp.tool()
def list_due_hubspot_sales_task_reminders(
    slack_user_email: str,
    mode: str = "morning",
    as_of: str = "",
    countries: list[str] | None = None,
    owner_email: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """List incomplete scoped HubSpot sales tasks due for reminder digest windows."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        selected = _safe_countries(countries, scope["countries"])
        if not selected:
            return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))
        normalized_mode = "eod" if _task_marker(mode) in {"eod", "end of day", "evening"} else "morning"
        local_as_of = _parse_task_reminder_as_of(as_of)
        today = local_as_of.date()
        include_tomorrow = normalized_mode == "morning"
        upper_due = today + timedelta(days=1 if include_tomorrow else 0)
        requested_limit = _bounded_int(limit, default=100, maximum=TASK_RETURN_LIMIT)
        target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)
        search_limit = min(TASK_SEARCH_RESULT_LIMIT, max(requested_limit * 5, 50))
        task_data = _task_search(_task_search_filters(target_owner_id, due_end=upper_due.isoformat()), search_limit)
        task_ids = [str(task.get("id") or "") for task in task_data.get("results", []) if task.get("id")]
        task_links = _task_company_links_for_tasks(task_ids)
        candidate_company_ids: list[str] = []
        for links in task_links.values():
            for linked_company_id in links.get("company_ids", []):
                if linked_company_id not in candidate_company_ids:
                    candidate_company_ids.append(linked_company_id)
        companies = {
            str(company.get("id")): company
            for company in _batch_read("companies", candidate_company_ids, COMPANY_PROPERTIES)
            if company.get("id")
        }
        buckets: dict[str, list[dict[str, Any]]] = {"overdue": [], "due_today": [], "due_tomorrow": []}
        seen_task_ids: set[str] = set()
        association_truncated = False
        for task in task_data.get("results", []):
            task_id = str(task.get("id") or "")
            if not task_id or task_id in seen_task_ids or not _is_incomplete_task(task):
                continue
            props = task.get("properties", {})
            bucket = _task_due_bucket(props.get("hs_timestamp"), today, include_tomorrow)
            if not bucket:
                continue
            links = task_links.get(task_id, {})
            association_truncated = association_truncated or bool(links.get("truncated"))
            task_owner_id = str(props.get("hubspot_owner_id") or "")
            for linked_company_id in links.get("company_ids", []):
                company = companies.get(str(linked_company_id))
                if not company or not _has_company_access(company, scope):
                    continue
                company_props = company.get("properties", {})
                if company_props.get("company_country") not in selected:
                    continue
                company_owner_id = str(company_props.get("hubspot_owner_id") or "")
                if target_owner_id and company_owner_id != str(target_owner_id):
                    continue
                if task_owner_id and company_owner_id != task_owner_id:
                    continue
                task_summary = _safe_task_summary(
                    task,
                    {task_id: links.get("company_sources", {}).get(str(linked_company_id), [])},
                )
                summary = _summarize_company(company)
                buckets[bucket].append(
                    {
                        "company_id": summary.get("company_id"),
                        "company_name": summary.get("name"),
                        "country": summary.get("country"),
                        "owner_email": summary.get("owner_email"),
                        **task_summary,
                    }
                )
                seen_task_ids.add(task_id)
                break

        total_tasks = sum(len(items) for items in buckets.values())
        truncated = bool(_search_metadata(task_data).get("truncated") or association_truncated or total_tasks > requested_limit)
        remaining = requested_limit
        returned_buckets: dict[str, list[dict[str, Any]]] = {}
        for bucket_name in ["overdue", "due_today", "due_tomorrow"]:
            sorted_items = _sort_tasks_by_due_at(buckets[bucket_name])
            returned_buckets[bucket_name] = sorted_items[:remaining]
            remaining = max(0, remaining - len(returned_buckets[bucket_name]))
        return {
            "answer": {
                "mode": normalized_mode,
                "date": today.isoformat(),
                "window": "overdue, due today, due tomorrow" if include_tomorrow else "overdue, due today",
                "buckets": returned_buckets,
                "total_task_count": total_tasks,
                "returned_task_count": sum(len(items) for items in returned_buckets.values()),
                "will_mutate_hubspot": False,
                "recurring_reminder_source": "HubSpot Task hs_timestamp; incomplete until hs_task_status=COMPLETED",
            },
            "source": "HubSpot Tasks API search over incomplete scoped sales-owned tasks",
            "scope": _scope_response(scope, selected, target_owner_id, target_owner_email),
            **_search_metadata(task_data),
            "task_truncated": truncated,
            "confidence": "needs-check" if truncated else "verified",
            "caveat": "Reminder read only. Native hs_task_reminders is optional UI nudge, not recurring reminder truth.",
        }
    except (ScopeError, ValueError) as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email or ""})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def audit_owner_whatsapp_kns_window(
    slack_user_email: str,
    owner_email: str = "",
    for_date: str = "",
    countries: list[str] | None = None,
    whatsapp_window_start_local: str = AE_COACHING_DEFAULT_WINDOW_START,
    whatsapp_window_end_local: str = AE_COACHING_DEFAULT_WINDOW_END,
    timezone_override_by_owner_email: dict[str, str] | None = None,
    limit: int = WHATSAPP_KNS_AUDIT_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Audit one owner's scoped target-account WhatsApp messages for KNS flags within a local window."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        if scope["kind"] not in {"admin", "manager"}:
            return _blocked(
                "KNS WhatsApp body checks require manager/admin scope.",
                {"caller_email": slack_user_email, "owner_email": owner_email},
            )

        selected_countries = _safe_countries(countries, scope["countries"])
        if not selected_countries:
            return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))

        target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email or None)
        if not target_owner_id:
            return _blocked(
                "Provide owner_email for manager/admin WhatsApp KNS window audits.",
                _scope_response(scope, selected_countries),
            )

        reference_date = (_date_value(for_date) or datetime.now(SINGAPORE_TIMEZONE).date()).isoformat()
        window = _coaching_window_contract(
            target_owner_email or owner_email,
            timezone_override_by_owner_email,
            whatsapp_window_start_local,
            whatsapp_window_end_local,
            reference_date,
        )
        if window["timezone_source"] in {"missing", "invalid"} or not window["utc_window"]:
            return {
                "answer": {
                    "owner_email": target_owner_email or owner_email,
                    "owner_id": target_owner_id,
                    "date": reference_date,
                    "target_account_whatsapp_sent_count": "needs-check",
                    "messages_missing_kns_count": "needs-check",
                    "messages_missing_kns": [],
                    "all_target_account_messages": [],
                    "count_status": "blocked_timezone_missing_or_invalid",
                    "kns_status": "not_checked",
                    "will_mutate_hubspot": False,
                },
                "source": "HubSpot scoped target-account WhatsApp communications; query not executed because local window could not be converted to UTC",
                "scope": {
                    **_scope_response(scope, selected_countries, target_owner_id, target_owner_email),
                    "for_date": reference_date,
                    "whatsapp_local_window": window["local_window"],
                    "whatsapp_utc_window": window["utc_window"],
                    "timezone_source": window["timezone_source"],
                },
                "total": 0,
                "requested_limit": limit,
                "returned_count": 0,
                "has_more": False,
                "truncated": False,
                "confidence": "needs-check",
                "caveat": (
                    "The owner's timezone is missing or invalid in the runtime access policy and no explicit override was provided. "
                    "Set the rep timezone in the NurtureAny access policy, or pass timezone_override_by_owner_email for this run. "
                    "Slack and HubSpot owner records are identity sources, not the timezone source of truth."
                ),
            }

        requested_limit = _bounded_int(limit, default=WHATSAPP_KNS_AUDIT_DEFAULT_LIMIT, maximum=1000)
        communication_filters = [
            {"propertyName": "hubspot_owner_id", "operator": "EQ", "value": target_owner_id},
            {"propertyName": "hs_timestamp", "operator": "GTE", "value": window["utc_window"]["start"]},
            {"propertyName": "hs_timestamp", "operator": "LTE", "value": window["utc_window"]["end"]},
        ]
        communication_data = _object_search(
            "communications",
            communication_filters,
            COMMUNICATION_EVENT_PROPERTIES,
            limit=requested_limit,
            maximum=1000,
            sorts=[{"propertyName": "hs_timestamp", "direction": "ASCENDING"}],
        )
        owner_whatsapp_messages = [
            communication for communication in communication_data.get("results", []) if _is_whatsapp_communication(communication)
        ]
        owner_whatsapp_ids = [str(communication.get("id") or "") for communication in owner_whatsapp_messages if communication.get("id")]

        company_data = _company_search(
            _target_filters(selected_countries, target_owner_id),
            requested_limit,
            maximum=HUBSPOT_SEARCH_TOTAL_LIMIT,
            sorts=[{"propertyName": "name", "direction": "ASCENDING"}],
        )
        companies = company_data.get("results", [])
        company_by_id = {str(company.get("id") or ""): company for company in companies if company.get("id")}
        company_ids = list(company_by_id.keys())
        selected_company_ids = set(company_ids)
        contact_to_companies = _reverse_company_association_index(_batch_association_ids("companies", "contacts", company_ids))
        deal_to_companies = _reverse_company_association_index(_batch_association_ids("companies", "deals", company_ids))
        comm_company_index = _batch_association_ids("communications", "companies", owner_whatsapp_ids)
        comm_contact_index = _batch_association_ids("communications", "contacts", owner_whatsapp_ids)
        comm_deal_index = _batch_association_ids("communications", "deals", owner_whatsapp_ids)

        target_linked_messages: list[dict[str, Any]] = []
        target_company_ids_with_whatsapp: set[str] = set()
        for communication in owner_whatsapp_messages:
            communication_id = str(communication.get("id") or "")
            if not communication_id:
                continue
            associated_target_company_ids: set[str] = set()
            source_by_key: dict[tuple[str, str], dict[str, str]] = {}

            def add_source(source_type: str, source_id: str, company_ids_for_source: list[str]) -> None:
                matched_company_ids = [source_company_id for source_company_id in company_ids_for_source if source_company_id in selected_company_ids]
                if not matched_company_ids:
                    return
                source_key = (source_type, str(source_id))
                source_by_key.setdefault(source_key, {"object_type": source_type, "object_id": str(source_id)})
                associated_target_company_ids.update(matched_company_ids)

            for company_id in comm_company_index.get(communication_id, []):
                if company_id in selected_company_ids:
                    add_source("company", str(company_id), [str(company_id)])
            for contact_id in comm_contact_index.get(communication_id, []):
                add_source("contact", str(contact_id), contact_to_companies.get(str(contact_id), []))
            for deal_id in comm_deal_index.get(communication_id, []):
                add_source("deal", str(deal_id), deal_to_companies.get(str(deal_id), []))
            if not associated_target_company_ids:
                continue

            props = communication.get("properties", {})
            timestamp = _activity_timestamp(communication)
            timestamp_dt = _datetime_value(timestamp)
            kns = _whatsapp_kns_audit_from_body(props.get("hs_communication_body"))
            target_company_ids = sorted(associated_target_company_ids)
            target_company_ids_with_whatsapp.update(target_company_ids)
            safe_message = {
                **_safe_followup_evidence("communication", communication, {communication_id: list(source_by_key.values())}),
                "timestamp_local": timestamp_dt.astimezone(window["zone"]).isoformat() if timestamp_dt and window["zone"] else "",
                "target_company_ids": target_company_ids,
                "target_accounts": [
                    {
                        "company_id": company_id,
                        "company_name": company_by_id.get(company_id, {}).get("properties", {}).get("name") or "",
                    }
                    for company_id in target_company_ids
                ],
                **kns,
            }
            target_linked_messages.append(safe_message)

        target_linked_messages = sorted(
            target_linked_messages,
            key=lambda item: _datetime_value(str(item.get("timestamp") or "")) or datetime.min.replace(tzinfo=timezone.utc),
        )
        messages_missing_kns = [message for message in target_linked_messages if message.get("kns_status") != "pass"]
        body_unavailable_count = sum(1 for message in target_linked_messages if not message.get("body_available"))
        truncated = bool(company_data.get("truncated") or communication_data.get("truncated"))
        return {
            "answer": {
                "owner_email": target_owner_email or owner_email,
                "owner_id": target_owner_id,
                "date": reference_date,
                "timezone": window["timezone"],
                "timezone_source": window["timezone_source"],
                "local_window": window["local_window"],
                "utc_window": window["utc_window"],
                "owner_whatsapp_sent_count": len(owner_whatsapp_messages),
                "target_account_whatsapp_sent_count": len(target_linked_messages),
                "target_account_count_scanned": len(companies),
                "target_account_count_with_whatsapp": len(target_company_ids_with_whatsapp),
                "messages_missing_kns_count": len(messages_missing_kns),
                "body_unavailable_count": body_unavailable_count,
                "messages_missing_kns": messages_missing_kns,
                "all_target_account_messages": target_linked_messages,
                "raw_bodies_returned": False,
                "will_mutate_hubspot": False,
            },
            "source": "HubSpot owner-level WhatsApp communications plus scoped target-account association mapping; raw WhatsApp bodies read only internally for KNS flags",
            "scope": {
                **_scope_response(scope, selected_countries, target_owner_id, target_owner_email),
                "for_date": reference_date,
                "whatsapp_local_window": window["local_window"],
                "whatsapp_utc_window": window["utc_window"],
                "timezone_source": window["timezone_source"],
            },
            "total": communication_data.get("total"),
            "requested_limit": requested_limit,
            "returned_count": len(owner_whatsapp_messages),
            "has_more": truncated,
            "truncated": truncated,
            "confidence": "needs-check",
            "caveat": (
                "KNS classification is heuristic and returns flags only; raw WhatsApp bodies are omitted from output. "
                "Rows with missing body text remain body_unavailable and need manual review in HubSpot Conversations or Eazybe."
            ),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})


@mcp.tool()
def count_owner_whatsapp_sent_today(
    slack_user_email: str,
    owner_email: str = "",
    for_date: str = "",
    countries: list[str] | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    """Count today's HubSpot WhatsApp communications for one owner's scoped target accounts."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})

        selected_countries = _safe_countries(countries, scope["countries"])
        if not selected_countries:
            return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))

        target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email or None)
        if not target_owner_id:
            return _blocked(
                "Provide owner_email for manager/admin WhatsApp sent-today checks.",
                _scope_response(scope, selected_countries),
            )

        day = _singapore_day_window(for_date)
        requested_limit = _bounded_int(limit, default=500, maximum=1000)
        communication_filters = [
            {"propertyName": "hubspot_owner_id", "operator": "EQ", "value": target_owner_id},
            {"propertyName": "hs_timestamp", "operator": "GTE", "value": day["start_dt"].isoformat().replace("+00:00", "Z")},
            {"propertyName": "hs_timestamp", "operator": "LTE", "value": day["end_dt"].isoformat().replace("+00:00", "Z")},
        ]
        communication_data = _object_search(
            "communications",
            communication_filters,
            COMMUNICATION_PROPERTIES,
            limit=requested_limit,
            maximum=1000,
            sorts=[{"propertyName": "hs_timestamp", "direction": "DESCENDING"}],
        )
        owner_whatsapp_messages = [
            communication for communication in communication_data.get("results", []) if _is_whatsapp_communication(communication)
        ]
        owner_whatsapp_ids = [str(communication.get("id") or "") for communication in owner_whatsapp_messages if communication.get("id")]

        company_data = _company_search(
            _target_filters(selected_countries, target_owner_id),
            requested_limit,
            maximum=HUBSPOT_SEARCH_TOTAL_LIMIT,
            sorts=[{"propertyName": "name", "direction": "ASCENDING"}],
        )
        companies = company_data.get("results", [])
        company_ids = [str(company.get("id") or "") for company in companies if company.get("id")]
        contact_index = _batch_association_ids("companies", "contacts", company_ids)
        deal_index = _batch_association_ids("companies", "deals", company_ids)
        selected_company_ids = set(company_ids)
        contact_to_companies = _reverse_company_association_index(contact_index)
        deal_to_companies = _reverse_company_association_index(deal_index)
        comm_company_index = _batch_association_ids("communications", "companies", owner_whatsapp_ids)
        comm_contact_index = _batch_association_ids("communications", "contacts", owner_whatsapp_ids)
        comm_deal_index = _batch_association_ids("communications", "deals", owner_whatsapp_ids)

        target_linked_messages: list[dict[str, Any]] = []
        target_company_ids_with_whatsapp: set[str] = set()
        for communication in owner_whatsapp_messages:
            communication_id = str(communication.get("id") or "")
            if not communication_id:
                continue
            associated_target_company_ids: set[str] = set()
            sources: list[dict[str, str]] = []
            for company_id in comm_company_index.get(communication_id, []):
                if company_id in selected_company_ids:
                    associated_target_company_ids.add(company_id)
                    sources.append({"object_type": "company", "object_id": company_id})
            for contact_id in comm_contact_index.get(communication_id, []):
                for company_id in contact_to_companies.get(str(contact_id), []):
                    associated_target_company_ids.add(company_id)
                    sources.append({"object_type": "contact", "object_id": str(contact_id)})
            for deal_id in comm_deal_index.get(communication_id, []):
                for company_id in deal_to_companies.get(str(deal_id), []):
                    associated_target_company_ids.add(company_id)
                    sources.append({"object_type": "deal", "object_id": str(deal_id)})
            if not associated_target_company_ids:
                continue
            target_company_ids_with_whatsapp.update(associated_target_company_ids)
            target_linked_messages.append(_safe_followup_evidence("communication", communication, {communication_id: sources}))

        target_linked_messages = _sort_followup_evidence(target_linked_messages)
        owner_messages = _sort_followup_evidence(
            [_safe_followup_evidence("communication", communication, {str(communication.get("id") or ""): []}) for communication in owner_whatsapp_messages]
        )
        latest_sent_at = owner_messages[0]["timestamp"] if owner_messages else ""
        truncated = bool(company_data.get("truncated") or communication_data.get("truncated"))
        return {
            "answer": {
                "owner_email": target_owner_email or owner_email or scope.get("email"),
                "owner_id": target_owner_id,
                "date": day["date"],
                "timezone": day["timezone"],
                "whatsapp_sent_count": len(owner_messages),
                "target_account_whatsapp_sent_count": len(target_linked_messages),
                "target_account_count_scanned": len(companies),
                "target_account_count_with_whatsapp": len(target_company_ids_with_whatsapp),
                "latest_sent_at": latest_sent_at,
                "sample_evidence": owner_messages[:10],
                "target_account_sample_evidence": target_linked_messages[:10],
                "will_mutate_hubspot": False,
            },
            "source": "HubSpot owner-level WhatsApp communications metadata, with scoped target-account association mapping",
            "scope": {
                **_scope_response(scope, selected_countries, target_owner_id, target_owner_email),
                "for_date": day["date"],
                "timezone": day["timezone"],
                "start_at": day["start_dt"].isoformat(),
                "end_at": day["end_dt"].isoformat(),
                "fast_path": "owner_day_communications_first",
            },
            "total": communication_data.get("total"),
            "requested_limit": requested_limit,
            "returned_count": len(owner_whatsapp_messages),
            "has_more": truncated,
            "truncated": truncated,
            "confidence": "needs-check" if truncated else "verified",
            "caveat": (
                "Fast path counts owner-level HubSpot WhatsApp communications metadata for the selected day, then separately maps "
                "which records are associated to scoped target accounts. It skips calls, tasks, notes, meetings, Friday review scoring, and raw WhatsApp bodies."
            ),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def check_account_followup_status(
    slack_user_email: str,
    company_ids: list[str],
    since_at: str,
    until_at: str = "",
    limit: int = 50,
) -> dict[str, Any]:
    """Check safe HubSpot follow-up status for selected scoped target accounts."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})

        since_dt = _datetime_value(since_at)
        if not since_dt:
            return _blocked("Provide a valid since_at timestamp for follow-up status checks.", {"caller_email": slack_user_email})
        until_dt = _datetime_value(until_at) if until_at else None
        if until_at and not until_dt:
            return _blocked("Provide a valid until_at timestamp or omit it.", {"caller_email": slack_user_email})
        if until_dt and until_dt < since_dt:
            return _blocked("until_at must be after since_at.", {"caller_email": slack_user_email})

        normalized_ids = _normalized_company_ids(company_ids)
        if not normalized_ids:
            return _blocked(
                "Provide selected HubSpot company IDs or company links before checking follow-up status.",
                {"caller_email": slack_user_email},
            )

        requested_limit = _bounded_int(limit, default=50, maximum=50)
        selected_ids = normalized_ids[:requested_limit]
        companies: list[dict[str, Any]] = []
        countries: list[str] = []
        for company_id in selected_ids:
            company = _assert_company_access(company_id, scope)
            companies.append(company)
            company_country = str(company.get("properties", {}).get("company_country") or "")
            if company_country and company_country not in countries:
                countries.append(company_country)

        contact_index = _batch_association_ids("companies", "contacts", selected_ids)
        deal_index = _batch_association_ids("companies", "deals", selected_ids)
        activity_index = _followup_activity_index_for_companies(companies, contact_index, deal_index, since_dt, until_dt)
        rows = [
            _account_followup_status_from_index(
                company,
                activity_index.get(str(company.get("id") or ""), _empty_followup_activity()),
            )
            for company in companies
        ]

        truncated = len(normalized_ids) > requested_limit
        needs_check = truncated or any(row.get("confidence") == "needs-check" for row in rows)
        scope_response = _scope_response(scope, countries or list(scope.get("countries", ())))
        scope_response["since_at"] = since_at
        if until_at:
            scope_response["until_at"] = until_at

        return {
            "answer": rows,
            "source": "HubSpot WhatsApp communications, notes, tasks, and scoped associations",
            "scope": scope_response,
            "total": len(normalized_ids),
            "requested_limit": requested_limit,
            "returned_count": len(rows),
            "has_more": truncated,
            "truncated": truncated,
            "confidence": "needs-check" if needs_check else "verified",
            "caveat": (
                "Read-only follow-up status. WhatsApp is read from HubSpot communications; raw WhatsApp bodies, note bodies, "
                "task bodies, phone numbers, unmatched event attendees, and secrets are omitted."
            ),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "company_ids": company_ids})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


def _event_followup_context(event: dict[str, Any], event_tags: list[str] | None) -> dict[str, Any]:
    return {
        "event": event,
        "event_tags": event_tags or [],
        "read_body_internal_only": True,
    }


def _event_status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"followed_up": 0, "scheduled": 0, "not_found": 0, "needs_check": 0}
    for row in rows:
        status = str(row.get("followup_status") or "needs_check")
        counts[status if status in counts else "needs_check"] += 1
    return counts


def _apply_attendance_match_quality(row: dict[str, Any], match: dict[str, Any]) -> dict[str, Any]:
    safe_row = dict(row)
    safe_row["event_attendance_match"] = {
        "match_confidence": match.get("match_confidence") or "needs-check",
        "match_reasons": match.get("match_reasons") or [],
        "attended_match_count": match.get("attended_match_count") or 0,
    }
    if match.get("match_confidence") == "needs-check":
        safe_row["followup_status"] = "needs_check"
        safe_row["confidence"] = "needs-check"
        safe_row["caveat"] = (
            "Attendance matched by candidate company-name evidence; HubSpot follow-up evidence is safe, but account match needs review."
        )
    return safe_row


def _event_country_scope(scope: dict[str, Any], country: str, location: str, event_tags: list[str] | None) -> list[str]:
    filters = _resolved_event_filters(country, "", location)
    selected_country = filters["country"]
    if not selected_country:
        for tag in event_tags or []:
            selected_country = _canonical_country(tag) or selected_country
            if selected_country:
                break
    return _safe_countries([selected_country] if selected_country else None, scope["countries"])


@mcp.tool()
def check_event_followup_status(
    slack_user_email: str,
    event_tags: list[str] | None = None,
    event_id: str = "",
    location: str = "",
    country: str = "",
    event_type: str = "",
    start: str = "",
    end: str = "",
    owner_email: str | None = None,
    since_at: str = "",
    until_at: str = "",
    limit: int = 50,
) -> dict[str, Any]:
    """Resolve Luma attendance, then check event-specific HubSpot/Eazybe follow-up status."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        selected_countries = _event_country_scope(scope, country, location, event_tags)
        if not selected_countries:
            return _blocked("Requested event country/location is outside caller scope.", _scope_response(scope, []))
        target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)

        requested_limit = _bounded_int(limit, default=50, maximum=200)
        normalized_event_tags = _event_tag_filters(event_tags, country, event_type, location)
        events_has_more = False
        events_truncated = False
        if event_id:
            event = _single_luma_event(str(event_id).strip())
        else:
            events, events_has_more, events_truncated = _list_luma_events_for_followup(
                "",
                start,
                end,
                country,
                event_type,
                location,
                event_tags,
            )
            event = _latest_luma_event(events)
            if not event:
                return _blocked(
                    "No matching Luma event found for the requested tags/window.",
                    {
                        **_scope_response(scope, selected_countries, target_owner_id, target_owner_email),
                        "event_tag_filters": normalized_event_tags,
                    },
                )

        event_start = _datetime_value(str(event.get("start_at") or ""))
        event_end = _datetime_value(str(event.get("end_at") or "")) or event_start
        since_dt = _datetime_value(since_at) or event_end
        if not since_dt:
            return _blocked(
                "Could not determine event end time; provide since_at.",
                {
                    **_scope_response(scope, selected_countries, target_owner_id, target_owner_email),
                    "event_id": event.get("event_id") or event_id,
                },
            )
        until_dt = _datetime_value(until_at) if until_at else None
        if until_at and not until_dt:
            return _blocked("Provide a valid until_at timestamp or omit it.", {"caller_email": slack_user_email})
        if until_dt and until_dt < since_dt:
            return _blocked("until_at must be after since_at.", {"caller_email": slack_user_email})

        guests, guests_has_more, guests_truncated = _list_luma_guests(str(event.get("event_id") or event_id))
        match_data = _matched_event_companies(guests, scope, selected_countries, target_owner_id)
        matches = match_data["matches"]
        matched_company_ids = sorted(matches.keys())
        selected_company_ids = matched_company_ids[:requested_limit]
        rows: list[dict[str, Any]] = []
        event_context = _event_followup_context(event, normalized_event_tags)
        for company_id in selected_company_ids:
            match = matches[company_id]
            company = match["company"]
            contact_ids = _association_ids("companies", company_id, "contacts", 50)
            deal_ids = _association_ids("companies", company_id, "deals", 20)
            row = _account_followup_status(company, contact_ids, deal_ids, since_dt, until_dt, event_context)
            rows.append(_apply_attendance_match_quality(row, match))

        truncated = (
            len(matched_company_ids) > requested_limit
            or bool(events_truncated)
            or bool(guests_truncated)
            or any(row.get("activity_truncated") for row in rows)
        )
        candidate_match = any(match.get("match_confidence") == "needs-check" for match in matches.values())
        unmatched_attendees = match_data["unmatched_attended_guest_count"] > 0
        needs_check = truncated or candidate_match or unmatched_attendees or any(row.get("confidence") == "needs-check" for row in rows)
        scope_response = _scope_response(scope, selected_countries, target_owner_id, target_owner_email)
        scope_response.update(
            {
                "event_tag_filters": normalized_event_tags,
                "event_id": event.get("event_id") or event_id,
                "since_at": since_dt.isoformat().replace("+00:00", "Z"),
            }
        )
        if until_at:
            scope_response["until_at"] = until_at

        return {
            "answer": {
                "event": event,
                "matched_target_account_count": len(matched_company_ids),
                "status_counts": _event_status_counts(rows),
                "accounts": rows,
                "match_summary": {
                    "attended_guest_count": match_data["attended_guest_count"],
                    "matched_guest_count": match_data["matched_guest_count"],
                    "unmatched_attended_guest_count": match_data["unmatched_attended_guest_count"],
                    "verified_match_count": match_data["verified_match_count"],
                    "candidate_match_count": match_data["candidate_match_count"],
                    "events_has_more": events_has_more,
                    "guests_has_more": guests_has_more,
                },
            },
            "source": "Luma checked-in attendance plus HubSpot/Eazybe WhatsApp communications, tasks, notes, and scoped associations",
            "scope": scope_response,
            "total": len(matched_company_ids),
            "requested_limit": requested_limit,
            "returned_count": len(rows),
            "has_more": len(matched_company_ids) > requested_limit or events_has_more or guests_has_more,
            "truncated": truncated,
            "confidence": "needs-check" if needs_check else "verified",
            "caveat": (
                "Read-only event follow-up status. WhatsApp bodies are inspected only inside the classifier for event-specific matching and are never returned; "
                "raw attendee lists, guest emails, phone numbers, note bodies, task bodies, and secrets are omitted."
            ),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except LumaEventError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "source": "Luma"})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def score_nurture_accounts(
    slack_user_email: str,
    company_ids: list[str] | None = None,
    countries: list[str] | None = None,
    limit: int = 20,
    owner_email: str | None = None,
) -> dict[str, Any]:
    """Score scoped target accounts for nurture priority."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})

        contexts: list[dict[str, Any]] = []
        metadata: dict[str, Any]
        selected = _safe_countries(countries, scope["countries"])
        target_owner_id = ""
        target_owner_email = ""
        if company_ids:
            requested_limit = _bounded_int(limit, default=20, maximum=50)
            for company_id in company_ids[:requested_limit]:
                context = _company_context(str(company_id), scope)
                if context is None:
                    raise ScopeError("One or more requested companies are outside caller scope or are not HubSpot target accounts.")
                contexts.append(context)
            metadata = {
                "total": len(company_ids),
                "requested_limit": requested_limit,
                "returned_count": len(contexts),
                "has_more": len(company_ids) > requested_limit,
                "truncated": len(company_ids) > requested_limit,
            }
        else:
            target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)
            data = _company_search(_target_filters(selected, target_owner_id), limit)
            metadata = _search_metadata(data)
            for company in data.get("results", []):
                summary = _summarize_company(company)
                task_context = _sales_followup_task_context(company, task_limit=5)
                summary.update(task_context["signals"])
                contexts.append(
                    {
                        "company": summary,
                        "contacts": [],
                        "deals": [],
                        "sales_followup_tasks": task_context["tasks"],
                        "coverage": {},
                    }
                )

        ranked = []
        for context in contexts:
            company = context["company"]
            score = _score_company(company)
            ranked.append({**company, **score})
        ranked.sort(key=lambda item: item["priority_score"], reverse=True)
        task_truncated = any(item.get("sales_followup_task_truncated") for item in ranked)
        return {
            "answer": ranked,
            "source": "HubSpot account context scoring",
            "scope": _scope_response(scope, selected, target_owner_id, target_owner_email),
            **metadata,
            "confidence": "needs-check"
            if metadata.get("truncated") or task_truncated or any(item.get("missing_fields") for item in ranked)
            else "verified",
            "caveat": _coverage_caveat(
                {**metadata, "truncated": bool(metadata.get("truncated") or task_truncated)},
                "Scoring uses HubSpot fields only unless C360/Luma context is separately supplied.",
            ),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})



def _singapore_lead_enrichment_deps() -> dict[str, Any]:
    return {
        "blocked": _blocked,
        "bounded_int": _bounded_int,
        "caller_scope": _caller_scope,
        "coverage": _coverage,
        "coverage_caveat": _coverage_caveat,
        "batch_association_ids": _batch_association_ids,
        "batch_read": _batch_read,
        "company_search": _company_search,
        "contact_properties": CONTACT_PROPERTIES,
        "get_company": _get_company,
        "safe_contact": _safe_contact,
        "scope_response": _scope_response,
        "score_company": _score_company,
        "search_metadata": _search_metadata,
        "short_text": _short_text,
        "summarize_company_with_contacts": _summarize_company_with_contacts,
        "target_filters": _target_filters,
        "target_owner_id_for_scope": _target_owner_id_for_scope,
        "buckets": SINGAPORE_LEAD_ENRICHMENT_BUCKETS,
        "country": SINGAPORE_LEAD_ENRICHMENT_COUNTRY,
        "default_batch_size": SINGAPORE_LEAD_ENRICHMENT_DEFAULT_BATCH_SIZE,
        "default_limit": SINGAPORE_LEAD_ENRICHMENT_DEFAULT_LIMIT,
        "max_limit": SINGAPORE_LEAD_ENRICHMENT_MAX_LIMIT,
        "normalized_words": _normalized_words,
        "phone_sources": PHONE_VERIFICATION_SOURCES,
        "phone_stale_after_days": PHONE_VERIFICATION_DEFAULT_STALE_AFTER_DAYS,
        "phone_statuses": PHONE_VERIFICATION_STATUSES,
        "pilot_metrics": SINGAPORE_LEAD_ENRICHMENT_PILOT_METRICS,
        "provider_jobs": SINGAPORE_LEAD_ENRICHMENT_PROVIDER_JOBS,
        "scope_source": SCOPE_SOURCE,
        "source_ladder": SINGAPORE_LEAD_ENRICHMENT_SOURCE_LADDER,
    }


@mcp.tool()
def build_singapore_lead_enrichment_plan(
    slack_user_email: str,
    owner_email: str | None = None,
    company_ids: list[str] | None = None,
    limit: int | None = None,
    batch_size: int = SINGAPORE_LEAD_ENRICHMENT_DEFAULT_BATCH_SIZE,
    phone_stale_after_days: int = PHONE_VERIFICATION_DEFAULT_STALE_AFTER_DAYS,
    output_mode: str = "full",
) -> dict[str, Any]:
    """Build a review-first SG lead-enrichment plan for HubSpot companies before WhatsApp nurture."""

    try:
        return _sg_lead_enrichment.build_singapore_lead_enrichment_plan(
            slack_user_email,
            deps=_singapore_lead_enrichment_deps(),
            owner_email=owner_email,
            company_ids=company_ids,
            limit=limit,
            batch_size=batch_size,
            phone_stale_after_days=phone_stale_after_days,
            output_mode=output_mode,
        )
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email, "company_ids": company_ids or []})


@mcp.tool()
def find_contact_gaps(
    slack_user_email: str,
    countries: list[str] | None = None,
    limit: int = 50,
    owner_email: str | None = None,
) -> dict[str, Any]:
    """Find target accounts missing contact, persona, channel, or decision-maker coverage."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        selected = _safe_countries(countries, scope["countries"])
        if not selected:
            return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))
        target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)
        data = _company_search(_target_filters(selected, target_owner_id), limit)
        companies = data.get("results", [])
        company_ids = [str(company.get("id") or "") for company in companies if company.get("id")]
        contact_index = _batch_association_ids("companies", "contacts", company_ids)
        contact_detail_index = _safe_contact_index(contact_index)

        gaps = []
        for company in companies:
            company_id = str(company.get("id") or "")
            contacts = contact_detail_index.get(company_id, [])
            contact_count = len(contact_index.get(company_id, []))
            summary = _summarize_company_with_contacts(company, contacts, contact_count)
            missing = list(summary.get("missing_fields", []))
            gap_fields = {"associated contact", "decision maker", "persona", "channel fit"}
            if any(field in missing for field in gap_fields) or summary.get("enrichment_status") != "nurture_ready":
                gaps.append(
                    {
                        "company_id": summary.get("company_id"),
                        "name": summary.get("name"),
                        "country": summary.get("country"),
                        "enrichment_status": summary.get("enrichment_status"),
                        "missing_fields": missing,
                        "associated_contact_count": summary.get("associated_contact_count"),
                        "decision_maker_count": summary.get("decision_maker_count"),
                        "buying_role_contact_count": summary.get("buying_role_contact_count"),
                        "role_inferred_decision_maker_candidate_count": summary.get(
                            "role_inferred_decision_maker_candidate_count"
                        ),
                        "decision_maker_coverage": summary.get("decision_maker_coverage"),
                    }
                )
        metadata = _search_metadata(data)
        return {
            "answer": gaps,
            "source": "HubSpot target-account companies plus associated contact role and buying-role fields",
            "scope": _scope_response(scope, selected, target_owner_id, target_owner_email),
            "gap_count": len(gaps),
            "scored_account_count": metadata.get("returned_count", len(companies)),
            **metadata,
            "confidence": "needs-check" if metadata.get("truncated") or gaps else "verified",
            "caveat": _coverage_caveat(
                data,
                "Raw contact details are omitted; this is a coverage summary from HubSpot contact associations, persona fields, channel fit, and buying roles.",
            ),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def find_t90_renewal_gaps(
    slack_user_email: str,
    countries: list[str] | None = None,
    limit: int = HUBSPOT_SEARCH_TOTAL_LIMIT,
    owner_email: str | None = None,
    include_followup_tasks: bool = True,
    include_missing_renewal_dates: bool = True,
    missing_contract_end_date_limit: int = T90_MISSING_CONTRACT_END_DATE_DEFAULT_LIMIT,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Find T-90 renewal target accounts and renewal-date classification gaps."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})

        selected = _safe_countries(countries, scope["countries"])
        if not selected:
            return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))

        target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)
        requested_limit = _bounded_int(limit, default=HUBSPOT_SEARCH_TOTAL_LIMIT, maximum=HUBSPOT_SEARCH_TOTAL_LIMIT)
        requested_missing_contract_end_date_limit = _bounded_int(
            missing_contract_end_date_limit,
            default=T90_MISSING_CONTRACT_END_DATE_DEFAULT_LIMIT,
            maximum=HUBSPOT_SEARCH_TOTAL_LIMIT,
        )
        today = datetime.now(timezone.utc).date()
        window_start = _date_value(start_date) or today
        window_end = _date_value(end_date) or today + timedelta(days=90)
        if window_end < window_start:
            return _blocked(
                "end_date must be on or after start_date.",
                {"caller_email": slack_user_email, "start_date": start_date, "end_date": end_date},
            )
        data = _company_search_by_renewal_window(selected, target_owner_id, window_start, window_end, requested_limit)
        missing_data = (
            _company_search_missing_renewal_dates(
                selected,
                target_owner_id,
                requested_missing_contract_end_date_limit,
            )
            if include_missing_renewal_dates
            else {
                "results": [],
                "total": 0,
                "requested_limit": requested_missing_contract_end_date_limit,
                "returned_count": 0,
                "has_more": False,
                "truncated": False,
            }
        )

        task_index: dict[str, list[dict[str, Any]]] = {}
        task_metadata: dict[str, Any] = {}
        task_truncated = False
        task_lookup_skipped = False
        if include_followup_tasks and target_owner_id:
            task_context = _sales_followup_task_index_for_companies(
                data.get("results", []),
                target_owner_id,
                TASK_SEARCH_AIRTIGHT_RESULT_LIMIT,
            )
            task_index = task_context.get("tasks_by_company", {})
            task_metadata = task_context.get("metadata", {})
            task_truncated = bool(task_context.get("truncated"))
        elif include_followup_tasks:
            task_lookup_skipped = True

        renewing_company_ids = [str(company.get("id") or "") for company in data.get("results", []) if company.get("id")]
        renewing_contact_index = _batch_association_ids("companies", "contacts", renewing_company_ids)
        renewing_contact_detail_index = _safe_contact_index(renewing_contact_index)
        renewing_accounts = []
        gap_accounts = []
        for company in data.get("results", []):
            company_id = str(company.get("id") or "")
            summary = _summarize_company_with_contacts(
                company,
                renewing_contact_detail_index.get(company_id, []),
                len(renewing_contact_index.get(company_id, [])),
            )
            company_id = str(summary.get("company_id") or "")
            renewal_matches = _renewal_matches_in_window(company, window_start, window_end)
            if not renewal_matches:
                continue
            primary_renewal = renewal_matches[0]
            renewal = primary_renewal["date"]
            days_until_renewal = (renewal - today).days

            tasks = task_index.get(company_id, [])
            missing = list(summary.get("missing_fields", []))
            gap_reasons: list[str] = []
            if summary.get("enrichment_status") != "nurture_ready":
                gap_reasons.append(f"not nurture-ready ({summary.get('enrichment_status')})")
            if "decision maker" in missing:
                gap_reasons.append("missing decision-maker coverage")
            if include_followup_tasks and not task_lookup_skipped:
                if task_truncated and not tasks:
                    gap_reasons.append("open sales-owned follow-up not verified because task lookup was truncated")
                elif not task_truncated and not tasks:
                    gap_reasons.append("no open sales-owned follow-up found")

            score_input = dict(summary)
            score_input.update(_sales_followup_signals(tasks, task_truncated))
            next_due = score_input.get("next_sales_followup_due_at") or ""
            row = {
                "company_id": company_id,
                "hubspot_scoped": True,
                "scope_source": SCOPE_SOURCE,
                "name": summary.get("name"),
                "country": summary.get("country"),
                "owner_id": summary.get("owner_id"),
                "owner_email": summary.get("owner_email"),
                "owner_name": summary.get("owner_name"),
                "account_status": summary.get("account_status"),
                "account_status_source": summary.get("account_status_source"),
                "contract_end_date": summary.get("contract_end_date"),
                "current_tool_renewal_date": summary.get("current_tool_renewal_date"),
                "current_tools": summary.get("current_tools"),
                "contract_or_renewal_date": primary_renewal["value"],
                "renewal_source_of_truth": RENEWAL_SOURCE_OF_TRUTH_PROPERTY,
                "current_tools_source_of_truth": CURRENT_TOOLS_SOURCE_OF_TRUTH_PROPERTY,
                "days_until_renewal": days_until_renewal,
                "renewal_match_fields": [match["property_name"] for match in renewal_matches],
                "renewal_matches": [
                    {"property_name": match["property_name"], "value": match["value"]}
                    for match in renewal_matches
                ],
                "enrichment_status": summary.get("enrichment_status"),
                "missing_fields": missing,
                "decision_maker_count": summary.get("decision_maker_count"),
                "verified_decision_maker_count": summary.get("verified_decision_maker_count"),
                "buying_role_contact_count": summary.get("buying_role_contact_count"),
                "role_inferred_decision_maker_candidate_count": summary.get(
                    "role_inferred_decision_maker_candidate_count"
                ),
                "decision_maker_coverage": summary.get("decision_maker_coverage"),
                "decision_maker_count_source": summary.get("decision_maker_count_source"),
                "buying_role_contact_count_source": summary.get("buying_role_contact_count_source"),
                "followup_task_lookup_complete": bool(
                    include_followup_tasks and not task_lookup_skipped and not task_truncated
                ),
                "open_followup_task_count": len(tasks),
                "next_sales_followup_due_at": next_due,
                "has_gap": bool(gap_reasons),
                "gap_reasons": gap_reasons,
                **_score_company(score_input),
            }
            renewing_accounts.append(row)
            if gap_reasons:
                gap_accounts.append(row)

        renewing_accounts.sort(
            key=lambda item: (
                0 if item.get("open_followup_task_count") == 0 else 1,
                item.get("days_until_renewal", 999),
                -item.get("priority_score", 0),
            )
        )
        gap_accounts.sort(
            key=lambda item: (
                0 if item.get("open_followup_task_count") == 0 else 1,
                item.get("days_until_renewal", 999),
                -item.get("priority_score", 0),
            )
        )

        missing_renewal_date_accounts = []
        for company in missing_data.get("results", []):
            summary = _summarize_company(company)
            missing_fields = list(summary.get("missing_fields", []))
            if "contract end date" not in missing_fields:
                missing_fields.append("contract end date")
            missing_renewal_date_accounts.append(
                {
                    "company_id": summary.get("company_id"),
                    "hubspot_scoped": True,
                    "scope_source": SCOPE_SOURCE,
                    "name": summary.get("name"),
                    "country": summary.get("country"),
                    "owner_id": summary.get("owner_id"),
                    "owner_email": summary.get("owner_email"),
                    "owner_name": summary.get("owner_name"),
                    "account_status": summary.get("account_status"),
                    "account_status_source": summary.get("account_status_source"),
                    "contract_end_date": summary.get("contract_end_date"),
                    "current_tool_renewal_date": summary.get("current_tool_renewal_date"),
                    "current_tools": summary.get("current_tools"),
                    "renewal_source_of_truth": RENEWAL_SOURCE_OF_TRUTH_PROPERTY,
                    "current_tools_source_of_truth": CURRENT_TOOLS_SOURCE_OF_TRUTH_PROPERTY,
                    "enrichment_status": summary.get("enrichment_status"),
                    "missing_fields": missing_fields,
                    "decision_maker_count": summary.get("decision_maker_count"),
                    "verified_decision_maker_count": summary.get("verified_decision_maker_count"),
                    "buying_role_contact_count": summary.get("buying_role_contact_count"),
                    "decision_maker_coverage": summary.get("decision_maker_coverage"),
                    "classification_needed": "missing_contract_end_date",
                }
            )
        missing_renewal_date_accounts.sort(key=lambda item: (str(item.get("country") or ""), str(item.get("name") or "")))

        metadata = _search_metadata(data)
        missing_metadata = _search_metadata(missing_data)
        source_bits = ["HubSpot company renewal search"]
        if include_missing_renewal_dates:
            source_bits.append("HubSpot missing-contract-end-date search")
        if include_followup_tasks and target_owner_id:
            source_bits.append("batched HubSpot task lookup")
        scope_response = _scope_response(scope, selected, target_owner_id, target_owner_email)
        scope_response["renewal_window_start"] = window_start.isoformat()
        scope_response["renewal_window_end"] = window_end.isoformat()
        account_truncated = bool(metadata.get("truncated") or missing_metadata.get("truncated"))
        result_truncated = bool(account_truncated or task_truncated)
        caveat = (
            "T-90 search uses HubSpot contract_end_date as renewal source of truth before enrichment checks and separately lists target accounts missing contract_end_date. current_tool_renewal_date is returned as secondary context only. Raw contacts and task bodies are omitted."
        )
        if account_truncated:
            caveat += " Account buckets are truncated; do not present counts as complete."
        if missing_metadata.get("truncated"):
            caveat += " Missing-contract-end-date bucket is a bounded classification sample; use a larger missing_contract_end_date_limit only when a full classification list is explicitly needed."
        if task_truncated:
            caveat += " Task lookup was truncated, so missing-follow-up flags may be incomplete."
        if task_lookup_skipped:
            caveat += " Follow-up task lookup was skipped because no single target owner was selected; no-follow-up gaps were not asserted."
        answer_payload = {
            "known_t90_contract_end_date_accounts": renewing_accounts,
            "renewing_next_90_days": renewing_accounts,
            "gap_accounts": gap_accounts,
            "missing_contract_end_date_accounts": missing_renewal_date_accounts,
            "counts": {
                "renewing_account_count": len(renewing_accounts),
                "gap_count": len(gap_accounts),
                "missing_contact_account_count": len(
                    [row for row in renewing_accounts if "associated contact" in row.get("missing_fields", [])]
                ),
                "missing_decision_maker_account_count": len(
                    [row for row in renewing_accounts if "decision maker" in row.get("missing_fields", [])]
                ),
                "role_only_decision_maker_account_count": len(
                    [
                        row
                        for row in renewing_accounts
                        if row.get("decision_maker_coverage", {}).get("verified_decision_maker_count", 0) < 1
                        and row.get("decision_maker_coverage", {}).get(
                            "role_inferred_decision_maker_candidate_count",
                            0,
                        )
                        > 0
                    ]
                ),
                "missing_contract_end_date_account_count": len(missing_renewal_date_accounts),
                "known_t90_requested_limit": requested_limit,
                "missing_contract_end_date_requested_limit": missing_metadata.get("requested_limit"),
            },
            "required_output_sections": [
                "known_t90_contract_end_date_accounts",
                "missing_contract_end_date_accounts",
                "completeness",
            ],
        }
        return {
            "answer": answer_payload,
            "renewing_next_90_days": renewing_accounts,
            "gap_accounts": gap_accounts,
            "missing_contract_end_date_accounts": missing_renewal_date_accounts,
            "missing_renewal_date_accounts": missing_renewal_date_accounts,
            "required_output_sections": answer_payload["required_output_sections"],
            "data_sources": {
                "source_of_truth": {
                    "target_accounts": "HubSpot companies hs_is_target_account",
                    "ownership": "HubSpot owners API plus company hubspot_owner_id",
                    "country": "HubSpot company company_country",
                    "renewal_timing": "HubSpot company contract_end_date",
                    "current_tools": "HubSpot company current_tools",
                },
                "secondary_context": {
                    "current_tool_renewal_date": "Returned for context only; not used as the T-90 renewal source of truth.",
                    "sales_followup_tasks": "Existing incomplete sales-owned HubSpot tasks when a single owner scope is selected.",
                },
            },
            "source": " plus ".join(source_bits),
            "scope": scope_response,
            **metadata,
            "account_list_complete": not account_truncated,
            "known_t90_account_list_complete": not bool(metadata.get("truncated")),
            "missing_contract_end_date_account_list_complete": not bool(missing_metadata.get("truncated")),
            "renewing_account_count": len(renewing_accounts),
            "gap_count": len(gap_accounts),
            "missing_contract_end_date_account_count": len(missing_renewal_date_accounts),
            "missing_renewal_date_account_count": len(missing_renewal_date_accounts),
            "missing_contract_end_date_metadata": missing_metadata,
            "missing_renewal_date_metadata": missing_metadata,
            "task_lookup": {
                **task_metadata,
                "truncated": task_truncated,
                "skipped": task_lookup_skipped,
            },
            "confidence": "needs-check" if result_truncated or task_lookup_skipped else "verified",
            "caveat": caveat,
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})


@mcp.tool()
def generate_free_search_tasks(
    slack_user_email: str,
    company_ids: list[str] | None = None,
    countries: list[str] | None = None,
    limit: int = 20,
    source_types: list[str] | None = None,
    owner_email: str | None = None,
) -> dict[str, Any]:
    """Generate free/manual public-search tasks for scoped HubSpot enrichment gaps."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        selected_sources = _safe_free_source_types(source_types)
        if not selected_sources:
            return _blocked("No supported free public source_types requested.", _scope_response(scope, []))

        contexts: list[dict[str, Any]] = []
        capped_limit = _bounded_int(limit, default=20, maximum=PUBLIC_TASK_ACCOUNT_LIMIT)
        metadata: dict[str, Any]
        selected = _safe_countries(countries, scope["countries"])
        target_owner_id = ""
        target_owner_email = ""
        if company_ids:
            for company_id in company_ids[:capped_limit]:
                context = _company_context(str(company_id), scope)
                if context is None:
                    raise ScopeError("One or more requested companies are outside caller scope or are not HubSpot target accounts.")
                contexts.append(context)
            metadata = {
                "total": len(company_ids),
                "requested_limit": capped_limit,
                "returned_count": len(contexts),
                "has_more": len(company_ids) > capped_limit,
                "truncated": len(company_ids) > capped_limit,
            }
        else:
            if not selected:
                return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))
            target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)
            data = _company_search(_target_filters(selected, target_owner_id), capped_limit)
            metadata = _search_metadata(data)
            for company in data.get("results", []):
                company_id = str(company.get("id") or "")
                if company_id:
                    context = _company_context(company_id, scope)
                    if context:
                        contexts.append(context)

        accounts = []
        for context in contexts:
            company = context["company"]
            coverage = context.get("coverage", {})
            missing = company.get("missing_fields", [])
            needs_public_enrichment = (
                bool(missing)
                or company.get("enrichment_status") != "nurture_ready"
                or coverage.get("channel_fit_known_count", 0) < 1
            )
            if not needs_public_enrichment and not company_ids:
                continue
            accounts.append(
                {
                    "company_id": company.get("company_id"),
                    "name": company.get("name"),
                    "country": company.get("country"),
                    "enrichment_status": company.get("enrichment_status"),
                    "missing_fields": missing,
                    "coverage": coverage,
                    "tasks": _free_search_tasks_for_company(company, selected_sources),
                }
            )

        return {
            "answer": accounts,
            "source": "HubSpot scoped gaps plus free public search task templates",
            "scope": _scope_response(scope, selected, target_owner_id, target_owner_email),
            **metadata,
            "confidence": "needs-check",
            "caveat": _coverage_caveat(
                metadata,
                "Tasks are manual/free. No paid API, social scraping, PII reveal, HubSpot mutation, or external message send was performed.",
            ),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def review_public_enrichment_evidence(
    slack_user_email: str,
    company_id: str,
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Review public evidence snippets/URLs and dedupe contact candidates against HubSpot."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        context = _company_context(str(company_id), scope)
        if context is None:
            return _blocked("Company is outside caller scope.", {"caller_email": slack_user_email, "company_id": company_id})
        if not evidence_items:
            return _blocked("No public evidence items were provided for review.", _scope_response(scope, [context["company"]["country"]]))

        existing_contacts = _raw_contacts_for_company(str(company_id))
        reviewed_evidence = []
        candidate_contacts = []
        company_signals = []

        for raw_item in evidence_items[:PUBLIC_EVIDENCE_ITEM_LIMIT]:
            if not isinstance(raw_item, dict):
                continue
            item = raw_item
            source_url = str(item.get("url") or item.get("source_url") or "").strip()
            raw_source_type = str(item.get("source_type") or "").strip().lower()
            source_type = _public_evidence_source_type(raw_source_type, source_url)
            fetched_text, fetch_status = _fetch_public_evidence_text(source_type, source_url)
            signals = _extract_company_signals(item, source_type, source_url, fetched_text)
            company_signals.extend(signals)

            candidate = _candidate_from_evidence(item, source_type, source_url)
            if candidate:
                candidate["dedupe"] = _dedupe_candidate(candidate, existing_contacts)
                candidate_contacts.append(candidate)

            reviewed_evidence.append(
                {
                    "source_type": source_type,
                    "original_source_type": raw_source_type,
                    "source_url": source_url,
                    "title": _short_text(str(item.get("title") or ""), 160),
                    "observed_at": str(item.get("observed_at") or ""),
                    "fetch_status": fetch_status,
                    "signals_found": [signal["signal_type"] for signal in signals],
                }
            )

        dedupe_summary = {
            "likely_existing_contact_count": len(
                [
                    candidate
                    for candidate in candidate_contacts
                    if candidate.get("dedupe", {}).get("status") == "likely_existing_contact"
                ]
            ),
            "possible_existing_contact_count": len(
                [
                    candidate
                    for candidate in candidate_contacts
                    if candidate.get("dedupe", {}).get("status") == "possible_existing_contact"
                ]
            ),
            "new_candidate_count": len(
                [candidate for candidate in candidate_contacts if candidate.get("dedupe", {}).get("status") == "new_candidate"]
            ),
        }

        return {
            "answer": {
                "company": context["company"],
                "reviewed_evidence": reviewed_evidence,
                "candidate_contacts": candidate_contacts,
                "company_signals": company_signals[:20],
                "outreach_angles": _outreach_angles(company_signals, candidate_contacts),
                "dedupe_summary": dedupe_summary,
                "will_mutate_hubspot": False,
            },
            "source": "HubSpot scoped account context plus reviewed public evidence",
            "scope": _scope_response(scope, [context["company"]["country"]]),
            "confidence": "needs-check",
            "caveat": "Public evidence is review-only. Social/gated sources are not fetched, and no HubSpot mutation or external message send was performed.",
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "company_id": company_id})


@mcp.tool()
def scan_drive_event_photos(
    slack_user_email: str,
    drive_files: list[dict[str, Any]],
    folder_id: str = DRIVE_ALL_RANDOM_FOLDER_ID,
    limit: int = 20,
    event_name: str = "",
    context_text: str = "",
    luma_events: list[dict[str, Any]] | None = None,
    luma_event_auto_tag: bool = False,
) -> dict[str, Any]:
    """Normalize recent Drive all-random photo metadata into photo-match work items."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        if not isinstance(drive_files, list):
            return _blocked("Drive file metadata list is required; raw images must stay transient.", _scope_response(scope, list(scope.get("countries", ()))))

        requested_limit = _bounded_int(limit, default=20, maximum=PHOTO_SCAN_LIMIT)
        photos = []
        skipped_non_images = 0
        for raw_file in drive_files[:requested_limit]:
            if not isinstance(raw_file, dict):
                continue
            metadata = {**raw_file, "folder_id": folder_id or DRIVE_ALL_RANDOM_FOLDER_ID}
            if not _is_photo_file(metadata):
                skipped_non_images += 1
                continue
            source_pointer = _photo_source_pointer("drive", metadata)
            photo_key = _photo_key(source_pointer)
            luma_event_context = _photo_luma_event_context(source_pointer, luma_events, auto_tag=bool(luma_event_auto_tag))
            resolved_event_name = event_name or (
                luma_event_context.get("event_name") if luma_event_context.get("auto_event_tag_status") == "verified" else ""
            ) or ""
            confirmation_request = _photo_confirmation_request(source_pointer, luma_event_context=luma_event_context)
            photos.append(
                {
                    "photo_key": photo_key,
                    "source_pointer": source_pointer,
                    "source_timestamp": source_pointer.get("source_timestamp")
                    or source_pointer.get("created_time")
                    or source_pointer.get("modified_time")
                    or "",
                    "reconcile_keys": {
                        "photo_key": photo_key,
                        "md5_checksum": source_pointer.get("md5_checksum") or "",
                        "filename": source_pointer.get("filename") or "",
                        "source_timestamp": source_pointer.get("source_timestamp") or source_pointer.get("created_time") or "",
                    },
                    "luma_event_context": luma_event_context,
                    "hubspot_custom_object_plan": _photo_custom_object_plan(
                        photo_key,
                        source_pointer,
                        resolved_event_name,
                        context_text,
                        luma_event_context,
                    ),
                    "confirmation_request": confirmation_request,
                    "next_tool": "propose_photo_people_matches",
                }
            )

        confirmation_batches = _photo_confirmation_batches(photos)
        return {
            "answer": {
                "folder_id": folder_id or DRIVE_ALL_RANDOM_FOLDER_ID,
                "photos": photos,
                "photo_count": len(photos),
                "skipped_non_image_count": skipped_non_images,
                "luma_event_date_correlation": {
                    "enabled": isinstance(luma_events, list),
                    "auto_tag_enabled": bool(luma_event_auto_tag),
                    "candidate_event_count": len(luma_events or []) if isinstance(luma_events, list) else 0,
                    "auto_event_tag_only": bool(luma_event_auto_tag),
                    "person_auto_tag": False,
                },
                "confirmation_policy": "Ask the Slack uploader to identify or confirm every matched person before any HubSpot association.",
                "uploader_confirmation_batches": confirmation_batches,
                "will_mutate_hubspot": False,
                "raw_image_copy": False,
                "daily_pilot_scan_ready": True,
            },
            "source": "Google Drive all-random folder metadata plus HubSpot caller scope",
            "scope": {
                **_scope_response(scope, list(scope.get("countries", ()))),
                "drive_folder_id": folder_id or DRIVE_ALL_RANDOM_FOLDER_ID,
            },
            "total": len(drive_files),
            "requested_limit": requested_limit,
            "returned_count": len(photos),
            "has_more": len(drive_files) > requested_limit,
            "truncated": len(drive_files) > requested_limit,
            "confidence": "needs-check",
            "caveat": (
                "Metadata intake only. The Drive runtime must download images transiently for vision/OCR, then pass clues into propose_photo_people_matches. "
                "HubSpot custom object writes are represented as a preview plan; raw image copies are not stored by default."
            ),
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def propose_photo_people_matches(
    slack_user_email: str,
    photo_source: str,
    photo_metadata: dict[str, Any],
    context_text: str = "",
    vision_clues: dict[str, Any] | None = None,
    explicit_contact_name: str = "",
    explicit_company_name: str = "",
    event_name: str = "",
    country: str = "",
    limit: int = PHOTO_MATCH_LIMIT,
    luma_event_candidates: list[dict[str, Any]] | None = None,
    luma_event_auto_tag: bool = False,
) -> dict[str, Any]:
    """Propose HubSpot contact/company matches for one Slack or Drive event photo."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        source = _photo_source_type(photo_source)
        if not source:
            return _blocked("photo_source must be either drive or slack.", _scope_response(scope, list(scope.get("countries", ()))))
        if not isinstance(photo_metadata, dict):
            return _blocked("photo_metadata must include source pointers, not raw image bytes.", _scope_response(scope, list(scope.get("countries", ()))))

        source_pointer = _photo_source_pointer(source, photo_metadata)
        photo_key = _photo_key(source_pointer)
        metadata_events = photo_metadata.get("luma_event_candidates") or photo_metadata.get("luma_events") or luma_event_candidates
        luma_event_context = _photo_luma_event_context(source_pointer, metadata_events, auto_tag=bool(luma_event_auto_tag))
        resolved_event_name = event_name or (
            luma_event_context.get("event_name") if luma_event_context.get("auto_event_tag_status") == "verified" else ""
        ) or ""
        resolved_country = country or (
            luma_event_context.get("country") if luma_event_context.get("auto_event_tag_status") == "verified" else ""
        ) or ""
        hints = _photo_matching_hints(
            context_text,
            vision_clues,
            explicit_contact_name,
            explicit_company_name,
            resolved_event_name,
            resolved_country,
            luma_event_context,
        )
        selected_countries = _photo_scope_countries(scope, hints)
        if hints.get("countries") and not selected_countries:
            return _blocked("Requested photo country is outside caller scope.", _scope_response(scope, []))

        requested_limit = _bounded_int(limit, default=PHOTO_MATCH_LIMIT, maximum=10)
        company_candidates = _photo_company_candidates(scope, hints, requested_limit)
        contact_candidates = _photo_contact_candidates(scope, hints, company_candidates, requested_limit)
        prompt = _photo_missing_clue_prompt(hints, contact_candidates, company_candidates)
        confirmation_request = _photo_confirmation_request(
            source_pointer,
            prompt,
            has_candidates=bool(contact_candidates or company_candidates),
            luma_event_context=luma_event_context,
        )

        return {
            "answer": {
                "photo_key": photo_key,
                "source_pointer": source_pointer,
                "luma_event_context": luma_event_context,
                "hints": hints,
                "contact_candidates": contact_candidates,
                "company_candidates": company_candidates,
                "missing_clue_prompt": prompt,
                "confirmation_request": confirmation_request,
                "requires_human_confirmation": True,
                "will_mutate_hubspot": False,
                "raw_image_copy": False,
                "hubspot_custom_object_plan": _photo_custom_object_plan(
                    photo_key,
                    source_pointer,
                    resolved_event_name,
                    context_text,
                    luma_event_context,
                ),
                "next_step": "Ask the original uploader to confirm one contact/company before preparing the HubSpot note and WhatsApp follow-up task.",
            },
            "source": "Slack/Drive photo source pointer, transient LLM vision clues, and HubSpot scoped contact/company search",
            "scope": {
                **_scope_response(scope, selected_countries or list(scope.get("countries", ()))),
                "photo_source": source,
            },
            "total": len(contact_candidates),
            "requested_limit": requested_limit,
            "returned_count": len(contact_candidates),
            "has_more": False,
            "truncated": False,
            "confidence": "needs-check",
            "caveat": "Photo matching is proposal-only. Even high-confidence matches require human confirmation before CRM association or follow-up task preview.",
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "photo_source": photo_source})


@mcp.tool()
def plan_event_photo_followup(
    slack_user_email: str,
    selected_match: dict[str, Any],
    event_name: str = "",
    due_at: str = "",
    approval_marker: str = "",
) -> dict[str, Any]:
    """Preview the HubSpot note and WhatsApp follow-up task after a human confirms a photo match."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        if scope["kind"] == "manager":
            return _blocked("Managers have read-only team scope and cannot create photo follow-up write-back previews.", _scope_response(scope, list(scope.get("countries", ()))))
        if not isinstance(selected_match, dict):
            return _blocked("selected_match must be the confirmed contact/company candidate.", _scope_response(scope, list(scope.get("countries", ()))))

        contact_id = str(selected_match.get("contact_id") or "").strip()
        company_id = _selected_match_company_id(selected_match)
        if not contact_id or not company_id:
            return _blocked("Confirmed photo match requires contact_id and scoped company_id.", _scope_response(scope, list(scope.get("countries", ()))))

        company = _assert_company_access(company_id, scope)
        company_name = _selected_match_company_name(selected_match, company)
        contact_name = str(selected_match.get("display_name") or selected_match.get("contact_name") or "there")
        due = due_at or _next_business_day_10_sg()
        draft = _photo_followup_draft(contact_name, company_name, event_name)
        source_pointer = selected_match.get("source_pointer") or selected_match.get("photo_source_pointer") or {}
        if not isinstance(source_pointer, dict):
            source_pointer = {}
        photo_key = str(selected_match.get("photo_key") or (_photo_key(source_pointer) if source_pointer else ""))
        note_summary = _short_text(
            f"Event photo match confirmed for {contact_name} from {company_name}"
            + (f" after {event_name}" if event_name else "")
            + ". Prepare manual WhatsApp follow-up; no message was sent.",
            500,
        )
        action = {
            "company_id": company_id,
            "contact_id": contact_id,
            "task": f"WhatsApp follow-up after {event_name or 'event photo'}",
            "note_summary": note_summary,
            "due_at": due,
            "draft_whatsapp_copy": draft,
            "source_type": "event_photo",
            "source_url": source_pointer.get("permalink") or source_pointer.get("drive_link") or "",
            "source_evidence": {
                "photo_key": photo_key,
                "source_pointer": source_pointer,
                "match_evidence": selected_match.get("evidence", []),
                "confidence_band": selected_match.get("confidence_band", "needs-check"),
            },
            "confidence": "needs-check",
            "selected": True,
        }
        writeback = plan_hubspot_writeback(slack_user_email, [action], approval_marker)
        if writeback.get("confidence") == "blocked":
            return writeback
        preview_id = writeback.get("answer", {}).get("preview_id", "")
        return {
            "answer": {
                "preview_id": preview_id,
                "company_id": company_id,
                "contact_id": contact_id,
                "hubspot_note_summary": note_summary,
                "whatsapp_followup_task": {
                    "subject": action["task"],
                    "due_at": due,
                    "type": "TODO",
                    "company_id": company_id,
                    "contact_id": contact_id,
                },
                "draft_whatsapp_copy": draft,
                "selected_actions": writeback.get("answer", {}).get("actions", [action]),
                "custom_object_preview": {
                    "nurture_event": {"event_name": event_name or "event photo"},
                    "nurture_event_photo": {"photo_key": photo_key, "source_pointer": source_pointer, "raw_image_copy": False},
                    "nurture_person_appearance": {
                        "contact_id": contact_id,
                        "company_id": company_id,
                        "confirmed_by": scope.get("email"),
                        "confirmation_required": False,
                    },
                },
                "requires_approval": True,
                "will_mutate_hubspot": False,
                "whatsapp_auto_send": False,
            },
            "source": "Confirmed photo match plus NurtureAny HubSpot write-back dry run",
            "scope": _scope_response(scope, [company.get("properties", {}).get("company_country") or ""]),
            "confidence": "verified",
            "caveat": "Preview only. Create the HubSpot note/task only after explicit approval; WhatsApp is draft-only and never auto-sent in V1.",
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def build_daily_nurture_plan(
    slack_user_email: str,
    for_date: str = "",
    countries: list[str] | None = None,
    owner_email: str | None = None,
    daily_account_count: int = DAILY_NURTURE_DEFAULT_ACCOUNT_COUNT,
    protected_pool_size: int = DAILY_NURTURE_PROTECTED_POOL_SIZE,
    material_registry_rows: list[dict[str, Any]] | None = None,
    include_full_payload: bool = False,
    sample_account_count: int = 5,
) -> dict[str, Any]:
    """Build the 9am daily target-account nurture pack with approval-gated WhatsApp drafts."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed NurtureAny scope.", {"caller_email": slack_user_email})
        selected_countries = _safe_countries(countries, scope["countries"])
        target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)
        if not target_owner_email:
            target_owner_email = scope.get("hubspot_owner_email") or scope.get("email") or ""
        if not target_owner_id:
            return _blocked("Daily nurture planning requires a concrete HubSpot owner email.", _scope_response(scope, selected_countries))

        selected_date = _daily_nurture_for_date(for_date)
        weekend = selected_date.weekday() >= DAILY_NURTURE_WORKWEEK_DAYS
        capped_pool = max(1, min(int(protected_pool_size or DAILY_NURTURE_PROTECTED_POOL_SIZE), HUBSPOT_SEARCH_TOTAL_LIMIT))
        active_material_rows, ignored_material_rows = _safe_material_rows(material_registry_rows or [], selected_date)
        search = _company_search(
            _target_filters(selected_countries, target_owner_id),
            limit=capped_pool,
            maximum=HUBSPOT_SEARCH_TOTAL_LIMIT,
            sorts=[{"propertyName": "name", "direction": "ASCENDING"}],
        )
        pool = search.get("results", [])
        bucket = _daily_nurture_company_bucket(pool, selected_date, daily_account_count)
        selected_companies = bucket["companies"]
        selected_company_ids = [str(company.get("id") or company.get("company_id") or "") for company in selected_companies]
        run_id = _daily_nurture_run_id(target_owner_email, selected_date, bucket["bucket_index"], selected_company_ids)
        daily_contexts = _daily_nurture_contexts(selected_companies, scope)

        accounts: list[dict[str, Any]] = []
        messages: list[dict[str, Any]] = []
        inaccessible_accounts: list[dict[str, str]] = []
        role_gaps: list[dict[str, str]] = []
        material_gaps: list[dict[str, str]] = []

        for company in selected_companies:
            company_id = str(company.get("id") or company.get("company_id") or "")
            if not company_id:
                continue
            context = daily_contexts.get(company_id)
            if not context:
                inaccessible_accounts.append({"company_id": company_id, "reason": "outside caller scope or inaccessible"})
                continue
            stakeholders, gaps = _daily_nurture_stakeholders(context)
            company_summary = context.get("company", {})
            account_messages = [
                _daily_nurture_message(run_id, context, stakeholder, active_material_rows) for stakeholder in stakeholders
            ]
            messages.extend(account_messages)
            role_gaps.extend(
                [
                    {
                        "company_id": company_summary.get("company_id") or company_id,
                        "company_name": company_summary.get("name") or "",
                        "role": gap["role"],
                        "reason": gap["reason"],
                    }
                    for gap in gaps
                ]
            )
            material_gaps.extend(
                [
                    {
                        "company_id": message.get("company_id") or company_id,
                        "company_name": message.get("company_name") or "",
                        "contact_id": message.get("contact_id") or "",
                        "stakeholder_role": message.get("stakeholder_role") or "",
                        "reason": "contact marked do-not-contact"
                        if message.get("do_not_contact")
                        else "no active Sheet/case-study material or approved template",
                    }
                    for message in account_messages
                    if not message.get("eazybe_ready")
                ]
            )
            accounts.append(
                {
                    "company_id": company_summary.get("company_id") or company_id,
                    "company_name": company_summary.get("name") or "",
                    "country": company_summary.get("country") or "",
                    "industry": company_summary.get("industry") or "",
                    "current_tools": company_summary.get("current_tools") or "",
                    "stakeholder_count": len(stakeholders),
                    "message_count": len(account_messages),
                    "role_gaps": gaps,
                }
            )

        confidence = "verified"
        caveats = []
        if weekend:
            confidence = "needs-check"
            caveats.append("Requested date is a weekend; v1 working days are Monday to Friday and this returns the Friday bucket.")
        if search.get("truncated"):
            confidence = "needs-check"
            caveats.append("HubSpot search was truncated; protected pool may exceed returned rows.")
        if len(pool) < capped_pool:
            confidence = "needs-check"
            caveats.append(f"Only {len(pool)} protected target accounts were returned for this owner; no silent replacement was done.")
        if len(selected_companies) < bucket["daily_account_count"]:
            confidence = "needs-check"
            caveats.append(f"Bucket has only {len(selected_companies)} accounts; no silent replacement was done.")
        if role_gaps or material_gaps or inaccessible_accounts:
            confidence = "needs-check"
            caveats.append("Some accounts have missing stakeholder roles, inaccessible context, or missing approved material/template matches.")
        if not material_registry_rows:
            confidence = "needs-check"
            caveats.append("No Google Sheet material registry rows were supplied; matching fell back to approved repo case studies only.")
        if selected_companies:
            caveats.append("Daily Slack plan uses batched HubSpot company/contact context; deep task/deal/C360 expansion is skipped to stay inside the Slack runtime window.")

        response = {
            "answer": {
                "run_id": run_id,
                "for_date": selected_date.isoformat(),
                "timezone": "Asia/Singapore",
                "working_day_policy": "Monday to Friday; public holiday suppression not enabled in v1",
                "bucket_index": bucket["bucket_index"],
                "bucket_label": bucket["bucket_label"],
                "account_rotation": {
                    "protected_pool_size": capped_pool,
                    "daily_account_count": bucket["daily_account_count"],
                    "returned_pool_count": len(pool),
                    "selected_account_count": len(accounts),
                    "selected_company_ids": selected_company_ids,
                    "no_silent_replacement": True,
                },
                "material_registry": {
                    "contract": _material_registry_contract(),
                    "supplied_rows": len(material_registry_rows or []),
                    "active_rows": len(active_material_rows),
                    "ignored_rows": ignored_material_rows[:20],
                    "read_only": True,
                },
                "selected_accounts": accounts,
                "messages": messages,
                "message_count": len(messages),
                "eazybe_ready_message_count": sum(1 for message in messages if message.get("eazybe_ready")),
                "role_gaps": role_gaps,
                "material_gaps": material_gaps,
                "inaccessible_accounts": inaccessible_accounts,
                "approval_instructions": "Review message_ids, then call preview_eazybe_template_messages. Only call send_approved_eazybe_messages with selected message_ids and approval_marker.",
                "twelve_pm_sent_definition": "Sent means Eazybe accepted/queued the approved template message, or HubSpot later shows a matching WhatsApp communication for the stakeholder/account after run start. Explicit skips suppress reminders.",
                "whatsapp_auto_send": False,
            },
            "source": "HubSpot target accounts/contacts/activity + read-only Google Sheet material registry rows + approved repo case-study catalog",
            "scope": {**_scope_response(scope, selected_countries, target_owner_id, target_owner_email), "target_owner_email": target_owner_email, "target_owner_id": target_owner_id},
            "confidence": confidence,
            "caveat": " ".join(caveats) if caveats else "Deterministic 5-working-day rotation over the returned protected target-account pool. WhatsApp sends remain approval-gated.",
        }
        persistence = _persist_daily_nurture_run(run_id, response)
        response["answer"]["run_persistence"] = persistence
        if not persistence.get("persisted"):
            response["confidence"] = "needs-check"
            response["caveat"] = f"{response['caveat']} Daily run payload was not persisted for 12pm reminder reload: {persistence.get('reason')}."
        else:
            _persist_daily_nurture_run(run_id, response)
        if include_full_payload:
            return response
        return _compact_daily_nurture_response(response, sample_account_count=sample_account_count)
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})
    except ValueError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def record_nurtureany_lesson_candidate(
    source_summary: str,
    proposed_rule: str,
    applies_to: str,
    target_repo_surface: str,
    risk_class: str,
    source_thread_permalink: str = "",
    lesson_id: str = "",
) -> dict[str, Any]:
    """Record a pending reviewed-learning candidate in the profile runtime store."""

    source_thread_permalink = _clean_lesson_text(source_thread_permalink, max_length=300)
    source_summary = _clean_lesson_text(source_summary, max_length=800)
    proposed_rule = _clean_lesson_text(proposed_rule, max_length=800)
    applies_to = _clean_lesson_text(applies_to, max_length=300)
    target_repo_surface = _clean_lesson_text(target_repo_surface, max_length=80)
    risk_class = _clean_lesson_text(risk_class, max_length=20).lower()
    if not source_summary or not proposed_rule or not applies_to or not target_repo_surface or not risk_class:
        return _blocked(
            "source_summary, proposed_rule, applies_to, target_repo_surface, and risk_class are required.",
            {"lesson_candidates": "required-fields"},
        )
    if target_repo_surface not in LESSON_CANDIDATE_TARGET_SURFACES:
        return _blocked(
            "target_repo_surface must be one of skill_reference, soul, mcp_contract, config_template, regression_case, runbook, research_wiki, or app_manifest.",
            {"target_repo_surface": target_repo_surface},
        )
    if risk_class not in LESSON_CANDIDATE_RISK_CLASSES:
        return _blocked("risk_class must be low, medium, or high.", {"risk_class": risk_class})
    unsafe_reason = _lesson_payload_unsafe(source_thread_permalink, source_summary, proposed_rule, applies_to)
    if unsafe_reason:
        return _blocked(
            "Lesson candidates must not contain raw Slack transcripts, raw HubSpot rows, phone numbers, secrets, tokens, or contact exports.",
            {"reason": unsafe_reason},
        )

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if lesson_id:
        safe_lesson_id = _safe_file_stem(str(lesson_id).strip())
    else:
        digest = hashlib.sha256(f"{source_summary}\n{proposed_rule}\n{applies_to}".encode("utf-8")).hexdigest()[:10]
        safe_lesson_id = f"lesson-{now.replace(':', '').replace('+', 'Z')}-{digest}"
    if not safe_lesson_id:
        return _blocked("lesson_id could not be normalized.", {"lesson_candidates": "invalid-id"})
    path = _lesson_candidate_path(safe_lesson_id)
    if path.exists():
        return _blocked("A lesson candidate already exists for this lesson_id.", {"lesson_id": safe_lesson_id})

    record = {
        "lesson_id": safe_lesson_id,
        "created_at": now,
        "source_thread_permalink": source_thread_permalink,
        "source_summary": source_summary,
        "proposed_rule": proposed_rule,
        "applies_to": applies_to,
        "target_repo_surface": target_repo_surface,
        "risk_class": risk_class,
        "status": "pending_review",
        "reviewer": "",
        "review_notes": "",
        "promotion_policy": "Runtime candidate only. Human review must promote approved behavior into the repo packet, tests, and deployment.",
        "source_of_truth_boundary": "Does not override HubSpot, access policy, Slack identity rules, safety rules, or approved repo references.",
        "honcho_used": False,
        "will_mutate_hubspot": False,
    }
    try:
        _atomic_write_json(path, record)
    except OSError as error:
        return _blocked(f"Lesson candidate write failed: {error.__class__.__name__}", {"lesson_id": safe_lesson_id})
    return {
        "answer": _compact_lesson_candidate(record),
        "source": "NurtureAny profile-runtime reviewed lesson candidates",
        "scope": {"lesson_id": safe_lesson_id, "lesson_candidates_dir": str(_lesson_candidates_dir()), "status": "pending_review"},
        "confidence": "verified",
        "caveat": "Candidate only. It does not change bot behavior until reviewed, promoted into the repo packet, verified, and deployed.",
    }


@mcp.tool()
def list_nurtureany_lesson_candidates(status: str = "", limit: int = 20) -> dict[str, Any]:
    """List compact NurtureAny lesson candidates from the profile runtime store."""

    status = str(status or "").strip()
    if status and status not in LESSON_CANDIDATE_STATUSES:
        return _blocked("status must be one of pending_review, approved_for_repo_promotion, rejected, or promoted.", {"status": status})
    try:
        safe_limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        safe_limit = 20
    candidates = []
    for record in _iter_lesson_candidates():
        candidate_status = str(record.get("status") or "pending_review").strip()
        if status and candidate_status != status:
            continue
        compact = _compact_lesson_candidate(record)
        unsafe_reason = _lesson_payload_unsafe(
            compact.get("source_thread_permalink", ""),
            compact.get("source_summary", ""),
            compact.get("proposed_rule", ""),
            compact.get("applies_to", ""),
            compact.get("review_notes", ""),
        )
        if unsafe_reason:
            compact = {
                "lesson_id": compact.get("lesson_id") or "",
                "status": candidate_status,
                "created_at": compact.get("created_at") or "",
                "redacted": True,
                "redaction_reason": unsafe_reason,
            }
        candidates.append(compact)
    candidates.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    returned = candidates[:safe_limit]
    return {
        "answer": {
            "candidates": returned,
            "returned_count": len(returned),
            "total_matching_count": len(candidates),
            "status_filter": status or "all",
            "valid_statuses": sorted(LESSON_CANDIDATE_STATUSES),
        },
        "source": "NurtureAny profile-runtime reviewed lesson candidates",
        "scope": {"lesson_candidates_dir": str(_lesson_candidates_dir()), "limit": safe_limit},
        "confidence": "verified",
        "caveat": "Runtime candidates are not durable behavior until promoted into the repo packet and deployed.",
    }


@mcp.tool()
def read_nurtureany_lesson_candidate(lesson_id: str) -> dict[str, Any]:
    """Read one NurtureAny lesson candidate by id."""

    lesson_id = _safe_file_stem(str(lesson_id or "").strip())
    if not lesson_id:
        return _blocked("lesson_id is required to read a lesson candidate.", {"lesson_candidates": "required-id"})
    record = _load_lesson_candidate(lesson_id)
    if not record:
        return _blocked("No lesson candidate found for this lesson_id.", {"lesson_id": lesson_id})
    compact = _compact_lesson_candidate(record)
    unsafe_reason = _lesson_payload_unsafe(
        compact.get("source_thread_permalink", ""),
        compact.get("source_summary", ""),
        compact.get("proposed_rule", ""),
        compact.get("applies_to", ""),
        compact.get("review_notes", ""),
    )
    if unsafe_reason:
        return _blocked(
            "Lesson candidate contains material that should not be returned through Slack/MCP.",
            {"lesson_id": lesson_id, "reason": unsafe_reason},
        )
    return {
        "answer": compact,
        "source": "NurtureAny profile-runtime reviewed lesson candidates",
        "scope": {"lesson_id": lesson_id, "lesson_candidates_dir": str(_lesson_candidates_dir())},
        "confidence": "verified",
        "caveat": "Read-only candidate. It does not change bot behavior until promoted into the repo packet and deployed.",
    }


@mcp.tool()
def record_nurtureany_operation_checkpoint(
    operation_id: str,
    slack_thread: str,
    phase: str,
    checkpoint: str,
    approval_marker: str = "",
    idempotency_key: str = "",
    side_effect: str = "none",
    compact_error: str = "",
) -> dict[str, Any]:
    """Persist a restart-safe workflow checkpoint in the profile runtime ledger."""

    operation_id = str(operation_id or "").strip()
    if not operation_id:
        return _blocked("operation_id is required before checkpointing a workflow.", {"ledger": "operation-ledger"})
    phase = str(phase or "").strip()[:80]
    checkpoint = str(checkpoint or "").strip()[:1000]
    side_effect = str(side_effect or "none").strip().lower()
    if side_effect not in {"none", "preview", "external_send", "hubspot_write", "eazybe_send"}:
        return _blocked("side_effect must be one of none, preview, external_send, hubspot_write, or eazybe_send.", {"operation_id": operation_id})

    now = datetime.now(timezone.utc).isoformat()
    record = _load_operation_record(operation_id)
    history = record.get("history") if isinstance(record.get("history"), list) else []
    event = {
        "at": now,
        "phase": phase,
        "checkpoint": checkpoint,
        "side_effect": side_effect,
        "approval_marker_present": bool(str(approval_marker or "").strip()),
        "idempotency_key": str(idempotency_key or "").strip(),
        "compact_error": str(compact_error or "").strip()[:500],
    }
    history.append(event)
    record.update(
        {
            "operation_id": operation_id,
            "slack_thread": str(slack_thread or "").strip()[:300],
            "phase": phase,
            "last_checkpoint": checkpoint,
            "approval_marker": str(approval_marker or "").strip(),
            "idempotency_key": str(idempotency_key or "").strip(),
            "side_effect": side_effect,
            "compact_error": str(compact_error or "").strip()[:500],
            "updated_at": now,
            "history": history[-50:],
        }
    )
    try:
        path = _ledger_path(operation_id)
        _atomic_write_json(path, record)
    except OSError as error:
        return _blocked(f"Operation checkpoint write failed: {error.__class__.__name__}", {"operation_id": operation_id})
    return {
        "answer": _compact_ledger_record(record),
        "source": "NurtureAny profile-runtime operation ledger",
        "scope": {"operation_id": operation_id, "ledger_dir": str(_operation_ledger_dir()), "external_side_effects_allowed": False},
        "confidence": "verified",
        "caveat": "Checkpoint only. Repeated sends or writes still require an approval marker and idempotency key.",
    }


@mcp.tool()
def read_nurtureany_operation_ledger(operation_id: str) -> dict[str, Any]:
    """Read a compact restart-continuation checkpoint for a NurtureAny operation."""

    operation_id = str(operation_id or "").strip()
    if not operation_id:
        return _blocked("operation_id is required to read the operation ledger.", {"ledger": "operation-ledger"})
    record = _load_operation_record(operation_id)
    if not record:
        return _blocked("No operation ledger record found for this operation_id.", {"operation_id": operation_id})
    compact = _compact_ledger_record(record)
    side_effect = compact.get("side_effect")
    can_repeat_side_effect = bool(record.get("approval_marker")) and bool(record.get("idempotency_key"))
    return {
        "answer": {
            **compact,
            "can_resume_read_only": True,
            "can_repeat_side_effect": can_repeat_side_effect,
            "resume_policy": "Rerun read-only tool calls safely. Do not repeat external sends or writes unless can_repeat_side_effect=true.",
        },
        "source": "NurtureAny profile-runtime operation ledger",
        "scope": {"operation_id": operation_id, "side_effect": side_effect},
        "confidence": "verified" if side_effect == "none" or can_repeat_side_effect else "needs-check",
        "caveat": "Missing approval marker or idempotency key blocks repeated external sends/writes.",
    }


@mcp.tool()
def draft_nurture_message(
    account_name: str,
    segment: str,
    persona: str = "",
    channel: str = "WhatsApp",
    trigger: str = "",
    locale: str = "neutral",
) -> dict[str, Any]:
    """Draft manual-review nurture copy. This tool never sends external messages."""

    safe_channel = channel if channel in {"WhatsApp", "email", "LinkedIn"} else "WhatsApp"
    greeting = "Hi" if safe_channel != "email" else "Hi there"
    persona_text = f" for your {persona} team" if persona else ""
    trigger_text = f" Saw that {trigger}." if trigger else ""
    if safe_channel == "email":
        draft = (
            f"Subject: Quick check-in on {account_name}\n\n"
            f"{greeting},\n\n"
            f"I wanted to check in on {account_name}{persona_text}.{trigger_text} "
            "Happy to share a few practical ideas if this is useful.\n\n"
            "Best,\n"
            "<AE name>"
        )
    elif safe_channel == "LinkedIn":
        draft = (
            f"{greeting}, noticed {account_name} is on our target-account list."
            f"{trigger_text} Open to a quick exchange on what your team is prioritising?"
        )
    else:
        draft = (
            f"{greeting}, checking in on {account_name}{persona_text}."
            f"{trigger_text} Would it be useful if I shared a few quick ideas?"
        )
    return {
        "answer": {
            "account_name": account_name,
            "segment": segment,
            "channel": safe_channel,
            "draft": draft,
        },
        "source": "NurtureAny drafting playbook",
        "scope": {"external_message_sending": False, "locale": locale},
        "confidence": "needs-check",
        "caveat": "Draft only; AE must review and send manually.",
    }


@mcp.tool()
def plan_hubspot_writeback(
    slack_user_email: str,
    selected_actions: list[dict[str, Any]],
    approval_marker: str = "",
) -> dict[str, Any]:
    """Create a dry-run HubSpot write-back plan. This tool does not mutate HubSpot."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        if scope["kind"] in {"manager", "event_operator"}:
            return _blocked("Managers and regional event operators cannot create HubSpot write-back previews.", _scope_response(scope, list(scope.get("countries", ()))))
        if not selected_actions:
            return _blocked("At least one selected action is required for a write-back preview.", _scope_response(scope, list(scope.get("countries", ()))))

        scoped_actions = selected_actions[:50]
        for action in scoped_actions:
            company_id = str(action.get("company_id") or "").strip()
            if not company_id:
                raise ScopeError("Every write-back preview action requires a scoped HubSpot company_id.")
            _assert_company_access(company_id, scope)

        payload = json.dumps(
            {
                "caller": scope.get("email"),
                "actions": scoped_actions,
                "approval_marker": approval_marker,
                "date": datetime.now(timezone.utc).isoformat(),
            },
            sort_keys=True,
        )
        preview_id = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        preview = []
        for action in scoped_actions:
            source = action.get("source") if isinstance(action.get("source"), dict) else {}
            source_evidence = action.get("source_evidence") or source
            preview.append(
                {
                    "company_id": action.get("company_id"),
                    "contact_id": action.get("contact_id"),
                    "task": action.get("task"),
                    "note_summary": action.get("note_summary"),
                    "field_updates": action.get("field_updates", {}),
                    "source_evidence": source_evidence,
                    "source_type": action.get("source_type") or source.get("type"),
                    "source_url": action.get("source_url") or source.get("url"),
                    "confidence": action.get("confidence", "needs-check"),
                    "selected": bool(action.get("selected", True)),
                }
            )
        return {
            "answer": {
                "preview_id": preview_id,
                "actions": preview,
                "will_mutate_hubspot": False,
            },
            "source": "NurtureAny HubSpot write-back dry run",
            "scope": _scope_response(scope, list(scope.get("countries", ()))),
            "confidence": "verified",
            "caveat": (
                "Preview only for generic write-back. Managers are blocked from generic team write-back previews; "
                "HubSpot Task writes use the separate exact-approval task primitives."
            ),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


if __name__ == "__main__":
    mcp.run("stdio")
