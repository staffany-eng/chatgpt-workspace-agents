#!/usr/bin/env node

import { loadLocalEnvFile } from "./load-env.mjs";

const DEFAULT_MAX_COMMENTS = 10;
const VALID_FORMATS = new Set(["summary", "json"]);

function printUsage() {
  console.log(`Usage:
  node <skill-dir>/scripts/read-jira-ticket.mjs --issue <ISSUE_KEY|URL> [options]

Required:
  --issue <ISSUE_KEY|URL>  Jira key (SCHE-1234) or browse URL

Options:
  --format <FORMAT>        summary | json (default: summary)
  --include-links          Include linked issue summary (with IFI highlights)
  --include-comments       Include latest comments in output
  --max-comments <N>       Max comments to fetch (default: 10)
  --dry-run                Print request preview only, do not call Jira API
  -h, --help               Show this help message

Environment variables:
  JIRA_BASE_URL            Example: https://staffany.atlassian.net
  JIRA_EMAIL               Atlassian account email
  JIRA_API_TOKEN           Atlassian API token

Notes:
  Auto-loads local .env from current working directory, skill directory, or detected repo root.
`);
}

function fail(message) {
  console.error(`Error: ${message}`);
  process.exit(1);
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

function parseArgs(argv) {
  const parsed = {
    issue: "",
    format: "summary",
    includeLinks: false,
    includeComments: false,
    maxComments: DEFAULT_MAX_COMMENTS,
    dryRun: false,
    help: false,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "-h" || arg === "--help") {
      parsed.help = true;
      continue;
    }
    if (arg === "--include-links") {
      parsed.includeLinks = true;
      continue;
    }
    if (arg === "--include-comments") {
      parsed.includeComments = true;
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
    if (arg === "--format") {
      parsed.format = argv[i + 1] ?? "";
      i += 1;
      continue;
    }
    if (arg === "--max-comments") {
      parsed.maxComments = Number(argv[i + 1]);
      i += 1;
      continue;
    }
  }

  return parsed;
}

function extractPlainTextFromAdf(node) {
  if (!node || typeof node !== "object") {
    return "";
  }

  if (node.type === "text") {
    return typeof node.text === "string" ? node.text : "";
  }

  if (!Array.isArray(node.content)) {
    return "";
  }

  return node.content.map(extractPlainTextFromAdf).join("");
}

function adfToSimpleText(adf) {
  if (!adf || typeof adf !== "object") {
    return "";
  }
  if (!Array.isArray(adf.content)) {
    return "";
  }

  const blocks = adf.content
    .map((block) => {
      const text = extractPlainTextFromAdf(block);
      return text.trim();
    })
    .filter(Boolean);

  return blocks.join("\n\n");
}

function normalizeLinkedIssue(issue, direction, relationship) {
  return {
    key: issue?.key ?? "",
    direction,
    relationship,
    summary: issue?.fields?.summary ?? "",
    status: issue?.fields?.status?.name ?? "",
    issueType: issue?.fields?.issuetype?.name ?? "",
  };
}

function extractLinkedIssues(issue) {
  const issueLinks = issue?.fields?.issuelinks;
  if (!Array.isArray(issueLinks)) {
    return [];
  }

  const linked = [];
  for (const link of issueLinks) {
    const relationship = link?.type?.name ?? link?.type?.outward ?? link?.type?.inward ?? "linked";
    if (link?.outwardIssue) {
      linked.push(normalizeLinkedIssue(link.outwardIssue, "outward", relationship));
    }
    if (link?.inwardIssue) {
      linked.push(normalizeLinkedIssue(link.inwardIssue, "inward", relationship));
    }
  }
  return linked;
}

function deriveIfiJtbdSignals(linkedIssues) {
  const linkedIfi = linkedIssues.filter((item) => /^IFI-\d+$/u.test(item.key));
  const counts = new Map();

  for (const item of linkedIfi) {
    const normalizedSummary = item.summary.trim().toLowerCase().replace(/\s+/gu, " ");
    if (!normalizedSummary) {
      continue;
    }
    counts.set(normalizedSummary, (counts.get(normalizedSummary) ?? 0) + 1);
  }

  const recurring = [];
  for (const [summary, count] of counts.entries()) {
    if (count > 1) {
      recurring.push({ summary, occurrences: count });
    }
  }

  recurring.sort((a, b) => b.occurrences - a.occurrences);

  return {
    linkedIfiCount: linkedIfi.length,
    recurringJtbdCandidates: recurring,
  };
}

async function jiraRequest({ method, url, authHeader }) {
  const response = await fetch(url, {
    method,
    headers: {
      Authorization: authHeader,
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`${method} ${url} failed (${response.status}): ${errorText}`);
  }

  return response.json();
}

function printSummary({ issue, comments, linkedIssues, ifiSignals, includeLinks }) {
  const fields = issue.fields ?? {};
  const summary = fields.summary ?? "";
  const status = fields.status?.name ?? "";
  const assignee = fields.assignee?.displayName ?? "Unassigned";
  const reporter = fields.reporter?.displayName ?? "Unknown";
  const priority = fields.priority?.name ?? "Unknown";
  const issueType = fields.issuetype?.name ?? "Unknown";
  const description = adfToSimpleText(fields.description);

  console.log(`Issue: ${issue.key}`);
  console.log(`Summary: ${summary}`);
  console.log(`Status: ${status}`);
  console.log(`Type: ${issueType}`);
  console.log(`Priority: ${priority}`);
  console.log(`Assignee: ${assignee}`);
  console.log(`Reporter: ${reporter}`);
  console.log(`URL: ${issue.self?.replace("/rest/api/3/issue/" + issue.key, "/browse/" + issue.key) ?? ""}`);
  console.log("");
  console.log("Description:");
  console.log(description || "(empty)");

  if (includeLinks) {
    console.log("");
    console.log(`Linked Issues (${linkedIssues.length}):`);
    if (linkedIssues.length === 0) {
      console.log("(none)");
    }
    for (const linked of linkedIssues) {
      console.log(
        `- ${linked.key} [${linked.issueType || "Unknown"} | ${linked.status || "Unknown"} | ${linked.direction}] ${linked.summary}`,
      );
    }

    const recurring = ifiSignals?.recurringJtbdCandidates ?? [];
    console.log("");
    console.log(`Linked IFI Count: ${ifiSignals?.linkedIfiCount ?? 0}`);
    if (recurring.length > 0) {
      console.log("Recurring JTBD Candidates (heuristic from repeated IFI summaries):");
      for (const item of recurring) {
        console.log(`- ${item.occurrences}x ${item.summary}`);
      }
    }
  }

  if (comments.length > 0) {
    console.log("");
    console.log(`Latest Comments (${comments.length}):`);
    for (const comment of comments) {
      const bodyText = adfToSimpleText(comment.body);
      console.log("");
      console.log(`- ${comment.author?.displayName ?? "Unknown"} @ ${comment.updated ?? comment.created ?? ""}`);
      console.log(bodyText || "(empty)");
    }
  }
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

  const issueKey = normalizeIssueInput(args.issue);
  if (!/^[A-Z][A-Z0-9]+-\d+$/.test(issueKey)) {
    fail("Invalid --issue value. Provide Jira key (SCHE-1234) or browse URL.");
  }

  if (!VALID_FORMATS.has(args.format)) {
    fail("Invalid --format. Use summary or json.");
  }

  if (!Number.isInteger(args.maxComments) || args.maxComments < 1) {
    fail("Invalid --max-comments. Use an integer >= 1.");
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
  const issueUrl = `${normalizedBaseUrl}/rest/api/3/issue/${encodeURIComponent(issueKey)}?fields=summary,status,assignee,reporter,priority,issuetype,description,issuelinks`;
  const commentsUrl = `${normalizedBaseUrl}/rest/api/3/issue/${encodeURIComponent(issueKey)}/comment?orderBy=-created&maxResults=${args.maxComments}`;
  const authHeader = `Basic ${Buffer.from(`${jiraEmail}:${jiraApiToken}`).toString("base64")}`;

  if (args.dryRun) {
    console.log(
      JSON.stringify(
        {
          issue: args.issue,
          resolvedIssueKey: issueKey,
          requests: {
            issueUrl,
            includeLinks: args.includeLinks,
            commentsUrl: args.includeComments ? commentsUrl : null,
          },
        },
        null,
        2,
      ),
    );
    return;
  }

  const issue = await jiraRequest({
    method: "GET",
    url: issueUrl,
    authHeader,
  });

  const linkedIssues = args.includeLinks ? extractLinkedIssues(issue) : [];
  const ifiSignals = args.includeLinks ? deriveIfiJtbdSignals(linkedIssues) : { linkedIfiCount: 0, recurringJtbdCandidates: [] };

  let comments = [];
  if (args.includeComments) {
    const commentsResponse = await jiraRequest({
      method: "GET",
      url: commentsUrl,
      authHeader,
    });
    comments = Array.isArray(commentsResponse?.comments) ? commentsResponse.comments : [];
  }

  if (args.format === "json") {
    console.log(JSON.stringify({ issue, linkedIssues, ifiSignals, comments }, null, 2));
    return;
  }

  printSummary({ issue, comments, linkedIssues, ifiSignals, includeLinks: args.includeLinks });
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
