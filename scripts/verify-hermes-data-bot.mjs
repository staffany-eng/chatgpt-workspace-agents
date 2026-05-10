import { existsSync, readFileSync } from "node:fs";
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
  }
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
  "runtime/jira-release-sync.md",
  "runtime/sync-jira-release-registry.sh",
  "runtime/high-priority-feature-digest.md",
  "runtime/prompts/high-priority-feature-usage-digest.md",
  "runtime/memory-honcho.md",
  "runtime/slack.md",
  "runtime/health-checks.md",
  "runtime/check-health.sh",
  "runtime/audit-live-profile.sh",
  "runtime/backup-honcho.sh",
  "runtime/review-honcho-memory.sh",
  "deploy/gce-onboarding-runbook.md",
  "tests/regression-cases.md"
];

for (const relPath of filesToScan) {
  assertFile(relPath);
  scanForSecretPatterns(relPath);
}

const configText = existsSync(join(appRoot, "profile", "config.template.yaml"))
  ? readFileSync(join(appRoot, "profile", "config.template.yaml"), "utf8")
  : "";
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
if (configText.includes('all@staffany')) fail('config.template.yaml must not reference known-bad all@staffany model alias');
if (configText.includes("OPENAI_API_KEY")) fail("config.template.yaml must not configure OpenAI API key routing");
if (configText.includes('base_url: "https://api.openai.com/v1"')) fail("config.template.yaml must not configure OpenAI API base_url");

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
  'needs-mapping',
  'scheduled digest'
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
  "#kaiyi-bot-testing",
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

if (failures.length > 0) {
  console.error("Hermes Data Bot packet verification failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log("Hermes Data Bot packet verification passed.");
