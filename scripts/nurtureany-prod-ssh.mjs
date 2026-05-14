#!/usr/bin/env node
import { spawnSync } from "node:child_process";

const DEFAULTS = {
  project: "staffany-warehouse",
  zone: "asia-southeast1-a",
  vm: "nurtureany-sales-bot-prod",
  runtimeOwner: "leekaiyi",
  profile: "nurtureanysalesbot",
};

const GCLOUD_CANDIDATES = [
  process.env.GCLOUD_BIN,
  "gcloud",
  "/opt/homebrew/share/google-cloud-sdk/bin/gcloud",
  "/usr/local/share/google-cloud-sdk/bin/gcloud",
].filter(Boolean);

const args = parseArgs(process.argv.slice(2));

if (args.help) {
  printHelp();
  process.exit(0);
}

const gcloud = resolveCommand("gcloud", GCLOUD_CANDIDATES);
const remoteCommand = buildRemoteCommand(args);

run(gcloud, [
  "compute",
  "ssh",
  args.vm,
  "--project",
  args.project,
  "--zone",
  args.zone,
  "--tunnel-through-iap",
  "--command",
  remoteCommand,
]);

function parseArgs(argv) {
  const parsed = {
    ...DEFAULTS,
    mode: "status",
    command: "",
    verbose: false,
    help: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const raw = argv[index];
    if (raw === "--help" || raw === "-h") {
      parsed.help = true;
      continue;
    }
    if (raw === "--verbose") {
      parsed.verbose = true;
      continue;
    }
    if (raw === "--status") {
      parsed.mode = "status";
      continue;
    }
    if (raw === "--health") {
      parsed.mode = "health";
      continue;
    }
    if (raw === "--socket") {
      parsed.mode = "socket";
      continue;
    }
    if (raw === "--doctor") {
      parsed.mode = "doctor";
      continue;
    }
    if (raw === "--shell") {
      parsed.mode = "shell";
      continue;
    }
    if (raw === "--command") {
      parsed.mode = "command";
      parsed.command = requireValue(argv, ++index, raw);
      continue;
    }
    if (raw === "--project") {
      parsed.project = requireValue(argv, ++index, raw);
      continue;
    }
    if (raw === "--zone") {
      parsed.zone = requireValue(argv, ++index, raw);
      continue;
    }
    if (raw === "--vm") {
      parsed.vm = requireValue(argv, ++index, raw);
      continue;
    }
    if (raw === "--runtime-owner") {
      parsed.runtimeOwner = requireValue(argv, ++index, raw);
      continue;
    }
    if (raw === "--profile") {
      parsed.profile = requireValue(argv, ++index, raw);
      continue;
    }
    throw new Error(`Unknown option: ${raw}`);
  }

  return parsed;
}

function requireValue(argv, index, flag) {
  const value = argv[index];
  if (!value || value.startsWith("--")) {
    throw new Error(`Missing value for ${flag}`);
  }
  return value;
}

function buildRemoteCommand(options) {
  const profileDir = `/home/${options.runtimeOwner}/.hermes/profiles/${options.profile}`;
  const service = `hermes-gateway-${options.profile}.service`;
  const runtimeCommand = runtimeCommandForMode(options, profileDir, service);

  return [
    "set -euo pipefail",
    `runtime_owner=${shellQuote(options.runtimeOwner)}`,
    "uid=$(id -u \"$runtime_owner\")",
    `sudo -H -u "$runtime_owner" XDG_RUNTIME_DIR="/run/user/$uid" HERMES_PROFILE_DIR=${shellQuote(profileDir)} HERMES_HOME=${shellQuote(profileDir)} bash -lc ${shellQuote(runtimeCommand)}`,
  ].join("; ");
}

function runtimeCommandForMode(options, profileDir, service) {
  const pathPrefix = "export PATH=\"$HOME/.local/bin:$HOME/.hermes/hermes-agent:$PATH\"";
  const quotedService = shellQuote(service);
  const quotedProfileDir = shellQuote(profileDir);

  switch (options.mode) {
    case "status":
      return `${pathPrefix}; systemctl --user status ${quotedService} --no-pager -l`;
    case "health":
      return `${pathPrefix}; ${quotedProfileDir}/scripts/nurtureanysalesbot-check-health.sh; echo check_health_exit:$?`;
    case "socket":
      return `${pathPrefix}; ${quotedProfileDir}/scripts/nurtureanysalesbot-check-slack-socket-health.sh; echo socket_health_exit:$?`;
    case "doctor":
      return `${pathPrefix}; ${quotedProfileDir}/scripts/nurtureanysalesbot-cloud-doctor.sh`;
    case "shell":
      return "exec bash -l";
    case "command":
      return `${pathPrefix}; ${options.command}`;
    default:
      throw new Error(`Unsupported mode: ${options.mode}`);
  }
}

function resolveCommand(label, candidates) {
  for (const candidate of candidates) {
    const result = spawnSync(candidate, ["--version"], { encoding: "utf8" });
    if (!result.error && result.status === 0) {
      return candidate;
    }
  }
  throw new Error(`Required command not available: ${label}`);
}

function run(command, commandArgs) {
  if (args.verbose) {
    console.error(`$ ${[command, ...commandArgs].join(" ")}`);
  }
  const result = spawnSync(command, commandArgs, {
    stdio: "inherit",
    encoding: "utf8",
  });
  if (result.error) {
    throw result.error;
  }
  process.exit(result.status ?? 1);
}

function shellQuote(value) {
  return `'${String(value).replaceAll("'", "'\\''")}'`;
}

function printHelp() {
  console.log(`Usage: node scripts/nurtureany-prod-ssh.mjs [mode] [options]

SSH into NurtureAny production and run commands as the real Hermes runtime user.

Modes:
  --status                 Show systemd user service status. Default.
  --health                 Run NurtureAny health check.
  --socket                 Run Slack Socket Mode watchdog check.
  --doctor                 Run redacted cloud doctor.
  --command <cmd>          Run a custom command as the runtime user.
  --shell                  Open a login shell as the runtime user.

Options:
  --project <id>           GCP project. Default: ${DEFAULTS.project}
  --zone <zone>            GCP zone. Default: ${DEFAULTS.zone}
  --vm <name>              VM name. Default: ${DEFAULTS.vm}
  --runtime-owner <user>   Runtime OS user. Default: ${DEFAULTS.runtimeOwner}
  --profile <name>         Hermes profile. Default: ${DEFAULTS.profile}
  --verbose                Print the resolved gcloud command.
  --help                   Show this help.

Notes:
  - Resolves gcloud from PATH, /opt/homebrew, or /usr/local.
  - GCP OS Login may land as another user; this script switches to ${DEFAULTS.runtimeOwner}.
  - The runtime command always sets XDG_RUNTIME_DIR for the runtime user's systemd.
`);
}
