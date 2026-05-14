#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { existsSync, lstatSync, mkdirSync, openSync, readFileSync, closeSync, symlinkSync, unlinkSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(fileURLToPath(new URL("../..", import.meta.url)));
const defaultRegistryPath = join(repoRoot, "ops", "hermes", "profiles.yaml");

export function parseScalar(raw) {
  const value = String(raw ?? "").trim();
  if (value === "{}") return {};
  if (value === "[]") return [];
  if (value === "true") return true;
  if (value === "false") return false;
  if (/^-?\d+$/.test(value)) return Number(value);
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }
  if (value.startsWith("[") && value.endsWith("]")) {
    const inner = value.slice(1, -1).trim();
    if (!inner) return [];
    return inner.split(",").map((part) => parseScalar(part.trim()));
  }
  return value;
}

function stripComment(line) {
  let inSingle = false;
  let inDouble = false;
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    if (char === "'" && !inDouble) inSingle = !inSingle;
    if (char === '"' && !inSingle) inDouble = !inDouble;
    if (char === "#" && !inSingle && !inDouble) return line.slice(0, index);
  }
  return line;
}

function nextMeaningfulLine(lines, startIndex) {
  for (let index = startIndex + 1; index < lines.length; index += 1) {
    const stripped = stripComment(lines[index]).trim();
    if (stripped) return stripped;
  }
  return "";
}

export function parseProfilesYaml(text) {
  const root = {};
  const stack = [{ indent: -1, value: root }];
  const lines = String(text).split(/\r?\n/);

  for (let index = 0; index < lines.length; index += 1) {
    const line = stripComment(lines[index]);
    if (!line.trim()) continue;
    const indent = line.match(/^ */)[0].length;
    const content = line.trim();

    while (stack.length > 1 && indent <= stack[stack.length - 1].indent) stack.pop();
    const parent = stack[stack.length - 1].value;

    if (content.startsWith("- ")) {
      if (!Array.isArray(parent)) throw new Error(`YAML list item has non-list parent near: ${content}`);
      const rest = content.slice(2).trim();
      if (!rest) {
        const item = {};
        parent.push(item);
        stack.push({ indent, value: item });
        continue;
      }
      const match = rest.match(/^([^:]+):(.*)$/);
      if (match) {
        const item = {};
        item[match[1].trim()] = parseScalar(match[2].trim());
        parent.push(item);
        stack.push({ indent, value: item });
      } else {
        parent.push(parseScalar(rest));
      }
      continue;
    }

    const match = content.match(/^([^:]+):(.*)$/);
    if (!match || Array.isArray(parent)) throw new Error(`Unsupported YAML line near: ${content}`);
    const key = match[1].trim();
    const rest = match[2].trim();
    if (rest) {
      parent[key] = parseScalar(rest);
      continue;
    }
    const child = nextMeaningfulLine(lines, index).startsWith("- ") ? [] : {};
    parent[key] = child;
    stack.push({ indent, value: child });
  }

  if (!Array.isArray(root.profiles)) throw new Error("profiles.yaml must contain a profiles list");
  return root.profiles;
}

export function expandPath(value, env = process.env) {
  if (!value) return value;
  const home = env.HOME || "";
  return String(value)
    .replace(/^\~(?=\/|$)/, home)
    .replaceAll("${HOME}", home);
}

function envFromFile(path) {
  if (!existsSync(path)) return {};
  const output = {};
  for (const rawLine of readFileSync(path, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const [key, ...rest] = line.split("=");
    output[key] = rest.join("=").replace(/^['"]|['"]$/g, "");
  }
  return output;
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd || repoRoot,
    env: { ...process.env, ...(options.env || {}) },
    encoding: "utf8",
    timeout: options.timeout || 120000,
  });
  return {
    ok: result.status === 0,
    status: result.status,
    stdout: result.stdout || "",
    stderr: result.stderr || "",
  };
}

function parseToolCount(output) {
  const match = String(output).match(/Tools discovered:\s*([0-9]+)/i);
  return match ? Number(match[1]) : null;
}

function readJsonFile(path, fallback) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return fallback;
  }
}

function latestTimestampFor(text, pattern) {
  let latest = null;
  for (const line of String(text || "").split(/\r?\n/)) {
    if (!pattern.test(line)) continue;
    const match = line.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/);
    if (match) latest = new Date(`${match[1].replace(" ", "T")}Z`).getTime();
  }
  return latest;
}

function socketStaleFromLog(profileDir, thresholdSeconds) {
  const logPath = join(profileDir, "logs", "gateway.log");
  const errorPath = join(profileDir, "logs", "gateway.error.log");
  const text = [logPath, errorPath].filter(existsSync).map((path) => readFileSync(path, "utf8")).join("\n");
  const stale = latestTimestampFor(text, /seems to be stale|Failed to check .*session|Failed to connect|ClientConnectorDNSError|TimeoutError/i);
  if (!stale) return false;
  const good = latestTimestampFor(text, /Socket Mode connected|slack connected|A new session .* established/i) || 0;
  if (good >= stale) return false;
  return Date.now() - stale > thresholdSeconds * 1000;
}

function launchdServiceDisabled(profile) {
  if (process.platform !== "darwin") return false;
  const label = profile.service?.launchd_label;
  if (!label) return false;
  const result = run("launchctl", ["print-disabled", `gui/${process.getuid()}`], { timeout: 30000 });
  return result.ok && new RegExp(`"${label}"\\s*=>\\s*disabled`).test(result.stdout);
}

function isRemoteOnlyFromThisHost(profile) {
  return process.platform === "darwin" && profile.deploy_host && profile.deploy_host !== "local-macos";
}

function cronFacts(profileDir, profile) {
  const jobsPath = join(profileDir, "cron", "jobs.json");
  const payload = readJsonFile(jobsPath, { jobs: [] });
  const jobs = Array.isArray(payload) ? payload : payload.jobs || [];
  const unsafePrefixes = profile.unsafe_cron_name_prefixes || [];
  return jobs
    .filter((job) => job && job.enabled === true)
    .map((job) => {
      const name = String(job.name || "");
      const prompt = String(job.prompt || "");
      const unsafeByName = unsafePrefixes.some((prefix) => name.startsWith(prefix));
      const unsafeByPrompt = /send_message\s*\(/.test(prompt);
      const lastError = String(job.last_error || "");
      return {
        id: String(job.id || ""),
        name,
        unsafe: unsafeByName || unsafeByPrompt,
        missingTimezone: !job.timezone && job.no_agent !== true,
        lastStatus: job.last_status || null,
        lastError,
      };
    });
}

function blockForServer(configText, serverName) {
  const marker = `  ${serverName}:`;
  const start = configText.indexOf(marker);
  if (start === -1) return "";
  const rest = configText.slice(start);
  const next = rest.slice(marker.length).search(/\n  [A-Za-z0-9_]+:/);
  return next === -1 ? rest : rest.slice(0, marker.length + next);
}

export function countMissingConfiguredPaths(profileDir, profile = {}) {
  const configPath = join(profileDir, "config.yaml");
  if (!existsSync(configPath)) return 0;
  const text = readFileSync(configPath, "utf8");
  const requiredServers = Object.keys(profile.required_mcp || {});
  const searchText = requiredServers.length > 0
    ? requiredServers.map((server) => blockForServer(text, server)).join("\n")
    : text;
  const matches = [...searchText.matchAll(/\/Users\/[^\s'"]+\/\.hermes\/profiles\/[^\s'"]+/g)];
  let missing = 0;
  for (const match of matches) {
    const path = match[0].replace(/[:,]+$/, "");
    if (!existsSync(path)) missing += 1;
  }
  return missing;
}

export function decideActions(profile, facts) {
  if (facts.remoteOnly) return [];

  const actions = [];
  if (facts.needsProfileAlias && profile.recovery?.create_profile_alias) {
    actions.push({ type: "create_profile_alias", severity: "repair", reason: "canonical profile dir is missing but live alias exists" });
  }
  if (facts.serviceDisabled) {
    actions.push({ type: "enable_launchd_service", severity: "repair", reason: "launchd service is disabled" });
  }
  if (facts.serviceDefinitionStale && facts.gatewayRunning) {
    actions.push({ type: "refresh_gateway_service", severity: "repair", reason: "managed service definition is stale" });
  }
  if (!facts.gatewayRunning) {
    actions.push({ type: "start_gateway", severity: "repair", reason: "gateway is not running" });
  } else if (facts.socketStale) {
    actions.push({ type: "restart_gateway", severity: "repair", reason: "slack socket is stale" });
  }
  if (facts.profileDrift) {
    actions.push({ type: "sync_profile", severity: "repair", reason: facts.profileDrift });
  }
  if (facts.missingConfiguredPathCount > 0) {
    actions.push({ type: "repair_profile_paths", severity: "repair", reason: `${facts.missingConfiguredPathCount} configured profile paths do not exist` });
  }
  for (const job of facts.unsafeCrons || []) {
    actions.push({ type: "pause_cron", severity: "repair", jobId: job.id, jobName: job.name, reason: "active cron is unsafe for bot-owned delivery" });
  }
  for (const channel of facts.missingChannelMembership || []) {
    actions.push({ type: "report_blocked_channel", severity: "blocked", channelId: channel, reason: "bot token is not a member of configured channel" });
  }
  if ((facts.staleSessionCount || 0) > 0 && (facts.activeAgents || 0) === 0) {
    actions.push({ type: "clear_stale_sessions", severity: "repair", reason: `${facts.staleSessionCount} stale sessions and no active agents` });
  }
  if (actions.length > 0) {
    actions.push({ type: "report", severity: "notice", reason: "repair actions or blockers detected" });
  }
  return actions;
}

export function summarizeFacts(profile, facts, actions) {
  return {
    profile: profile.name,
    live_profile: profile.live_profile || profile.name,
    status: profile.status,
    remote_only: Boolean(facts.remoteOnly),
    gateway_running: facts.gatewayRunning,
    service_disabled: Boolean(facts.serviceDisabled),
    service_definition_stale: Boolean(facts.serviceDefinitionStale),
    socket_stale: facts.socketStale,
    profile_drift: facts.profileDrift || "",
    missing_configured_path_count: facts.missingConfiguredPathCount,
    unsafe_crons: (facts.unsafeCrons || []).map((job) => job.name),
    missing_channel_membership: facts.missingChannelMembership || [],
    actions: actions.map((action) => ({ type: action.type, reason: action.reason, job: action.jobName || action.jobId || undefined })),
  };
}

async function slackApi(token, method, params = {}) {
  const url = new URL(`https://slack.com/api/${method}`);
  for (const [key, value] of Object.entries(params)) url.searchParams.set(key, value);
  const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  return response.json();
}

async function collectSlackMembership(profile, profileDir, checkSlack) {
  if (!checkSlack) return [];
  const env = envFromFile(join(profileDir, ".env"));
  const token = env.SLACK_BOT_TOKEN;
  if (!token) return [];
  const channels = [
    ...(profile.slack?.allowed_channel_ids || []),
    ...(profile.slack?.blocked_until_member_channel_ids || []),
  ];
  const missing = [];
  for (const channel of channels) {
    try {
      const result = await slackApi(token, "conversations.info", { channel });
      if (result.ok && result.channel && result.channel.is_member === false) missing.push(channel);
      if (!result.ok && result.error === "not_in_channel") missing.push(channel);
    } catch {
      // Network failures are not treated as missing membership.
    }
  }
  return missing;
}

async function collectFacts(profile, options) {
  const liveProfile = profile.live_profile || profile.name;
  const canonicalDir = expandPath(profile.profile_dir);
  const liveDir = expandPath(profile.live_profile_dir || profile.profile_dir);
  const remoteOnly = isRemoteOnlyFromThisHost(profile);
  if (remoteOnly) {
    const ledgerDir = join(process.env.HOME || repoRoot, ".hermes", "logs", "caretaker", profile.name);
    return {
      profileDir: canonicalDir,
      ledgerDir,
      canonicalDir,
      liveDir,
      remoteOnly: true,
      needsProfileAlias: false,
      serviceDisabled: false,
      serviceDefinitionStale: false,
      gatewayRunning: false,
      socketStale: false,
      healthOk: true,
      healthError: "",
      profileDrift: "",
      missingConfiguredPathCount: 0,
      unsafeCrons: [],
      missingChannelMembership: [],
      activeAgents: 0,
      staleSessionCount: 0,
    };
  }
  const profileDir = existsSync(canonicalDir) ? canonicalDir : liveDir;
  const gateway = run("hermes", ["-p", liveProfile, "gateway", "status"], { timeout: 30000 });
  const gatewayRunning = gateway.ok && !/not loaded|not running|✗ Gateway service is not loaded/i.test(gateway.stdout + gateway.stderr);
  const serviceDefinitionStale = /Service definition is stale/i.test(gateway.stdout + gateway.stderr);
  const health = profile.checks?.health_command ? run("bash", ["-lc", profile.checks.health_command], { env: { HERMES_PROFILE: liveProfile }, timeout: 180000 }) : { ok: true };
  const audit = profile.checks?.audit_command ? run("bash", ["-lc", profile.checks.audit_command], { env: { HERMES_PROFILE: liveProfile, HERMES_PROFILE_DIR: profileDir }, timeout: 180000 }) : { ok: true };
  const unsafeCrons = cronFacts(profileDir, profile).filter((job) => job.unsafe);
  const state = readJsonFile(join(profileDir, "gateway_state.json"), {});
  const missingChannelMembership = await collectSlackMembership(profile, profileDir, options.checkSlack);

  return {
    profileDir,
    canonicalDir,
    liveDir,
    needsProfileAlias: canonicalDir !== liveDir && existsSync(liveDir) && !existsSync(canonicalDir),
    serviceDisabled: launchdServiceDisabled(profile),
    serviceDefinitionStale,
    gatewayRunning,
    socketStale: socketStaleFromLog(profileDir, Number(profile.recovery?.stale_socket_seconds || 300)),
    healthOk: health.ok,
    healthError: (health.stderr || health.stdout || "").trim(),
    profileDrift: audit.ok ? "" : (audit.stderr || audit.stdout || "profile audit failed").trim().split(/\r?\n/).at(-1),
    missingConfiguredPathCount: countMissingConfiguredPaths(profileDir, profile),
    unsafeCrons,
    missingChannelMembership,
    activeAgents: Number(state.active_agents || 0),
    staleSessionCount: 0,
  };
}

function ledgerPath(profileDir) {
  const dir = join(profileDir, "operation-ledger");
  mkdirSync(dir, { recursive: true });
  return join(dir, "hermes-caretaker.jsonl");
}

function writeLedger(profileDir, event) {
  const row = JSON.stringify({ at: new Date().toISOString(), ...event });
  writeFileSync(ledgerPath(profileDir), `${row}\n`, { flag: "a", mode: 0o600 });
}

function acquireLock(lockPath) {
  try {
    const fd = openSync(lockPath, "wx");
    writeFileSync(fd, `${process.pid}\n`);
    return fd;
  } catch {
    throw new Error(`caretaker lock is already held: ${lockPath}`);
  }
}

function releaseLock(lockPath, fd) {
  try {
    closeSync(fd);
  } finally {
    try {
      unlinkSync(lockPath);
    } catch {
      // Ignore cleanup races.
    }
  }
}

function applyAction(profile, facts, action, options) {
  const liveProfile = profile.live_profile || profile.name;
  if (options.dryRun || !options.apply) return { ok: true, skipped: true };

  if (action.type === "create_profile_alias") {
    symlinkSync(facts.liveDir, facts.canonicalDir, "dir");
    return { ok: true };
  }
  if (action.type === "restart_gateway") {
    return run("hermes", ["-p", liveProfile, "gateway", "restart"], { timeout: 120000 });
  }
  if (action.type === "start_gateway") {
    return run("hermes", ["-p", liveProfile, "gateway", "start"], { timeout: 120000 });
  }
  if (action.type === "refresh_gateway_service") {
    return run("hermes", ["-p", liveProfile, "gateway", "start"], { timeout: 120000 });
  }
  if (action.type === "enable_launchd_service") {
    const label = profile.service?.launchd_label;
    if (!label || process.platform !== "darwin") return { ok: true, skipped: true };
    return run("launchctl", ["enable", `gui/${process.getuid()}/${label}`], { timeout: 30000 });
  }
  if (action.type === "pause_cron" && action.jobId) {
    return run("hermes", ["-p", liveProfile, "cron", "pause", action.jobId], { timeout: 60000 });
  }
  if (action.type === "sync_profile") {
    return { ok: false, stderr: "profile sync is classified but not auto-applied by caretaker yet" };
  }
  return { ok: true, skipped: true };
}

async function postReport(profile, facts, actions, options) {
  if (!options.postReport || options.dryRun || !options.apply || actions.length === 0) return;
  const env = envFromFile(join(facts.profileDir, ".env"));
  const token = env.SLACK_BOT_TOKEN;
  const channel = profile.slack?.home_channel_id;
  if (!token || !channel) return;
  const prefix = profile.slack?.report_prefix || "Hermes repair automation:";
  const repairLines = actions
    .filter((action) => action.type !== "report")
    .map((action) => `- ${action.type}: ${action.reason}${action.jobName ? ` (${action.jobName})` : ""}`)
    .join("\n");
  await slackApi(token, "chat.postMessage", {
    channel,
    text: `${prefix} ${profile.display_name || profile.name} caretaker ran.\n${repairLines || "- no repair action"}`,
  });
}

async function runCaretaker(argv = process.argv.slice(2)) {
  const options = {
    registry: defaultRegistryPath,
    profile: "",
    dryRun: !argv.includes("--apply"),
    apply: argv.includes("--apply"),
    checkSlack: argv.includes("--check-slack"),
    postReport: argv.includes("--post-report"),
    json: argv.includes("--json"),
  };
  for (let index = 0; index < argv.length; index += 1) {
    if (argv[index] === "--registry") options.registry = resolve(argv[index + 1]);
    if (argv[index] === "--profile") options.profile = argv[index + 1];
  }

  const profiles = parseProfilesYaml(readFileSync(options.registry, "utf8"))
    .filter((profile) => !options.profile || profile.name === options.profile || profile.live_profile === options.profile || (profile.aliases || []).includes(options.profile));
  if (profiles.length === 0) throw new Error(`no profiles matched ${options.profile || "registry"}`);

  const lockPath = join(process.env.TMPDIR || "/tmp", "hermes-caretaker.lock");
  const lockFd = acquireLock(lockPath);
  const summaries = [];
  try {
    for (const profile of profiles) {
      const facts = await collectFacts(profile, options);
      const actions = decideActions(profile, facts);
      const actionResults = [];
      for (const action of actions) {
        const result = applyAction(profile, facts, action, options);
        actionResults.push({ action, result });
      }
      writeLedger(facts.ledgerDir || facts.profileDir, {
        profile: profile.name,
        live_profile: profile.live_profile || profile.name,
        dry_run: options.dryRun,
        actions: actionResults.map(({ action, result }) => ({ type: action.type, reason: action.reason, ok: result.ok, skipped: Boolean(result.skipped) })),
      });
      await postReport(profile, facts, actions, options);
      summaries.push(summarizeFacts(profile, facts, actions));
    }
  } finally {
    releaseLock(lockPath, lockFd);
  }

  if (options.json) {
    console.log(JSON.stringify({ dry_run: options.dryRun, profiles: summaries }, null, 2));
  } else {
    for (const summary of summaries) {
      console.log(`${summary.profile}: ${summary.actions.length ? summary.actions.map((action) => action.type).join(",") : "ok"}`);
      for (const action of summary.actions) {
        console.log(`  - ${action.type}: ${action.reason}`);
      }
    }
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  runCaretaker().catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
}
