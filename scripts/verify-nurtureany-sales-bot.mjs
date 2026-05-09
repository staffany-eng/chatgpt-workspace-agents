import { existsSync, readFileSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";

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
    if (manifest.model !== "claude-sonnet-4-6") fail("Manifest model must be claude-sonnet-4-6");
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
      "draft_nurture_message",
      "search_lusha_decision_maker_candidates",
      "get_lusha_credit_usage"
    ];
    const readTools = manifest.tools?.read || [];
    for (const tool of expectedReadTools) {
      if (!readTools.includes(tool)) fail(`Manifest missing read tool: ${tool}`);
    }
    if (!manifest.tools?.preview?.includes("plan_hubspot_writeback")) {
      fail("Manifest missing preview tool: plan_hubspot_writeback");
    }
    if (!manifest.tools?.approval_gated_enrichment?.includes("reveal_lusha_contact_details")) {
      fail("Manifest missing approval-gated enrichment tool: reveal_lusha_contact_details");
    }
    for (const tool of ["create_hubspot_task", "append_hubspot_note", "update_nurture_fields"]) {
      if (!manifest.tools?.mutation_requires_explicit_approval?.includes(tool)) {
        fail(`Manifest missing approval-gated mutation tool: ${tool}`);
      }
    }
    if (manifest.lusha?.auth_env_var !== "LUSHA_API_KEY") fail("Manifest missing LUSHA_API_KEY auth env var");
    if (manifest.lusha?.max_search_companies !== 5) fail("Manifest Lusha max_search_companies must be 5");
    if (manifest.lusha?.max_candidates_per_company !== 5) fail("Manifest Lusha max_candidates_per_company must be 5");
    if (manifest.lusha?.max_reveal_contacts !== 3) fail("Manifest Lusha max_reveal_contacts must be 3");
    if (manifest.lusha?.selected_pii_in_slack !== true) fail("Manifest Lusha selected_pii_in_slack must be true");
    if (manifest.lusha?.bulk_contact_exports !== false) fail("Manifest Lusha bulk_contact_exports must be false");
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
  "runtime/lusha.md",
  "runtime/mcp/lusha_nurtureany_server.py",
  "runtime/mcp/test_lusha_nurtureany_server.py",
  "runtime/health-checks.md",
  "tests/regression-cases.md"
];

for (const relPath of filesToScan) {
  assertFile(relPath);
  scanForSecretPatterns(relPath);
}

const configText = textOf("profile/config.template.yaml");
if (!configText.includes('provider: "anthropic"')) fail("config.template.yaml must set model.provider to anthropic");
if (!configText.includes('default: "claude-sonnet-4-6"')) fail("config.template.yaml must set model.default to claude-sonnet-4-6");
if (configText.includes("OPENAI_API_KEY")) fail("config.template.yaml must not configure OpenAI API key routing");
if (configText.includes('base_url: "https://api.openai.com/v1"')) fail("config.template.yaml must not configure OpenAI API base_url");
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
  "plan_hubspot_writeback",
  "lusha_nurtureany",
  "LUSHA_API_KEY",
  "search_lusha_decision_maker_candidates",
  "reveal_lusha_contact_details",
  "get_lusha_credit_usage"
]) {
  if (!configText.includes(text)) fail(`config.template.yaml missing required text: ${text}`);
}

const soulText = textOf("profile/SOUL.md");
for (const text of ["plan-first", "run", "explicit approval", "Never auto-send", "Confidence", "credit_report", "approval_marker", "reveal_phones"]) {
  if (!soulText.includes(text)) fail(`SOUL.md missing required safety/contract text: ${text}`);
}

const skillText = textOf("skills/nurtureany-sales-bot/SKILL.md");
for (const text of [
  "hs_is_target_account",
  "company_country",
  "hubspot_owner_id",
  "Nurture-ready enriched",
  "Do not use Honcho",
  "Confidence: <verified | needs-check | blocked>",
  "search_lusha_decision_maker_candidates",
  "reveal_lusha_contact_details",
  "get_lusha_credit_usage",
  "credit_report",
  "approval_marker",
  "revealEmails",
  "revealPhones"
]) {
  if (!skillText.includes(text)) fail(`SKILL.md missing required text: ${text}`);
}

const lushaText = textOf("runtime/lusha.md");
for (const text of [
  "POST /prospecting/contact/search",
  "POST /prospecting/contact/enrich",
  "GET /account/usage",
  "credit_report",
  "approval_marker",
  "revealEmails",
  "revealPhones",
  "15s hard timeout",
  "Selected contact PII",
  "No actual HubSpot mutation"
]) {
  if (!lushaText.includes(text)) fail(`runtime/lusha.md missing required text: ${text}`);
}

const lushaServerText = textOf("runtime/mcp/lusha_nurtureany_server.py");
for (const text of [
  "LUSHA_API_KEY",
  "LUSHA_TIMEOUT_SECONDS = 15",
  "MAX_SEARCH_COMPANIES = 5",
  "MAX_CANDIDATES_PER_COMPANY = 5",
  "MAX_REVEAL_CONTACTS = 3",
  "revealEmails",
  "revealPhones",
  "credit_report",
  "plan_hubspot_writeback"
]) {
  if (!lushaServerText.includes(text)) fail(`runtime/mcp/lusha_nurtureany_server.py missing required text: ${text}`);
}

const compileCheck = spawnSync("python3", ["-m", "py_compile", join(appRoot, "runtime/mcp/lusha_nurtureany_server.py")], {
  encoding: "utf8"
});
if (compileCheck.status !== 0) {
  fail(`Python compile failed for Lusha MCP: ${(compileCheck.stderr || compileCheck.stdout).trim()}`);
}

const unitCheck = spawnSync("python3", ["-m", "unittest", "apps/nurtureany-sales-bot/runtime/mcp/test_lusha_nurtureany_server.py"], {
  cwd: repoRoot,
  encoding: "utf8"
});
if (unitCheck.status !== 0) {
  fail(`Python unit tests failed for Lusha MCP: ${(unitCheck.stderr || unitCheck.stdout).trim()}`);
}

if (failures.length > 0) {
  console.error("NurtureAny Sales Bot packet verification failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log("NurtureAny Sales Bot packet verification passed.");
