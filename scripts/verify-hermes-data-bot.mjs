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
  "skills/staffany-data-bot/references/staffany-data-bot-metric-registry.md",
  "skills/staffany-data-bot/references/staffany-product-lookup-registry.md",
  "skills/staffany-data-bot/references/staffany-release-feature-registry.md",
  "skills/staffany-data-bot/references/rbac-access-levels.md",
  "skills/staffany-data-bot/references/regression-cases.md",
  "runtime/mcp/staffany-bigquery.md",
  "runtime/mcp/staffany_slack_context_server.py",
  "runtime/mcp/staffany_c360_server.py",
  "runtime/mcp/profile_env.py",
  "runtime/mcp/test_helpers.py",
  "runtime/mcp/test_staffany_slack_context_server.py",
  "runtime/mcp/test_staffany_c360_server.py",
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
  'Marketing banner on and AA used as banner content/target'
]) {
  if (!skillText.includes(requiredText)) fail(`staffany-data-bot skill missing required guardrail text: ${requiredText}`);
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
  "staffany_c360"
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
  "slack:selected-thread:ok",
  "C0A0V39AK44"
]) {
  if (!cloudDoctorText.includes(requiredText)) fail(`staffanydatabot-cloud-doctor.sh missing required text: ${requiredText}`);
}

const mcpTest = spawnSync("python3", [
  "-m",
  "unittest",
  "apps/hermes-data-bot/runtime/mcp/test_staffany_slack_context_server.py",
  "apps/hermes-data-bot/runtime/mcp/test_staffany_c360_server.py"
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
