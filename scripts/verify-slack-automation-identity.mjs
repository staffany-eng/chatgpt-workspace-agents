import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const repoRoot = fileURLToPath(new URL("..", import.meta.url));
const home = process.env.HOME;

const checks = [
  {
    path: join(repoRoot, "AGENTS.md"),
    required: [
      "Do not send visible Slack automation replies using Kai Yi's user token",
      "Every automation-authored Slack status must identify itself as automation",
      "After any automation bug fix, repair, deploy, or blocked repair, always emit a completion report",
    ],
  },
  {
    path: join(repoRoot, "apps/hermes-data-bot/AGENTS.md"),
    required: [
      "Do not send visible Slack automation replies using Kai Yi's user token",
      "Every automation-authored Slack status must identify itself as automation",
      "After any automation bug fix, repair, deploy, or blocked repair, always emit a completion report",
    ],
  },
  {
    path: join(home, ".codex/automations/watch-customer-360-slack-requests/automation.toml"),
    optional: true,
    required: [
      "Do not send visible Slack messages using Kai Yi's user token",
      "Customer 360 automation:",
      "Every bug fix, deploy, or blocked repair must produce a completion report",
    ],
  },
  {
    path: join(home, ".codex/automations/watch-slack-bot-stuck-threads/automation.toml"),
    optional: true,
    required: [
      "Do not use Kai Yi's user token",
      "Hermes repair automation:",
      "Every bug/runtime repair or blocked repair must produce a completion report",
    ],
  },
];

const forbiddenPatterns = [
  {
    pattern: /use Kai Yi's local Slack user token, not the Slack connector identity/i,
    reason: "tells the automation to post/read as Kai Yi's local Slack user token",
  },
  {
    pattern: /SLACK_USER_TOKEN[^.]+chat\.postMessage/is,
    reason: "allows chat.postMessage with the user token",
  },
  {
    pattern: /using Kai Yi's local Slack user token/i,
    reason: "uses Kai Yi's local token as a visible posting identity",
  },
  {
    pattern: /using Kai Yi's local token/i,
    reason: "uses Kai Yi's local token as a visible posting identity",
  },
  {
    pattern: /Reply in the original Slack thread first using Kai Yi/i,
    reason: "starts repair by posting as Kai Yi",
  },
  {
    pattern: /post a final repair status in the original thread using Kai Yi/i,
    reason: "finishes repair by posting as Kai Yi",
  },
  {
    pattern: /Use Kai Yi's local Slack user token for the test\/status post/i,
    reason: "tests or reports as Kai Yi",
  },
];

const failures = [];

for (const check of checks) {
  if (!existsSync(check.path)) {
    if (!check.optional) {
      failures.push(`${check.path}: missing required file`);
    }
    continue;
  }

  const text = readFileSync(check.path, "utf8");

  for (const required of check.required) {
    if (!text.includes(required)) {
      failures.push(`${check.path}: missing required rule: ${required}`);
    }
  }

  for (const { pattern, reason } of forbiddenPatterns) {
    if (pattern.test(text)) {
      failures.push(`${check.path}: forbidden Slack identity wording: ${reason}`);
    }
  }
}

if (failures.length > 0) {
  console.error("Slack automation identity verification failed:");
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  process.exit(1);
}

console.log("Slack automation identity verification passed.");
