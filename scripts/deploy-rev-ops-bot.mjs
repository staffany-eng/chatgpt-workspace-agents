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
  profile: "revopsbot",
  runtimeOwner: "leekaiyi",
  sshUser: "",
  sshKeyFile: "",
  transport: "gcloud",
  sourceRoot: "/home/leekaiyi/chatgpt-workspace-agents",
  ref: "origin/main",
};

const PRESERVED_RUNTIME_STATE = [
  ".env",
  "auth/session credentials",
  "cron runtime state",
  "logs",
  "sessions",
  "gateway state",
  "memory files",
  "/home/leekaiyi/agent-builder customer-360 checkout",
];

const args = parseArgs(process.argv.slice(2));

if (args.help) {
  printHelp();
  process.exit(0);
}

const gitCommand = resolveCommand("git", ["git"]);
const npmCommand = resolveCommand("npm", ["npm", "/opt/homebrew/bin/npm", "/usr/local/bin/npm"]);
const sshCommand = resolvePathCommand("ssh", ["ssh", "/usr/bin/ssh"]);
const scpCommand = resolvePathCommand("scp", ["scp", "/usr/bin/scp"]);
const gcloudCommand = resolveCommand("gcloud", [
  "gcloud",
  "/opt/homebrew/share/google-cloud-sdk/bin/gcloud",
  "/usr/local/share/google-cloud-sdk/bin/gcloud",
]);

log(`Preparing RevOps Bot deploy from ${args.ref}`);
const sshUser = args.sshUser || args.runtimeOwner;
log(`Target: project=${args.project} zone=${args.zone} vm=${args.vm} ssh_user=${sshUser} profile=${args.profile} runtime_owner=${args.runtimeOwner}`);
log(`Source root: ${args.sourceRoot}`);
if (args.verbose) log(`Preserved runtime state: ${PRESERVED_RUNTIME_STATE.join(", ")}`);

if (args.ref === "origin/main") {
  run(gitCommand, ["fetch", "origin", "main"]);
}
const deploySha = runCapture(gitCommand, ["rev-parse", args.ref]).trim();
if (!deploySha) throw new Error(`Could not resolve ${args.ref} deploy SHA.`);
log(`Deploy SHA: ${deploySha}`);

run(npmCommand, ["run", "rev-ops-bot:verify"]);
run(npmCommand, ["run", "rev-ops-bot:prompt-evals"]);

const archiveName = `rev-ops-bot-${deploySha}.tar.gz`;
const shaName = `rev-ops-bot-${deploySha}.sha`;
const archivePath = join(tmpRoot, archiveName);
const shaPath = join(tmpRoot, shaName);

if (!args.apply) {
  log("Dry run only. No archive upload, remote sync, gateway restart, or production checks were run.");
  log(`Use \`npm run rev-ops-bot:deploy -- --apply --ref ${args.ref}\` to deploy this exact ${args.ref} SHA.`);
  printSummary({
    deploySha,
    deployRef: args.ref,
    timestamp: "",
    gateway: "not checked (dry run)",
    remoteVerify: "not run (dry run)",
    audit: "not run (dry run)",
    health: "not run (dry run)",
  });
  process.exit(0);
}

writeFileSync(shaPath, `${deploySha}\n`);
run(gitCommand, ["archive", "--format=tar.gz", "-o", archivePath, args.ref]);

if (!args.skipUpload) {
  uploadFile(archivePath, `/tmp/${archiveName}`);
  uploadFile(shaPath, `/tmp/${shaName}`);
} else {
  log(`Skipping upload. Remote deploy will use existing /tmp/${archiveName} and /tmp/${shaName}.`);
}

const remoteOutput = runRemote(remoteDeployScript(args, deploySha, args.ref));

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
  const valueOptions = new Set(["project", "zone", "vm", "profile", "runtime-owner", "ssh-user", "ssh-key-file", "transport", "source-root", "ref"]);
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
      else if (optionName === "ssh-user") parsed.sshUser = optionValue;
      else if (optionName === "ssh-key-file") parsed.sshKeyFile = optionValue;
      else if (optionName === "transport") parsed.transport = optionValue;
      else if (optionName === "source-root") parsed.sourceRoot = optionValue;
      else parsed[optionName] = optionValue;
    } else {
      throw new Error(`Unexpected positional argument: ${raw}`);
    }
  }
  if (parsed.sourceRoot.includes("/agent-builder")) {
    throw new Error("--source-root must not point at /home/leekaiyi/agent-builder; that path is reserved for Customer 360 on the shared VM.");
  }
  if (!["gcloud", "iap-ssh"].includes(parsed.transport)) {
    throw new Error("--transport must be either gcloud or iap-ssh");
  }
  return parsed;
}

function printHelp() {
  console.log(`Usage: node scripts/deploy-rev-ops-bot.mjs [options]

Deploys an exact git ref for RevOps Bot to the shared Hermes VM without touching Customer 360.

Options:
  --apply               Mutate production. Required for upload, sync, restart, and checks.
  --project <id>        GCP project. Default: ${DEFAULTS.project}
  --zone <zone>         GCP zone. Default: ${DEFAULTS.zone}
  --vm <name>           VM name. Default: ${DEFAULTS.vm}
  --profile <name>      Hermes profile. Default: ${DEFAULTS.profile}
  --runtime-owner <u>   Runtime OS user. Default: ${DEFAULTS.runtimeOwner}
  --ssh-user <u>        SSH login user. Default: runtime-owner
  --ssh-key-file <path> Optional SSH key file passed to gcloud compute ssh/scp.
  --transport <mode>    gcloud or iap-ssh. Default: ${DEFAULTS.transport}
  --source-root <path>  Remote source root. Default: ${DEFAULTS.sourceRoot}
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

function resolvePathCommand(label, candidates) {
  for (const candidate of candidates) {
    if (candidate.includes("/")) {
      if (existsSync(candidate)) return candidate;
      continue;
    }
    const result = spawnSync("/usr/bin/which", [candidate], { encoding: "utf8" });
    if (!result.error && result.status === 0 && result.stdout.trim()) return result.stdout.trim();
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

function sshKeyArgs(options) {
  return options.sshKeyFile ? ["--ssh-key-file", options.sshKeyFile] : [];
}

function uploadFile(localPath, remotePath) {
  const sshUser = args.sshUser || args.runtimeOwner;
  if (args.transport === "iap-ssh") {
    run(scpCommand, [
      ...iapSshArgs(args),
      localPath,
      `${sshUser}@${args.vm}:${remotePath}`,
    ]);
    return;
  }
  run(gcloudCommand, [
    "compute",
    "scp",
    localPath,
    `${sshUser}@${args.vm}:${remotePath}`,
    "--project",
    args.project,
    "--zone",
    args.zone,
    "--tunnel-through-iap",
    ...sshKeyArgs(args),
  ]);
}

function runRemote(input) {
  const sshUser = args.sshUser || args.runtimeOwner;
  if (args.transport === "iap-ssh") {
    return runCapture(
      sshCommand,
      [
        ...iapSshArgs(args),
        `${sshUser}@${args.vm}`,
        "bash -s",
      ],
      { input },
    );
  }
  return runCapture(
    gcloudCommand,
    [
      "compute",
      "ssh",
      `${sshUser}@${args.vm}`,
      "--project",
      args.project,
      "--zone",
      args.zone,
      "--tunnel-through-iap",
      ...sshKeyArgs(args),
      "--command",
      "bash -s",
    ],
    { input },
  );
}

function iapSshArgs(options) {
  const proxyCommand = `${gcloudCommand} compute start-iap-tunnel ${options.vm} %p --project=${options.project} --zone=${options.zone} --listen-on-stdin --verbosity=warning`;
  return [
    "-o",
    "BatchMode=yes",
    "-o",
    "StrictHostKeyChecking=no",
    "-o",
    "UserKnownHostsFile=/dev/null",
    "-o",
    `ProxyCommand=${proxyCommand}`,
    ...(options.sshKeyFile ? ["-i", options.sshKeyFile] : []),
  ];
}

function remoteDeployScript(options, deploySha, deployRef) {
  const profile = shellQuote(options.profile);
  const runtimeOwner = shellQuote(options.runtimeOwner);
  const sourceRoot = shellQuote(options.sourceRoot);
  const deployShaExpected = shellQuote(deploySha);
  const deployRefLabel = shellQuote(deployRef);
  const skipRestart = options.skipRestart ? "1" : "0";
  return `set -euo pipefail
profile_name=${profile}
runtime_owner=${runtimeOwner}
source_root=${sourceRoot}
deploy_sha_expected=${deployShaExpected}
deploy_ref_label=${deployRefLabel}
skip_restart=${skipRestart}
profile="/home/$runtime_owner/.hermes/profiles/$profile_name"
service="hermes-gateway-$profile_name.service"
archive="/tmp/rev-ops-bot-$deploy_sha_expected.tar.gz"
sha_file="/tmp/rev-ops-bot-$deploy_sha_expected.sha"

case "$source_root" in
  *"/agent-builder"* )
    echo "deploy:error:source-root-must-not-be-agent-builder:$source_root"
    exit 1
    ;;
esac

test -f "$archive" || { echo "deploy:error:archive-missing"; exit 1; }
test -f "$sha_file" || { echo "deploy:error:sha-missing"; exit 1; }
test "$(cat "$sha_file")" = "$deploy_sha_expected" || { echo "deploy:error:sha-mismatch"; exit 1; }
sudo test -d "$profile" || { echo "deploy:error:profile-not-found:$profile"; exit 1; }

active_owners=$(ps -ef | awk -v profile="$profile_name" '$0 ~ "hermes_cli.main" && $0 ~ "--profile " profile " gateway run" {print $1}' | sort -u | tr '\\n' ' ' | sed 's/[[:space:]]*$//')
if [ "$skip_restart" = "0" ] && [ -n "$active_owners" ] && [ "$active_owners" != "$runtime_owner" ]; then
  echo "deploy:error:active-runtime-owner-mismatch:$active_owners"
  exit 1
fi

deploy_dir=$(mktemp -d /tmp/rev-ops-bot-main.XXXXXX)
cleanup() { sudo rm -rf "$deploy_dir"; }
trap cleanup EXIT

tar -xzf "$archive" -C "$deploy_dir"
sudo chown -R "$runtime_owner:$runtime_owner" "$deploy_dir"
sudo chmod -R a+rX "$deploy_dir"
runtime_path="/home/$runtime_owner/.local/bin:$PATH"
sudo -H -u "$runtime_owner" env PATH="$runtime_path" bash -c 'command -v node >/dev/null 2>&1' || { echo "deploy:error:node-not-found"; exit 1; }
sudo -H -u "$runtime_owner" env PATH="$runtime_path" bash -c 'command -v npm >/dev/null 2>&1' || { echo "deploy:error:npm-not-found"; exit 1; }
sudo -H -u "$runtime_owner" env PATH="$runtime_path" npm --prefix "$deploy_dir" run rev-ops-bot:verify
sudo -H -u "$runtime_owner" env PATH="$runtime_path" npm --prefix "$deploy_dir" run rev-ops-bot:prompt-evals
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

sudo mkdir -p "$source_root/apps" "$source_root/scripts/lib" "$source_root/ops/hermes"
sudo chown -R "$runtime_owner:$runtime_owner" "$source_root"
copy_dir "$deploy_dir/apps/rev-ops-bot" "$source_root/apps/rev-ops-bot"
copy_dir "$deploy_dir/scripts/lib" "$source_root/scripts/lib"
copy_file "$deploy_dir/package.json" "$source_root/package.json" 0644
copy_file "$deploy_dir/scripts/deploy-rev-ops-bot.mjs" "$source_root/scripts/deploy-rev-ops-bot.mjs" 0755
copy_file "$deploy_dir/scripts/verify-rev-ops-bot.mjs" "$source_root/scripts/verify-rev-ops-bot.mjs" 0644
copy_file "$deploy_dir/scripts/run-prompt-evals.mjs" "$source_root/scripts/run-prompt-evals.mjs" 0644
copy_file "$deploy_dir/ops/hermes/channels.md" "$source_root/ops/hermes/channels.md" 0644
copy_file "$deploy_dir/ops/hermes/profiles.yaml" "$source_root/ops/hermes/profiles.yaml" 0644

sudo mkdir -p "$profile/source" "$profile/runtime" "$profile/skills"
sudo chown "$runtime_owner:$runtime_owner" "$profile/source" "$profile/runtime" "$profile/skills"
copy_dir "$deploy_dir/apps/rev-ops-bot" "$profile/source/rev-ops-bot"
copy_file "$deploy_dir/apps/rev-ops-bot/profile/SOUL.md" "$profile/SOUL.md" 0644
copy_dir "$deploy_dir/apps/rev-ops-bot/skills/rev-ops-bot" "$profile/skills/rev-ops-bot"
copy_dir "$deploy_dir/apps/rev-ops-bot/runtime/mcp" "$profile/runtime/mcp"

sudo python3 - "$deploy_dir/apps/rev-ops-bot/profile/config.template.yaml" "$profile/config.yaml" "$source_root/apps/rev-ops-bot" <<'PY'
import copy
import sys
from pathlib import Path
import yaml

template_path = Path(sys.argv[1])
config_path = Path(sys.argv[2])
source_app_dir = sys.argv[3]
template = yaml.safe_load(template_path.read_text()) or {}
if config_path.exists():
    config = yaml.safe_load(config_path.read_text()) or {}
else:
    config = {}

changed = False
for key in ("security", "display", "model", "agent", "kanban", "slack"):
    expected = copy.deepcopy(template.get(key))
    if expected is not None and config.get(key) != expected:
        config[key] = expected
        changed = True

if "terminal" in template:
    terminal = copy.deepcopy(template["terminal"])
    terminal["cwd"] = source_app_dir
    if config.get("terminal") != terminal:
        config["terminal"] = terminal
        changed = True

if "cron" in template:
    target = config.setdefault("cron", {})
    for cron_key, value in template["cron"].items():
        if target.get(cron_key) != value:
            target[cron_key] = value
            changed = True

for key in ("gateway", "rev_ops", "mcp_servers"):
    expected = copy.deepcopy(template.get(key))
    if expected is not None and config.get(key) != expected:
        config[key] = expected
        changed = True

if changed:
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
PY
sudo chown "$runtime_owner:$runtime_owner" "$profile/config.yaml"
sudo chmod 0644 "$profile/config.yaml"

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
  exit 0
fi

cd /tmp
uid=$(id -u "$runtime_owner")
sudo -H -u "$runtime_owner" XDG_RUNTIME_DIR="/run/user/$uid" systemctl --user reset-failed "$service" || true
sudo -H -u "$runtime_owner" XDG_RUNTIME_DIR="/run/user/$uid" systemctl --user restart "$service"
sudo -H -u "$runtime_owner" XDG_RUNTIME_DIR="/run/user/$uid" systemctl --user is-active "$service"
sleep "\${REVOPS_BOT_DEPLOY_GATEWAY_SETTLE_SECONDS:-10}"

run_post_deploy_check() {
  label="$1"
  shift
  attempts="\${REVOPS_BOT_DEPLOY_CHECK_ATTEMPTS:-4}"
  delay_seconds="\${REVOPS_BOT_DEPLOY_CHECK_RETRY_SECONDS:-15}"
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

run_post_deploy_check audit sudo -H -u "$runtime_owner" HERMES_PROFILE_DIR="$profile" HERMES_HOME="$profile" XDG_RUNTIME_DIR="/run/user/$uid" "$source_root/apps/rev-ops-bot/runtime/audit-live-profile.sh"
run_post_deploy_check health sudo -H -u "$runtime_owner" HERMES_PROFILE_DIR="$profile" HERMES_HOME="$profile" XDG_RUNTIME_DIR="/run/user/$uid" bash -lc "cd '$source_root' && apps/rev-ops-bot/runtime/check-health.sh"
sudo -H -u "$runtime_owner" XDG_RUNTIME_DIR="/run/user/$uid" systemctl --user status "$service" --no-pager

echo "deploy:summary:sha=$deploy_sha"
echo "deploy:summary:ref=$deploy_branch"
echo "deploy:summary:timestamp=$deploy_timestamp"
echo "deploy:summary:gateway=active"
echo "deploy:summary:remote_verify=$remote_verify"
echo "deploy:summary:audit=passed"
echo "deploy:summary:health=passed"
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
}

function log(message) {
  console.log(`[rev-ops-bot-deploy] ${message}`);
}
