import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, resolve } from "node:path";
import {
  assertManifestPaths,
  readJson as sharedReadJson,
  scanForSecretPatterns as sharedScanForSecretPatterns,
  textOf
} from "./lib/app-packet-verify.mjs";

const repoRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
const appRoot = join(repoRoot, "apps", "product-ops-bot");
const manifestPath = join(appRoot, "app.manifest.json");

const failures = [];

function fail(message) {
  failures.push(message);
}

function readJson(path) {
  return sharedReadJson(path, fail);
}

function scanForSecretPatterns(relPath) {
  sharedScanForSecretPatterns(appRoot, relPath, fail);
}

if (!existsSync(manifestPath)) {
  fail("Missing apps/product-ops-bot/app.manifest.json");
} else {
  const manifest = readJson(manifestPath);
  if (manifest) {
    if (manifest.profile_name !== "productopsbot") fail("Manifest profile_name must be productopsbot");
    if (manifest.model_provider !== "anthropic") fail("Manifest model_provider must be anthropic");
    if (manifest.model !== "claude-sonnet-4-6") fail("Manifest model must be claude-sonnet-4-6");
    if (manifest.secrets_copied !== false) fail("Manifest secrets_copied must be false");
    assertManifestPaths(appRoot, manifest.paths || {}, fail);
  }
}

const filesToScan = [
  "README.md",
  "AGENTS.md",
  "app.manifest.json",
  "profile/SOUL.md",
  "profile/config.template.yaml",
  "profile/.env.template",
  "skills/product-ops-bot/SKILL.md",
  "skills/product-ops-intake-linking/SKILL.md",
  "skills/staffany-product-delivery-workflow/SKILL.md",
  "skills/product-ops-bot/references/workflow-contract.md",
  "skills/product-ops-bot/references/regression-cases.md",
  "runtime/slack.md",
  "runtime/health-checks.md",
  "runtime/check-health.sh",
  "runtime/audit-live-profile.sh",
  "runtime/mcp/README.md",
  "deploy/gce-onboarding-runbook.md",
  "tests/regression-cases.md"
];

for (const relPath of filesToScan) {
  if (!textOf(appRoot, relPath)) fail(`Missing or empty required file: ${relPath}`);
  scanForSecretPatterns(relPath);
}

const configText = textOf(appRoot, "profile/config.template.yaml");
for (const requiredText of [
  'provider: "anthropic"',
  'default: "claude-sonnet-4-6"',
  "redact_secrets: true",
  "require_mention: true",
  "interim_assistant_messages: false",
  'tool_progress: "off"',
  "streaming: false",
  "reactions: false",
  "max_parallel_jobs: 1",
  'primary_skill: "product-ops-intake-linking"',
  'supporting_skill: "staffany-product-delivery-workflow"',
  'base_url_env: "JIRA_BASE_URL"',
  'email_env: "JIRA_EMAIL"',
  'api_token_env: "JIRA_API_TOKEN"',
  'api_key_env: "NOTION_API_KEY"',
  'version_env: "NOTION_VERSION"'
]) {
  if (!configText.includes(requiredText)) fail(`config.template.yaml missing required text: ${requiredText}`);
}

const envTemplateText = textOf(appRoot, "profile/.env.template");
for (const requiredText of [
  "JIRA_BASE_URL=",
  "JIRA_EMAIL=",
  "JIRA_API_TOKEN=",
  "NOTION_API_KEY=",
  "NOTION_VERSION="
]) {
  if (!envTemplateText.includes(requiredText)) fail(`.env.template missing required text: ${requiredText}`);
}

const skillText = textOf(appRoot, "skills/product-ops-bot/SKILL.md");
for (const requiredText of [
  "require explicit `run`",
  "write actions",
  "product-ops-intake-linking",
  "staffany-product-delivery-workflow",
  "Answer:",
  "Confidence: <verified | needs-check | blocked>"
]) {
  if (!skillText.includes(requiredText)) fail(`Skill missing required text: ${requiredText}`);
}

const intakeSkillText = textOf(appRoot, "skills/product-ops-intake-linking/SKILL.md");
for (const requiredText of [
  "KER-*",
  "Do not recommend `EDT-*` items unless the requester explicitly asks to include EDT scope.",
  "offer `New` instead of switching project scope implicitly",
  "Start with `Jira-updated.csv` as the first-pass KER discovery source.",
  "create an IFI ticket in Jira Service Management",
  "Use Atlassian Rovo for Jira and related Atlassian work.",
  "Use GitHub when you need to inspect Kraken or Gryphon code",
  "Use Notion for PRD collaboration.",
  "for Jira grooming or PRD generation, use `staffany-product-delivery-workflow` as the default workflow",
  "Any option except `Stop` proceeds to create IFI ticket immediately",
  "If best match is at least 85%, set organization field."
]) {
  if (!intakeSkillText.includes(requiredText)) fail(`Intake skill missing required text: ${requiredText}`);
}

const soulText = textOf(appRoot, "profile/SOUL.md");
if (!soulText.includes("search and recommend `KER-*` tickets by default")) {
  fail("SOUL.md must enforce KER default backlog scope");
}

const jiraRuntimeText = textOf(appRoot, "runtime/jira.md");
if (!jiraRuntimeText.includes("default backlog search scope is `KER` project tickets")) {
  fail("runtime/jira.md must enforce KER default backlog scope");
}

const manifest = existsSync(manifestPath) ? readJson(manifestPath) : null;
if (manifest) {
  if (manifest.skill_routing?.primary !== "product-ops-intake-linking") {
    fail("Manifest skill_routing.primary must be product-ops-intake-linking");
  }
  const supporting = manifest.skill_routing?.supporting || [];
  for (const skill of ["staffany-product-delivery-workflow", "product-ops-bot"]) {
    if (!supporting.includes(skill)) fail(`Manifest skill_routing.supporting missing ${skill}`);
  }
}

const healthText = textOf(appRoot, "runtime/health-checks.md");
if (!healthText.includes("npm run product-ops-bot:verify")) {
  fail("runtime/health-checks.md must include product-ops-bot verify command");
}

if (process.env.PRODUCT_OPS_FULL_WORKFLOW === "1") {
  const requiredFullModeEnv = [
    "JIRA_BASE_URL",
    "JIRA_EMAIL",
    "JIRA_API_TOKEN",
    "NOTION_API_KEY",
    "NOTION_VERSION"
  ];
  for (const key of requiredFullModeEnv) {
    const value = process.env[key];
    if (!value || value.trim() === "") fail(`Full workflow mode missing env var: ${key}`);
  }
}

if (process.env.PRODUCT_OPS_JIRA_WORKFLOW === "1") {
  const requiredJiraModeEnv = [
    "JIRA_BASE_URL",
    "JIRA_EMAIL",
    "JIRA_API_TOKEN"
  ];
  for (const key of requiredJiraModeEnv) {
    const value = process.env[key];
    if (!value || value.trim() === "") fail(`Jira workflow mode missing env var: ${key}`);
  }
}

if (failures.length > 0) {
  console.error("Product Ops Bot packet verification failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log("Product Ops Bot packet verification passed.");
