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
  "skills/product-ops-bot/SKILL.md",
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
  "max_parallel_jobs: 1"
]) {
  if (!configText.includes(requiredText)) fail(`config.template.yaml missing required text: ${requiredText}`);
}

const skillText = textOf(appRoot, "skills/product-ops-bot/SKILL.md");
for (const requiredText of [
  "require explicit `run`",
  "write actions",
  "Answer:",
  "Confidence: <verified | needs-check | blocked>"
]) {
  if (!skillText.includes(requiredText)) fail(`Skill missing required text: ${requiredText}`);
}

const healthText = textOf(appRoot, "runtime/health-checks.md");
if (!healthText.includes("npm run product-ops-bot:verify")) {
  fail("runtime/health-checks.md must include product-ops-bot verify command");
}

if (failures.length > 0) {
  console.error("Product Ops Bot packet verification failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log("Product Ops Bot packet verification passed.");
