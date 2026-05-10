import { existsSync, readFileSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";

const repoRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
const appRoot = join(repoRoot, "apps", "nurtureany-sales-bot");
const manifestPath = join(appRoot, "app.manifest.json");

const failures = [];

function fail(message) {
  failures.push(message);
}

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    fail(`Invalid JSON: ${path}: ${error.message}`);
    return null;
  }
}

function assertFile(relPath) {
  const path = join(appRoot, relPath);
  if (!existsSync(path)) {
    fail(`Missing app file: ${relPath}`);
    return;
  }
  if (!statSync(path).isFile()) {
    fail(`Expected file, got non-file path: ${relPath}`);
  }
}

function textOf(relPath) {
  const path = join(appRoot, relPath);
  if (!existsSync(path) || !statSync(path).isFile()) return "";
  return readFileSync(path, "utf8");
}

function scanForSecretPatterns(relPath) {
  const text = textOf(relPath);
  if (!text) return;
  const patterns = [
    [/xox[baprs]-[A-Za-z0-9-]+/, "Slack token"],
    [/xapp-[A-Za-z0-9-]+/, "Slack app token"],
    [/sk-[A-Za-z0-9_-]{20,}/, "OpenAI-style API key"],
    [/pat-[a-z0-9]+-[A-Za-z0-9-]{20,}/, "HubSpot private app token"],
    [/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/, "private key"],
    [/AIza[0-9A-Za-z_-]{20,}/, "Google API key"]
  ];
  for (const [pattern, label] of patterns) {
    if (pattern.test(text)) fail(`${label} pattern found in ${relPath}`);
  }
}

if (!existsSync(manifestPath)) {
  fail("Missing apps/nurtureany-sales-bot/app.manifest.json");
} else {
  const manifest = readJson(manifestPath);
  if (manifest) {
    if (manifest.profile_name !== "nurtureanysalesbot") fail("Manifest profile_name must be nurtureanysalesbot");
    if (manifest.model !== "claude-sonnet-4-6") fail("Manifest model must be claude-sonnet-4-6");
    if (manifest.secrets_copied !== false) fail("Manifest secrets_copied must be false");
    if (manifest.external_message_sending !== false) fail("Manifest external_message_sending must be false");
    if (manifest.honcho_enabled !== false) fail("Manifest honcho_enabled must be false");

    const countries = manifest.scope?.countries || [];
    for (const country of ["Singapore", "Malaysia", "Indonesia"]) {
      if (!countries.includes(country)) fail(`Manifest missing country scope: ${country}`);
    }

    const admins = manifest.scope?.overall_admins || [];
    for (const email of ["eugene@staffany.com", "kaiyi@staffany.com"]) {
      if (!admins.includes(email)) fail(`Manifest missing overall admin: ${email}`);
    }

    const managers = manifest.scope?.regional_managers || [];
    const managerByEmail = new Map(managers.map((manager) => [manager.email, manager.countries || []]));
    const kerren = managerByEmail.get("kerren.fong@staffany.com") || [];
    if (!kerren.includes("Singapore") || !kerren.includes("Malaysia") || kerren.includes("Indonesia")) {
      fail("Manifest Kerren scope must be Singapore and Malaysia only");
    }
    const sarah = managerByEmail.get("sarah@staffany.com") || [];
    if (!sarah.includes("Indonesia") || sarah.includes("Singapore") || sarah.includes("Malaysia")) {
      fail("Manifest Sarah scope must be Indonesia only");
    }
    if (manifest.access_policy?.runtime_env_var !== "NURTUREANY_ACCESS_POLICY_PATH") {
      fail("Manifest access_policy runtime_env_var must be NURTUREANY_ACCESS_POLICY_PATH");
    }
    if (manifest.access_policy?.template !== "runtime/access-policy.template.json") {
      fail("Manifest access_policy template must be runtime/access-policy.template.json");
    }
    if (manifest.access_policy?.unclassified_hubspot_owners !== "blocked") {
      fail("Manifest must block unclassified HubSpot owners");
    }
    if (manifest.access_policy?.manager_scope !== "country_scoped_team_read_only") {
      fail("Manifest manager scope must be country_scoped_team_read_only");
    }

    const paths = manifest.paths || {};
    for (const value of Object.values(paths)) {
      if (Array.isArray(value)) {
        for (const relPath of value) assertFile(relPath);
      } else {
        assertFile(value);
      }
    }

    const expectedReadTools = [
      "list_my_target_accounts",
      "list_team_target_accounts",
      "audit_hubspot_owner_roster",
      "audit_priority_account_coverage",
      "build_friday_sales_review",
      "get_account_context",
      "build_pre_demo_game_plans",
      "list_sales_followup_tasks",
      "check_account_followup_status",
      "check_event_followup_status",
      "score_nurture_accounts",
      "find_contact_gaps",
      "find_t90_renewal_gaps",
      "generate_free_search_tasks",
      "review_public_enrichment_evidence",
      "scan_drive_event_photos",
      "propose_photo_people_matches",
      "list_drive_folder_images",
      "extract_drive_image_clues",
      "draft_nurture_message",
      "list_google_calendar_events",
      "audit_google_calendar_meeting_quality",
      "list_luma_events",
      "get_luma_event_context",
      "resolve_known_area_for_near_me",
      "build_near_me_outlet_matches_query",
      "refresh_google_places_for_known_area",
      "build_near_me_c360_customer_query",
      "merge_near_me_sources",
      "search_exa_people_candidates",
      "search_lusha_decision_maker_candidates",
      "get_lusha_credit_usage"
    ];
    const readTools = manifest.tools?.read || [];
    for (const tool of expectedReadTools) {
      if (!readTools.includes(tool)) fail(`Manifest missing read tool: ${tool}`);
    }
    if (!manifest.tools?.preview?.includes("plan_hubspot_writeback")) {
      fail("Manifest missing preview tool: plan_hubspot_writeback");
    }
    if (!manifest.tools?.preview?.includes("plan_event_photo_followup")) {
      fail("Manifest missing preview tool: plan_event_photo_followup");
    }
    if (!manifest.tools?.approval_gated_enrichment?.includes("reveal_lusha_contact_details")) {
      fail("Manifest missing approval-gated enrichment tool: reveal_lusha_contact_details");
    }
    for (const tool of ["create_hubspot_task", "append_hubspot_note", "update_nurture_fields"]) {
      if (!manifest.tools?.mutation_requires_explicit_approval?.includes(tool)) {
        fail(`Manifest missing approval-gated mutation tool: ${tool}`);
      }
    }
    if (manifest.lusha?.auth_env_var !== "LUSHA_API_KEY") fail("Manifest missing LUSHA_API_KEY auth env var");
    if (manifest.lusha?.max_search_companies !== 5) fail("Manifest Lusha max_search_companies must be 5");
    if (manifest.lusha?.max_candidates_per_company !== 5) fail("Manifest Lusha max_candidates_per_company must be 5");
    if (manifest.lusha?.max_reveal_contacts !== 3) fail("Manifest Lusha max_reveal_contacts must be 3");
    if (manifest.lusha?.selected_pii_in_slack !== true) fail("Manifest Lusha selected_pii_in_slack must be true");
    if (manifest.lusha?.bulk_contact_exports !== false) fail("Manifest Lusha bulk_contact_exports must be false");
    if (manifest.exa?.auth_env_var !== "EXA_API_KEY") fail("Manifest missing EXA_API_KEY auth env var");
    if (manifest.exa?.max_search_companies !== 5) fail("Manifest Exa max_search_companies must be 5");
    if (manifest.exa?.max_candidates_per_company !== 5) fail("Manifest Exa max_candidates_per_company must be 5");
    if (manifest.exa?.selected_pii_in_slack !== false) fail("Manifest Exa selected_pii_in_slack must be false");
    if (manifest.exa?.bulk_contact_exports !== false) fail("Manifest Exa bulk_contact_exports must be false");
    if (manifest.exa?.allowed_endpoint !== "POST /search") fail("Manifest Exa allowed_endpoint must be POST /search");
    if (manifest.exa?.category !== "people") fail("Manifest Exa category must be people");
    if (manifest.photo_matching?.drive_folder_id !== "1qXlFnr5TKFtsYNWk7ZywBBctDaae3RY-") {
      fail("Manifest photo_matching drive_folder_id must be the all-random folder");
    }
    if (manifest.photo_matching?.source_pointer_only !== true) fail("Manifest photo_matching must store source pointers only");
    if (manifest.photo_matching?.raw_image_copy_default !== false) fail("Manifest photo_matching must not copy raw images by default");
    if (manifest.photo_matching?.human_confirmation_required !== true) fail("Manifest photo_matching must require human confirmation");
    if (manifest.photo_matching?.drive_scan_confirmation_owner !== "slack_uploader") {
      fail("Manifest photo_matching drive_scan_confirmation_owner must be slack_uploader");
    }
    if (manifest.photo_matching?.batch_confirmation_by_uploader !== true) {
      fail("Manifest photo_matching must batch confirmation prompts by uploader");
    }
    if (manifest.photo_matching?.luma_event_date_correlation !== true) {
      fail("Manifest photo_matching must enable Luma event-date correlation");
    }
    if (manifest.photo_matching?.auto_event_tag_from_luma_date !== true) {
      fail("Manifest photo_matching must allow event-only Luma auto-tagging");
    }
    if (manifest.photo_matching?.person_auto_tag !== false) {
      fail("Manifest photo_matching must not auto-tag people from Luma date context");
    }
    if (manifest.photo_matching?.whatsapp_auto_send !== false) fail("Manifest photo_matching must not auto-send WhatsApp");
    for (const objectName of ["nurture_event", "nurture_event_photo", "nurture_person_appearance"]) {
      if (!manifest.photo_matching?.hubspot_custom_objects?.includes(objectName)) {
        fail(`Manifest photo_matching missing custom object: ${objectName}`);
      }
    }
    for (const tool of ["extract_drive_image_clues", "scan_drive_event_photos", "propose_photo_people_matches", "plan_event_photo_followup"]) {
      if (!manifest.photo_matching?.allowed_tools?.includes(tool)) {
        fail(`Manifest photo_matching missing allowed tool: ${tool}`);
      }
    }
    if (manifest.google_calendar?.account_email !== "team@staffany.com") fail("Manifest Google Calendar account_email must be team@staffany.com");
    if (manifest.google_calendar?.access_mode !== "team_oauth_shared_calendar") {
      fail("Manifest Google Calendar access_mode must be team_oauth_shared_calendar");
    }
    if (manifest.google_calendar?.service_account !== false) fail("Manifest Google Calendar must not claim service_account=true");
    if (manifest.google_calendar?.owner_calendar_strategy !== "resolve_hubspot_owner_email_then_pass_as_calendar_id") {
      fail("Manifest Google Calendar owner_calendar_strategy must resolve HubSpot owner email and pass it as calendar_id");
    }
    if (manifest.google_calendar?.inaccessible_owner_calendar_confidence !== "blocked") {
      fail("Manifest Google Calendar inaccessible_owner_calendar_confidence must be blocked");
    }
    if (manifest.google_calendar?.required_scope !== "https://www.googleapis.com/auth/calendar.readonly") {
      fail("Manifest Google Calendar required_scope must be calendar.readonly");
    }
    if (manifest.google_calendar?.read_only !== true) fail("Manifest Google Calendar read_only must be true");
    if (manifest.google_calendar?.max_calendars !== 5) fail("Manifest Google Calendar max_calendars must be 5");
    if (manifest.google_calendar?.max_events_per_calendar !== 50) {
      fail("Manifest Google Calendar max_events_per_calendar must be 50");
    }
    if (!manifest.google_calendar?.allowed_tools?.includes("list_google_calendar_events")) {
      fail("Manifest Google Calendar missing list_google_calendar_events tool");
    }
    if (!manifest.google_calendar?.allowed_tools?.includes("audit_google_calendar_meeting_quality")) {
      fail("Manifest Google Calendar missing audit_google_calendar_meeting_quality tool");
    }
    if (manifest.google_calendar?.meeting_quality_audit !== "match_internal_attendee_email_hashes_to_hubspot_contacts") {
      fail("Manifest Google Calendar meeting_quality_audit must use safe attendee hash matching");
    }
    if (manifest.google_calendar?.attendee_visibility !== "safe_summary_only_no_raw_emails") {
      fail("Manifest Google Calendar attendee_visibility must be safe summary only");
    }
    if (manifest.google_calendar?.event_mutations !== false) fail("Manifest Google Calendar event_mutations must be false");
    if (manifest.google_calendar?.attendee_exports !== false) fail("Manifest Google Calendar attendee_exports must be false");
    if (manifest.google_drive?.account_email !== "team@staffany.com") fail("Manifest Google Drive account_email must be team@staffany.com");
    if (manifest.google_drive?.access_mode !== "team_oauth_drive_readonly") {
      fail("Manifest Google Drive access_mode must be team_oauth_drive_readonly");
    }
    if (manifest.google_drive?.service_account !== false) fail("Manifest Google Drive must not claim service_account=true");
    if (manifest.google_drive?.required_scope !== "https://www.googleapis.com/auth/drive.readonly") {
      fail("Manifest Google Drive required_scope must be drive.readonly");
    }
    if (manifest.google_drive?.read_only !== true) fail("Manifest Google Drive read_only must be true");
    if (manifest.google_drive?.default_folder_id !== "1qXlFnr5TKFtsYNWk7ZywBBctDaae3RY-") {
      fail("Manifest Google Drive default_folder_id must be all-random folder");
    }
    if (manifest.google_drive?.max_files !== 100) fail("Manifest Google Drive max_files must be 100");
    if (!manifest.google_drive?.allowed_tools?.includes("list_drive_folder_images")) {
      fail("Manifest Google Drive missing list_drive_folder_images tool");
    }
    if (!manifest.google_drive?.allowed_tools?.includes("extract_drive_image_clues")) {
      fail("Manifest Google Drive missing extract_drive_image_clues tool");
    }
    if (manifest.google_drive?.transient_vision_downloads !== true) {
      fail("Manifest Google Drive transient_vision_downloads must be true");
    }
    if (manifest.google_drive?.uploader_profile_lookup !== "best_effort_slack_users_info") {
      fail("Manifest Google Drive uploader_profile_lookup must be best_effort_slack_users_info");
    }
    if (manifest.google_drive?.file_downloads !== false) fail("Manifest Google Drive file_downloads must be false");
    if (manifest.google_drive?.drive_mutations !== false) fail("Manifest Google Drive drive_mutations must be false");
    if (manifest.luma?.auth_env_var !== "LUMA_API_KEY") fail("Manifest missing LUMA_API_KEY auth env var");
    if (manifest.luma?.base_url !== "https://public-api.luma.com") fail("Manifest Luma base_url must be public-api.luma.com");
    if (manifest.luma?.read_only !== true) fail("Manifest Luma read_only must be true");
    if (manifest.luma?.max_events !== 50) fail("Manifest Luma max_events must be 50");
    if (manifest.luma?.default_event_limit !== 20) fail("Manifest Luma default_event_limit must be 20");
    if (manifest.luma?.max_events_for_context !== 20) fail("Manifest Luma max_events_for_context must be 20");
    if (manifest.luma?.max_guests_per_event !== 250) fail("Manifest Luma max_guests_per_event must be 250");
    if (manifest.luma?.attendance_definition !== "checked_in_at_present") {
      fail("Manifest Luma attendance_definition must be checked_in_at_present");
    }
    for (const country of ["Singapore", "Malaysia", "Indonesia"]) {
      if (!manifest.luma?.country_tags?.includes(country)) fail(`Manifest Luma missing country tag ${country}`);
    }
    for (const location of ["Singapore", "Jakarta", "Bali", "Kuala Lumpur"]) {
      if (!manifest.luma?.location_tags?.includes(location)) fail(`Manifest Luma missing location tag ${location}`);
    }
    for (const eventType of ["Sports", "Appreciation Afternoon", "HR Happy Hour", "Leaders Lounge"]) {
      if (!manifest.luma?.event_type_tags?.includes(eventType)) fail(`Manifest Luma missing event type tag ${eventType}`);
    }
    if (manifest.luma?.preferred_event_filter !== "event_tags") {
      fail("Manifest Luma preferred_event_filter must be event_tags");
    }
    if (manifest.luma?.location_tag_country_map?.Jakarta !== "Indonesia") {
      fail("Manifest Luma must map Jakarta location tag to Indonesia");
    }
    if (!manifest.luma?.allowed_tools?.includes("list_luma_events")) fail("Manifest Luma missing list_luma_events tool");
    if (!manifest.luma?.allowed_tools?.includes("get_luma_event_context")) fail("Manifest Luma missing get_luma_event_context tool");
    if (manifest.luma?.requires_scoped_hubspot_companies !== true) {
      fail("Manifest Luma requires_scoped_hubspot_companies must be true");
    }
    if (manifest.luma?.raw_attendee_exports !== false) fail("Manifest Luma raw_attendee_exports must be false");
    if (manifest.luma?.event_mutations !== false) fail("Manifest Luma event_mutations must be false");
    if (manifest.luma?.hubspot_writeback !== "none") fail("Manifest Luma hubspot_writeback must be none");
    if (manifest.near_me?.google_places_auth_env_var !== "GOOGLE_PLACES_API_KEY") {
      fail("Manifest Near-Me missing GOOGLE_PLACES_API_KEY auth env var");
    }
    if (manifest.near_me?.known_areas_source !== "curated_config_outside_hubspot") {
      fail("Manifest Near-Me known_areas_source must be curated_config_outside_hubspot");
    }
    if (manifest.near_me?.memory_layer !== "bigquery_outlet_matches") {
      fail("Manifest Near-Me memory_layer must be bigquery_outlet_matches");
    }
    if (manifest.near_me?.outlet_matches_table_env_var !== "NURTUREANY_OUTLET_MATCHES_TABLE") {
      fail("Manifest Near-Me outlet_matches_table_env_var must be NURTUREANY_OUTLET_MATCHES_TABLE");
    }
    if (manifest.near_me?.default_outlet_matches_table !== "staffany-warehouse.analytics.nurtureany_near_me_outlet_matches") {
      fail("Manifest Near-Me default outlet matches table is incorrect");
    }
    if (manifest.near_me?.c360_customer_layer !== "analytics.fct_deal_org_company") {
      fail("Manifest Near-Me C360 customer layer must be analytics.fct_deal_org_company");
    }
    if (manifest.near_me?.mrr_enrichment_only !== "analytics.fct_company_org_mrr") {
      fail("Manifest Near-Me MRR enrichment must be analytics.fct_company_org_mrr");
    }
    if (manifest.near_me?.geofence_source !== "kraken_rds.Locations") {
      fail("Manifest Near-Me geofence source must be kraken_rds.Locations");
    }
    if (manifest.near_me?.employee_gps_allowed !== false) fail("Manifest Near-Me must disallow employee GPS");
    if (manifest.near_me?.google_candidate_storage !== "live_candidate_only_until_review_approval") {
      fail("Manifest Near-Me candidate storage must stay review-gated");
    }
    for (const tool of [
      "resolve_known_area_for_near_me",
      "build_near_me_outlet_matches_query",
      "refresh_google_places_for_known_area",
      "build_near_me_c360_customer_query",
      "merge_near_me_sources"
    ]) {
      if (!manifest.near_me?.allowed_tools?.includes(tool)) fail(`Manifest Near-Me missing allowed tool: ${tool}`);
    }
  }
}

const filesToScan = [
  "AGENTS.md",
  "README.md",
  "profile/SOUL.md",
  "profile/config.template.yaml",
  "runtime/access-policy.template.json",
  "skills/nurtureany-sales-bot/SKILL.md",
  "skills/nurtureany-sales-bot/references/hubspot-fields.md",
  "skills/nurtureany-sales-bot/references/sales-best-practices.md",
  "skills/nurtureany-sales-bot/references/playbooks.md",
  "skills/nurtureany-sales-bot/references/pre-demo-game-plans.md",
  "skills/nurtureany-sales-bot/references/regression-cases.md",
  "runtime/slack.md",
  "runtime/hubspot.md",
  "runtime/mcp/hubspot_nurtureany_server.py",
  "runtime/mcp/test_hubspot_nurtureany_server.py",
  "runtime/bigquery.md",
  "runtime/google-calendar.md",
  "runtime/mcp/google_calendar_nurtureany_server.py",
  "runtime/mcp/test_google_calendar_nurtureany_server.py",
  "runtime/google-drive.md",
  "runtime/mcp/google_drive_nurtureany_server.py",
  "runtime/mcp/test_google_drive_nurtureany_server.py",
  "runtime/luma.md",
  "runtime/mcp/luma_nurtureany_server.py",
  "runtime/mcp/test_luma_nurtureany_server.py",
  "runtime/near-me.md",
  "runtime/sql/near-me-outlet-matches.sql",
  "runtime/mcp/near_me_nurtureany_server.py",
  "runtime/mcp/test_near_me_nurtureany_server.py",
  "runtime/exa.md",
  "runtime/mcp/exa_nurtureany_server.py",
  "runtime/mcp/test_exa_nurtureany_server.py",
  "runtime/lusha.md",
  "runtime/mcp/lusha_nurtureany_server.py",
  "runtime/mcp/test_lusha_nurtureany_server.py",
  "runtime/health-checks.md",
  "tests/regression-cases.md"
];

for (const relPath of filesToScan) {
  assertFile(relPath);
  scanForSecretPatterns(relPath);
}

const configText = textOf("profile/config.template.yaml");
if (!configText.includes('provider: "anthropic"')) fail("config.template.yaml must set model.provider to anthropic");
if (!configText.includes('default: "claude-sonnet-4-6"')) fail("config.template.yaml must set model.default to claude-sonnet-4-6");
if (configText.includes("OPENAI_API_KEY")) fail("config.template.yaml must not configure OpenAI API key routing");
if (configText.includes('base_url: "https://api.openai.com/v1"')) fail("config.template.yaml must not configure OpenAI API base_url");
for (const text of [
  "Singapore",
  "Malaysia",
  "Indonesia",
  "eugene@staffany.com",
  "kaiyi@staffany.com",
  "kerren.fong@staffany.com",
  "sarah@staffany.com",
  "NURTUREANY_ACCESS_POLICY_PATH",
  "runtime/access-policy.template.json",
  "unclassified_hubspot_owners",
  "list_my_target_accounts",
  "list_team_target_accounts",
  "audit_hubspot_owner_roster",
  "audit_priority_account_coverage",
  "build_friday_sales_review",
  "NURTUREANY_QO_PIPELINE_IDS",
  "NURTUREANY_QO_STAGE_IDS",
  "NURTUREANY_QO_MET_STAGE_IDS",
  "NURTUREANY_CLOSED_WON_STAGE_IDS",
  "connected_call_target: 40",
  "build_pre_demo_game_plans",
  "list_sales_followup_tasks",
  "check_account_followup_status",
  "check_event_followup_status",
  "generate_free_search_tasks",
  "review_public_enrichment_evidence",
  "scan_drive_event_photos",
  "propose_photo_people_matches",
  "plan_event_photo_followup",
  "1qXlFnr5TKFtsYNWk7ZywBBctDaae3RY-",
  "files:read",
  "nurture_event_photo",
  "plan_hubspot_writeback",
  "google_calendar_nurtureany",
  "GOOGLE_CALENDAR_TOKEN_FILE",
  "google_drive_nurtureany",
  "GOOGLE_DRIVE_TOKEN_FILE",
  "SLACK_BOT_TOKEN",
  "https://www.googleapis.com/auth/drive.readonly",
  "list_drive_folder_images",
  "extract_drive_image_clues",
  "team@staffany.com",
  "team_oauth_shared_calendar",
  "resolved_hubspot_owner_email",
  "confidence_blocked",
  "list_google_calendar_events",
  "audit_google_calendar_meeting_quality",
  "internal_attendee_email_hash_match_to_hubspot_contacts",
  "safe_summary_only_no_raw_emails",
  "luma_nurtureany",
  "LUMA_API_KEY",
  "runtime/mcp/luma_nurtureany_server.py",
  "checked_in_at_present",
  "list_luma_events",
  "get_luma_event_context",
  "near_me_nurtureany",
  "GOOGLE_PLACES_API_KEY",
  "NURTUREANY_KNOWN_AREAS_FILE",
  "NURTUREANY_OUTLET_MATCHES_TABLE",
  "resolve_known_area_for_near_me",
  "build_near_me_outlet_matches_query",
  "refresh_google_places_for_known_area",
  "build_near_me_c360_customer_query",
  "merge_near_me_sources",
  "analytics.fct_deal_org_company",
  "kraken_rds.Locations",
  "exa_nurtureany",
  "EXA_API_KEY",
  "search_exa_people_candidates",
  "lusha_nurtureany",
  "LUSHA_API_KEY",
  "search_lusha_decision_maker_candidates",
  "reveal_lusha_contact_details",
  "get_lusha_credit_usage"
]) {
  if (!configText.includes(text)) fail(`config.template.yaml missing required text: ${text}`);
}

const soulText = textOf("profile/SOUL.md");
for (const text of [
  "plan-first",
  "run",
  "explicit approval",
  "Never auto-send",
  "Confidence",
  "sales-owned follow-up tasks",
  "build_friday_sales_review",
  "audit_priority_account_coverage",
  "sales-best-practices.md",
  "120/150 account coverage",
  "40 connected calls",
  "QO/QO Met",
  "pre-demo game plans",
  "NURTUREANY_ACCESS_POLICY_PATH",
  "Unclassified HubSpot owners are blocked",
  "Managers cannot create HubSpot write-back previews",
  "Google Calendar",
  "team@staffany.com",
  "audit_google_calendar_meeting_quality",
  "calendar_audit_seed",
  "raw attendee emails",
  "bounded `query` option on the target-account list tools",
  "resolved HubSpot owner email as the AE calendar ID",
  "Confidence: blocked",
  "Luma",
  "checked_in_at",
  "raw guest lists",
  "cost_report",
  "credit_report",
  "approval_marker",
  "reveal_phones",
  "exact company names",
  "ambiguous",
  "people layer",
  "photo match",
  "list_drive_folder_images",
  "extract_drive_image_clues",
  "uploader display names",
  "original Slack uploader",
  "Luma event-date context",
  "must not auto-tag a HubSpot contact/person",
  "nurture_event_photo",
  "known_area",
  "outlet_matches",
  "Google Places",
  "fct_deal_org_company",
  "pricing needed",
  "case-study match needed"
]) {
  if (!soulText.includes(text)) fail(`SOUL.md missing required safety/contract text: ${text}`);
}

const skillText = textOf("skills/nurtureany-sales-bot/SKILL.md");
for (const text of [
  "NURTUREANY_ACCESS_POLICY_PATH",
  "unclassified HubSpot owners are blocked",
  "hs_is_target_account",
  "company_country",
  "hubspot_owner_id",
  "references/sales-best-practices.md",
  "references/pre-demo-game-plans.md",
  "Nurture-ready enriched",
  "verified decision maker",
  "missing-decision-maker counts",
  "Do not use Honcho",
  "Confidence: <verified | needs-check | blocked>",
  "audit_hubspot_owner_roster",
  "audit_priority_account_coverage",
  "build_friday_sales_review",
  "120_150_accounts_worked",
  "40_connected_calls",
  "NURTUREANY_QO_PIPELINE_IDS",
  "build_pre_demo_game_plans",
  "exact company names",
  "ambiguous matches",
  "pricing needed",
  "case-study match needed",
  "list_sales_followup_tasks",
  "sales-owned HubSpot follow-up tasks",
  "check_account_followup_status",
  "check_event_followup_status",
  "WhatsApp communications",
  "generate_free_search_tasks",
  "review_public_enrichment_evidence",
  "scan_drive_event_photos",
  "propose_photo_people_matches",
  "list_drive_folder_images",
  "extract_drive_image_clues",
  "uploader display names",
  "original Slack uploader",
  "Luma event-date context",
  "must not auto-tag a HubSpot contact/person",
  "plan_event_photo_followup",
  "files:read",
  "nurture_person_appearance",
  "list_google_calendar_events",
  "audit_google_calendar_meeting_quality",
  "calendar_audit_seed",
  "raw attendee emails",
  "team@staffany.com",
  "owner email as a Google Calendar `calendar_ids` entry",
  "Confidence: blocked",
  "list_luma_events",
  "get_luma_event_context",
  "checked_in_at",
  "raw guest lists",
  "resolve_known_area_for_near_me",
  "build_near_me_outlet_matches_query",
  "refresh_google_places_for_known_area",
  "build_near_me_c360_customer_query",
  "merge_near_me_sources",
  "outlet_matches",
  "Google Places",
  "fct_deal_org_company",
  "kraken_rds.Locations",
  "search_exa_people_candidates",
  "search_lusha_decision_maker_candidates",
  "reveal_lusha_contact_details",
  "get_lusha_credit_usage",
  "cost_report",
  "credit_report",
  "approval_marker",
  "revealEmails",
  "revealPhones"
]) {
  if (!skillText.includes(text)) fail(`SKILL.md missing required text: ${text}`);
}

const salesBestPracticesText = textOf("skills/nurtureany-sales-bot/references/sales-best-practices.md");
for (const text of [
  "HubSpot Override Rule",
  "protected 150-account pool",
  "120 of 150 priority accounts",
  "30 WhatsApp nurturing touches",
  "40 connected calls",
  "double taps",
  "QO-to-QO-Met",
  "associated contact",
  "verified decision maker",
  "build_friday_sales_review",
  "build_pre_demo_game_plans",
  "manual-review only",
  "Do not build a new MCP"
]) {
  if (!salesBestPracticesText.includes(text)) {
    fail(`sales-best-practices.md missing required text: ${text}`);
  }
}

const accessPolicyTemplate = readJson(join(appRoot, "runtime/access-policy.template.json"));
if (accessPolicyTemplate) {
  if (!Array.isArray(accessPolicyTemplate.sales_reps)) fail("access-policy.template.json must include sales_reps examples");
  const templateText = textOf("runtime/access-policy.template.json");
  for (const text of ["example.invalid", "NURTUREANY_ACCESS_POLICY_PATH", "Do not commit the real sales roster"]) {
    if (!templateText.includes(text)) fail(`access-policy.template.json missing required text: ${text}`);
  }
}

const hubspotServerText = textOf("runtime/mcp/hubspot_nurtureany_server.py");
for (const text of [
  "ACCESS_POLICY_ENV_VAR = \"NURTUREANY_ACCESS_POLICY_PATH\"",
  "audit_hubspot_owner_roster",
  "unclassified",
  "Managers have read-only team scope",
  "Company is outside caller scope or is not a HubSpot target account",
  "build_pre_demo_game_plans",
  "audit_priority_account_coverage",
  "build_friday_sales_review",
  "CALL_PROPERTIES",
  "MEETING_PROPERTIES",
  "CONNECTED_CALL_MIN_DURATION_MS",
  "NURTUREANY_QO_PIPELINE_IDS",
  "PRE_DEMO_GAME_PLAN_ACCOUNT_LIMIT = 5",
  "_resolve_scoped_company_name",
  "ambiguous_matches",
  "pricing needed",
  "case-study match needed",
  "list_sales_followup_tasks",
  "check_account_followup_status",
  "check_event_followup_status",
  "COMMUNICATION_PROPERTIES",
  "calendar_audit_seed",
  "_hash_email",
  "contact_match_records",
  "find_t90_renewal_gaps",
  "_decision_maker_coverage",
  "missing_decision_maker_account_count",
  "role_only_decision_maker_account_count",
  "TASK_PROPERTIES",
  "sales_followup_task_count",
  "\"hubspot_scoped\": True",
  "scope_source",
  "DRIVE_ALL_RANDOM_FOLDER_ID",
  "scan_drive_event_photos",
  "propose_photo_people_matches",
  "plan_event_photo_followup",
  "nurture_person_appearance",
  "confirmation_request",
  "uploader_confirmation_batches",
  "luma_event_context",
  "auto_event_tag_status"
]) {
  if (!hubspotServerText.includes(text)) fail(`runtime/mcp/hubspot_nurtureany_server.py missing required text: ${text}`);
}

const exaText = textOf("runtime/exa.md");
for (const text of [
  "POST /search",
  "category: \"people\"",
  "EXA_API_KEY",
  "cost_report",
  "Requires NurtureAny scoped HubSpot company inputs",
  "LinkedIn-Safe Handling",
  "manual-check evidence",
  "Exa Admin API",
  "15s hard timeout",
  "No Exa output mutates HubSpot directly"
]) {
  if (!exaText.includes(text)) fail(`runtime/exa.md missing required text: ${text}`);
}

const exaServerText = textOf("runtime/mcp/exa_nurtureany_server.py");
for (const text of [
  "EXA_API_KEY",
  "EXA_TIMEOUT_SECONDS = 15",
  "EXA_USER_AGENT",
  "MAX_SEARCH_COMPANIES = 5",
  "MAX_CANDIDATES_PER_COMPANY = 5",
  "\"category\": \"people\"",
  "\"type\": \"auto\"",
  "cost_report",
  "SCOPE_SOURCE = \"hubspot_nurtureany\"",
  "requires scoped HubSpot company inputs",
  "linkedin_manual_check",
  "search_exa_people_candidates"
]) {
  if (!exaServerText.includes(text)) fail(`runtime/mcp/exa_nurtureany_server.py missing required text: ${text}`);
}

const googleCalendarText = textOf("runtime/google-calendar.md");
for (const text of [
  "team@staffany.com",
  "GOOGLE_CALENDAR_TOKEN_FILE",
  "https://www.googleapis.com/auth/calendar.readonly",
  "list_google_calendar_events",
  "audit_google_calendar_meeting_quality",
  "calendar_audit_seed",
  "Email hashes/domains",
  "This is not a Google service account",
  "resolved HubSpot account owner",
  "Cap reads at 5 calendars and 50 events per calendar",
  "Do not create, update, delete, invite, RSVP, export attendees",
  "Confidence: blocked"
]) {
  if (!googleCalendarText.includes(text)) fail(`runtime/google-calendar.md missing required text: ${text}`);
}

const googleCalendarServerText = textOf("runtime/mcp/google_calendar_nurtureany_server.py");
for (const text of [
  "GOOGLE_CALENDAR_TOKEN_FILE",
  "CALENDAR_READONLY_SCOPE",
  "DEFAULT_ACCOUNT_EMAIL = \"team@staffany.com\"",
  "MAX_CALENDARS = 5",
  "MAX_EVENTS_PER_CALENDAR = 50",
  "list_google_calendar_events",
  "audit_google_calendar_meeting_quality",
  "contact_email_match",
  "no-calendar-follow-up",
  "hubspot_followup_check",
  "No event mutations, attendee exports, descriptions, or raw guest lists.",
  "calendar_access_mode",
  "blocked_calendar_ids",
  "mcp.run(\"stdio\")"
]) {
  if (!googleCalendarServerText.includes(text)) {
    fail(`runtime/mcp/google_calendar_nurtureany_server.py missing required text: ${text}`);
  }
}

const googleDriveText = textOf("runtime/google-drive.md");
for (const text of [
  "team@staffany.com",
  "GOOGLE_DRIVE_TOKEN_FILE",
  "https://www.googleapis.com/auth/drive.readonly",
  "list_drive_folder_images",
  "extract_drive_image_clues",
  "slack_uploader_name",
  "users.info",
  "all-random",
  "Download image bytes only transiently",
  "Confidence: blocked"
]) {
  if (!googleDriveText.includes(text)) fail(`runtime/google-drive.md missing required text: ${text}`);
}

const googleDriveServerText = textOf("runtime/mcp/google_drive_nurtureany_server.py");
for (const text of [
  "GOOGLE_DRIVE_TOKEN_FILE",
  "DRIVE_READONLY_SCOPE",
  "DEFAULT_ACCOUNT_EMAIL = \"team@staffany.com\"",
  "DEFAULT_DRIVE_FOLDER_ID = \"1qXlFnr5TKFtsYNWk7ZywBBctDaae3RY-\"",
  "MAX_DRIVE_FILES = 100",
  "list_drive_folder_images",
  "extract_drive_image_clues",
  "slack_uploader_name",
  "SLACK_BOT_TOKEN",
  "Metadata only. No image bytes, Drive mutations, exports, or raw image copies.",
  "Transient download for OCR/vision only",
  "drive_access_mode",
  "mimeType contains 'image/'",
  "mcp.run(\"stdio\")"
]) {
  if (!googleDriveServerText.includes(text)) {
    fail(`runtime/mcp/google_drive_nurtureany_server.py missing required text: ${text}`);
  }
}

const lumaText = textOf("runtime/luma.md");
for (const text of [
  "https://public-api.luma.com",
  "x-luma-api-key",
  "LUMA_API_KEY",
  "GET /v1/calendar/list-events",
  "GET /v1/calendar/event-tags/list",
  "GET /v1/event/get",
  "GET /v1/event/get-guests",
  "list_luma_events",
  "get_luma_event_context",
  "event_tags=[\"Singapore\", \"Sports\"]",
  "event_tags=[\"Jakarta\", \"Appreciation Afternoon\"]",
  "HR Happy Hour",
  "Appreciation Afternoon",
  "Leaders Lounge",
  "runtime/mcp/luma_nurtureany_server.py",
  "15s hard timeout",
  "Requires scoped HubSpot company inputs",
  "checked_in_at",
  "Do not expose raw attendee exports",
  "Do not create, update, invite, RSVP, check in",
  "Confidence: blocked"
]) {
  if (!lumaText.includes(text)) fail(`runtime/luma.md missing required text: ${text}`);
}

const lumaServerText = textOf("runtime/mcp/luma_nurtureany_server.py");
for (const text of [
  "LUMA_API_KEY",
  "LUMA_TIMEOUT_SECONDS = 15",
  "LUMA_USER_AGENT",
  "MAX_EVENTS = 50",
  "MAX_GUESTS_PER_EVENT = 250",
  "SCOPE_SOURCE = \"hubspot_nurtureany\"",
  "x-luma-api-key",
  "EVENT_TYPE_TAGS",
  "COUNTRY_TAGS",
  "LOCATION_TAGS",
  "event_tags",
  "event_tag_filters",
  "event_type",
  "location_filter",
  "country_filter",
  "/v1/calendar/event-tags/list",
  "list_luma_events",
  "get_luma_event_context",
  "requires scoped HubSpot company inputs",
  "checked_in_at",
  "email_hash",
  "mcp.run(\"stdio\")"
]) {
  if (!lumaServerText.includes(text)) fail(`runtime/mcp/luma_nurtureany_server.py missing required text: ${text}`);
}

const nearMeText = textOf("runtime/near-me.md");
for (const text of [
  "known_area",
  "outlet_matches",
  "Google Places",
  "places:searchNearby",
  "analytics.fct_deal_org_company",
  "analytics.fct_company_org_mrr",
  "kraken_rds.Locations",
  "dim_org_section",
  "live_candidate_only_until_review_approval",
  "raw employee location rows"
]) {
  if (!nearMeText.includes(text)) fail(`runtime/near-me.md missing required text: ${text}`);
}

const nearMeServerText = textOf("runtime/mcp/near_me_nurtureany_server.py");
for (const text of [
  "GOOGLE_PLACES_API_KEY",
  "GOOGLE_PLACES_FIELD_MASK",
  "places:searchNearby",
  "DEFAULT_OUTLET_MATCHES_TABLE = \"staffany-warehouse.analytics.nurtureany_near_me_outlet_matches\"",
  "NURTUREANY_KNOWN_AREAS_FILE",
  "resolve_known_area_for_near_me",
  "build_near_me_outlet_matches_query",
  "refresh_google_places_for_known_area",
  "build_near_me_c360_customer_query",
  "merge_near_me_sources",
  "`staffany-warehouse.kraken_rds.Locations`",
  "`staffany-warehouse.analytics.fct_deal_org_company`",
  "LEFT JOIN `staffany-warehouse.analytics.fct_company_org_mrr`",
  "live_candidate_only_until_review_approval",
  "mcp.run(\"stdio\")"
]) {
  if (!nearMeServerText.includes(text)) fail(`runtime/mcp/near_me_nurtureany_server.py missing required text: ${text}`);
}

const nearMeSqlText = textOf("runtime/sql/near-me-outlet-matches.sql");
for (const text of [
  "CREATE TABLE IF NOT EXISTS `staffany-warehouse.analytics.nurtureany_near_me_outlet_matches`",
  "outlet_match_id STRING NOT NULL",
  "google_place_id STRING",
  "hubspot_company_id STRING",
  "organisation_id STRING",
  "match_status STRING NOT NULL",
  "CLUSTER BY area_id, google_place_id, hubspot_company_id, organisation_id",
  "Do not run through staffany_bigquery.execute_sql_readonly"
]) {
  if (!nearMeSqlText.includes(text)) fail(`runtime/sql/near-me-outlet-matches.sql missing required text: ${text}`);
}

const lushaText = textOf("runtime/lusha.md");
for (const text of [
  "POST /prospecting/contact/search",
  "POST /prospecting/contact/enrich",
  "GET /account/usage",
  "credit_report",
  "Requires NurtureAny scoped HubSpot company inputs",
  "Requires scoped HubSpot `company_ids`",
  "approval_marker",
  "revealEmails",
  "revealPhones",
  "15s hard timeout",
  "Selected contact PII",
  "No actual HubSpot mutation"
]) {
  if (!lushaText.includes(text)) fail(`runtime/lusha.md missing required text: ${text}`);
}

const lushaServerText = textOf("runtime/mcp/lusha_nurtureany_server.py");
for (const text of [
  "LUSHA_API_KEY",
  "LUSHA_TIMEOUT_SECONDS = 15",
  "LUSHA_USER_AGENT",
  "MAX_SEARCH_COMPANIES = 5",
  "MAX_CANDIDATES_PER_COMPANY = 5",
  "MAX_REVEAL_CONTACTS = 3",
  "revealEmails",
  "revealPhones",
  "credit_report",
  "SCOPE_SOURCE = \"hubspot_nurtureany\"",
  "scoped_company_ids",
  "plan_hubspot_writeback"
]) {
  if (!lushaServerText.includes(text)) fail(`runtime/mcp/lusha_nurtureany_server.py missing required text: ${text}`);
}

const compileCheck = spawnSync("python3", ["-m", "py_compile", join(appRoot, "runtime/mcp/lusha_nurtureany_server.py")], {
  encoding: "utf8"
});
if (compileCheck.status !== 0) {
  fail(`Python compile failed for Lusha MCP: ${(compileCheck.stderr || compileCheck.stdout).trim()}`);
}

const hubspotCompileCheck = spawnSync("python3", ["-m", "py_compile", join(appRoot, "runtime/mcp/hubspot_nurtureany_server.py")], {
  encoding: "utf8"
});
if (hubspotCompileCheck.status !== 0) {
  fail(`Python compile failed for HubSpot MCP: ${(hubspotCompileCheck.stderr || hubspotCompileCheck.stdout).trim()}`);
}

const exaCompileCheck = spawnSync("python3", ["-m", "py_compile", join(appRoot, "runtime/mcp/exa_nurtureany_server.py")], {
  encoding: "utf8"
});
if (exaCompileCheck.status !== 0) {
  fail(`Python compile failed for Exa MCP: ${(exaCompileCheck.stderr || exaCompileCheck.stdout).trim()}`);
}

const googleCalendarCompileCheck = spawnSync("python3", ["-m", "py_compile", join(appRoot, "runtime/mcp/google_calendar_nurtureany_server.py")], {
  encoding: "utf8"
});
if (googleCalendarCompileCheck.status !== 0) {
  fail(`Python compile failed for Google Calendar MCP: ${(googleCalendarCompileCheck.stderr || googleCalendarCompileCheck.stdout).trim()}`);
}

const googleDriveCompileCheck = spawnSync("python3", ["-m", "py_compile", join(appRoot, "runtime/mcp/google_drive_nurtureany_server.py")], {
  encoding: "utf8"
});
if (googleDriveCompileCheck.status !== 0) {
  fail(`Python compile failed for Google Drive MCP: ${(googleDriveCompileCheck.stderr || googleDriveCompileCheck.stdout).trim()}`);
}

const lumaCompileCheck = spawnSync("python3", ["-m", "py_compile", join(appRoot, "runtime/mcp/luma_nurtureany_server.py")], {
  encoding: "utf8"
});
if (lumaCompileCheck.status !== 0) {
  fail(`Python compile failed for Luma MCP: ${(lumaCompileCheck.stderr || lumaCompileCheck.stdout).trim()}`);
}

const nearMeCompileCheck = spawnSync("python3", ["-m", "py_compile", join(appRoot, "runtime/mcp/near_me_nurtureany_server.py")], {
  encoding: "utf8"
});
if (nearMeCompileCheck.status !== 0) {
  fail(`Python compile failed for Near-Me MCP: ${(nearMeCompileCheck.stderr || nearMeCompileCheck.stdout).trim()}`);
}

const hubspotUnitCheck = spawnSync("python3", ["-m", "unittest", "apps/nurtureany-sales-bot/runtime/mcp/test_hubspot_nurtureany_server.py"], {
  cwd: repoRoot,
  encoding: "utf8"
});
if (hubspotUnitCheck.status !== 0) {
  fail(`Python unit tests failed for HubSpot MCP: ${(hubspotUnitCheck.stderr || hubspotUnitCheck.stdout).trim()}`);
}

const exaUnitCheck = spawnSync("python3", ["-m", "unittest", "apps/nurtureany-sales-bot/runtime/mcp/test_exa_nurtureany_server.py"], {
  cwd: repoRoot,
  encoding: "utf8"
});
if (exaUnitCheck.status !== 0) {
  fail(`Python unit tests failed for Exa MCP: ${(exaUnitCheck.stderr || exaUnitCheck.stdout).trim()}`);
}

const googleCalendarUnitCheck = spawnSync("python3", ["-m", "unittest", "apps/nurtureany-sales-bot/runtime/mcp/test_google_calendar_nurtureany_server.py"], {
  cwd: repoRoot,
  encoding: "utf8"
});
if (googleCalendarUnitCheck.status !== 0) {
  fail(`Python unit tests failed for Google Calendar MCP: ${(googleCalendarUnitCheck.stderr || googleCalendarUnitCheck.stdout).trim()}`);
}

const googleDriveUnitCheck = spawnSync("python3", ["-m", "unittest", "apps/nurtureany-sales-bot/runtime/mcp/test_google_drive_nurtureany_server.py"], {
  cwd: repoRoot,
  encoding: "utf8"
});
if (googleDriveUnitCheck.status !== 0) {
  fail(`Python unit tests failed for Google Drive MCP: ${(googleDriveUnitCheck.stderr || googleDriveUnitCheck.stdout).trim()}`);
}

const lumaUnitCheck = spawnSync("python3", ["-m", "unittest", "apps/nurtureany-sales-bot/runtime/mcp/test_luma_nurtureany_server.py"], {
  cwd: repoRoot,
  encoding: "utf8"
});
if (lumaUnitCheck.status !== 0) {
  fail(`Python unit tests failed for Luma MCP: ${(lumaUnitCheck.stderr || lumaUnitCheck.stdout).trim()}`);
}

const nearMeUnitCheck = spawnSync("python3", ["-m", "unittest", "apps/nurtureany-sales-bot/runtime/mcp/test_near_me_nurtureany_server.py"], {
  cwd: repoRoot,
  encoding: "utf8"
});
if (nearMeUnitCheck.status !== 0) {
  fail(`Python unit tests failed for Near-Me MCP: ${(nearMeUnitCheck.stderr || nearMeUnitCheck.stdout).trim()}`);
}

const unitCheck = spawnSync("python3", ["-m", "unittest", "apps/nurtureany-sales-bot/runtime/mcp/test_lusha_nurtureany_server.py"], {
  cwd: repoRoot,
  encoding: "utf8"
});
if (unitCheck.status !== 0) {
  fail(`Python unit tests failed for Lusha MCP: ${(unitCheck.stderr || unitCheck.stdout).trim()}`);
}

if (failures.length > 0) {
  console.error("NurtureAny Sales Bot packet verification failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log("NurtureAny Sales Bot packet verification passed.");
