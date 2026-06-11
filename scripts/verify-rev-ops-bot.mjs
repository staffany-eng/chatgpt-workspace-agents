import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { join, resolve } from "node:path";
import {
  assertFile as sharedAssertFile,
  assertManifestPaths,
  readJson as sharedReadJson,
  scanForSecretPatterns as sharedScanForSecretPatterns,
  textOf,
} from "./lib/app-packet-verify.mjs";

const repoRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
const appRoot = join(repoRoot, "apps", "rev-ops-bot");
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

const manifest = existsSync(manifestPath) ? sharedReadJson(manifestPath, fail) : null;
if (!manifest) {
  fail("Missing apps/rev-ops-bot/app.manifest.json");
} else {
  if (manifest.profile_name !== "revopsbot") fail("Manifest profile_name must be revopsbot");
  if (manifest.model_provider !== "anthropic") fail("Manifest model_provider must be anthropic");
  if (manifest.model !== "claude-sonnet-4-6") fail("Manifest model must be claude-sonnet-4-6");
  if (manifest.secrets_copied !== false) fail("Manifest secrets_copied must be false");
  if (manifest.write_policy?.default_mode !== "approval_required") {
    fail("Manifest default_mode must be approval_required");
  }
  if (manifest.write_policy?.hermes_business_writes !== false) fail("Manifest must forbid Hermes business writes");
  if (manifest.write_policy?.windmill_live_execution !== "approval_gated") {
    fail("Manifest windmill_live_execution must be approval_gated");
  }
  const tools = new Set(manifest.mcp?.revops_windmill?.tools || []);
  for (const tool of [
    "check_windmill_revops_config",
    "search_billing_main_deals",
    "preflight_create_sub_deal_request",
    "preview_create_sub_deal_and_service_agreement",
    "preview_preflight_updates",
    "apply_approved_preflight_updates",
    "execute_approved_create_sub_deal_and_service_agreement",
    "preview_send_service_agreement",
    "execute_approved_send_service_agreement",
  ]) {
    if (!tools.has(tool)) fail(`Manifest revops_windmill missing tool: ${tool}`);
  }
  if (manifest.mcp?.revops_windmill?.windmill?.preview_forces_dry_run !== true) {
    fail("Manifest revops_windmill previews must force dry_run");
  }
  if (manifest.mcp?.revops_windmill?.windmill?.execution_requires_approval !== true) {
    fail("Manifest revops_windmill execution must require approval");
  }
  assertManifestPaths(appRoot, manifest.paths || {}, fail);
}

const filesToScan = [
  "README.md",
  "AGENTS.md",
  "app.manifest.json",
  "profile/SOUL.md",
  "profile/config.template.yaml",
  "profile/.env.template",
  "skills/rev-ops-bot/SKILL.md",
  "skills/rev-ops-bot/references/windmill-preview-contract.md",
  "skills/rev-ops-bot/references/regression-cases.md",
  "runtime/slack.md",
  "runtime/windmill.md",
  "runtime/health-checks.md",
  "runtime/check-health.sh",
  "runtime/audit-live-profile.sh",
  "runtime/mcp/README.md",
  "runtime/mcp/profile_env.py",
  "runtime/mcp/revops_windmill_core.py",
  "runtime/mcp/revops_windmill_server.py",
  "runtime/mcp/test_revops_windmill_core.py",
  "tests/regression-cases.md",
  "tests/prompt-evals.json",
];

for (const relPath of filesToScan) {
  assertFile(relPath);
  scanForSecretPatterns(relPath);
}

const configText = textOf(appRoot, "profile/config.template.yaml");
for (const requiredText of [
  'provider: "anthropic"',
  'default: "claude-sonnet-4-6"',
  "redact_secrets: true",
  "require_mention: true",
  'tool_progress: "off"',
  "streaming: false",
  'mode: "approval_required"',
  'base_url_env: "REVOPS_WINDMILL_BASE_URL"',
  'workspace_id_env: "REVOPS_WINDMILL_WORKSPACE_ID"',
  'token_env: "REVOPS_WINDMILL_TOKEN"',
  'apply_preflight_updates_script_path: "f/rev_ops/apply_preflight_updates"',
  'send_service_agreement_script_path: "f/rev_ops/send_service_agreement"',
  "revops_windmill_server.py",
]) {
  if (!configText.includes(requiredText)) fail(`config.template.yaml missing required text: ${requiredText}`);
}

const envTemplateText = textOf(appRoot, "profile/.env.template");
for (const requiredText of [
  "SLACK_APP_TOKEN=",
  "SLACK_BOT_TOKEN=",
  "REVOPS_CREATE_SUB_DEAL_MODAL_ENABLED=1",
  "REVOPS_BOT_USER_ID=",
  "REVOPS_CREATE_SUB_DEAL_COMMAND=",
  "REVOPS_CREATE_SUB_DEAL_ALLOWED_CHANNEL_IDS=",
  "REVOPS_WINDMILL_BASE_URL=https://mill.staffany.net",
  "REVOPS_WINDMILL_WORKSPACE_ID=staffany",
  "REVOPS_WINDMILL_TOKEN=",
]) {
  if (!envTemplateText.includes(requiredText)) fail(`.env.template missing required text: ${requiredText}`);
}

const skillText = textOf(appRoot, "skills/rev-ops-bot/SKILL.md");
for (const requiredText of [
  "Live writes require explicit approval",
  "execute_approved_create_sub_deal_and_service_agreement",
  "execute_approved_send_service_agreement",
  "apply_approved_preflight_updates",
  "preview_create_sub_deal_and_service_agreement",
  "search_billing_main_deals",
]) {
  if (!skillText.includes(requiredText)) fail(`Skill missing required text: ${requiredText}`);
}

const coreText = textOf(appRoot, "runtime/mcp/revops_windmill_core.py");
for (const requiredText of [
  '"dry_run": True',
  '"dry_run": False',
  "run_wait_result",
  "REVOPS_WINDMILL_TOKEN",
  "Bearer",
  "APPLY_PREFLIGHT_UPDATES_SCRIPT_PATH",
  "SEND_SERVICE_AGREEMENT_SCRIPT_PATH",
  "execute_create_sub_deal_and_service_agreement",
  "execute_send_service_agreement",
]) {
  if (!coreText.includes(requiredText)) fail(`Windmill core missing required text: ${requiredText}`);
}

const unit = spawnSync(
  "python3",
  ["-m", "unittest", "discover", join(appRoot, "runtime", "mcp"), "-p", "test_*.py"],
  {
    cwd: repoRoot,
    encoding: "utf8",
  },
);
if (unit.status !== 0) {
  fail(`RevOps MCP unit tests failed:\n${unit.stdout}\n${unit.stderr}`);
}

if (failures.length > 0) {
  console.error("RevOps Bot packet verification failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log("RevOps Bot packet verification passed.");
