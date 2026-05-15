import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, resolve } from "node:path";

const repoRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
const failures = [];

function fail(message) {
  failures.push(message);
}

function readText(relPath) {
  const path = join(repoRoot, relPath);
  if (!existsSync(path)) {
    fail(`Missing ${relPath}`);
    return "";
  }
  return readFileSync(path, "utf8");
}

function readJson(relPath) {
  const text = readText(relPath);
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch (error) {
    fail(`${relPath} is invalid JSON: ${error.message}`);
    return null;
  }
}

const packageJson = readJson("package.json");
if (packageJson) {
  if (packageJson.scripts?.["hermes-bot:onboard-access"] !== "node scripts/onboard-hermes-bot-access.mjs") {
    fail("package.json must expose hermes-bot:onboard-access");
  }
  if (packageJson.scripts?.["hermes-bot:onboard-access:test"] !== "node --test scripts/onboard-hermes-bot-access.test.mjs") {
    fail("package.json must expose hermes-bot:onboard-access:test");
  }
  if (packageJson.scripts?.["hermes-bot:onboard-access:verify"] !== "node scripts/verify-hermes-bot-onboarding.mjs") {
    fail("package.json must expose hermes-bot:onboard-access:verify");
  }
}

const scriptText = readText("scripts/onboard-hermes-bot-access.mjs");
for (const requiredText of [
  "hermes-data-bot-poc",
  "nurtureany-sales-bot-prod",
  "hermes-psm-ops-bot-poc",
  "staffanydatabot",
  "nurtureanysalesbot",
  "psmopsbot",
  "launchbot",
  "roles/compute.viewer",
  "roles/iap.tunnelResourceAccessor",
  "roles/compute.osLogin",
  "roles/compute.osAdminLogin",
  "roles/iam.serviceAccountUser",
  "hermesBotVmSshMetadataWriter",
  "compute.instances.setMetadata",
  "iam.serviceAccounts.actAs",
  "policy-troubleshoot",
  "add-iam-policy-binding",
]) {
  if (!scriptText.includes(requiredText)) fail(`onboarding script missing required text: ${requiredText}`);
}

for (const forbiddenGrant of [
  '"roles/editor"',
  '"roles/owner"',
  '"roles/compute.admin"',
  '"roles/compute.instanceAdmin"',
  '"roles/secretmanager.secretAccessor"',
]) {
  if (scriptText.includes(forbiddenGrant)) {
    fail(`onboarding script must not grant ${forbiddenGrant}`);
  }
}

const testText = readText("scripts/onboard-hermes-bot-access.test.mjs");
for (const requiredText of [
  "plans only PSM Ops VM",
  "dedupes shared VM",
  "does not include mutating gcloud commands without apply",
  "refuses broad or secret-bearing roles",
]) {
  if (!testText.includes(requiredText)) fail(`onboarding test missing coverage: ${requiredText}`);
}

const runbookText = readText("docs/hermes-bot-deploy-access.md");
for (const requiredText of [
  "Source-code access is separate from VM deploy access",
  "Runtime secrets are not part of this onboarding script",
  "compute.instances.setMetadata",
  "roles/iam.serviceAccountUser",
  "hermesBotVmSshMetadataWriter",
  "roles/compute.admin",
  "roles/editor",
  "roles/owner",
  "Secret Manager",
]) {
  if (!runbookText.includes(requiredText)) fail(`deploy access runbook missing required text: ${requiredText}`);
}

if (failures.length) {
  console.error("Hermes bot onboarding verification failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log("Hermes bot onboarding verification passed.");
