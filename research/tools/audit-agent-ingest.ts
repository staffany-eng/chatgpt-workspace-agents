#!/usr/bin/env bun

import { existsSync, readFileSync } from "fs";
import { dirname, join, relative, resolve } from "path";
import { fileURLToPath } from "url";

type Options = {
  wikiPath: string;
  failUnder: number;
  json: boolean;
};

type Factor = {
  score: number;
  issues: string[];
};

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

function usage() {
  console.log(`Usage:
  bun research/tools/audit-agent-ingest.ts --wiki <source-note.md> [options]

Options:
  --wiki <path>       Maintained source note under research/wiki/sources/.
  --fail-under <n>    Exit non-zero if any factor is below n. Defaults to 10.
  --json              Print machine-readable JSON.`);
}

function parseArgs(argv: string[]): Options | null {
  const opts: Options = { wikiPath: "", failUnder: 10, json: false };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "-h" || arg === "--help") {
      usage();
      return null;
    }
    if (arg === "--wiki") opts.wikiPath = argv[++i] || "";
    else if (arg === "--fail-under") opts.failUnder = Number(argv[++i]);
    else if (arg === "--json") opts.json = true;
    else throw new Error(`Unknown argument: ${arg}`);
  }
  if (!opts.wikiPath) throw new Error("--wiki is required");
  if (!Number.isFinite(opts.failUnder) || opts.failUnder < 0 || opts.failUnder > 10) {
    throw new Error("--fail-under must be a number from 0 to 10");
  }
  return opts;
}

function read(path: string) {
  return readFileSync(path, "utf8");
}

function headingRegex(title: string) {
  return new RegExp(`^##\\s+${title.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*$`, "m");
}

function hasSection(text: string, title: string) {
  return headingRegex(title).test(text);
}

function getSection(text: string, title: string) {
  const match = headingRegex(title).exec(text);
  if (!match) return "";
  const start = match.index + match[0].length;
  const next = text.slice(start).search(/^##\s+/m);
  return next === -1 ? text.slice(start).trim() : text.slice(start, start + next).trim();
}

function bullets(section: string) {
  return section.split("\n").filter((line) => /^\s*-\s+\S/.test(line));
}

function titleOf(text: string) {
  return text.match(/^#\s+(.+)$/m)?.[1]?.trim() || "";
}

function score(issues: string[]): Factor {
  return { score: Math.max(0, 10 - issues.length), issues };
}

function linkedRawPaths(wikiPath: string, wikiText: string) {
  const evidence = getSection(wikiText, "Evidence Used");
  const links = [...evidence.matchAll(/\]\(([^)]+research\/raw\/[^)]+|(?:\.\.?\/)+raw\/[^)]+)\)/g)];
  return links
    .map((match) => resolve(dirname(wikiPath), match[1]))
    .filter((absolute) => absolute.startsWith(repoRoot));
}

function auditRawPreservation(wikiPath: string, wikiText: string) {
  const issues: string[] = [];
  const rawPaths = linkedRawPaths(wikiPath, wikiText);
  if (rawPaths.length < 1) issues.push("Evidence Used must link to at least one raw-source file under research/raw/.");

  for (const rawPath of rawPaths) {
    if (!existsSync(rawPath)) {
      issues.push(`Linked raw-source file does not exist: ${relative(repoRoot, rawPath)}`);
      continue;
    }
    const rawText = read(rawPath);
    if (!hasSection(rawText, "Source Metadata")) issues.push(`${relative(repoRoot, rawPath)} must include Source Metadata.`);
    if (!hasSection(rawText, "Raw Content Policy")) issues.push(`${relative(repoRoot, rawPath)} must include Raw Content Policy.`);
    if (!hasSection(rawText, "Source Inventory")) issues.push(`${relative(repoRoot, rawPath)} must include Source Inventory.`);
    if (!hasSection(rawText, "Evidence Extracts")) issues.push(`${relative(repoRoot, rawPath)} must include Evidence Extracts.`);
    if (!/Date checked:|Date ingested:|Base URL:|Source URL:|Source path:/i.test(rawText)) {
      issues.push(`${relative(repoRoot, rawPath)} must include retrieval/source metadata.`);
    }
    if (/API_KEY=|SECRET=|TOKEN=|BEGIN PRIVATE KEY|botToken":\s*"[^"$]/i.test(rawText)) {
      issues.push(`${relative(repoRoot, rawPath)} appears to contain secret-like raw content.`);
    }
  }
  return score(issues);
}

function auditMaintainedSourceNote(wikiText: string) {
  const issues: string[] = [];
  const requiredSections = [
    "Source Metadata",
    "Context Caveat",
    "Evidence Used",
    "What They Said",
    "Evidence Trace",
    "Learning Summary",
    "Synthesis Gate",
    "Possible Agent Builder Relevance",
    "Follow-Up Questions",
  ];
  for (const section of requiredSections) {
    if (!hasSection(wikiText, section)) issues.push(`Maintained source note must include ${section}.`);
  }
  if (/\bTODO\b|\bTBD\b|placeholder/i.test(wikiText)) issues.push("Maintained source note must not contain TODO/TBD/placeholder residue.");
  if (!/Default weight:\s*[1-5]/.test(getSection(wikiText, "Source Metadata"))) {
    issues.push("Source Metadata must include Default weight.");
  }
  if (!/Privacy:\s*(public|private|confidential|local repo|public docs|public MIT repo)/i.test(getSection(wikiText, "Source Metadata"))) {
    issues.push("Source Metadata must include a privacy classification.");
  }
  if (bullets(getSection(wikiText, "What They Said")).length < 3) {
    issues.push("What They Said must contain at least 3 direct evidence bullets.");
  }
  if (bullets(getSection(wikiText, "Learning Summary")).length < 3) {
    issues.push("Learning Summary must contain at least 3 source-learning bullets.");
  }
  const synthesisGate = getSection(wikiText, "Synthesis Gate");
  if (!/Mode:\s*autonomous_current_focus_synthesis/i.test(synthesisGate)) {
    issues.push("Synthesis Gate must use Mode: autonomous_current_focus_synthesis.");
  }
  if (!/Status:\s*(completed|blocked)/i.test(synthesisGate)) {
    issues.push("Synthesis Gate must include Status: completed or Status: blocked.");
  }
  if (!/Focus source:/i.test(synthesisGate)) issues.push("Synthesis Gate must record focus sources.");
  if (!/Evidence weight check:/i.test(synthesisGate)) issues.push("Synthesis Gate must record evidence weight check.");
  const relevance = getSection(wikiText, "Possible Agent Builder Relevance");
  if (!/(Agent-synthesized|Do-not-promote|Open question|User-supplied|User-confirmed)/i.test(relevance)) {
    issues.push("Possible Agent Builder Relevance must label implications.");
  }
  return score(issues);
}

function auditCompounding(wikiPath: string, wikiText: string) {
  const issues: string[] = [];
  const title = titleOf(wikiText);
  const relWiki = relative(join(repoRoot, "research", "wiki"), wikiPath).replaceAll("\\", "/");
  const indexPath = join(repoRoot, "research", "wiki", "index.md");
  const logPath = join(repoRoot, "research", "wiki", "log.md");
  const indexText = existsSync(indexPath) ? read(indexPath) : "";
  const logText = existsSync(logPath) ? read(logPath) : "";

  if (!wikiPath.includes(`${join("research", "wiki", "sources")}`)) {
    issues.push("Maintained source note should live under research/wiki/sources/.");
  }
  if (!indexText.includes(relWiki) && title && !indexText.includes(title)) {
    issues.push("research/wiki/index.md must link to the maintained source note.");
  }
  if (title && !logText.toLowerCase().includes(title.toLowerCase())) {
    issues.push("research/wiki/log.md must include an ingest entry for this source.");
  }
  if (!/Default weight:\s*[1-5]/.test(wikiText)) issues.push("Source note must carry evidence weight.");
  if (/\bDecision:\b/i.test(getSection(wikiText, "Possible Agent Builder Relevance"))) {
    issues.push("Do not promote source-note relevance directly as decisions.");
  }
  return score(issues);
}

function traceEntries(section: string) {
  return section.split("\n").filter((line) => /^\s*-\s+Claim:/.test(line));
}

function auditAuditability(wikiText: string) {
  const issues: string[] = [];
  const trace = getSection(wikiText, "Evidence Trace");
  const whatTheySaidCount = bullets(getSection(wikiText, "What They Said")).length;
  const entries = traceEntries(trace);
  const lineRefRegex = /research\/raw\/[^`\s)]+:\d+/g;
  const lineRefs = trace.match(lineRefRegex) || [];

  if (!trace) issues.push("Evidence Trace section is required.");
  if (entries.length < whatTheySaidCount) {
    issues.push(`Evidence Trace needs at least one trace entry per What They Said bullet (${entries.length}/${whatTheySaidCount}).`);
  }
  if (entries.some((line) => !line.includes("Evidence:") || !line.includes("Source:"))) {
    issues.push("Each Evidence Trace entry must include Claim, Evidence, and Source.");
  }
  if (lineRefs.length < entries.length) {
    issues.push("Every Evidence Trace entry should cite a research/raw line reference.");
  }
  return score(issues);
}

function auditReadability(wikiText: string) {
  const issues: string[] = [];
  const text = wikiText.trim();
  if (text.length < 1200) issues.push("Source note is too short to be a useful maintained note.");
  if (text.split("\n").some((line) => line.length > 320)) {
    issues.push("Source note has lines over 320 chars; wrap long claims for readability.");
  }
  if (!/^#\s+\S/m.test(text)) issues.push("Source note must start with a title.");
  if (bullets(getSection(wikiText, "Follow-Up Questions")).length < 1) {
    issues.push("Follow-Up Questions must contain at least one concrete question.");
  }
  return score(issues);
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (!opts) return;
  const wikiPath = resolve(opts.wikiPath);
  if (!existsSync(wikiPath)) throw new Error(`Wiki path not found: ${opts.wikiPath}`);
  const wikiText = read(wikiPath);

  const factors = {
    raw_preservation: auditRawPreservation(wikiPath, wikiText),
    maintained_source_note: auditMaintainedSourceNote(wikiText),
    compounding: auditCompounding(wikiPath, wikiText),
    auditability: auditAuditability(wikiText),
    readability: auditReadability(wikiText),
  };

  const result = { wiki: relative(repoRoot, wikiPath), factors };
  if (opts.json) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    console.log(`Audit: ${result.wiki}`);
    for (const [name, factor] of Object.entries(factors)) {
      console.log(`- ${name}: ${factor.score}/10`);
      for (const issue of factor.issues) console.log(`  - ${issue}`);
    }
  }

  const failed = Object.values(factors).some((factor) => factor.score < opts.failUnder);
  if (failed) process.exit(1);
}

main();
