import { existsSync, readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { join, resolve } from "node:path";
import {
  assertFile as sharedAssertFile,
  readJson as sharedReadJson,
  scanForSecretPatterns as sharedScanForSecretPatterns
} from "./lib/app-packet-verify.mjs";

const repoRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
const appRoot = join(repoRoot, "apps", "hermes-data-bot");
const manifestPath = join(appRoot, "app.manifest.json");
const packageJsonPath = join(repoRoot, "package.json");

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

function scanForSecretPatterns(relPath) {
  sharedScanForSecretPatterns(appRoot, relPath, fail);
}

function profileBlock(profilesText, profileName) {
  const marker = `  - name: ${profileName}`;
  const start = profilesText.indexOf(marker);
  if (start === -1) return "";
  const next = profilesText.indexOf("\n  - name:", start + marker.length);
  return profilesText.slice(start, next === -1 ? undefined : next);
}

if (!existsSync(manifestPath)) {
  fail("Missing apps/hermes-data-bot/app.manifest.json");
} else {
  const manifest = readJson(manifestPath);
  if (manifest) {
    if (manifest.profile_name !== "staffanydatabot") fail("Manifest profile_name must be staffanydatabot");
    if (manifest.secrets_copied !== false) fail("Manifest secrets_copied must be false");
    const paths = manifest.paths || {};
    for (const value of Object.values(paths)) {
      if (Array.isArray(value)) {
        for (const relPath of value) assertFile(relPath);
      } else {
        assertFile(value);
      }
    }
    const expectedTools = [
      "list_dataset_ids",
      "list_table_ids",
      "get_table_info",
      "execute_sql_readonly"
    ];
    const actualTools = manifest.mcp?.expected_tools || [];
    for (const tool of expectedTools) {
      if (!actualTools.includes(tool)) fail(`Manifest missing MCP tool: ${tool}`);
    }
    for (const tool of actualTools) {
      if (!expectedTools.includes(tool)) fail(`Manifest has unexpected MCP tool: ${tool}`);
    }
    const slackTools = manifest.slack_context_mcp?.expected_tools || [];
    for (const tool of ["get_current_slack_thread_context", "get_selected_slack_thread_context"]) {
      if (!slackTools.includes(tool)) fail(`Manifest missing Slack context MCP tool: ${tool}`);
    }
    if (manifest.slack_context_mcp?.read_only !== true) fail("Manifest Slack context MCP must be read_only");
    if (manifest.slack_context_mcp?.uses_user_token !== false) fail("Manifest Slack context MCP must not use user token");
    if (manifest.slack_context_mcp?.uses_slack_connector !== false) fail("Manifest Slack context MCP must not use Slack connector");
    const c360Tools = manifest.c360_mcp?.expected_tools || [];
    if (!c360Tools.includes("list_current_customer_orgs")) fail("Manifest missing C360 MCP tool: list_current_customer_orgs");
    if (manifest.c360_mcp?.read_only !== true) fail("Manifest C360 MCP must be read_only");
    if (manifest.c360_mcp?.auth_header !== "X-Customer360-Internal-Token") fail("Manifest C360 MCP must use custom internal auth header");
    if (manifest.c360_mcp?.uses_browser_cookie !== false) fail("Manifest C360 MCP must not use browser cookies");
    if (manifest.c360_mcp?.uses_personal_customer360_session !== false) fail("Manifest C360 MCP must not use personal customer360_session");
    const dataLearningTools = manifest.data_learning_mcp?.expected_tools || [];
    for (const tool of [
      "record_staffany_data_lesson_candidate",
      "list_staffany_data_lesson_candidates",
      "read_staffany_data_lesson_candidate",
      "update_staffany_data_lesson_candidate_status"
    ]) {
      if (!dataLearningTools.includes(tool)) fail(`Manifest missing data learning MCP tool: ${tool}`);
    }
    for (const status of ["pending_review", "needs_more_evidence", "approved_for_repo_promotion", "rejected", "promoted"]) {
      if (!manifest.data_learning_mcp?.valid_statuses?.includes(status)) fail(`Manifest data learning MCP missing status: ${status}`);
    }
    if (manifest.data_learning_mcp?.review_status_tool !== "update_staffany_data_lesson_candidate_status") fail("Manifest data learning MCP missing review status tool");
    if (manifest.data_learning_mcp?.review_approval_marker !== "human reviewed lesson") fail("Manifest data learning MCP missing human review marker");
    if (manifest.data_learning_mcp?.writes_runtime_candidates_only !== true) fail("Manifest data learning MCP must write runtime candidates only");
    if (manifest.data_learning_mcp?.active_behavior_change !== false) fail("Manifest data learning MCP must not change active behavior");
    if (manifest.data_learning_mcp?.self_approval !== false) fail("Manifest data learning MCP must not allow self approval");
    if (manifest.data_learning_mcp?.honcho_source_of_truth !== false) fail("Manifest data learning MCP must not use Honcho as source of truth");
    if (manifest.data_learning_mcp?.stores_raw_slack_transcripts !== false) fail("Manifest data learning MCP must not store raw Slack transcripts");
    if (manifest.data_learning_mcp?.stores_raw_query_rows !== false) fail("Manifest data learning MCP must not store raw query rows");
    if (manifest.data_learning_mcp?.stores_sensitive_data !== false) fail("Manifest data learning MCP must not store sensitive data");
    if (manifest.data_learning_review_report?.prints_safe_counts_only !== true) fail("Manifest data learning report must print safe counts only");
    if (manifest.data_learning_review_report?.prints_raw_lesson_content !== false) fail("Manifest data learning report must not print raw lesson content");
    const googleSheetsTools = manifest.google_sheets_output_mcp?.expected_tools || [];
    for (const tool of ["check_google_sheets_output_access", "create_spreadsheet_from_rows"]) {
      if (!googleSheetsTools.includes(tool)) fail(`Manifest missing Google Sheets output MCP tool: ${tool}`);
    }
    if (manifest.google_sheets_output_mcp?.account_email !== "team@staffany.com") fail("Manifest Google Sheets output account_email must be team@staffany.com");
    if (manifest.google_sheets_output_mcp?.access_mode !== "team_oauth_google_sheets_output") fail("Manifest Google Sheets output access_mode must be team_oauth_google_sheets_output");
    if (manifest.google_sheets_output_mcp?.service_account !== false) fail("Manifest Google Sheets output must not claim service_account=true");
    if (manifest.google_sheets_output_mcp?.create_only !== true) fail("Manifest Google Sheets output must be create_only");
    if (manifest.google_sheets_output_mcp?.edits_existing_spreadsheets !== false) fail("Manifest Google Sheets output must not edit existing spreadsheets");
    if (manifest.google_sheets_output_mcp?.uses_user_token !== false) fail("Manifest Google Sheets output must not use user token");
    if (manifest.google_sheets_output_mcp?.uses_slack_connector !== false) fail("Manifest Google Sheets output must not use Slack connector");
    if (manifest.google_sheets_output_mcp?.requires_output_folder_or_share_target !== true) fail("Manifest Google Sheets output must require folder or share target");
    if (!manifest.google_sheets_output_mcp?.required_scopes?.includes("https://www.googleapis.com/auth/spreadsheets")) fail("Manifest Google Sheets output missing spreadsheets scope");
    if (!manifest.google_sheets_output_mcp?.required_scopes?.includes("https://www.googleapis.com/auth/drive.file")) fail("Manifest Google Sheets output missing drive.file scope");
  }
}

const packageJson = existsSync(packageJsonPath) ? readJson(packageJsonPath) : null;
if (packageJson?.scripts?.["hermes-data-bot:deploy"] !== "node scripts/deploy-hermes-data-bot.mjs") {
  fail("package.json must expose hermes-data-bot:deploy");
}
if (!existsSync(join(repoRoot, "scripts", "deploy-hermes-data-bot.mjs"))) {
  fail("Missing scripts/deploy-hermes-data-bot.mjs");
}

const filesToScan = [
  "profile/SOUL.md",
  "profile/config.template.yaml",
  "skills/staffany-data-bot/SKILL.md",
  "../hermes-shared/google-sheets-output/README.md",
  "../hermes-shared/google-sheets-output/skills/staffany-google-sheets-output/SKILL.md",
  "../hermes-shared/google-sheets-output/runtime/google-sheets-output.md",
  "../hermes-shared/google-sheets-output/runtime/mcp/google_oauth.py",
  "../hermes-shared/google-sheets-output/runtime/mcp/staffany_google_sheets_server.py",
  "../hermes-shared/google-sheets-output/runtime/mcp/test_helpers.py",
  "../hermes-shared/google-sheets-output/runtime/mcp/test_staffany_google_sheets_server.py",
  "skills/staffany-data-bot/references/staffany-data-bot-metric-registry.md",
  "skills/staffany-data-bot/references/staffany-product-lookup-registry.md",
  "skills/staffany-data-bot/references/staffany-release-feature-registry.md",
  "skills/staffany-data-bot/references/rbac-access-levels.md",
  "skills/staffany-data-bot/references/reviewed-lessons.md",
  "skills/staffany-data-bot/references/regression-cases.md",
  "runtime/mcp/staffany-bigquery.md",
  "runtime/mcp/staffany_slack_context_server.py",
  "runtime/mcp/staffany_c360_server.py",
  "runtime/mcp/staffany_data_learning_server.py",
  "runtime/mcp/profile_env.py",
  "runtime/mcp/test_helpers.py",
  "runtime/mcp/test_staffany_slack_context_server.py",
  "runtime/mcp/test_staffany_c360_server.py",
  "runtime/mcp/test_staffany_data_learning_server.py",
  "runtime/jira-release-sync.md",
  "runtime/sync-jira-release-registry.sh",
  "runtime/high-priority-feature-digest.md",
  "runtime/prompts/high-priority-feature-usage-digest.md",
  "runtime/memory-honcho.md",
  "runtime/slack.md",
  "runtime/health-checks.md",
  "runtime/check-health.sh",
  "runtime/check-cloud-heartbeat.sh",
  "runtime/staffanydatabot-cloud-doctor.sh",
  "runtime/report-staffany-data-learning.py",
  "runtime/audit-live-profile.sh",
  "runtime/backup-honcho.sh",
  "runtime/review-honcho-memory.sh",
  "deploy/gcp-vm-topology.md",
  "deploy/gce-onboarding-runbook.md",
  "tests/regression-cases.md",
  "tests/prompt-evals.json"
];

for (const relPath of filesToScan) {
  assertFile(relPath);
  scanForSecretPatterns(relPath);
}

const configText = existsSync(join(appRoot, "profile", "config.template.yaml"))
  ? readFileSync(join(appRoot, "profile", "config.template.yaml"), "utf8")
  : "";
for (const requiredText of [
  "Apply on hermes-data-bot-poc only",
  "Do not create a Mac-local",
  "staffanydatabot profile"
]) {
  if (!configText.includes(requiredText)) fail(`config.template.yaml missing cloud-only profile guidance: ${requiredText}`);
}
for (const tool of ["list_dataset_ids", "list_table_ids", "get_table_info", "execute_sql_readonly"]) {
  if (!configText.includes(tool)) fail(`config.template.yaml missing allowlisted tool ${tool}`);
}
if (!configText.includes('provider: "anthropic"')) fail('config.template.yaml must set model.provider to anthropic');
if (!configText.includes('default: "claude-sonnet-4-6"')) fail('config.template.yaml must set model.default to claude-sonnet-4-6');
if (!configText.includes("api_max_retries: 3")) fail("config.template.yaml must keep Anthropic provider retries enabled");
if (!configText.includes('personality: "concise"')) fail("config.template.yaml must use concise display personality");
if (!configText.includes("interim_assistant_messages: false")) fail("config.template.yaml must disable Slack interim assistant messages");
if (!configText.includes('tool_progress: "off"')) fail("config.template.yaml must disable Slack tool progress");
if (!configText.includes("streaming: false")) fail("config.template.yaml must disable Slack streaming");
if (!configText.includes("reactions: false")) fail("config.template.yaml must disable Slack reactions");
if (!configText.includes("max_parallel_jobs: 1")) fail("config.template.yaml must cap cron.max_parallel_jobs at 1");
if (!configText.includes('Authorization: "Bearer ${MCP_STAFFANY_BIGQUERY_API_KEY}"')) fail("config.template.yaml must configure BigQuery MCP bearer header auth");
if (!configText.includes("resources: false")) fail("config.template.yaml must disable MCP resources");
if (!configText.includes("prompts: false")) fail("config.template.yaml must disable MCP prompts");
for (const requiredText of [
  "staffany_slack_context",
  "get_current_slack_thread_context",
  "get_selected_slack_thread_context",
  "STAFFANY_DATA_BOT_SLACK_CONTEXT_CHANNEL_IDS",
  "C0A0V39AK44",
  "C0A0PETSFJS",
  "slack_connector_fallback: false",
  "user_token_fallback: false",
  "workspace_search: false",
  "slack_posting: false"
]) {
  if (!configText.includes(requiredText)) fail(`config.template.yaml missing Slack context contract: ${requiredText}`);
}
for (const requiredText of [
  "staffany_c360",
  "list_current_customer_orgs",
  "CUSTOMER360_BASE_URL",
  "CUSTOMER360_INTERNAL_API_TOKEN",
  "X-Customer360-Internal-Token",
  "custom_internal_header_only: true",
  "browser_cookie: false",
  "personal_customer360_session: false",
  "write_operations: false"
]) {
  if (!configText.includes(requiredText)) fail(`config.template.yaml missing C360 contract: ${requiredText}`);
}
for (const requiredText of [
  "staffany_data_learning",
  "staffany_data_learning_server.py",
  "STAFFANY_DATA_LEARNING_CANDIDATES_DIR",
  "reviewed_learning_candidates_runtime_only",
  "record_status: \"pending_review\"",
  "needs_more_evidence",
  "review_status_tool: \"update_staffany_data_lesson_candidate_status\"",
  "review_approval_marker: \"human reviewed lesson\"",
  "auto_behavior_change: false",
  "self_approval: false",
  "honcho_used_as_source_of_truth: false",
  "raw_slack_transcript_persistence: false",
  "raw_query_row_persistence: false",
  "sensitive_data_persistence: false",
  "kanban_dispatch: false",
  "persistent_goal_continuation: false",
  "self_evolution_gepa: false",
  "record_staffany_data_lesson_candidate",
  "list_staffany_data_lesson_candidates",
  "read_staffany_data_lesson_candidate",
  "update_staffany_data_lesson_candidate_status"
]) {
  if (!configText.includes(requiredText)) fail(`config.template.yaml missing data learning contract: ${requiredText}`);
}
for (const requiredText of [
  "staffany_google_sheets",
  "staffany_google_sheets_server.py",
  "team@staffany.com",
  "GOOGLE_SHEETS_TOKEN_FILE",
  "GOOGLE_SHEETS_CLIENT_SECRET_FILE",
  "GOOGLE_SHEETS_ACCOUNT_EMAIL",
  "GOOGLE_SHEETS_OUTPUT_FOLDER_ID",
  "GOOGLE_SHEETS_OUTPUT_SHARE_EMAILS",
  "GOOGLE_SHEETS_OUTPUT_SHARE_ROLE",
  "https://www.googleapis.com/auth/spreadsheets",
  "https://www.googleapis.com/auth/drive.file",
  "requires_output_folder_or_share_target: true",
  "edit_existing_spreadsheets: false",
  "read_arbitrary_spreadsheets: false",
  "user_token_fallback: false",
  "slack_connector_fallback: false",
  "max_tabs: 5",
  "max_rows_per_tab: 5000",
  "max_total_cells: 100000",
  "max_cell_chars: 2000",
  "formula_like_cells_escaped: true",
  "check_google_sheets_output_access",
  "create_spreadsheet_from_rows"
]) {
  if (!configText.includes(requiredText)) fail(`config.template.yaml missing Google Sheets output contract: ${requiredText}`);
}
if (configText.includes('all@staffany')) fail('config.template.yaml must not reference known-bad all@staffany model alias');
if (configText.includes("OPENAI_API_KEY")) fail("config.template.yaml must not configure OpenAI API key routing");
if (configText.includes('base_url: "https://api.openai.com/v1"')) fail("config.template.yaml must not configure OpenAI API base_url");

const topologyText = existsSync(join(appRoot, "deploy", "gcp-vm-topology.md"))
  ? readFileSync(join(appRoot, "deploy", "gcp-vm-topology.md"), "utf8")
  : "";
for (const requiredText of [
  "hermes-data-bot-poc",
  "hermes-gateway-launchbot.service",
  "launchbot",
  "#launch-bot-testing",
  "C0B32M34J3W",
  "U0ASVD79UT1",
  "B0ATPPEGBCH",
  "hermes-gateway-staffanydatabot.service",
  "hermes-psm-ops-bot-poc",
  "hermes-gateway-psmopsbot.service",
  "nurtureany-sales-bot-prod",
  "hermes-gateway-nurtureanysalesbot.service",
  "profile directory is not deployment proof",
  "Do not create a separate LaunchBot VM unless"
]) {
  if (!topologyText.includes(requiredText)) fail(`GCP VM topology doc missing required text: ${requiredText}`);
}

const profilesText = existsSync(join(repoRoot, "ops", "hermes", "profiles.yaml"))
  ? readFileSync(join(repoRoot, "ops", "hermes", "profiles.yaml"), "utf8")
  : "";
for (const [profileName, deployHost] of [
  ["staffanydatabot", "hermes-data-bot-poc"],
  ["launchbot", "hermes-data-bot-poc"],
  ["psmopsbot", "hermes-psm-ops-bot-poc"],
  ["nurtureanysalesbot", "nurtureany-sales-bot-prod"]
]) {
  const block = profileBlock(profilesText, profileName);
  if (!block) {
    fail(`ops/hermes/profiles.yaml missing ${profileName} profile`);
    continue;
  }
  if (!block.includes(`deploy_host: ${deployHost}`)) {
    fail(`${profileName} profile must deploy to ${deployHost}`);
  }
  if (!block.includes("local_profile_policy: cloud_only")) {
    fail(`${profileName} profile must be marked cloud-only`);
  }
  if (block.includes("launchd_label:")) {
    fail(`${profileName} profile must not define a Mac launchd_label`);
  }
}

const deployRunbookText = existsSync(join(appRoot, "deploy", "gce-onboarding-runbook.md"))
  ? readFileSync(join(appRoot, "deploy", "gce-onboarding-runbook.md"), "utf8")
  : "";
for (const requiredText of [
  "deploy/gcp-vm-topology.md",
  "hermes-gateway-launchbot.service",
  "Deployment means the matching `hermes-gateway-<profile>.service` is active"
]) {
  if (!deployRunbookText.includes(requiredText)) fail(`GCE onboarding runbook missing topology text: ${requiredText}`);
}

const skillText = existsSync(join(appRoot, "skills", "staffany-data-bot", "SKILL.md"))
  ? readFileSync(join(appRoot, "skills", "staffany-data-bot", "SKILL.md"), "utf8")
  : "";
for (const requiredText of [
  'Reply "run" to start',
  'first Slack mentions',
  'Confidence: blocked',
  'employee-level payroll detail',
  'staffany-release-feature-registry.md',
  'Do not query Jira live',
  'Do not say the release-feature registry is missing unless that exact reference-file load fails',
  'needs-mapping',
  'scheduled digest',
  'staffany_c360.list_current_customer_orgs',
  'Customer 360 is the source of truth for the current-customer universe',
  'Marketing banner on and AA used as banner content/target',
  'staffany_google_sheets.create_spreadsheet_from_rows',
  'Google Sheets output',
  'Do not edit existing spreadsheets in v1',
  'Do not say the bot has no direct Google Sheets integration',
  'references/reviewed-lessons.md',
  'record_staffany_data_lesson_candidate',
  'update_staffany_data_lesson_candidate_status',
  'approval_marker="human reviewed lesson"',
  'Runtime candidates do not change behavior by themselves.',
  'Same-session caveat',
  'runtime-created or Curator-patched skills'
]) {
  if (!skillText.includes(requiredText)) fail(`staffany-data-bot skill missing required guardrail text: ${requiredText}`);
}

const reviewedLessonsText = existsSync(join(appRoot, "skills", "staffany-data-bot", "references", "reviewed-lessons.md"))
  ? readFileSync(join(appRoot, "skills", "staffany-data-bot", "references", "reviewed-lessons.md"), "utf8")
  : "";
for (const requiredText of [
  "Reviewed lessons are the only approved V1 path",
  "Hermes Learning Primitives",
  "`record_staffany_data_lesson_candidate` writes only `pending_review` candidates.",
  "update_staffany_data_lesson_candidate_status",
  "needs_more_evidence",
  "approval_marker=\"human reviewed lesson\"",
  "recallMode=tools",
  "saveMessages=false",
  "sessionStrategy=per-session",
  "runtime-created or Curator-patched skills are review artifacts only",
  "runtime/report-staffany-data-learning.py --stale-days 14",
  "Self-evolution/GEPA",
  "candidate recorded"
]) {
  if (!reviewedLessonsText.includes(requiredText)) fail(`reviewed-lessons.md missing required text: ${requiredText}`);
}

const releaseRegistryText = existsSync(join(appRoot, "skills", "staffany-data-bot", "references", "staffany-release-feature-registry.md"))
  ? readFileSync(join(appRoot, "skills", "staffany-data-bot", "references", "staffany-release-feature-registry.md"), "utf8")
  : "";
for (const requiredText of [
  "jira_issue_key",
  "release_version",
  "release_date",
  "canonical_feature_name",
  "product_area",
  "launch_priority_field",
  "launch_priority_value",
  "usage_metric_key",
  "source_table_hint",
  "sync_timestamp",
  "priority_mapping_status = confirmed",
  "tracking_status = track",
  "Launch Priority",
  "P1 - High Reach Retention and Growth",
  "Confidence: blocked"
]) {
  if (!releaseRegistryText.includes(requiredText)) fail(`release feature registry missing required text: ${requiredText}`);
}

const jiraSyncText = existsSync(join(appRoot, "runtime", "sync-jira-release-registry.sh"))
  ? readFileSync(join(appRoot, "runtime", "sync-jira-release-registry.sh"), "utf8")
  : "";
for (const requiredText of [
  "sync:priority-mapping-needs-confirmation",
  "JIRA_LAUNCH_PRIORITY_FIELD_ID",
  "JIRA_HIGH_PRIORITY_VALUES",
  "project = KER",
  "P1 - High Reach Retention and Growth",
  "needs-mapping"
]) {
  if (!jiraSyncText.includes(requiredText)) fail(`jira release sync script missing required text: ${requiredText}`);
}

const digestRuntimeText = existsSync(join(appRoot, "runtime", "high-priority-feature-digest.md"))
  ? readFileSync(join(appRoot, "runtime", "high-priority-feature-digest.md"), "utf8")
  : "";
for (const requiredText of [
  "0 1 * * 1",
  "#da-ta-hermz-testing",
  "C0AU19E6T0C",
  "staffanydatabot high-priority release feature usage digest",
  "Confidence: <verified | needs-check | blocked>"
]) {
  if (!digestRuntimeText.includes(requiredText)) fail(`feature usage digest runtime doc missing required text: ${requiredText}`);
}

const digestPromptText = existsSync(join(appRoot, "runtime", "prompts", "high-priority-feature-usage-digest.md"))
  ? readFileSync(join(appRoot, "runtime", "prompts", "high-priority-feature-usage-digest.md"), "utf8")
  : "";
for (const requiredText of [
  "Do not query Jira live",
  "priority_mapping_status = confirmed",
  "tracking_status = track",
  "Confidence: blocked"
]) {
  if (!digestPromptText.includes(requiredText)) fail(`feature usage digest prompt missing required text: ${requiredText}`);
}

const googleSheetsSharedRoot = join(repoRoot, "apps", "hermes-shared", "google-sheets-output");
const googleSheetsSkillText = existsSync(join(googleSheetsSharedRoot, "skills", "staffany-google-sheets-output", "SKILL.md"))
  ? readFileSync(join(googleSheetsSharedRoot, "skills", "staffany-google-sheets-output", "SKILL.md"), "utf8")
  : "";
for (const requiredText of [
  "team@staffany.com",
  "GOOGLE_SHEETS_TOKEN_FILE",
  "GOOGLE_SHEETS_CLIENT_SECRET_FILE",
  "GOOGLE_SHEETS_OUTPUT_FOLDER_ID",
  "GOOGLE_SHEETS_OUTPUT_SHARE_EMAILS",
  "check_google_sheets_output_access",
  "create_spreadsheet_from_rows",
  "Max 5 tabs",
  "Max 5,000 rows per tab",
  "Escape cells beginning with",
  "Creation-only in v1",
  "Do not edit existing spreadsheets"
]) {
  if (!googleSheetsSkillText.includes(requiredText)) fail(`shared Google Sheets output skill missing required text: ${requiredText}`);
}

const googleSheetsServerText = existsSync(join(googleSheetsSharedRoot, "runtime", "mcp", "staffany_google_sheets_server.py"))
  ? readFileSync(join(googleSheetsSharedRoot, "runtime", "mcp", "staffany_google_sheets_server.py"), "utf8")
  : "";
for (const requiredText of [
  "DEFAULT_ACCOUNT_EMAIL = \"team@staffany.com\"",
  "GOOGLE_SHEETS_TOKEN_FILE",
  "GOOGLE_SHEETS_CLIENT_SECRET_FILE",
  "GOOGLE_SHEETS_OUTPUT_FOLDER_ID",
  "GOOGLE_SHEETS_OUTPUT_SHARE_EMAILS",
  "SPREADSHEETS_SCOPE",
  "DRIVE_FILE_SCOPE",
  "MAX_TABS = 5",
  "MAX_ROWS_PER_TAB = 5000",
  "MAX_TOTAL_CELLS = 100_000",
  "MAX_CELL_CHARS = 2000",
  "FORMULA_PREFIXES",
  "check_google_sheets_output_access",
  "create_spreadsheet_from_rows",
  "mcp.run(\"stdio\")"
]) {
  if (!googleSheetsServerText.includes(requiredText)) fail(`shared Google Sheets MCP missing required text: ${requiredText}`);
}

const cloudHeartbeatText = existsSync(join(appRoot, "runtime", "check-cloud-heartbeat.sh"))
  ? readFileSync(join(appRoot, "runtime", "check-cloud-heartbeat.sh"), "utf8")
  : "";
for (const requiredText of [
  "hermes-gateway-staffanydatabot.service",
  "hermes-gateway-launchbot.service",
  "staffanydatabot local cloud heartbeat",
  "staffanydatabot Honcho backup",
  "EXPECTED_ENABLED_CRON_COUNT",
  "Asia/Singapore",
  "systemctl --user is-active",
  "systemctl --user is-enabled"
]) {
  if (!cloudHeartbeatText.includes(requiredText)) fail(`cloud heartbeat script missing required text: ${requiredText}`);
}

const shellCheck = spawnSync("bash", [
  "-n",
  join(appRoot, "runtime", "check-health.sh"),
  join(appRoot, "runtime", "check-cloud-heartbeat.sh"),
  join(appRoot, "runtime", "staffanydatabot-cloud-doctor.sh"),
  join(appRoot, "runtime", "audit-live-profile.sh"),
  join(appRoot, "runtime", "backup-honcho.sh"),
  join(appRoot, "runtime", "review-honcho-memory.sh")
], {
  cwd: repoRoot,
  encoding: "utf8"
});
if (shellCheck.status !== 0) {
  fail(`Shell syntax check failed: ${shellCheck.stderr || shellCheck.stdout}`);
}

const pythonCompile = spawnSync("python3", [
  "-m",
  "py_compile",
  join(appRoot, "runtime", "mcp", "staffany_data_learning_server.py"),
  join(appRoot, "runtime", "report-staffany-data-learning.py")
], {
  cwd: repoRoot,
  encoding: "utf8"
});
if (pythonCompile.status !== 0) {
  fail(`Python compile failed: ${pythonCompile.stderr || pythonCompile.stdout}`);
}

const dataLearningServerText = existsSync(join(appRoot, "runtime", "mcp", "staffany_data_learning_server.py"))
  ? readFileSync(join(appRoot, "runtime", "mcp", "staffany_data_learning_server.py"), "utf8")
  : "";
for (const requiredText of [
  "update_staffany_data_lesson_candidate_status",
  "LESSON_CANDIDATE_REVIEW_MARKER = \"human reviewed lesson\"",
  "needs_more_evidence",
  "approved_for_repo_promotion",
  "min(max(0, int(limit)), 100)",
  "\\b{re.escape(marker)}\\b",
  "promoted requires live_verified_at and live_verification_summary"
]) {
  if (!dataLearningServerText.includes(requiredText)) fail(`staffany_data_learning_server.py missing required review workflow text: ${requiredText}`);
}

const deployScriptText = existsSync(join(repoRoot, "scripts", "deploy-hermes-data-bot.mjs"))
  ? readFileSync(join(repoRoot, "scripts", "deploy-hermes-data-bot.mjs"), "utf8")
  : "";
for (const requiredText of [
  "--apply",
  "Dry run only",
  "node scripts/verify-hermes-data-bot.mjs",
  "node scripts/run-prompt-evals.mjs --app hermes-data-bot --mode all",
  "staffanydatabot-cloud-doctor.sh",
  "deploy:summary:cloud_doctor=passed",
  "VERSION",
  "staffany_slack_context",
  "staffany_c360",
  "staffany_data_learning",
  "staffany_google_sheets",
  "staffanydatabot-report-data-learning.py",
  "hermes-shared/google-sheets-output",
  "staffany-google-sheets-output"
]) {
  if (!deployScriptText.includes(requiredText)) fail(`deploy-hermes-data-bot.mjs missing required text: ${requiredText}`);
}

const cloudDoctorText = existsSync(join(appRoot, "runtime", "staffanydatabot-cloud-doctor.sh"))
  ? readFileSync(join(appRoot, "runtime", "staffanydatabot-cloud-doctor.sh"), "utf8")
  : "";
for (const requiredText of [
  "staffanydatabot-cloud-doctor:profile=$PROFILE",
  "hermes-gateway-staffanydatabot.service",
  "hermes-gateway-launchbot.service",
  "deliver_null",
  "check_mcp_tools \"staffany_bigquery\"",
  "check_mcp_tools \"staffany_slack_context\"",
  "check_mcp_tools \"staffany_c360\"",
  "check_mcp_tools \"staffany_data_learning\"",
  "EXPECTED_DATA_LEARNING_MCP_TOOLS=\"${EXPECTED_DATA_LEARNING_MCP_TOOLS:-4}\"",
  "check_mcp_tools \"staffany_google_sheets\"",
  "staffany_data_learning_review_report:ok",
  "lesson_candidates_content:omitted",
  "slack:selected-thread:ok",
  "C0A0V39AK44"
]) {
  if (!cloudDoctorText.includes(requiredText)) fail(`staffanydatabot-cloud-doctor.sh missing required text: ${requiredText}`);
}

const mcpTest = spawnSync("python3", [
  "-m",
  "unittest",
  "apps/hermes-data-bot/runtime/mcp/test_staffany_slack_context_server.py",
  "apps/hermes-data-bot/runtime/mcp/test_staffany_c360_server.py",
  "apps/hermes-data-bot/runtime/mcp/test_staffany_data_learning_server.py",
  "apps/hermes-shared/google-sheets-output/runtime/mcp/test_staffany_google_sheets_server.py"
], {
  cwd: repoRoot,
  encoding: "utf8"
});
if (mcpTest.status !== 0) {
  fail(`MCP unittest failed: ${mcpTest.stderr || mcpTest.stdout}`);
}

if (failures.length > 0) {
  console.error("Hermes Data Bot packet verification failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log("Hermes Data Bot packet verification passed.");
