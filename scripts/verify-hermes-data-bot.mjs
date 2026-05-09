import { existsSync, readFileSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, resolve } from "node:path";

const repoRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
const appRoot = join(repoRoot, "apps", "hermes-data-bot");
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

function scanForSecretPatterns(relPath) {
  const path = join(appRoot, relPath);
  if (!existsSync(path) || !statSync(path).isFile()) return;
  const text = readFileSync(path, "utf8");
  const patterns = [
    [/xox[baprs]-[A-Za-z0-9-]+/, "Slack token"],
    [/xapp-[A-Za-z0-9-]+/, "Slack app token"],
    [/sk-[A-Za-z0-9_-]{20,}/, "OpenAI-style API key"],
    [/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/, "private key"],
    [/AIza[0-9A-Za-z_-]{20,}/, "Google API key"]
  ];
  for (const [pattern, label] of patterns) {
    if (pattern.test(text)) fail(`${label} pattern found in ${relPath}`);
  }
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
  "skills/staffany-data-bot/references/regression-cases.md",
  "runtime/mcp/staffany-bigquery.md",
  "runtime/memory-honcho.md",
  "runtime/slack.md",
  "runtime/health-checks.md",
  "runtime/check-health.sh",
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
if (!configText.includes('provider: "openai-codex"')) fail('config.template.yaml must set model.provider to openai-codex');
if (!configText.includes('default: "gpt-5.3-codex"')) fail('config.template.yaml must set model.default to gpt-5.3-codex');
if (!configText.includes("api_max_retries: 0")) fail("config.template.yaml must disable provider retries for Codex-only routing");
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
  'employee-level payroll detail'
]) {
  if (!skillText.includes(requiredText)) fail(`staffany-data-bot skill missing required guardrail text: ${requiredText}`);
}

if (failures.length > 0) {
  console.error("Hermes Data Bot packet verification failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log("Hermes Data Bot packet verification passed.");
