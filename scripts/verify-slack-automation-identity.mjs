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
      "When asked to check Slack for bot/runtime work, use the relevant Slack bot token",
      "Do not use the Slack connector or Kai Yi's user token for Slack inspection when a relevant bot token exists",
      "Use Kai Yi's user token or the Slack UI only for explicit human-authored smoke tests",
      "Every automation-authored Slack status must identify itself as automation",
      "After any automation bug fix, repair, deploy, or blocked repair, always emit a completion report",
    ],
  },
  {
    path: join(repoRoot, "apps/hermes-data-bot/AGENTS.md"),
    required: [
      "Do not send visible Slack automation replies using Kai Yi's user token",
      "When asked to check Slack for Hermes bot/runtime work, use the relevant Slack bot token",
      "Do not use the Slack connector or Kai Yi's user token for Slack inspection when the Hermes bot token exists",
      "Use Kai Yi's user token or the Slack UI only for explicit human-authored smoke tests",
      "Every automation-authored Slack status must identify itself as automation",
      "After any automation bug fix, repair, deploy, or blocked repair, always emit a completion report",
    ],
  },
  {
    path: join(repoRoot, "apps/hermes-data-bot/runtime/slack.md"),
    required: [
      "Operational Slack checks for bot/runtime work must use the relevant Slack bot token",
      "Do not use the Slack connector or Kai Yi's user token for Slack inspection when the Hermes bot token exists",
      "User token or Slack UI evidence is allowed only for explicit human-authored smoke tests",
    ],
  },
  {
    path: join(repoRoot, "package.json"),
    required: [
      '"hooks:install": "git config core.hooksPath .githooks"',
      '"slack-automation-identity:verify": "node scripts/verify-slack-automation-identity.mjs"',
    ],
  },
  {
    path: join(repoRoot, "skills/verify-target-environment/SKILL.md"),
    required: [
      "profile's prefix from `ops/hermes/profiles.yaml`",
      "Your Slack UI or user credential may send only the explicit human-authored trigger",
      "Bot-token paths own Slack reads, result checks, and automation status delivery",
      "Visible automation status must come from the target bot/app identity",
      "Never post automation status as Kai Yi",
      "Never use Slack connector writes for this flow",
      "close the loop in that original thread with a bot-owned reply",
      "blocked: bot-owned Slack delivery unavailable",
      "npm run slack-automation-identity:verify",
    ],
  },
  {
    path: join(repoRoot, "skills/verify-target-environment/agents/openai.yaml"),
    required: [
      'display_name: "Verify Target Environment"',
      'short_description: "Verify bot deploys in target env"',
      "Use $verify-target-environment",
    ],
  },
  {
    path: join(repoRoot, ".githooks/pre-commit"),
    required: [
      "npm run slack-automation-identity:verify",
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
  {
    pattern: /(^|[.\n]\s*[-*]?\s*)(Use|use|Default to|default to|Route through|route through) the Slack connector[^.\n]*(?:check|inspect|read|monitor|diagnostic)/,
    reason: "routes Slack inspection through the connector instead of the relevant bot token",
  },
  {
    pattern: /(?:check|inspect|read|monitor|diagnostic)[^.\n]*Slack[^.\n]*(?:Kai Yi's user token|SLACK_USER_TOKEN)/i,
    reason: "routes Slack inspection through Kai Yi's user token instead of the relevant bot token",
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
