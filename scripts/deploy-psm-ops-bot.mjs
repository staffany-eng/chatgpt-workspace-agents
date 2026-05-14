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
  vm: "hermes-psm-ops-bot-poc",
  profile: "psmopsbot",
  runtimeOwner: "leekaiyi",
  remoteSourceDir: "",
};

const FORBIDDEN_RUNTIME_STATE_LABELS = [
  ".env",
  "auth.json",
  "cron",
  "logs",
  "sessions",
  "state.db",
  "gateway_state.json",
  "runtime secrets",
];

const args = parseArgs(process.argv.slice(2));

if (args.help) {
  printHelp();
  process.exit(0);
}

const gitCommand = resolveCommand("git", ["git"]);
const gcloudCommand = resolveCommand("gcloud", [
  "gcloud",
  "/opt/homebrew/share/google-cloud-sdk/bin/gcloud",
  "/usr/local/share/google-cloud-sdk/bin/gcloud",
]);

log("Preparing PSM Ops Bot deploy from origin/main");
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

run(process.execPath, ["scripts/verify-psm-ops-bot.mjs"]);

const archiveName = `psm-ops-origin-main-${deploySha}.tar.gz`;
const shaName = `psm-ops-origin-main-${deploySha}.sha`;
const archivePath = join(tmpRoot, archiveName);
const shaPath = join(tmpRoot, shaName);

if (!args.apply) {
  log("Dry run only. No archive upload, remote sync, gateway restart, or production health checks were run.");
  log("Use `npm run psm-ops-bot:deploy -- --apply` to deploy this exact origin/main SHA.");
  printSummary({
    deploySha,
    deployRef: "origin/main",
    timestamp: "",
    gateway: "not checked (dry run)",
    audit: "not run (dry run)",
    health: "not run (dry run)",
    heartbeat: "not run (dry run)",
    rockProductionsC360: "not run (dry run)",
    remoteVerify: "not run (dry run)",
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
    `${args.vm}:/tmp/${archiveName}`,
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
    `${args.vm}:/tmp/${shaName}`,
    "--project",
    args.project,
    "--zone",
    args.zone,
    "--tunnel-through-iap",
  ]);
} else {
  log(`Skipping upload. Remote deploy will use existing /tmp/${archiveName} and /tmp/${shaName}.`);
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
  { input: remoteDeployScript(args, deploySha) },
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
  rockProductionsC360: remoteSummary.rockProductionsC360 || "unknown",
  remoteVerify: remoteSummary.remoteVerify || "unknown",
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
  const valueOptions = new Set(["project", "zone", "vm", "profile", "runtime-owner", "remote-source-dir"]);
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
    } else if (optionName === "remote-source-dir") {
      parsed.remoteSourceDir = optionValue;
    } else {
      parsed[optionName] = optionValue;
    }
  }
  return parsed;
}

function printHelp() {
  console.log(`Usage: node scripts/deploy-psm-ops-bot.mjs [options]

Deploys exact origin/main for PSM Ops Bot to the production Hermes profile.

Options:
  --apply                  Mutate production. Required for upload, sync, restart, and checks.
  --project <id>           GCP project. Default: ${DEFAULTS.project}
  --zone <zone>            GCP zone. Default: ${DEFAULTS.zone}
  --vm <name>              VM name. Default: ${DEFAULTS.vm}
  --profile <name>         Hermes profile. Default: ${DEFAULTS.profile}
  --runtime-owner <u>      Runtime OS user. Default: ${DEFAULTS.runtimeOwner}
  --remote-source-dir <p>  Remote source snapshot. Default: /home/<runtime-owner>/agent-builder
  --skip-upload            Reuse archive already uploaded to /tmp on the VM.
  --skip-restart           Sync and stamp version, but do not restart or run post-restart checks.
  --verbose                Print commands before running them.
  --help                   Show this help.
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

function remoteDeployScript(options, deploySha) {
  const profile = shellQuote(options.profile);
  const runtimeOwner = shellQuote(options.runtimeOwner);
  const remoteSourceDir = shellQuote(options.remoteSourceDir || `/home/${options.runtimeOwner}/agent-builder`);
  const deployShaExpected = shellQuote(deploySha);
  const skipRestart = options.skipRestart ? "1" : "0";
  return `set -euo pipefail
profile_name=${profile}
runtime_owner=${runtimeOwner}
remote_source_dir=${remoteSourceDir}
deploy_sha_expected=${deployShaExpected}
skip_restart=${skipRestart}
profile="/home/$runtime_owner/.hermes/profiles/$profile_name"
service="hermes-gateway-$profile_name.service"
archive="/tmp/psm-ops-origin-main-$deploy_sha_expected.tar.gz"
sha_file="/tmp/psm-ops-origin-main-$deploy_sha_expected.sha"
source_app="$remote_source_dir/apps/psm-ops-bot"

test -f "$archive" || { echo "deploy:error:archive-missing"; exit 1; }
test -f "$sha_file" || { echo "deploy:error:sha-missing"; exit 1; }
sudo test -d "$profile" || { echo "deploy:error:profile-not-found:$profile"; exit 1; }

active_owners=$(ps -ef | awk -v profile="$profile_name" '$0 ~ "hermes_cli.main" && $0 ~ "--profile " profile " gateway run" {print $1}' | sort -u | tr '\\n' ' ' | sed 's/[[:space:]]*$//')
if [ "$skip_restart" = "0" ] && [ -n "$active_owners" ] && [ "$active_owners" != "$runtime_owner" ]; then
  echo "deploy:error:active-runtime-owner-mismatch:$active_owners"
  exit 1
fi

deploy_dir=$(mktemp -d /tmp/psm-ops-main.XXXXXX)
cleanup() {
  rm -rf "$deploy_dir"
}
trap cleanup EXIT

tar -xzf "$archive" -C "$deploy_dir"

test -f "$deploy_dir/package.json" || { echo "deploy:error:package-json-missing"; exit 1; }
test -f "$deploy_dir/scripts/verify-psm-ops-bot.mjs" || { echo "deploy:error:verify-script-missing"; exit 1; }
test -d "$deploy_dir/apps/psm-ops-bot" || { echo "deploy:error:app-packet-missing"; exit 1; }

deploy_sha=$(cat "$sha_file")
[ "$deploy_sha" = "$deploy_sha_expected" ] || { echo "deploy:error:sha-mismatch:$deploy_sha:$deploy_sha_expected"; exit 1; }
deploy_branch=main
deploy_timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
remote_verify="skipped:node-not-found"

copy_dir() {
  src="$1"
  dst="$2"
  sudo mkdir -p "$dst"
  sudo chown "$runtime_owner:$runtime_owner" "$dst"
  sudo find "$dst" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
  tar -C "$src" -cf - . | sudo -u "$runtime_owner" tar -C "$dst" -xf -
}

copy_file() {
  src="$1"
  dst="$2"
  mode="$3"
  sudo mkdir -p "$(dirname "$dst")"
  sudo install -o "$runtime_owner" -g "$runtime_owner" -m "$mode" "$src" "$dst"
}

sudo mkdir -p "$remote_source_dir" "$remote_source_dir/apps" "$remote_source_dir/scripts" "$remote_source_dir/ops" "$profile/scripts" "$profile/source" "$profile/runtime" "$profile/skills" "$profile/hooks"
sudo chown "$runtime_owner:$runtime_owner" "$remote_source_dir" "$remote_source_dir/apps" "$remote_source_dir/scripts" "$remote_source_dir/ops" "$profile/scripts" "$profile/source" "$profile/runtime" "$profile/skills" "$profile/hooks"

copy_file "$deploy_dir/package.json" "$remote_source_dir/package.json" 0644
copy_file "$deploy_dir/README.md" "$remote_source_dir/README.md" 0644
copy_dir "$deploy_dir/scripts" "$remote_source_dir/scripts"
copy_dir "$deploy_dir/ops/hermes" "$remote_source_dir/ops/hermes"
copy_dir "$deploy_dir/apps/psm-ops-bot" "$source_app"

copy_dir "$deploy_dir/apps/psm-ops-bot" "$profile/source/psm-ops-bot"
copy_file "$deploy_dir/apps/psm-ops-bot/profile/SOUL.md" "$profile/SOUL.md" 0644
copy_dir "$deploy_dir/apps/psm-ops-bot/skills/psm-ops-bot" "$profile/skills/psm-ops-bot"
copy_dir "$deploy_dir/apps/psm-ops-bot/runtime/mcp" "$profile/runtime/mcp"
copy_dir "$deploy_dir/apps/psm-ops-bot/runtime/hooks/psm-ops-adoption-telemetry" "$profile/hooks/psm-ops-adoption-telemetry"

copy_file "$deploy_dir/apps/psm-ops-bot/runtime/check-health.sh" "$profile/scripts/psmopsbot-check-health.sh" 0755
copy_file "$deploy_dir/apps/psm-ops-bot/runtime/check-cloud-heartbeat.sh" "$profile/scripts/psmopsbot-check-cloud-heartbeat.sh" 0755
copy_file "$deploy_dir/apps/psm-ops-bot/runtime/audit-live-profile.sh" "$profile/scripts/psmopsbot-audit-live-profile.sh" 0755
copy_file "$deploy_dir/apps/psm-ops-bot/runtime/smoke-rock-productions-c360.sh" "$profile/scripts/psmopsbot-rock-productions-c360-smoke.sh" 0755
copy_file "$deploy_dir/apps/psm-ops-bot/runtime/psm_ops_adoption_digest.py" "$profile/scripts/psm_ops_adoption_digest.py" 0755

if command -v node >/dev/null 2>&1; then
  (cd "$remote_source_dir" && node scripts/verify-psm-ops-bot.mjs)
  remote_verify="passed"
else
  echo "deploy:remote-verify=skipped:node-not-found"
fi

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
  echo "deploy:summary:rock_productions_c360=not run (skip-restart)"
  echo "deploy:summary:remote_verify=$remote_verify"
  exit 0
fi

uid=$(id -u "$runtime_owner")
sudo -H -u "$runtime_owner" XDG_RUNTIME_DIR="/run/user/$uid" systemctl --user reset-failed "$service" || true
sudo -H -u "$runtime_owner" XDG_RUNTIME_DIR="/run/user/$uid" systemctl --user restart "$service"
sudo -H -u "$runtime_owner" XDG_RUNTIME_DIR="/run/user/$uid" systemctl --user is-active "$service"
sleep "\${PSM_OPS_DEPLOY_GATEWAY_SETTLE_SECONDS:-20}"

run_post_deploy_check() {
  label="$1"
  shift
  attempts="\${PSM_OPS_DEPLOY_CHECK_ATTEMPTS:-3}"
  delay_seconds="\${PSM_OPS_DEPLOY_CHECK_RETRY_SECONDS:-10}"
  attempt=1
  while [ "$attempt" -le "$attempts" ]; do
    if "$@"; then
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

run_post_deploy_check audit sudo -H -u "$runtime_owner" PSM_OPS_SOURCE_DIR="$source_app" HERMES_PROFILE_DIR="$profile" XDG_RUNTIME_DIR="/run/user/$uid" "$source_app/runtime/audit-live-profile.sh"
run_post_deploy_check health sudo -H -u "$runtime_owner" HERMES_PROFILE_DIR="$profile" XDG_RUNTIME_DIR="/run/user/$uid" "$source_app/runtime/check-health.sh"
run_post_deploy_check heartbeat sudo -H -u "$runtime_owner" HERMES_PROFILE_DIR="$profile" XDG_RUNTIME_DIR="/run/user/$uid" "$source_app/runtime/check-cloud-heartbeat.sh"
run_post_deploy_check rock_productions_c360 sudo -H -u "$runtime_owner" PSM_OPS_SOURCE_DIR="$source_app" HERMES_PROFILE_DIR="$profile" XDG_RUNTIME_DIR="/run/user/$uid" "$source_app/runtime/smoke-rock-productions-c360.sh"
sudo -H -u "$runtime_owner" XDG_RUNTIME_DIR="/run/user/$uid" systemctl --user status "$service" --no-pager

echo "deploy:summary:sha=$deploy_sha"
echo "deploy:summary:ref=$deploy_branch"
echo "deploy:summary:timestamp=$deploy_timestamp"
echo "deploy:summary:gateway=active"
echo "deploy:summary:audit=passed"
echo "deploy:summary:health=passed"
echo "deploy:summary:heartbeat=passed"
echo "deploy:summary:rock_productions_c360=passed"
echo "deploy:summary:remote_verify=$remote_verify"
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
    if (key === "rock_productions_c360") summary.rockProductionsC360 = value;
    if (key === "remote_verify") summary.remoteVerify = value;
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
  console.log(`- rock_productions_c360: ${summary.rockProductionsC360}`);
  console.log(`- remote_verify: ${summary.remoteVerify}`);
}

function log(message) {
  console.log(`[psm-ops-deploy] ${message}`);
}
