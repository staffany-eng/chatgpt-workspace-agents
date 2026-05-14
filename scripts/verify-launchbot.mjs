import { existsSync, readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { join, resolve } from "node:path";
import {
  assertFile as sharedAssertFile,
  readJson as sharedReadJson,
  scanForSecretPatterns as sharedScanForSecretPatterns,
} from "./lib/app-packet-verify.mjs";

const repoRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
const appRoot = join(repoRoot, "apps", "launchbot");
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

function textOf(relPath) {
  const path = join(appRoot, relPath);
  return existsSync(path) ? readFileSync(path, "utf8") : "";
}

const manifest = existsSync(manifestPath) ? sharedReadJson(manifestPath, fail) : null;
if (!manifest) {
  fail("Missing apps/launchbot/app.manifest.json");
} else {
  if (manifest.profile_name !== "launchbot") fail("Manifest profile_name must be launchbot");
  if (manifest.secrets_copied !== false) fail("Manifest secrets_copied must be false");
  for (const value of Object.values(manifest.paths || {})) {
    assertFile(value);
  }
  if (manifest.launch_workflow?.source_status !== "skill_and_workflow_from_2026_05_11_handoff_source_code_not_present") {
    fail("Manifest launch_workflow.source_status must keep the handoff as a Launchbot skill/workflow");
  }
  if (manifest.launch_workflow?.test_feature?.jira_issue !== "KER-1742") {
    fail("Manifest launch_workflow must preserve KER-1742 test feature");
  }
  if (manifest.launch_workflow?.test_feature?.latest_clean_version !== "v005") {
    fail("Manifest launch_workflow must preserve v005 clean test version");
  }
  const step4 = (manifest.launch_workflow?.workflow_steps || []).find((step) => step.step === 4);
  if (step4?.status !== "planned_stub") fail("Manifest launch_workflow Step 4 must remain planned_stub");
  const contract = manifest.launch_workflow?.help_article_contract || {};
  for (const key of [
    "publishable_body_excludes_internal_appendix",
    "audience_block_centered",
    "numbered_steps_restart_per_subsection",
  ]) {
    if (contract[key] !== true) fail(`Manifest launch_workflow.help_article_contract.${key} must be true`);
  }
  for (const key of [
    "raw_html_in_markdown_body",
    "text_dividers_in_markdown_body",
    "repeated_title_in_body",
  ]) {
    if (contract[key] !== false) fail(`Manifest launch_workflow.help_article_contract.${key} must be false`);
  }
  if (contract.clubany_product_label !== "StaffAny") fail("Manifest must set ClubAny product label to StaffAny");
  if (contract.clubany_management_article_default !== "combined_brands_and_perks_article") {
    fail("Manifest must prefer the combined ClubAny management article");
  }
  for (const evidencePath of Object.values(manifest.launch_workflow?.evidence || {})) {
    const absolute = join(repoRoot, evidencePath);
    if (!existsSync(absolute)) fail(`Manifest launch_workflow evidence path is missing: ${evidencePath}`);
  }
}

for (const relPath of [
  "profile/SOUL.md",
  "profile/config.template.yaml",
  "runtime/slack.md",
  "runtime/health-checks.md",
  "runtime/check-health.sh",
  "runtime/audit-live-profile.sh",
  "runtime/mcp/profile_env.py",
  "runtime/mcp/launchbot_ker_server.py",
  "runtime/mcp/test_helpers.py",
  "runtime/mcp/test_launchbot_ker_server.py",
  "skills/help-article-generator/SKILL.md",
  "skills/help-article-generator/references/help-article-skeleton.md",
  "runtime/launch-workflow.md",
  "runtime/launchbot_e2e.py",
  "tests/launch-workflow-regression-cases.md",
]) {
  assertFile(relPath);
  scanForSecretPatterns(relPath);
}

const configText = existsSync(join(appRoot, "profile", "config.template.yaml"))
  ? readFileSync(join(appRoot, "profile", "config.template.yaml"), "utf8")
  : "";
for (const requiredText of [
  'provider: "anthropic"',
  'default: "claude-sonnet-4-6"',
  "interim_assistant_messages: false",
  'tool_progress: "off"',
  "streaming: false",
  "reactions: false",
  "C0B32M34J3W",
  "C0AJAUNCEL8",
  "launchbot_ker",
  "find_ker_ticket_from_slack_thread",
  "lookup_ker_ticket_by_key",
  "JIRA_API_TOKEN",
  "/home/leekaiyi/.hermes/profiles/launchbot/source/launchbot",
]) {
  if (!configText.includes(requiredText)) fail(`config.template.yaml missing required text: ${requiredText}`);
}
if (configText.includes("/Users/leekaiyi/.hermes/profiles/launchbot/source/launchbot")) {
  fail("config.template.yaml must not point cloud runtime at the local Mac launchbot profile");
}

const soulText = existsSync(join(appRoot, "profile", "SOUL.md"))
  ? readFileSync(join(appRoot, "profile", "SOUL.md"), "utf8")
  : "";
for (const requiredText of [
  "Do not use Kai Yi's user token",
  "Kai Yi's user token",
  "Confidence: <verified | needs-check | blocked>",
  "find_ker_ticket_from_slack_thread",
  "KER-2109",
  "code-grounded help article drafts",
  "Intercom draft articles",
  "Launchbot packet",
  "Launch Superpower handoff is a Launchbot skill/workflow",
  "Never answer `Source: Launch Superpower Bot packet`",
  "experimental",
]) {
  if (!soulText.includes(requiredText)) fail(`SOUL.md missing required text: ${requiredText}`);
}

const mcpText = existsSync(join(appRoot, "runtime", "mcp", "launchbot_ker_server.py"))
  ? readFileSync(join(appRoot, "runtime", "mcp", "launchbot_ker_server.py"), "utf8")
  : "";
for (const requiredText of [
  "SLACK_BOT_TOKEN",
  "JIRA_BASE_URL",
  "JIRA_EMAIL",
  "JIRA_API_TOKEN",
  "conversations.replies",
  "/rest/api/3/search/jql",
  "will_mutate_jira",
  "will_post_message",
  "transcript_persisted",
  "C0AJAUNCEL8",
]) {
  if (!mcpText.includes(requiredText)) fail(`launchbot_ker_server.py missing required text: ${requiredText}`);
}

for (const forbiddenText of ["chat.postMessage", "transitionIssue", "/comment", "/transitions"]) {
  if (mcpText.includes(forbiddenText)) fail(`launchbot_ker_server.py must not contain forbidden mutation surface: ${forbiddenText}`);
}

const skillText = textOf("skills/help-article-generator/SKILL.md");
for (const requiredText of [
  "Handoff-upgraded rules in this Launchbot skill override the older Grimoire help-article skill",
  "one combined management article",
  "Managing Brands",
  "Managing Perks",
  "Do not use raw HTML",
  "Do not place any visible divider lines",
  "Do not include the internal appendix",
  "A brand is the business profile",
  "A perk sits under a brand",
  "For ClubAny / Club Blue content, set Product to `StaffAny`",
  "numbered steps from `1` for each subsection",
]) {
  if (!skillText.includes(requiredText)) fail(`Help article skill missing required text: ${requiredText}`);
}
if (/^<div|^<br|^\s*<[^>]+style=|^\s*<[^>]+align=/m.test(skillText)) {
  fail("Help article skill must not include raw HTML formatting examples");
}

const skeletonText = textOf("skills/help-article-generator/references/help-article-skeleton.md");
if (!skeletonText.includes("**This guide will cover how to:**")) {
  fail("Help article skeleton missing guide outline line");
}
if (!/^1\. \[Main section\]/m.test(skeletonText)) {
  fail("Help article skeleton outline must use numbered items");
}
if (/^---$/m.test(skeletonText)) {
  fail("Help article skeleton must not use text divider lines");
}
if (/<div|<br|align=|style=/.test(skeletonText)) {
  fail("Help article skeleton must not include raw HTML formatting examples");
}

const workflowText = textOf("runtime/launch-workflow.md");
for (const requiredText of [
  "Slack Capability Questions",
  "what can u do",
  "code-grounded help article drafts",
  "Do not list generic assistant categories",
  "source code under `vk-super-productivity/launch-superpower-bot` is not present",
  "runtime/launchbot_e2e.py",
  "Intercom draft articles",
  "bot-owned posting credentials",
  "@Launch Bot",
  "U0ASVD79UT1",
  "B0ATPPEGBCH",
  "#launch-bot-testing",
  "light cowboy voice",
  "Do not commit token values",
  "Step 4 launch derivatives are not implemented",
]) {
  if (!workflowText.includes(requiredText)) fail(`Launch workflow doc missing required text: ${requiredText}`);
}

const e2eRunnerText = textOf("runtime/launchbot_e2e.py");
for (const requiredText of [
  "LAUNCH_STEP2_SLACK_BOT_TOKEN",
  "LAUNCH_STEP3_SLACK_BOT_TOKEN",
  "LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN",
  "LAUNCH_STEP3_SLACK_AUTHORIZED_REVIEWER_IDS",
  "GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE",
  "C0B32M34J3W",
  "launch-bot-testing",
  "EXPECTED_SLACK_BOT_USER_ID",
  "EXPECTED_SLACK_BOT_ID",
  "slack:wrong-bot-profile",
  "Launchbot automation: Howdy, partner. Review draft is saddled up for approval",
  "Approved review is now drafted in Intercom",
  "--approval-only",
  "approval_user_ids",
  "approval:no-authorized-reviewer",
  "fit to ride into Intercom draft",
  "\"state\": \"draft\"",
  "\"parent_type\": \"collection\"",
  "conversations.join",
  "conversations.history",
  "thread_ts",
  "intercom_direct_url",
  "LAUNCH_STEP3_INTERCOM_APP_ID",
  "omit_top_heading=True",
]) {
  if (!e2eRunnerText.includes(requiredText)) fail(`Launch workflow runner missing required text: ${requiredText}`);
}

const pyCompile = spawnSync(
  "python3",
  [
    "-c",
    "from pathlib import Path; import sys; p=Path(sys.argv[1]); compile(p.read_text(encoding='utf-8'), str(p), 'exec')",
    join(appRoot, "runtime", "launchbot_e2e.py"),
  ],
  { encoding: "utf8" }
);
if (pyCompile.status !== 0) {
  fail(`Launch workflow runner Python syntax check failed: ${(pyCompile.stderr || pyCompile.stdout || "").trim()}`);
}

const sourceNotePath = join(repoRoot, "research/wiki/sources/launch-superpower-bot-handoff.md");
if (!existsSync(sourceNotePath)) fail("Missing maintained Launch Superpower handoff source note");

const regressionText = textOf("tests/launch-workflow-regression-cases.md");
for (const requiredText of [
  "#launch-bot-testing",
  "@Launch Bot",
  "U0ASVD79UT1",
  "B0ATPPEGBCH",
  "light cowboy voice",
]) {
  if (!regressionText.includes(requiredText)) fail(`Launch workflow regression cases missing required text: ${requiredText}`);
}

const testRun = spawnSync("python3", ["-m", "unittest", "discover", "-s", join(appRoot, "runtime", "mcp"), "-p", "test_*.py"], {
  cwd: repoRoot,
  encoding: "utf8",
});
if (testRun.status !== 0) {
  fail(`Launchbot MCP unit tests failed:\n${testRun.stdout || ""}${testRun.stderr || ""}`);
}

if (failures.length > 0) {
  console.error("Launchbot packet verification failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log("Launchbot packet verification passed.");
