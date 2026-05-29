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
      "validate_roi_jira_configuration",
      "resolve_slack_user_identity",
      "classify_roi_ticket_request",
      "find_engineering_issue",
      "resolve_customer_channel_org",
      "list_my_pco_tasks",
      "search_pco_tickets",
      "find_duplicate_pco_candidates",
      "find_ticket_by_slack_thread",
      "find_roi_ticket_by_slack_thread",
      "create_roi_ticket_from_slack",
      "create_or_link_pco_roi_tracker",
      "create_ps_wee_intake_ticket",
      "attach_aa_selfie_to_thread",
      "verify_drive_oauth",
      "append_ps_wee_ticket_update",
      "draft_pco_task",
      "create_approved_pco_task",
      "transition_pco_task",
      "add_internal_pco_comment",
      "set_pco_assignee",
      "set_pco_ps_team",
      "link_pco_to_engineering_issue",
      "link_pco_to_pco_issue",
      "merge_pco_tickets",
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

    const expectedGoogleCalendarTools = [
      "read_customer_calendar_context"
    ];
    const actualGoogleCalendarTools = manifest.mcp?.psm_google_calendar?.expected_tools || [];
    for (const tool of expectedGoogleCalendarTools) {
      if (!actualGoogleCalendarTools.includes(tool)) fail(`Manifest missing psm_google_calendar tool: ${tool}`);
    }
    for (const tool of actualGoogleCalendarTools) {
      if (!expectedGoogleCalendarTools.includes(tool)) fail(`Manifest has unexpected psm_google_calendar tool: ${tool}`);
    }
    if ((manifest.google_calendar?.allowed_tools || []).includes("list_google_calendar_events")) {
      fail("Manifest must not expose broad list_google_calendar_events as an allowed Google Calendar tool");
    }
    if (manifest.google_calendar?.account_email !== "team@staffany.com") fail("Manifest Google Calendar account_email must be team@staffany.com");
    if (manifest.google_calendar?.access_mode !== "team_oauth_shared_calendar") {
      fail("Manifest Google Calendar access_mode must be team_oauth_shared_calendar");
    }
    if (manifest.google_calendar?.service_account !== false) fail("Manifest Google Calendar must not claim service_account=true");
    if (manifest.google_calendar?.required_scope !== "https://www.googleapis.com/auth/calendar.readonly") {
      fail("Manifest Google Calendar required_scope must be calendar.readonly");
    }
    if (manifest.google_calendar?.read_only !== true) fail("Manifest Google Calendar read_only must be true");
    if (manifest.google_calendar?.max_calendars !== 5) fail("Manifest Google Calendar max_calendars must be 5");
    if (manifest.google_calendar?.max_events_per_calendar !== 50) {
      fail("Manifest Google Calendar max_events_per_calendar must be 50");
    }
    if (manifest.google_calendar?.event_mutations !== false) fail("Manifest Google Calendar event_mutations must be false");
    if (manifest.google_calendar?.attendee_exports !== false) fail("Manifest Google Calendar attendee_exports must be false");
    if (manifest.google_calendar?.private_field_exports !== false) {
      fail("Manifest Google Calendar private_field_exports must be false");
    }
    const expectedSlackScopes = [
      "app_mentions:read",
      "channels:read",
      "channels:history",
      "channels:join",
      "chat:write",
      "users:read",
      "users:read.email"
    ];
    const actualSlackScopes = manifest.slack?.required_bot_scopes || [];
    for (const scope of expectedSlackScopes) {
      if (!actualSlackScopes.includes(scope)) fail(`Manifest missing Slack bot scope: ${scope}`);
    }
    if (manifest.slack?.allowed_channels_expected_empty !== true) {
      fail("Manifest Slack contract must require empty SLACK_ALLOWED_CHANNELS for open public-channel mode");
    }
    if (manifest.slack?.join_public_channels_script !== "runtime/scripts/psm_ops_join_public_channels.py") {
      fail("Manifest Slack contract must point to psm_ops_join_public_channels.py");
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
  "skills/psm-ops-bot/references/customer-channel-candidates.md",
  "skills/psm-ops-bot/references/regression-cases.md",
  "runtime/slack.md",
  "runtime/jira.md",
  "runtime/c360.md",
  "runtime/google-calendar.md",
  "runtime/health-checks.md",
  "runtime/check-health.sh",
  "runtime/check-cloud-heartbeat.sh",
  "runtime/audit-live-profile.sh",
  "runtime/smoke-rock-productions-c360.sh",
  "runtime/psm_ops_adoption_digest.py",
  "runtime/scripts/psm_ops_due_date_reminders.py",
  "runtime/scripts/psm_ops_pco_assignment_hygiene.py",
  "runtime/scripts/psm_ops_roi_tracker_sync.py",
  "runtime/scripts/psm_ops_churn_reporting_chase.py",
  "runtime/sql/psm_ops_churn_projection_dashboard_292.sql",
  "runtime/scripts/psm_ops_join_public_channels.py",
  "runtime/mcp/psm_slack_notifier.py",
  "runtime/mcp/psm_jira_server.py",
  "runtime/mcp/psm_c360_server.py",
  "runtime/mcp/google_oauth.py",
  "runtime/mcp/psm_google_calendar_server.py",
  "runtime/hooks/psm-ops-adoption-telemetry/HOOK.yaml",
  "runtime/hooks/psm-ops-adoption-telemetry/handler.py",
  "runtime/hooks/psm-ops-mention-guard/HOOK.yaml",
  "runtime/hooks/psm-ops-mention-guard/handler.py",
  "runtime/hooks/psm-ops-mention-guard/test_handler.py",
  "runtime/test_psm_ops_due_date_reminders.py",
  "runtime/test_psm_ops_pco_assignment_hygiene.py",
  "runtime/test_psm_ops_roi_tracker_sync.py",
  "runtime/test_psm_ops_churn_reporting_chase.py",
  "runtime/test_psm_ops_join_public_channels.py",
  "deploy/gce-onboarding-runbook.md",
  "tests/regression-cases.md",
  "tests/prompt-evals.json"
];

for (const relPath of filesToScan) {
  assertFile(relPath);
  scanForSecretPatterns(relPath);
}

if (!existsSync(packageJsonPath)) {
  fail("Missing package.json");
} else {
  const packageJson = readJson(packageJsonPath);
  if (packageJson?.scripts?.["psm-ops-bot:deploy"] !== "node scripts/deploy-psm-ops-bot.mjs") {
    fail("package.json must expose psm-ops-bot:deploy");
  }
}

const deployScriptRelPath = "scripts/deploy-psm-ops-bot.mjs";
const deployScriptPath = join(repoRoot, deployScriptRelPath);
if (!existsSync(deployScriptPath)) {
  fail("Missing scripts/deploy-psm-ops-bot.mjs");
} else {
  const deployScriptText = readFileSync(deployScriptPath, "utf8");
  for (const requiredText of [
    'vm: "hermes-psm-ops-bot-poc"',
    'profile: "psmopsbot"',
    "psm-ops-origin-main-${deploySha}.tar.gz",
    "psm-ops-origin-main-${deploySha}.sha",
    "deploy_sha_expected",
    "sha-mismatch",
    "scripts/verify-psm-ops-bot.mjs",
    "apps/psm-ops-bot",
    "source/psm-ops-bot",
    "skills/psm-ops-bot",
    "psmopsbot-check-health.sh",
    "psmopsbot-check-cloud-heartbeat.sh",
    "psmopsbot-audit-live-profile.sh",
    "psmopsbot-rock-productions-c360-smoke.sh",
    "psm_ops_adoption_digest.py",
    "psm_ops_due_date_reminders.py",
    "psm_ops_due_date_reminders_eod.py",
    "psm_ops_pco_assignment_hygiene.py",
    "psm_ops_join_public_channels.py",
    "psm_ops_churn_reporting_chase.py",
    "runtime/sql",
    "psm_ops_churn_projection_dashboard_292.sql",
    "psm-ops-adoption-telemetry",
    "psm-ops-mention-guard",
    "smoke-rock-productions-c360.sh",
    "rock_productions_c360",
    "hermes-gateway-$profile_name.service",
    "PSM_OPS_SOURCE_DIR",
    "PSM_OPS_DEPLOY_GATEWAY_SETTLE_SECONDS",
    "systemctl --user reset-failed",
    'remote_verify="skipped:node-not-found"',
    "FORBIDDEN_RUNTIME_STATE_LABELS"
  ]) {
    if (!deployScriptText.includes(requiredText)) fail(`${deployScriptRelPath} missing required text: ${requiredText}`);
  }
  if (/SLACK_BOT_TOKEN=.*xox|JIRA_API_TOKEN=.*[A-Za-z0-9_-]{20,}|CUSTOMER360_INTERNAL_API_TOKEN=.*[A-Za-z0-9_-]{20,}/.test(deployScriptText)) {
    fail(`${deployScriptRelPath} appears to contain secret material`);
  }
}

const configText = textOf(appRoot, "profile/config.template.yaml");
if (configText.includes('      - "list_google_calendar_events"')) {
  fail("config.template.yaml must not expose broad list_google_calendar_events");
}

const slackRuntimeText = textOf(appRoot, "runtime/slack.md");
for (const requiredText of [
  "channels:join",
  "conversations.join",
  "psm_ops_join_public_channels.py --dry-run",
  "psm_ops_join_public_channels.py --apply",
  "Do not use Kai Yi's user token or the Slack connector to invite or post as a workaround"
]) {
  if (!slackRuntimeText.includes(requiredText)) fail(`runtime/slack.md missing required text: ${requiredText}`);
}
for (const requiredText of [
  "psmopsbot",
  "SLACK_ALLOWED_CHANNELS empty",
  'provider: "anthropic"',
  'default: "claude-sonnet-4-6"',
  "title_generation:",
  'model: "claude-haiku-4-5"',
  "timeout: 10",
  "max_parallel_jobs: 1",
  "PSM_OPS_JIRA_SERVICE_DESK_ID",
  "PSM_OPS_JIRA_FIELD_REMINDER_AT",
  "PSM_OPS_ROI_JIRA_PROJECT_KEY",
  "PSM_OPS_ROI_JIRA_REQUEST_TYPE_ID",
  "PSM_OPS_ROI_JIRA_FIELD_REQUESTER",
  "PSM_OPS_ROI_JIRA_FIELD_STAFFANY_ORGS",
  "psm-ops-bot-roi-jira-env",
  "CUSTOMER360_INTERNAL_API_TOKEN",
  "SLACK_BOT_TOKEN",
  'allow_bots: "mentions"',
  "socket_raw_fallback: true",
  "resolve_slack_user_identity",
    "PSM_OPS_CENTRAL_SLACK_CHANNEL_ID",
    "PSM_OPS_ADOPTION_METRICS_PATH",
    "PSM_OPS_CHURN_REPORTING_CHANNEL_ID",
    "PSM_OPS_CHURN_REPORTING_BQ_PROJECT",
    "PSM_OPS_CHURN_REPORTING_BQ_DATASET",
    "PSM_OPS_REMINDER_MENTION_MAP_PATH",
    "assignment_hygiene:",
    "ps_leads.Josica",
    "central_digest_only",
    "classify_roi_ticket_request",
  "find_engineering_issue",
  "search_pco_tickets",
  "find_duplicate_pco_candidates",
  "validate_roi_jira_configuration",
  "create_roi_ticket_from_slack",
  "create_or_link_pco_roi_tracker",
  "ps-wee-roi-tracker",
  "find_roi_ticket_by_slack_thread",
  "resolve_customer_channel_org",
  "PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH",
  "create_ps_wee_intake_ticket",
  "find_ticket_by_slack_thread",
  "append_ps_wee_ticket_update",
  "set_pco_ps_team",
  "link_pco_to_engineering_issue",
  "merge_pco_tickets",
  "psm_jira",
  "psm_c360",
  "psm_google_calendar",
  "GOOGLE_CALENDAR_TOKEN_FILE",
  "GOOGLE_CALENDAR_CLIENT_SECRET_FILE",
  "team@staffany.com",
  "calendar.readonly"
]) {
  if (!configText.includes(requiredText)) fail(`config.template.yaml missing required text: ${requiredText}`);
}

const soulText = textOf(appRoot, "profile/SOUL.md");
for (const requiredText of [
  "Task creation is preview first",
  "ROI-direct requests are ticket-first",
  "pco_tracker_default=true",
  "create_or_link_pco_roi_tracker",
  "No bot, team, or team@staffany.com requester fallback is allowed",
  "Status transitions, Jira assignee updates, internal comments, and due-date reminder updates may execute directly",
  "PS Team = CS Duty",
  "customer reached out",
  "task list",
  "Calendar",
  "Slack poster",
  "Slack profile email/name",
  "Slack sender ID/mention",
  "past due date",
  "all customers",
  "Google Calendar",
  "team@staffany.com",
  "read_customer_calendar_context",
  "Do not use personal `customer360_session` cookies",
  "PSM Ops automation:"
]) {
  if (!soulText.includes(requiredText)) fail(`SOUL.md missing required text: ${requiredText}`);
}

const skillText = textOf(appRoot, "skills/psm-ops-bot/SKILL.md");
for (const requiredText of [
  "PCO is the only task system",
  "ROI is the source of truth for RevOps, BD Ops, NYSS, and ROI-board work",
  "PS WEE",
  "create_roi_ticket_from_slack",
  "create_or_link_pco_roi_tracker",
  "ps-wee-roi-tracker",
  "find_roi_ticket_by_slack_thread",
  "classify_roi_ticket_request",
  "create_ps_wee_intake_ticket",
  "resolve_slack_user_identity",
  "resolve_customer_channel_org",
  "customer-specific Slack channels",
  "customer-channel-candidates.md",
  "customer reached out",
  "task list",
  "Slack thread permalink is the V1 idempotency key",
  "Slack poster",
  "Task creation must be preview first",
  "Caller task ownership is Jira `PS Team`",
  "current Slack sender ID/mention",
  "past due date",
  "set_pco_assignee",
  "set_pco_ps_team",
  "find_engineering_issue",
  "link_pco_to_engineering_issue",
  "Public customer-visible comments are blocked",
  "Reminder source of truth is Jira",
  "Use `search_c360_customers`",
  "read_customer_calendar_context",
  "team@staffany.com",
  "calendar.readonly"
]) {
  if (!skillText.includes(requiredText)) fail(`Skill missing required text: ${requiredText}`);
}

const jiraMcpText = textOf(appRoot, "runtime/mcp/psm_jira_server.py");
for (const requiredText of [
  "@mcp.tool()",
  "validate_jira_configuration",
  "validate_roi_jira_configuration",
  "resolve_slack_user_identity",
  "classify_roi_ticket_request",
  "resolve_customer_channel_org",
  "PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH",
  "list_my_pco_tasks",
  "search_pco_tickets",
  "find_ticket_by_slack_thread",
  "find_roi_ticket_by_slack_thread",
  "create_roi_ticket_from_slack",
  "create_or_link_pco_roi_tracker",
  "ROI_TRACKER_LABEL",
  "pco_tracker_default",
  "create_ps_wee_intake_ticket",
  "append_ps_wee_ticket_update",
  "Slack poster",
  "create_approved_pco_task",
  "transition_pco_task",
  "add_internal_pco_comment",
  "set_pco_assignee",
  "set_pco_ps_team",
    "find_engineering_issue",
    "search_pco_tickets",
    "link_pco_to_engineering_issue",
  "set_pco_reminder",
  "list_due_pco_reminders",
  "PSM_OPS_JIRA_FIELD_REMINDER_AT",
  "users.list",
  "jira://request-types",
  "PSM_OPS_TODAY",
  "PSM_OPS_TIMEZONE",
  "post_ps_wee_audit",
  "ROI_TRIGGER_PATTERNS",
  "PSM_OPS_ROI_JIRA_REQUEST_TYPE_ID",
  "PSM_OPS_ROI_JIRA_FIELD_STAFFANY_ORGS",
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
  "X-Customer360-Internal-Token",
  "searched_variants",
  "missing_mapping",
  "No Customer 360 customer/org mapping"
]) {
  if (!c360McpText.includes(requiredText)) fail(`psm_c360_server.py missing required text: ${requiredText}`);
}

const rockProductionsSmokeText = textOf(appRoot, "runtime/smoke-rock-productions-c360.sh");
for (const requiredText of [
  "proj-cs-rockproductions",
  "rockproductions",
  "rock productions",
  "rock production",
  "Rock Productions Pte Ltd",
  "8051493928",
  "Rock Productions",
  "missing_mapping",
  "matchedValue",
  "StaffAny org",
  "c360:rock-productions:ok"
]) {
  if (!rockProductionsSmokeText.includes(requiredText)) {
    fail(`Rock Productions C360 smoke script missing required text: ${requiredText}`);
  }
}

const profilesText = readFileSync(join(repoRoot, "ops", "hermes", "profiles.yaml"), "utf8");
const nurtureProfileBlock = profileBlock(profilesText, "nurtureanysalesbot");
if (!nurtureProfileBlock) {
  fail("ops/hermes/profiles.yaml missing nurtureanysalesbot profile");
} else if (/ps\s+wee\s+manager/i.test(nurtureProfileBlock)) {
  fail("nurtureanysalesbot must not claim PS Wee Manager workflow aliases");
} else if (!nurtureProfileBlock.includes("local_profile_policy: cloud_only")) {
  fail("nurtureanysalesbot profile must be marked cloud-only");
} else if (nurtureProfileBlock.includes("launchd_label:")) {
  fail("nurtureanysalesbot profile must not define a Mac launchd_label");
}

const psmOpsProfileBlock = profileBlock(profilesText, "psmopsbot");
if (!psmOpsProfileBlock) {
  fail("ops/hermes/profiles.yaml missing psmopsbot profile");
} else {
  for (const requiredText of [
    "display_name: PSM Ops Bot",
    "canonical_profile: psmopsbot",
    "live_profile: psmopsbot",
    "workflow_aliases: [PS WEE, PS Wee Manager, PSM Manager Ops Bot, ps wee manager, ps wee, psm manager ops bot]",
    "app_packet: apps/psm-ops-bot",
    "deploy_host: hermes-psm-ops-bot-poc",
    "local_profile_policy: cloud_only",
    "systemd_unit: hermes-gateway-psmopsbot.service",
    "bot_name: ps_wee_manager",
    "open_channel_mode: true",
    "psm_jira: 28",
    "psm_c360: 3",
    "psmopsbot due-date reminders",
    "psmopsbot assignment hygiene",
    "psmopsbot due-date eod catch-up",
    "psmopsbot roi tracker sync",
    "psmopsbot churn reporting chase",
    "psm_ops_roi_tracker_sync.py",
    "psm_ops_churn_reporting_chase.py",
    "psm_ops_due_date_reminders.py",
    "psm_ops_pco_assignment_hygiene.py",
    "psm_ops_due_date_reminders_eod.py",
    "psmopsbot local cloud heartbeat",
    "psmopsbot adoption digest"
  ]) {
    if (!psmOpsProfileBlock.includes(requiredText)) {
      fail(`psmopsbot profile missing required text: ${requiredText}`);
    }
  }
  if (psmOpsProfileBlock.includes("launchd_label:")) {
    fail("psmopsbot profile must not define a Mac launchd_label");
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

const googleCalendarText = textOf(appRoot, "runtime/google-calendar.md");
for (const requiredText of [
  "team@staffany.com",
  "GOOGLE_CALENDAR_TOKEN_FILE",
  "https://www.googleapis.com/auth/calendar.readonly",
  "read_customer_calendar_context",
  "Max calendars per request: 5",
  "Max events per calendar: 50",
  "Do not create, update, delete, RSVP, invite, export attendees"
]) {
  if (!googleCalendarText.includes(requiredText)) fail(`runtime/google-calendar.md missing required text: ${requiredText}`);
}

const googleCalendarMcpText = textOf(appRoot, "runtime/mcp/psm_google_calendar_server.py");
for (const requiredText of [
  "GOOGLE_CALENDAR_TOKEN_FILE",
  "GOOGLE_CALENDAR_CLIENT_SECRET_FILE",
  "DEFAULT_ACCOUNT_EMAIL = \"team@staffany.com\"",
  "CALENDAR_READONLY_SCOPE",
  "MAX_CALENDARS = 5",
  "MAX_EVENTS_PER_CALENDAR = 50",
  "read_customer_calendar_context",
  "WEAK_CUSTOMER_QUERY_TOKENS",
  "team_oauth_shared_calendar",
  "blocked_calendar_ids",
  "No event mutations, attendee exports, descriptions, raw guest lists, or conference links"
]) {
  if (!googleCalendarMcpText.includes(requiredText)) fail(`psm_google_calendar_server.py missing required text: ${requiredText}`);
}

const notifierText = textOf(appRoot, "runtime/mcp/psm_slack_notifier.py");
for (const requiredText of [
  "SLACK_BOT_TOKEN",
  "PSM_OPS_CENTRAL_SLACK_CHANNEL_ID",
  "chat.postMessage",
  "conversations.replies",
  "PSM Ops automation:",
  "PSM_OPS_ADOPTION_METRICS_PATH"
]) {
  if (!notifierText.includes(requiredText)) fail(`psm_slack_notifier.py missing required text: ${requiredText}`);
}
for (const forbiddenText of ["SLACK_USER_TOKEN", "SLACK_TOKEN"]) {
  if (notifierText.includes(forbiddenText)) fail(`psm_slack_notifier.py must not use ${forbiddenText}`);
}

const hookText = textOf(appRoot, "runtime/hooks/psm-ops-adoption-telemetry/handler.py");
for (const requiredText of ["response_confidence", "psm-ops-adoption.jsonl", "PSM_OPS_ADOPTION_METRICS_PATH"]) {
  if (!hookText.includes(requiredText)) fail(`adoption hook handler missing required text: ${requiredText}`);
}

const runbookText = textOf(appRoot, "deploy/gce-onboarding-runbook.md");
for (const requiredText of [
  "hermes-psm-ops-bot-poc",
  "staffany-warehouse",
  "asia-southeast1",
  "hermes-gateway-psmopsbot.service",
  "Secret Manager",
  "public/open channels",
  "channels:join",
  "psm_ops_join_public_channels.py --apply",
  "pnpm psm-ops-bot:deploy",
  "psm-ops-origin-main-<sha>.tar.gz",
  "preserves runtime secrets/state",
  "GOOGLE_CALENDAR_TOKEN_FILE",
  "team@staffany.com",
  "psm_ops_roi_tracker_sync.py",
  "psm_ops_churn_reporting_chase.py",
  "psm_ops_pco_assignment_hygiene.py",
  "psmopsbot roi tracker sync"
]) {
  if (!runbookText.includes(requiredText)) fail(`GCE runbook missing required text: ${requiredText}`);
}

const heartbeatText = textOf(appRoot, "runtime/check-cloud-heartbeat.sh");
for (const requiredText of [
  "hermes-gateway-psmopsbot.service",
    "psmopsbot due-date reminders",
    "psmopsbot assignment hygiene",
    "psmopsbot due-date eod catch-up",
    "psmopsbot roi tracker sync",
    "psmopsbot churn reporting chase",
    "psm_ops_due_date_reminders.py",
    "psm_ops_pco_assignment_hygiene.py",
    "psm_ops_due_date_reminders_eod.py",
    "psm_ops_roi_tracker_sync.py",
    "psm_ops_churn_reporting_chase.py",
    "psmopsbot local cloud heartbeat",
    "psmopsbot adoption digest",
    "EXPECTED_ENABLED_CRON_COUNT",
    "Asia/Singapore",
  "systemctl --user is-active",
    "systemctl --user is-enabled"
]) {
  if (!heartbeatText.includes(requiredText)) fail(`Cloud heartbeat script missing required text: ${requiredText}`);
}

const auditText = textOf(appRoot, "runtime/audit-live-profile.sh");
for (const requiredText of [
  "profile:health-script-drift",
  "profile:public-channel-join-script-drift",
  "profile:assignment-hygiene-script-drift",
  "profile:churn-reporting-chase-script-drift",
  "cron:churn-reporting-chase-missing",
  "psm_ops_join_public_channels.py"
]) {
  if (!auditText.includes(requiredText)) fail(`Audit script missing required text: ${requiredText}`);
}

const healthCheckText = textOf(appRoot, "runtime/check-health.sh");
for (const requiredText of [
  "slack-display:interim-assistant-messages-not-disabled",
  "slack-display:tool-progress-not-off",
  "slack-display:streaming-not-disabled",
  "slack:reactions-not-disabled",
  "conversations.join",
  "slack:public-channel-join-scope-missing",
  "auxiliary:title-generation-provider-not-anthropic",
  "auxiliary:title-generation-model-not-haiku",
  "auxiliary:title-generation-timeout-too-high",
  "bigquery:bq-not-found",
  "psmopsbot churn reporting chase",
  "psm_ops_churn_reporting_chase.py",
  "slack:auth-test-missing-user-id"
]) {
  if (!healthCheckText.includes(requiredText)) fail(`Health check script missing required text: ${requiredText}`);
}

const joinPublicChannelsText = textOf(appRoot, "runtime/scripts/psm_ops_join_public_channels.py");
for (const requiredText of [
  "conversations.list",
  "conversations.join",
  "missing_scope",
  "--apply",
  "--dry-run",
  "SLACK_BOT_TOKEN"
]) {
  if (!joinPublicChannelsText.includes(requiredText)) fail(`Public-channel join script missing required text: ${requiredText}`);
}

const adoptionDigestText = textOf(appRoot, "runtime/psm_ops_adoption_digest.py");
for (const requiredText of [
  "PSM Ops automation: PS WEE adoption digest",
  "psm-ops-adoption.jsonl",
  "ticket_created",
  "roi_ticket_created",
  "c360_search",
  "Central copy",
  "hermes -p psmopsbot insights --days 30 --source slack"
]) {
  if (!adoptionDigestText.includes(requiredText)) fail(`Adoption digest script missing required text: ${requiredText}`);
}

const dueDateReminderText = textOf(appRoot, "runtime/scripts/psm_ops_due_date_reminders.py");
for (const requiredText of [
  "PSM Ops automation: PCO due-date reminder",
  "[SILENT] PSM Ops automation",
  "statusCategory != Done",
  "duedate is not EMPTY",
  "customfield_10876",
  "central digest only",
  "PSM_OPS_REMINDER_MENTION_MAP_PATH",
  "PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH",
  "PSM_OPS_JIRA_FIELD_SOURCE_LINKS",
  "Mention gaps:",
  "Customer team:",
  "choices=[\"morning\", \"eod\"]",
  "description",
  "comment",
  "transcript"
]) {
  if (!dueDateReminderText.includes(requiredText)) fail(`Due-date reminder script missing required text: ${requiredText}`);
}
if (dueDateReminderText.includes("users.list")) {
  fail("Due-date reminder script must not call Slack users.list for inverse PS Team mapping");
}

const assignmentHygieneText = textOf(appRoot, "runtime/scripts/psm_ops_pco_assignment_hygiene.py");
for (const requiredText of [
  "PSM Ops automation: PCO assignment hygiene",
  "[SILENT] PSM Ops automation",
  "statusCategory != Done",
  "assignee is EMPTY",
  "duedate is EMPTY",
  "customfield_10876",
  "Needs PS lead triage",
  "Needs due date by PS Team",
  "Lead mention gap:",
  "Mention gaps:",
  "PSM_OPS_REMINDER_MENTION_MAP_PATH",
  "ps_leads",
  "ps_teams",
  "description",
  "comment",
  "transcript",
  "attachment"
]) {
  if (!assignmentHygieneText.includes(requiredText)) fail(`Assignment hygiene script missing required text: ${requiredText}`);
}
if (assignmentHygieneText.includes("users.list")) {
  fail("Assignment hygiene script must not call Slack users.list for inverse PS Team mapping");
}

const roiTrackerSyncText = textOf(appRoot, "runtime/scripts/psm_ops_roi_tracker_sync.py");
for (const requiredText of [
  "PSM Ops automation: ROI tracker sync",
  "[SILENT] PSM Ops automation",
  "ps-wee-roi-tracker",
  "Waiting Internal",
  "linked ROI ticket is Done",
  "duedate",
  "description",
  "comment"
]) {
  if (!roiTrackerSyncText.includes(requiredText)) fail(`ROI tracker sync script missing required text: ${requiredText}`);
}

const churnReportingChaseText = textOf(appRoot, "runtime/scripts/psm_ops_churn_reporting_chase.py");
for (const requiredText of [
  "PSM Ops automation: Weekly churn reporting chase",
  "[SILENT] PSM Ops automation",
  "psm_ops_churn_projection_dashboard_292.sql",
  "Dashboard 292 SQL",
  "1-Actualized",
  "company_churn_reason_bucket",
  "renewal_assessment_reason",
  "fct_upcoming_renewal_cycles",
  "fct_company_revenue_snapshot",
  "fct_churnmrrbymonth",
  "PSM_OPS_CHURN_REPORTING_CHANNEL_ID",
  "C019RVCR4S1",
  "current quarter plus next two quarters",
  "renewal status, churn reason/category, evidence link",
  "No writes are ever performed"
]) {
  if (!churnReportingChaseText.includes(requiredText)) fail(`Churn reporting chase script missing required text: ${requiredText}`);
}
const churnProjectionDashboard292SqlText = textOf(appRoot, "runtime/sql/psm_ops_churn_projection_dashboard_292.sql");
for (const requiredText of [
  "Metabase card 2446",
  "get_churn_class",
  "churn_class",
  "weighted_churn_mrr",
  "company_churn_reason_bucket",
  "renewal_assessment_reason",
  "fct_alldealsmrr",
  "stg_hubspot__companies"
]) {
  if (!churnProjectionDashboard292SqlText.includes(requiredText)) {
    fail(`Dashboard 292 SQL missing required text: ${requiredText}`);
  }
}
for (const forbiddenText of [
  "13UjJOZpkyngN_5oo4LtzeJWfqhc7PAD8hR1E_aU6gP0",
  "spreadsheets.values",
  "googleapis.com/sheets",
  "gspread",
  "SLACK_USER_TOKEN",
  "xoxp-"
]) {
  if (churnReportingChaseText.includes(forbiddenText)) {
    fail(`Churn reporting chase script must not include forbidden runtime source/token text: ${forbiddenText}`);
  }
  if (churnProjectionDashboard292SqlText.includes(forbiddenText)) {
    fail(`Dashboard 292 SQL must not include forbidden runtime source/token text: ${forbiddenText}`);
  }
}

const shellCheck = spawnSync("bash", [
  "-n",
  join(appRoot, "runtime", "check-health.sh"),
  join(appRoot, "runtime", "check-cloud-heartbeat.sh"),
  join(appRoot, "runtime", "audit-live-profile.sh"),
  join(appRoot, "runtime", "smoke-rock-productions-c360.sh")
], {
  cwd: repoRoot,
  encoding: "utf8"
});
if (shellCheck.status !== 0) {
  fail(`Shell syntax check failed: ${shellCheck.stderr || shellCheck.stdout}`);
}

const deployScriptSyntaxCheck = spawnSync(process.execPath, [
  "--check",
  deployScriptPath
], {
  cwd: repoRoot,
  encoding: "utf8"
});
if (deployScriptSyntaxCheck.status !== 0) {
  fail(`Deploy script syntax check failed: ${deployScriptSyntaxCheck.stderr || deployScriptSyntaxCheck.stdout}`);
}

const pyCompile = spawnSync("python3", [
  "-m",
  "py_compile",
  join(appRoot, "runtime/mcp/psm_slack_notifier.py"),
  join(appRoot, "runtime/mcp/psm_jira_server.py"),
  join(appRoot, "runtime/mcp/psm_c360_server.py"),
  join(appRoot, "runtime/mcp/google_oauth.py"),
  join(appRoot, "runtime/mcp/psm_google_calendar_server.py"),
  join(appRoot, "runtime/hooks/psm-ops-adoption-telemetry/handler.py"),
  join(appRoot, "runtime/hooks/psm-ops-mention-guard/handler.py"),
  join(appRoot, "runtime/psm_ops_adoption_digest.py"),
  join(appRoot, "runtime/scripts/psm_ops_due_date_reminders.py"),
  join(appRoot, "runtime/scripts/psm_ops_pco_assignment_hygiene.py"),
  join(appRoot, "runtime/scripts/psm_ops_roi_tracker_sync.py"),
  join(appRoot, "runtime/scripts/psm_ops_churn_reporting_chase.py"),
  join(appRoot, "runtime/scripts/psm_ops_join_public_channels.py")
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

const reminderScriptUnitCheck = spawnSync("python3", [
  "-m",
  "unittest",
  join(appRoot, "runtime/test_psm_ops_due_date_reminders.py")
], {
  cwd: repoRoot,
  env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
  encoding: "utf8"
});
if (reminderScriptUnitCheck.status !== 0) {
  fail(`Due-date reminder unit tests failed: ${reminderScriptUnitCheck.stderr || reminderScriptUnitCheck.stdout}`);
}

const roiTrackerScriptUnitCheck = spawnSync("python3", [
  "-m",
  "unittest",
  join(appRoot, "runtime/test_psm_ops_roi_tracker_sync.py")
], {
  cwd: repoRoot,
  env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
  encoding: "utf8"
});
if (roiTrackerScriptUnitCheck.status !== 0) {
  fail(`ROI tracker sync unit tests failed: ${roiTrackerScriptUnitCheck.stderr || roiTrackerScriptUnitCheck.stdout}`);
}

const churnReportingChaseScriptUnitCheck = spawnSync("python3", [
  "-m",
  "unittest",
  join(appRoot, "runtime/test_psm_ops_churn_reporting_chase.py")
], {
  cwd: repoRoot,
  env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
  encoding: "utf8"
});
if (churnReportingChaseScriptUnitCheck.status !== 0) {
  fail(`Churn reporting chase unit tests failed: ${churnReportingChaseScriptUnitCheck.stderr || churnReportingChaseScriptUnitCheck.stdout}`);
}

const assignmentHygieneScriptUnitCheck = spawnSync("python3", [
  "-m",
  "unittest",
  join(appRoot, "runtime/test_psm_ops_pco_assignment_hygiene.py")
], {
  cwd: repoRoot,
  env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
  encoding: "utf8"
});
if (assignmentHygieneScriptUnitCheck.status !== 0) {
  fail(`Assignment hygiene unit tests failed: ${assignmentHygieneScriptUnitCheck.stderr || assignmentHygieneScriptUnitCheck.stdout}`);
}

const joinPublicChannelsUnitCheck = spawnSync("python3", [
  "-m",
  "unittest",
  join(appRoot, "runtime/test_psm_ops_join_public_channels.py")
], {
  cwd: repoRoot,
  env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
  encoding: "utf8"
});
if (joinPublicChannelsUnitCheck.status !== 0) {
  fail(`Public-channel join unit tests failed: ${joinPublicChannelsUnitCheck.stderr || joinPublicChannelsUnitCheck.stdout}`);
}

const mentionGuardUnitCheck = spawnSync("python3", [
  join(appRoot, "runtime/hooks/psm-ops-mention-guard/test_handler.py")
], {
  cwd: repoRoot,
  env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
  encoding: "utf8"
});
if (mentionGuardUnitCheck.status !== 0) {
  fail(`Mention-guard hook unit tests failed: ${mentionGuardUnitCheck.stderr || mentionGuardUnitCheck.stdout}`);
}

if (failures.length > 0) {
  console.error("PSM Ops Bot packet verification failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log("PSM Ops Bot packet verification passed.");
