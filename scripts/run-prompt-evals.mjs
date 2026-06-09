import { existsSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
const appsRoot = join(repoRoot, "apps");
const allowedModes = new Set(["static", "tool-trace", "answer-contract", "live-smoke"]);
const requiredEvalFields = [
  "id",
  "bot",
  "surface",
  "input",
  "setup",
  "expected_tool_trace",
  "expected_answer_contract",
  "forbidden_behavior",
  "grade_notes"
];

function usage() {
  return [
    "Usage: node scripts/run-prompt-evals.mjs --app <app|all> --mode <static|tool-trace|answer-contract|live-smoke|all>",
    "",
    "This v1 runner is deterministic. It validates prompt eval manifests, source-file",
    "contract assertions, regex syntax, and expected tool/answer assertions. It does",
    "not call models or write Slack messages."
  ].join("\n");
}

function parseArgs(argv) {
  const args = { app: "all", mode: "all" };
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index];
    if (item === "--help" || item === "-h") {
      args.help = true;
    } else if (item === "--app") {
      args.app = argv[++index];
    } else if (item.startsWith("--app=")) {
      args.app = item.slice("--app=".length);
    } else if (item === "--mode") {
      args.mode = argv[++index];
    } else if (item.startsWith("--mode=")) {
      args.mode = item.slice("--mode=".length);
    } else {
      throw new Error(`Unknown argument: ${item}`);
    }
  }
  return args;
}

function fail(failures, relPath, message) {
  failures.push(`${relPath}: ${message}`);
}

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function listAppsWithPromptEvals() {
  return [
    "hermes-data-bot",
    "nurtureany-sales-bot",
    "launchbot"
  ].filter((app) => existsSync(join(appsRoot, app, "tests", "prompt-evals.json")));
}

function assertPlainObject(failures, relPath, value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    fail(failures, relPath, `${label} must be an object`);
    return false;
  }
  return true;
}

function assertString(failures, relPath, value, label) {
  if (typeof value !== "string" || value.trim() === "") {
    fail(failures, relPath, `${label} must be a non-empty string`);
    return false;
  }
  return true;
}

function assertStringArray(failures, relPath, value, label) {
  if (!Array.isArray(value)) {
    fail(failures, relPath, `${label} must be an array`);
    return false;
  }
  for (const item of value) {
    if (typeof item !== "string" || item.trim() === "") {
      fail(failures, relPath, `${label} contains a non-string or empty item`);
      return false;
    }
  }
  return true;
}

function compileRegexList(failures, relPath, patterns, label) {
  if (!patterns) return;
  if (!assertStringArray(failures, relPath, patterns, label)) return;
  for (const pattern of patterns) {
    try {
      new RegExp(pattern);
    } catch (error) {
      fail(failures, relPath, `${label} has invalid regex ${JSON.stringify(pattern)}: ${error.message}`);
    }
  }
}

function checkFileAssertion(failures, appRoot, relPath, assertion, label) {
  if (!assertPlainObject(failures, relPath, assertion, label)) return;
  if (!assertString(failures, relPath, assertion.path, `${label}.path`)) return;
  const absolutePath = join(appRoot, assertion.path);
  if (!existsSync(absolutePath) || !statSync(absolutePath).isFile()) {
    fail(failures, relPath, `${label}.path missing: ${assertion.path}`);
    return;
  }
  const text = readFileSync(absolutePath, "utf8");
  const mustContain = assertion.must_contain || [];
  const mustNotContain = assertion.must_not_contain || [];
  const mustMatch = assertion.must_match || [];
  const mustNotMatch = assertion.must_not_match || [];
  assertStringArray(failures, relPath, mustContain, `${label}.must_contain`);
  assertStringArray(failures, relPath, mustNotContain, `${label}.must_not_contain`);
  compileRegexList(failures, relPath, mustMatch, `${label}.must_match`);
  compileRegexList(failures, relPath, mustNotMatch, `${label}.must_not_match`);

  for (const requiredText of mustContain) {
    if (!text.includes(requiredText)) {
      fail(failures, relPath, `${assertion.path} missing required text: ${requiredText}`);
    }
  }
  for (const forbiddenText of mustNotContain) {
    if (text.includes(forbiddenText)) {
      fail(failures, relPath, `${assertion.path} contains forbidden text: ${forbiddenText}`);
    }
  }
  for (const pattern of mustMatch) {
    if (!new RegExp(pattern, "m").test(text)) {
      fail(failures, relPath, `${assertion.path} missing regex match: ${pattern}`);
    }
  }
  for (const pattern of mustNotMatch) {
    if (new RegExp(pattern, "m").test(text)) {
      fail(failures, relPath, `${assertion.path} matched forbidden regex: ${pattern}`);
    }
  }
}

function validateEval(failures, appRoot, relPath, evalCase, selectedMode, seenIds) {
  if (!assertPlainObject(failures, relPath, evalCase, "eval")) return false;
  for (const field of requiredEvalFields) {
    if (!(field in evalCase)) fail(failures, relPath, `${evalCase.id || "eval"} missing required field: ${field}`);
  }
  if (!assertString(failures, relPath, evalCase.id, "eval.id")) return false;
  if (seenIds.has(evalCase.id)) fail(failures, relPath, `duplicate eval id: ${evalCase.id}`);
  seenIds.add(evalCase.id);
  if (!assertString(failures, relPath, evalCase.bot, `${evalCase.id}.bot`)) return false;
  if (!assertString(failures, relPath, evalCase.surface, `${evalCase.id}.surface`)) return false;
  if (!assertString(failures, relPath, evalCase.input, `${evalCase.id}.input`)) return false;
  if (!allowedModes.has(evalCase.lane)) {
    fail(failures, relPath, `${evalCase.id}.lane must be one of ${[...allowedModes].join(", ")}`);
  }
  assertPlainObject(failures, relPath, evalCase.setup, `${evalCase.id}.setup`);
  assertPlainObject(failures, relPath, evalCase.expected_tool_trace, `${evalCase.id}.expected_tool_trace`);
  assertPlainObject(failures, relPath, evalCase.expected_answer_contract, `${evalCase.id}.expected_answer_contract`);
  assertStringArray(failures, relPath, evalCase.forbidden_behavior, `${evalCase.id}.forbidden_behavior`);
  assertString(failures, relPath, evalCase.grade_notes, `${evalCase.id}.grade_notes`);

  const trace = evalCase.expected_tool_trace || {};
  for (const key of ["must_call", "may_call", "allowed_tools", "forbidden_tools", "must_not_call"]) {
    if (trace[key] !== undefined) assertStringArray(failures, relPath, trace[key], `${evalCase.id}.expected_tool_trace.${key}`);
  }
  const answer = evalCase.expected_answer_contract || {};
  for (const key of ["must_include", "must_not_include", "must_match", "must_not_match"]) {
    if (key.includes("match")) {
      compileRegexList(failures, relPath, answer[key], `${evalCase.id}.expected_answer_contract.${key}`);
    } else if (answer[key] !== undefined) {
      assertStringArray(failures, relPath, answer[key], `${evalCase.id}.expected_answer_contract.${key}`);
    }
  }

  const assertions = evalCase.assertions || {};
  if (assertions.source_files !== undefined) {
    if (!Array.isArray(assertions.source_files)) {
      fail(failures, relPath, `${evalCase.id}.assertions.source_files must be an array`);
    } else {
      assertions.source_files.forEach((assertion, index) => {
        checkFileAssertion(failures, appRoot, relPath, assertion, `${evalCase.id}.assertions.source_files[${index}]`);
      });
    }
  }
  if (assertions.answer_fixture !== undefined) {
    if (!assertPlainObject(failures, relPath, assertions.answer_fixture, `${evalCase.id}.assertions.answer_fixture`)) return true;
    const fixture = assertions.answer_fixture;
    const output = String(fixture.output || "");
    if (!output) {
      fail(failures, relPath, `${evalCase.id}.assertions.answer_fixture.output must be non-empty`);
    }
    for (const requiredText of answer.must_include || []) {
      if (!output.includes(requiredText)) {
        fail(failures, relPath, `${evalCase.id}.answer_fixture missing required output text: ${requiredText}`);
      }
    }
    for (const forbiddenText of [...(answer.must_not_include || []), ...(evalCase.forbidden_behavior || [])]) {
      if (output.includes(forbiddenText)) {
        fail(failures, relPath, `${evalCase.id}.answer_fixture contains forbidden text: ${forbiddenText}`);
      }
    }
    for (const pattern of answer.must_match || []) {
      if (!new RegExp(pattern, "m").test(output)) {
        fail(failures, relPath, `${evalCase.id}.answer_fixture missing regex match: ${pattern}`);
      }
    }
    for (const pattern of answer.must_not_match || []) {
      if (new RegExp(pattern, "m").test(output)) {
        fail(failures, relPath, `${evalCase.id}.answer_fixture matched forbidden regex: ${pattern}`);
      }
    }
  }

  return selectedMode === "all" || selectedMode === evalCase.lane;
}

function validateManifest(app, selectedMode) {
  const appRoot = join(appsRoot, app);
  const path = join(appRoot, "tests", "prompt-evals.json");
  const relPath = `apps/${app}/tests/prompt-evals.json`;
  const failures = [];
  let evaluated = 0;
  let liveSmokeSpecs = 0;

  if (!existsSync(path)) {
    fail(failures, relPath, "missing prompt eval manifest");
    return { failures, evaluated, liveSmokeSpecs };
  }

  let manifest;
  try {
    manifest = readJson(path);
  } catch (error) {
    fail(failures, relPath, `invalid JSON: ${error.message}`);
    return { failures, evaluated, liveSmokeSpecs };
  }

  if (manifest.schema_version !== 1) fail(failures, relPath, "schema_version must be 1");
  if (manifest.app !== app) fail(failures, relPath, `app must be ${app}`);
  assertString(failures, relPath, manifest.bot, "bot");
  if (!assertPlainObject(failures, relPath, manifest.runtime_model, "runtime_model")) {
    return { failures, evaluated, liveSmokeSpecs };
  }
  if (manifest.runtime_model.provider !== "anthropic") fail(failures, relPath, "runtime_model.provider must be anthropic");
  if (manifest.runtime_model.model !== "claude-sonnet-4-6") {
    fail(failures, relPath, "runtime_model.model must be claude-sonnet-4-6");
  }
  if (!assertPlainObject(failures, relPath, manifest.codex_operator_checks || {}, "codex_operator_checks")) {
    return { failures, evaluated, liveSmokeSpecs };
  }
  if (!Array.isArray(manifest.evals)) {
    fail(failures, relPath, "evals must be an array");
    return { failures, evaluated, liveSmokeSpecs };
  }

  const seenIds = new Set();
  for (const evalCase of manifest.evals) {
    const selected = validateEval(failures, appRoot, relPath, evalCase, selectedMode, seenIds);
    if (selected) evaluated += 1;
    if (evalCase?.lane === "live-smoke") liveSmokeSpecs += 1;
  }

  if (selectedMode !== "all" && evaluated === 0) {
    fail(failures, relPath, `no evals selected for mode ${selectedMode}`);
  }
  return { failures, evaluated, liveSmokeSpecs };
}

let args;
try {
  args = parseArgs(process.argv.slice(2));
} catch (error) {
  console.error(error.message);
  console.error(usage());
  process.exit(2);
}

if (args.help) {
  console.log(usage());
  process.exit(0);
}

if (args.mode !== "all" && !allowedModes.has(args.mode)) {
  console.error(`Invalid --mode: ${args.mode}`);
  console.error(usage());
  process.exit(2);
}

const apps = args.app === "all" ? listAppsWithPromptEvals() : [args.app];
if (apps.length === 0) {
  console.error("No prompt eval manifests found.");
  process.exit(1);
}

const allFailures = [];
let totalEvaluated = 0;
let totalLiveSmokeSpecs = 0;
for (const app of apps) {
  const { failures, evaluated, liveSmokeSpecs } = validateManifest(app, args.mode);
  allFailures.push(...failures);
  totalEvaluated += evaluated;
  totalLiveSmokeSpecs += liveSmokeSpecs;
}

if (allFailures.length > 0) {
  console.error("Prompt eval verification failed:");
  for (const failure of allFailures) console.error(`- ${failure}`);
  process.exit(1);
}

const liveSmokeNote = totalLiveSmokeSpecs > 0
  ? ` live_smoke_specs=${totalLiveSmokeSpecs} live_slack_writes=not-run`
  : "";
console.log(`prompt-evals:ok apps=${apps.join(",")} mode=${args.mode} evals=${totalEvaluated}${liveSmokeNote}`);
