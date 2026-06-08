import { existsSync, readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { join, resolve } from "node:path";
import {
  assertFile as sharedAssertFile,
  readJson as sharedReadJson,
  scanForSecretPatterns as sharedScanForSecretPatterns,
} from "./lib/app-packet-verify.mjs";

const repoRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
const appRoot = join(repoRoot, "apps", "launchbot");
const manifestPath = join(appRoot, "app.manifest.json");
const failures = [];

function fail(message) {
  failures.push(message);
}

function assertFile(relPath) {
  sharedAssertFile(appRoot, relPath, fail);
}

function scanForSecretPatterns(relPath) {
  sharedScanForSecretPatterns(appRoot, relPath, fail);
}

function textOf(relPath) {
  const path = join(appRoot, relPath);
  return existsSync(path) ? readFileSync(path, "utf8") : "";
}

function profileBlock(profilesText, profileName) {
  const marker = `  - name: ${profileName}`;
  const start = profilesText.indexOf(marker);
  if (start === -1) return "";
  const next = profilesText.indexOf("\n  - name:", start + marker.length);
  return profilesText.slice(start, next === -1 ? undefined : next);
}

const manifest = existsSync(manifestPath) ? sharedReadJson(manifestPath, fail) : null;
if (!manifest) {
  fail("Missing apps/launchbot/app.manifest.json");
} else {
  if (manifest.profile_name !== "launchbot") fail("Manifest profile_name must be launchbot");
  if (manifest.secrets_copied !== false) fail("Manifest secrets_copied must be false");
  for (const value of Object.values(manifest.paths || {})) {
    assertFile(value);
  }
  if (manifest.launch_workflow?.source_status !== "skill_and_workflow_from_2026_05_11_handoff_source_code_not_present") {
    fail("Manifest launch_workflow.source_status must keep the handoff as a Launchbot skill/workflow");
  }
  if (manifest.launch_workflow?.test_feature?.jira_issue !== "KER-1742") {
    fail("Manifest launch_workflow must preserve KER-1742 test feature");
  }
  if (manifest.launch_workflow?.test_feature?.latest_clean_version !== "v005") {
    fail("Manifest launch_workflow must preserve v005 clean test version");
  }
  if (manifest.slack?.socket_mode !== true) {
    fail("Manifest Slack socket_mode must be true");
  }
  if (manifest.slack?.gateway_restart_notification !== false) {
    fail("Manifest Slack gateway restart notifications must be disabled");
  }
  if (manifest.slack?.strict_mention !== true) {
    fail("Manifest Slack strict_mention must be true");
  }
  if (manifest.slack?.allow_bots !== "mentions") {
    fail("Manifest Slack allow_bots must be mentions");
  }
  if (!manifest.channels?.includes("Slack #all-product-questions")) {
    fail("Manifest channels must include #all-product-questions for read-only KER lookup");
  }
  if (!manifest.channels?.includes("Slack #all-bugs-production")) {
    fail("Manifest channels must include #all-bugs-production for support-watch output");
  }
  for (const eventName of ["app_mention", "message.channels"]) {
    if (!manifest.slack?.required_bot_events?.includes(eventName)) {
      fail(`Manifest Slack required bot events missing ${eventName}`);
    }
  }
  for (const scopeName of ["app_mentions:read", "channels:history", "channels:read", "channels:join", "chat:write"]) {
    if (!manifest.slack?.required_oauth_scopes?.includes(scopeName)) {
      fail(`Manifest Slack required OAuth scopes missing ${scopeName}`);
    }
  }
  if (!manifest.slack?.event_subscription_drift_guard?.includes("message.channels")) {
    fail("Manifest Slack event subscription drift guard must mention message.channels");
  }
  const step0 = (manifest.launch_workflow?.workflow_steps || []).find((step) => step.step === 0);
  if (step0?.status !== "implemented_in_packet") fail("Manifest launch_workflow Step 0 must be implemented_in_packet");
  const step4 = (manifest.launch_workflow?.workflow_steps || []).find((step) => step.step === 4);
  if (step4?.status !== "skill_backed_draft_evaluator") {
    fail("Manifest launch_workflow Step 4 must remain skill_backed_draft_evaluator");
  }
  const contract = manifest.launch_workflow?.help_article_contract || {};
  for (const key of [
    "publishable_body_excludes_internal_appendix",
    "audience_block_centered",
    "numbered_steps_restart_per_subsection",
  ]) {
    if (contract[key] !== true) fail(`Manifest launch_workflow.help_article_contract.${key} must be true`);
  }
  for (const key of [
    "raw_html_in_markdown_body",
    "text_dividers_in_markdown_body",
    "repeated_title_in_body",
  ]) {
    if (contract[key] !== false) fail(`Manifest launch_workflow.help_article_contract.${key} must be false`);
  }
  if (contract.clubany_product_label !== "StaffAny") fail("Manifest must set ClubAny product label to StaffAny");
  if (contract.clubany_management_article_default !== "combined_brands_and_perks_article") {
    fail("Manifest must prefer the combined ClubAny management article");
  }
  if (contract.visible_article_preview_format !== "html") {
    fail("Manifest must require visible help article previews as HTML");
  }
  if (contract.markdown_source_internal_only !== true) {
    fail("Manifest must keep Markdown source internal-only for help articles");
  }
  const defaultLocales = contract.default_article_locales || [];
  if (!defaultLocales.includes("en") || !defaultLocales.includes("id")) {
    fail("Manifest help article contract must default normal article work to en and id locales");
  }
  for (const key of [
    "english_source_before_indonesian",
    "per_locale_evidence_gate",
    "per_locale_format_gate",
    "per_locale_google_docs_review",
    "per_locale_slack_approval",
    "per_locale_intercom_draft",
    "indonesian_needs_refresh_when_english_changes",
  ]) {
    if (contract[key] !== true) fail(`Manifest launch_workflow.help_article_contract.${key} must be true`);
  }
  const videoLane = contract.video_only_update_lane || {};
  if (videoLane.mode !== "Update -> Video-only update") fail("Manifest must register video-only help article update lane");
  if (videoLane.registry !== "skills/help-article-generator/references/video-placement-registry.json") {
    fail("Manifest video-only lane must point at the video placement registry");
  }
  if (videoLane.slot_match_required !== true) fail("Manifest video-only lane must require a slot match");
  if (videoLane.supported_provider !== "loom") fail("Manifest video-only lane must be Loom-only");
  if (videoLane.replace_policy !== "replace_next_video_after_anchor") fail("Manifest video-only lane must use registered anchor replace policy");
  if (videoLane.draft_state_only !== true) fail("Manifest video-only lane must be draft-state only");
  if (videoLane.article_text_rewrite !== false) fail("Manifest video-only lane must forbid article text rewrites");
  if (videoLane.publish !== false) fail("Manifest video-only lane must forbid publishing");
  if (contract.source_of_truth !== "pantheon_code_grounded_behavior") {
    fail("Manifest launch_workflow.help_article_contract.source_of_truth must use Pantheon code-grounded behavior");
  }
  if (contract.code_source_checkout?.repo !== "pantheon") {
    fail("Manifest launch_workflow.help_article_contract.code_source_checkout must describe Pantheon");
  }
  for (const key of [
    "pantheon_evidence_required",
    "pantheon_evidence_gate",
    "pantheon_missing_or_dirty_blocks",
    "pantheon_ambiguous_or_conflicting_blocks",
    "article_planner_required_before_draft",
    "adaptive_intake_gate_before_plan",
    "article_inventory_metadata_only",
    "article_inventory_used_before_live_search",
    "article_shape_stale_check_before_staging",
    "cached_intercom_planning_profile",
    "pre_publish_format_gate",
    "live_intercom_wins_on_conflict",
    "screenshot_capture_optional",
    "screenshot_capture_failure_keeps_placeholders",
    "screenshot_capture_requires_demo_data",
    "screenshot_troubleshooting_uses_playwright",
    "screenshot_staging_credentials_secret_backed",
  ]) {
    if (contract[key] !== true) fail(`Manifest launch_workflow.help_article_contract.${key} must be true`);
  }
  if (contract.screenshot_capture_failure_blocks_article_workflow !== false) {
    fail("Manifest launch_workflow.help_article_contract.screenshot_capture_failure_blocks_article_workflow must be false");
  }
  if (contract.screenshot_storage_state_repo_persistence !== false) {
    fail("Manifest launch_workflow.help_article_contract.screenshot_storage_state_repo_persistence must be false");
  }
  if (contract.intercom_format_profile !== "skills/help-article-generator/references/intercom-format-profile.json") {
    fail("Manifest must point to the Intercom format profile");
  }
  if (contract.article_planning_profile !== "skills/help-article-generator/references/article-planning-profile.json") {
    fail("Manifest must point to the Intercom article planning profile");
  }
  if (contract.intercom_article_inventory !== "skills/help-article-generator/references/intercom-article-inventory.json") {
    fail("Manifest must point to the Intercom article inventory");
  }
  for (const evidencePath of Object.values(manifest.launch_workflow?.evidence || {})) {
    const absolute = join(repoRoot, evidencePath);
    if (!existsSync(absolute)) fail(`Manifest launch_workflow evidence path is missing: ${evidencePath}`);
  }
  if (manifest.source_repositories?.pantheon?.remote !== "git@github.com:staffany-eng/pantheon.git") {
    fail("Manifest Pantheon remote must be staffany-eng/pantheon");
  }
  if (manifest.source_repositories?.pantheon?.branch !== "develop") {
    fail("Manifest Pantheon branch must be develop");
  }
  if (manifest.source_repositories?.pantheon?.daily_update_requires !== "VM GitHub SSH access to staffany-eng/pantheon") {
    fail("Manifest Pantheon daily update must be gated on VM GitHub SSH access");
  }
  const helpMcp = manifest.mcp?.launchbot_help_article || {};
  if (helpMcp.mode !== "draft_only_registered_video_slots") fail("Manifest help article MCP must be draft-only registered video slots");
  const helpTools = new Set(helpMcp.tools || []);
  for (const tool of ["preview_help_article_video_update", "create_help_article_video_update_draft"]) {
    if (!helpTools.has(tool)) fail(`Manifest help article MCP missing tool: ${tool}`);
  }
  if (helpMcp.registry !== "skills/help-article-generator/references/video-placement-registry.json") {
    fail("Manifest help article MCP must point at the video placement registry");
  }
  if (helpMcp.intercom?.access_token_env_var !== "LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN") {
    fail("Manifest help article MCP must use LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN");
  }
  if (helpMcp.intercom?.forced_state !== "draft") fail("Manifest help article MCP must force draft state");
  for (const key of ["publish", "delete", "tag_mutation", "collection_mutation"]) {
    if (helpMcp.intercom?.[key] !== false) fail(`Manifest help article MCP must forbid ${key}`);
  }
  if (helpMcp.video?.provider !== "loom") fail("Manifest help article MCP must be Loom-only");
  if (helpMcp.video?.reject_raw_video_files !== true) fail("Manifest help article MCP must reject raw video files");
  if (helpMcp.video?.reject_slack_file_urls !== true) fail("Manifest help article MCP must reject Slack file URLs");
  const shippedWindmill = manifest.help_article_jira_shipped_windmill || {};
  if (shippedWindmill.mode !== "jira_transition_to_windmill_webhook") fail("Manifest shipped help article Windmill mode unexpected");
  if (shippedWindmill.flow_name !== "launchbot_ker_help_article_on_shipped") fail("Manifest shipped help article Windmill flow name unexpected");
  if (shippedWindmill.state_table !== "launchbot_help_article_runs") fail("Manifest shipped help article state table unexpected");
  if (shippedWindmill.trigger?.transition_to !== "6 - Shipped & Launching") fail("Manifest shipped help article trigger status unexpected");
  if (shippedWindmill.jira?.launch_priority_field_id !== "customfield_10561") fail("Manifest shipped help article launch priority field unexpected");
  if (shippedWindmill.jira?.product_lead_field_id_env_var !== "JIRA_FIELD_PRODUCT_LEAD") fail("Manifest shipped help article Product Lead env unexpected");
  if (shippedWindmill.slack?.default_review_channel_id !== "C0B32M34J3W") fail("Manifest shipped help article review channel unexpected");
  if (shippedWindmill.slack?.mention_gated_feedback !== true) fail("Manifest shipped help article feedback must be mention-gated");
  const releaseNotes = shippedWindmill.release_notes || {};
  if (releaseNotes.screenshot_skill !== "skills/help-article-screenshot-capture/SKILL.md") {
    fail("Manifest release notes must use help-article-screenshot-capture for screenshots");
  }
  if (releaseNotes.screenshot_max_count !== 2) fail("Manifest release notes screenshot max must be 2");
  if (releaseNotes.screenshot_prefer_count !== 1) fail("Manifest release notes should prefer 1 screenshot");
  if (releaseNotes.screenshot_requires_contextual_ui_delta !== true) {
    fail("Manifest release notes screenshots must require contextual UI delta");
  }
  if (releaseNotes.screenshot_sensitive_data_blocks !== true) {
    fail("Manifest release notes screenshots must block sensitive data");
  }
  if (shippedWindmill.intercom?.create_state !== "draft") fail("Manifest shipped help article Intercom create state must be draft");
  if (shippedWindmill.intercom?.publish_state !== "published") fail("Manifest shipped help article Intercom publish state unexpected");
  for (const key of [
    "launch_priority_required",
    "product_lead_slack_mapping_required",
    "pantheon_evidence_required",
    "cached_intercom_planning_first",
    "live_intercom_stale_check_before_write",
    "english_source_before_indonesian",
    "indonesian_needs_refresh_when_english_changes",
    "product_lead_or_override_publish_only",
    "auto_publish_after_exact_confirmation",
  ]) {
    if (shippedWindmill.guards?.[key] !== true) fail(`Manifest shipped help article guard missing: ${key}`);
  }
  const kerMcp = manifest.mcp?.launchbot_ker || {};
  const ifiMcp = manifest.mcp?.launchbot_ifi || {};
  if (ifiMcp.mode !== "preview_first_confirmed_jira_mutation") fail("Manifest IFI MCP must be preview-first confirmed Jira mutation");
  const ifiTools = new Set(ifiMcp.tools || []);
  for (const tool of [
    "preview_ifi_feature_request_tracking",
    "create_or_update_ifi_feature_request_tracking",
    "preview_ifi_feature_request_from_bd_note",
    "create_or_update_ifi_feature_request_from_bd_note",
  ]) {
    if (!ifiTools.has(tool)) fail(`Manifest IFI MCP missing tool: ${tool}`);
  }
  if (ifiMcp.hubspot?.company_identity !== "HubSpot Company ID") fail("Manifest IFI MCP must anchor on HubSpot Company ID");
  if (ifiMcp.jira?.project_key !== "IFI") fail("Manifest IFI MCP must create/update IFI project issues");
  if (ifiMcp.jira?.hubspot_company_id_field_id !== "customfield_10881") {
    fail("Manifest IFI MCP must use customfield_10881 for HubSpot Company ID");
  }
  if (ifiMcp.jira?.approval_marker !== "confirm IFI") fail("Manifest IFI MCP must require confirm IFI");
  if (ifiMcp.jira?.slack_post !== false) fail("Manifest IFI MCP must not post Slack");
  if (ifiMcp.bd_notes?.requires_confirmed_hubspot_company_id !== true) {
    fail("Manifest IFI BD notes mode must require confirmed HubSpot Company ID");
  }
  if (ifiMcp.bd_notes?.alias_auto_mapping !== false) fail("Manifest IFI BD notes mode must not auto-map aliases");
  const productCommitmentMcp = manifest.mcp?.launchbot_product_commitment || {};
  if (productCommitmentMcp.mode !== "read_only_commitment_check") fail("Manifest product commitment MCP must be read-only commitment check");
  const productCommitmentTools = new Set(productCommitmentMcp.tools || []);
  if (!productCommitmentTools.has("check_product_commitment_from_slack_thread")) {
    fail("Manifest product commitment MCP missing tool: check_product_commitment_from_slack_thread");
  }
  if (productCommitmentMcp.slack_context?.configured_channel_ids_env_var !== "LAUNCHBOT_PRODUCT_COMMITMENT_ALLOWED_CHANNEL_IDS") {
    fail("Manifest product commitment MCP must use LAUNCHBOT_PRODUCT_COMMITMENT_ALLOWED_CHANNEL_IDS");
  }
  if (productCommitmentMcp.slack_context?.raw_transcript_persistence !== false) {
    fail("Manifest product commitment MCP must not persist raw Slack transcripts");
  }
  if (productCommitmentMcp.jira?.project_key !== "KER") fail("Manifest product commitment MCP must search KER");
  if (productCommitmentMcp.jira?.reviewed_commitment_fields_env_var !== "LAUNCHBOT_PRODUCT_COMMITMENT_FIELD_IDS") {
    fail("Manifest product commitment MCP must use LAUNCHBOT_PRODUCT_COMMITMENT_FIELD_IDS");
  }
  if (!productCommitmentMcp.jira?.standard_commitment_fields?.includes("fixVersions")) {
    fail("Manifest product commitment MCP must count fixVersions as a standard commitment field");
  }
  for (const key of ["mutations", "comments", "transitions", "assignments", "timeline_inference", "intake_creation"]) {
    if (productCommitmentMcp.jira?.[key] !== false) fail(`Manifest product commitment MCP must forbid Jira ${key}`);
  }
  const featureIntakeMcp = manifest.mcp?.launchbot_feature_intake || {};
  if (featureIntakeMcp.mode !== "confirmed_jpd_intake_create") fail("Manifest feature intake MCP must be confirmed JPD intake create");
  const featureIntakeTools = new Set(featureIntakeMcp.tools || []);
  for (const tool of ["preview_feature_intake_from_slack_thread", "create_feature_intake_from_slack_thread"]) {
    if (!featureIntakeTools.has(tool)) fail(`Manifest feature intake MCP missing tool: ${tool}`);
  }
  if (featureIntakeMcp.slack_context?.configured_channel_ids_env_var !== "LAUNCHBOT_FEATURE_INTAKE_ALLOWED_CHANNEL_IDS") {
    fail("Manifest feature intake MCP must use LAUNCHBOT_FEATURE_INTAKE_ALLOWED_CHANNEL_IDS");
  }
  if (featureIntakeMcp.slack_context?.raw_transcript_persistence !== false) {
    fail("Manifest feature intake MCP must not persist raw Slack transcripts");
  }
  if (featureIntakeMcp.jira?.project_key !== "KER") fail("Manifest feature intake MCP must create in KER");
  if (featureIntakeMcp.jira?.issue_type_id !== "10043") fail("Manifest feature intake MCP must use KER Idea issue type");
  if (featureIntakeMcp.jira?.slack_prd_field_id !== "customfield_10080") {
    fail("Manifest feature intake MCP must use Slack / PRD customfield_10080");
  }
  if (!featureIntakeMcp.jira?.mutations?.includes("create_issue")) {
    fail("Manifest feature intake MCP must expose only create_issue mutation");
  }
  for (const key of ["comments", "transitions", "assignments"]) {
    if (featureIntakeMcp.jira?.[key] !== false) fail(`Manifest feature intake MCP must forbid Jira ${key}`);
  }
  if (featureIntakeMcp.confirmation?.phrase !== "create intake") {
    fail("Manifest feature intake MCP confirmation phrase must be create intake");
  }
  const supportWatchMcp = manifest.mcp?.launchbot_support_watch || {};
  if (supportWatchMcp.mode !== "read_only_weekly_support_watch") fail("Manifest support watch MCP must be read-only weekly support watch");
  const supportWatchTools = new Set(supportWatchMcp.tools || []);
  if (!supportWatchTools.has("preview_weekly_support_watch_report")) {
    fail("Manifest support watch MCP missing tool: preview_weekly_support_watch_report");
  }
  if (supportWatchMcp.intercom?.tickets_api || supportWatchMcp.intercom?.access_token_env_var) {
    fail("Manifest support watch must not use Intercom Tickets API credentials");
  }
  const supportWatchBigQuery = supportWatchMcp.bigquery || {};
  if (supportWatchBigQuery.default_source !== "bigquery") fail("Manifest support watch must use BigQuery source");
  if (supportWatchBigQuery.project_env_var !== "LAUNCHBOT_SUPPORT_WATCH_INTERCOM_PROJECT") fail("Manifest support watch BigQuery project env unexpected");
  if (supportWatchBigQuery.default_project !== "staffany-warehouse") fail("Manifest support watch BigQuery project unexpected");
  if (supportWatchBigQuery.intercom_dataset_env_var !== "LAUNCHBOT_SUPPORT_WATCH_INTERCOM_DATASET") fail("Manifest support watch Intercom dataset env unexpected");
  if (!supportWatchBigQuery.intercom_tables?.includes("conversations") || !supportWatchBigQuery.intercom_tables?.includes("conversation_parts")) {
    fail("Manifest support watch must use Intercom conversations and conversation_parts tables");
  }
  if (supportWatchBigQuery.analytics_dataset_env_var !== "LAUNCHBOT_SUPPORT_WATCH_ANALYTICS_DATASET") fail("Manifest support watch analytics dataset env unexpected");
  if (supportWatchBigQuery.bq_timeout_seconds_env_var !== "LAUNCHBOT_SUPPORT_WATCH_BQ_TIMEOUT_SECONDS") fail("Manifest support watch BigQuery timeout env unexpected");
  if (supportWatchBigQuery.default_bq_timeout_seconds !== 240) fail("Manifest support watch BigQuery timeout unexpected");
  if (supportWatchBigQuery.org_mapping_table !== "dim_org_company") fail("Manifest support watch must document dim_org_company mapping");
  if (supportWatchBigQuery.include_whatsapp_env_var !== "LAUNCHBOT_SUPPORT_WATCH_INCLUDE_WHATSAPP") fail("Manifest support watch WhatsApp include env unexpected");
  if (supportWatchBigQuery.whatsapp_view_env_var !== "LAUNCHBOT_SUPPORT_WATCH_WHATSAPP_VIEW") fail("Manifest support watch WhatsApp view env unexpected");
  if (supportWatchBigQuery.default_whatsapp_view !== "analytics.support_watch_whatsapp_ticket_logs") fail("Manifest support watch WhatsApp view unexpected");
  if (supportWatchBigQuery.default_whatsapp_view?.startsWith("gsheets.")) fail("Manifest support watch WhatsApp runtime source must not be Drive-backed gsheets");
  if (supportWatchBigQuery.whatsapp_source_view_env_var !== "LAUNCHBOT_SUPPORT_WATCH_WHATSAPP_SOURCE_VIEW") fail("Manifest support watch WhatsApp source view env unexpected");
  if (supportWatchBigQuery.default_whatsapp_source_view !== "gsheets.cs_tickets_logs_all_view") fail("Manifest support watch WhatsApp source view unexpected");
  if (supportWatchBigQuery.whatsapp_refresh_transfer_name_env_var !== "LAUNCHBOT_SUPPORT_WATCH_WHATSAPP_REFRESH_TRANSFER_NAME") fail("Manifest support watch WhatsApp refresh transfer env unexpected");
  if (supportWatchBigQuery.default_whatsapp_refresh_transfer_name !== "Launchbot support watch WhatsApp native mirror refresh") fail("Manifest support watch WhatsApp refresh transfer name unexpected");
  if (supportWatchBigQuery.whatsapp_refresh_schedule_utc_env_var !== "LAUNCHBOT_SUPPORT_WATCH_WHATSAPP_REFRESH_SCHEDULE_UTC") fail("Manifest support watch WhatsApp refresh schedule env unexpected");
  if (supportWatchBigQuery.default_whatsapp_refresh_schedule_utc !== "every day 00:30") fail("Manifest support watch WhatsApp refresh schedule unexpected");
  if (supportWatchBigQuery.whatsapp_max_staleness_hours_env_var !== "LAUNCHBOT_SUPPORT_WATCH_WHATSAPP_MAX_STALENESS_HOURS") fail("Manifest support watch WhatsApp staleness env unexpected");
  if (supportWatchBigQuery.default_whatsapp_max_staleness_hours !== 36) fail("Manifest support watch WhatsApp staleness unexpected");
  if (supportWatchMcp.slack_context?.default_output_channel_name !== "all-bugs-production") {
    fail("Manifest support watch default output channel must be all-bugs-production");
  }
  if (supportWatchMcp.slack_context?.dedupe_channel_names_env_var !== "LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_NAMES") {
    fail("Manifest support watch dedupe channel names env unexpected");
  }
  if (supportWatchMcp.slack_context?.mcp_posts_slack !== false) fail("Manifest support watch MCP must not post Slack");
  if (supportWatchMcp.jira?.default_edt_jql !== 'project = PCO AND "PS Team" = "Eng Duty" AND statusCategory != Done ORDER BY updated DESC') {
    fail("Manifest support watch default EDT JQL unexpected");
  }
  for (const key of ["mutations", "comments", "transitions", "assignments"]) {
    if (supportWatchMcp.jira?.[key] !== false) fail(`Manifest support watch MCP must forbid Jira ${key}`);
  }
  for (const forbiddenAction of ["linear_ticket_create", "jira_ticket_create", "engineer_tag", "owner_assignment"]) {
    if (!supportWatchMcp.v1_forbidden_actions?.includes(forbiddenAction)) {
      fail(`Manifest support watch missing forbidden action: ${forbiddenAction}`);
    }
  }
  const supportWatchWhatsappRefresh = (manifest.expected_crons || []).find((cron) => cron.name === "Launchbot support watch WhatsApp native mirror refresh");
  if (supportWatchWhatsappRefresh?.schedule !== "every day 00:30") fail("Manifest must define WhatsApp native mirror scheduled query");
  if (supportWatchWhatsappRefresh?.mode !== "bigquery-scheduled-query") fail("Manifest WhatsApp native mirror refresh must be a BigQuery scheduled query");
  if (supportWatchWhatsappRefresh?.source !== "staffany-warehouse.gsheets.cs_tickets_logs_all_view") fail("Manifest WhatsApp native mirror source unexpected");
  if (supportWatchWhatsappRefresh?.target !== "staffany-warehouse.analytics.support_watch_whatsapp_ticket_logs") fail("Manifest WhatsApp native mirror target unexpected");
  const healthCron = (manifest.expected_crons || []).find((cron) => cron.name === "launchbot health check");
  if (healthCron?.schedule !== "*/5 * * * *") fail("Manifest must define Launchbot health check cron");
  if (healthCron?.mode !== "no-agent") fail("Manifest health check cron must be no-agent");
  const pantheonCron = (manifest.expected_crons || []).find((cron) => cron.name === "launchbot pantheon repo update");
  if (pantheonCron?.schedule !== "0 22 * * *") fail("Manifest must define daily Pantheon repo update cron");
  if (pantheonCron?.mode !== "no-agent") fail("Manifest Pantheon repo update cron must be no-agent");
  if (pantheonCron?.requires !== "VM GitHub SSH access to staffany-eng/pantheon") {
    fail("Manifest Pantheon repo update cron must document the GitHub SSH access gate");
  }
  const monitorCron = (manifest.expected_crons || []).find((cron) => cron.name === "launchbot feature intake monitor");
  if (monitorCron?.schedule !== "* * * * *") fail("Manifest must define feature intake monitor cron");
  if (monitorCron?.mode !== "no-agent") fail("Manifest feature intake monitor cron must be no-agent");
  const monitor = manifest.feature_intake_monitor || {};
  if (monitor.mode !== "no_agent_slack_poll") fail("Manifest feature intake monitor mode must be no_agent_slack_poll");
  if (!monitor.default_channel_ids?.includes("CF8PK6V4J")) fail("Manifest feature intake monitor default channels must include CF8PK6V4J");
  if (monitor.channel_ids_env_var !== "LAUNCHBOT_FEATURE_INTAKE_MONITOR_CHANNEL_IDS") fail("Manifest monitor channel env unexpected");
  if (monitor.state_path_env_var !== "LAUNCHBOT_FEATURE_INTAKE_MONITOR_STATE_PATH") fail("Manifest monitor state path env unexpected");
  if (monitor.default_state_path !== "~/.hermes/profiles/launchbot/runtime/feature-intake-monitor-state.json") fail("Manifest monitor state path unexpected");
  if (monitor.default_max_messages_per_run !== 100) fail("Manifest monitor max messages default unexpected");
  if (monitor.default_overlap_seconds !== 600) fail("Manifest monitor overlap default unexpected");
  if (monitor.normal_gateway_require_mention !== true) fail("Manifest monitor must keep normal gateway mention-gated");
  if (monitor.raw_transcript_persistence !== false) fail("Manifest monitor must not persist raw transcripts");
  if (monitor.posts_slack_previews !== true) fail("Manifest monitor must post Launchbot-owned previews");
  if (monitor.slack_reply_prefix !== "Launchbot automation:") fail("Manifest monitor must use Launchbot automation prefix");
  const supportWatchCron = (manifest.expected_crons || []).find((cron) => cron.name === "launchbot support watch");
  if (supportWatchCron?.schedule !== "0 1 * * 4") fail("Manifest must define support watch cron");
  if (supportWatchCron?.mode !== "no-agent") fail("Manifest support watch cron must be no-agent");
  const supportWatchMonitor = manifest.support_watch_monitor || {};
  if (supportWatchMonitor.mode !== "no_agent_weekly_report") fail("Manifest support watch monitor mode must be no_agent_weekly_report");
  if (supportWatchMonitor.default_output_channel_name !== "all-bugs-production") fail("Manifest support watch output must be all-bugs-production");
  if (supportWatchMonitor.output_channel_name_env_var !== "LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME") fail("Manifest support watch channel name env unexpected");
  if (supportWatchMonitor.output_channel_id_env_var !== "LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_ID") fail("Manifest support watch channel ID env unexpected");
  if (supportWatchMonitor.dedupe_channel_ids_env_var !== "LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_IDS") fail("Manifest support watch dedupe env unexpected");
  if (supportWatchMonitor.dedupe_channel_names_env_var !== "LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_NAMES") fail("Manifest support watch dedupe names env unexpected");
  if (supportWatchMonitor.default_dedupe_channel_names !== "team-cs-eng-duty") fail("Manifest support watch default dedupe channel name unexpected");
  if (supportWatchMonitor.edt_jql_env_var !== "LAUNCHBOT_SUPPORT_WATCH_EDT_JQL") fail("Manifest support watch EDT JQL env unexpected");
  if (supportWatchMonitor.default_state_path !== "~/.hermes/profiles/launchbot/runtime/support-watch-state.json") fail("Manifest support watch state path unexpected");
  if (supportWatchMonitor.default_lookback_days !== 7) fail("Manifest support watch lookback default unexpected");
  if (supportWatchMonitor.default_max_tickets !== 100) fail("Manifest support watch max tickets default unexpected");
  if (supportWatchMonitor.default_source !== "bigquery") fail("Manifest support watch monitor source unexpected");
  if (supportWatchMonitor.default_intercom_project !== "staffany-warehouse") fail("Manifest support watch monitor project unexpected");
  if (supportWatchMonitor.default_intercom_dataset !== "intercom") fail("Manifest support watch monitor dataset unexpected");
  if (supportWatchMonitor.bq_timeout_seconds_env_var !== "LAUNCHBOT_SUPPORT_WATCH_BQ_TIMEOUT_SECONDS") fail("Manifest support watch monitor BigQuery timeout env unexpected");
  if (supportWatchMonitor.default_bq_timeout_seconds !== 240) fail("Manifest support watch monitor BigQuery timeout unexpected");
  if (supportWatchMonitor.default_include_whatsapp !== true) fail("Manifest support watch monitor must include WhatsApp by default");
  if (supportWatchMonitor.default_whatsapp_view !== "analytics.support_watch_whatsapp_ticket_logs") fail("Manifest support watch monitor WhatsApp view unexpected");
  if (supportWatchMonitor.default_whatsapp_view?.startsWith("gsheets.")) fail("Manifest support watch monitor WhatsApp runtime source must not be Drive-backed gsheets");
  if (supportWatchMonitor.default_whatsapp_source_view !== "gsheets.cs_tickets_logs_all_view") fail("Manifest support watch monitor WhatsApp source view unexpected");
  if (supportWatchMonitor.default_whatsapp_refresh_transfer_name !== "Launchbot support watch WhatsApp native mirror refresh") fail("Manifest support watch monitor WhatsApp refresh transfer unexpected");
  if (supportWatchMonitor.default_whatsapp_refresh_schedule_utc !== "every day 00:30") fail("Manifest support watch monitor WhatsApp refresh schedule unexpected");
  if (supportWatchMonitor.default_whatsapp_max_staleness_hours !== 36) fail("Manifest support watch monitor WhatsApp max staleness unexpected");
  if (supportWatchMonitor.raw_transcript_persistence !== false) fail("Manifest support watch must not persist raw transcripts");
  if (supportWatchMonitor.posts_slack_reports !== true) fail("Manifest support watch must post reports from monitor");
  if (supportWatchMonitor.slack_reply_prefix !== "Launchbot automation:") fail("Manifest support watch must use Launchbot automation prefix");
  for (const key of ["ticket_creation", "engineer_tags", "owner_assignment"]) {
    if (supportWatchMonitor[key] !== false) fail(`Manifest support watch monitor must forbid ${key}`);
  }
  const taxAdvisory = manifest.tax_advisory || {};
  if (taxAdvisory.mode !== "source_backed_indonesia_payroll_tax_answers") {
    fail("Manifest tax_advisory mode must be source_backed_indonesia_payroll_tax_answers");
  }
  if (taxAdvisory.skill !== "skills/staffany-indonesia-payroll-tax-grimoire/SKILL.md") {
    fail("Manifest tax_advisory must point to the Indonesia payroll tax grimoire skill");
  }
  if (taxAdvisory.regulation_update_skill !== "skills/staffany-indonesia-payroll-tax-grimoire/skills/indonesia-tax-knowledge-updater/SKILL.md") {
    fail("Manifest tax_advisory must point to the Indonesia tax knowledge updater skill");
  }
  if (taxAdvisory.knowledge_bank_validator !== "skills/staffany-indonesia-payroll-tax-grimoire/skills/indonesia-tax-knowledge-updater/scripts/validate_knowledge_bank.rb") {
    fail("Manifest tax_advisory must point to the Indonesia tax knowledge-bank validator");
  }
  for (const topic of ["PPh21", "SPT Masa PPh 21/26", "Formulir 1721-A1 / BPA1", "BPMP", "BP21"]) {
    if (!taxAdvisory.topics?.includes(topic)) fail(`Manifest tax_advisory missing topic: ${topic}`);
  }
  for (const contractField of [
    "Direct answer",
    "Regulatory basis",
    "StaffAny system behavior",
    "Gap / risk / not validated",
    "Sources checked",
    "Confidence",
  ]) {
    if (!taxAdvisory.answer_contract?.includes(contractField)) {
      fail(`Manifest tax_advisory answer contract missing: ${contractField}`);
    }
  }
  if (!taxAdvisory.current_fact_policy?.includes("official online sources")) {
    fail("Manifest tax_advisory must require official online checks for current facts");
  }
  if (!taxAdvisory.current_fact_policy?.includes("regulation update skill workflow")) {
    fail("Manifest tax_advisory must require the regulation update workflow before current-law answers");
  }
  if (!taxAdvisory.pre_final_validation_policy?.includes("knowledge-bank validator")) {
    fail("Manifest tax_advisory must require knowledge-bank validation before final answers when knowledge changes");
  }
  if (!taxAdvisory.staffany_behavior_policy?.includes("Pantheon code")) {
    fail("Manifest tax_advisory must require Pantheon/code evidence for StaffAny behavior");
  }
  if (!taxAdvisory.bpjs_scope?.includes("outside the core tax skill")) {
    fail("Manifest tax_advisory must label BPJS-only scope");
  }
  if (!taxAdvisory.sensitive_data_policy?.includes("NPWP")) {
    fail("Manifest tax_advisory must include sensitive payroll data policy");
  }
}

for (const relPath of [
  "profile/SOUL.md",
  "profile/config.template.yaml",
  "runtime/slack.md",
  "runtime/health-checks.md",
  "runtime/check-health.sh",
  "runtime/audit-live-profile.sh",
  "runtime/sync-live-profile.sh",
  "runtime/update-pantheon-repo.sh",
  "runtime/monitor-feature-intake.py",
  "runtime/test_monitor_feature_intake.py",
  "runtime/monitor-support-watch.py",
  "runtime/test_monitor_support_watch.py",
  "runtime/support-watch-whatsapp-refresh.sql",
  "runtime/intercom-format-gate.mjs",
  "runtime/intercom-format-gate.test.mjs",
  "runtime/help-article-staging-auth-state.mjs",
  "runtime/help-article-staging-auth-state.test.mjs",
  "runtime/mcp/profile_env.py",
  "runtime/mcp/launchbot_ker_server.py",
  "runtime/mcp/launchbot_ifi_server.py",
  "runtime/mcp/launchbot_product_commitment_server.py",
  "runtime/mcp/launchbot_feature_intake_core.py",
  "runtime/mcp/launchbot_feature_intake_server.py",
  "runtime/mcp/launchbot_support_watch_core.py",
  "runtime/mcp/launchbot_support_watch_server.py",
  "runtime/mcp/launchbot_help_article_server.py",
  "runtime/windmill/launchbot_ker_help_article_on_shipped.mjs",
  "runtime/windmill/launchbot_ker_help_article_on_shipped.test.mjs",
  "runtime/windmill/launchbot_help_article_runs.sql",
  "runtime/mcp/test_helpers.py",
  "runtime/mcp/test_launchbot_ker_server.py",
  "runtime/mcp/test_launchbot_ifi_server.py",
  "runtime/mcp/test_launchbot_feature_intake_server.py",
  "runtime/mcp/test_launchbot_support_watch_server.py",
  "runtime/mcp/test_launchbot_help_article_server.py",
  "runtime/mcp/fixtures/help_article_video_fixtures.json",
  "skills/help-article-generator/SKILL.md",
  "skills/help-article-validator/SKILL.md",
  "skills/help-article-validator/agents/openai.yaml",
  "skills/help-article-validator/references/model-help-articles.md",
  "skills/help-article-feedback-updater/SKILL.md",
  "skills/help-article-feedback-updater/agents/openai.yaml",
  "skills/help-article-screenshot-capture/SKILL.md",
  "skills/help-article-screenshot-troubleshooter/SKILL.md",
  "skills/help-article-generator/references/help-article-skeleton.md",
  "skills/help-article-generator/references/intercom-format-profile.json",
  "skills/help-article-generator/references/article-planning-profile.json",
  "skills/help-article-generator/references/intercom-article-inventory.json",
  "skills/help-article-generator/references/video-placement-registry.json",
  "skills/launch-priority-identifier/SKILL.md",
  "skills/launch-priority-identifier/agents/openai.yaml",
  "skills/customer-support-release-notes-generator/SKILL.md",
  "skills/customer-support-release-notes-generator/agents/openai.yaml",
  "skills/customer-support-release-notes-validator/SKILL.md",
  "skills/customer-support-release-notes-validator/agents/openai.yaml",
  "skills/customer-support-release-notes-feedback-updater/SKILL.md",
  "skills/customer-support-release-notes-feedback-updater/agents/openai.yaml",
  "skills/weekly-support-watch/SKILL.md",
  "skills/staffany-indonesia-payroll-tax-grimoire/SKILL.md",
  "skills/staffany-indonesia-payroll-tax-grimoire/skills/indonesia-payroll-tax-advisor/SKILL.md",
  "skills/staffany-indonesia-payroll-tax-grimoire/skills/indonesia-payroll-tax-advisor/references/reporting.md",
  "skills/staffany-indonesia-payroll-tax-grimoire/skills/indonesia-payroll-tax-advisor/references/pph21.md",
  "skills/staffany-indonesia-payroll-tax-grimoire/skills/indonesia-payroll-tax-advisor/references/source-quality.md",
  "skills/staffany-indonesia-payroll-tax-grimoire/skills/indonesia-tax-knowledge-updater/SKILL.md",
  "skills/staffany-indonesia-payroll-tax-grimoire/skills/indonesia-tax-knowledge-updater/scripts/validate_knowledge_bank.rb",
  "skills/staffany-indonesia-payroll-tax-grimoire/skills/pph21-settings-explainer/SKILL.md",
  "runtime/launch-workflow.md",
  "runtime/launchbot_e2e.py",
  "tests/launch-workflow-regression-cases.md",
  "tests/prompt-evals.json",
]) {
  assertFile(relPath);
  scanForSecretPatterns(relPath);
}

const configText = existsSync(join(appRoot, "profile", "config.template.yaml"))
  ? readFileSync(join(appRoot, "profile", "config.template.yaml"), "utf8")
  : "";
for (const requiredText of [
  'provider: "anthropic"',
  'default: "claude-sonnet-4-6"',
  "interim_assistant_messages: false",
  'tool_progress: "off"',
  "streaming: false",
  "reactions: false",
  "gateway_restart_notification: false",
  "C0B32M34J3W",
  "CF8PK6V4J",
  "launchbot_ker",
  "launchbot_ifi",
  "launchbot_product_commitment",
  "launchbot_feature_intake",
  "launchbot_help_article",
  "find_ker_ticket_from_slack_thread",
  "lookup_ker_ticket_by_key",
  "preview_ifi_feature_request_tracking",
  "create_or_update_ifi_feature_request_tracking",
  "preview_ifi_feature_request_from_bd_note",
  "create_or_update_ifi_feature_request_from_bd_note",
  "preview_feature_intake_from_slack_thread",
  "create_feature_intake_from_slack_thread",
  "preview_help_article_video_update",
  "create_help_article_video_update_draft",
  "help_article_jira_shipped_windmill",
  "launchbot_ker_help_article_on_shipped",
  "launchbot_help_article_runs",
  "WINDMILL_WEBHOOK_TOKEN",
  "JIRA_FIELD_LAUNCH_PRIORITY",
  "customfield_10561",
  "JIRA_FIELD_PRODUCT_LEAD",
  "LAUNCHBOT_REVIEW_CHANNEL_ID",
  "LAUNCHBOT_JIRA_ACCOUNT_TO_SLACK_USER_MAP",
  "INTERCOM_AUTHOR_ID",
  "INTERCOM_HELP_ARTICLE_DEFAULT_PARENT_ID",
  "LAUNCHBOT_INTERCOM_UPDATE_DRAFT_SUPPORTED",
  "@Launch Bot publish help articles KER-123",
  "LAUNCHBOT_RELEASE_NOTES_OUTPUT_CHANNEL_ID",
  "LAUNCHBOT_RELEASE_NOTES_OUTPUT_CHANNEL_NAME",
  "@Launch Bot approve release notes KER-123",
  "all-product-new-updates",
  "JIRA_API_TOKEN",
  "HUBSPOT_ACCESS_TOKEN",
  "JIRA_IFI_HUBSPOT_COMPANY_ID_FIELD_ID",
  "customfield_10881",
  "confirm IFI",
  "LAUNCHBOT_PRODUCT_COMMITMENT_ALLOWED_CHANNEL_IDS",
  "LAUNCHBOT_PRODUCT_COMMITMENT_FIELD_IDS",
  "read_only_commitment_check",
  "no_timeline_inference: true",
  "no_intake_creation: true",
  "LAUNCHBOT_FEATURE_INTAKE_ALLOWED_CHANNEL_IDS",
  "LAUNCHBOT_FEATURE_INTAKE_MONITOR_CHANNEL_IDS",
  "LAUNCHBOT_FEATURE_INTAKE_MONITOR_STATE_PATH",
  "LAUNCHBOT_FEATURE_INTAKE_MONITOR_MAX_MESSAGES_PER_RUN",
  "LAUNCHBOT_FEATURE_INTAKE_MONITOR_OVERLAP_SECONDS",
  "feature_intake_monitor",
  "no_agent_slack_poll",
  "no_raw_transcript_persistence: true",
  "launchbot_support_watch",
  "preview_weekly_support_watch_report",
  "support_watch_monitor",
  "no_agent_weekly_report",
  "LAUNCHBOT_SUPPORT_WATCH_SOURCE",
  "LAUNCHBOT_SUPPORT_WATCH_INTERCOM_PROJECT",
  "LAUNCHBOT_SUPPORT_WATCH_INTERCOM_DATASET",
  "LAUNCHBOT_SUPPORT_WATCH_ANALYTICS_DATASET",
  "LAUNCHBOT_SUPPORT_WATCH_BQ_TIMEOUT_SECONDS",
  "LAUNCHBOT_SUPPORT_WATCH_INCLUDE_WHATSAPP",
  "LAUNCHBOT_SUPPORT_WATCH_WHATSAPP_VIEW",
  "LAUNCHBOT_SUPPORT_WATCH_WHATSAPP_SOURCE_VIEW",
  "LAUNCHBOT_SUPPORT_WATCH_WHATSAPP_REFRESH_TRANSFER_NAME",
  "LAUNCHBOT_SUPPORT_WATCH_WHATSAPP_REFRESH_SCHEDULE_UTC",
  "LAUNCHBOT_SUPPORT_WATCH_WHATSAPP_MAX_STALENESS_HOURS",
  "LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME",
  "LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_ID",
  "LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_IDS",
  "LAUNCHBOT_SUPPORT_WATCH_EDT_JQL",
  "LAUNCHBOT_SUPPORT_WATCH_STATE_PATH",
  "LAUNCHBOT_SUPPORT_WATCH_LOOKBACK_DAYS",
  "LAUNCHBOT_SUPPORT_WATCH_MAX_TICKETS",
  "all-bugs-production",
  "0 1 * * 4",
  "read_only_weekly_support_watch",
  "no_ticket_creation: true",
  "no_engineer_tags: true",
  "no_owner_assignment: true",
  "confirmed_jpd_intake_create",
  "required_confirmation: \"create intake\"",
  "LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN",
  "draft_only_registered_video_slots",
  "allow_publish: false",
  "allow_delete: false",
  "allow_tag_mutation: false",
  "allow_collection_mutation: false",
  'allowed_channels: ""',
  "/home/leekaiyi/.hermes/profiles/launchbot/source/launchbot",
  "sources:",
  "pantheon:",
  "git@github.com:staffany-eng/pantheon.git",
  "LAUNCHBOT_PANTHEON_REPO_DIR",
  "LAUNCHBOT_PANTHEON_SSH_KEY",
]) {
  if (!configText.includes(requiredText)) fail(`config.template.yaml missing required text: ${requiredText}`);
}
if (configText.includes("/Users/leekaiyi/.hermes/profiles/launchbot/source/launchbot")) {
  fail("config.template.yaml must not point cloud runtime at the local Mac launchbot profile");
}

const profilesText = existsSync(join(repoRoot, "ops", "hermes", "profiles.yaml"))
  ? readFileSync(join(repoRoot, "ops", "hermes", "profiles.yaml"), "utf8")
  : "";
const launchbotProfileBlock = profileBlock(profilesText, "launchbot");
if (!launchbotProfileBlock) {
  fail("ops/hermes/profiles.yaml missing launchbot profile");
} else {
  for (const requiredText of [
    "deploy_host: hermes-data-bot-poc",
    "local_profile_policy: cloud_only",
    "systemd_unit: hermes-gateway-launchbot.service",
    "C01RZ7SHC8K",
    "CF8PK6V4J",
    "launchbot_ifi:",
    "launchbot_product_commitment:",
    "launchbot feature intake monitor",
    "launchbot support watch",
    "launchbot_feature_intake:",
    "launchbot_support_watch:",
    "launchbot_help_article:",
  ]) {
    if (!launchbotProfileBlock.includes(requiredText)) {
      fail(`launchbot profile missing required cloud-only text: ${requiredText}`);
    }
  }
  if (launchbotProfileBlock.includes("launchd_label:")) {
    fail("launchbot profile must not define a Mac launchd_label");
  }
}

const soulText = existsSync(join(appRoot, "profile", "SOUL.md"))
  ? readFileSync(join(appRoot, "profile", "SOUL.md"), "utf8")
  : "";
for (const requiredText of [
  "Do not use Kai Yi's user token",
  "Kai Yi's user token",
  "Confidence: <verified | needs-check | blocked>",
  "find_ker_ticket_from_slack_thread",
  "preview_ifi_feature_request_tracking",
  "create_or_update_ifi_feature_request_tracking",
  "preview_ifi_feature_request_from_bd_note",
  "create_or_update_ifi_feature_request_from_bd_note",
  "preview-first IFI tracking linked to HubSpot Company ID",
  "customfield_10881",
  "confirm IFI",
  "Do not auto-map aliases",
  "preview_feature_intake_from_slack_thread",
  "create_feature_intake_from_slack_thread",
  "check_product_commitment_from_slack_thread",
  "read-only product commitment checks from Jira KER/JPD",
  "LAUNCHBOT_PRODUCT_COMMITMENT_FIELD_IDS",
  "create intake",
  "confirmed Slack-to-KER feature intake",
  "no-agent monitor",
  "Broad channel monitoring must run through the no-agent feature-intake monitor",
  "It must not store raw Slack transcripts",
  "weekly report-only support watch",
  "preview_weekly_support_watch_report",
  "Weekly Support Watch",
  "#all-bugs-production",
  "LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME",
  "LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_IDS",
  "No new findings means no Slack post",
  "no ticket creation, owner assignment, or engineer tags",
  "KER-2109",
  "cached Intercom article planning",
  "Pantheon-grounded StaffAny help articles in English and Indonesian",
  "Intercom-ready HTML, not Markdown",
  "help-article-validator",
  "help-article-feedback-updater",
  "Create and Manage Disbursement",
  "Managing Employee Document Types",
  "registered video-slot update drafts",
  "Intercom format checks",
  "message.channels",
  "Intercom draft/staging articles",
  "preview_help_article_video_update",
  "create_help_article_video_update_draft",
  "draft it",
  "skills/help-article-generator/references/video-placement-registry.json",
  "will_publish: false",
  "Launchbot packet",
  "Launch Superpower handoff is a Launchbot skill/workflow",
  "Never answer `Source: Launch Superpower Bot packet`",
  "#all-product-questions",
  "read-only product-commitment / KER lookup",
  "cloud-primary",
  "Launchbot's bot identity",
  "every Slack turn must include an explicit `@Launch Bot` mention",
  "applies inside threads too",
  "Never print a `Router:` line in normal Slack replies.",
  "do not redirect users to another bot. Execute the workflow directly in Launchbot.",
  "Do not tell users to `Ping @Product Ops Bot`",
  "Use `skills/staffany-indonesia-payroll-tax-grimoire/SKILL.md` first.",
  "For StaffAny product capability claims, inspect Pantheon code",
  "For current laws, rates, forms, deadlines, filing channels, or regulator platform changes, verify against official online sources",
  "use `skills/indonesia-tax-knowledge-updater/SKILL.md` inside the grimoire before the final answer.",
  "run `skills/indonesia-tax-knowledge-updater/scripts/validate_knowledge_bank.rb` before the final answer",
  "BPJS-only questions are outside the core tax skill",
  "Regulatory basis:",
  "StaffAny system behavior:",
  "Gap / risk / not validated:",
  "Jira-Shipped Launch Notes Lane",
  "launch-priority-identifier",
  "help-article-validator",
  "help-article-feedback-updater",
  "release-notes-generator",
  "release-notes-validator",
  "release-notes-feedback-updater",
  "help-article-screenshot-capture",
  "only 1-2 screenshots",
  "directly show the UI/UX delta",
  "#all-product-new-updates",
  "@Launch Bot approve release notes KER-123",
  "mention the Product Lead",
  "Module, What's new, How this helps users, What's needed to be setup, Help article link",
]) {
  if (!soulText.includes(requiredText)) fail(`SOUL.md missing required text: ${requiredText}`);
}

const launchPrioritySkillText = textOf("skills/launch-priority-identifier/SKILL.md");
for (const requiredText of [
  "customfield_10561",
  "Do not use Jira engineering priority",
  "Next Skill: release-notes-generator",
  "Priority Source: <slack_message | jira_customfield_10561 | needs-check>",
]) {
  if (!launchPrioritySkillText.includes(requiredText)) fail(`launch-priority-identifier/SKILL.md missing required text: ${requiredText}`);
}

const csReleaseNotesSkillText = textOf("skills/customer-support-release-notes-generator/SKILL.md");
for (const requiredText of [
  "name: release-notes-generator",
  "Generate short release notes for Sales, PS, CS, and Product",
  "Focus `What's new` on UI/UX changes from the previous version to the newer one",
  "Include just enough existing StaffAny feature context",
  "- Module",
  "- What's new",
  "- How this helps users",
  "- What's needed to be setup",
  "- Help article link",
  "Do not explain how the change helps CS, support agents, triage, or internal teams in that section.",
  "Use `help-article-screenshot-capture`",
  "at most 2 screenshots",
  "Screenshot 1: the changed screen or entry point users will notice first.",
  "release-notes-validator",
  "release-notes-feedback-updater",
  "Launchbot automation: <@product_lead_slack_user_id> please review these release notes",
  "@Launch Bot approve release notes <KER-key>",
  "#all-product-new-updates",
]) {
  if (!csReleaseNotesSkillText.includes(requiredText)) fail(`customer-support-release-notes-generator/SKILL.md missing required text: ${requiredText}`);
}

const helpArticleValidatorSkillText = textOf("skills/help-article-validator/SKILL.md");
for (const requiredText of [
  "Validate StaffAny Help Center article drafts",
  "HTML display readiness",
  "draft_html",
  "visible draft or patch must be HTML, not Markdown",
  "Read `references/model-help-articles.md` before scoring",
  "Model article format fit: `0-30`",
  "Information correctness and source grounding: `0-35`",
  "Validation Score: <0-100>",
  "Evidence-Based Reasoning:",
  "Next Skill: <none | help-article-feedback-updater>",
]) {
  if (!helpArticleValidatorSkillText.includes(requiredText)) fail(`help-article-validator/SKILL.md missing required text: ${requiredText}`);
}

const helpArticleModelReferenceText = textOf("skills/help-article-validator/references/model-help-articles.md");
for (const requiredText of [
  "https://help.staffany.com/en/articles/13867569-create-and-manage-disbursement",
  "https://help.staffany.com/en/articles/14318367-managing-employee-document-types",
  "Create and Manage Disbursement",
  "Managing Employee Document Types",
  "Shared High-Score Patterns",
  "Failure Modes To Penalize",
]) {
  if (!helpArticleModelReferenceText.includes(requiredText)) fail(`help-article-validator model references missing required text: ${requiredText}`);
}

const helpArticleUpdaterSkillText = textOf("skills/help-article-feedback-updater/SKILL.md");
for (const requiredText of [
  "Update StaffAny Help Center article drafts",
  "original_article_html",
  "Intercom-ready HTML, not Markdown",
  "Apply validator `Required Changes` in priority order",
  "Improve model fit",
  "Updated Help Article:",
  "Changes Applied:",
  "Remaining Needs Check:",
  "Re-run help-article-validator before marking ready.",
]) {
  if (!helpArticleUpdaterSkillText.includes(requiredText)) fail(`help-article-feedback-updater/SKILL.md missing required text: ${requiredText}`);
}

const liveProfileSyncText = textOf("runtime/sync-live-profile.sh");
for (const requiredText of [
  "PROFILE_DIR/source/launchbot",
  "PROFILE_DIR/skills",
  "launchbot-sync-skill-to-repo.sh",
  "launchbot-apply-skill-sync.sh",
  "product-marketing-launch-workflow",
  "launch-priority-identifier",
  "customer-support-release-notes-generator",
  "customer-support-release-notes-validator",
  "customer-support-release-notes-feedback-updater",
  "staffany-indonesia-payroll-tax-grimoire",
]) {
  if (!liveProfileSyncText.includes(requiredText)) fail(`sync-live-profile.sh missing required text: ${requiredText}`);
}

const liveProfileAuditText = textOf("runtime/audit-live-profile.sh");
for (const requiredText of [
  "profile-skill-missing",
  "source-skill-missing",
  "profile-drift:skill-sync-script",
  "profile-drift:skill-sync-apply-script",
  "product-marketing-launch-workflow",
  "launch-priority-identifier",
  "customer-support-release-notes-generator",
  "customer-support-release-notes-validator",
  "customer-support-release-notes-feedback-updater",
]) {
  if (!liveProfileAuditText.includes(requiredText)) fail(`audit-live-profile.sh missing required text: ${requiredText}`);
}

const liveHealthText = textOf("runtime/check-health.sh");
for (const requiredText of [
  "profile-skill:",
  "source-skill:",
  "product-marketing-launch-workflow",
  "launch-priority-identifier",
  "customer-support-release-notes-generator",
  "customer-support-release-notes-validator",
  "customer-support-release-notes-feedback-updater",
]) {
  if (!liveHealthText.includes(requiredText)) fail(`check-health.sh missing required text: ${requiredText}`);
}

const csReleaseNotesValidatorSkillText = textOf("skills/customer-support-release-notes-validator/SKILL.md");
for (const requiredText of [
  "name: release-notes-validator",
  "Validate StaffAny release notes for Sales, PS, CS, and Product",
  "Evidence-Based Reasoning",
  "Confidence Score: <0-100>",
  "Evidence grounding: `0-30`",
  "UI/UX delta clarity: `0-25`",
  "Enablement usefulness: `0-20`",
  "Screenshot relevance",
  "More than 2 screenshots is a revision issue",
  "It must not explain how the change helps CS, support agents, triage, or internal teams.",
  "Set decision to `revise` when `How this helps users` contains CS/support/internal-team value",
  "Next Skill: <none | release-notes-feedback-updater>",
]) {
  if (!csReleaseNotesValidatorSkillText.includes(requiredText)) fail(`customer-support-release-notes-validator/SKILL.md missing required text: ${requiredText}`);
}

const csReleaseNotesUpdaterSkillText = textOf("skills/customer-support-release-notes-feedback-updater/SKILL.md");
for (const requiredText of [
  "name: release-notes-feedback-updater",
  "Update StaffAny release notes for Sales, PS, CS, and Product",
  "Apply validator `Required Changes` in priority order",
  "Remove CS, support-agent, triage, or internal-team explanations from that section.",
  "Preserve only 1-2 contextually correct screenshots",
  "Updated Release Notes:",
  "Changes Applied:",
  "Remaining Needs Check:",
  "Re-run release-notes-validator before marking ready.",
]) {
  if (!csReleaseNotesUpdaterSkillText.includes(requiredText)) fail(`customer-support-release-notes-feedback-updater/SKILL.md missing required text: ${requiredText}`);
}

const mcpText = existsSync(join(appRoot, "runtime", "mcp", "launchbot_ker_server.py"))
  ? readFileSync(join(appRoot, "runtime", "mcp", "launchbot_ker_server.py"), "utf8")
  : "";
for (const requiredText of [
  "SLACK_BOT_TOKEN",
  "JIRA_BASE_URL",
  "JIRA_EMAIL",
  "JIRA_API_TOKEN",
  "conversations.replies",
  "/rest/api/3/search/jql",
  "will_mutate_jira",
  "will_post_message",
  "transcript_persisted",
]) {
  if (!mcpText.includes(requiredText)) fail(`launchbot_ker_server.py missing required text: ${requiredText}`);
}

for (const forbiddenText of ["chat.postMessage", "transitionIssue", "/comment", "/transitions"]) {
  if (mcpText.includes(forbiddenText)) fail(`launchbot_ker_server.py must not contain forbidden mutation surface: ${forbiddenText}`);
}

const ifiMcpText = textOf("runtime/mcp/launchbot_ifi_server.py");
for (const requiredText of [
  "HUBSPOT_ACCESS_TOKEN",
  "HUBSPOT_PRIVATE_APP_TOKEN",
  "JIRA_IFI_HUBSPOT_COMPANY_ID_FIELD_ID",
  "customfield_10881",
  "HubSpot Company ID",
  "preview_ifi_feature_request_tracking",
  "create_or_update_ifi_feature_request_tracking",
  "preview_ifi_feature_request_from_bd_note",
  "create_or_update_ifi_feature_request_from_bd_note",
  "confirm IFI",
  "/rest/api/3/search/jql",
  "/rest/api/3/issue",
  "/rest/api/3/issueLink",
  "willPostMessage",
  "COMPANY_CONFIRMATION_GUIDANCE",
]) {
  if (!ifiMcpText.includes(requiredText)) fail(`launchbot_ifi_server.py missing required text: ${requiredText}`);
}
for (const forbiddenText of ["chat.postMessage", "SLACK_USER_TOKEN"]) {
  if (ifiMcpText.includes(forbiddenText)) fail(`launchbot_ifi_server.py must not contain forbidden mutation surface: ${forbiddenText}`);
}

const productCommitmentMcpText = textOf("runtime/mcp/launchbot_product_commitment_server.py");
for (const requiredText of [
  "SLACK_BOT_TOKEN",
  "JIRA_BASE_URL",
  "JIRA_EMAIL",
  "JIRA_API_TOKEN",
  "conversations.replies",
  "/rest/api/3/search/jql",
  "check_product_commitment_from_slack_thread",
  "LAUNCHBOT_PRODUCT_COMMITMENT_ALLOWED_CHANNEL_IDS",
  "LAUNCHBOT_PRODUCT_COMMITMENT_FIELD_IDS",
  "fixVersions",
  "will_mutate_jira",
  "will_post_message",
  "transcript_persisted",
  "will_create_intake",
  "will_estimate_timeline",
]) {
  if (!productCommitmentMcpText.includes(requiredText)) fail(`launchbot_product_commitment_server.py missing required text: ${requiredText}`);
}
for (const forbiddenText of ["chat.postMessage", "transitionIssue", "/comment", "/transitions", "/rest/api/3/issue?notifyUsers=false", "method=\"PUT\"", "method='PUT'", "DELETE"]) {
  if (productCommitmentMcpText.includes(forbiddenText)) fail(`launchbot_product_commitment_server.py must not contain forbidden mutation surface: ${forbiddenText}`);
}

const featureIntakeMcpText = textOf("runtime/mcp/launchbot_feature_intake_server.py");
for (const requiredText of [
  "launchbot_feature_intake_core",
  "preview_feature_intake_from_slack_thread",
  "create_feature_intake_from_slack_thread",
  "CONFIRMATION_PHRASES",
  "create intake",
]) {
  if (!featureIntakeMcpText.includes(requiredText)) fail(`launchbot_feature_intake_server.py missing required text: ${requiredText}`);
}
for (const forbiddenText of ["chat.postMessage", "transitionIssue", "/comment", "/transitions", "DELETE"]) {
  if (featureIntakeMcpText.includes(forbiddenText)) fail(`launchbot_feature_intake_server.py must not contain forbidden mutation surface: ${forbiddenText}`);
}

const featureIntakeCoreText = textOf("runtime/mcp/launchbot_feature_intake_core.py");
for (const requiredText of [
  "SLACK_BOT_TOKEN",
  "JIRA_BASE_URL",
  "JIRA_EMAIL",
  "JIRA_API_TOKEN",
  "conversations.replies",
  "/rest/api/3/search/jql",
  "/rest/api/3/issue?notifyUsers=false",
  "preview_feature_intake_from_slack_thread",
  "create_feature_intake_from_slack_thread",
  "CONFIRMATION_PHRASES",
  "create intake",
  "customfield_10080",
  "will_mutate_jira",
  "will_post_message",
  "transcript_persisted",
]) {
  if (!featureIntakeCoreText.includes(requiredText)) fail(`launchbot_feature_intake_core.py missing required text: ${requiredText}`);
}
for (const forbiddenText of ["chat.postMessage", "transitionIssue", "/comment", "/transitions", "DELETE"]) {
  if (featureIntakeCoreText.includes(forbiddenText)) fail(`launchbot_feature_intake_core.py must not contain forbidden mutation surface: ${forbiddenText}`);
}

const featureIntakeMonitorText = textOf("runtime/monitor-feature-intake.py");
for (const requiredText of [
  "conversations.history",
  "conversations.replies",
  "chat.postMessage",
  "LAUNCHBOT_FEATURE_INTAKE_MONITOR_CHANNEL_IDS",
  "LAUNCHBOT_FEATURE_INTAKE_MONITOR_STATE_PATH",
  "LAUNCHBOT_FEATURE_INTAKE_MONITOR_MAX_MESSAGES_PER_RUN",
  "LAUNCHBOT_FEATURE_INTAKE_MONITOR_OVERLAP_SECONDS",
  "LAUNCHBOT_FEATURE_INTAKE_APPROVER_USER_IDS",
  "Launchbot automation: Potential KER intake detected.",
  "create intake",
  "create ker intake",
  "will_post_message",
  "transcript_persisted",
]) {
  if (!featureIntakeMonitorText.includes(requiredText)) fail(`monitor-feature-intake.py missing required text: ${requiredText}`);
}

const supportWatchMcpText = textOf("runtime/mcp/launchbot_support_watch_server.py");
for (const requiredText of [
  "launchbot_support_watch",
  "preview_weekly_support_watch_report",
  "Read-only Launchbot support-watch preview adapter",
  "never sends Slack messages",
  "creates Jira/Linear tickets",
  "tags engineers",
  "persists raw support transcripts",
]) {
  if (!supportWatchMcpText.includes(requiredText)) fail(`launchbot_support_watch_server.py missing required text: ${requiredText}`);
}
for (const forbiddenText of ["chat.postMessage", "method=\"PUT\"", "method='PUT'", "DELETE"]) {
  if (supportWatchMcpText.includes(forbiddenText)) fail(`launchbot_support_watch_server.py must not contain forbidden mutation surface: ${forbiddenText}`);
}

const supportWatchCoreText = textOf("runtime/mcp/launchbot_support_watch_core.py");
for (const requiredText of [
  "LAUNCHBOT_SUPPORT_WATCH_SOURCE",
  "LAUNCHBOT_SUPPORT_WATCH_INTERCOM_PROJECT",
  "LAUNCHBOT_SUPPORT_WATCH_INTERCOM_DATASET",
  "LAUNCHBOT_SUPPORT_WATCH_ANALYTICS_DATASET",
  "LAUNCHBOT_SUPPORT_WATCH_INCLUDE_WHATSAPP",
  "LAUNCHBOT_SUPPORT_WATCH_WHATSAPP_VIEW",
  "build_intercom_conversations_query",
  "conversation_parts",
  "support_watch_whatsapp_ticket_logs",
  "build_intercom_counts_query",
  "build_whatsapp_counts_query",
  "candidate_score",
  "total_matching_rows",
  "source_status",
  "LAUNCHBOT_SUPPORT_WATCH_BQ_TIMEOUT_SECONDS",
  "start_new_session=True",
  "os.killpg",
  "conversations.history",
  "public_channel",
  "/rest/api/3/search/jql",
  "LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_IDS",
  "LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_NAMES",
  "LAUNCHBOT_SUPPORT_WATCH_EDT_JQL",
  "LAUNCHBOT_PANTHEON_REPO_DIR",
  "preview_weekly_support_watch_report",
  "will_post_message",
  "will_create_ticket",
  "will_tag_engineer",
  "raw_transcript_persisted",
  "Launchbot automation:",
  "all-bugs-production",
]) {
  if (!supportWatchCoreText.includes(requiredText)) fail(`launchbot_support_watch_core.py missing required text: ${requiredText}`);
}
for (const forbiddenText of ["chat.postMessage", "/tickets/search", "Intercom-Version", "transitionIssue", "/comment", "/transitions", "/rest/api/3/issue?notifyUsers=false", "method=\"PUT\"", "method='PUT'", "DELETE"]) {
  if (supportWatchCoreText.includes(forbiddenText)) fail(`launchbot_support_watch_core.py must not contain forbidden mutation surface: ${forbiddenText}`);
}
if (supportWatchCoreText.includes("public_channel,private_channel")) {
  fail("launchbot_support_watch_core.py must not request private-channel scope for public channel resolution");
}

const supportWatchWhatsappRefreshSql = textOf("runtime/support-watch-whatsapp-refresh.sql");
for (const requiredText of [
  "CREATE OR REPLACE TABLE `staffany-warehouse.analytics.support_watch_whatsapp_ticket_logs`",
  "PARTITION BY reported_date",
  "FROM `staffany-warehouse.gsheets.cs_tickets_logs_all_view`",
]) {
  if (!supportWatchWhatsappRefreshSql.includes(requiredText)) fail(`support-watch-whatsapp-refresh.sql missing required text: ${requiredText}`);
}

const supportWatchMonitorText = textOf("runtime/monitor-support-watch.py");
for (const requiredText of [
  "chat.postMessage",
  "LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME",
  "LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_ID",
  "LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_IDS",
  "LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_NAMES",
  "LAUNCHBOT_SUPPORT_WATCH_EDT_JQL",
  "LAUNCHBOT_SUPPORT_WATCH_STATE_PATH",
  "LAUNCHBOT_SUPPORT_WATCH_LOOKBACK_DAYS",
  "LAUNCHBOT_SUPPORT_WATCH_MAX_TICKETS",
  "source_status",
  "all-bugs-production",
  "0 1 * * 4",
  "Launchbot automation:",
  "no-new-findings",
  "duplicate-report-signature",
  "will_post_message",
  "will_create_ticket",
  "will_tag_engineer",
  "transcript_persisted",
]) {
  if (!supportWatchMonitorText.includes(requiredText)) fail(`monitor-support-watch.py missing required text: ${requiredText}`);
}

const helpArticleMcpText = textOf("runtime/mcp/launchbot_help_article_server.py");
for (const requiredText of [
  "LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN",
  "preview_help_article_video_update",
  "create_help_article_video_update_draft",
  "normalize_loom_embed_url",
  "replace_next_video_after_anchor",
  "LOOM_IFRAME_RE",
  "PUT",
  "\"state\": \"draft\"",
  "will_publish",
  "will_mutate_tags_or_collections",
]) {
  if (!helpArticleMcpText.includes(requiredText)) fail(`launchbot_help_article_server.py missing required text: ${requiredText}`);
}
for (const forbiddenText of ["\"state\": \"published\"", "method=\"DELETE\"", "method='DELETE'"]) {
  if (helpArticleMcpText.includes(forbiddenText)) fail(`launchbot_help_article_server.py must not contain forbidden mutation surface: ${forbiddenText}`);
}

const healthText = textOf("runtime/check-health.sh");
for (const requiredText of [
  "pantheon:checkout-missing",
  "pantheon:remote-unexpected",
  "pantheon:ssh-access-denied",
  "git ls-remote",
  "LAUNCHBOT_PANTHEON_SSH_KEY",
  "pantheon:status-stale",
  "platforms:slack:gateway-restart-notification-not-disabled",
  "slack:allowed-channels-static-not-empty",
  "MCP_TEST_ATTEMPTS",
  "MCP_TEST_TIMEOUT_SECONDS",
  'MCP_TEST_TIMEOUT_SECONDS="${MCP_TEST_TIMEOUT_SECONDS:-60}"',
  'timeout "${MCP_TEST_TIMEOUT_SECONDS}s" "$hermes_python" "$hermes_bin"',
  "run_hermes",
  "LAUNCHBOT_PANTHEON_REPO_DIR",
  "mcp:launchbot_ifi",
  "mcp:launchbot_help_article",
  "mcp:launchbot_product_commitment",
  "mcp:launchbot_feature_intake",
  "preview_ifi_feature_request_from_bd_note",
  "create_or_update_ifi_feature_request_from_bd_note",
  "HUBSPOT_ACCESS_TOKEN",
  "JIRA_IFI_HUBSPOT_COMPANY_ID_FIELD_ID",
  "EXPECT_KER_ALLOWED_CHANNELS",
  "mcp:launchbot_ker:default-channel-missing",
  "mcp:launchbot_ker:env-channel-missing",
  "mcp:launchbot_ker:process-env-channel-missing",
  "LAUNCHBOT_PRODUCT_COMMITMENT_ALLOWED_CHANNEL_IDS",
  "mcp:launchbot_product_commitment:default-channel-missing",
  "mcp:launchbot_product_commitment:env-channel-missing",
  "feature-intake-monitor:script-missing",
  "feature-intake-monitor:py-compile-failed",
  "feature-intake-monitor:raw-transcript-persistence-not-disabled",
  "LAUNCHBOT_FEATURE_INTAKE_MONITOR_CHANNEL_IDS",
  "launchbot_feature_intake_core",
  "mcp:launchbot_support_watch",
  "support-watch-monitor:script-missing",
  "support-watch-monitor:py-compile-failed",
  "support-watch-monitor:raw-transcript-persistence-not-disabled",
  "support-watch-monitor:bq-timeout-env-unexpected",
  "support-watch-monitor:bq-timeout-unexpected",
  "support-watch-monitor:whatsapp-refresh-transfer-name-unexpected",
  "support-watch-monitor:whatsapp-refresh-schedule-unexpected",
  "support-watch-monitor:whatsapp-max-staleness-unexpected",
  "support-watch:whatsapp-table-metadata-missing",
  "support-watch:whatsapp-table-stale",
  "support-watch:whatsapp-runtime-source-drive-backed",
  "__TABLES__",
  "timeout=120",
  "LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME",
  "LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_ID",
  "LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_IDS",
  "LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_NAMES",
  "LAUNCHBOT_SUPPORT_WATCH_EDT_JQL",
  "LAUNCHBOT_SUPPORT_WATCH_STATE_PATH",
  "launchbot_support_watch_core",
  "LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN",
  "help-article-video-registry",
]) {
  if (!healthText.includes(requiredText)) fail(`check-health.sh missing required Pantheon health text: ${requiredText}`);
}
for (const forbiddenText of ["EXPECT_ALLOWED_CHANNELS", "slack:allowed-channel-missing"]) {
  if (healthText.includes(forbiddenText)) {
    fail(`check-health.sh must not enforce static normal-reply Slack allowlists: ${forbiddenText}`);
  }
}

const auditText = textOf("runtime/audit-live-profile.sh");
for (const requiredText of [
  "cron:health-check-missing",
  "cron:feature-intake-monitor-missing",
  "cron:support-watch-missing",
  "bigquery:whatsapp-refresh-transfer-missing",
  "cron:pantheon-repo-update-missing",
  "cron:pantheon-repo-update-present-without-github-ssh",
  "LAUNCHBOT_PANTHEON_SSH_KEY",
  "GIT_SSH_COMMAND",
  "GIT_TERMINAL_PROMPT=0 git ls-remote",
  "profile-drift:help-article-mcp",
  "profile-drift:ifi-mcp",
  "profile-drift:product-commitment-mcp",
  "profile-drift:feature-intake-mcp",
  "profile-drift:feature-intake-core",
  "profile-drift:feature-intake-monitor-script",
  "profile-drift:support-watch-mcp",
  "profile-drift:support-watch-core",
  "profile-drift:support-watch-monitor-script",
  "profile-drift:support-watch-whatsapp-refresh-sql",
  "profile-drift:help-article-video-registry",
  "sessions:stale-system-prompt",
  "sessions:active-session-json-missing",
]) {
  if (!auditText.includes(requiredText)) fail(`audit-live-profile.sh missing required cron/access text: ${requiredText}`);
}

const pantheonUpdateText = textOf("runtime/update-pantheon-repo.sh");
for (const requiredText of [
  "git ls-remote",
  "git clone --branch",
  "pull --ff-only",
  "pantheon:updated",
  "pantheon:ssh-access-denied",
  "GIT_TERMINAL_PROMPT=0",
  "LAUNCHBOT_PANTHEON_REPO_URL",
  "LAUNCHBOT_PANTHEON_SSH_KEY",
  "GIT_SSH_COMMAND",
  "pantheon-repo-status.json",
]) {
  if (!pantheonUpdateText.includes(requiredText)) fail(`update-pantheon-repo.sh missing required text: ${requiredText}`);
}

const skillText = textOf("skills/help-article-generator/SKILL.md");
for (const requiredText of [
  "Handoff-upgraded rules in this Launchbot skill override the older Grimoire help-article skill",
  "show it as Intercom-ready HTML, not Markdown",
  "visible LaunchBot output must show the help article as HTML",
  "HTML display rules",
  "Do not show Markdown syntax",
  "one combined management article",
  "Managing Brands",
  "Managing Perks",
  "Do not use raw HTML",
  "Do not place any visible divider lines",
  "Do not include the internal appendix",
  "cached Intercom article-shape profile",
  "needs-intake",
  "missing high-impact questions",
  "launchbot-with-secrets.mjs",
  "help-article:shape-refresh",
  "intercom:inventory",
  "help-article:plan",
  "help-article:format-check",
  "intercom:affected",
  "intercom:stage-update",
  "help-article:pantheon-scan",
  "help-article:evidence-check",
  "Pantheon evidence",
  "Public publishing stays manual in Intercom",
  "A brand is the business profile",
  "A perk sits under a brand",
  "For ClubAny / Club Blue content, set Product to `StaffAny`",
  "numbered steps from `1` for each subsection",
  "Update -> Video-only update",
  "references/video-placement-registry.json",
  "will_publish: false",
  "state: \"draft\"",
  "registry-only and draft-only",
]) {
  if (!skillText.includes(requiredText)) fail(`Help article skill missing required text: ${requiredText}`);
}
if (/^<div|^<br|^\s*<[^>]+style=|^\s*<[^>]+align=/m.test(skillText)) {
  fail("Help article skill must not include raw HTML formatting examples");
}

const screenshotTroubleshooterText = textOf("skills/help-article-screenshot-troubleshooter/SKILL.md");
for (const requiredText of [
  "Troubleshoot Launchbot help article screenshot capture",
  "Playwright",
  "LAUNCHBOT_STAGING_URL",
  "LAUNCHBOT_STAGING_EMAIL",
  "LAUNCHBOT_STAGING_PASSWORD",
  "help-article-staging-auth-state.mjs",
  "runtime-only storage state",
  "Never ask users to paste passwords",
  "Never save Playwright storage-state in this repo",
  "keep screenshot placeholders",
  "Do not insert screenshots unless redaction is verified",
]) {
  if (!screenshotTroubleshooterText.includes(requiredText)) fail(`Screenshot troubleshooter skill missing required text: ${requiredText}`);
}

const stagingAuthText = textOf("runtime/help-article-staging-auth-state.mjs");
for (const requiredText of [
  "LAUNCHBOT_STAGING_URL",
  "STAFFANY_STAGING_URL",
  "LAUNCHBOT_STAGING_EMAIL",
  "LAUNCHBOT_STAGING_PASSWORD",
  "values_printed: false",
  "Refusing to write staging storage-state",
  "Playwright is not installed",
  "Staging target host is not allowlisted",
]) {
  if (!stagingAuthText.includes(requiredText)) fail(`Staging auth helper missing required text: ${requiredText}`);
}
if (/console\.log\(.*password|stdout\.write\(.*password|console\.log\(.*email|stdout\.write\(.*email/.test(stagingAuthText)) {
  fail("Staging auth helper must not print staging credential values");
}

const supportWatchSkillText = textOf("skills/weekly-support-watch/SKILL.md");
for (const requiredText of [
  "Launchbot Weekly Support Watch",
  "0 1 * * 4",
  "all-bugs-production",
  "team-cs-eng-duty",
  "preview_weekly_support_watch_report",
  "runtime/monitor-support-watch.py",
  "LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME",
  "LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_ID",
  "LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_IDS",
  "LAUNCHBOT_SUPPORT_WATCH_EDT_JQL",
  "problem-keyword scoring",
  "Do not create Linear/Jira tickets",
  "Launchbot automation:",
  "No new findings",
]) {
  if (!supportWatchSkillText.includes(requiredText)) fail(`Weekly support-watch skill missing required text: ${requiredText}`);
}

const indonesiaTaxSkillText = textOf("skills/staffany-indonesia-payroll-tax-grimoire/SKILL.md");
for (const requiredText of [
  "StaffAny Indonesia Payroll Tax Grimoire",
  "skills/indonesia-payroll-tax-advisor/SKILL.md",
  "skills/pph21-settings-explainer/SKILL.md",
  "Direct answer",
  "Regulatory basis",
  "StaffAny system behavior",
  "Gap / risk / not validated",
  "Sources checked",
  "Confidence",
  "Formulir 1721-A1 / BPA1",
  "Browse official sources for current law, reporting forms, rates, filing processes, and Coretax/DJP template changes.",
  "Protect sensitive payroll data",
]) {
  if (!indonesiaTaxSkillText.includes(requiredText)) {
    fail(`Indonesia payroll tax grimoire missing required text: ${requiredText}`);
  }
}
const indonesiaTaxReportingText = textOf("skills/staffany-indonesia-payroll-tax-grimoire/skills/indonesia-payroll-tax-advisor/references/reporting.md");
for (const requiredText of [
  "SPT Masa PPh 21/26",
  "e-Bupot 21/26",
  "BPA1",
  "Coretax can generate/download 1721-A1",
  "StaffAny Behavior Map",
]) {
  if (!indonesiaTaxReportingText.includes(requiredText)) {
    fail(`Indonesia payroll tax reporting reference missing required text: ${requiredText}`);
  }
}
const indonesiaTaxUpdaterText = textOf("skills/staffany-indonesia-payroll-tax-grimoire/skills/indonesia-tax-knowledge-updater/SKILL.md");
for (const requiredText of [
  "Indonesia Tax Knowledge Updater",
  "Verify current regulator facts against official sources before writing them into the knowledge bank.",
  "Record source title, publisher, URL, effective period, last checked date, topics, status, confidence, and notes.",
  "validate_knowledge_bank.rb",
  "Required Source Fields",
]) {
  if (!indonesiaTaxUpdaterText.includes(requiredText)) {
    fail(`Indonesia tax knowledge updater missing required text: ${requiredText}`);
  }
}

const launchbotHealthText = textOf("runtime/check-health.sh");
for (const requiredText of [
  "slack:scope-missing:",
  "channels:read",
  "channels:history",
  "channels:join",
  "chat:write",
  "conversations.info",
  "conversations.join",
  "support-watch:output-channel-unresolved",
  "support-watch:output-channel-join-failed",
  "support-watch:output-channel-not-member",
  "support-watch:dedupe-channel-join-failed",
  "support-watch:dedupe-channel-unresolved",
]) {
  if (!launchbotHealthText.includes(requiredText)) fail(`Launchbot health check missing support-watch Slack validation text: ${requiredText}`);
}

const skeletonText = textOf("skills/help-article-generator/references/help-article-skeleton.md");
if (!skeletonText.includes("**This guide will cover how to:**")) {
  fail("Help article skeleton missing guide outline line");
}
if (!/^1\. \[Main section\]/m.test(skeletonText)) {
  fail("Help article skeleton outline must use numbered items");
}
if (/^---$/m.test(skeletonText)) {
  fail("Help article skeleton must not use text divider lines");
}
if (/<div|<br|align=|style=/.test(skeletonText)) {
  fail("Help article skeleton must not include raw HTML formatting examples");
}

const videoRegistryPath = join(appRoot, "skills", "help-article-generator", "references", "video-placement-registry.json");
const videoRegistry = existsSync(videoRegistryPath) ? sharedReadJson(videoRegistryPath, fail) : null;
if (!videoRegistry) {
  fail("Missing video placement registry");
} else {
  if (videoRegistry.version !== 1) fail("Video placement registry must be version 1");
  const articles = Array.isArray(videoRegistry.articles) ? videoRegistry.articles : [];
  const articleKeys = new Set(articles.map((article) => article.article_key));
  for (const key of ["web-app-timesheet", "run-payroll", "general-settings"]) {
    if (!articleKeys.has(key)) fail(`Video placement registry missing fixture article: ${key}`);
  }
  for (const article of articles) {
    for (const key of ["article_key", "locale", "title", "public_url", "intercom_article_id", "slots"]) {
      if (!article[key]) fail(`Video placement registry article missing field: ${key}`);
    }
    if (article.locale !== "en") fail(`Video placement registry V1 must be English-only: ${article.article_key}`);
    for (const slot of article.slots || []) {
      for (const key of ["slot_id", "purpose", "anchor_text", "provider", "replace_policy"]) {
        if (!slot[key]) fail(`Video placement registry slot missing field: ${key}`);
      }
      if (slot.provider !== "loom") fail(`Video placement registry slot must be Loom-only: ${slot.slot_id}`);
      if (slot.replace_policy !== "replace_next_video_after_anchor") {
        fail(`Video placement registry slot has unsupported policy: ${slot.slot_id}`);
      }
    }
  }
}

const workflowText = textOf("runtime/launch-workflow.md");
for (const requiredText of [
  "Slack Capability Questions",
  "what can u do",
  "code-grounded English and Indonesian help article drafts shown as Intercom-ready HTML",
  "Visible help article previews shown in Slack or chat must be Intercom-ready HTML, not Markdown",
  "Do not list generic assistant categories",
  "source code under `vk-super-productivity/launch-superpower-bot` is not present",
  "runtime/launchbot_e2e.py",
  "Intercom draft articles",
  "Pantheon Evidence, Intercom Format Profile, And Pre-Publish Gates",
  "Midas/Karpathy-style ingest",
  "help-article:shape-refresh",
  "help-article:shape-ingest",
  "intercom:inventory",
  "help-article:plan",
  "intercom:format:pull",
  "help-article:format-check",
  "intercom:affected",
  "intercom:stage-update",
  "help-article:pantheon-scan",
  "help-article:evidence-check",
  "LAUNCH_INTERCOM_SHAPE_FAMILIES",
  "intercom-article-inventory.json",
  "cached inventory for affected article lookup",
  "live Intercom wins",
  "pre-stage target-article stale check",
  "Public publishing stays manual in Intercom",
  "normal create or text-update article work, create both English (`en`) and Indonesian (`id`) article records",
  "Run Pantheon evidence and Intercom format gates separately for `en` and `id`",
  "bot-owned posting credentials",
  "@Launch Bot",
  "U0ASVD79UT1",
  "B0ATPPEGBCH",
  "message.channels",
  "channels:history",
  "#launch-bot-testing",
  "#all-product-questions",
  "C01RZ7SHC8K",
  "light cowboy voice",
  "Do not commit token values",
  "PMM workflow launch derivatives are scoped to help article work items and concise release notes with validator checkpoints only",
  "include only 1-2 contextually correct screenshots",
  "Pantheon checkout",
  "apps/kraken",
  "apps/gryphon",
  "apps/pixie",
  "IFI Feature Request Tracking",
  "preview_ifi_feature_request_tracking",
  "preview_ifi_feature_request_from_bd_note",
  "customfield_10881",
  "confirm IFI",
  "Video-only Help Article Update",
  "video-placement-registry.json",
  "preview_help_article_video_update",
  "create_help_article_video_update_draft",
  "replace_next_video_after_anchor",
  "raw `.mp4`, Slack file URLs",
  "Weekly Support Watch",
  "preview_weekly_support_watch_report",
  "runtime/monitor-support-watch.py",
  "0 1 * * 4",
  "Thursday 09:00 SGT",
  "LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME",
  "LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_IDS",
  "Do not create Linear/Jira tickets",
]) {
  if (!workflowText.includes(requiredText)) fail(`Launch workflow doc missing required text: ${requiredText}`);
}

const e2eRunnerText = textOf("runtime/launchbot_e2e.py");
for (const requiredText of [
  "LAUNCH_STEP2_SLACK_BOT_TOKEN",
  "LAUNCH_STEP3_SLACK_BOT_TOKEN",
  "LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN",
  "LAUNCH_STEP3_SLACK_AUTHORIZED_REVIEWER_IDS",
  "GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE",
  "C0B32M34J3W",
  "launch-bot-testing",
  "EXPECTED_SLACK_BOT_USER_ID",
  "EXPECTED_SLACK_BOT_ID",
  "slack:wrong-bot-profile",
  "Launchbot automation: Howdy, partner. Review draft is saddled up for approval",
  "Approved review is now drafted in Intercom",
  "--approval-only",
  "approval_user_ids",
  "approval:no-authorized-reviewer",
  "fit to ride into Intercom draft",
  "\"state\": \"draft\"",
  "\"parent_type\": \"collection\"",
  "conversations.join",
  "conversations.history",
  "thread_ts",
  "intercom_direct_url",
  "LAUNCH_STEP3_INTERCOM_APP_ID",
  "omit_top_heading=True",
  "run_intercom_format_gate",
  "run_help_article_plan",
  "run_pantheon_evidence_gate",
  "help-article:plan",
  "article_plan_status",
  "pantheon_evidence_gate",
  "help-article:format-check",
  "help-article:evidence-check",
  "NODE_BINARY",
  "format_gate_status",
]) {
  if (!e2eRunnerText.includes(requiredText)) fail(`Launch workflow runner missing required text: ${requiredText}`);
}

const intercomGateText = textOf("runtime/intercom-format-gate.mjs");
for (const requiredText of [
  "intercom:format:pull",
  "intercom:format:profile",
  "intercom:inventory",
  "help-article:shape-refresh",
  "help-article:shape-ingest",
  "help-article:plan",
  "help-article:format-check",
  "help-article:pantheon-scan",
  "help-article:evidence-check",
  "intercom:affected",
  "intercom:stage-update",
  "LAUNCH_PANTHEON_REPO",
  "DEFAULT_ARTICLE_SHAPE_PROFILE_PATH",
  "DEFAULT_ARTICLE_INVENTORY_PATH",
  "buildArticleInventory",
  "buildArticlePlanningProfile",
  "planHelpArticles",
  "evaluateHelpArticleIntake",
  "needs-intake",
  "--surface",
  "--audience",
  "--outcome",
  "checkArticleShapeFreshness",
  "LAUNCH_INTERCOM_SHAPE_FAMILIES",
  "LAUNCH_INTERCOM_INVENTORY_STATE",
  "affected_articles_from_cached_inventory",
  "pre_stage_stale_check",
  "needs-refresh",
  "DEFAULT_PANTHEON_REPO",
  "scanPantheonEvidence",
  "checkPantheonEvidence",
  "dirty_pantheon_repo",
  "ambiguous_pantheon_app",
  "unsupported_product_behavior_claim",
  "internal_pantheon_app_name_leakage",
  "LAUNCH_INTERCOM_HELP_CENTER_ID",
  "LAUNCH_INTERCOM_FORMAT_SAMPLE_IDS",
  "LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN",
  "INTERCOM_ACCESS_TOKEN",
  "read_stage_only",
  "draft_only",
  "missing_audience_metadata",
  "repeated_title_in_body",
  "raw_html_or_markdown_leakage",
  "text_divider_lines",
  "internal_appendix",
  "bad_list_numbering",
  "missing_faq",
  "missing_numbered_outline",
  "state: \"draft\"",
  "apiRequest(\"GET\", \"/articles/search\"",
  "apiRequest(\"GET\", `/articles/${encodeURIComponent(id)}`",
]) {
  if (!intercomGateText.includes(requiredText)) fail(`Intercom format gate missing required text: ${requiredText}`);
}
if (/apiRequest\("PUT"|method:\s*"PUT"/.test(intercomGateText)) {
  fail("Intercom format gate must not contain publish/update write paths");
}

const secretWrapperPath = join(repoRoot, "scripts/launchbot-with-secrets.mjs");
if (!existsSync(secretWrapperPath)) fail("Missing LaunchBot Secret Manager wrapper");
const secretWrapperText = existsSync(secretWrapperPath) ? readFileSync(secretWrapperPath, "utf8") : "";
for (const requiredText of [
  "launchbot-step3-intercom-access-token",
  "launchbot-staging-url",
  "launchbot-staging-email",
  "launchbot-staging-password",
  "LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN",
  "INTERCOM_ACCESS_TOKEN",
  "LAUNCHBOT_STAGING_URL",
  "LAUNCHBOT_STAGING_EMAIL",
  "LAUNCHBOT_STAGING_PASSWORD",
  "staffany-warehouse",
  "values_printed",
  "gcloud",
  "secrets",
  "versions",
  "access",
  "latest",
]) {
  if (!secretWrapperText.includes(requiredText)) fail(`Secret Manager wrapper missing required text: ${requiredText}`);
}
if (/console\.log\(.*value|stdout\.write\(.*value/.test(secretWrapperText)) {
  fail("Secret Manager wrapper must not print secret values");
}

const nodeTest = spawnSync(
  process.execPath,
  ["--test", join(appRoot, "runtime", "intercom-format-gate.test.mjs")],
  { encoding: "utf8" }
);
if (nodeTest.status !== 0) {
  fail(`Intercom format gate tests failed: ${(nodeTest.stderr || nodeTest.stdout || "").trim()}`);
}

const stagingAuthTest = spawnSync(
  process.execPath,
  ["--test", join(appRoot, "runtime", "help-article-staging-auth-state.test.mjs")],
  { encoding: "utf8" }
);
if (stagingAuthTest.status !== 0) {
  fail(`Staging auth helper tests failed: ${(stagingAuthTest.stderr || stagingAuthTest.stdout || "").trim()}`);
}

const pyCompile = spawnSync(
  "python3",
  [
    "-c",
    "from pathlib import Path; import sys; p=Path(sys.argv[1]); compile(p.read_text(encoding='utf-8'), str(p), 'exec')",
    join(appRoot, "runtime", "launchbot_e2e.py"),
  ],
  { encoding: "utf8" }
);
if (pyCompile.status !== 0) {
  fail(`Launch workflow runner Python syntax check failed: ${(pyCompile.stderr || pyCompile.stdout || "").trim()}`);
}

const sourceNotePath = join(repoRoot, "research/wiki/sources/launch-superpower-bot-handoff.md");
if (!existsSync(sourceNotePath)) fail("Missing maintained Launch Superpower handoff source note");
const intercomShapeSourceNotePath = join(repoRoot, "research/wiki/sources/staffany-intercom-help-article-shape.md");
if (!existsSync(intercomShapeSourceNotePath)) fail("Missing maintained Intercom help article shape source note");
const helpArticlePlanningSynthesisPath = join(repoRoot, "research/wiki/syntheses/help-article-planning-rules.md");
if (!existsSync(helpArticlePlanningSynthesisPath)) fail("Missing help article planning rules synthesis");

const regressionText = textOf("tests/launch-workflow-regression-cases.md");
for (const requiredText of [
  "#launch-bot-testing",
  "#all-product-questions",
  "C01RZ7SHC8K",
  "@Launch Bot",
  "U0ASVD79UT1",
  "B0ATPPEGBCH",
  "message.channels",
  "light cowboy voice",
  "help-article:shape-refresh",
  "help-article:plan",
  "needs-intake",
  "intake.questions",
  "article_shape_stale_check.status: needs-refresh",
  "Video-only Help Article Updates",
  "Feature Intake Channel Monitor",
  "Launchbot automation: Potential KER intake detected.",
  "create KER intake",
  "Weekly Support Watch",
  "#all-bugs-production",
  "#team-cs-eng-duty",
  "No new findings means no Slack post",
  "raw support transcripts",
  "IFI Feature Request Tracking",
  "preview_ifi_feature_request_tracking",
  "preview_ifi_feature_request_from_bd_note",
  "create_or_update_ifi_feature_request_tracking",
  "create_or_update_ifi_feature_request_from_bd_note",
  "Neon Group asked whether StaffAny can generate a native Citibank payroll bank file.",
  "25638156628",
  "customfield_10881",
  "confirm IFI",
  "raw Slack transcripts",
  "will_publish: false",
  "state: \"draft\"",
  "no registered slot match",
]) {
  if (!regressionText.includes(requiredText)) fail(`Launch workflow regression cases missing required text: ${requiredText}`);
}

const packageJson = existsSync(join(repoRoot, "package.json"))
  ? sharedReadJson(join(repoRoot, "package.json"), fail)
  : null;
if (packageJson) {
  const intercomRuntimeScripts = [
    "intercom:format:pull",
    "intercom:format:profile",
    "intercom:inventory",
    "help-article:shape-refresh",
    "help-article:shape-ingest",
    "help-article:plan",
    "help-article:format-check",
    "intercom:affected",
    "intercom:stage-update",
    "help-article:pantheon-scan",
    "help-article:evidence-check",
  ];
  for (const scriptName of intercomRuntimeScripts) {
    if (!packageJson.scripts?.[scriptName]?.includes("apps/launchbot/runtime/intercom-format-gate.mjs")) {
      fail(`package.json missing Launchbot script ${scriptName}`);
    }
  }
  if (!packageJson.scripts?.["launchbot:with-secrets"]?.includes("launchbot-with-secrets.mjs")) {
    fail("package.json missing script launchbot:with-secrets");
  }
}

const testRun = spawnSync("python3", ["-m", "unittest", "discover", "-s", join(appRoot, "runtime", "mcp"), "-p", "test_*.py"], {
  cwd: repoRoot,
  encoding: "utf8",
});
if (testRun.status !== 0) {
  fail(`Launchbot MCP unit tests failed:\n${testRun.stdout || ""}${testRun.stderr || ""}`);
}

const monitorTestRun = spawnSync("python3", ["-m", "unittest", join(appRoot, "runtime", "test_monitor_feature_intake.py")], {
  cwd: repoRoot,
  encoding: "utf8",
});
if (monitorTestRun.status !== 0) {
  fail(`Launchbot feature intake monitor tests failed:\n${monitorTestRun.stdout || ""}${monitorTestRun.stderr || ""}`);
}

const supportWatchMonitorTestRun = spawnSync("python3", ["-m", "unittest", join(appRoot, "runtime", "test_monitor_support_watch.py")], {
  cwd: repoRoot,
  encoding: "utf8",
});
if (supportWatchMonitorTestRun.status !== 0) {
  fail(`Launchbot support watch monitor tests failed:\n${supportWatchMonitorTestRun.stdout || ""}${supportWatchMonitorTestRun.stderr || ""}`);
}

const pantheonUpdateTestRun = spawnSync("python3", ["-m", "unittest", join(appRoot, "runtime", "test_update_pantheon_repo.py")], {
  cwd: repoRoot,
  encoding: "utf8",
});
if (pantheonUpdateTestRun.status !== 0) {
  fail(`Launchbot Pantheon update tests failed:\n${pantheonUpdateTestRun.stdout || ""}${pantheonUpdateTestRun.stderr || ""}`);
}

if (failures.length > 0) {
  console.error("Launchbot packet verification failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log("Launchbot packet verification passed.");
