#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

export const PROJECT_ID = "staffany-warehouse";
export const DEFAULT_ZONE = "asia-southeast1-a";
export const CUSTOM_METADATA_ROLE_ID = "hermesBotVmSshMetadataWriter";
export const CUSTOM_METADATA_ROLE = `projects/${PROJECT_ID}/roles/${CUSTOM_METADATA_ROLE_ID}`;
export const SSH_METADATA_PERMISSION = "compute.instances.setMetadata";
export const SERVICE_ACCOUNT_ACT_AS_PERMISSION = "iam.serviceAccounts.actAs";

export const BOT_REGISTRY = {
  "hermes-data-bot": {
    appSlug: "hermes-data-bot",
    profile: "staffanydatabot",
    vm: "hermes-data-bot-poc",
    zone: DEFAULT_ZONE,
    serviceAccount: "hermes-data-bot@staffany-warehouse.iam.gserviceaccount.com",
  },
  "nurtureany-sales-bot": {
    appSlug: "nurtureany-sales-bot",
    profile: "nurtureanysalesbot",
    vm: "nurtureany-sales-bot-prod",
    zone: DEFAULT_ZONE,
    serviceAccount: "hermes-data-bot@staffany-warehouse.iam.gserviceaccount.com",
  },
  "psm-ops-bot": {
    appSlug: "psm-ops-bot",
    profile: "psmopsbot",
    vm: "hermes-psm-ops-bot-poc",
    zone: DEFAULT_ZONE,
    serviceAccount: "hermes-psm-ops-bot@staffany-warehouse.iam.gserviceaccount.com",
  },
  launchbot: {
    appSlug: "launchbot",
    profile: "launchbot",
    vm: "hermes-data-bot-poc",
    zone: DEFAULT_ZONE,
    serviceAccount: "hermes-data-bot@staffany-warehouse.iam.gserviceaccount.com",
  },
};

export const PROJECT_ROLES = [
  "roles/compute.viewer",
  "roles/iap.tunnelResourceAccessor",
  "roles/compute.osLogin",
];

export const INSTANCE_ROLES = [
  "roles/compute.osAdminLogin",
  CUSTOM_METADATA_ROLE,
];

export const SERVICE_ACCOUNT_ROLES = [
  "roles/iam.serviceAccountUser",
];

const FORBIDDEN_ROLE_PATTERNS = [
  /^roles\/owner$/,
  /^roles\/editor$/,
  /^roles\/compute\.admin$/,
  /^roles\/compute\.instanceAdmin(?:\.v1)?$/,
  /^roles\/secretmanager\./,
];

function printHelp() {
  console.log(`Usage: node scripts/onboard-hermes-bot-access.mjs --email <user@staffany.com> --bot <bot|all> [options]

Grants and verifies GCP VM deploy access for StaffAny Hermes bots.

Options:
  --email <email>    Google user email to onboard. Required.
  --bot <name|all>   One of: ${Object.keys(BOT_REGISTRY).join(", ")}, all. Required.
  --apply            Mutate IAM. Without this flag, only prints dry-run plan and current status.
  --json             Print machine-readable JSON.
  --verbose          Print read-only check commands and apply commands as they run.
  --help             Show this help.
`);
}

export function parseArgs(argv) {
  const parsed = {
    email: "",
    bot: "",
    apply: false,
    json: false,
    verbose: false,
    help: false,
  };
  const valueOptions = new Set(["email", "bot"]);
  for (let index = 0; index < argv.length; index += 1) {
    const raw = argv[index];
    if (raw === "--apply") {
      parsed.apply = true;
      continue;
    }
    if (raw === "--json") {
      parsed.json = true;
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
    parsed[optionName] = optionValue;
  }
  return parsed;
}

export function selectedBots(botName) {
  if (botName === "all") return Object.values(BOT_REGISTRY);
  const bot = BOT_REGISTRY[botName];
  if (!bot) {
    throw new Error(`Unknown bot: ${botName}. Expected one of: ${Object.keys(BOT_REGISTRY).join(", ")}, all`);
  }
  return [bot];
}

export function principalForEmail(email) {
  const normalized = String(email || "").trim().toLowerCase();
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(normalized)) {
    throw new Error(`Invalid --email: ${email}`);
  }
  return `user:${normalized}`;
}

export function assertSafeRole(role) {
  if (FORBIDDEN_ROLE_PATTERNS.some((pattern) => pattern.test(role))) {
    throw new Error(`Refusing to grant broad or secret-bearing role: ${role}`);
  }
}

function dedupeByKey(items) {
  const seen = new Set();
  const deduped = [];
  for (const item of items) {
    if (seen.has(item.key)) continue;
    seen.add(item.key);
    deduped.push(item);
  }
  return deduped;
}

export function buildGrantPlan({ email, bot }) {
  const principal = principalForEmail(email);
  const bots = selectedBots(bot);
  const actions = [];

  actions.push({
    type: "customRole",
    key: `custom-role:${CUSTOM_METADATA_ROLE_ID}`,
    role: CUSTOM_METADATA_ROLE,
    command: [
      "gcloud", "iam", "roles", "create", CUSTOM_METADATA_ROLE_ID,
      `--project=${PROJECT_ID}`,
      "--title=Hermes Bot VM SSH metadata writer",
      "--description=Allows gcloud compute ssh/scp to add SSH keys to reviewed Hermes bot VM metadata.",
      `--permissions=${SSH_METADATA_PERMISSION}`,
      "--stage=GA",
    ],
  });

  for (const role of PROJECT_ROLES) {
    assertSafeRole(role);
    actions.push({
      type: "projectBinding",
      key: `project:${PROJECT_ID}:${role}:${principal}`,
      role,
      principal,
      resource: PROJECT_ID,
      command: [
        "gcloud", "projects", "add-iam-policy-binding", PROJECT_ID,
        `--member=${principal}`,
        `--role=${role}`,
      ],
    });
  }

  for (const botConfig of bots) {
    for (const role of INSTANCE_ROLES) {
      assertSafeRole(role);
      actions.push({
        type: "instanceBinding",
        key: `instance:${PROJECT_ID}:${botConfig.zone}:${botConfig.vm}:${role}:${principal}`,
        role,
        principal,
        bot: botConfig.appSlug,
        profile: botConfig.profile,
        resource: botConfig.vm,
        zone: botConfig.zone,
        command: [
          "gcloud", "compute", "instances", "add-iam-policy-binding", botConfig.vm,
          `--project=${PROJECT_ID}`,
          `--zone=${botConfig.zone}`,
          `--member=${principal}`,
          `--role=${role}`,
        ],
      });
    }

    for (const role of SERVICE_ACCOUNT_ROLES) {
      assertSafeRole(role);
      actions.push({
        type: "serviceAccountBinding",
        key: `service-account:${botConfig.serviceAccount}:${role}:${principal}`,
        role,
        principal,
        bot: botConfig.appSlug,
        profile: botConfig.profile,
        resource: botConfig.serviceAccount,
        command: [
          "gcloud", "iam", "service-accounts", "add-iam-policy-binding", botConfig.serviceAccount,
          `--project=${PROJECT_ID}`,
          `--member=${principal}`,
          `--role=${role}`,
        ],
      });
    }
  }

  return {
    project: PROJECT_ID,
    principal,
    email: principal.slice("user:".length),
    bot,
    bots: bots.map((botConfig) => ({ ...botConfig })),
    actions: dedupeByKey(actions),
  };
}

export function readOnlyCommandsForPlan(plan) {
  const commands = [
    ["gcloud", "iam", "roles", "describe", CUSTOM_METADATA_ROLE_ID, `--project=${PROJECT_ID}`, "--format=json"],
    ["gcloud", "projects", "get-iam-policy", PROJECT_ID, "--format=json"],
  ];
  const instances = new Map();
  const serviceAccounts = new Set();
  for (const botConfig of plan.bots) {
    instances.set(`${botConfig.zone}:${botConfig.vm}`, botConfig);
    serviceAccounts.add(botConfig.serviceAccount);
  }
  for (const botConfig of instances.values()) {
    commands.push([
      "gcloud", "compute", "instances", "get-iam-policy", botConfig.vm,
      `--project=${PROJECT_ID}`,
      `--zone=${botConfig.zone}`,
      "--format=json",
    ]);
  }
  for (const serviceAccount of serviceAccounts) {
    commands.push([
      "gcloud", "iam", "service-accounts", "get-iam-policy", serviceAccount,
      `--project=${PROJECT_ID}`,
      "--format=json",
    ]);
  }
  for (const botConfig of instances.values()) {
    commands.push([
      "gcloud", "policy-troubleshoot", "iam",
      `//compute.googleapis.com/projects/${PROJECT_ID}/zones/${botConfig.zone}/instances/${botConfig.vm}`,
      `--principal-email=${plan.email}`,
      `--permission=${SSH_METADATA_PERMISSION}`,
      "--format=json(access)",
    ]);
  }
  for (const serviceAccount of serviceAccounts) {
    commands.push([
      "gcloud", "policy-troubleshoot", "iam",
      `//iam.googleapis.com/projects/${PROJECT_ID}/serviceAccounts/${serviceAccount}`,
      `--principal-email=${plan.email}`,
      `--permission=${SERVICE_ACCOUNT_ACT_AS_PERMISSION}`,
      "--format=json(access)",
    ]);
  }
  return commands;
}

export function commandsToRun(plan, { apply = false } = {}) {
  return apply
    ? [...readOnlyCommandsForPlan(plan), ...plan.actions.map((action) => action.command)]
    : readOnlyCommandsForPlan(plan);
}

function runCommand(command, { verbose = false, allowNotFound = false } = {}) {
  if (verbose) console.error(`$ ${command.map(shellQuote).join(" ")}`);
  const result = spawnSync(command[0], command.slice(1), {
    encoding: "utf8",
    stdio: "pipe",
    maxBuffer: 10 * 1024 * 1024,
  });
  if (allowNotFound && result.status !== 0 && /NOT_FOUND|not found/i.test(`${result.stderr}\n${result.stdout}`)) {
    return null;
  }
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`Command failed (${result.status}): ${command.map(shellQuote).join(" ")}\n${result.stderr || result.stdout}`);
  }
  return result.stdout || "";
}

function runJson(command, options = {}) {
  const output = runCommand(command, options);
  if (output === null) return null;
  return output.trim() ? JSON.parse(output) : {};
}

function hasBinding(policy, role, member) {
  return Boolean((policy?.bindings || []).some((binding) => (
    binding.role === role && (binding.members || []).includes(member)
  )));
}

function roleStatus(roleJson) {
  if (roleJson === null) return { exists: false, safe: true, permissions: [] };
  const permissions = [...(roleJson.includedPermissions || [])].sort();
  const safe = permissions.length === 1 && permissions[0] === SSH_METADATA_PERMISSION;
  return { exists: true, safe, permissions };
}

function troubleshootAccess(command, options) {
  try {
    const json = runJson(command, options);
    return json?.access || "UNKNOWN";
  } catch (error) {
    return `ERROR: ${error.message}`;
  }
}

function collectState(plan, { verbose = false } = {}) {
  const role = roleStatus(runJson(
    ["gcloud", "iam", "roles", "describe", CUSTOM_METADATA_ROLE_ID, `--project=${PROJECT_ID}`, "--format=json"],
    { verbose, allowNotFound: true },
  ));
  const projectPolicy = runJson(["gcloud", "projects", "get-iam-policy", PROJECT_ID, "--format=json"], { verbose });
  const instancePolicies = new Map();
  const serviceAccountPolicies = new Map();
  const verification = [];

  const instances = new Map();
  const serviceAccounts = new Set();
  for (const botConfig of plan.bots) {
    instances.set(`${botConfig.zone}:${botConfig.vm}`, botConfig);
    serviceAccounts.add(botConfig.serviceAccount);
  }

  for (const [key, botConfig] of instances) {
    instancePolicies.set(key, runJson([
      "gcloud", "compute", "instances", "get-iam-policy", botConfig.vm,
      `--project=${PROJECT_ID}`,
      `--zone=${botConfig.zone}`,
      "--format=json",
    ], { verbose }));
    verification.push({
      type: "instancePermission",
      resource: botConfig.vm,
      permission: SSH_METADATA_PERMISSION,
      access: troubleshootAccess([
        "gcloud", "policy-troubleshoot", "iam",
        `//compute.googleapis.com/projects/${PROJECT_ID}/zones/${botConfig.zone}/instances/${botConfig.vm}`,
        `--principal-email=${plan.email}`,
        `--permission=${SSH_METADATA_PERMISSION}`,
        "--format=json(access)",
      ], { verbose }),
    });
  }

  for (const serviceAccount of serviceAccounts) {
    serviceAccountPolicies.set(serviceAccount, runJson([
      "gcloud", "iam", "service-accounts", "get-iam-policy", serviceAccount,
      `--project=${PROJECT_ID}`,
      "--format=json",
    ], { verbose }));
    verification.push({
      type: "serviceAccountPermission",
      resource: serviceAccount,
      permission: SERVICE_ACCOUNT_ACT_AS_PERMISSION,
      access: troubleshootAccess([
        "gcloud", "policy-troubleshoot", "iam",
        `//iam.googleapis.com/projects/${PROJECT_ID}/serviceAccounts/${serviceAccount}`,
        `--principal-email=${plan.email}`,
        `--permission=${SERVICE_ACCOUNT_ACT_AS_PERMISSION}`,
        "--format=json(access)",
      ], { verbose }),
    });
  }

  const statuses = plan.actions.map((action) => {
    if (action.type === "customRole") {
      return { ...action, status: role.exists ? "present" : "missing" };
    }
    if (action.type === "projectBinding") {
      return { ...action, status: hasBinding(projectPolicy, action.role, action.principal) ? "present" : "missing" };
    }
    if (action.type === "instanceBinding") {
      const policy = instancePolicies.get(`${action.zone}:${action.resource}`);
      return { ...action, status: hasBinding(policy, action.role, action.principal) ? "present" : "missing" };
    }
    if (action.type === "serviceAccountBinding") {
      const policy = serviceAccountPolicies.get(action.resource);
      return { ...action, status: hasBinding(policy, action.role, action.principal) ? "present" : "missing" };
    }
    return { ...action, status: "unknown" };
  });

  return {
    role,
    actions: statuses,
    verification,
  };
}

function applyMissing(state, { verbose = false } = {}) {
  if (state.role.exists && !state.role.safe) {
    throw new Error(`${CUSTOM_METADATA_ROLE} exists but is unsafe. Included permissions: ${state.role.permissions.join(", ")}`);
  }
  const applied = [];
  for (const action of state.actions) {
    if (action.status !== "missing") continue;
    runCommand(action.command, { verbose });
    applied.push(action.key);
  }
  return applied;
}

function summarize(plan, state, { apply = false, applied = [] } = {}) {
  return {
    project: plan.project,
    principal: plan.principal,
    selectedBots: plan.bots.map((bot) => bot.appSlug),
    mode: apply ? "apply" : "dry-run",
    dryRun: !apply,
    customRole: state.role,
    actions: state.actions.map((action) => ({
      type: action.type,
      key: action.key,
      status: action.status,
      command: action.command,
    })),
    verification: state.verification,
    applied,
  };
}

function printHuman(summary, { apply }) {
  console.log(`Hermes bot deploy-access onboarding for ${summary.principal}`);
  console.log(`Project: ${summary.project}`);
  console.log(`Bots: ${summary.selectedBots.join(", ")}`);
  console.log("");

  if (!summary.customRole.exists) {
    console.log(`Custom role: missing (${CUSTOM_METADATA_ROLE})`);
  } else if (!summary.customRole.safe) {
    console.log(`Custom role: unsafe (${summary.customRole.permissions.join(", ")})`);
  } else {
    console.log(`Custom role: present (${CUSTOM_METADATA_ROLE})`);
  }
  console.log("");

  const missing = summary.actions.filter((action) => action.status === "missing");
  const present = summary.actions.filter((action) => action.status === "present");
  console.log(`Present grants: ${present.length}`);
  console.log(`Missing grants: ${missing.length}`);
  for (const action of missing) {
    console.log(`- ${action.key}`);
    console.log(`  ${action.command.map(shellQuote).join(" ")}`);
  }
  console.log("");

  if (summary.verification.length) {
    console.log("Permission checks:");
    for (const check of summary.verification) {
      console.log(`- ${check.resource} ${check.permission}: ${check.access}`);
    }
    console.log("");
  }

  if (apply) {
    console.log(`Applied grants: ${summary.applied.length}`);
  } else {
    console.log("Dry run only. Re-run with --apply to mutate IAM.");
  }
}

function shellQuote(value) {
  const text = String(value);
  return /^[A-Za-z0-9_./:@=-]+$/.test(text) ? text : `'${text.replace(/'/g, "'\"'\"'")}'`;
}

export function runCli(argv = process.argv.slice(2)) {
  const args = parseArgs(argv);
  if (args.help) {
    printHelp();
    return 0;
  }
  if (!args.email) throw new Error("--email is required");
  if (!args.bot) throw new Error("--bot is required");

  const plan = buildGrantPlan({ email: args.email, bot: args.bot });
  const stateBefore = collectState(plan, { verbose: args.verbose });
  const applied = args.apply ? applyMissing(stateBefore, { verbose: args.verbose }) : [];
  const stateAfter = args.apply ? collectState(plan, { verbose: args.verbose }) : stateBefore;
  const summary = summarize(plan, stateAfter, { apply: args.apply, applied });

  if (args.json) {
    console.log(JSON.stringify(summary, null, 2));
  } else {
    printHuman(summary, { apply: args.apply });
  }
  return 0;
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  try {
    process.exitCode = runCli(process.argv.slice(2));
  } catch (error) {
    console.error(`onboard-hermes-bot-access:error:${error.message}`);
    process.exitCode = 1;
  }
}
