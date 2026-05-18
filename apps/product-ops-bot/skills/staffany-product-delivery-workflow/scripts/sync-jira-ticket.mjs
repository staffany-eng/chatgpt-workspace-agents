#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { loadLocalEnvFile } from "./load-env.mjs";

const VALID_MODES = new Set(["description", "comment", "both"]);
const IMPACT_VALUES = new Set(["3", "2", "1", "0.5", "0.25"]);
const NEED_PRODUCT_REVIEW_FIELD = process.env.JIRA_FIELD_NEED_PRODUCT_REVIEW || "customfield_10843";
const RICE_FIELD_REACH = process.env.JIRA_FIELD_REACH || "";
const RICE_FIELD_IMPACT = process.env.JIRA_FIELD_IMPACT || "";
const RICE_FIELD_CONFIDENCE = process.env.JIRA_FIELD_CONFIDENCE || "";
const RICE_FIELD_EFFORT = process.env.JIRA_FIELD_EFFORT || "";
const RICE_FIELD_RATIONALE = process.env.JIRA_FIELD_RICE_RATIONALE || "";

function printUsage() {
  console.log(`Usage:
  node <skill-dir>/scripts/sync-jira-ticket.mjs --issue <ISSUE_KEY> --file <MARKDOWN_PATH> [options]

Required:
  --issue <ISSUE_KEY|URL>          Jira key (SCHE-1234) or browse URL
  --file <MARKDOWN_PATH>           Path to groomed markdown file

Options:
  --mode <MODE>                    description | comment | both (default: description)
  --update-summary                 Also set Jira summary from markdown H1 title
  --set-need-product-review <0|1>  Set Need Product Review field (customfield_10843)
  --skip-rice-check                Skip mandatory RICE validation before sync
  --dry-run                        Print payload preview only, do not call Jira API
  -h, --help                       Show this help message

Environment variables:
  JIRA_BASE_URL                    Example: https://staffany.atlassian.net
  JIRA_EMAIL                       Atlassian account email
  JIRA_API_TOKEN                   Atlassian API token
  JIRA_FIELD_NEED_PRODUCT_REVIEW   Jira field id (default: customfield_10843)
  JIRA_FIELD_REACH                 Optional Jira field id for Reach
  JIRA_FIELD_IMPACT                Optional Jira field id for Impact
  JIRA_FIELD_CONFIDENCE            Optional Jira field id for Confidence
  JIRA_FIELD_EFFORT                Optional Jira field id for Effort
  JIRA_FIELD_RICE_RATIONALE        Optional Jira field id for short RICE rationale text

Notes:
  Auto-loads local .env from current working directory, skill directory, or detected repo root.
`);
}

function parseArgs(argv) {
  const parsed = {
    issue: "",
    filePath: "",
    mode: "description",
    updateSummary: false,
    setNeedProductReview: null,
    skipRiceCheck: false,
    dryRun: false,
    help: false,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "-h" || arg === "--help") {
      parsed.help = true;
      continue;
    }
    if (arg === "--update-summary") {
      parsed.updateSummary = true;
      continue;
    }
    if (arg === "--skip-rice-check") {
      parsed.skipRiceCheck = true;
      continue;
    }
    if (arg === "--dry-run") {
      parsed.dryRun = true;
      continue;
    }
    if (arg === "--issue") {
      parsed.issue = argv[i + 1] ?? "";
      i += 1;
      continue;
    }
    if (arg === "--file") {
      parsed.filePath = argv[i + 1] ?? "";
      i += 1;
      continue;
    }
    if (arg === "--mode") {
      parsed.mode = argv[i + 1] ?? "";
      i += 1;
      continue;
    }
    if (arg === "--set-need-product-review") {
      parsed.setNeedProductReview = argv[i + 1] ?? "";
      i += 1;
    }
  }

  return parsed;
}

function fail(message) {
  console.error(`Error: ${message}`);
  process.exit(1);
}

function parseMarkdownTitle(markdown) {
  const firstHeading = markdown.match(/^#\s+(.+)$/m);
  return firstHeading?.[1]?.trim() ?? "";
}

function collectRiceFactorValues(markdown) {
  const rowPattern = /^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|/gmu;
  const factorValues = new Map();
  for (const match of markdown.matchAll(rowPattern)) {
    const factor = (match[1] ?? "").trim().toLowerCase();
    const value = normalizeValue(match[2] ?? "");
    if (factor) {
      factorValues.set(factor, value);
    }
  }
  return factorValues;
}

function normalizeValue(raw) {
  return raw.trim().replace(/`/gu, "");
}

function isPlaceholder(value) {
  if (!value) return true;
  if (/^<[^>]+>$/u.test(value)) return true;
  if (/^tbd$/iu.test(value)) return true;
  if (/^n\/?a$/iu.test(value)) return true;
  return false;
}

function parseNumber(value) {
  const normalized = value.replace(/,/gu, "").trim();
  if (!normalized) return null;
  const number = Number(normalized);
  return Number.isFinite(number) ? number : null;
}

function parsePercent(value) {
  const normalized = value.replace(/%/gu, "").replace(/,/gu, "").trim();
  if (!normalized) return null;
  const number = Number(normalized);
  return Number.isFinite(number) ? number : null;
}

function validateMandatoryRice(markdown) {
  const errors = [];
  const hasRiceHeading = /##\s+RICE Assessment\b/im.test(markdown);
  const factorValues = collectRiceFactorValues(markdown);

  if (!hasRiceHeading && factorValues.size === 0) {
    errors.push("Missing RICE section or factor rows.");
  }

  const requiredFactors = ["reach", "impact", "confidence", "effort", "rice score"];
  for (const factor of requiredFactors) {
    const value = factorValues.get(factor) ?? "";
    if (!value) {
      errors.push(`Missing RICE factor row: ${factor}.`);
      continue;
    }
    if (isPlaceholder(value)) {
      errors.push(`RICE factor '${factor}' has placeholder/empty value: ${value}`);
    }
  }

  const impact = factorValues.get("impact");
  if (impact && !isPlaceholder(impact) && !IMPACT_VALUES.has(impact)) {
    errors.push("Impact must be one of: 3, 2, 1, 0.5, 0.25.");
  }

  const confidence = factorValues.get("confidence");
  if (confidence && !isPlaceholder(confidence)) {
    const confidenceValue = parsePercent(confidence);
    if (confidenceValue === null || confidenceValue < 0 || confidenceValue > 100) {
      errors.push("Confidence must be a number between 0 and 100 (percent allowed). ");
    }
  }

  const reach = factorValues.get("reach");
  if (reach && !isPlaceholder(reach)) {
    const reachValue = parseNumber(reach);
    if (reachValue === null || reachValue <= 0) {
      errors.push("Reach must be a positive number.");
    }
  }

  const effort = factorValues.get("effort");
  if (effort && !isPlaceholder(effort)) {
    const effortValue = parseNumber(effort);
    if (effortValue === null || effortValue <= 0) {
      errors.push("Effort must be a positive number (person-months).");
    }
  }

  const riceScore = factorValues.get("rice score");
  if (riceScore && !isPlaceholder(riceScore)) {
    const riceScoreValue = parseNumber(riceScore);
    if (riceScoreValue === null || riceScoreValue <= 0) {
      errors.push("RICE Score must be a positive number.");
    }
  }

  if (errors.length > 0) {
    throw new Error(
      `RICE validation failed:\n- ${errors.join("\n- ")}\n` +
        "Add valid values to the mandatory RICE section, or pass --skip-rice-check intentionally.",
    );
  }
}

function extractRiceFactors(markdown) {
  const factorValues = collectRiceFactorValues(markdown);
  const reach = factorValues.get("reach") ?? "";
  const impact = factorValues.get("impact") ?? "";
  const confidence = factorValues.get("confidence") ?? "";
  const effort = factorValues.get("effort") ?? "";
  const score = factorValues.get("rice score") ?? "";
  const rationale = `RICE ${score}: Reach ${reach}, Impact ${impact}, Confidence ${confidence}, Effort ${effort}`.slice(
    0,
    255,
  );
  return { reach, impact, confidence, effort, score, rationale };
}

function normalizeBaseUrl(raw) {
  return raw.replace(/\/+$/, "");
}

function normalizeIssueInput(value) {
  const trimmed = value.trim();
  const fromUrl = trimmed.match(/\/browse\/([A-Za-z][A-Za-z0-9]+-\d+)(?:[/?#].*)?$/);
  const issueKey = fromUrl ? fromUrl[1] : trimmed;
  return issueKey.toUpperCase();
}

function fallbackInlineContent() {
  return [{ type: "text", text: " " }];
}

function parseInlineMarkdown(text) {
  if (!text) {
    return fallbackInlineContent();
  }

  const pattern = /(\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_|`[^`]+`|\[[^\]]+\]\([^)]+\))/gu;
  const nodes = [];
  let cursor = 0;

  const pushText = (value, marks = []) => {
    if (!value) {
      return;
    }
    const node = { type: "text", text: value };
    if (marks.length > 0) {
      node.marks = marks;
    }
    nodes.push(node);
  };

  for (const match of text.matchAll(pattern)) {
    const index = match.index ?? 0;
    const token = match[0] ?? "";

    if (index > cursor) {
      pushText(text.slice(cursor, index));
    }

    if ((token.startsWith("**") && token.endsWith("**")) || (token.startsWith("__") && token.endsWith("__"))) {
      pushText(token.slice(2, -2), [{ type: "strong" }]);
    } else if ((token.startsWith("*") && token.endsWith("*")) || (token.startsWith("_") && token.endsWith("_"))) {
      pushText(token.slice(1, -1), [{ type: "em" }]);
    } else if (token.startsWith("`") && token.endsWith("`")) {
      pushText(token.slice(1, -1), [{ type: "code" }]);
    } else if (token.startsWith("[")) {
      const linkMatch = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/u);
      if (linkMatch) {
        pushText(linkMatch[1], [{ type: "link", attrs: { href: linkMatch[2] } }]);
      } else {
        pushText(token);
      }
    } else {
      pushText(token);
    }

    cursor = index + token.length;
  }

  if (cursor < text.length) {
    pushText(text.slice(cursor));
  }

  return nodes.length > 0 ? nodes : fallbackInlineContent();
}

function isMarkdownTableSeparator(line) {
  return /^\s*\|?[\s:-]+(\|[\s:-]+)+\|?\s*$/u.test(line);
}

function parseMarkdownTableRow(line) {
  const trimmed = line.trim().replace(/^\|/u, "").replace(/\|$/u, "");
  return trimmed.split("|").map((cell) => cell.trim());
}

function buildAdfTable(headerRow, bodyRows) {
  const columnCount = Math.max(headerRow.length, ...bodyRows.map((row) => row.length), 1);
  const toCells = (cells, isHeader) => {
    const filled = [...cells];
    while (filled.length < columnCount) {
      filled.push("");
    }
    return filled.map((cell) => ({
      type: isHeader ? "tableHeader" : "tableCell",
      content: [{ type: "paragraph", content: parseInlineMarkdown(cell) }],
    }));
  };

  return {
    type: "table",
    attrs: { isNumberColumnEnabled: false, layout: "default" },
    content: [
      { type: "tableRow", content: toCells(headerRow, true) },
      ...bodyRows.map((row) => ({ type: "tableRow", content: toCells(row, false) })),
    ],
  };
}

function parseMarkdownToAdfBlocks(markdown) {
  const lines = markdown.split(/\r?\n/u);
  const blocks = [];
  let index = 0;

  const isTableStartAt = (lineIndex) =>
    lineIndex + 1 < lines.length && lines[lineIndex].includes("|") && isMarkdownTableSeparator(lines[lineIndex + 1]);

  const isBlockStart = (line, lineIndex) =>
    /^(#{1,6})\s+/.test(line) ||
    /^\s*[-*]\s+/.test(line) ||
    /^\s*\d+\.\s+/.test(line) ||
    /^>\s?/.test(line) ||
    /^```/.test(line) ||
    isTableStartAt(lineIndex);

  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();

    if (!trimmed) {
      index += 1;
      continue;
    }

    if (isTableStartAt(index)) {
      const headerRow = parseMarkdownTableRow(lines[index]);
      const bodyRows = [];
      index += 2;
      while (index < lines.length && lines[index].trim() && lines[index].includes("|")) {
        bodyRows.push(parseMarkdownTableRow(lines[index]));
        index += 1;
      }
      blocks.push(buildAdfTable(headerRow, bodyRows));
      continue;
    }

    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/u);
    if (headingMatch) {
      blocks.push({
        type: "heading",
        attrs: { level: headingMatch[1].length },
        content: parseInlineMarkdown(headingMatch[2].trim()),
      });
      index += 1;
      continue;
    }

    if (/^```/.test(trimmed)) {
      const fenceMatch = trimmed.match(/^```(\w+)?/u);
      const language = fenceMatch?.[1] || "markdown";
      const codeLines = [];
      index += 1;

      while (index < lines.length && !/^```/.test(lines[index].trim())) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) {
        index += 1;
      }

      blocks.push({
        type: "codeBlock",
        attrs: { language },
        content: [{ type: "text", text: codeLines.join("\n") }],
      });
      continue;
    }

    if (/^\s*[-*]\s+/.test(line)) {
      const items = [];
      while (index < lines.length && /^\s*[-*]\s+/.test(lines[index])) {
        const itemText = lines[index].replace(/^\s*[-*]\s+/u, "").trim();
        items.push({
          type: "listItem",
          content: [{ type: "paragraph", content: parseInlineMarkdown(itemText) }],
        });
        index += 1;
      }
      blocks.push({ type: "bulletList", content: items });
      continue;
    }

    if (/^\s*\d+\.\s+/.test(line)) {
      const items = [];
      while (index < lines.length && /^\s*\d+\.\s+/.test(lines[index])) {
        const itemText = lines[index].replace(/^\s*\d+\.\s+/u, "").trim();
        items.push({
          type: "listItem",
          content: [{ type: "paragraph", content: parseInlineMarkdown(itemText) }],
        });
        index += 1;
      }
      blocks.push({ type: "orderedList", content: items });
      continue;
    }

    if (/^>\s?/.test(line)) {
      const quoteLines = [];
      while (index < lines.length && /^>\s?/.test(lines[index])) {
        quoteLines.push(lines[index].replace(/^>\s?/u, ""));
        index += 1;
      }
      blocks.push({
        type: "blockquote",
        content: [{ type: "paragraph", content: parseInlineMarkdown(quoteLines.join(" ").trim()) }],
      });
      continue;
    }

    const paragraphLines = [];
    while (index < lines.length) {
      const candidate = lines[index];
      if (!candidate.trim()) {
        break;
      }
      if (isBlockStart(candidate, index)) {
        break;
      }
      paragraphLines.push(candidate.trim());
      index += 1;
    }

    if (paragraphLines.length === 0) {
      paragraphLines.push(line.trim());
      index += 1;
    }

    blocks.push({
      type: "paragraph",
      content: parseInlineMarkdown(paragraphLines.join(" ")),
    });
  }

  return blocks;
}

function buildDescriptionAdf({ markdown }) {
  const markdownBlocks = parseMarkdownToAdfBlocks(markdown);
  const content =
    markdownBlocks.length > 0
      ? markdownBlocks
      : [{ type: "paragraph", content: [{ type: "text", text: "(empty)" }] }];
  return {
    type: "doc",
    version: 1,
    content,
  };
}

function buildCommentAdf({ sourceFileName, syncedAt, markdown }) {
  const markdownBlocks = parseMarkdownToAdfBlocks(markdown);
  return {
    body: {
      type: "doc",
      version: 1,
      content: [
        {
          type: "paragraph",
          content: [
            {
              type: "text",
              text: `Synced grooming draft from ${sourceFileName} at ${syncedAt}.`,
            },
          ],
        },
        ...markdownBlocks,
      ],
    },
  };
}

async function jiraRequest({ method, url, authHeader, body }) {
  const response = await fetch(url, {
    method,
    headers: {
      Authorization: authHeader,
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`${method} ${url} failed (${response.status}): ${errorText}`);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

function parseNeedProductReviewInput(value) {
  if (value === null) {
    return null;
  }
  if (value === "0" || value === "1") {
    return value;
  }
  fail("Invalid --set-need-product-review value. Use 0 or 1.");
}

async function main() {
  loadLocalEnvFile();

  const args = parseArgs(process.argv.slice(2));

  if (args.help) {
    printUsage();
    return;
  }

  if (!args.issue) {
    fail("Missing required --issue argument.");
  }
  if (!args.filePath) {
    fail("Missing required --file argument.");
  }
  if (!VALID_MODES.has(args.mode)) {
    fail("Invalid --mode. Use description, comment, or both.");
  }

  const setNeedProductReview = parseNeedProductReviewInput(args.setNeedProductReview);

  if (!fs.existsSync(args.filePath)) {
    fail(`Markdown file not found: ${args.filePath}`);
  }

  const markdown = fs.readFileSync(args.filePath, "utf8");
  const markdownTitle = parseMarkdownTitle(markdown);
  const syncedAt = new Date().toISOString();
  const sourceFileName = path.basename(args.filePath);

  if (!args.skipRiceCheck) {
    validateMandatoryRice(markdown);
  }

  const issueKey = normalizeIssueInput(args.issue);

  if (!/^[A-Z][A-Z0-9]+-\d+$/.test(issueKey)) {
    fail("Invalid --issue value. Provide Jira key (SCHE-1234) or browse URL.");
  }

  const issueFields = {};
  const rice = extractRiceFactors(markdown);

  if (args.mode === "description" || args.mode === "both") {
    issueFields.description = buildDescriptionAdf({ markdown });
  }

  if (args.updateSummary && markdownTitle) {
    issueFields.summary = markdownTitle;
  }

  if (setNeedProductReview !== null) {
    issueFields[NEED_PRODUCT_REVIEW_FIELD] = setNeedProductReview === "1" ? 1 : null;
  }

  // Optional Jira custom-field mapping for RICE components.
  // Values are applied only when field ids are configured.
  if (RICE_FIELD_REACH && rice.reach && !isPlaceholder(rice.reach)) {
    const parsed = parseNumber(rice.reach);
    issueFields[RICE_FIELD_REACH] = parsed ?? rice.reach;
  }
  if (RICE_FIELD_IMPACT && rice.impact && !isPlaceholder(rice.impact)) {
    const parsed = parseNumber(rice.impact);
    issueFields[RICE_FIELD_IMPACT] = parsed ?? rice.impact;
  }
  if (RICE_FIELD_CONFIDENCE && rice.confidence && !isPlaceholder(rice.confidence)) {
    const parsed = parsePercent(rice.confidence);
    issueFields[RICE_FIELD_CONFIDENCE] = parsed ?? rice.confidence;
  }
  if (RICE_FIELD_EFFORT && rice.effort && !isPlaceholder(rice.effort)) {
    const parsed = parseNumber(rice.effort);
    issueFields[RICE_FIELD_EFFORT] = parsed ?? rice.effort;
  }
  if (RICE_FIELD_RATIONALE && rice.rationale) {
    issueFields[RICE_FIELD_RATIONALE] = rice.rationale;
  }

  const issueUpdateBody = Object.keys(issueFields).length > 0 ? { fields: issueFields } : null;
  const commentBody = buildCommentAdf({ sourceFileName, syncedAt, markdown });

  if (args.dryRun) {
    const dryRunPreview = {
      issue: args.issue,
      resolvedIssueKey: issueKey,
      mode: args.mode,
      updateSummary: args.updateSummary,
      setNeedProductReview,
      riceFieldMapping: {
        reachField: RICE_FIELD_REACH || null,
        impactField: RICE_FIELD_IMPACT || null,
        confidenceField: RICE_FIELD_CONFIDENCE || null,
        effortField: RICE_FIELD_EFFORT || null,
        rationaleField: RICE_FIELD_RATIONALE || null,
      },
      riceValidation: args.skipRiceCheck ? "skipped" : "passed",
      requestBodies: {
        issueUpdate: issueUpdateBody,
        comment: commentBody,
      },
    };
    console.log(JSON.stringify(dryRunPreview, null, 2));
    return;
  }

  const baseUrl = process.env.JIRA_BASE_URL ?? "";
  const jiraEmail = process.env.JIRA_EMAIL ?? "";
  const jiraApiToken = process.env.JIRA_API_TOKEN ?? "";

  if (!baseUrl) {
    fail("Missing env var JIRA_BASE_URL.");
  }
  if (!jiraEmail) {
    fail("Missing env var JIRA_EMAIL.");
  }
  if (!jiraApiToken) {
    fail("Missing env var JIRA_API_TOKEN.");
  }

  const normalizedBaseUrl = normalizeBaseUrl(baseUrl);
  const authHeader = `Basic ${Buffer.from(`${jiraEmail}:${jiraApiToken}`).toString("base64")}`;
  const issueUrl = `${normalizedBaseUrl}/rest/api/3/issue/${encodeURIComponent(issueKey)}`;
  const commentUrl = `${issueUrl}/comment`;

  if (issueUpdateBody) {
    await jiraRequest({
      method: "PUT",
      url: issueUrl,
      authHeader,
      body: issueUpdateBody,
    });

    if (args.mode === "description" || args.mode === "both") {
      console.log(`Updated description for ${issueKey}.`);
    }
    if (setNeedProductReview !== null) {
      console.log(
        `${setNeedProductReview === "1" ? "Checked" : "Unchecked"} Need Product Review for ${issueKey}.`,
      );
    }
  }

  if (args.mode === "comment" || args.mode === "both") {
    await jiraRequest({
      method: "POST",
      url: commentUrl,
      authHeader,
      body: commentBody,
    });
    console.log(`Added sync comment for ${issueKey}.`);
  }

  console.log(`Jira sync completed for ${issueKey} from ${args.filePath}.`);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
