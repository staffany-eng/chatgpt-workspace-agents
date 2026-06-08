#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";

const DEFAULT_PROJECT = "staffany-warehouse";

const SECRET_SPECS = [
  {
    group: "hubspot",
    secret: "hubspot-access-token",
    env: "HUBSPOT_ACCESS_TOKEN",
    aliases: ["HUBSPOT_PRIVATE_APP_TOKEN"]
  },
  {
    group: "jira",
    secret: "customer-360-jira-email",
    env: "JIRA_EMAIL"
  },
  {
    group: "jira",
    secret: "customer-360-jira-api-token",
    env: "JIRA_API_TOKEN"
  },
  {
    group: "intercom",
    secret: "launchbot-step3-intercom-access-token",
    env: "LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN",
    aliases: ["INTERCOM_ACCESS_TOKEN"]
  },
  {
    group: "slack",
    secret: "launchbot-step2-slack-bot-token",
    env: "LAUNCH_STEP2_SLACK_BOT_TOKEN"
  },
  {
    group: "slack",
    secret: "launchbot-step3-slack-bot-token",
    env: "LAUNCH_STEP3_SLACK_BOT_TOKEN"
  },
  {
    group: "slack",
    secret: "launchbot-step3-slack-signing-secret",
    env: "LAUNCH_STEP3_SLACK_SIGNING_SECRET"
  },
  {
    group: "google",
    secret: "launchbot-google-workspace-auth-json",
    env: "LAUNCH_GOOGLE_AUTH_JSON"
  },
  {
    group: "staging",
    secret: "launchbot-staging-url",
    env: "LAUNCHBOT_STAGING_URL",
    aliases: ["STAFFANY_STAGING_URL"]
  },
  {
    group: "staging",
    secret: "launchbot-staging-email",
    env: "LAUNCHBOT_STAGING_EMAIL"
  },
  {
    group: "staging",
    secret: "launchbot-staging-password",
    env: "LAUNCHBOT_STAGING_PASSWORD"
  }
];

function usage() {
  return [
    "Usage:",
    "  node scripts/launchbot-with-secrets.mjs [--project <gcp-project>] [--only intercom,slack,google,jira,hubspot,staging] -- <command> [args...]",
    "  node scripts/launchbot-with-secrets.mjs --check [--only intercom]",
    "",
    "Examples:",
    "  node scripts/launchbot-with-secrets.mjs --only intercom -- node apps/launch-superpower-bot/runtime/intercom-format-gate.mjs intercom:affected --topic ClubAny",
    "  node scripts/launchbot-with-secrets.mjs --check --only intercom"
  ].join("\\n");
}

function parseArgs(argv) {
  const separator = argv.indexOf("--");
  const optionArgs = separator === -1 ? argv : argv.slice(0, separator);
  const command = separator === -1 ? [] : argv.slice(separator + 1);
  const options = {
    project: process.env.LAUNCHBOT_GCP_PROJECT || DEFAULT_PROJECT,
    only: new Set(["intercom", "slack", "google", "jira", "hubspot", "staging"]),
    check: false
  };

  for (let index = 0; index < optionArgs.length; index += 1) {
    const arg = optionArgs[index];
    if (arg === "--project") {
      options.project = optionArgs[index + 1] || "";
      index += 1;
    } else if (arg === "--only") {
      options.only = new Set(
        String(optionArgs[index + 1] || "")
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean)
      );
      index += 1;
    } else if (arg === "--check") {
      options.check = true;
    } else if (arg === "-h" || arg === "--help") {
      console.log(usage());
      process.exit(0);
    } else {
      throw new Error(`Unknown option: ${arg}\\n${usage()}`);
    }
  }

  if (!options.project) throw new Error("Missing --project");
  return { options, command };
}

function findGcloud() {
  const candidates = [
    process.env.GCLOUD_BIN,
    "gcloud",
    "/opt/homebrew/bin/gcloud",
    "/usr/local/bin/gcloud",
    `${process.env.HOME || ""}/google-cloud-sdk/bin/gcloud`
  ].filter(Boolean);
  for (const candidate of candidates) {
    if (candidate.includes("/") && !existsSync(candidate)) continue;
    const result = spawnSync(candidate, ["--version"], { encoding: "utf8" });
    if (result.status === 0) return candidate;
  }
  throw new Error("gcloud CLI not found. Install gcloud or set GCLOUD_BIN.");
}

function accessSecret({ gcloud, project, secret }) {
  const result = spawnSync(
    gcloud,
    ["secrets", "versions", "access", "latest", "--project", project, "--secret", secret],
    { encoding: "utf8", maxBuffer: 10 * 1024 * 1024 }
  );
  if (result.status !== 0) {
    const detail = (result.stderr || result.stdout || "").trim();
    throw new Error(`Secret Manager access failed for ${secret}: ${detail}`);
  }
  return result.stdout.replace(/\\n$/, "");
}

function buildSecretEnv({ project, only }) {
  const gcloud = findGcloud();
  const env = { ...process.env };
  const loaded = [];
  const skipped = [];

  for (const spec of SECRET_SPECS) {
    if (!only.has(spec.group)) {
      skipped.push(spec.env);
      continue;
    }
    const value = accessSecret({ gcloud, project, secret: spec.secret });
    if (!value) throw new Error(`Secret Manager returned an empty value for ${spec.secret}`);
    env[spec.env] = value;
    loaded.push({ group: spec.group, secret: spec.secret, env: spec.env });
    for (const alias of spec.aliases || []) {
      env[alias] = value;
      loaded.push({ group: spec.group, secret: spec.secret, env: alias, alias_for: spec.env });
    }
  }

  return { env, loaded, skipped, project };
}

function main(argv = process.argv.slice(2)) {
  const { options, command } = parseArgs(argv);
  const { env, loaded, skipped, project } = buildSecretEnv(options);

  if (options.check) {
    console.log(JSON.stringify({
      status: "ok",
      project,
      loaded_env_names: loaded.map((item) => item.env),
      skipped_env_names: skipped,
      values_printed: false
    }, null, 2));
    return 0;
  }

  if (command.length === 0) throw new Error(`Missing command after --\\n${usage()}`);
  const result = spawnSync(command[0], command.slice(1), {
    stdio: "inherit",
    env
  });
  if (result.error) throw result.error;
  return result.status || 0;
}

try {
  process.exitCode = main();
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
