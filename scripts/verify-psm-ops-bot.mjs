import { existsSync, readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { join, resolve } from "node:path";
import {
  assertFile as sharedAssertFile,
  assertManifestPaths,
  readJson as sharedReadJson,
  scanForSecretPatterns as sharedScanForSecretPatterns,
  textOf
} from "./lib/app-packet-verify.mjs";

const repoRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
const appRoot = join(repoRoot, "apps", "psm-ops-bot");
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

function profileBlock(profilesText, profileName) {
  const marker = `  - name: ${profileName}`;
  const start = profilesText.indexOf(marker);
  if (start === -1) return "";
  const next = profilesText.indexOf("\n  - name:", start + marker.length);
  return profilesText.slice(start, next === -1 ? undefined : next);
}

if (!existsSync(manifestPath)) {
  fail("Missing apps/psm-ops-bot/app.manifest.json");
} else {
  const manifest = readJson(manifestPath);
  if (manifest) {
    if (manifest.profile_name !== "psmopsbot") fail("Manifest profile_name must be psmopsbot");
    if (manifest.secrets_copied !== false) fail("Manifest secrets_copied must be false");
    if (manifest.rollout_stage !== "Slack open-channel enabled") fail("Manifest rollout_stage must be Slack open-channel enabled");
    if (manifest.cloud?.vm_name !== "hermes-psm-ops-bot-poc") fail("Manifest cloud vm_name must be hermes-psm-ops-bot-poc");
    if (manifest.jira?.task_owner_field !== "PS Team") fail("Manifest jira.task_owner_field must be PS Team");
    if (manifest.jira?.task_owner_field_id !== "customfield_10876") fail("Manifest jira.task_owner_field_id must be customfield_10876");
    assertManifestPaths(appRoot, manifest.paths || {}, fail);

    const expectedJiraTools = [
      "validate_jira_configuration",
      "resolve_slack_user_identity",
      "list_my_pco_tasks",
      "find_ticket_by_slack_thread",
      "create_ps_wee_intake_ticket",
      "append_ps_wee_ticket_update",
      "mark_ps_wee_ticket_ready",
      "draft_pco_task",
      "create_approved_pco_task",
      "transition_pco_task",
      "add_internal_pco_comment",
      "set_pco_assignee",
      "set_pco_ps_team",
      "set_pco_reminder",
      "list_due_pco_reminders"
    ];
    const actualJiraTools = manifest.mcp?.psm_jira?.expected_tools || [];
    for (const tool of expectedJiraTools) {
      if (!actualJiraTools.includes(tool)) fail(`Manifest missing psm_jira tool: ${tool}`);
    }
    for (const tool of actualJiraTools) {
      if (!expectedJiraTools.includes(tool)) fail(`Manifest has unexpected psm_jira tool: ${tool}`);
    }

    const expectedC360Tools = [
      "search_c360_customers",
      "get_c360_account_context",
      "ask_c360_customer_context"
    ];
    const actualC360Tools = manifest.mcp?.psm_c360?.expected_tools || [];
    for (const tool of expectedC360Tools) {
      if (!actualC360Tools.includes(tool)) fail(`Manifest missing psm_c360 tool: ${tool}`);
    }
    for (const tool of actualC360Tools) {
      if (!expectedC360Tools.includes(tool)) fail(`Manifest has unexpected psm_c360 tool: ${tool}`);
    }
  }
}

const filesToScan = [
  "README.md",
  "AGENTS.md",
  "app.manifest.json",
  "profile/SOUL.md",
  "profile/config.template.yaml",
  "skills/psm-ops-bot/SKILL.md",
  "skills/psm-ops-bot/references/jira-field-contract.md",
  "skills/psm-ops-bot/references/regression-cases.md",
  "runtime/slack.md",
  "runtime/jira.md",
  "runtime/c360.md",
  "runtime/health-checks.md",
  "runtime/check-health.sh",
  "runtime/check-cloud-heartbeat.sh",
  "runtime/audit-live-profile.sh",
  "runtime/mcp/psm_jira_server.py",
  "runtime/mcp/psm_c360_server.py",
  "deploy/gce-onboarding-runbook.md",
  "tests/regression-cases.md"
];

for (const relPath of filesToScan) {
  assertFile(relPath);
  scanForSecretPatterns(relPath);
}

const configText = textOf(appRoot, "profile/config.template.yaml");
for (const requiredText of [
  "psmopsbot",
  "SLACK_ALLOWED_CHANNELS empty",
  'provider: "anthropic"',
  'default: "claude-sonnet-4-6"',
  "max_parallel_jobs: 1",
  "PSM_OPS_JIRA_SERVICE_DESK_ID",
  "PSM_OPS_JIRA_FIELD_REMINDER_AT",
  "CUSTOMER360_INTERNAL_API_TOKEN",
  "SLACK_BOT_TOKEN",
  "resolve_slack_user_identity",
  "create_ps_wee_intake_ticket",
  "find_ticket_by_slack_thread",
  "append_ps_wee_ticket_update",
  "mark_ps_wee_ticket_ready",
  "set_pco_ps_team",
  "psm_jira",
  "psm_c360"
]) {
  if (!configText.includes(requiredText)) fail(`config.template.yaml missing required text: ${requiredText}`);
}

const soulText = textOf(appRoot, "profile/SOUL.md");
for (const requiredText of [
  "Task creation is preview first",
  "Status transitions, Jira assignee updates, internal comments, and due-date reminder updates may execute directly",
  "PS Team = CS Duty",
  "customer reached out",
  "task list",
  "Calendar",
  "Slack profile email/name",
  "all customers",
  "Do not use personal `customer360_session` cookies",
  "PSM Ops automation:"
]) {
  if (!soulText.includes(requiredText)) fail(`SOUL.md missing required text: ${requiredText}`);
}

const skillText = textOf(appRoot, "skills/psm-ops-bot/SKILL.md");
for (const requiredText of [
  "PCO is the only task system",
  "PS WEE",
  "create_ps_wee_intake_ticket",
  "resolve_slack_user_identity",
  "customer reached out",
  "task list",
  "Slack thread permalink is the V1 idempotency key",
  "Task creation must be preview first",
  "Caller task ownership is Jira `PS Team`",
  "set_pco_assignee",
  "set_pco_ps_team",
  "Public customer-visible comments are blocked",
  "Reminder source of truth is Jira",
  "Use `search_c360_customers`"
]) {
  if (!skillText.includes(requiredText)) fail(`Skill missing required text: ${requiredText}`);
}

const jiraMcpText = textOf(appRoot, "runtime/mcp/psm_jira_server.py");
for (const requiredText of [
  "@mcp.tool()",
  "validate_jira_configuration",
  "resolve_slack_user_identity",
  "list_my_pco_tasks",
  "find_ticket_by_slack_thread",
  "create_ps_wee_intake_ticket",
  "append_ps_wee_ticket_update",
  "mark_ps_wee_ticket_ready",
  "create_approved_pco_task",
  "transition_pco_task",
  "add_internal_pco_comment",
  "set_pco_assignee",
  "set_pco_ps_team",
  "set_pco_reminder",
  "list_due_pco_reminders",
  "PSM_OPS_JIRA_FIELD_REMINDER_AT",
  "users.list",
  "PS Team",
  "Public customer-visible comments are disabled"
]) {
  if (!jiraMcpText.includes(requiredText)) fail(`psm_jira_server.py missing required text: ${requiredText}`);
}

const c360McpText = textOf(appRoot, "runtime/mcp/psm_c360_server.py");
for (const requiredText of [
  "search_c360_customers",
  "get_c360_account_context",
  "ask_c360_customer_context",
  "CUSTOMER360_INTERNAL_API_TOKEN",
  "Authorization",
  "searched_variants",
  "missing_mapping",
  "No Customer 360 customer/org mapping"
]) {
  if (!c360McpText.includes(requiredText)) fail(`psm_c360_server.py missing required text: ${requiredText}`);
}

const profilesText = readFileSync(join(repoRoot, "ops", "hermes", "profiles.yaml"), "utf8");
const nurtureProfileBlock = profileBlock(profilesText, "nurtureanysalesbot");
if (!nurtureProfileBlock) {
  fail("ops/hermes/profiles.yaml missing nurtureanysalesbot profile");
} else if (/ps\s+wee\s+manager/i.test(nurtureProfileBlock)) {
  fail("nurtureanysalesbot must not claim PS Wee Manager workflow aliases");
}

const psmOpsProfileBlock = profileBlock(profilesText, "psmopsbot");
if (!psmOpsProfileBlock) {
  fail("ops/hermes/profiles.yaml missing psmopsbot profile");
} else {
  for (const requiredText of [
    "display_name: PSM Ops Bot",
    "canonical_profile: psmopsbot",
    "live_profile: psmopsbot",
    "workflow_aliases: [PS WEE, PS Wee Manager, PSM manager ops bot]",
    "app_packet: apps/psm-ops-bot",
    "deploy_host: hermes-psm-ops-bot-poc",
    "systemd_unit: hermes-gateway-psmopsbot.service",
    "bot_name: ps_wee_manager",
    "open_channel_mode: true",
    "psm_jira: 14",
    "psm_c360: 3",
    "psmopsbot due-date reminders",
    "psmopsbot local cloud heartbeat"
  ]) {
    if (!psmOpsProfileBlock.includes(requiredText)) {
      fail(`psmopsbot profile missing required text: ${requiredText}`);
    }
  }
}

for (const [relPath, text] of [
  ["README.md", readFileSync(join(repoRoot, "README.md"), "utf8")],
  ["ops/hermes/channels.md", readFileSync(join(repoRoot, "ops", "hermes", "channels.md"), "utf8")]
]) {
  if (!/PS WEE[\s\S]*psmopsbot|psmopsbot[\s\S]*PS WEE/i.test(text)) {
    fail(`${relPath} must document PS WEE as psmopsbot`);
  }
  if (/ps\s+wee\s+manager[^.\n]*(?:uses?|are)\s+NurtureAny|ps\s+wee\s+manager[^.\n]*NurtureAny\s+workflows/i.test(text)) {
    fail(`${relPath} must not route PS Wee Manager to NurtureAny`);
  }
}

const runbookText = textOf(appRoot, "deploy/gce-onboarding-runbook.md");
for (const requiredText of [
  "hermes-psm-ops-bot-poc",
  "staffany-warehouse",
  "asia-southeast1",
  "hermes-gateway-psmopsbot.service",
  "Secret Manager",
  "public/open channels"
]) {
  if (!runbookText.includes(requiredText)) fail(`GCE runbook missing required text: ${requiredText}`);
}

const heartbeatText = textOf(appRoot, "runtime/check-cloud-heartbeat.sh");
for (const requiredText of [
  "hermes-gateway-psmopsbot.service",
  "psmopsbot due-date reminders",
  "psmopsbot local cloud heartbeat",
  "EXPECTED_ENABLED_CRON_COUNT",
  "Asia/Singapore",
  "systemctl --user is-active",
  "systemctl --user is-enabled"
]) {
  if (!heartbeatText.includes(requiredText)) fail(`Cloud heartbeat script missing required text: ${requiredText}`);
}

const shellCheck = spawnSync("bash", [
  "-n",
  join(appRoot, "runtime", "check-health.sh"),
  join(appRoot, "runtime", "check-cloud-heartbeat.sh"),
  join(appRoot, "runtime", "audit-live-profile.sh")
], {
  cwd: repoRoot,
  encoding: "utf8"
});
if (shellCheck.status !== 0) {
  fail(`Shell syntax check failed: ${shellCheck.stderr || shellCheck.stdout}`);
}

const pyCompile = spawnSync("python3", [
  "-m",
  "py_compile",
  join(appRoot, "runtime/mcp/psm_jira_server.py"),
  join(appRoot, "runtime/mcp/psm_c360_server.py")
], {
  cwd: repoRoot,
  env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
  encoding: "utf8"
});
if (pyCompile.status !== 0) {
  fail(`Python MCP compile failed: ${pyCompile.stderr || pyCompile.stdout}`);
}

const unitCheck = spawnSync("python3", [
  "-m",
  "unittest",
  "discover",
  "-s",
  join(appRoot, "runtime/mcp"),
  "-p",
  "test_psm_*_server.py"
], {
  cwd: repoRoot,
  env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
  encoding: "utf8"
});
if (unitCheck.status !== 0) {
  fail(`Python MCP unit tests failed: ${unitCheck.stderr || unitCheck.stdout}`);
}

if (failures.length > 0) {
  console.error("PSM Ops Bot packet verification failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log("PSM Ops Bot packet verification passed.");
