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
  vm: "hermes-data-bot-poc",
  profile: "staffanydatabot",
  runtimeOwner: "leekaiyi",
  ref: "origin/main",
};

const PRESERVED_RUNTIME_STATE = [
  ".env",
  "auth/session credentials",
  "cron runtime state",
  "logs",
  "sessions",
  "Honcho data",
  "gateway state",
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

log(`Preparing Hermes Data Bot deploy from ${args.ref}`);
log(`Target: project=${args.project} zone=${args.zone} vm=${args.vm} profile=${args.profile} runtime_owner=${args.runtimeOwner}`);
if (args.verbose) log(`Preserved runtime state: ${PRESERVED_RUNTIME_STATE.join(", ")}`);

if (args.ref === "origin/main") {
  run(gitCommand, ["fetch", "origin", "main"]);
}
const deploySha = runCapture(gitCommand, ["rev-parse", args.ref]).trim();
if (!deploySha) throw new Error(`Could not resolve ${args.ref} deploy SHA.`);
log(`Deploy SHA: ${deploySha}`);

run(npmCommand, ["run", "hermes-data-bot:verify"]);
run(npmCommand, ["run", "hermes-data-bot:prompt-evals"]);

const archiveName = `hermes-data-bot-${deploySha}.tar.gz`;
const shaName = `hermes-data-bot-${deploySha}.sha`;
const archivePath = join(tmpRoot, archiveName);
const shaPath = join(tmpRoot, shaName);

if (!args.apply) {
  log("Dry run only. No archive upload, remote sync, gateway restart, or production checks were run.");
  log(`Use \`npm run hermes-data-bot:deploy -- --apply --ref ${args.ref}\` to deploy this exact ${args.ref} SHA.`);
  printSummary({
    deploySha,
    deployRef: args.ref,
    timestamp: "",
    gateway: "not checked (dry run)",
    remoteVerify: "not run (dry run)",
    audit: "not run (dry run)",
    health: "not run (dry run)",
    heartbeat: "not run (dry run)",
    cloudDoctor: "not run (dry run)",
  });
  process.exit(0);
}

writeFileSync(shaPath, `${deploySha}\n`);
run(gitCommand, ["archive", "--format=tar.gz", "-o", archivePath, args.ref]);

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
  { input: remoteDeployScript(args, deploySha, args.ref) },
);

process.stdout.write(remoteOutput);
const remoteSummary = parseRemoteSummary(remoteOutput);
printSummary({
  deploySha: remoteSummary.sha || deploySha,
  deployRef: remoteSummary.ref || args.ref,
  timestamp: remoteSummary.timestamp || "",
  gateway: remoteSummary.gateway || "unknown",
  remoteVerify: remoteSummary.remoteVerify || "unknown",
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
  const valueOptions = new Set(["project", "zone", "vm", "profile", "runtime-owner", "ref"]);
  for (let index = 0; index < argv.length; index += 1) {
    const raw = argv[index];
    if (raw === "--apply") parsed.apply = true;
    else if (raw === "--skip-upload") parsed.skipUpload = true;
    else if (raw === "--skip-restart") parsed.skipRestart = true;
    else if (raw === "--verbose") parsed.verbose = true;
    else if (raw === "--help" || raw === "-h") parsed.help = true;
    else if (raw.startsWith("--")) {
      const optionText = raw.slice(2);
      const [optionName, inlineValue] = optionText.split("=", 2);
      if (!valueOptions.has(optionName)) throw new Error(`Unknown option: ${raw}`);
      const optionValue = inlineValue ?? argv[++index];
      if (!optionValue || optionValue.startsWith("--")) throw new Error(`Missing value for --${optionName}`);
      if (optionName === "runtime-owner") parsed.runtimeOwner = optionValue;
      else parsed[optionName] = optionValue;
    } else {
      throw new Error(`Unexpected positional argument: ${raw}`);
    }
  }
  return parsed;
}

function printHelp() {
  console.log(`Usage: node scripts/deploy-hermes-data-bot.mjs [options]

Deploys an exact git ref for StaffAny Hermes Data Bot to the cloud Hermes profile.

Options:
  --apply               Mutate production. Required for upload, sync, restart, and checks.
  --project <id>        GCP project. Default: ${DEFAULTS.project}
  --zone <zone>         GCP zone. Default: ${DEFAULTS.zone}
  --vm <name>           VM name. Default: ${DEFAULTS.vm}
  --profile <name>      Hermes profile. Default: ${DEFAULTS.profile}
  --runtime-owner <u>   Runtime OS user. Default: ${DEFAULTS.runtimeOwner}
  --ref <git-ref>       Git ref to archive and deploy. Default: ${DEFAULTS.ref}
  --skip-upload         Reuse archive already uploaded to /tmp on the VM.
  --skip-restart        Sync and stamp version, but do not restart or run post-restart checks.
  --verbose             Print commands before running them.
  --help                Show this help.
`);
}

function resolveCommand(label, candidates) {
  for (const candidate of candidates) {
    const result = spawnSync(candidate, ["--version"], { encoding: "utf8" });
    if (!result.error && result.status === 0) return candidate;
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
  if (args.verbose) log(`$ ${[command, ...commandArgs].join(" ")}`);
  const result = spawnSync(command, commandArgs, {
    cwd: repoRoot,
    input: options.input,
    encoding: "utf8",
    stdio: options.stdio,
    maxBuffer: 10 * 1024 * 1024,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    const stderr = result.stderr ? `\n${result.stderr.trim()}` : "";
    const stdout = result.stdout ? `\n${result.stdout.trim()}` : "";
    throw new Error(`Command failed (${result.status}): ${command} ${commandArgs.join(" ")}${stdout}${stderr}`);
  }
  return result;
}

function remoteDeployScript(options, deploySha, deployRef) {
  const profile = shellQuote(options.profile);
  const runtimeOwner = shellQuote(options.runtimeOwner);
  const deployShaExpected = shellQuote(deploySha);
  const deployRefLabel = shellQuote(deployRef);
  const skipRestart = options.skipRestart ? "1" : "0";
  return `set -euo pipefail
profile_name=${profile}
runtime_owner=${runtimeOwner}
deploy_sha_expected=${deployShaExpected}
deploy_ref_label=${deployRefLabel}
skip_restart=${skipRestart}
profile="/home/$runtime_owner/.hermes/profiles/$profile_name"
service="hermes-gateway-$profile_name.service"
archive="/tmp/hermes-data-bot-$deploy_sha_expected.tar.gz"
sha_file="/tmp/hermes-data-bot-$deploy_sha_expected.sha"

test -f "$archive" || { echo "deploy:error:archive-missing"; exit 1; }
test -f "$sha_file" || { echo "deploy:error:sha-missing"; exit 1; }
test "$(cat "$sha_file")" = "$deploy_sha_expected" || { echo "deploy:error:sha-mismatch"; exit 1; }
sudo test -d "$profile" || { echo "deploy:error:profile-not-found:$profile"; exit 1; }

active_owners=$(ps -ef | awk -v profile="$profile_name" '$0 ~ "hermes_cli.main" && $0 ~ "--profile " profile " gateway run" {print $1}' | sort -u | tr '\\n' ' ' | sed 's/[[:space:]]*$//')
if [ "$skip_restart" = "0" ] && [ -n "$active_owners" ] && [ "$active_owners" != "$runtime_owner" ]; then
  echo "deploy:error:active-runtime-owner-mismatch:$active_owners"
  exit 1
fi

deploy_dir=$(mktemp -d /tmp/hermes-data-bot-main.XXXXXX)
cleanup() { rm -rf "$deploy_dir"; }
trap cleanup EXIT

tar -xzf "$archive" -C "$deploy_dir"
cd "$deploy_dir"
command -v node >/dev/null 2>&1 || { echo "deploy:error:node-not-found"; exit 1; }
node scripts/verify-hermes-data-bot.mjs
node scripts/run-prompt-evals.mjs --app hermes-data-bot --mode all
remote_verify="passed"

deploy_sha=$(cat "$sha_file")
deploy_branch=$deploy_ref_label
deploy_timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)

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

sudo mkdir -p "$profile/scripts" "$profile/source" "$profile/runtime" "$profile/skills"
sudo chown "$runtime_owner:$runtime_owner" "$profile/scripts" "$profile/source" "$profile/runtime" "$profile/skills"

copy_dir "$deploy_dir/apps/hermes-data-bot" "$profile/source/hermes-data-bot"
copy_file "$deploy_dir/apps/hermes-data-bot/profile/SOUL.md" "$profile/SOUL.md" 0644
copy_dir "$deploy_dir/apps/hermes-data-bot/skills/staffany-data-bot" "$profile/skills/staffany-data-bot"
copy_dir "$deploy_dir/apps/hermes-data-bot/runtime/mcp" "$profile/runtime/mcp"

python3 - "$deploy_dir/apps/hermes-data-bot/profile/config.template.yaml" "$profile/config.yaml" "$runtime_owner" <<'PY'
import sys
from pathlib import Path
import yaml

template_path, config_path, runtime_owner = sys.argv[1:4]
template = yaml.safe_load(Path(template_path).read_text()) or {}
config = yaml.safe_load(Path(config_path).read_text()) or {}

changed = False
for key in ("security", "display", "model", "agent", "kanban", "slack"):
    if key in template and config.get(key) != template[key]:
        config[key] = template[key]
        changed = True

if "cron" in template:
    target = config.setdefault("cron", {})
    for cron_key, value in template["cron"].items():
        if target.get(cron_key) != value:
            target[cron_key] = value
            changed = True

template_servers = template.get("mcp_servers") or {}
config_servers = config.setdefault("mcp_servers", {})
for server_name in ("staffany_bigquery", "staffany_slack_context", "staffany_c360"):
    expected = template_servers.get(server_name)
    if expected is None:
        continue
    rendered = yaml.safe_load(yaml.safe_dump(expected))
    rendered_text = yaml.safe_dump(rendered, sort_keys=False)
    rendered_text = rendered_text.replace("/home/leekaiyi", f"/home/{runtime_owner}")
    rendered = yaml.safe_load(rendered_text)
    if config_servers.get(server_name) != rendered:
        config_servers[server_name] = rendered
        changed = True

gateway = template.get("gateway")
if gateway and config.get("gateway") != gateway:
    config["gateway"] = gateway
    changed = True

if changed:
    Path(config_path).write_text(yaml.safe_dump(config, sort_keys=False))
PY
sudo chown "$runtime_owner:$runtime_owner" "$profile/config.yaml"
sudo chmod 0644 "$profile/config.yaml"

copy_file "$deploy_dir/apps/hermes-data-bot/runtime/check-health.sh" "$profile/scripts/staffanydatabot-check-health.sh" 0755
copy_file "$deploy_dir/apps/hermes-data-bot/runtime/check-cloud-heartbeat.sh" "$profile/scripts/staffanydatabot-check-cloud-heartbeat.sh" 0755
copy_file "$deploy_dir/apps/hermes-data-bot/runtime/audit-live-profile.sh" "$profile/scripts/staffanydatabot-audit-live-profile.sh" 0755
copy_file "$deploy_dir/apps/hermes-data-bot/runtime/staffanydatabot-cloud-doctor.sh" "$profile/scripts/staffanydatabot-cloud-doctor.sh" 0755
copy_file "$deploy_dir/apps/hermes-data-bot/runtime/backup-honcho.sh" "$profile/scripts/staffanydatabot-honcho-backup.sh" 0755
copy_file "$deploy_dir/apps/hermes-data-bot/runtime/review-honcho-memory.sh" "$profile/scripts/staffanydatabot-review-honcho-memory.sh" 0755

printf '%s | %s | %s\\n' "$deploy_sha" "$deploy_branch" "$deploy_timestamp" | sudo tee "$profile/VERSION" >/dev/null
sudo chown "$runtime_owner:$runtime_owner" "$profile/VERSION"
sudo chmod 0644 "$profile/VERSION"

if [ "$skip_restart" = "1" ]; then
  echo "deploy:restart=skipped"
  echo "deploy:summary:sha=$deploy_sha"
  echo "deploy:summary:ref=$deploy_branch"
  echo "deploy:summary:timestamp=$deploy_timestamp"
  echo "deploy:summary:gateway=not checked (skip-restart)"
  echo "deploy:summary:remote_verify=$remote_verify"
  echo "deploy:summary:audit=not run (skip-restart)"
  echo "deploy:summary:health=not run (skip-restart)"
  echo "deploy:summary:heartbeat=not run (skip-restart)"
  echo "deploy:summary:cloud_doctor=not run (skip-restart)"
  exit 0
fi

cd /tmp
uid=$(id -u "$runtime_owner")
sudo -H -u "$runtime_owner" XDG_RUNTIME_DIR="/run/user/$uid" systemctl --user reset-failed "$service" || true
sudo -H -u "$runtime_owner" XDG_RUNTIME_DIR="/run/user/$uid" systemctl --user restart "$service"
sudo -H -u "$runtime_owner" XDG_RUNTIME_DIR="/run/user/$uid" systemctl --user is-active "$service"
sleep "\${HERMES_DATA_BOT_DEPLOY_GATEWAY_SETTLE_SECONDS:-20}"

run_post_deploy_check() {
  label="$1"
  shift
  attempts="\${HERMES_DATA_BOT_DEPLOY_CHECK_ATTEMPTS:-4}"
  delay_seconds="\${HERMES_DATA_BOT_DEPLOY_CHECK_RETRY_SECONDS:-15}"
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

run_post_deploy_check audit sudo -H -u "$runtime_owner" HERMES_DATA_BOT_APP_ROOT="$profile/source/hermes-data-bot" HERMES_PROFILE_DIR="$profile" HERMES_HOME="$profile" XDG_RUNTIME_DIR="/run/user/$uid" "$profile/scripts/staffanydatabot-audit-live-profile.sh"
run_post_deploy_check health sudo -H -u "$runtime_owner" HERMES_PROFILE_DIR="$profile" HERMES_HOME="$profile" XDG_RUNTIME_DIR="/run/user/$uid" "$profile/scripts/staffanydatabot-check-health.sh"
run_post_deploy_check heartbeat sudo -H -u "$runtime_owner" HERMES_PROFILE_DIR="$profile" HERMES_HOME="$profile" XDG_RUNTIME_DIR="/run/user/$uid" "$profile/scripts/staffanydatabot-check-cloud-heartbeat.sh"
run_post_deploy_check cloud_doctor sudo -H -u "$runtime_owner" HERMES_PROFILE_DIR="$profile" HERMES_HOME="$profile" XDG_RUNTIME_DIR="/run/user/$uid" "$profile/scripts/staffanydatabot-cloud-doctor.sh"
sudo -H -u "$runtime_owner" XDG_RUNTIME_DIR="/run/user/$uid" systemctl --user status "$service" --no-pager

echo "deploy:summary:sha=$deploy_sha"
echo "deploy:summary:ref=$deploy_branch"
echo "deploy:summary:timestamp=$deploy_timestamp"
echo "deploy:summary:gateway=active"
echo "deploy:summary:remote_verify=$remote_verify"
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
    if (key === "remote_verify") summary.remoteVerify = value;
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
  console.log(`- remote_verify: ${summary.remoteVerify}`);
  console.log(`- audit: ${summary.audit}`);
  console.log(`- health: ${summary.health}`);
  console.log(`- heartbeat: ${summary.heartbeat}`);
  console.log(`- cloud_doctor: ${summary.cloudDoctor}`);
}

function log(message) {
  console.log(`[hermes-data-bot-deploy] ${message}`);
}
