#!/usr/bin/env bun

import { createHash } from "crypto";
import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "fs";
import { join, relative, resolve } from "path";

const repoRoot = resolve(import.meta.dir, "..", "..");
const today = "2026-04-30";

function ensureDir(path: string) {
  mkdirSync(path, { recursive: true });
}

function sha256(text: string | Buffer) {
  return createHash("sha256").update(text).digest("hex");
}

function firstHeading(text: string) {
  return text.match(/^#\s+(.+)$/m)?.[1]?.trim() || "";
}

function walk(dir: string, predicate: (path: string) => boolean, out: string[] = []) {
  if (!existsSync(dir)) return out;
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    const rel = relative(dir, path);
    if (entry === ".git" || entry === "node_modules" || entry === ".venv" || entry === "venv") continue;
    const stat = statSync(path);
    if (stat.isDirectory()) walk(path, predicate, out);
    else if (predicate(path)) out.push(path);
  }
  return out;
}

function mdTable(rows: string[][]) {
  return rows.map((row) => `| ${row.join(" | ")} |`).join("\n");
}

async function buildOpenClawInventory() {
  const rawDir = join(repoRoot, "research", "raw", "openclaw-docs");
  ensureDir(rawDir);
  const xml = await fetch("https://docs.openclaw.ai/sitemap.xml").then((res) => {
    if (!res.ok) throw new Error(`OpenClaw sitemap fetch failed: ${res.status}`);
    return res.text();
  });
  const entries = [...xml.matchAll(/<loc>([^<]+)<\/loc>\s*<lastmod>([^<]+)<\/lastmod>/g)]
    .map((match) => ({ url: match[1], lastmod: match[2] }))
    .filter((entry) => !/docs\.openclaw\.ai\/(?:ar|de|es|fr|it|ja|ko|pt|ru|tr|zh|id)\//.test(entry.url))
    .sort((a, b) => a.url.localeCompare(b.url));
  const rows = [["URL", "Last Modified"]];
  for (const entry of entries) rows.push([entry.url, entry.lastmod]);
  const content = `# OpenClaw Docs URL Inventory

## Source Metadata

- Type: generated docs URL inventory
- Source class: OpenClaw official docs
- Source URL: https://docs.openclaw.ai/sitemap.xml
- Date checked: ${today}
- URL count: ${entries.length}
- Sitemap SHA-256: ${sha256(xml)}

## Raw Content Policy

This inventory records English OpenClaw docs URLs from the public sitemap. It excludes locale-prefixed translated duplicates and does not copy page bodies.

## Source Inventory

${mdTable(rows)}

## Evidence Extracts

- Generated from the public OpenClaw sitemap.
- Locale-prefixed translated duplicates are excluded so English source coverage is easier to audit.
- Use this inventory to select official docs pages for deeper source notes.
`;
  writeFileSync(join(rawDir, "url-inventory.md"), content);
  return entries.length;
}

function buildHermesInventory() {
  const hermesRoot = process.env.HERMES_AGENT_SOURCE || "/tmp/hermes-agent-agent-builder";
  const rawDir = join(repoRoot, "research", "raw", "hermes");
  ensureDir(rawDir);
  const wanted = (path: string) => {
    const rel = relative(hermesRoot, path).replaceAll("\\", "/");
    if (!/\.(md|mdx|yml|yaml|json|toml)$/.test(path)) return false;
    if (rel.includes("package-lock.json")) return false;
    return (
      rel === "README.md" ||
      rel === "AGENTS.md" ||
      rel === "CONTRIBUTING.md" ||
      rel === "SECURITY.md" ||
      rel.startsWith("website/docs/") ||
      rel.startsWith("skills/") ||
      rel.startsWith("optional-skills/") ||
      rel.startsWith("plugins/") ||
      rel.startsWith("gateway/platforms/")
    );
  };
  const files = walk(hermesRoot, wanted).sort((a, b) => a.localeCompare(b));
  const rows = [["Path", "Bytes", "SHA-256", "Title"]];
  let websiteDocs = 0;
  let skills = 0;
  let optionalSkills = 0;
  let pluginDocs = 0;
  for (const path of files) {
    const rel = relative(hermesRoot, path).replaceAll("\\", "/");
    const text = readFileSync(path);
    if (rel.startsWith("website/docs/") && rel.endsWith(".md")) websiteDocs++;
    if (rel.startsWith("skills/") && rel.endsWith("SKILL.md")) skills++;
    if (rel.startsWith("optional-skills/") && rel.endsWith("SKILL.md")) optionalSkills++;
    if (rel.startsWith("plugins/")) pluginDocs++;
    rows.push([rel, String(text.byteLength), sha256(text).slice(0, 16), firstHeading(text.toString("utf8"))]);
  }
  const commit = existsSync(join(hermesRoot, ".git"))
    ? Bun.spawnSync(["git", "-C", hermesRoot, "rev-parse", "--short", "HEAD"]).stdout.toString().trim()
    : "unavailable";
  const content = `# Hermes Docs Inventory

## Source Metadata

- Type: generated repo docs inventory
- Source class: Hermes Agent
- Source path: ${hermesRoot}
- Source URL: https://github.com/NousResearch/hermes-agent
- Commit: ${commit}
- Date checked: ${today}
- Total indexed files: ${files.length}
- Website docs count: ${websiteDocs}
- Built-in skill count: ${skills}
- Optional skill count: ${optionalSkills}
- Plugin doc/config count: ${pluginDocs}

## Raw Content Policy

This inventory records all discovered Hermes docs, skill docs, optional skill docs, plugin docs/configs, and key top-level docs with hashes. It does not duplicate full public repo contents.

## Source Inventory

${mdTable(rows)}

## Evidence Extracts

- Generated from the Hermes public repo clone at the commit recorded above.
- Includes website docs, built-in skills, optional skills, plugin docs/configs, and key top-level docs.
- Hashes let future agents detect when a source file changed before trusting stale synthesis.
`;
  writeFileSync(join(rawDir, "docs-inventory.md"), content);
  return { files: files.length, websiteDocs, skills, optionalSkills, pluginDocs };
}

function buildOpenClawKaiyiInventory() {
  const sourceRoot = "/Users/leekaiyi/workspace/openclaw-kaiyi";
  const rawDir = join(repoRoot, "research", "raw", "openclaw-kaiyi");
  ensureDir(rawDir);
  const wanted = (path: string) => {
    const rel = relative(sourceRoot, path).replaceAll("\\", "/");
    if (rel.startsWith(".git/") || rel.includes("/.git/")) return false;
    if (rel === ".env" || rel.startsWith(".env.")) return false;
    if (rel.includes("auth") || rel.includes("credentials")) return false;
    return /\.(md|json|ts|py|sh|yml|yaml)$/.test(path);
  };
  const files = walk(sourceRoot, wanted).sort((a, b) => a.localeCompare(b));
  const rows = [["Path", "Lines", "Bytes", "SHA-256"]];
  for (const path of files) {
    const rel = relative(sourceRoot, path).replaceAll("\\", "/");
    const text = readFileSync(path);
    rows.push([rel, String(text.toString("utf8").split("\n").length), String(text.byteLength), sha256(text).slice(0, 16)]);
  }
  const branch = Bun.spawnSync(["git", "-C", sourceRoot, "status", "--short", "--branch"]).stdout.toString().trim().split("\n")[0] || "unavailable";
  const content = `# openclaw-kaiyi File Inventory

## Source Metadata

- Type: generated local file inventory
- Source class: Kai Yi OpenClaw repo
- Source path: ${sourceRoot}
- Date checked: ${today}
- Git branch/status: ${branch}
- Indexed file count: ${files.length}

## Raw Content Policy

This inventory records non-secret docs, scripts, tests, and config-shaped files. It excludes .git, .env files, auth paths, and credential paths.

## Source Inventory

${mdTable(rows)}

## Evidence Extracts

- Generated from the local \`openclaw-kaiyi\` checkout without copying secrets.
- Includes docs, scripts, tests, runtime workspace files, and OpenClaw extension files.
- Excludes .env, auth, credential, and .git paths.
`;
  writeFileSync(join(rawDir, "file-inventory.md"), content);
  return files.length;
}

function buildMidasInventory() {
  const rawDir = join(repoRoot, "research", "raw", "midas");
  ensureDir(rawDir);
  const sourceRoot = "/Users/leekaiyi/workspace/midas";
  const paths = [
    "AGENTS.md",
    "docs/documentation-guide.md",
    "docs/product-compass.md",
    "research/wiki/index.md",
    "research/wiki/playbooks/ingest-source.md",
    "research/wiki/playbooks/plan-feature-from-research.md",
    "research/wiki/weights.md",
    "research/tools/audit-karpathy-ingest.ts",
    "skills/karpathy-research-ingest-audit/SKILL.md",
  ];
  const rows = [["Path", "Bytes", "SHA-256", "Title"]];
  for (const rel of paths) {
    const path = join(sourceRoot, rel);
    if (!existsSync(path)) continue;
    const text = readFileSync(path);
    rows.push([rel, String(text.byteLength), sha256(text).slice(0, 16), firstHeading(text.toString("utf8"))]);
  }
  const content = `# Midas Process File Inventory

## Source Metadata

- Type: generated local process inventory
- Source class: Midas process
- Source path: ${sourceRoot}
- Date checked: ${today}
- Indexed file count: ${rows.length - 1}

## Raw Content Policy

This inventory records process files used to model Agent Builder's research workflow. It does not copy full Midas source content.

## Source Inventory

${mdTable(rows)}

## Evidence Extracts

- Generated from selected Midas process files that define the research workflow.
- These files are used as process evidence, not product-domain evidence.
- Hashes let future agents detect drift in the process template.
`;
  writeFileSync(join(rawDir, "process-inventory.md"), content);
  return rows.length - 1;
}

function buildChatGptInventory() {
  const rawDir = join(repoRoot, "research", "raw", "chatgpt");
  ensureDir(rawDir);
  const rows = [
    ["URL", "Purpose"],
    ["https://help.openai.com/en/articles/20001143-chatgpt-workspace-agents-for-enterprise-and-business", "Workspace agent creation, builder, tools, apps, skills, files, schedules, Slack, admin controls"],
    ["https://help.openai.com/en/articles/20001066-skills-in-chatgpt", "ChatGPT skills behavior, sharing, beta/admin controls"],
    ["https://developers.openai.com/cookbook/articles/chatgpt-agents-sales-meeting-prep", "Workspace-agent cookbook and example build loop"],
    ["https://developers.openai.com/apps-sdk/build/state-management", "Apps SDK state categories and persistence guidance"],
    ["https://developers.openai.com/apps-sdk/guides/security-privacy", "Apps SDK security and privacy guidance"],
    ["https://developers.openai.com/apps-sdk/mcp-apps-in-chatgpt", "MCP Apps compatibility and ChatGPT-specific extensions"],
    ["https://developers.openai.com/codex/learn/best-practices", "Codex guidance on skills, MCP, automations, and session controls"],
    ["https://docs.cloud.google.com/bigquery/docs/use-bigquery-mcp", "Google BigQuery remote MCP endpoint, IAM/OAuth, roles, scopes, and limitations"],
    ["https://docs.cloud.google.com/bigquery/docs/reference/mcp/get_dataset_info", "BigQuery MCP tool reference and HTTP endpoint examples"],
    ["https://docs.cloud.google.com/run/docs/host-mcp-servers", "Cloud Run guidance for hosting streamable HTTP MCP servers"],
  ];
  const content = `# ChatGPT Workspace Agent URL Inventory

## Source Metadata

- Type: generated official URL inventory
- Source class: ChatGPT/OpenAI docs
- Date checked: ${today}
- URL count: ${rows.length - 1}

## Raw Content Policy

This inventory records official OpenAI and Help Center URLs used by the ChatGPT workspace-agent source note. It does not copy page bodies.

## Source Inventory

${mdTable(rows)}

## Evidence Extracts

- Generated from official OpenAI and Help Center URLs selected for ChatGPT workspace-agent planning.
- The inventory records URLs and intended use, not full copyrighted page bodies.
- Re-check these URLs before making production workspace-agent configuration decisions.
`;
  writeFileSync(join(rawDir, "url-inventory.md"), content);
  return rows.length - 1;
}

const openclaw = await buildOpenClawInventory();
const hermes = buildHermesInventory();
const kaiyi = buildOpenClawKaiyiInventory();
const midas = buildMidasInventory();
const chatgpt = buildChatGptInventory();

console.log("Inventories built:");
console.log(`- OpenClaw docs URLs: ${openclaw}`);
console.log(`- Hermes files: ${hermes.files} (website docs ${hermes.websiteDocs}, skills ${hermes.skills}, optional skills ${hermes.optionalSkills}, plugin docs/configs ${hermes.pluginDocs})`);
console.log(`- openclaw-kaiyi files: ${kaiyi}`);
console.log(`- Midas process files: ${midas}`);
console.log(`- ChatGPT URLs: ${chatgpt}`);
