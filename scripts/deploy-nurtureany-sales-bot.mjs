#!/usr/bin/env node
import { existsSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
const tmpRoot = existsSync("/private/tmp") ? "/private/tmp" : tmpdir();

const DEFAULTS = {
  project: "staffany-warehouse",
  zone: "asia-southeast1-a",
  vm: "nurtureany-sales-bot-prod",
  profile: "nurtureanysalesbot",
  runtimeOwner: "leekaiyi",
};

const FORBIDDEN_RUNTIME_STATE_LABELS = [
  ".env",
  "OAuth files",
  "NURTUREANY_ACCESS_POLICY_PATH",
  "cron",
  "logs",
  "sessions",
  "daily-runs",
  "operation-ledger",
];

const args = parseArgs(process.argv.slice(2));

if (args.help) {
  printHelp();
  process.exit(0);
}

const gitCommand = resolveCommand("git", ["git"]);
const npmCommand = resolveCommand("npm", ["npm", "/opt/homebrew/bin/npm", "/usr/local/bin/npm"]);
const gcloudCommand = resolveCommand("gcloud", [
  "gcloud",
  "/opt/homebrew/share/google-cloud-sdk/bin/gcloud",
  "/usr/local/share/google-cloud-sdk/bin/gcloud",
]);

log("Preparing NurtureAny Sales Bot deploy from origin/main");
log(`Target: project=${args.project} zone=${args.zone} vm=${args.vm} profile=${args.profile} runtime_owner=${args.runtimeOwner}`);
if (args.verbose) {
  log(`Preserved runtime state: ${FORBIDDEN_RUNTIME_STATE_LABELS.join(", ")}`);
}

run(gitCommand, ["fetch", "origin", "main"]);
const deploySha = runCapture(gitCommand, ["rev-parse", "origin/main"]).trim();
if (!deploySha) {
  throw new Error("Could not resolve origin/main deploy SHA.");
}
log(`Deploy SHA: ${deploySha}`);

run(npmCommand, ["run", "nurtureany-sales-bot:verify"]);

const archivePath = join(tmpRoot, "nurtureany-origin-main.tar.gz");
const shaPath = join(tmpRoot, "nurtureany-origin-main.sha");

if (!args.apply) {
  log("Dry run only. No archive upload, remote sync, gateway restart, or production health checks were run.");
  log("Use `npm run nurtureany-sales-bot:deploy -- --apply` to deploy this exact origin/main SHA.");
  printSummary({
    deploySha,
    deployRef: "origin/main",
    timestamp: "",
    gateway: "not checked (dry run)",
    audit: "not run (dry run)",
    health: "not run (dry run)",
    heartbeat: "not run (dry run)",
    cloudDoctor: "not run (dry run)",
  });
  process.exit(0);
}

writeFileSync(shaPath, `${deploySha}\n`);
run(gitCommand, ["archive", "--format=tar.gz", "-o", archivePath, "origin/main"]);

if (!args.skipUpload) {
  run(gcloudCommand, [
    "compute",
    "scp",
    archivePath,
    `${args.vm}:/tmp/nurtureany-origin-main.tar.gz`,
    "--project",
    args.project,
    "--zone",
    args.zone,
    "--tunnel-through-iap",
  ]);
  run(gcloudCommand, [
    "compute",
    "scp",
    shaPath,
    `${args.vm}:/tmp/nurtureany-origin-main.sha`,
    "--project",
    args.project,
    "--zone",
    args.zone,
    "--tunnel-through-iap",
  ]);
} else {
  log("Skipping upload. Remote deploy will use existing /tmp/nurtureany-origin-main.tar.gz and .sha.");
}

const remoteOutput = runCapture(
  gcloudCommand,
  [
    "compute",
    "ssh",
    args.vm,
    "--project",
    args.project,
    "--zone",
    args.zone,
    "--tunnel-through-iap",
    "--command",
    "bash -s",
  ],
  { input: remoteDeployScript(args) },
);

process.stdout.write(remoteOutput);

const remoteSummary = parseRemoteSummary(remoteOutput);
printSummary({
  deploySha: remoteSummary.sha || deploySha,
  deployRef: remoteSummary.ref || "main",
  timestamp: remoteSummary.timestamp || "",
  gateway: remoteSummary.gateway || "unknown",
  audit: remoteSummary.audit || "unknown",
  health: remoteSummary.health || "unknown",
  heartbeat: remoteSummary.heartbeat || "unknown",
  cloudDoctor: remoteSummary.cloudDoctor || "unknown",
});

function parseArgs(argv) {
  const parsed = {
    ...DEFAULTS,
    apply: false,
    skipUpload: false,
    skipRestart: false,
    verbose: false,
    help: false,
  };
  const valueOptions = new Set(["project", "zone", "vm", "profile", "runtime-owner"]);
  for (let index = 0; index < argv.length; index += 1) {
    const raw = argv[index];
    if (raw === "--apply") {
      parsed.apply = true;
      continue;
    }
    if (raw === "--skip-upload") {
      parsed.skipUpload = true;
      continue;
    }
    if (raw === "--skip-restart") {
      parsed.skipRestart = true;
      continue;
    }
    if (raw === "--verbose") {
      parsed.verbose = true;
      continue;
    }
    if (raw === "--help" || raw === "-h") {
      parsed.help = true;
      continue;
    }
    if (!raw.startsWith("--")) {
      throw new Error(`Unexpected positional argument: ${raw}`);
    }
    const optionText = raw.slice(2);
    const [optionName, inlineValue] = optionText.split("=", 2);
    if (!valueOptions.has(optionName)) {
      throw new Error(`Unknown option: ${raw}`);
    }
    const optionValue = inlineValue ?? argv[++index];
    if (!optionValue || optionValue.startsWith("--")) {
      throw new Error(`Missing value for --${optionName}`);
    }
    if (optionName === "runtime-owner") {
      parsed.runtimeOwner = optionValue;
    } else {
      parsed[optionName] = optionValue;
    }
  }
  return parsed;
}

function printHelp() {
  console.log(`Usage: node scripts/deploy-nurtureany-sales-bot.mjs [options]

Deploys exact origin/main for NurtureAny Sales Bot to the production Hermes profile.

Options:
  --apply               Mutate production. Required for upload, sync, restart, and checks.
  --project <id>        GCP project. Default: ${DEFAULTS.project}
  --zone <zone>         GCP zone. Default: ${DEFAULTS.zone}
  --vm <name>           VM name. Default: ${DEFAULTS.vm}
  --profile <name>      Hermes profile. Default: ${DEFAULTS.profile}
  --runtime-owner <u>   Runtime OS user. Default: ${DEFAULTS.runtimeOwner}
  --skip-upload         Reuse archive already uploaded to /tmp on the VM.
  --skip-restart        Sync and stamp version, but do not restart or run post-restart checks.
  --verbose             Print commands before running them.
  --help                Show this help.
`);
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

function run(command, commandArgs, options = {}) {
  runProcess(command, commandArgs, { ...options, stdio: "inherit" });
}

function runCapture(command, commandArgs, options = {}) {
  const result = runProcess(command, commandArgs, { ...options, stdio: "pipe" });
  return result.stdout || "";
}

function runProcess(command, commandArgs, options = {}) {
  if (args.verbose) {
    log(`$ ${[command, ...commandArgs].join(" ")}`);
  }
  const result = spawnSync(command, commandArgs, {
    cwd: repoRoot,
    input: options.input,
    encoding: "utf8",
    stdio: options.stdio,
    maxBuffer: 10 * 1024 * 1024,
  });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    const stderr = result.stderr ? `\n${result.stderr.trim()}` : "";
    const stdout = result.stdout ? `\n${result.stdout.trim()}` : "";
    throw new Error(`Command failed (${result.status}): ${command} ${commandArgs.join(" ")}${stdout}${stderr}`);
  }
  return result;
}

function remoteDeployScript(options) {
  const profile = shellQuote(options.profile);
  const runtimeOwner = shellQuote(options.runtimeOwner);
  const skipRestart = options.skipRestart ? "1" : "0";
  return `set -euo pipefail
profile_name=${profile}
runtime_owner=${runtimeOwner}
skip_restart=${skipRestart}
profile="/home/$runtime_owner/.hermes/profiles/$profile_name"
service="hermes-gateway-$profile_name.service"
archive="/tmp/nurtureany-origin-main.tar.gz"
sha_file="/tmp/nurtureany-origin-main.sha"

test -f "$archive" || { echo "deploy:error:archive-missing"; exit 1; }
test -f "$sha_file" || { echo "deploy:error:sha-missing"; exit 1; }

active_owners=$(ps -ef | awk -v profile="$profile_name" '$0 ~ "hermes_cli.main" && $0 ~ "--profile " profile " gateway run" {print $1}' | sort -u | tr '\\n' ' ' | sed 's/[[:space:]]*$//')
if [ "$skip_restart" = "0" ] && [ "$active_owners" != "$runtime_owner" ]; then
  echo "deploy:error:active-runtime-owner-mismatch:$active_owners"
  exit 1
fi
sudo test -d "$profile" || { echo "deploy:error:profile-not-found:$profile"; exit 1; }

deploy_dir=$(mktemp -d /tmp/nurtureany-main.XXXXXX)
cleanup() {
  rm -rf "$deploy_dir"
}
trap cleanup EXIT

tar -xzf "$archive" -C "$deploy_dir"
cd "$deploy_dir"
npm run nurtureany-sales-bot:verify

deploy_sha=$(cat "$sha_file")
deploy_branch=main
deploy_timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)

copy_dir() {
  src="$1"
  dst="$2"
  sudo mkdir -p "$dst"
  sudo chown "$runtime_owner:$runtime_owner" "$dst"
  sudo find "$dst" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
  tar -C "$src" -cf - . | sudo -u "$runtime_owner" tar -C "$dst" -xf -
}

sudo mkdir -p "$profile/scripts" "$profile/source" "$profile/runtime" "$profile/skills"
sudo chown "$runtime_owner:$runtime_owner" "$profile/scripts" "$profile/source" "$profile/runtime" "$profile/skills"

copy_dir "$deploy_dir/apps/nurtureany-sales-bot" "$profile/source/nurtureany-sales-bot"
sudo install -o "$runtime_owner" -g "$runtime_owner" -m 0644 "$deploy_dir/apps/nurtureany-sales-bot/profile/SOUL.md" "$profile/SOUL.md"
copy_dir "$deploy_dir/apps/nurtureany-sales-bot/skills/nurtureany-sales-bot" "$profile/skills/nurtureany-sales-bot"
copy_dir "$deploy_dir/apps/nurtureany-sales-bot/skills/target-account-news-scout" "$profile/skills/target-account-news-scout"
copy_dir "$deploy_dir/apps/nurtureany-sales-bot/runtime/mcp" "$profile/runtime/mcp"
copy_dir "$deploy_dir/apps/nurtureany-sales-bot/runtime/data" "$profile/runtime/data"
copy_dir "$deploy_dir/apps/nurtureany-sales-bot/runtime/jobs" "$profile/runtime/jobs"
copy_dir "$deploy_dir/apps/nurtureany-sales-bot/runtime/sql" "$profile/runtime/sql"

sudo python3 - "$deploy_dir/apps/nurtureany-sales-bot/profile/config.template.yaml" "$profile/config.yaml" <<'PY'
import sys
from pathlib import Path
import yaml

template_path = Path(sys.argv[1])
config_path = Path(sys.argv[2])

template = yaml.safe_load(template_path.read_text())
config = yaml.safe_load(config_path.read_text())
template_servers = template.get("mcp_servers") or {}
config_servers = config.get("mcp_servers") or {}

changed = False
for server_name, template_server in template_servers.items():
    template_tools = template_server.get("tools") or {}
    expected = template_tools.get("include") or template_server.get("tool_allowlist") or []
    if not expected:
        continue
    config_server = config_servers.get(server_name)
    if not isinstance(config_server, dict):
        raise SystemExit(f"deploy:error:mcp-server-missing:{server_name}")
    config_tools = config_server.setdefault("tools", {})
    if config_tools.get("include") != expected:
        config_tools["include"] = list(expected)
        changed = True
    if config_server.pop("tool_allowlist", None) is not None:
        changed = True
    for key in ("resources", "prompts"):
        if key in template_tools and config_tools.get(key) != template_tools[key]:
            config_tools[key] = template_tools[key]
            changed = True

if changed:
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
PY
sudo chown "$runtime_owner:$runtime_owner" "$profile/config.yaml"

if [ -f "$deploy_dir/apps/nurtureany-sales-bot/runtime/apply-live-config-overrides.py" ]; then
  python3 "$deploy_dir/apps/nurtureany-sales-bot/runtime/apply-live-config-overrides.py" --profile-dir "$profile"
else
  echo "deploy:config-overrides-skipped:apply-live-config-overrides.py-not-present"
fi

sudo install -o "$runtime_owner" -g "$runtime_owner" -m 0755 "$deploy_dir/apps/nurtureany-sales-bot/runtime/check-health.sh" "$profile/scripts/nurtureanysalesbot-check-health.sh"
sudo install -o "$runtime_owner" -g "$runtime_owner" -m 0755 "$deploy_dir/apps/nurtureany-sales-bot/runtime/check-cloud-heartbeat.sh" "$profile/scripts/nurtureanysalesbot-check-cloud-heartbeat.sh"
sudo install -o "$runtime_owner" -g "$runtime_owner" -m 0755 "$deploy_dir/apps/nurtureany-sales-bot/runtime/audit-live-profile.sh" "$profile/scripts/nurtureanysalesbot-audit-live-profile.sh"
sudo install -o "$runtime_owner" -g "$runtime_owner" -m 0755 "$deploy_dir/apps/nurtureany-sales-bot/runtime/check-slack-socket-health.sh" "$profile/scripts/nurtureanysalesbot-check-slack-socket-health.sh"
sudo install -o "$runtime_owner" -g "$runtime_owner" -m 0755 "$deploy_dir/apps/nurtureany-sales-bot/runtime/nurtureany-cloud-doctor.sh" "$profile/scripts/nurtureanysalesbot-cloud-doctor.sh"

printf '%s | %s | %s\\n' "$deploy_sha" "$deploy_branch" "$deploy_timestamp" | sudo tee "$profile/VERSION" >/dev/null
sudo chown "$runtime_owner:$runtime_owner" "$profile/VERSION"
sudo chmod 0644 "$profile/VERSION"

if [ "$skip_restart" = "1" ]; then
  echo "deploy:restart=skipped"
  echo "deploy:summary:sha=$deploy_sha"
  echo "deploy:summary:ref=$deploy_branch"
  echo "deploy:summary:timestamp=$deploy_timestamp"
  echo "deploy:summary:gateway=not checked (skip-restart)"
  echo "deploy:summary:audit=not run (skip-restart)"
  echo "deploy:summary:health=not run (skip-restart)"
  echo "deploy:summary:heartbeat=not run (skip-restart)"
  echo "deploy:summary:cloud_doctor=not run (skip-restart)"
  exit 0
fi

uid=$(id -u "$runtime_owner")
sudo -H -u "$runtime_owner" XDG_RUNTIME_DIR="/run/user/$uid" systemctl --user restart "$service"
sudo -H -u "$runtime_owner" XDG_RUNTIME_DIR="/run/user/$uid" systemctl --user is-active "$service"
sleep 10

run_post_deploy_check() {
  label="$1"
  shift
  attempts="\${NURTUREANY_DEPLOY_CHECK_ATTEMPTS:-8}"
  delay_seconds="\${NURTUREANY_DEPLOY_CHECK_RETRY_SECONDS:-20}"
  command_timeout_seconds="\${NURTUREANY_DEPLOY_CHECK_COMMAND_TIMEOUT_SECONDS:-90}"
  attempt=1
  while [ "$attempt" -le "$attempts" ]; do
    if timeout "$command_timeout_seconds" "$@"; then
      if [ "$attempt" -gt 1 ]; then
        echo "deploy:check:$label=passed-after-retry:$attempt"
      fi
      return 0
    else
      status="$?"
    fi
    if [ "$attempt" -eq "$attempts" ]; then
      echo "deploy:check:$label=failed-after-$attempts-attempts"
      return "$status"
    fi
    echo "deploy:check:$label=retry:$attempt/$attempts"
    sleep "$delay_seconds"
    attempt=$((attempt + 1))
  done
}

run_post_deploy_check audit sudo -H -u "$runtime_owner" HERMES_PROFILE_DIR="$profile" HERMES_HOME="$profile" NURTUREANY_APP_ROOT="$profile/source/nurtureany-sales-bot" RUN_NESTED_HEALTH_CHECK=0 XDG_RUNTIME_DIR="/run/user/$uid" "$profile/scripts/nurtureanysalesbot-audit-live-profile.sh"
health_warmup_seconds="\${NURTUREANY_DEPLOY_HEALTH_WARMUP_SECONDS:-120}"
if [ "$health_warmup_seconds" -gt 0 ]; then
  echo "deploy:check:health=warmup:$health_warmup_seconds"
  sleep "$health_warmup_seconds"
fi
run_post_deploy_check health sudo -H -u "$runtime_owner" HERMES_PROFILE_DIR="$profile" HERMES_HOME="$profile" XDG_RUNTIME_DIR="/run/user/$uid" "$profile/scripts/nurtureanysalesbot-check-health.sh"
run_post_deploy_check cloud_doctor sudo -H -u "$runtime_owner" HERMES_PROFILE_DIR="$profile" HERMES_HOME="$profile" XDG_RUNTIME_DIR="/run/user/$uid" "$profile/scripts/nurtureanysalesbot-cloud-doctor.sh"
run_post_deploy_check heartbeat sudo -H -u "$runtime_owner" HERMES_PROFILE_DIR="$profile" HERMES_HOME="$profile" XDG_RUNTIME_DIR="/run/user/$uid" "$profile/scripts/nurtureanysalesbot-check-cloud-heartbeat.sh"
sudo -H -u "$runtime_owner" XDG_RUNTIME_DIR="/run/user/$uid" systemctl --user status "$service" --no-pager

echo "deploy:summary:sha=$deploy_sha"
echo "deploy:summary:ref=$deploy_branch"
echo "deploy:summary:timestamp=$deploy_timestamp"
echo "deploy:summary:gateway=active"
echo "deploy:summary:audit=passed"
echo "deploy:summary:health=passed"
echo "deploy:summary:heartbeat=passed"
echo "deploy:summary:cloud_doctor=passed"
`;
}

function shellQuote(value) {
  return `'${String(value).replace(/'/g, "'\"'\"'")}'`;
}

function parseRemoteSummary(output) {
  const summary = {};
  for (const line of output.split(/\r?\n/)) {
    if (!line.startsWith("deploy:summary:")) continue;
    const [, keyValue] = line.split("deploy:summary:");
    const [key, ...valueParts] = keyValue.split("=");
    const value = valueParts.join("=");
    if (key === "sha") summary.sha = value;
    if (key === "ref") summary.ref = value;
    if (key === "timestamp") summary.timestamp = value;
    if (key === "gateway") summary.gateway = value;
    if (key === "audit") summary.audit = value;
    if (key === "health") summary.health = value;
    if (key === "heartbeat") summary.heartbeat = value;
    if (key === "cloud_doctor") summary.cloudDoctor = value;
  }
  return summary;
}

function printSummary(summary) {
  console.log("\nDeploy summary");
  console.log(`- deployed_sha: ${summary.deploySha}`);
  console.log(`- deployed_ref: ${summary.deployRef}`);
  console.log(`- timestamp: ${summary.timestamp || "n/a"}`);
  console.log(`- gateway: ${summary.gateway}`);
  console.log(`- audit: ${summary.audit}`);
  console.log(`- health: ${summary.health}`);
  console.log(`- heartbeat: ${summary.heartbeat}`);
  console.log(`- cloud_doctor: ${summary.cloudDoctor}`);
}

function log(message) {
  console.log(`[nurtureany-deploy] ${message}`);
}
