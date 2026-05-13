import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import {
  assertFile as sharedAssertFile,
  assertManifestPaths,
  readJson as sharedReadJson,
  scanForSecretPatterns as sharedScanForSecretPatterns,
  textOf as sharedTextOf
} from "./lib/app-packet-verify.mjs";

const repoRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
const appRoot = join(repoRoot, "apps", "launch-superpower-bot");
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

function textOf(relPath) {
  return sharedTextOf(appRoot, relPath);
}

function scanForSecretPatterns(relPath) {
  sharedScanForSecretPatterns(appRoot, relPath, fail);
}

if (!existsSync(manifestPath)) {
  fail("Missing apps/launch-superpower-bot/app.manifest.json");
} else {
  const manifest = readJson(manifestPath);
  if (manifest) {
    if (manifest.app_slug !== "launch-superpower-bot") fail("Manifest app_slug must be launch-superpower-bot");
    if (manifest.secrets_copied !== false) fail("Manifest secrets_copied must be false");
    if (manifest.source_status !== "packet_from_2026_05_11_handoff_source_code_not_present") {
      fail("Manifest source_status must state that source code is not present");
    }
    if (manifest.test_feature?.jira_issue !== "KER-1742") fail("Manifest must preserve KER-1742 test feature");
    if (manifest.test_feature?.latest_clean_version !== "v005") fail("Manifest must preserve v005 clean test version");
    assertManifestPaths(appRoot, manifest.paths || {}, fail);

    const step4 = (manifest.workflow_steps || []).find((step) => step.step === 4);
    if (step4?.status !== "planned_stub") fail("Manifest Step 4 must remain planned_stub");
    if (manifest.integrations?.slack?.posting_identity !== "bot_owned_only") {
      fail("Manifest Slack posting identity must be bot_owned_only");
    }
    if (manifest.integrations?.slack?.expected_bot_name !== "Launch Bot") {
      fail("Manifest Slack expected bot name must be Launch Bot");
    }
    if (manifest.integrations?.slack?.expected_bot_user_id !== "U0ASVD79UT1") {
      fail("Manifest Slack expected bot user ID must be U0ASVD79UT1");
    }
    if (manifest.integrations?.slack?.expected_bot_id !== "B0ATPPEGBCH") {
      fail("Manifest Slack expected bot ID must be B0ATPPEGBCH");
    }
    if (!manifest.integrations?.slack?.wrong_profile_guard?.includes("@codexlaunchbot")) {
      fail("Manifest Slack wrong profile guard must name @codexlaunchbot");
    }
    if (manifest.integrations?.slack?.default_test_channel_name !== "launch-bot-testing") {
      fail("Manifest Slack default test channel name must be launch-bot-testing");
    }
    if (manifest.integrations?.slack?.default_test_channel_id !== "C0B32M34J3W") {
      fail("Manifest Slack default test channel ID must be C0B32M34J3W");
    }
    if (manifest.integrations?.slack?.automation_voice !== "light_cowboy") {
      fail("Manifest Slack automation voice must be light_cowboy");
    }
    if (manifest.integrations?.intercom?.publish_mode !== "draft_only") {
      fail("Manifest Intercom publish mode must be draft_only");
    }

    const requiredEnvNames = [
      "LAUNCH_STEP2_SLACK_BOT_TOKEN",
      "LAUNCH_STEP3_SLACK_SIGNING_SECRET",
      "LAUNCH_STEP3_SLACK_BOT_TOKEN",
      "LAUNCH_STEP3_GOOGLE_SERVICE_ACCOUNT_JSON",
      "LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN",
      "LAUNCH_STEP3_INTERCOM_STAGING_COLLECTION_ID"
    ];
    for (const name of requiredEnvNames) {
      if (!manifest.required_env_names?.includes(name)) fail(`Manifest missing env name: ${name}`);
    }
    for (const name of [
      "LAUNCH_STEP3_SLACK_APPROVAL_REACTION",
      "LAUNCH_STEP3_SLACK_AUTHORIZED_REVIEWER_IDS"
    ]) {
      if (!manifest.optional_env_names?.includes(name)) fail(`Manifest missing optional env name: ${name}`);
    }

    const contract = manifest.help_article_contract || {};
    const falseFlags = [
      "raw_html_in_markdown_body",
      "text_dividers_in_markdown_body",
      "repeated_title_in_body"
    ];
    for (const key of falseFlags) {
      if (contract[key] !== false) fail(`Manifest help_article_contract.${key} must be false`);
    }
    for (const key of [
      "publishable_body_excludes_internal_appendix",
      "audience_block_centered",
      "numbered_steps_restart_per_subsection"
    ]) {
      if (contract[key] !== true) fail(`Manifest help_article_contract.${key} must be true`);
    }
    if (contract.clubany_product_label !== "StaffAny") fail("Manifest must set ClubAny product label to StaffAny");
    if (contract.clubany_management_article_default !== "combined_brands_and_perks_article") {
      fail("Manifest must prefer the combined ClubAny management article");
    }

    for (const evidencePath of Object.values(manifest.evidence || {})) {
      const absolute = join(repoRoot, evidencePath);
      if (!existsSync(absolute)) fail(`Manifest evidence path is missing: ${evidencePath}`);
    }
  }
}

const filesToScan = [
  "README.md",
  "AGENTS.md",
  "app.manifest.json",
  "profile/SOUL.md",
  "skills/help-article-generator/SKILL.md",
  "skills/help-article-generator/references/help-article-skeleton.md",
  "runtime/workflow.md",
  "runtime/launchbot_e2e.py",
  "tests/regression-cases.md"
];

for (const relPath of filesToScan) {
  assertFile(relPath);
  scanForSecretPatterns(relPath);
}

const skillText = textOf("skills/help-article-generator/SKILL.md");
for (const requiredText of [
  "Handoff-upgraded rules in this packet override the older Grimoire help-article skill",
  "one combined management article",
  "Managing Brands",
  "Managing Perks",
  "Do not use raw HTML",
  "Do not place any visible divider lines",
  "Do not include the internal appendix",
  "A brand is the business profile",
  "A perk sits under a brand",
  "For ClubAny / Club Blue content, set Product to `StaffAny`",
  "numbered steps from `1` for each subsection"
]) {
  if (!skillText.includes(requiredText)) fail(`Skill missing required text: ${requiredText}`);
}
if (/^<div|^<br|^\s*<[^>]+style=|^\s*<[^>]+align=/m.test(skillText)) {
  fail("Skill must not include raw HTML formatting examples");
}

const soulText = textOf("profile/SOUL.md");
for (const requiredText of [
  "You are StaffAny Launchbot in Slack",
  "turn a shipped Jira feature into reviewable launch assets",
  "Draft code-grounded StaffAny help articles",
  "Create Google Docs review drafts and Slack review messages",
  "Watch for approved Slack review reactions",
  "Create Intercom draft articles after approval",
  "You are not a general-purpose computer assistant in Slack",
  "what can you do",
  "Launch Superpower Bot packet",
  "Step 4 launch derivatives are planned only"
]) {
  if (!soulText.includes(requiredText)) fail(`Profile SOUL missing required text: ${requiredText}`);
}
for (const forbiddenText of [
  "Control Spotify",
  "Philips Hue",
  "Post to X/Twitter",
  "Run ML experiments",
  "Write songs"
]) {
  if (soulText.includes(forbiddenText)) fail(`Profile SOUL includes generic capability text: ${forbiddenText}`);
}

const skeletonText = textOf("skills/help-article-generator/references/help-article-skeleton.md");
if (!skeletonText.includes("**This guide will cover how to:**")) {
  fail("Skeleton missing guide outline line");
}
if (!/^1\. \[Main section\]/m.test(skeletonText)) {
  fail("Skeleton outline must use numbered items");
}
if (/^---$/m.test(skeletonText)) {
  fail("Skeleton must not use text divider lines");
}
if (/<div|<br|align=|style=/.test(skeletonText)) {
  fail("Skeleton must not include raw HTML formatting examples");
}

const workflowText = textOf("runtime/workflow.md");
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
  "Step 4 launch derivatives are not implemented"
]) {
  if (!workflowText.includes(requiredText)) fail(`Workflow doc missing required text: ${requiredText}`);
}

const rawManifestPath = join(repoRoot, "research/raw/launch-superpower-bot/2026-05-11-handoff/source-manifest.md");
if (!existsSync(rawManifestPath)) {
  fail("Missing raw Launch Superpower Bot source manifest");
} else {
  const rawManifestText = readFileSync(rawManifestPath, "utf8");
  for (const requiredText of [
    "Source Metadata",
    "Raw Content Policy",
    "Source Inventory",
    "Evidence Extracts",
    "103993db42687d54c6a2b375b0a8d5dcbe65c7e57e521f1fded4a582788a934d",
    "579f8ddc9b1098a4d9b12900c21bd8f6c0b208c226e2f563ac32d326351af376"
  ]) {
    if (!rawManifestText.includes(requiredText)) fail(`Raw source manifest missing required text: ${requiredText}`);
  }
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
  "omit_top_heading=True"
]) {
  if (!e2eRunnerText.includes(requiredText)) fail(`E2E runner missing required text: ${requiredText}`);
}

const pyCompile = spawnSync(
  "python3",
  [
    "-c",
    "from pathlib import Path; import sys; p=Path(sys.argv[1]); compile(p.read_text(encoding='utf-8'), str(p), 'exec')",
    join(appRoot, "runtime", "launchbot_e2e.py")
  ],
  { encoding: "utf8" }
);
if (pyCompile.status !== 0) {
  fail(`E2E runner Python syntax check failed: ${(pyCompile.stderr || pyCompile.stdout || "").trim()}`);
}

const sourceNotePath = join(repoRoot, "research/wiki/sources/launch-superpower-bot-handoff.md");
if (!existsSync(sourceNotePath)) fail("Missing maintained Launch Superpower Bot source note");

const agentsText = textOf("AGENTS.md");
for (const requiredText of [
  "#launch-bot-testing",
  "C0B32M34J3W",
  "@Launch Bot",
  "U0ASVD79UT1",
  "B0ATPPEGBCH",
  "light cowboy voice",
  "Launchbot automation:"
]) {
  if (!agentsText.includes(requiredText)) fail(`AGENTS missing required text: ${requiredText}`);
}

const regressionText = textOf("tests/regression-cases.md");
for (const requiredText of [
  "#launch-bot-testing",
  "@Launch Bot",
  "U0ASVD79UT1",
  "B0ATPPEGBCH",
  "light cowboy voice"
]) {
  if (!regressionText.includes(requiredText)) fail(`Regression cases missing required text: ${requiredText}`);
}

if (failures.length > 0) {
  console.error("Launch Superpower Bot packet verification failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log("Launch Superpower Bot packet verification passed.");
