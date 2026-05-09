import { existsSync, readFileSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, resolve } from "node:path";

const repoRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
const appRoot = join(repoRoot, "apps", "nurtureany-sales-bot");
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

function textOf(relPath) {
  const path = join(appRoot, relPath);
  if (!existsSync(path) || !statSync(path).isFile()) return "";
  return readFileSync(path, "utf8");
}

function scanForSecretPatterns(relPath) {
  const text = textOf(relPath);
  if (!text) return;
  const patterns = [
    [/xox[baprs]-[A-Za-z0-9-]+/, "Slack token"],
    [/xapp-[A-Za-z0-9-]+/, "Slack app token"],
    [/sk-[A-Za-z0-9_-]{20,}/, "OpenAI-style API key"],
    [/pat-[a-z0-9]+-[A-Za-z0-9-]{20,}/, "HubSpot private app token"],
    [/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/, "private key"],
    [/AIza[0-9A-Za-z_-]{20,}/, "Google API key"]
  ];
  for (const [pattern, label] of patterns) {
    if (pattern.test(text)) fail(`${label} pattern found in ${relPath}`);
  }
}

if (!existsSync(manifestPath)) {
  fail("Missing apps/nurtureany-sales-bot/app.manifest.json");
} else {
  const manifest = readJson(manifestPath);
  if (manifest) {
    if (manifest.profile_name !== "nurtureanysalesbot") fail("Manifest profile_name must be nurtureanysalesbot");
    if (manifest.secrets_copied !== false) fail("Manifest secrets_copied must be false");
    if (manifest.external_message_sending !== false) fail("Manifest external_message_sending must be false");
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

    const paths = manifest.paths || {};
    for (const value of Object.values(paths)) {
      if (Array.isArray(value)) {
        for (const relPath of value) assertFile(relPath);
      } else {
        assertFile(value);
      }
    }

    const expectedReadTools = [
      "list_my_target_accounts",
      "list_team_target_accounts",
      "get_account_context",
      "score_nurture_accounts",
      "find_contact_gaps",
      "draft_nurture_message"
    ];
    const readTools = manifest.tools?.read || [];
    for (const tool of expectedReadTools) {
      if (!readTools.includes(tool)) fail(`Manifest missing read tool: ${tool}`);
    }
    if (!manifest.tools?.preview?.includes("plan_hubspot_writeback")) {
      fail("Manifest missing preview tool: plan_hubspot_writeback");
    }
    for (const tool of ["create_hubspot_task", "append_hubspot_note", "update_nurture_fields"]) {
      if (!manifest.tools?.mutation_requires_explicit_approval?.includes(tool)) {
        fail(`Manifest missing approval-gated mutation tool: ${tool}`);
      }
    }
  }
}

const filesToScan = [
  "AGENTS.md",
  "README.md",
  "profile/SOUL.md",
  "profile/config.template.yaml",
  "skills/nurtureany-sales-bot/SKILL.md",
  "skills/nurtureany-sales-bot/references/hubspot-fields.md",
  "skills/nurtureany-sales-bot/references/playbooks.md",
  "skills/nurtureany-sales-bot/references/regression-cases.md",
  "runtime/slack.md",
  "runtime/hubspot.md",
  "runtime/mcp/hubspot_nurtureany_server.py",
  "runtime/bigquery.md",
  "runtime/luma.md",
  "runtime/health-checks.md",
  "tests/regression-cases.md"
];

for (const relPath of filesToScan) {
  assertFile(relPath);
  scanForSecretPatterns(relPath);
}

const configText = textOf("profile/config.template.yaml");
for (const text of [
  "Singapore",
  "Malaysia",
  "Indonesia",
  "eugene@staffany.com",
  "kaiyi@staffany.com",
  "kerren.fong@staffany.com",
  "sarah@staffany.com",
  "list_my_target_accounts",
  "list_team_target_accounts",
  "plan_hubspot_writeback"
]) {
  if (!configText.includes(text)) fail(`config.template.yaml missing required text: ${text}`);
}

const soulText = textOf("profile/SOUL.md");
for (const text of ["plan-first", "run", "explicit approval", "Never auto-send", "Confidence"]) {
  if (!soulText.includes(text)) fail(`SOUL.md missing required safety/contract text: ${text}`);
}

const skillText = textOf("skills/nurtureany-sales-bot/SKILL.md");
for (const text of [
  "hs_is_target_account",
  "company_country",
  "hubspot_owner_id",
  "Nurture-ready enriched",
  "Do not use Honcho",
  "Confidence: <verified | needs-check | blocked>"
]) {
  if (!skillText.includes(text)) fail(`SKILL.md missing required text: ${text}`);
}

if (failures.length > 0) {
  console.error("NurtureAny Sales Bot packet verification failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log("NurtureAny Sales Bot packet verification passed.");
