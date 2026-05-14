import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import {
  assertFile as sharedAssertFile,
  readJson as sharedReadJson,
  scanForSecretPatterns as sharedScanForSecretPatterns,
  textOf as sharedTextOf
} from "./lib/app-packet-verify.mjs";

const repoRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
const appRoot = join(repoRoot, "apps", "nurtureany-sales-bot");
const manifestPath = join(appRoot, "app.manifest.json");

const failures = [];

function fail(message) {
  failures.push(message);
}

function readJson(path) {
  return sharedReadJson(path, fail);
}

function assertFile(relPath) {
  sharedAssertFile(appRoot, relPath, fail);
}

function textOf(relPath) {
  return sharedTextOf(appRoot, relPath);
}

function repoTextOf(relPath) {
  const path = join(repoRoot, relPath);
  if (!existsSync(path)) return "";
  return readFileSync(path, "utf8");
}

function scanForSecretPatterns(relPath) {
  sharedScanForSecretPatterns(appRoot, relPath, fail);
}

function sortedUnique(values) {
  return [...new Set(values)].sort();
}

function decoratedMcpTools(relPath) {
  const text = textOf(relPath);
  const tools = [];
  const pattern = /@mcp\.tool\(\)\s*(?:\n\s*#[^\n]*)*\n\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(/g;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    tools.push(match[1]);
  }
  return tools;
}

function compareSortedArrays(label, actual, expected) {
  const actualList = sortedUnique(actual);
  const expectedList = sortedUnique(expected);
  const missing = expectedList.filter((item) => !actualList.includes(item));
  const extra = actualList.filter((item) => !expectedList.includes(item));
  for (const item of missing) fail(`${label} missing: ${item}`);
  for (const item of extra) fail(`${label} unexpected: ${item}`);
}

if (!existsSync(manifestPath)) {
  fail("Missing apps/nurtureany-sales-bot/app.manifest.json");
} else {
  const manifest = readJson(manifestPath);
  if (manifest) {
    if (manifest.profile_name !== "nurtureanysalesbot") fail("Manifest profile_name must be nurtureanysalesbot");
    if (manifest.model !== "claude-sonnet-4-6") fail("Manifest model must be claude-sonnet-4-6");
    if (manifest.secrets_copied !== false) fail("Manifest secrets_copied must be false");
    if (manifest.external_message_sending !== "approval_gated_eazybe_templates") {
      fail("Manifest external_message_sending must be approval_gated_eazybe_templates");
    }
    if (manifest.whatsapp_auto_send !== false) fail("Manifest whatsapp_auto_send must be false");
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
    const sarahAlias = managerByEmail.get("sarah.ayutania@staffany.com") || [];
    if (!sarahAlias.includes("Indonesia") || sarahAlias.includes("Singapore") || sarahAlias.includes("Malaysia")) {
      fail("Manifest Sarah alias scope must be Indonesia only");
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
    if (manifest.quick_autorun?.enabled !== true) fail("Manifest quick_autorun must be enabled");
    if (manifest.quick_autorun?.tool !== "read_recent_slack_intent_context") {
      fail("Manifest quick_autorun tool must be read_recent_slack_intent_context");
    }
    if (manifest.quick_autorun?.max_messages !== 10) fail("Manifest quick_autorun max_messages must be 10");
    if (manifest.quick_autorun?.max_lookback_minutes !== 30) {
      fail("Manifest quick_autorun max_lookback_minutes must be 30");
    }
    if (manifest.quick_autorun?.max_expected_seconds !== 60) {
      fail("Manifest quick_autorun max_expected_seconds must be 60");
    }
    for (const workClass of ["read_only", "preview_only", "draft_only"]) {
      if (!manifest.quick_autorun?.allowed_work?.includes(workClass)) {
        fail(`Manifest quick_autorun missing allowed work: ${workClass}`);
      }
    }
    for (const blockedClass of ["hubspot_mutation", "external_message_send", "paid_enrichment", "public_deep_research", "photo_or_deck", "broad_audit", "bulk_export"]) {
      if (!manifest.quick_autorun?.blocked_source_classes?.includes(blockedClass)) {
        fail(`Manifest quick_autorun missing blocked source class: ${blockedClass}`);
      }
    }
    if (manifest.quick_autorun?.slack_context?.token_env_var !== "SLACK_BOT_TOKEN") {
      fail("Manifest quick_autorun Slack context must use SLACK_BOT_TOKEN");
    }
    if (manifest.quick_autorun?.slack_context?.configured_channel_ids_env_var !== "NURTUREANY_SLACK_INTENT_CHANNEL_IDS") {
      fail("Manifest quick_autorun Slack context must name NURTUREANY_SLACK_INTENT_CHANNEL_IDS");
    }
    if (manifest.quick_autorun?.slack_context?.configured_thread_channel_ids_env_var !== "NURTUREANY_SLACK_THREAD_CONTEXT_CHANNEL_IDS") {
      fail("Manifest quick_autorun Slack context must name NURTUREANY_SLACK_THREAD_CONTEXT_CHANNEL_IDS");
    }
    if (manifest.quick_autorun?.slack_context?.public_thread_channels_env_var !== "NURTUREANY_SLACK_THREAD_CONTEXT_PUBLIC_CHANNELS") {
      fail("Manifest quick_autorun Slack context must name NURTUREANY_SLACK_THREAD_CONTEXT_PUBLIC_CHANNELS");
    }
    if (manifest.quick_autorun?.slack_context?.configured_public_thread_channel_auto_join !== true) {
      fail("Manifest quick_autorun Slack context must enable configured public thread-channel auto join");
    }
    if (manifest.quick_autorun?.slack_context?.public_channels_only !== true) {
      fail("Manifest quick_autorun Slack context must restrict broad thread reads to public channels only");
    }
    if (manifest.quick_autorun?.slack_context?.raw_transcript_persistence !== false) {
      fail("Manifest quick_autorun must disable raw transcript persistence");
    }
    if (manifest.quick_autorun?.slack_context?.user_token_fallback !== false) {
      fail("Manifest quick_autorun must disable user token fallback");
    }
    if (manifest.quick_autorun?.slack_context?.slack_connector_fallback !== false) {
      fail("Manifest quick_autorun must disable Slack connector fallback");
    }

    const paths = manifest.paths || {};
    for (const value of Object.values(paths)) {
      if (Array.isArray(value)) {
        for (const relPath of value) assertFile(relPath);
      } else {
        assertFile(value);
      }
    }
    const references = paths.references || [];
    const expectedReferenceOrder = [
      "skills/nurtureany-sales-bot/references/hubspot-fields.md",
      "skills/nurtureany-sales-bot/references/sales-best-practices.md",
      "skills/nurtureany-sales-bot/references/sop-tool-coverage.md",
      "skills/nurtureany-sales-bot/references/playbooks.md",
      "skills/nurtureany-sales-bot/references/pre-demo-game-plans.md",
      "skills/nurtureany-sales-bot/references/case-studies.md",
      "skills/nurtureany-sales-bot/references/regression-cases.md"
    ];
    let lastReferenceIndex = -1;
    for (const reference of expectedReferenceOrder) {
      const index = references.indexOf(reference);
      if (index === -1) {
        fail(`Manifest references missing source-order file: ${reference}`);
      } else if (index < lastReferenceIndex) {
        fail(`Manifest references source order is wrong around: ${reference}`);
      }
      lastReferenceIndex = Math.max(lastReferenceIndex, index);
    }

    const expectedReadTools = [
      "read_recent_slack_intent_context",
      "get_current_slack_thread_context",
      "get_selected_slack_thread_context",
      "list_inbound_threads",
      "get_inbound_thread_context",
      "audit_inbound_sla",
      "list_marketing_campaigns",
      "get_campaign_assets",
      "get_campaign_social_effectiveness",
      "get_marketing_touch_context",
      "get_marketing_campaign_attribution",
      "list_my_target_accounts",
      "list_team_target_accounts",
      "audit_hubspot_owner_roster",
      "audit_priority_account_coverage",
      "build_sales_metric_actuals_query",
      "build_hubspot_revenue_funnel_metrics",
      "build_ae_coaching_audit",
      "audit_owner_whatsapp_kns_window",
      "prepare_sales_navigator_decision_maker_queue",
      "build_friday_sales_review",
      "build_manager_chase_plan",
      "find_aircall_calls",
      "transcribe_aircall_recording",
      "get_account_context",
      "build_pre_demo_game_plans",
      "find_sales_case_studies",
      "build_singapore_lead_enrichment_plan",
      "list_active_deals_missing_next_meeting",
      "list_sales_followup_tasks",
      "count_owner_whatsapp_sent_today",
      "check_account_followup_status",
      "check_event_followup_status",
      "build_daily_nurture_plan",
      "find_target_accounts_by_luma_match_keys",
      "score_nurture_accounts",
      "find_contact_gaps",
      "find_t90_renewal_gaps",
      "generate_free_search_tasks",
      "review_public_enrichment_evidence",
      "scan_drive_event_photos",
      "propose_photo_people_matches",
      "list_drive_folder_images",
      "read_google_slides_deck",
      "extract_drive_image_clues",
      "read_nurture_material_registry",
      "read_indonesia_event_registration_attendance",
      "check_eazybe_send_status",
      "build_daily_nurture_reminder",
      "record_nurtureany_operation_checkpoint",
      "read_nurtureany_operation_ledger",
      "draft_nurture_message",
      "list_google_calendar_events",
      "audit_google_calendar_meeting_quality",
      "list_luma_events",
      "get_luma_event_match_keys",
      "find_target_accounts_by_luma_match_keys",
      "get_luma_event_context",
      "resolve_known_area_for_near_me",
      "build_near_me_outlet_matches_query",
      "refresh_google_places_for_known_area",
      "build_near_me_c360_customer_query",
      "prepare_near_me_seed_review_candidates",
      "merge_near_me_sources",
      "research_public_company_signals",
      "find_brand_parent_candidates",
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
    if (!manifest.tools?.preview?.includes("preview_eazybe_template_messages")) {
      fail("Manifest missing preview tool: preview_eazybe_template_messages");
    }
    if (!manifest.tools?.approval_gated_enrichment?.includes("reveal_lusha_contact_details")) {
      fail("Manifest missing approval-gated enrichment tool: reveal_lusha_contact_details");
    }
    if (!manifest.tools?.approval_gated_external_message_sending?.includes("send_approved_eazybe_messages")) {
      fail("Manifest missing approval-gated Eazybe tool: send_approved_eazybe_messages");
    }
    const plannedWriteTools = ["create_hubspot_task", "append_hubspot_note", "update_nurture_fields"];
    if (manifest.tools?.write_phase_planned_disabled?.state !== "disabled_in_v1") {
      fail("Manifest write_phase_planned_disabled.state must be disabled_in_v1");
    }
    compareSortedArrays(
      "Manifest planned disabled write tools",
      manifest.tools?.write_phase_planned_disabled?.tools || [],
      plannedWriteTools
    );
    if (manifest.tools?.mutation_requires_explicit_approval) {
      fail("Manifest must not expose callable-looking mutation_requires_explicit_approval tools in V1");
    }
    for (const tool of ["create_hubspot_task", "append_hubspot_note", "update_nurture_fields"]) {
      const disabled = manifest.tools?.write_phase_planned_disabled;
      if (disabled?.state !== "disabled_in_v1" || !disabled?.tools?.includes(tool)) {
        fail(`Manifest missing disabled planned write tool: ${tool}`);
      }
    }
    const manifestCallableTools = [
      ...(manifest.tools?.read || []),
      ...(manifest.tools?.preview || []),
      ...(manifest.tools?.approval_gated_enrichment || []),
      ...(manifest.tools?.approval_gated_external_message_sending || [])
    ];
    const actualMcpTools = [
      "runtime/mcp/slack_nurtureany_server.py",
      "runtime/mcp/hubspot_nurtureany_server.py",
      "runtime/mcp/aircall_nurtureany_server.py",
      "runtime/mcp/google_calendar_nurtureany_server.py",
      "runtime/mcp/google_drive_nurtureany_server.py",
      "runtime/mcp/eazybe_nurtureany_server.py",
      "runtime/mcp/luma_nurtureany_server.py",
      "runtime/mcp/near_me_nurtureany_server.py",
      "runtime/mcp/public_research_nurtureany_server.py",
      "runtime/mcp/exa_nurtureany_server.py",
      "runtime/mcp/lusha_nurtureany_server.py"
    ].flatMap((relPath) => decoratedMcpTools(relPath));
    compareSortedArrays("Manifest callable tools vs MCP decorators", manifestCallableTools, actualMcpTools);
    for (const tool of plannedWriteTools) {
      if (actualMcpTools.includes(tool)) fail(`Planned write tool must not be exposed by MCP decorator in V1: ${tool}`);
    }
    if (manifest.lusha?.auth_env_var !== "LUSHA_API_KEY") fail("Manifest missing LUSHA_API_KEY auth env var");
    if (manifest.lusha?.max_search_companies !== 5) fail("Manifest Lusha max_search_companies must be 5");
    if (manifest.lusha?.max_candidates_per_company !== 5) fail("Manifest Lusha max_candidates_per_company must be 5");
    if (manifest.lusha?.max_reveal_contacts !== 3) fail("Manifest Lusha max_reveal_contacts must be 3");
    if (manifest.lusha?.selected_pii_in_slack !== true) fail("Manifest Lusha selected_pii_in_slack must be true");
    if (manifest.lusha?.bulk_contact_exports !== false) fail("Manifest Lusha bulk_contact_exports must be false");
    if (!manifest.aircall?.auth_env_vars?.includes("AIRCALL_API_ID")) fail("Manifest Aircall missing AIRCALL_API_ID");
    if (!manifest.aircall?.auth_env_vars?.includes("AIRCALL_API_TOKEN")) fail("Manifest Aircall missing AIRCALL_API_TOKEN");
    if (manifest.aircall?.transcription_auth_env_var !== "OPENAI_API_KEY") fail("Manifest Aircall missing OPENAI_API_KEY");
    if (manifest.aircall?.read_only !== true) fail("Manifest Aircall read_only must be true");
    if (manifest.aircall?.default_transcription_model !== "gpt-4o-transcribe-diarize") {
      fail("Manifest Aircall default model must be gpt-4o-transcribe-diarize");
    }
    if (manifest.aircall?.max_calls !== 5) fail("Manifest Aircall max_calls must be 5");
    if (manifest.aircall?.selected_call_only !== true) fail("Manifest Aircall must be selected_call_only");
    if (manifest.aircall?.max_audio_bytes !== 26214400) fail("Manifest Aircall max_audio_bytes must be 26214400");
    if (manifest.aircall?.max_audio_seconds !== 3600) fail("Manifest Aircall max_audio_seconds must be 3600");
    if (manifest.aircall?.raw_recording_urls_returned !== false) fail("Manifest Aircall must not return raw recording URLs");
    if (manifest.aircall?.raw_audio_retained !== false) fail("Manifest Aircall must not retain raw audio");
    if (manifest.aircall?.bulk_transcript_exports !== false) fail("Manifest Aircall must block bulk transcript exports");
    for (const tool of ["find_aircall_calls", "transcribe_aircall_recording"]) {
      if (!manifest.aircall?.allowed_tools?.includes(tool)) fail(`Manifest Aircall missing allowed tool: ${tool}`);
    }
    if (manifest.exa?.auth_env_var !== "EXA_API_KEY") fail("Manifest missing EXA_API_KEY auth env var");
    if (manifest.exa?.max_search_companies !== 5) fail("Manifest Exa max_search_companies must be 5");
    if (manifest.exa?.max_candidates_per_company !== 5) fail("Manifest Exa max_candidates_per_company must be 5");
    if (manifest.exa?.selected_pii_in_slack !== false) fail("Manifest Exa selected_pii_in_slack must be false");
    if (manifest.exa?.bulk_contact_exports !== false) fail("Manifest Exa bulk_contact_exports must be false");
    if (manifest.exa?.allowed_endpoint !== "POST /search") fail("Manifest Exa allowed_endpoint must be POST /search");
    if (manifest.exa?.category !== "people") fail("Manifest Exa category must be people");
    if (manifest.public_research?.auth_env_var !== "TAVILY_API_KEY") fail("Manifest missing TAVILY_API_KEY auth env var");
    if (manifest.public_research?.provider !== "Tavily Search and Extract") fail("Manifest public_research provider must be Tavily Search and Extract");
    if (manifest.public_research?.tavily_research_api !== false) fail("Manifest public_research must disable Tavily Research API");
    if (manifest.public_research?.max_search_companies !== 5) fail("Manifest public_research max_search_companies must be 5");
    if (manifest.public_research?.requires_scoped_hubspot_companies !== true) {
      fail("Manifest public_research must require scoped HubSpot company inputs");
    }
    if (!manifest.public_research?.allowed_tools?.includes("research_public_company_signals")) {
      fail("Manifest public_research missing research_public_company_signals");
    }
    if (!manifest.public_research?.allowed_tools?.includes("find_brand_parent_candidates")) {
      fail("Manifest public_research missing find_brand_parent_candidates");
    }
    if (manifest.public_research?.brand_parent_identity_lookup_requires_hubspot_rescope !== true) {
      fail("Manifest public_research brand parent lookup must require HubSpot rescope");
    }
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
    if (!manifest.google_drive?.allowed_tools?.includes("read_google_slides_deck")) {
      fail("Manifest Google Drive missing read_google_slides_deck tool");
    }
    if (!manifest.google_drive?.allowed_tools?.includes("extract_drive_image_clues")) {
      fail("Manifest Google Drive missing extract_drive_image_clues tool");
    }
    if (!manifest.google_drive?.allowed_tools?.includes("read_nurture_material_registry")) {
      fail("Manifest Google Drive missing read_nurture_material_registry tool");
    }
    if (!manifest.google_drive?.allowed_tools?.includes("read_indonesia_event_registration_attendance")) {
      fail("Manifest Google Drive missing read_indonesia_event_registration_attendance tool");
    }
    if (manifest.google_drive?.material_registry_spreadsheet_id_env_var !== "NURTUREANY_MATERIAL_REGISTRY_SPREADSHEET_ID") {
      fail("Manifest Google Drive missing NURTUREANY_MATERIAL_REGISTRY_SPREADSHEET_ID env var");
    }
    for (const tab of ["Materials", "Playbooks", "Peer Intros", "Speaker/Venue Opportunities", "Events", "Review Log"]) {
      if (!manifest.google_drive?.material_registry_tabs?.includes(tab)) fail(`Manifest Google Drive missing material registry tab: ${tab}`);
    }
    if (manifest.google_drive?.id_rev_events_spreadsheet_id !== "1mXixAVJGk0Uy0u1LtOmDFxU3XuW8DRfedB69E1f-drc") {
      fail("Manifest Google Drive ID Rev events spreadsheet id is incorrect");
    }
    if (!String(manifest.google_drive?.registration_attendance_fallback || "").includes("Attend The Event")) {
      fail("Manifest Google Drive registration_attendance_fallback must reference Attend The Event");
    }
    if (manifest.google_drive?.registration_attendance_column !== "Attend The Event") {
      fail("Manifest Google Drive registration_attendance_column must be Attend The Event");
    }
    if (manifest.google_drive?.transient_vision_downloads !== true) {
      fail("Manifest Google Drive transient_vision_downloads must be true");
    }
    if (manifest.google_drive?.uploader_profile_lookup !== "best_effort_slack_users_info") {
      fail("Manifest Google Drive uploader_profile_lookup must be best_effort_slack_users_info");
    }
    if (manifest.google_drive?.file_downloads !== false) fail("Manifest Google Drive file_downloads must be false");
    if (manifest.google_drive?.drive_mutations !== false) fail("Manifest Google Drive drive_mutations must be false");
    if (manifest.daily_nurture?.assumed_hubspot_owner_email !== "jeremy.wong@staffany.com") {
      fail("Manifest daily_nurture must assume Jeremy hubspot owner email");
    }
    if (manifest.daily_nurture?.protected_pool_baseline !== 150) fail("Manifest daily_nurture protected pool must be 150");
    if (manifest.daily_nurture?.daily_account_count !== 30) fail("Manifest daily_nurture daily account count must be 30");
    if (manifest.daily_nurture?.timezone !== "Asia/Singapore") fail("Manifest daily_nurture timezone must be Asia/Singapore");
    if (manifest.daily_nurture?.nine_am_cron_utc !== "0 1 * * 1-5") fail("Manifest daily_nurture 9am cron must be 01:00 UTC weekdays");
    if (manifest.daily_nurture?.noon_reminder_cron_utc !== "0 4 * * 1-5") fail("Manifest daily_nurture 12pm cron must be 04:00 UTC weekdays");
    if (manifest.daily_nurture?.nine_am_cron_local !== "0 9 * * 1-5") fail("Manifest daily_nurture 9am local cron must be 09:00 Asia/Singapore weekdays");
    if (manifest.daily_nurture?.noon_reminder_cron_local !== "0 12 * * 1-5") fail("Manifest daily_nurture 12pm local cron must be 12:00 Asia/Singapore weekdays");
    if (manifest.eazybe?.auth_env_var !== "EAZYBE_API_KEY") fail("Manifest Eazybe missing EAZYBE_API_KEY auth env var");
    if (manifest.eazybe?.base_mode !== "approval_gated_template_send") fail("Manifest Eazybe base_mode must be approval_gated_template_send");
    if (manifest.eazybe?.approved_templates_only !== true) fail("Manifest Eazybe must require approved templates");
    if (manifest.eazybe?.phone_numbers_redacted_in_slack !== true) fail("Manifest Eazybe must redact phone numbers in Slack");
    if (manifest.eazybe?.free_form_drafts_sendable !== false) fail("Manifest Eazybe must block free-form sends");
    if (manifest.eazybe?.approval_marker_required !== true) fail("Manifest Eazybe must require approval_marker");
    for (const tool of [
      "preview_eazybe_template_messages",
      "send_approved_eazybe_messages",
      "check_eazybe_send_status",
      "build_daily_nurture_reminder"
    ]) {
      if (!manifest.eazybe?.allowed_tools?.includes(tool)) fail(`Manifest Eazybe missing allowed tool: ${tool}`);
    }
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
    if (!manifest.luma?.allowed_tools?.includes("get_luma_event_match_keys")) fail("Manifest Luma missing get_luma_event_match_keys tool");
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

const caseStudyCatalog = readJson(join(appRoot, "runtime", "data", "case-studies.json"));
if (caseStudyCatalog) {
  const cases = Array.isArray(caseStudyCatalog.cases) ? caseStudyCatalog.cases : [];
  const bmcCases = cases.filter((item) => item?.source_type === "bmc_podcast");
  if (bmcCases.length !== 21) fail(`BMC podcast catalog must contain 21 approved cards; found ${bmcCases.length}`);
  for (const item of bmcCases) {
    const label = item?.id || item?.customer || "unknown BMC case";
    const review = item?.full_video_review || {};
    const refs = Array.isArray(item?.evidence_refs) ? item.evidence_refs : [];
    const moments = Array.isArray(item?.best_use_sales_moments) ? item.best_use_sales_moments : [];
    if (item?.approved_for_name_drops !== true) fail(`${label} must be approved_for_name_drops=true`);
    if (item?.approval_basis !== "bmc_podcast_full_video_review") fail(`${label} must use bmc_podcast_full_video_review approval basis`);
    if (review.primary_spoken_source !== "youtube_auto_caption") fail(`${label} must use YouTube captions as the primary spoken source`);
    if (review.reviewer_status !== "full_transcript_reviewed") fail(`${label} must be full_transcript_reviewed`);
    if (review.full_transcript_available !== true) fail(`${label} must have full transcript coverage`);
    if (!Number.isFinite(Number(review.transcript_word_count)) || Number(review.transcript_word_count) <= 0) {
      fail(`${label} must record positive transcript_word_count`);
    }
    if (!review.first_timestamp || !review.last_timestamp) fail(`${label} must record first and last transcript timestamps`);
    if (Array.isArray(review.gaps) && review.gaps.length > 0) fail(`${label} must not have transcript gaps for AE-approved use`);
    for (const moment of ["knowledge_touch", "pre_demo", "demo", "post_demo_followup"]) {
      if (!moments.includes(moment)) fail(`${label} missing sales moment: ${moment}`);
    }
    if (!Array.isArray(item?.do_not_claim) || item.do_not_claim.length === 0) fail(`${label} must include do_not_claim caveats`);
    if (refs.length === 0) fail(`${label} must include timestamped evidence refs`);
    for (const ref of refs) {
      if (!/^([0-9]{2}:){2}[0-9]{2}/.test(String(ref?.timestamp || ""))) fail(`${label} evidence ref missing timestamp`);
      if (!String(ref?.source_path || "").startsWith("research/raw/online/")) fail(`${label} evidence ref must point to Midas raw transcript path`);
      if (!Number.isFinite(Number(ref?.line)) || Number(ref?.line) <= 0) fail(`${label} evidence ref must include source line`);
      if (!String(ref?.claim || "").trim()) fail(`${label} evidence ref must include claim`);
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
  "skills/target-account-news-scout/SKILL.md",
  "skills/target-account-news-scout/references/search-playbook.md",
  "skills/target-account-news-scout/references/output-contract.md",
  "skills/target-account-news-scout/agents/openai.yaml",
  "skills/nurtureany-sales-bot/references/hubspot-fields.md",
  "skills/nurtureany-sales-bot/references/sales-best-practices.md",
  "skills/nurtureany-sales-bot/references/sop-tool-coverage.md",
  "skills/nurtureany-sales-bot/references/playbooks.md",
  "skills/nurtureany-sales-bot/references/pre-demo-game-plans.md",
  "skills/nurtureany-sales-bot/references/regression-cases.md",
  "runtime/slack.md",
  "runtime/mcp/slack_nurtureany_server.py",
  "runtime/mcp/test_slack_nurtureany_server.py",
  "runtime/hubspot.md",
  "runtime/mcp/hubspot_nurtureany_server.py",
  "runtime/aircall.md",
  "runtime/mcp/aircall_nurtureany_server.py",
  "runtime/mcp/test_aircall_nurtureany_server.py",
  "runtime/mcp/nurtureany_common/responses.py",
  "runtime/mcp/nurtureany_common/text.py",
  "runtime/mcp/nurtureany_common/scoped_company.py",
  "runtime/mcp/nurtureany_common/c360.py",
  "runtime/mcp/nurtureany_common/luma_filters.py",
  "runtime/mcp/nurtureany_common/google_oauth.py",
  "runtime/mcp/test_helpers.py",
  "runtime/mcp/test_hubspot_nurtureany_server.py",
  "runtime/bigquery.md",
  "runtime/google-calendar.md",
  "runtime/mcp/google_calendar_nurtureany_server.py",
  "runtime/mcp/test_google_calendar_nurtureany_server.py",
  "runtime/google-drive.md",
  "runtime/mcp/google_drive_nurtureany_server.py",
  "runtime/mcp/test_google_drive_nurtureany_server.py",
  "runtime/eazybe.md",
  "runtime/mcp/eazybe_nurtureany_server.py",
  "runtime/mcp/test_eazybe_nurtureany_server.py",
  "runtime/luma.md",
  "runtime/mcp/luma_nurtureany_server.py",
  "runtime/mcp/test_luma_nurtureany_server.py",
  "runtime/near-me.md",
  "runtime/sql/near-me-outlet-matches.sql",
  "runtime/mcp/near_me_nurtureany_server.py",
  "runtime/mcp/test_near_me_nurtureany_server.py",
  "runtime/public-research.md",
  "runtime/mcp/nurtureany_common/public_research.py",
  "runtime/mcp/public_research_nurtureany_server.py",
  "runtime/mcp/test_public_research_nurtureany_server.py",
  "runtime/exa.md",
  "runtime/mcp/exa_nurtureany_server.py",
  "runtime/mcp/test_exa_nurtureany_server.py",
  "runtime/lusha.md",
  "runtime/mcp/lusha_nurtureany_server.py",
  "runtime/mcp/test_lusha_nurtureany_server.py",
  "runtime/health-checks.md",
  "runtime/check-health.sh",
  "runtime/check-cloud-heartbeat.sh",
  "runtime/check-slack-socket-health.sh",
  "runtime/audit-live-profile.sh",
  "runtime/nurtureany-cloud-doctor.sh",
  "runtime/jobs/near_me_outlet_match_writer.py",
  "runtime/jobs/test_near_me_outlet_match_writer.py",
  "tests/regression-cases.md"
];

for (const relPath of filesToScan) {
  assertFile(relPath);
  scanForSecretPatterns(relPath);
}

const packageJson = readJson(join(repoRoot, "package.json"));
if (packageJson?.scripts?.["nurtureany-sales-bot:deploy"] !== "node scripts/deploy-nurtureany-sales-bot.mjs") {
  fail("package.json must expose nurtureany-sales-bot:deploy");
}

const deployScriptRelPath = "scripts/deploy-nurtureany-sales-bot.mjs";
const deployScriptPath = join(repoRoot, deployScriptRelPath);
if (!existsSync(deployScriptPath)) {
  fail("Missing scripts/deploy-nurtureany-sales-bot.mjs");
}
const deployScriptText = repoTextOf(deployScriptRelPath);
for (const text of [
  "project: \"staffany-warehouse\"",
  "zone: \"asia-southeast1-a\"",
  "vm: \"nurtureany-sales-bot-prod\"",
  "profile: \"nurtureanysalesbot\"",
  "runtimeOwner: \"leekaiyi\"",
  "--apply",
  "Dry run only. No archive upload, remote sync, gateway restart, or production health checks were run.",
  "/private/tmp",
  "nurtureany-origin-main.tar.gz",
  "nurtureany-origin-main.sha",
  "origin/main",
  "gcloud",
  "compute",
  "scp",
  "ssh",
  "copy_dir",
  "source/nurtureany-sales-bot",
  "skills/nurtureany-sales-bot",
  "skills/target-account-news-scout",
  "runtime/mcp",
  "runtime/data",
  "runtime/jobs",
  "runtime/sql",
  "check-cloud-heartbeat.sh",
  "nurtureanysalesbot-check-cloud-heartbeat.sh",
  "check-health.sh",
  "audit-live-profile.sh",
  "check-slack-socket-health.sh",
  "nurtureany-cloud-doctor.sh",
  "profile/config.template.yaml",
  "config.yaml",
  "tool_allowlist",
  "apply-live-config-overrides.py",
  ".env",
  "OAuth files",
  "NURTUREANY_ACCESS_POLICY_PATH",
  "cron",
  "logs",
  "sessions",
  "daily-runs",
  "operation-ledger",
  "hermes-gateway-$profile_name.service",
  "run_post_deploy_check",
  "NURTUREANY_DEPLOY_CHECK_ATTEMPTS",
  "NURTUREANY_DEPLOY_CHECK_RETRY_SECONDS",
  "NURTUREANY_DEPLOY_CHECK_COMMAND_TIMEOUT_SECONDS",
  "NURTUREANY_DEPLOY_HEALTH_WARMUP_SECONDS",
  "deploy:check:health=warmup:$health_warmup_seconds",
  "else\n      status=\"$?\"\n    fi",
  "deploy:check:$label=retry:$attempt/$attempts",
  "deploy:check:$label=failed-after-$attempts-attempts",
  "deploy:summary:sha=",
  "deploy:summary:cloud_doctor=passed"
]) {
  if (!deployScriptText.includes(text)) fail(`${deployScriptRelPath} missing required text: ${text}`);
}
for (const [pattern, label] of [
  [/xox[baprs]-[A-Za-z0-9-]+/, "Slack token"],
  [/xapp-[A-Za-z0-9-]+/, "Slack app token"],
  [/sk-[A-Za-z0-9_-]{20,}/, "OpenAI-style API key"],
  [/pat-[a-z0-9]+-[A-Za-z0-9-]{20,}/, "HubSpot private app token"],
  [/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/, "private key"],
  [/AIza[0-9A-Za-z_-]{20,}/, "Google API key"]
]) {
  if (pattern.test(deployScriptText)) fail(`${label} pattern found in ${deployScriptRelPath}`);
}
const deploySyntaxCheck = spawnSync("node", ["--check", deployScriptPath], { encoding: "utf8" });
if (deploySyntaxCheck.status !== 0) {
  fail(`Node syntax check failed for ${deployScriptRelPath}: ${(deploySyntaxCheck.stderr || deploySyntaxCheck.stdout).trim()}`);
}

const configText = textOf("profile/config.template.yaml");
if (!configText.includes('provider: "anthropic"')) fail("config.template.yaml must set model.provider to anthropic");
if (!configText.includes('default: "claude-sonnet-4-6"')) fail("config.template.yaml must set model.default to claude-sonnet-4-6");
if (!configText.includes("interim_assistant_messages: false")) fail("config.template.yaml must disable interim assistant messages");
if (!configText.includes("reactions: true")) fail("config.template.yaml must enable Slack reactions");
if (!configText.includes("max_parallel_jobs: 1")) fail("config.template.yaml must cap cron.max_parallel_jobs at 1");
if (!configText.includes("dispatch_in_gateway: false")) fail("config.template.yaml must disable kanban dispatch in gateway");
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
  "sarah.ayutania@staffany.com",
  "NURTUREANY_ACCESS_POLICY_PATH",
  "runtime/access-policy.template.json",
  "unclassified_hubspot_owners",
  "quick_autorun",
  "max_expected_seconds: 60",
  "max_context_messages: 10",
  "max_context_lookback_minutes: 30",
  "max_thread_context_messages: 50",
  "read_recent_slack_intent_context",
  "get_current_slack_thread_context",
  "get_selected_slack_thread_context",
  "slack_nurtureany",
  "runtime/mcp/slack_nurtureany_server.py",
  "NURTUREANY_SLACK_INTENT_CHANNEL_IDS",
  "safe summaries/permalinks only",
  "no_user_token_fallback: true",
  "no_slack_connector_fallback: true",
  "list_my_target_accounts",
  "list_team_target_accounts",
      "audit_hubspot_owner_roster",
      "audit_priority_account_coverage",
      "build_sales_metric_actuals_query",
      "build_hubspot_revenue_funnel_metrics",
      "build_ae_coaching_audit",
      "audit_owner_whatsapp_kns_window",
      "prepare_sales_navigator_decision_maker_queue",
  "build_friday_sales_review",
  "build_manager_chase_plan",
  "list_active_deals_missing_next_meeting",
  "NURTUREANY_REVENUE_NEW_BUSINESS_PIPELINE_IDS",
  "NURTUREANY_REVENUE_RENEWAL_PIPELINE_IDS",
  "NURTUREANY_QO_PIPELINE_IDS",
  "NURTUREANY_QO_STAGE_IDS",
  "NURTUREANY_QO_MET_STAGE_IDS",
  "NURTUREANY_CLOSED_WON_STAGE_IDS",
  "connected_call_target: 40",
  "build_pre_demo_game_plans",
  "list_sales_followup_tasks",
  "check_account_followup_status",
  "check_event_followup_status",
  "build_daily_nurture_plan",
  "daily_nurture",
  "jeremy.wong@staffany.com",
  "0 1 * * 1-5",
  "0 4 * * 1-5",
  "NURTUREANY_MATERIAL_REGISTRY_SPREADSHEET_ID",
  "get_campaign_social_effectiveness",
  "get_marketing_campaign_attribution",
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
  "read_google_slides_deck",
  "extract_drive_image_clues",
  "read_nurture_material_registry",
  "read_indonesia_event_registration_attendance",
  "read_nurture_material_registry",
  "1mXixAVJGk0Uy0u1LtOmDFxU3XuW8DRfedB69E1f-drc",
  "eazybe_nurtureany",
  "EAZYBE_API_KEY",
  "EAZYBE_BROADCAST_API_URL",
  "preview_eazybe_template_messages",
  "send_approved_eazybe_messages",
  "check_eazybe_send_status",
  "build_daily_nurture_reminder",
  "approval_gated_v2_only",
  "registration_attendance_fallback",
  "Attend The Event",
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
  "get_luma_event_match_keys",
  "find_target_accounts_by_luma_match_keys",
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
  "public_research_nurtureany",
  "TAVILY_API_KEY",
  "runtime/mcp/public_research_nurtureany_server.py",
  "research_public_company_signals",
  "find_brand_parent_candidates",
  "tavily_research_api: false",
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
  "local, read-only source-packet hydration",
  "Local references are allowed before `run`; app-backed or external sources are not",
  "KNS, K/N/S, or K N S",
  "Knowledge, Network, Support",
  "quick-autorun gate",
  "read_recent_slack_intent_context",
  "safe summaries/permalinks only",
  "no raw transcript persistence",
  "Smoke/test/eval prompts follow the same quick-autorun gate",
  "bot mention only",
  "please proceed",
  "explicit approval",
  "Never auto-send",
  "Confidence",
  "sales-owned follow-up tasks",
  "build_sales_metric_actuals_query",
  "build_friday_sales_review",
  "build_manager_chase_plan",
  "audit_priority_account_coverage",
  "sales-best-practices.md",
  "sop-tool-coverage.md",
  "120/150 account coverage",
  "40 connected calls",
  "QO/QO Met",
  "lead source",
  "AI/data-readiness",
  "event attribution",
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
  "found/selected Luma event",
  "event.url|event.name",
  "event-first matching",
  "raw guest lists",
  "read_indonesia_event_registration_attendance",
  "ID REV - LL & HHH EVENTS",
  "Attend The Event",
  "raw registration rows",
  "cost_report",
  "credit_report",
  "approval_marker",
  "reveal_phones",
  "exact company names",
  "ambiguous",
  "people layer",
  "photo match",
  "list_drive_folder_images",
  "read_google_slides_deck",
  "extract_drive_image_clues",
  "read_nurture_material_registry",
  "read_indonesia_event_registration_attendance",
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
  "case-study match needed",
  "get_campaign_social_effectiveness",
  "get_marketing_campaign_attribution",
  "SOCIAL_BROADCAST",
  "raw social channel IDs"
]) {
  if (!soulText.includes(text)) fail(`SOUL.md missing required safety/contract text: ${text}`);
}

const skillText = textOf("skills/nurtureany-sales-bot/SKILL.md");
for (const text of [
  "NURTUREANY_ACCESS_POLICY_PATH",
  "quick-autorun gate",
  "read_recent_slack_intent_context",
  "safe summaries/permalinks only",
  "no raw transcript persistence",
  "Smoke/test/eval prompts follow the same quick-autorun gate",
  "bot mention only",
  "please proceed",
  "local source-packet hydration",
  "KNS`, `K/N/S`, or `K N S`",
  "Knowledge, Network, Support",
  "unclassified HubSpot owners are blocked",
  "hs_is_target_account",
  "company_country",
  "hubspot_owner_id",
  "references/sales-best-practices.md",
  "references/sop-tool-coverage.md",
  "references/pre-demo-game-plans.md",
  "Nurture-ready enriched",
  "verified decision maker",
  "missing-decision-maker counts",
  "Do not use Honcho",
  "Confidence: <verified | needs-check | blocked>",
  "audit_hubspot_owner_roster",
  "audit_priority_account_coverage",
  "build_sales_metric_actuals_query",
  "build_friday_sales_review",
  "build_manager_chase_plan",
  "120_150_accounts_worked",
  "40_connected_calls",
  "NURTUREANY_QO_PIPELINE_IDS",
  "build_pre_demo_game_plans",
  "find_sales_case_studies",
  "exact company names",
  "ambiguous matches",
  "pricing needed",
  "case-study match needed",
  "get_campaign_social_effectiveness",
  "get_marketing_campaign_attribution",
  "SOCIAL_BROADCAST",
  "list_active_deals_missing_next_meeting",
  "list_sales_followup_tasks",
  "audit_owner_whatsapp_kns_window",
  "count_owner_whatsapp_sent_today",
  "sales-owned HubSpot follow-up tasks",
  "check_account_followup_status",
  "check_event_followup_status",
  "WhatsApp communications",
  "generate_free_search_tasks",
  "review_public_enrichment_evidence",
  "scan_drive_event_photos",
  "propose_photo_people_matches",
  "list_drive_folder_images",
  "read_google_slides_deck",
  "extract_drive_image_clues",
  "read_nurture_material_registry",
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
  "get_luma_event_match_keys",
  "find_target_accounts_by_luma_match_keys",
  "get_luma_event_context",
  "checked_in_at",
  "found/selected Luma event",
  "event.url|event.name",
  "event-first match keys",
  "raw guest lists",
  "ID REV - LL & HHH EVENTS",
  "Attend The Event",
  "raw registration rows",
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
  "lead source",
  "AI/data readiness",
  "event attribution",
  "disabled in V1",
  "approval_marker",
  "selected Lusha reveal",
  "raw phone number",
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
  "build_sales_metric_actuals_query",
  "build_friday_sales_review",
  "build_pre_demo_game_plans",
  "manual-review only",
  "Terminology aliases",
  "KNS`, `K/N/S`, and `K N S` all mean Knowledge, Network, Support",
  "Do not expand KNS as Know-Nurture-Sell",
  "Do not build a new MCP"
]) {
  if (!salesBestPracticesText.includes(text)) {
    fail(`sales-best-practices.md missing required text: ${text}`);
  }
}

const sopToolCoverageText = textOf("skills/nurtureany-sales-bot/references/sop-tool-coverage.md");
for (const text of [
  "Source hierarchy",
  "HubSpot override fields",
  "Intent-gated Slack flow",
  "quick-autorun",
  "read_recent_slack_intent_context",
  "Access scope",
  "PII/body safety",
  "Cost/credit reporting",
  "Mutation policy",
  "Sales-best-practices usage",
  "Inbound/routing",
  "Event attribution",
  "AI/data readiness",
  "disabled in V1"
]) {
  if (!sopToolCoverageText.includes(text)) fail(`sop-tool-coverage.md missing required text: ${text}`);
}
for (const tool of [
  "runtime/mcp/slack_nurtureany_server.py",
  "runtime/mcp/hubspot_nurtureany_server.py",
  "runtime/mcp/google_calendar_nurtureany_server.py",
  "runtime/mcp/google_drive_nurtureany_server.py",
  "runtime/mcp/eazybe_nurtureany_server.py",
  "runtime/mcp/luma_nurtureany_server.py",
  "runtime/mcp/near_me_nurtureany_server.py",
  "runtime/mcp/public_research_nurtureany_server.py",
  "runtime/mcp/exa_nurtureany_server.py",
  "runtime/mcp/lusha_nurtureany_server.py"
].flatMap((relPath) => decoratedMcpTools(relPath))) {
  if (!sopToolCoverageText.includes(`\`${tool}\``)) {
    fail(`sop-tool-coverage.md missing actual MCP tool: ${tool}`);
  }
}

const combinedRegressionText = `${textOf("skills/nurtureany-sales-bot/references/regression-cases.md")}\n${textOf("tests/regression-cases.md")}`;
for (const text of [
  "Inbound Routing Quality",
  "Smoke/test prompts follow the same quick-intent gate",
  "Quick Intent Auto-Run",
  "Ambiguous Recent Context Still Preflight",
  "Broad Friday Review Still Preflight",
  "Mutation Send Reveal Still Approval-Gated",
  "read_recent_slack_intent_context",
  "lead source",
  "checked/not-checked",
  "QO / closed-won attribution was not checked in this run",
  "AI/Data Readiness Guardrail",
  "Local Reference Hydration Before Run",
  "KNS / K/N/S / K N S means Knowledge, Network, Support",
  "must not expand KNS as Know-Nurture-Sell",
  "Campaign Social Effectiveness Style",
  "Event Attribution Guardrail",
  "Mutation Disabled In V1",
  "create_hubspot_task",
  "append_hubspot_note",
  "update_nurture_fields"
]) {
  if (!combinedRegressionText.includes(text)) fail(`regression cases missing SOP scenario text: ${text}`);
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
const slackIntentServerText = textOf("runtime/mcp/slack_nurtureany_server.py");
for (const text of [
  "SLACK_BOT_TOKEN",
  "NURTUREANY_SLACK_INTENT_CHANNEL_IDS",
  "NURTUREANY_SLACK_THREAD_CONTEXT_CHANNEL_IDS",
  "NURTUREANY_SLACK_THREAD_CONTEXT_PUBLIC_CHANNELS",
  "MAX_CONTEXT_MESSAGES = 10",
  "MAX_LOOKBACK_MINUTES = 30",
  "MAX_THREAD_CONTEXT_MESSAGES = 50",
  "conversations.info",
  "conversations.history",
  "conversations.replies",
  "conversations.join",
  "chat.getPermalink",
  "read_recent_slack_intent_context",
  "get_current_slack_thread_context",
  "get_selected_slack_thread_context",
  "safe_summaries",
  "will_post_message",
  "transcript_persisted",
  "mcp.run(\"stdio\")"
]) {
  if (!slackIntentServerText.includes(text)) fail(`runtime/mcp/slack_nurtureany_server.py missing required text: ${text}`);
}

const slackIntentTestText = textOf("runtime/mcp/test_slack_nurtureany_server.py");
for (const text of [
  "read_recent_slack_intent_context",
  "test_missing_token_blocks_without_network",
  "test_unconfigured_channel_blocks_without_network",
  "test_history_reads_are_capped_and_redacted",
  "test_thread_replies_path",
  "test_current_thread_reads_are_capped_and_redacted",
  "test_selected_permalink_thread_reads_parse_thread_ts",
  "test_selected_permalink_uses_separate_thread_context_channel_allowlist",
  "test_selected_permalink_auto_joins_configured_public_channel_before_retry",
  "test_selected_permalink_can_auto_join_unconfigured_public_channel_when_enabled",
  "test_selected_permalink_blocks_private_channel_even_when_all_public_enabled",
  "test_selected_permalink_blocks_malformed_without_network",
  "test_selected_permalink_blocks_unconfigured_channel_without_network"
]) {
  if (!slackIntentTestText.includes(text)) fail(`runtime/mcp/test_slack_nurtureany_server.py missing required text: ${text}`);
}

for (const text of [
  "ACCESS_POLICY_ENV_VAR = \"NURTUREANY_ACCESS_POLICY_PATH\"",
  "audit_hubspot_owner_roster",
  "unclassified",
  "Managers have read-only team scope",
  "Company is outside caller scope or is not a HubSpot target account",
  "build_pre_demo_game_plans",
  "audit_priority_account_coverage",
  "build_sales_metric_actuals_query",
  "build_friday_sales_review",
  "build_manager_chase_plan",
  "CALL_PROPERTIES",
  "MEETING_PROPERTIES",
  "CONNECTED_CALL_MIN_DURATION_MS",
  "NURTUREANY_QO_PIPELINE_IDS",
  "PRE_DEMO_GAME_PLAN_ACCOUNT_LIMIT = 5",
  "include_public_research: bool = False",
  "_public_research_for_game_plan_contexts",
  "_resolve_scoped_company_name",
  "ambiguous_matches",
  "pricing needed",
  "case-study match needed",
  "get_campaign_social_effectiveness",
  "get_marketing_campaign_attribution",
  "Raw social channel IDs",
  "list_active_deals_missing_next_meeting",
  "list_sales_followup_tasks",
  "audit_owner_whatsapp_kns_window",
  "count_owner_whatsapp_sent_today",
  "check_account_followup_status",
  "check_event_followup_status",
  "build_daily_nurture_plan",
  "DAILY_NURTURE_DEFAULT_ACCOUNT_COUNT = 30",
  "DAILY_NURTURE_PROTECTED_POOL_SIZE = 150",
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
  "auto_event_tag_status",
  "list_inbound_threads",
  "get_inbound_thread_context",
  "list_marketing_campaigns",
  "get_campaign_assets",
  "get_campaign_social_effectiveness",
  "get_marketing_touch_context",
  "get_marketing_campaign_attribution",
  "SOCIAL_BROADCAST",
  "MARKETING_ATTRIBUTION_SEARCH_PROPERTIES",
  "CASE_STUDY_CATALOG_PATH",
  "find_sales_case_studies",
  "bmc_podcast_full_video_review",
  "case_study_matches",
  "HubSpot Conversations",
  "PODCAST_EPISODE",
  "find_target_accounts_by_luma_match_keys",
  "LUMA_MATCH_DOMAIN_LIMIT",
  "No raw Luma attendees"
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

const publicResearchText = textOf("runtime/public-research.md");
for (const text of [
  "TAVILY_API_KEY",
  "research_public_company_signals",
  "find_brand_parent_candidates",
  "POST /search",
  "POST /extract",
  "POST /research",
  "about 3 Tavily credits",
  "about 5 Tavily credits",
  "about 6-8 Tavily credits",
  "cost_report",
  "will_mutate_hubspot=false",
  "scope_source=hubspot_nurtureany",
  "identity-resolution fallback",
  "manual-check only",
  "recommended_next_tool=search_exa_people_candidates"
]) {
  if (!publicResearchText.includes(text)) fail(`runtime/public-research.md missing required text: ${text}`);
}

const publicResearchServerText = textOf("runtime/mcp/public_research_nurtureany_server.py");
for (const text of [
  "TAVILY_API_KEY",
  "MAX_RESEARCH_COMPANIES",
  "research_public_company_signals",
  "find_brand_parent_candidates",
  "Tavily public company research",
  "scoped HubSpot",
  "cost_report",
  "will_mutate_hubspot=False",
  "mcp.run(\"stdio\")"
]) {
  if (!publicResearchServerText.includes(text)) fail(`runtime/mcp/public_research_nurtureany_server.py missing required text: ${text}`);
}

const publicResearchCommonText = textOf("runtime/mcp/nurtureany_common/public_research.py");
for (const text of [
  "TAVILY_BASE_URL = \"https://api.tavily.com\"",
  "MAX_RESEARCH_COMPANIES = 5",
  "MAX_BRAND_PARENT_CANDIDATES = 5",
  "MODE_CONFIGS",
  "research_public_company_signals",
  "find_brand_parent_candidates",
  "company_signals",
  "source_evidence",
  "game_plan_inputs",
  "manual_check_items",
  "missing_evidence",
  "cost_report",
  "linkedin_manual",
  "instagram_tiktok_manual",
  "facebook_manual",
  "google_maps_manual",
  "search_exa_people_candidates"
]) {
  if (!publicResearchCommonText.includes(text)) fail(`runtime/mcp/nurtureany_common/public_research.py missing required text: ${text}`);
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
  "read_google_slides_deck",
  "extract_drive_image_clues",
  "read_nurture_material_registry",
  "slack_uploader_name",
  "users.info",
  "all-random",
  "Google Slides",
  "Anyone with the link",
  "ID REV - LL & HHH EVENTS",
  "read_indonesia_event_registration_attendance",
  "Attend The Event",
  "phone numbers, full emails",
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
  "GOOGLE_SHEETS_API_BASE_URL",
  "ID_REV_EVENTS_SPREADSHEET_ID",
  "MATERIAL_REGISTRY_SPREADSHEET_ID_ENV",
  "MAX_REGISTRATION_ROWS = 250",
  "list_drive_folder_images",
  "read_google_slides_deck",
  "extract_drive_image_clues",
  "read_nurture_material_registry",
  "read_indonesia_event_registration_attendance",
  "read_nurture_material_registry",
  "Attend The Event",
  "NURTUREANY_MATERIAL_REGISTRY_SPREADSHEET_ID",
  "MATERIAL_REGISTRY_TABS",
  "No phone numbers, full emails, raw exports, or Drive mutations.",
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

const eazybeText = textOf("runtime/eazybe.md");
for (const text of [
  "EAZYBE_API_KEY",
  "EAZYBE_BROADCAST_API_URL",
  "preview_eazybe_template_messages",
  "send_approved_eazybe_messages",
  "check_eazybe_send_status",
  "build_daily_nurture_reminder",
  "approval_marker",
  "templateName",
  "ordered templateParams",
  "phone numbers are redacted",
  "No free-form WhatsApp sends"
]) {
  if (!eazybeText.includes(text)) fail(`runtime/eazybe.md missing required text: ${text}`);
}

const eazybeServerText = textOf("runtime/mcp/eazybe_nurtureany_server.py");
for (const text of [
  "EAZYBE_API_KEY",
  "EAZYBE_BROADCAST_API_URL",
  "EAZYBE_TIMEOUT_SECONDS = 15",
  "approval_gated_template_send",
  "PHONE_PATTERN",
  "templateName",
  "templateParams",
  "preview_eazybe_template_messages",
  "send_approved_eazybe_messages",
  "check_eazybe_send_status",
  "build_daily_nurture_reminder",
  "mcp.run(\"stdio\")"
]) {
  if (!eazybeServerText.includes(text)) fail(`runtime/mcp/eazybe_nurtureany_server.py missing required text: ${text}`);
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
  "get_luma_event_match_keys",
  "find_target_accounts_by_luma_match_keys",
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
  "Do not paste raw match-key lists",
  "read_indonesia_event_registration_attendance",
  "Attend The Event",
  "Do not create, update, invite, RSVP, check in",
  "Confidence: blocked"
]) {
  if (!lumaText.includes(text)) fail(`runtime/luma.md missing required text: ${text}`);
}

const slackText = textOf("runtime/slack.md");
for (const text of [
  "quick-autorun gate",
  "read_recent_slack_intent_context",
  "get_current_slack_thread_context",
  "get_selected_slack_thread_context",
  "SLACK_BOT_TOKEN",
  "NURTUREANY_SLACK_THREAD_CONTEXT_PUBLIC_CHANNELS",
  "public channels",
  "conversations.join",
  "safe summaries/permalinks only",
  "conversations.history",
  "conversations.replies",
  "chat.getPermalink",
  "bot mention only",
  "please proceed",
  "event_tags=[\"Singapore\", \"Sports\"]",
  "event-first matching",
  "event.url|event.name",
  "read_google_slides_deck",
  "Anyone with the link",
  "read_indonesia_event_registration_attendance",
  "Attend The Event",
  "date and event ID",
  "Do not run a post-answer acceptance workflow",
  "bare same-thread acknowledgements like `ok`, `done`, `yes`, and `thanks`"
]) {
  if (!slackText.includes(text)) fail(`runtime/slack.md missing required text: ${text}`);
}

const nurtureSkillText = textOf("skills/nurtureany-sales-bot/SKILL.md");
for (const text of [
  "Do not run a post-answer acceptance workflow",
  "do not mark the thread as action needed",
  "send reminders waiting for explicit acceptance"
]) {
  if (!nurtureSkillText.includes(text)) fail(`skills/nurtureany-sales-bot/SKILL.md missing required text: ${text}`);
}

const healthText = textOf("runtime/health-checks.md");
for (const text of [
  "Quick-autorun policy",
  "Slack intent-context smoke check",
  "Slack selected-thread smoke check",
  "read_recent_slack_intent_context",
  "get_current_slack_thread_context",
  "get_selected_slack_thread_context",
  "SLACK_BOT_TOKEN",
  "NURTUREANY_SLACK_THREAD_CONTEXT_PUBLIC_CHANNELS",
  "public channels",
  "conversations.join",
  "safe summaries/permalinks only",
  "conversations.history",
  "conversations.replies",
  "chat.getPermalink",
  "Luma event-link smoke check",
  "Event-first Luma smoke check",
  "campaign social-effectiveness smoke check",
  "marketing attribution smoke check",
  "Indonesia event-registration fallback smoke check",
  "Google Slides deck-access smoke check",
  "read_google_slides_deck",
  "Anyone with the link",
  "read_indonesia_event_registration_attendance",
  "Daily nurture smoke check",
  "read_nurture_material_registry",
  "Eazybe approval-gated smoke check",
  "send_approved_eazybe_messages",
  "Attend The Event",
  "event.url|event.name"
]) {
  if (!healthText.includes(text)) fail(`runtime/health-checks.md missing required text: ${text}`);
}

const lumaRegressionText = `${textOf("tests/regression-cases.md")}\n${textOf("skills/nurtureany-sales-bot/references/regression-cases.md")}`;
for (const text of [
  "clickable Luma event link",
  "event-first matching",
  "event.url|event.name",
  "ID REV - LL & HHH EVENTS",
  "HHH Bali 7 May - Rsvp",
  "raw registration rows",
  "date and event ID"
]) {
  if (!lumaRegressionText.includes(text)) fail(`Luma regression cases missing required text: ${text}`);
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
  "get_luma_event_match_keys",
  "MATCH_KEY_LIMIT",
  "PERSONAL_EMAIL_DOMAINS",
  "event_tag_filters",
  "event_type",
  "location_filter",
  "country_filter",
  "/v1/calendar/event-tags/list",
  "list_luma_events",
  "get_luma_event_match_keys",
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

for (const text of [
  "runtime/check-health.sh",
  "runtime/check-cloud-heartbeat.sh",
  "runtime/check-slack-socket-health.sh",
  "runtime/audit-live-profile.sh",
  "runtime/nurtureany-cloud-doctor.sh",
  "nurtureanysalesbot health check",
  "nurtureanysalesbot live profile audit",
  "nurtureanysalesbot local cloud heartbeat",
  "nurtureanysalesbot Slack socket watchdog",
  "four enabled operational crons",
  "check-cloud-heartbeat.sh",
  "check-slack-socket-health.sh",
  "nurtureany-cloud-doctor.sh",
  "*/5 * * * *",
  "--no-agent"
]) {
  if (!healthText.includes(text)) fail(`runtime/health-checks.md missing required text: ${text}`);
}

const healthScriptText = textOf("runtime/check-health.sh");
for (const text of [
  "PROFILE=\"${HERMES_PROFILE:-nurtureanysalesbot}\"",
  "export HERMES_HOME=\"$HOME/.hermes/profiles/$PROFILE\"",
  "EXPECT_SLACK_INTENT_TOOLS=\"${EXPECT_SLACK_INTENT_TOOLS:-3}\"",
  "EXPECT_HUBSPOT_TOOLS=\"${EXPECT_HUBSPOT_TOOLS:-42}\"",
  "NURTUREANY_GATEWAY_SERVICE_NAME",
  "systemctl --user is-active --quiet \"$GATEWAY_SERVICE_NAME\"",
  "GATEWAY_LAUNCHD_LABEL",
  "EXPECT_SOLE_NURTUREANY_GATEWAY",
  "NURTUREANY_DUPLICATE_PROFILE",
  "gateway:duplicate-profile-running",
  "gateway:duplicate-launchd-loaded",
  "gateway:multiple-nurtureany-processes",
  "EXPECT_GOOGLE_DRIVE_TOOLS=\"${EXPECT_GOOGLE_DRIVE_TOOLS:-5}\"",
  "EXPECT_EAZYBE_TOOLS=\"${EXPECT_EAZYBE_TOOLS:-4}\"",
  "EXPECT_LUMA_TOOLS=\"${EXPECT_LUMA_TOOLS:-3}\"",
  "EXPECT_PUBLIC_RESEARCH_TOOLS=\"${EXPECT_PUBLIC_RESEARCH_TOOLS:-2}\"",
  "EXPECT_NEAR_ME_TOOLS=\"${EXPECT_NEAR_ME_TOOLS:-6}\"",
  "EXPECT_C360_SALES_PACKET=\"${EXPECT_C360_SALES_PACKET:-1}\"",
  "C360_SALES_PACKET_SMOKE_COMPANY_ID=\"${C360_SALES_PACKET_SMOKE_COMPANY_ID:-9003704457}\"",
  "NURTUREANY_C360_INTERNAL_API_TOKEN",
  "NURTUREANY_C360_SALES_PACKET_URL_TEMPLATE",
  "c360-sales-packet:http-",
  "c360-sales-packet:payload-missing-data",
  "slack-display:interim-assistant-messages-not-disabled",
  "kanban:dispatch-in-gateway-not-disabled",
  "terminal:cwd-points-at-codex-worktree",
  "quick-autorun:not-enabled",
  "slack_nurtureany",
  "EXPECT_SLACK_INTENT_TOOLS=\"${EXPECT_SLACK_INTENT_TOOLS:-3}\"",
  "MCP_TEST_TIMEOUT_SECONDS=\"${MCP_TEST_TIMEOUT_SECONDS:-45}\"",
  "read_recent_slack_intent_context",
  "get_current_slack_thread_context",
  "get_selected_slack_thread_context",
  "slack-intent:configured-channel-ids-missing",
  "slack-thread-context:configured-channel-ids-missing",
  "slack-intent:missing-conversations-history-scope",
  "slack-intent:channel-not-found-or-not-in-channel",
  "slack-thread-context:channel-not-found-or-not-in-channel",
  "mcp:near_me_nurtureany:missing-google-places-env",
  "google-drive:token-permissions-not-600",
  "slack-allowlist:missing-policy-users",
  "slack-allowlist:extra-users",
  "mcp_test public_research_nurtureany",
  "mcp_test slack_nurtureany",
  "mcp:$name-test-timeout",
  "mcp_test eazybe_nurtureany",
  "mcp_test near_me_nurtureany"
]) {
  if (!healthScriptText.includes(text)) fail(`runtime/check-health.sh missing required text: ${text}`);
}

const cloudHeartbeatScriptPath = join(appRoot, "runtime/check-cloud-heartbeat.sh");
const cloudHeartbeatScriptText = textOf("runtime/check-cloud-heartbeat.sh");
for (const text of [
  "PROFILE=\"${HERMES_PROFILE:-nurtureanysalesbot}\"",
  "systemctl --user is-active --quiet \"$GATEWAY_SERVICE_NAME\"",
  "systemctl --user is-enabled \"$GATEWAY_SERVICE_NAME\"",
  "EXPECTED_CLOUD_HEARTBEAT_CRON_NAME",
  "nurtureanysalesbot local cloud heartbeat",
  "EXPECT_ENABLED_CRON_COUNT=\"${EXPECT_ENABLED_CRON_COUNT:-4}\"",
  "EXPECT_HUBSPOT_TOOLS=\"${EXPECT_HUBSPOT_TOOLS:-42}\"",
  "nurtureanysalesbot-check-cloud-heartbeat.sh",
  "cron:enabled-count-unexpected",
  "event-roi-enabled",
  "unsafe-send-message",
  "nurtureanysalesbot-cloud-doctor.sh",
  "cloud-doctor:cron-unhealthy",
  "mcp:hubspot_nurtureany:tools=$EXPECT_HUBSPOT_TOOLS"
]) {
  if (!cloudHeartbeatScriptText.includes(text)) fail(`runtime/check-cloud-heartbeat.sh missing required text: ${text}`);
}

const auditScriptText = textOf("runtime/audit-live-profile.sh");
for (const text of [
  "PROFILE=\"${HERMES_PROFILE:-nurtureanysalesbot}\"",
  "export HERMES_HOME=\"$HOME/.hermes/profiles/$PROFILE\"",
  "NURTUREANY_APP_ROOT",
  "APP_ROOT=\"$PROFILE_DIR/source/nurtureany-sales-bot\"",
  "profile-drift:soul",
  "profile-drift:nurtureany-sales-bot-skill",
  "profile-drift:runtime-mcp",
  "profile-drift:cloud-heartbeat-script",
  "profile-drift:slack-socket-watchdog-script",
  "profile-drift:cloud-doctor-script",
  "profile-boundary:staffany-data-bot-skill-installed",
  "cron:records-invalid",
  "cron:health-check-missing",
  "cron:audit-missing",
  "cron:cloud-heartbeat-missing",
  "cron:slack-socket-watchdog-missing",
  "live-profile:audit-ok"
]) {
  if (!auditScriptText.includes(text)) fail(`runtime/audit-live-profile.sh missing required text: ${text}`);
}

const cloudDoctorScriptPath = join(appRoot, "runtime/nurtureany-cloud-doctor.sh");
const cloudDoctorScriptText = textOf("runtime/nurtureany-cloud-doctor.sh");
for (const text of [
  "nurtureany-cloud-doctor:profile=$PROFILE",
  "gateway_service:systemd",
  "gateway_service:launchctl",
  "gateway_duplicate_check:nurtureanysalesbot_processes=",
  "gateway_duplicate_launchd:",
  "mcp:$server:tools=$count",
  "cron:enabled=",
  "operation_ledger:",
  "daily_runs:"
]) {
  if (!cloudDoctorScriptText.includes(text)) fail(`runtime/nurtureany-cloud-doctor.sh missing required text: ${text}`);
}

for (const [label, scriptPath] of [
  ["health check", join(appRoot, "runtime/check-health.sh")],
  ["cloud heartbeat", cloudHeartbeatScriptPath],
  ["live profile audit", join(appRoot, "runtime/audit-live-profile.sh")],
  ["cloud doctor", cloudDoctorScriptPath],
]) {
  const syntaxCheck = spawnSync("bash", ["-n", scriptPath], { encoding: "utf8" });
  if (syntaxCheck.status !== 0) {
    fail(`Shell syntax check failed for ${label}: ${(syntaxCheck.stderr || syntaxCheck.stdout).trim()}`);
  }
}

const slackSocketScriptPath = join(appRoot, "runtime/check-slack-socket-health.sh");
const slackSocketScriptText = textOf("runtime/check-slack-socket-health.sh");
for (const text of [
  "PROFILE=\"${HERMES_PROFILE:-nurtureanysalesbot}\"",
  "NURTUREANY_SLACK_SOCKET_THRESHOLD_SECONDS",
  "NURTUREANY_SLACK_SOCKET_RESTART_COOLDOWN_SECONDS",
  "NURTUREANY_SLACK_SOCKET_DRY_RUN",
  "systemctl --user restart hermes-gateway-$PROFILE.service",
  "seems to be stale",
  "A new session .* has been established",
  "slack-socket:restart-needed",
  "slack-socket:restart-failed",
  "slack-socket-watchdog.log"
]) {
  if (!slackSocketScriptText.includes(text)) fail(`runtime/check-slack-socket-health.sh missing required text: ${text}`);
}

const slackSocketSyntaxCheck = spawnSync("bash", ["-n", slackSocketScriptPath], {
  encoding: "utf8"
});
if (slackSocketSyntaxCheck.status !== 0) {
  fail(`Shell syntax check failed for Slack socket watchdog: ${(slackSocketSyntaxCheck.stderr || slackSocketSyntaxCheck.stdout).trim()}`);
}

const staleSocketCheck = spawnSync("bash", ["-lc", `
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
cat >"$tmp_dir/agent.log" <<'LOG'
2026-05-12 15:00:00,000 INFO slack_bolt.AsyncApp: A new session (s_1) has been established
2026-05-12 15:10:00,000 INFO slack_bolt.AsyncApp: The session (s_1) seems to be stale. Reconnecting... reason: disconnected for 600+ seconds)
LOG
NURTUREANY_SLACK_SOCKET_LOG="$tmp_dir/agent.log" \\
HERMES_PROFILE_DIR="$tmp_dir/profile" \\
NURTUREANY_SLACK_SOCKET_STATE_DIR="$tmp_dir/state" \\
NURTUREANY_SLACK_SOCKET_NOW_EPOCH=1778570400 \\
NURTUREANY_SLACK_SOCKET_DRY_RUN=1 \\
bash ${JSON.stringify(slackSocketScriptPath)}
`], { encoding: "utf8" });
if (staleSocketCheck.status !== 0 || !staleSocketCheck.stdout.includes("slack-socket:restart-needed")) {
  fail(`Slack socket watchdog stale dry-run failed: ${(staleSocketCheck.stderr || staleSocketCheck.stdout).trim()}`);
}

const recoveredSocketCheck = spawnSync("bash", ["-lc", `
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
cat >"$tmp_dir/agent.log" <<'LOG'
2026-05-12 15:00:00,000 INFO slack_bolt.AsyncApp: The session (s_1) seems to be stale. Reconnecting... reason: disconnected for 600+ seconds)
2026-05-12 15:01:00,000 INFO slack_bolt.AsyncApp: A new session (s_2) has been established
LOG
NURTUREANY_SLACK_SOCKET_LOG="$tmp_dir/agent.log" \\
HERMES_PROFILE_DIR="$tmp_dir/profile" \\
NURTUREANY_SLACK_SOCKET_STATE_DIR="$tmp_dir/state" \\
NURTUREANY_SLACK_SOCKET_NOW_EPOCH=1778570400 \\
NURTUREANY_SLACK_SOCKET_DRY_RUN=1 \\
bash ${JSON.stringify(slackSocketScriptPath)}
`], { encoding: "utf8" });
if (recoveredSocketCheck.status !== 0 || recoveredSocketCheck.stdout.trim() !== "") {
  fail(`Slack socket watchdog recovered dry-run failed: ${(recoveredSocketCheck.stderr || recoveredSocketCheck.stdout).trim()}`);
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

const eazybeCompileCheck = spawnSync("python3", ["-m", "py_compile", join(appRoot, "runtime/mcp/eazybe_nurtureany_server.py")], {
  encoding: "utf8"
});
if (eazybeCompileCheck.status !== 0) {
  fail(`Python compile failed for Eazybe MCP: ${(eazybeCompileCheck.stderr || eazybeCompileCheck.stdout).trim()}`);
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

const eazybeUnitCheck = spawnSync("python3", ["-m", "unittest", "apps/nurtureany-sales-bot/runtime/mcp/test_eazybe_nurtureany_server.py"], {
  cwd: repoRoot,
  encoding: "utf8"
});
if (eazybeUnitCheck.status !== 0) {
  fail(`Python unit tests failed for Eazybe MCP: ${(eazybeUnitCheck.stderr || eazybeUnitCheck.stdout).trim()}`);
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
