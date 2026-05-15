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

function profileBlock(profilesText, profileName) {
  const marker = `  - name: ${profileName}`;
  const start = profilesText.indexOf(marker);
  if (start === -1) return "";
  const next = profilesText.indexOf("\n  - name:", start + marker.length);
  return profilesText.slice(start, next === -1 ? undefined : next);
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
  if (manifest.slack?.socket_mode !== true) {
    fail("Manifest Slack socket_mode must be true");
  }
  if (manifest.slack?.gateway_restart_notification !== false) {
    fail("Manifest Slack gateway restart notifications must be disabled");
  }
  if (!manifest.channels?.includes("Slack #all-product-questions")) {
    fail("Manifest channels must include #all-product-questions for read-only KER lookup");
  }
  for (const eventName of ["app_mention", "message.channels"]) {
    if (!manifest.slack?.required_bot_events?.includes(eventName)) {
      fail(`Manifest Slack required bot events missing ${eventName}`);
    }
  }
  for (const scopeName of ["app_mentions:read", "channels:history", "channels:read", "chat:write"]) {
    if (!manifest.slack?.required_oauth_scopes?.includes(scopeName)) {
      fail(`Manifest Slack required OAuth scopes missing ${scopeName}`);
    }
  }
  if (!manifest.slack?.event_subscription_drift_guard?.includes("message.channels")) {
    fail("Manifest Slack event subscription drift guard must mention message.channels");
  }
  const step0 = (manifest.launch_workflow?.workflow_steps || []).find((step) => step.step === 0);
  if (step0?.status !== "implemented_in_packet") fail("Manifest launch_workflow Step 0 must be implemented_in_packet");
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
  const videoLane = contract.video_only_update_lane || {};
  if (videoLane.mode !== "Update -> Video-only update") fail("Manifest must register video-only help article update lane");
  if (videoLane.registry !== "skills/help-article-generator/references/video-placement-registry.json") {
    fail("Manifest video-only lane must point at the video placement registry");
  }
  if (videoLane.slot_match_required !== true) fail("Manifest video-only lane must require a slot match");
  if (videoLane.supported_provider !== "loom") fail("Manifest video-only lane must be Loom-only");
  if (videoLane.replace_policy !== "replace_next_video_after_anchor") fail("Manifest video-only lane must use registered anchor replace policy");
  if (videoLane.draft_state_only !== true) fail("Manifest video-only lane must be draft-state only");
  if (videoLane.article_text_rewrite !== false) fail("Manifest video-only lane must forbid article text rewrites");
  if (videoLane.publish !== false) fail("Manifest video-only lane must forbid publishing");
  if (contract.source_of_truth !== "pantheon_code_grounded_behavior") {
    fail("Manifest launch_workflow.help_article_contract.source_of_truth must use Pantheon code-grounded behavior");
  }
  if (contract.code_source_checkout?.repo !== "pantheon") {
    fail("Manifest launch_workflow.help_article_contract.code_source_checkout must describe Pantheon");
  }
  for (const key of [
    "pantheon_evidence_required",
    "pantheon_evidence_gate",
    "pantheon_missing_or_dirty_blocks",
    "pantheon_ambiguous_or_conflicting_blocks",
    "article_planner_required_before_draft",
    "adaptive_intake_gate_before_plan",
    "article_inventory_metadata_only",
    "article_inventory_used_before_live_search",
    "article_shape_stale_check_before_staging",
    "cached_intercom_planning_profile",
    "pre_publish_format_gate",
    "live_intercom_wins_on_conflict",
  ]) {
    if (contract[key] !== true) fail(`Manifest launch_workflow.help_article_contract.${key} must be true`);
  }
  if (contract.intercom_format_profile !== "skills/help-article-generator/references/intercom-format-profile.json") {
    fail("Manifest must point to the Intercom format profile");
  }
  if (contract.article_planning_profile !== "skills/help-article-generator/references/article-planning-profile.json") {
    fail("Manifest must point to the Intercom article planning profile");
  }
  if (contract.intercom_article_inventory !== "skills/help-article-generator/references/intercom-article-inventory.json") {
    fail("Manifest must point to the Intercom article inventory");
  }
  for (const evidencePath of Object.values(manifest.launch_workflow?.evidence || {})) {
    const absolute = join(repoRoot, evidencePath);
    if (!existsSync(absolute)) fail(`Manifest launch_workflow evidence path is missing: ${evidencePath}`);
  }
  if (manifest.source_repositories?.pantheon?.remote !== "git@github.com:staffany-eng/pantheon.git") {
    fail("Manifest Pantheon remote must be staffany-eng/pantheon");
  }
  if (manifest.source_repositories?.pantheon?.branch !== "develop") {
    fail("Manifest Pantheon branch must be develop");
  }
  if (manifest.source_repositories?.pantheon?.daily_update_requires !== "VM GitHub SSH access to staffany-eng/pantheon") {
    fail("Manifest Pantheon daily update must be gated on VM GitHub SSH access");
  }
  const helpMcp = manifest.mcp?.launchbot_help_article || {};
  if (helpMcp.mode !== "draft_only_registered_video_slots") fail("Manifest help article MCP must be draft-only registered video slots");
  const helpTools = new Set(helpMcp.tools || []);
  for (const tool of ["preview_help_article_video_update", "create_help_article_video_update_draft"]) {
    if (!helpTools.has(tool)) fail(`Manifest help article MCP missing tool: ${tool}`);
  }
  if (helpMcp.registry !== "skills/help-article-generator/references/video-placement-registry.json") {
    fail("Manifest help article MCP must point at the video placement registry");
  }
  if (helpMcp.intercom?.access_token_env_var !== "LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN") {
    fail("Manifest help article MCP must use LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN");
  }
  if (helpMcp.intercom?.forced_state !== "draft") fail("Manifest help article MCP must force draft state");
  for (const key of ["publish", "delete", "tag_mutation", "collection_mutation"]) {
    if (helpMcp.intercom?.[key] !== false) fail(`Manifest help article MCP must forbid ${key}`);
  }
  if (helpMcp.video?.provider !== "loom") fail("Manifest help article MCP must be Loom-only");
  if (helpMcp.video?.reject_raw_video_files !== true) fail("Manifest help article MCP must reject raw video files");
  if (helpMcp.video?.reject_slack_file_urls !== true) fail("Manifest help article MCP must reject Slack file URLs");
  for (const channelId of ["C0B32M34J3W", "C0AJAUNCEL8", "C01RZ7SHC8K", "CF8PK6V4J"]) {
    if (!manifest.slack?.allowed_channel_ids?.includes(channelId)) {
      fail(`Manifest Slack allowed channel IDs missing ${channelId}`);
    }
  }
  const kerMcp = manifest.mcp?.launchbot_ker || {};
  if (!kerMcp.slack_context?.default_channel_ids?.includes("C01RZ7SHC8K")) {
    fail("Manifest KER MCP default channels must include all-product-questions C01RZ7SHC8K");
  }
  const featureIntakeMcp = manifest.mcp?.launchbot_feature_intake || {};
  if (featureIntakeMcp.mode !== "confirmed_jpd_intake_create") fail("Manifest feature intake MCP must be confirmed JPD intake create");
  const featureIntakeTools = new Set(featureIntakeMcp.tools || []);
  for (const tool of ["preview_feature_intake_from_slack_thread", "create_feature_intake_from_slack_thread"]) {
    if (!featureIntakeTools.has(tool)) fail(`Manifest feature intake MCP missing tool: ${tool}`);
  }
  if (featureIntakeMcp.slack_context?.configured_channel_ids_env_var !== "LAUNCHBOT_FEATURE_INTAKE_ALLOWED_CHANNEL_IDS") {
    fail("Manifest feature intake MCP must use LAUNCHBOT_FEATURE_INTAKE_ALLOWED_CHANNEL_IDS");
  }
  if (!featureIntakeMcp.slack_context?.default_channel_ids?.includes("CF8PK6V4J")) {
    fail("Manifest feature intake MCP default channels must include CF8PK6V4J");
  }
  if (featureIntakeMcp.slack_context?.raw_transcript_persistence !== false) {
    fail("Manifest feature intake MCP must not persist raw Slack transcripts");
  }
  if (featureIntakeMcp.jira?.project_key !== "KER") fail("Manifest feature intake MCP must create in KER");
  if (featureIntakeMcp.jira?.issue_type_id !== "10043") fail("Manifest feature intake MCP must use KER Idea issue type");
  if (featureIntakeMcp.jira?.slack_prd_field_id !== "customfield_10080") {
    fail("Manifest feature intake MCP must use Slack / PRD customfield_10080");
  }
  if (!featureIntakeMcp.jira?.mutations?.includes("create_issue")) {
    fail("Manifest feature intake MCP must expose only create_issue mutation");
  }
  for (const key of ["comments", "transitions", "assignments"]) {
    if (featureIntakeMcp.jira?.[key] !== false) fail(`Manifest feature intake MCP must forbid Jira ${key}`);
  }
  if (featureIntakeMcp.confirmation?.phrase !== "create intake") {
    fail("Manifest feature intake MCP confirmation phrase must be create intake");
  }
  const healthCron = (manifest.expected_crons || []).find((cron) => cron.name === "launchbot health check");
  if (healthCron?.schedule !== "*/5 * * * *") fail("Manifest must define Launchbot health check cron");
  if (healthCron?.mode !== "no-agent") fail("Manifest health check cron must be no-agent");
  const pantheonCron = (manifest.expected_crons || []).find((cron) => cron.name === "launchbot pantheon repo update");
  if (pantheonCron?.schedule !== "0 22 * * *") fail("Manifest must define daily Pantheon repo update cron");
  if (pantheonCron?.mode !== "no-agent") fail("Manifest Pantheon repo update cron must be no-agent");
  if (pantheonCron?.requires !== "VM GitHub SSH access to staffany-eng/pantheon") {
    fail("Manifest Pantheon repo update cron must document the GitHub SSH access gate");
  }
}

for (const relPath of [
  "profile/SOUL.md",
  "profile/config.template.yaml",
  "runtime/slack.md",
  "runtime/health-checks.md",
  "runtime/check-health.sh",
  "runtime/audit-live-profile.sh",
  "runtime/update-pantheon-repo.sh",
  "runtime/intercom-format-gate.mjs",
  "runtime/intercom-format-gate.test.mjs",
  "runtime/mcp/profile_env.py",
  "runtime/mcp/launchbot_ker_server.py",
  "runtime/mcp/launchbot_feature_intake_server.py",
  "runtime/mcp/launchbot_help_article_server.py",
  "runtime/mcp/test_helpers.py",
  "runtime/mcp/test_launchbot_ker_server.py",
  "runtime/mcp/test_launchbot_feature_intake_server.py",
  "runtime/mcp/test_launchbot_help_article_server.py",
  "runtime/mcp/fixtures/help_article_video_fixtures.json",
  "skills/help-article-generator/SKILL.md",
  "skills/help-article-generator/references/help-article-skeleton.md",
  "skills/help-article-generator/references/intercom-format-profile.json",
  "skills/help-article-generator/references/article-planning-profile.json",
  "skills/help-article-generator/references/intercom-article-inventory.json",
  "skills/help-article-generator/references/video-placement-registry.json",
  "runtime/launch-workflow.md",
  "runtime/launchbot_e2e.py",
  "tests/launch-workflow-regression-cases.md",
  "tests/prompt-evals.json",
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
  "gateway_restart_notification: false",
  "C0B32M34J3W",
  "C0AJAUNCEL8",
  "C01RZ7SHC8K",
  "CF8PK6V4J",
  "launchbot_ker",
  "launchbot_feature_intake",
  "launchbot_help_article",
  "find_ker_ticket_from_slack_thread",
  "lookup_ker_ticket_by_key",
  "preview_feature_intake_from_slack_thread",
  "create_feature_intake_from_slack_thread",
  "preview_help_article_video_update",
  "create_help_article_video_update_draft",
  "JIRA_API_TOKEN",
  "LAUNCHBOT_FEATURE_INTAKE_ALLOWED_CHANNEL_IDS",
  "confirmed_jpd_intake_create",
  "required_confirmation: \"create intake\"",
  "LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN",
  "draft_only_registered_video_slots",
  "allow_publish: false",
  "allow_delete: false",
  "allow_tag_mutation: false",
  "allow_collection_mutation: false",
  "/home/leekaiyi/.hermes/profiles/launchbot/source/launchbot",
  "sources:",
  "pantheon:",
  "git@github.com:staffany-eng/pantheon.git",
  "LAUNCHBOT_PANTHEON_REPO_DIR",
  "LAUNCHBOT_PANTHEON_SSH_KEY",
]) {
  if (!configText.includes(requiredText)) fail(`config.template.yaml missing required text: ${requiredText}`);
}
if (configText.includes("/Users/leekaiyi/.hermes/profiles/launchbot/source/launchbot")) {
  fail("config.template.yaml must not point cloud runtime at the local Mac launchbot profile");
}

const profilesText = existsSync(join(repoRoot, "ops", "hermes", "profiles.yaml"))
  ? readFileSync(join(repoRoot, "ops", "hermes", "profiles.yaml"), "utf8")
  : "";
const launchbotProfileBlock = profileBlock(profilesText, "launchbot");
if (!launchbotProfileBlock) {
  fail("ops/hermes/profiles.yaml missing launchbot profile");
} else {
  for (const requiredText of [
    "deploy_host: hermes-data-bot-poc",
    "local_profile_policy: cloud_only",
    "systemd_unit: hermes-gateway-launchbot.service",
    "C01RZ7SHC8K",
    "CF8PK6V4J",
    "launchbot_feature_intake:",
    "launchbot_help_article:",
  ]) {
    if (!launchbotProfileBlock.includes(requiredText)) {
      fail(`launchbot profile missing required cloud-only text: ${requiredText}`);
    }
  }
  if (launchbotProfileBlock.includes("launchd_label:")) {
    fail("launchbot profile must not define a Mac launchd_label");
  }
}

const soulText = existsSync(join(appRoot, "profile", "SOUL.md"))
  ? readFileSync(join(appRoot, "profile", "SOUL.md"), "utf8")
  : "";
for (const requiredText of [
  "Do not use Kai Yi's user token",
  "Kai Yi's user token",
  "Confidence: <verified | needs-check | blocked>",
  "find_ker_ticket_from_slack_thread",
  "preview_feature_intake_from_slack_thread",
  "create_feature_intake_from_slack_thread",
  "create intake",
  "confirmed Slack-to-KER feature intake",
  "KER-2109",
  "cached Intercom article planning",
  "Pantheon-grounded help article drafts",
  "registered video-slot update drafts",
  "Intercom format checks",
  "message.channels",
  "Intercom draft/staging articles",
  "preview_help_article_video_update",
  "create_help_article_video_update_draft",
  "draft it",
  "skills/help-article-generator/references/video-placement-registry.json",
  "will_publish: false",
  "Launchbot packet",
  "Launch Superpower handoff is a Launchbot skill/workflow",
  "Never answer `Source: Launch Superpower Bot packet`",
  "#all-product-questions",
  "read-only product-commitment / KER lookup",
  "cloud-primary",
  "Launchbot's bot identity",
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
  "C01RZ7SHC8K",
]) {
  if (!mcpText.includes(requiredText)) fail(`launchbot_ker_server.py missing required text: ${requiredText}`);
}

for (const forbiddenText of ["chat.postMessage", "transitionIssue", "/comment", "/transitions"]) {
  if (mcpText.includes(forbiddenText)) fail(`launchbot_ker_server.py must not contain forbidden mutation surface: ${forbiddenText}`);
}

const featureIntakeMcpText = textOf("runtime/mcp/launchbot_feature_intake_server.py");
for (const requiredText of [
  "SLACK_BOT_TOKEN",
  "JIRA_BASE_URL",
  "JIRA_EMAIL",
  "JIRA_API_TOKEN",
  "conversations.replies",
  "/rest/api/3/search/jql",
  "/rest/api/3/issue?notifyUsers=false",
  "preview_feature_intake_from_slack_thread",
  "create_feature_intake_from_slack_thread",
  "CONFIRMATION_PHRASES",
  "create intake",
  "customfield_10080",
  "CF8PK6V4J",
  "will_mutate_jira",
  "will_post_message",
  "transcript_persisted",
]) {
  if (!featureIntakeMcpText.includes(requiredText)) fail(`launchbot_feature_intake_server.py missing required text: ${requiredText}`);
}
for (const forbiddenText of ["chat.postMessage", "transitionIssue", "/comment", "/transitions", "DELETE"]) {
  if (featureIntakeMcpText.includes(forbiddenText)) fail(`launchbot_feature_intake_server.py must not contain forbidden mutation surface: ${forbiddenText}`);
}

const helpArticleMcpText = textOf("runtime/mcp/launchbot_help_article_server.py");
for (const requiredText of [
  "LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN",
  "preview_help_article_video_update",
  "create_help_article_video_update_draft",
  "normalize_loom_embed_url",
  "replace_next_video_after_anchor",
  "LOOM_IFRAME_RE",
  "PUT",
  "\"state\": \"draft\"",
  "will_publish",
  "will_mutate_tags_or_collections",
]) {
  if (!helpArticleMcpText.includes(requiredText)) fail(`launchbot_help_article_server.py missing required text: ${requiredText}`);
}
for (const forbiddenText of ["\"state\": \"published\"", "method=\"DELETE\"", "method='DELETE'"]) {
  if (helpArticleMcpText.includes(forbiddenText)) fail(`launchbot_help_article_server.py must not contain forbidden mutation surface: ${forbiddenText}`);
}

const healthText = textOf("runtime/check-health.sh");
for (const requiredText of [
  "pantheon:checkout-missing",
  "pantheon:remote-unexpected",
  "pantheon:status-stale",
  "platforms:slack:gateway-restart-notification-not-disabled",
  "LAUNCHBOT_PANTHEON_REPO_DIR",
  "mcp:launchbot_help_article",
  "mcp:launchbot_feature_intake",
  "EXPECT_KER_ALLOWED_CHANNELS",
  "mcp:launchbot_ker:default-channel-missing",
  "mcp:launchbot_ker:env-channel-missing",
  "mcp:launchbot_ker:process-env-channel-missing",
  "LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN",
  "help-article-video-registry",
]) {
  if (!healthText.includes(requiredText)) fail(`check-health.sh missing required Pantheon health text: ${requiredText}`);
}

const auditText = textOf("runtime/audit-live-profile.sh");
for (const requiredText of [
  "cron:health-check-missing",
  "cron:pantheon-repo-update-missing",
  "cron:pantheon-repo-update-present-without-github-ssh",
  "GIT_TERMINAL_PROMPT=0 git ls-remote",
  "profile-drift:help-article-mcp",
  "profile-drift:feature-intake-mcp",
  "profile-drift:help-article-video-registry",
]) {
  if (!auditText.includes(requiredText)) fail(`audit-live-profile.sh missing required cron/access text: ${requiredText}`);
}

const pantheonUpdateText = textOf("runtime/update-pantheon-repo.sh");
for (const requiredText of [
  "git clone --branch",
  "pull --ff-only",
  "pantheon:updated",
  "LAUNCHBOT_PANTHEON_REPO_URL",
  "LAUNCHBOT_PANTHEON_SSH_KEY",
  "GIT_SSH_COMMAND",
  "pantheon-repo-status.json",
]) {
  if (!pantheonUpdateText.includes(requiredText)) fail(`update-pantheon-repo.sh missing required text: ${requiredText}`);
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
  "cached Intercom article-shape profile",
  "needs-intake",
  "missing high-impact questions",
  "launchbot-with-secrets.mjs",
  "help-article:shape-refresh",
  "intercom:inventory",
  "help-article:plan",
  "help-article:format-check",
  "intercom:affected",
  "intercom:stage-update",
  "help-article:pantheon-scan",
  "help-article:evidence-check",
  "Pantheon evidence",
  "Public publishing stays manual in Intercom",
  "A brand is the business profile",
  "A perk sits under a brand",
  "For ClubAny / Club Blue content, set Product to `StaffAny`",
  "numbered steps from `1` for each subsection",
  "Update -> Video-only update",
  "references/video-placement-registry.json",
  "will_publish: false",
  "state: \"draft\"",
  "registry-only and draft-only",
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

const videoRegistryPath = join(appRoot, "skills", "help-article-generator", "references", "video-placement-registry.json");
const videoRegistry = existsSync(videoRegistryPath) ? sharedReadJson(videoRegistryPath, fail) : null;
if (!videoRegistry) {
  fail("Missing video placement registry");
} else {
  if (videoRegistry.version !== 1) fail("Video placement registry must be version 1");
  const articles = Array.isArray(videoRegistry.articles) ? videoRegistry.articles : [];
  const articleKeys = new Set(articles.map((article) => article.article_key));
  for (const key of ["web-app-timesheet", "run-payroll", "general-settings"]) {
    if (!articleKeys.has(key)) fail(`Video placement registry missing fixture article: ${key}`);
  }
  for (const article of articles) {
    for (const key of ["article_key", "locale", "title", "public_url", "intercom_article_id", "slots"]) {
      if (!article[key]) fail(`Video placement registry article missing field: ${key}`);
    }
    if (article.locale !== "en") fail(`Video placement registry V1 must be English-only: ${article.article_key}`);
    for (const slot of article.slots || []) {
      for (const key of ["slot_id", "purpose", "anchor_text", "provider", "replace_policy"]) {
        if (!slot[key]) fail(`Video placement registry slot missing field: ${key}`);
      }
      if (slot.provider !== "loom") fail(`Video placement registry slot must be Loom-only: ${slot.slot_id}`);
      if (slot.replace_policy !== "replace_next_video_after_anchor") {
        fail(`Video placement registry slot has unsupported policy: ${slot.slot_id}`);
      }
    }
  }
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
  "Pantheon Evidence, Intercom Format Profile, And Pre-Publish Gates",
  "Midas/Karpathy-style ingest",
  "help-article:shape-refresh",
  "help-article:shape-ingest",
  "intercom:inventory",
  "help-article:plan",
  "intercom:format:pull",
  "help-article:format-check",
  "intercom:affected",
  "intercom:stage-update",
  "help-article:pantheon-scan",
  "help-article:evidence-check",
  "LAUNCH_INTERCOM_SHAPE_FAMILIES",
  "intercom-article-inventory.json",
  "cached inventory for affected article lookup",
  "live Intercom wins",
  "pre-stage target-article stale check",
  "Public publishing stays manual in Intercom",
  "bot-owned posting credentials",
  "@Launch Bot",
  "U0ASVD79UT1",
  "B0ATPPEGBCH",
  "message.channels",
  "channels:history",
  "#launch-bot-testing",
  "#all-product-questions",
  "C01RZ7SHC8K",
  "light cowboy voice",
  "Do not commit token values",
  "Step 4 launch derivatives are not implemented",
  "Pantheon checkout",
  "apps/kraken",
  "apps/gryphon",
  "apps/pixie",
  "Video-only Help Article Update",
  "video-placement-registry.json",
  "preview_help_article_video_update",
  "create_help_article_video_update_draft",
  "replace_next_video_after_anchor",
  "raw `.mp4`, Slack file URLs",
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
  "run_intercom_format_gate",
  "run_help_article_plan",
  "run_pantheon_evidence_gate",
  "help-article:plan",
  "article_plan_status",
  "pantheon_evidence_gate",
  "help-article:format-check",
  "help-article:evidence-check",
  "NODE_BINARY",
  "format_gate_status",
]) {
  if (!e2eRunnerText.includes(requiredText)) fail(`Launch workflow runner missing required text: ${requiredText}`);
}

const intercomGateText = textOf("runtime/intercom-format-gate.mjs");
for (const requiredText of [
  "intercom:format:pull",
  "intercom:format:profile",
  "intercom:inventory",
  "help-article:shape-refresh",
  "help-article:shape-ingest",
  "help-article:plan",
  "help-article:format-check",
  "help-article:pantheon-scan",
  "help-article:evidence-check",
  "intercom:affected",
  "intercom:stage-update",
  "LAUNCH_PANTHEON_REPO",
  "DEFAULT_ARTICLE_SHAPE_PROFILE_PATH",
  "DEFAULT_ARTICLE_INVENTORY_PATH",
  "buildArticleInventory",
  "buildArticlePlanningProfile",
  "planHelpArticles",
  "evaluateHelpArticleIntake",
  "needs-intake",
  "--surface",
  "--audience",
  "--outcome",
  "checkArticleShapeFreshness",
  "LAUNCH_INTERCOM_SHAPE_FAMILIES",
  "LAUNCH_INTERCOM_INVENTORY_STATE",
  "affected_articles_from_cached_inventory",
  "pre_stage_stale_check",
  "needs-refresh",
  "DEFAULT_PANTHEON_REPO",
  "scanPantheonEvidence",
  "checkPantheonEvidence",
  "dirty_pantheon_repo",
  "ambiguous_pantheon_app",
  "unsupported_product_behavior_claim",
  "internal_pantheon_app_name_leakage",
  "LAUNCH_INTERCOM_HELP_CENTER_ID",
  "LAUNCH_INTERCOM_FORMAT_SAMPLE_IDS",
  "LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN",
  "INTERCOM_ACCESS_TOKEN",
  "read_stage_only",
  "draft_only",
  "missing_audience_metadata",
  "repeated_title_in_body",
  "raw_html_or_markdown_leakage",
  "text_divider_lines",
  "internal_appendix",
  "bad_list_numbering",
  "missing_faq",
  "missing_numbered_outline",
  "state: \"draft\"",
  "apiRequest(\"GET\", \"/articles/search\"",
  "apiRequest(\"GET\", `/articles/${encodeURIComponent(id)}`",
]) {
  if (!intercomGateText.includes(requiredText)) fail(`Intercom format gate missing required text: ${requiredText}`);
}
if (/apiRequest\("PUT"|method:\s*"PUT"/.test(intercomGateText)) {
  fail("Intercom format gate must not contain publish/update write paths");
}

const secretWrapperPath = join(repoRoot, "scripts/launchbot-with-secrets.mjs");
if (!existsSync(secretWrapperPath)) fail("Missing LaunchBot Secret Manager wrapper");
const secretWrapperText = existsSync(secretWrapperPath) ? readFileSync(secretWrapperPath, "utf8") : "";
for (const requiredText of [
  "launchbot-step3-intercom-access-token",
  "LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN",
  "INTERCOM_ACCESS_TOKEN",
  "staffany-warehouse",
  "values_printed",
  "gcloud",
  "secrets",
  "versions",
  "access",
  "latest",
]) {
  if (!secretWrapperText.includes(requiredText)) fail(`Secret Manager wrapper missing required text: ${requiredText}`);
}
if (/console\.log\(.*value|stdout\.write\(.*value/.test(secretWrapperText)) {
  fail("Secret Manager wrapper must not print secret values");
}

const nodeTest = spawnSync(
  process.execPath,
  ["--test", join(appRoot, "runtime", "intercom-format-gate.test.mjs")],
  { encoding: "utf8" }
);
if (nodeTest.status !== 0) {
  fail(`Intercom format gate tests failed: ${(nodeTest.stderr || nodeTest.stdout || "").trim()}`);
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
const intercomShapeSourceNotePath = join(repoRoot, "research/wiki/sources/staffany-intercom-help-article-shape.md");
if (!existsSync(intercomShapeSourceNotePath)) fail("Missing maintained Intercom help article shape source note");
const helpArticlePlanningSynthesisPath = join(repoRoot, "research/wiki/syntheses/help-article-planning-rules.md");
if (!existsSync(helpArticlePlanningSynthesisPath)) fail("Missing help article planning rules synthesis");

const regressionText = textOf("tests/launch-workflow-regression-cases.md");
for (const requiredText of [
  "#launch-bot-testing",
  "#all-product-questions",
  "C01RZ7SHC8K",
  "@Launch Bot",
  "U0ASVD79UT1",
  "B0ATPPEGBCH",
  "message.channels",
  "light cowboy voice",
  "help-article:shape-refresh",
  "help-article:plan",
  "needs-intake",
  "intake.questions",
  "article_shape_stale_check.status: needs-refresh",
  "Video-only Help Article Updates",
  "will_publish: false",
  "state: \"draft\"",
  "no registered slot match",
]) {
  if (!regressionText.includes(requiredText)) fail(`Launch workflow regression cases missing required text: ${requiredText}`);
}

const packageJson = existsSync(join(repoRoot, "package.json"))
  ? sharedReadJson(join(repoRoot, "package.json"), fail)
  : null;
if (packageJson) {
  const intercomRuntimeScripts = [
    "intercom:format:pull",
    "intercom:format:profile",
    "intercom:inventory",
    "help-article:shape-refresh",
    "help-article:shape-ingest",
    "help-article:plan",
    "help-article:format-check",
    "intercom:affected",
    "intercom:stage-update",
    "help-article:pantheon-scan",
    "help-article:evidence-check",
  ];
  for (const scriptName of intercomRuntimeScripts) {
    if (!packageJson.scripts?.[scriptName]?.includes("apps/launchbot/runtime/intercom-format-gate.mjs")) {
      fail(`package.json missing Launchbot script ${scriptName}`);
    }
  }
  if (!packageJson.scripts?.["launchbot:with-secrets"]?.includes("launchbot-with-secrets.mjs")) {
    fail("package.json missing script launchbot:with-secrets");
  }
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
