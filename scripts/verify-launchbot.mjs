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

const manifest = existsSync(manifestPath) ? sharedReadJson(manifestPath, fail) : null;
if (!manifest) {
  fail("Missing apps/launchbot/app.manifest.json");
} else {
  if (manifest.profile_name !== "launchbot") fail("Manifest profile_name must be launchbot");
  if (manifest.secrets_copied !== false) fail("Manifest secrets_copied must be false");
  for (const value of Object.values(manifest.paths || {})) {
    assertFile(value);
  }
  if (manifest.source_repositories?.pantheon?.remote !== "git@github.com:staffany-eng/pantheon.git") {
    fail("Manifest Pantheon remote must be staffany-eng/pantheon");
  }
  if (manifest.source_repositories?.pantheon?.branch !== "develop") {
    fail("Manifest Pantheon branch must be develop");
  }
  const pantheonCron = (manifest.expected_crons || []).find((cron) => cron.name === "launchbot pantheon repo update");
  if (pantheonCron?.schedule !== "0 22 * * *") fail("Manifest must define daily Pantheon repo update cron");
  if (pantheonCron?.mode !== "no-agent") fail("Manifest Pantheon repo update cron must be no-agent");
}

for (const relPath of [
  "profile/SOUL.md",
  "profile/config.template.yaml",
  "runtime/slack.md",
  "runtime/health-checks.md",
  "runtime/check-health.sh",
  "runtime/audit-live-profile.sh",
  "runtime/update-pantheon-repo.sh",
  "runtime/mcp/profile_env.py",
  "runtime/mcp/launchbot_ker_server.py",
  "runtime/mcp/test_helpers.py",
  "runtime/mcp/test_launchbot_ker_server.py",
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
  "sources:",
  "pantheon:",
  "git@github.com:staffany-eng/pantheon.git",
  "LAUNCHBOT_PANTHEON_REPO_DIR",
  "LAUNCHBOT_PANTHEON_SSH_KEY",
]) {
  if (!configText.includes(requiredText)) fail(`config.template.yaml missing required text: ${requiredText}`);
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
  "experimental",
  "Pantheon Source Of Truth",
  "git@github.com:staffany-eng/pantheon.git",
  "Jira tickets and PRDs can explain launch intent",
]) {
  if (!soulText.includes(requiredText)) fail(`SOUL.md missing required text: ${requiredText}`);
}

const healthText = existsSync(join(appRoot, "runtime", "health-checks.md"))
  ? readFileSync(join(appRoot, "runtime", "health-checks.md"), "utf8")
  : "";
for (const requiredText of [
  "Pantheon is cloned",
  "launchbot pantheon repo update",
  "0 22 * * *",
]) {
  if (!healthText.includes(requiredText)) fail(`health-checks.md missing required text: ${requiredText}`);
}

const updatePantheonText = existsSync(join(appRoot, "runtime", "update-pantheon-repo.sh"))
  ? readFileSync(join(appRoot, "runtime", "update-pantheon-repo.sh"), "utf8")
  : "";
for (const requiredText of [
  "LAUNCHBOT_PANTHEON_REPO_DIR",
  "git@github.com:staffany-eng/pantheon.git",
  "develop",
  "LAUNCHBOT_PANTHEON_SSH_KEY",
  "GIT_SSH_COMMAND",
  "git clone --branch",
  "git -C \"$PANTHEON_REPO_DIR\" pull --ff-only origin \"$PANTHEON_BRANCH\"",
  "pantheon-repo-status.json",
]) {
  if (!updatePantheonText.includes(requiredText)) fail(`update-pantheon-repo.sh missing required text: ${requiredText}`);
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
