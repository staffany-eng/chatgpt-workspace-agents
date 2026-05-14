#!/usr/bin/env node
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { basename, dirname, extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const currentFile = fileURLToPath(import.meta.url);
const runtimeDir = dirname(currentFile);
const appRoot = resolve(runtimeDir, "..");
const repoRoot = resolve(appRoot, "..", "..");

export const DEFAULT_INTERCOM_API_BASE = "https://api.intercom.io";
export const DEFAULT_INTERCOM_VERSION = "2.14";
export const DEFAULT_PROFILE_PATH = join(
  appRoot,
  "skills",
  "help-article-generator",
  "references",
  "intercom-format-profile.json"
);
export const DEFAULT_CACHE_DIR = join(repoRoot, ".cache", "launch-superpower-bot", "intercom-format-corpus");
export const DEFAULT_PREVIEW_DIR = join(repoRoot, ".cache", "launch-superpower-bot", "format-check-previews");
export const DEFAULT_STAGED_UPDATE_DIR = join(repoRoot, ".cache", "launch-superpower-bot", "staged-updates");
export const DEFAULT_PANTHEON_REPO = "/Users/leekaiyi/workspace/pantheon";
export const DEFAULT_PANTHEON_EVIDENCE_DIR = join(repoRoot, ".cache", "launch-superpower-bot", "pantheon-evidence");
export const DEFAULT_INTERCOM_APP_ID = "y12ertqm";
export const DEFAULT_ARTICLE_SHAPE_PROFILE_PATH = join(
  appRoot,
  "skills",
  "help-article-generator",
  "references",
  "article-planning-profile.json"
);
export const DEFAULT_SHAPE_CACHE_DIR = join(repoRoot, ".cache", "launch-superpower-bot", "intercom-article-shape-corpus");
export const DEFAULT_ARTICLE_INVENTORY_PATH = join(
  appRoot,
  "skills",
  "help-article-generator",
  "references",
  "intercom-article-inventory.json"
);
export const DEFAULT_INVENTORY_CACHE_DIR = join(repoRoot, ".cache", "launch-superpower-bot", "intercom-article-inventory");

export const DEFAULT_ARTICLE_SHAPE_FAMILIES = [
  {
    id: "new_joiner_onboarding",
    label: "New Joiner / Onboarding",
    article_ids: ["14481424", "14460084", "14753121"],
    keywords: ["new joiner", "onboarding", "new hire", "form", "submit"],
    split_rule: "Split setup, onboarding review, and new-hire submission when HR and new hires perform different jobs.",
    default_mode: "mixed",
    planning_model: [
      {
        title_pattern: "Creating and Managing New Joiner Form",
        audience: ["Manager", "Owner"],
        platform: ["Web"],
        workflow: "form setup and management",
        create_or_update: "update_existing"
      },
      {
        title_pattern: "Onboarding New Hires",
        audience: ["Manager", "Owner"],
        platform: ["Web"],
        workflow: "onboarding review",
        create_or_update: "update_existing"
      },
      {
        title_pattern: "Submitting New Joiner Form",
        audience: ["Employee"],
        platform: ["Web", "Mobile"],
        workflow: "new hire form submission",
        create_or_update: "update_existing"
      }
    ]
  },
  {
    id: "company_documents",
    label: "Company Documents",
    article_ids: ["13722083", "13722074", "11755931", "14779347", "14318367"],
    keywords: ["company document", "documents", "acknowledgement", "document types", "templates", "signatures"],
    split_rule: "Split admin Web document management from employee Mobile acknowledgement/viewing.",
    default_mode: "mixed",
    planning_model: [
      {
        title_pattern: "Creating and Managing Company Documents",
        audience: ["Owner"],
        platform: ["Web"],
        workflow: "company document setup and publishing",
        create_or_update: "update_existing"
      },
      {
        title_pattern: "Acknowledging and Viewing Company Documents",
        audience: ["Employee", "Supervisor", "Manager", "Owner"],
        platform: ["Mobile"],
        workflow: "employee acknowledgement and viewing",
        create_or_update: "update_existing"
      }
    ]
  },
  {
    id: "clubany",
    label: "ClubAny",
    article_ids: ["14083228", "14083405"],
    keywords: ["clubany", "club blue", "brands", "perks", "redeem", "redemption"],
    split_rule: "Keep brand/perk management together for Web owners, and split Mobile redemption for staff.",
    default_mode: "mixed",
    planning_model: [
      {
        title_pattern: "Managing Brands and Perks on ClubAny",
        audience: ["Owner", "Manager"],
        platform: ["Web"],
        workflow: "brand and perk management",
        create_or_update: "update_existing"
      },
      {
        title_pattern: "Redeeming ClubAny Perks",
        audience: ["Employee", "Supervisor", "Manager", "Owner"],
        platform: ["Mobile"],
        workflow: "perk browsing and redemption",
        create_or_update: "update_existing"
      }
    ]
  },
  {
    id: "claims",
    label: "Claims",
    article_ids: ["9550497", "9550638", "9550707", "9550732", "9550576"],
    keywords: ["claims", "claim", "approval", "cut off", "payroll", "submission"],
    split_rule: "Split claim setup, employee submission, approval management, payroll processing, and cutoff behavior.",
    default_mode: "mixed",
    planning_model: [
      {
        title_pattern: "Creating and Managing Claims Types",
        audience: ["Owner"],
        platform: ["Web"],
        workflow: "claim type setup",
        create_or_update: "update_existing"
      },
      {
        title_pattern: "Submitting Claims on Mobile",
        audience: ["Employee", "Supervisor", "Manager", "Owner"],
        platform: ["Mobile"],
        workflow: "claim submission",
        create_or_update: "update_existing"
      },
      {
        title_pattern: "Managing Claim Submissions",
        audience: ["Owner", "Manager"],
        platform: ["Web"],
        workflow: "approval and export",
        create_or_update: "update_existing"
      },
      {
        title_pattern: "Managing Claims on Payroll",
        audience: ["Owner"],
        platform: ["Web"],
        workflow: "payroll processing",
        create_or_update: "update_existing"
      }
    ]
  },
  {
    id: "hireany",
    label: "HireAny",
    article_ids: ["10866862", "10900205", "11016372"],
    keywords: ["hireany", "casual", "provider", "vendor", "customer view", "worker view"],
    split_rule: "Split by marketplace side when customer, provider, and casual worker workflows differ.",
    default_mode: "mixed",
    planning_model: [
      {
        title_pattern: "HireAny (Beta) - Customer View",
        audience: ["Owner"],
        platform: ["Web"],
        workflow: "customer order management",
        create_or_update: "update_existing"
      },
      {
        title_pattern: "HireAny (Beta) - Vendor / Provider View",
        audience: ["Owner"],
        platform: ["Web"],
        workflow: "provider fulfilment",
        create_or_update: "update_existing"
      },
      {
        title_pattern: "HireAny (Beta) - Casual Worker View",
        audience: ["Employee"],
        platform: ["Mobile"],
        workflow: "casual worker setup and attendance",
        create_or_update: "update_existing"
      }
    ]
  },
  {
    id: "leave",
    label: "Leave",
    article_ids: ["14715267", "3589845", "3542111", "6015355"],
    keywords: ["leave", "leave calendar", "leave request", "approve leave"],
    split_rule: "Keep one combined article when the same manager workflow spans Web and Mobile; split approval/application flows when actor or platform changes.",
    default_mode: "update_existing",
    planning_model: [
      {
        title_pattern: "Managing Leave with Leave Calendar",
        audience: ["Owner", "Manager", "Supervisor"],
        platform: ["Web", "Mobile"],
        workflow: "leave calendar planning and approval",
        create_or_update: "update_existing"
      }
    ]
  },
  {
    id: "timesheet",
    label: "Timesheet",
    article_ids: ["4871108", "3458034", "7146545"],
    keywords: ["timesheet", "timesheet lock", "lock", "unlock", "recalculation"],
    split_rule: "Update the existing lifecycle article when behavior belongs to the same owner payroll-control workflow.",
    default_mode: "update_existing",
    planning_model: [
      {
        title_pattern: "Timesheet Lock",
        audience: ["Owner"],
        platform: ["Web"],
        workflow: "lock and unlock timesheets",
        create_or_update: "update_existing"
      }
    ]
  },
  {
    id: "payroll_payments",
    label: "Payroll / Payments",
    article_ids: ["13867429", "13867569", "9344548", "10090085", "8790142", "8898655"],
    keywords: ["payroll", "payment", "payments", "payslip", "bank file", "disbursement", "wallet", "iras"],
    split_rule: "Split by payroll operation when setup, disbursement, reports, statutory submission, and bank-file export have different workflows.",
    default_mode: "mixed",
    planning_model: [
      {
        title_pattern: "Create and Manage Disbursement",
        audience: ["Owner"],
        platform: ["Web"],
        workflow: "disbursement setup and management",
        create_or_update: "update_existing"
      },
      {
        title_pattern: "Top Up Disbursement Wallet Balance",
        audience: ["Owner"],
        platform: ["Web"],
        workflow: "wallet top-up",
        create_or_update: "update_existing"
      }
    ]
  },
  {
    id: "scheduling",
    label: "Scheduling",
    article_ids: ["15082227", "3180018", "5900189", "6014271"],
    keywords: ["schedule", "shift", "schedule import", "unscheduled shift"],
    split_rule: "Split manager Web scheduling from employee Mobile requests when the acting user and surface differ.",
    default_mode: "mixed",
    planning_model: [
      {
        title_pattern: "Web App: Schedule",
        audience: ["Owner", "Manager"],
        platform: ["Web"],
        workflow: "schedule management",
        create_or_update: "update_existing"
      },
      {
        title_pattern: "Schedule Import",
        audience: ["Owner", "Manager"],
        platform: ["Web"],
        workflow: "schedule import",
        create_or_update: "update_existing"
      }
    ]
  },
  {
    id: "permissions_access",
    label: "Permissions / Access",
    article_ids: ["4865824", "3728187"],
    keywords: ["permission", "permissions", "access", "access level", "user access", "role"],
    split_rule: "Prefer updating the canonical access article unless the change introduces a separate setup workflow.",
    default_mode: "update_existing",
    planning_model: [
      {
        title_pattern: "Permission Groups",
        audience: ["Owner", "Manager"],
        platform: ["Web"],
        workflow: "permission setup",
        create_or_update: "update_existing"
      }
    ]
  }
];

const PANTHEON_APPS = {
  gryphon: {
    root: "apps/gryphon",
    surface: "Web/admin",
    platform: "Web",
    evidenceRole: "web_admin_behavior"
  },
  pixie: {
    root: "apps/pixie",
    surface: "Mobile",
    platform: "Mobile",
    evidenceRole: "mobile_behavior"
  },
  kraken: {
    root: "apps/kraken",
    surface: "Backend/API/data",
    platform: "",
    evidenceRole: "backend_api_data_behavior"
  },
  manticore: {
    root: "apps/manticore",
    surface: "Analytics/reporting",
    platform: "",
    evidenceRole: "analytics_reporting_behavior"
  }
};

const STOPWORDS = new Set([
  "about",
  "after",
  "again",
  "article",
  "before",
  "being",
  "below",
  "between",
  "cannot",
  "center",
  "click",
  "contents",
  "draft",
  "enter",
  "every",
  "feature",
  "following",
  "guide",
  "helps",
  "intercom",
  "launchbot",
  "manage",
  "managing",
  "new",
  "opened",
  "owner",
  "owners",
  "review",
  "section",
  "select",
  "staffany",
  "status",
  "there",
  "these",
  "thing",
  "under",
  "users",
  "using",
  "where",
  "which",
  "while",
  "with",
  "without"
]);

const BLOCK_TAGS = [
  "h1",
  "h2",
  "h3",
  "h4",
  "p",
  "ol",
  "ul",
  "li",
  "strong",
  "b",
  "em",
  "a",
  "img",
  "table",
  "blockquote",
  "hr"
];

function assertString(value, name) {
  if (!value || typeof value !== "string") throw new Error(`${name} is required`);
  return value;
}

function cleanId(value) {
  return String(value || "").trim();
}

function envValue(names, env = process.env) {
  for (const name of Array.isArray(names) ? names : [names]) {
    const value = env[name];
    if (value) return value;
  }
  return "";
}

function csv(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function slugify(value) {
  return String(value || "pantheon-evidence")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80) || "pantheon-evidence";
}

function unique(values) {
  return [...new Set(values.filter(Boolean))];
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function topicTokens(value) {
  const tokens = String(value || "")
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .map((token) => token.trim())
    .filter((token) => token.length >= 3 && !STOPWORDS.has(token));
  const expanded = [];
  for (const token of tokens) {
    expanded.push(token);
    if (token.endsWith("s") && token.length > 4) expanded.push(token.slice(0, -1));
    if (!token.endsWith("s") && token.length > 3) expanded.push(`${token}s`);
  }
  return unique(expanded).slice(0, 20);
}

function runGit(repoPath, args, { allowFailure = false } = {}) {
  const result = spawnSync("git", ["-C", repoPath, ...args], {
    encoding: "utf8",
    maxBuffer: 10 * 1024 * 1024
  });
  if (result.status !== 0 && !allowFailure) {
    throw new Error((result.stderr || result.stdout || `git ${args.join(" ")} failed`).trim());
  }
  return result;
}

function safeRelativePath(path) {
  return String(path || "").replace(/^\/+/, "").replace(/\.\.(?:\/|$)/g, "");
}

function inferAppFromPath(path) {
  const normalized = safeRelativePath(path);
  return Object.entries(PANTHEON_APPS).find(([, config]) => normalized.startsWith(`${config.root}/`))?.[0] || "";
}

function parseRequestedApps(value) {
  const apps = csv(value);
  for (const app of apps) {
    if (!PANTHEON_APPS[app]) {
      throw new Error(`Unsupported Pantheon app: ${app}. Use one of: ${Object.keys(PANTHEON_APPS).join(", ")}`);
    }
  }
  return apps;
}

function parseArgs(argv) {
  const args = { _: [] };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith("--")) {
      args._.push(token);
      continue;
    }
    const raw = token.slice(2);
    const equalsIndex = raw.indexOf("=");
    if (equalsIndex >= 0) {
      args[raw.slice(0, equalsIndex)] = raw.slice(equalsIndex + 1);
      continue;
    }
    const next = argv[index + 1];
    if (!next || next.startsWith("--")) {
      args[raw] = true;
    } else {
      args[raw] = next;
      index += 1;
    }
  }
  return args;
}

function stripTags(html) {
  return String(html || "")
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, "")
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, "")
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/<[^>]+>/g, " ");
}

function decodeEntities(text) {
  return String(text || "")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/g, "'");
}

function visibleText(html) {
  return decodeEntities(stripTags(html))
    .replace(/\r/g, "")
    .replace(/[ \t]+/g, " ")
    .replace(/\n\s+/g, "\n")
    .trim();
}

function countMatches(text, pattern) {
  return [...String(text || "").matchAll(pattern)].length;
}

function extractHeadings(html) {
  return [...String(html || "").matchAll(/<h([1-6])\b[^>]*>([\s\S]*?)<\/h\1>/gi)].map((match) => ({
    level: Number(match[1]),
    text: visibleText(match[2])
  }));
}

function extractBlockSequence(html) {
  const pattern = new RegExp(`<\\/?(${BLOCK_TAGS.join("|")})\\b[^>]*>`, "gi");
  return [...String(html || "").matchAll(pattern)]
    .map((match) => match[1].toLowerCase())
    .filter((tag, index, sequence) => index === 0 || sequence[index - 1] !== tag);
}

function tagCounts(html) {
  const counts = {};
  for (const tag of BLOCK_TAGS) {
    counts[tag] = countMatches(html, new RegExp(`<${tag}\\b`, "gi"));
  }
  return counts;
}

function hasAudienceBlock(text) {
  return (
    /contents of this article are applicable to the following users/i.test(text) &&
    /\bProduct\s*:/i.test(text) &&
    /\bPlatform\s*:/i.test(text) &&
    /\bAccess Level\s*:/i.test(text)
  );
}

function hasFaq(text) {
  return /\bFAQ\b/i.test(text) && /\bQ\s*:/i.test(text);
}

function removeLeadingTitleHeading(html, title = "") {
  const normalizedTitle = title.trim().toLowerCase();
  if (!normalizedTitle) return html;
  return String(html || "").replace(/^\s*<h1\b[^>]*>([\s\S]*?)<\/h1>\s*/i, (match, headingText) => {
    return visibleText(headingText).trim().toLowerCase() === normalizedTitle ? "" : match;
  });
}

function detectForbiddenArtifacts({ html, title = "" }) {
  const text = visibleText(html);
  const lines = text.split("\n").map((line) => line.trim()).filter(Boolean);
  const normalizedTitle = title.trim().toLowerCase();
  const firstLine = (lines[0] || "").trim().toLowerCase();
  const firstBodyBlock = String(html || "").match(/^\s*<(p|h[2-6])\b[^>]*>([\s\S]*?)<\/\1>/i);
  const firstBodyBlockText = firstBodyBlock ? visibleText(firstBodyBlock[2]).trim().toLowerCase() : "";
  const errors = [];

  if (normalizedTitle && (firstLine === normalizedTitle || firstBodyBlockText === normalizedTitle)) {
    errors.push("repeated_title_in_body");
  }
  if (/```|~~~/.test(text) || /&lt;\/?(div|br|span|p|h[1-6]|ul|ol|li)\b/i.test(html)) {
    errors.push("raw_html_or_markdown_leakage");
  }
  if (lines.some((line) => /^(?:-{3,}|_{3,}|\*{3,})$/.test(line))) {
    errors.push("text_divider_lines");
  }
  if (/internal appendix|source of truth used|repository and branch|last verified commit|key file paths\/symbols/i.test(text)) {
    errors.push("internal_appendix");
  }
  if (!hasAudienceBlock(text)) {
    errors.push("missing_audience_metadata");
  }
  if (
    (/^\s*\d+\.\s+/m.test(text) && !/<ol\b/i.test(html)) ||
    /<p\b[^>]*>\s*\d+\.\s+[\s\S]*?<\/p>/i.test(html)
  ) {
    errors.push("bad_list_numbering");
  }

  return errors;
}

export function directIntercomArticleUrl(articleId, appId = DEFAULT_INTERCOM_APP_ID) {
  const id = cleanId(articleId);
  if (!id) return "";
  return `https://app.intercom.com/a/apps/${appId || DEFAULT_INTERCOM_APP_ID}/articles/articles/${id}/show`;
}

function pantheonRepoStatus(repoPath) {
  if (!existsSync(repoPath)) {
    return {
      exists: false,
      branch: "",
      sha: "",
      dirty: true,
      dirty_files: [],
      errors: ["missing_pantheon_repo"]
    };
  }
  try {
    const branch = runGit(repoPath, ["rev-parse", "--abbrev-ref", "HEAD"]).stdout.trim();
    const sha = runGit(repoPath, ["rev-parse", "HEAD"]).stdout.trim();
    const dirty = runGit(repoPath, ["status", "--porcelain"], { allowFailure: true }).stdout
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    return {
      exists: true,
      branch,
      sha,
      dirty: dirty.length > 0,
      dirty_files: dirty,
      errors: []
    };
  } catch (error) {
    return {
      exists: true,
      branch: "",
      sha: "",
      dirty: true,
      dirty_files: [],
      errors: [`pantheon_git_error:${error.message}`]
    };
  }
}

function readPantheonPathMatches(repoPath, relPath, tokens) {
  const absolutePath = join(repoPath, relPath);
  if (!existsSync(absolutePath)) return [];
  const content = readFileSync(absolutePath, "utf8");
  const lines = content.split(/\r?\n/);
  const matches = [];
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (tokens.length === 0 || tokens.some((token) => line.toLowerCase().includes(token))) {
      matches.push({ line: index + 1, text: line.trim().slice(0, 260) });
    }
    if (matches.length >= 6) break;
  }
  return matches;
}

function gitGrepPantheon(repoPath, roots, tokens) {
  if (tokens.length === 0) return [];
  const pattern = tokens.map(escapeRegExp).join("|");
  const result = runGit(
    repoPath,
    ["grep", "-n", "-I", "-i", "-m", "4", "-E", pattern, "--", ...roots],
    { allowFailure: true }
  );
  if (result.status !== 0 && result.status !== 1) {
    throw new Error((result.stderr || result.stdout || "Pantheon grep failed").trim());
  }
  if (!result.stdout.trim()) return [];
  return result.stdout
    .split("\n")
    .filter(Boolean)
    .slice(0, 240)
    .map((line) => {
      const firstColon = line.indexOf(":");
      const secondColon = line.indexOf(":", firstColon + 1);
      return {
        path: line.slice(0, firstColon),
        line: Number(line.slice(firstColon + 1, secondColon)),
        text: line.slice(secondColon + 1).trim().slice(0, 260)
      };
    });
}

function buildSourceFiles(matches) {
  const byPath = new Map();
  for (const match of matches) {
    if (!byPath.has(match.path)) {
      byPath.set(match.path, {
        path: match.path,
        app: inferAppFromPath(match.path),
        line_matches: []
      });
    }
    const item = byPath.get(match.path);
    if (item.line_matches.length < 6) {
      item.line_matches.push({ line: match.line, text: match.text });
    }
  }
  return [...byPath.values()]
    .filter((file) => file.app)
    .slice(0, 40);
}

function extractEvidenceDetails(sourceFiles) {
  const allMatches = sourceFiles.flatMap((file) =>
    file.line_matches.map((match) => ({
      ...match,
      path: file.path,
      app: file.app
    }))
  );
  const matchText = allMatches.map((match) => match.text).join("\n");
  const byPattern = (pattern) =>
    allMatches
      .filter((match) => pattern.test(`${match.path}\n${match.text}`))
      .slice(0, 20)
      .map((match) => ({ path: match.path, line: match.line, text: match.text }));
  const labels = unique([
    ...[...matchText.matchAll(/['"`]([^'"`]{3,80})['"`]/g)].map((match) => match[1]),
    ...[...matchText.matchAll(/\b([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){0,4})\b/g)].map((match) => match[1])
  ]).slice(0, 40);
  return {
    entry_points: byPattern(/route|routes|stack|screen|page|component|container|index\.(ts|tsx|js|jsx)|handler/i),
    routes_or_screens: byPattern(/route|routes|screen|stack|navigation|page|tab/i),
    api_data_touchpoints: byPattern(/api|endpoint|route|model|mutation|query|sequelize|table|dbt|ref\(/i),
    access_levels: byPattern(/owner|manager|supervisor|employee|permission|role|access|rbac|can[A-Z_]|authorized/i),
    flags_or_gating: byPattern(/flag|gate|enabled|isEnabled|feature.*toggle|launchdarkly|growthbook|config/i),
    statuses: byPattern(/active|inactive|draft|published|archiv|status|state|redeem/i),
    user_facing_labels: labels,
    edge_cases: byPattern(/error|empty|missing|cannot|disabled|hide|show|visible|not allowed|invalid/i)
  };
}

function evidenceTermIndex(topic, sourceFiles) {
  const text = [
    topic,
    ...sourceFiles.map((file) => file.path),
    ...sourceFiles.flatMap((file) => file.line_matches.map((match) => match.text))
  ].join("\n");
  return topicTokens(text).slice(0, 120);
}

export function scanPantheonEvidence({
  topic,
  app = "",
  paths = "",
  repoPath = process.env.LAUNCH_PANTHEON_REPO || DEFAULT_PANTHEON_REPO,
  conflict = "",
  generatedAt = new Date().toISOString()
} = {}) {
  assertString(topic, "topic");
  const absoluteRepoPath = resolve(repoPath);
  const requestedApps = parseRequestedApps(app);
  const requestedPaths = csv(paths).map(safeRelativePath);
  const conflictNotes = csv(conflict);
  const repo = pantheonRepoStatus(absoluteRepoPath);
  const errors = [...repo.errors];
  const warnings = [];
  let sourceFiles = [];

  if (repo.exists && errors.length === 0) {
    const tokens = topicTokens(topic);
    if (requestedPaths.length > 0) {
      const pathMatches = requestedPaths.flatMap((path) =>
        readPantheonPathMatches(absoluteRepoPath, path, tokens).map((match) => ({
          path,
          ...match
        }))
      );
      sourceFiles = buildSourceFiles(pathMatches);
      const missingPaths = requestedPaths.filter((path) => !existsSync(join(absoluteRepoPath, path)));
      for (const missingPath of missingPaths) errors.push(`missing_requested_pantheon_path:${missingPath}`);
    } else {
      const roots = (requestedApps.length > 0 ? requestedApps : Object.keys(PANTHEON_APPS))
        .map((appName) => PANTHEON_APPS[appName].root);
      sourceFiles = buildSourceFiles(gitGrepPantheon(absoluteRepoPath, roots, tokens));
    }
  }

  if (repo.dirty) errors.push("dirty_pantheon_repo");
  if (sourceFiles.length === 0 && repo.exists) errors.push("missing_pantheon_evidence");

  const matchedApps = unique(sourceFiles.map((file) => file.app));
  if (requestedApps.length > 0) {
    for (const requestedApp of requestedApps) {
      if (!matchedApps.includes(requestedApp)) errors.push(`missing_requested_app_evidence:${requestedApp}`);
    }
  } else if (requestedPaths.length === 0 && matchedApps.length > 1) {
    errors.push(`ambiguous_pantheon_app:${matchedApps.join(",")}`);
  }
  if (conflictNotes.length > 0) errors.push("pantheon_source_conflict");

  const appGuidance = matchedApps.map((appName) => {
    const guidancePath = join(PANTHEON_APPS[appName].root, "AGENTS.md");
    return {
      app: appName,
      path: guidancePath,
      exists: existsSync(join(absoluteRepoPath, guidancePath)),
      surface: PANTHEON_APPS[appName].surface,
      evidence_role: PANTHEON_APPS[appName].evidenceRole
    };
  });
  if (appGuidance.some((item) => !item.exists)) warnings.push("missing_app_agents_guidance");

  const evidence = extractEvidenceDetails(sourceFiles);
  const status = errors.length === 0 ? "pass" : "needs-check";
  return {
    status,
    evidence_status: status,
    topic,
    generated_at: generatedAt,
    source_strategy: "pantheon_local_checkout_read_only",
    auto_pull: false,
    repo: {
      path: absoluteRepoPath,
      exists: repo.exists,
      branch: repo.branch,
      sha: repo.sha,
      dirty: repo.dirty,
      dirty_files_count: repo.dirty_files.length,
      dirty_files: repo.dirty_files
    },
    requested_apps: requestedApps,
    requested_paths: requestedPaths,
    matched_apps: matchedApps,
    app_guidance: appGuidance,
    source_files: sourceFiles,
    evidence,
    verified_terms: evidenceTermIndex(topic, sourceFiles),
    conflicts: conflictNotes,
    errors: unique(errors),
    warnings: unique(warnings),
    approval_status: "not_requested"
  };
}

export class IntercomArticleClient {
  constructor({ token, apiBase = DEFAULT_INTERCOM_API_BASE, version = DEFAULT_INTERCOM_VERSION, fetchImpl = globalThis.fetch } = {}) {
    this.token = token;
    this.apiBase = apiBase.replace(/\/$/, "");
    this.version = version;
    this.fetchImpl = fetchImpl;
    if (!this.fetchImpl) throw new Error("A fetch implementation is required");
  }

  static fromEnv(env = process.env, options = {}) {
    const token = envValue(["LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN", "INTERCOM_ACCESS_TOKEN"], env);
    if (!token) throw new Error("Missing LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN or INTERCOM_ACCESS_TOKEN");
    return new IntercomArticleClient({ token, ...options });
  }

  async apiRequest(method, path, { query = {}, payload } = {}) {
    if (!this.token) throw new Error("Missing Intercom access token");
    const url = new URL(`${this.apiBase}${path}`);
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
    }
    const response = await this.fetchImpl(url, {
      method,
      headers: {
        Authorization: `Bearer ${this.token}`,
        Accept: "application/json",
        "Content-Type": "application/json",
        "Intercom-Version": this.version
      },
      body: payload ? JSON.stringify(payload) : undefined
    });
    if (!response.ok) {
      const body = typeof response.text === "function" ? await response.text() : "";
      throw new Error(`Intercom ${method} ${path} failed: ${response.status} ${body}`.trim());
    }
    return response.json();
  }

  async searchArticles({ phrase, state = "published", helpCenterId = "", highlight = true }) {
    assertString(phrase, "phrase");
    return this.apiRequest("GET", "/articles/search", {
      query: {
        phrase,
        state,
        help_center_id: helpCenterId,
        highlight: highlight ? "true" : "false"
      }
    });
  }

  async getArticle(articleId) {
    const id = assertString(cleanId(articleId), "articleId");
    return this.apiRequest("GET", `/articles/${encodeURIComponent(id)}`);
  }

  async listArticles({ perPage = 50, page = 1, state = "" } = {}) {
    return this.apiRequest("GET", "/articles", {
      query: {
        per_page: perPage,
        page,
        state
      }
    });
  }

  async createStagingDraft({ title, description = "Draft generated by Launchbot automation for review.", body, authorId, parentId, parentType = "collection" }) {
    assertString(title, "title");
    assertString(body, "body");
    if (!authorId) throw new Error("authorId is required for Intercom draft creation");
    if (!parentId) throw new Error("parentId is required for Intercom draft creation");
    return this.apiRequest("POST", "/articles", {
      payload: {
        title,
        description,
        body,
        author_id: Number(authorId),
        parent_id: Number(parentId),
        parent_type: parentType,
        state: "draft"
      }
    });
  }
}

export async function findAffectedArticles({ client, topic, helpCenterId = "", appId = DEFAULT_INTERCOM_APP_ID }) {
  assertString(topic, "topic");
  const published = await client.searchArticles({ phrase: topic, state: "published", helpCenterId, highlight: true });
  const publishedArticles = published?.data?.articles || [];
  const response = publishedArticles.length > 0
    ? { state_used: "published", response: published }
    : { state_used: "all", response: await client.searchArticles({ phrase: topic, state: "all", helpCenterId, highlight: true }) };
  const articles = response.response?.data?.articles || [];
  const highlights = response.response?.data?.highlights || [];
  return {
    topic,
    state_used: response.state_used,
    total_count: response.response?.total_count || articles.length,
    articles: articles.map((article, index) => {
      const title = article.title || "";
      const titleHit = title.toLowerCase().includes(topic.toLowerCase());
      return {
        id: article.id,
        title,
        url: article.url || "",
        state: article.state || "",
        updated_at: article.updated_at || null,
        direct_edit_url: directIntercomArticleUrl(article.id, appId),
        highlight: highlights[index] || null,
        confidence: titleHit ? "high" : highlights[index] ? "medium" : "low",
        approval_status: "not_requested"
      };
    })
  };
}

export function fingerprintArticle(article, { appId = DEFAULT_INTERCOM_APP_ID } = {}) {
  const body = article.body || "";
  const text = visibleText(body);
  const headings = extractHeadings(body);
  return {
    id: String(article.id || ""),
    title: article.title || "",
    url: article.url || "",
    state: article.state || "",
    updated_at: article.updated_at || null,
    direct_edit_url: directIntercomArticleUrl(article.id, appId),
    structure: {
      block_sequence: extractBlockSequence(body),
      tag_counts: tagCounts(body),
      headings,
      heading_levels: headings.map((heading) => heading.level),
      has_audience_block: hasAudienceBlock(text),
      has_faq: hasFaq(text),
      text_length: text.length
    }
  };
}

export function buildFormatProfile(articles, { appId = DEFAULT_INTERCOM_APP_ID, generatedAt = new Date().toISOString() } = {}) {
  const fingerprints = articles.map((article) => fingerprintArticle(article, { appId }));
  const aggregate = {
    reference_count: fingerprints.length,
    audience_block_count: fingerprints.filter((item) => item.structure.has_audience_block).length,
    faq_count: fingerprints.filter((item) => item.structure.has_faq).length,
    heading_level_counts: {},
    tag_counts: {}
  };
  for (const item of fingerprints) {
    for (const level of item.structure.heading_levels) {
      aggregate.heading_level_counts[level] = (aggregate.heading_level_counts[level] || 0) + 1;
    }
    for (const [tag, count] of Object.entries(item.structure.tag_counts)) {
      aggregate.tag_counts[tag] = (aggregate.tag_counts[tag] || 0) + count;
    }
  }
  return {
    version: 1,
    profile_status: fingerprints.length > 0 ? "live_intercom_profile" : "seeded_until_live_pull",
    generated_at: generatedAt,
    source_strategy: "hybrid_live_pull_then_normalized_profile",
    write_boundary: "read_stage_only",
    publish_mode: "draft_only",
    rules: defaultFormatRules(),
    aggregate,
    reference_articles: fingerprints
  };
}

export function defaultFormatRules() {
  return {
    language: "en",
    required_order: [
      "title",
      "audience_applicability_block",
      "intro",
      "guide_outline",
      "main_sections",
      "faq"
    ],
    required_audience_labels: ["Product", "Platform", "Access Level"],
    optional_audience_labels: ["Tier"],
    required_blocks: ["p", "strong", "ol", "ul", "h2"],
    allowed_blocks: BLOCK_TAGS,
    forbidden_artifacts: [
      "repeated_title_in_body",
      "raw_html_or_markdown_leakage",
      "text_divider_lines",
      "internal_appendix",
      "bad_list_numbering",
      "missing_audience_metadata"
    ],
    require_faq: true,
    require_outline_numbered_list: true,
    live_intercom_wins_on_conflict: true
  };
}

function hasGuideOutline(text) {
  return /this guide will cover how to|this article covers|in this article/i.test(String(text || ""));
}

function wordCount(text) {
  return (String(text || "").match(/\b[\w'-]+\b/g) || []).length;
}

function stableHash(value) {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

function metadataValue(text, label) {
  const pattern = new RegExp(`\\b${escapeRegExp(label)}\\s*:?\\s*(.+?)(?=\\b(?:Tier|Product|Platform|Access Level)\\s*:|$)`, "i");
  return String(text || "").match(pattern)?.[1]?.trim() || "";
}

function normalizePlatformValues(value) {
  const text = String(value || "").toLowerCase();
  const values = [];
  if (/\bweb\b|portal|admin/.test(text)) values.push("Web");
  if (/\bmobile\b|\bapp\b/.test(text)) values.push("Mobile");
  if (/\bapi\b/.test(text)) values.push("API");
  return unique(values);
}

function inferPlatformLabels(text) {
  return normalizePlatformValues(metadataValue(text, "Platform") || text);
}

function inferProductLabels(text) {
  const value = metadataValue(text, "Product");
  const raw = value || text;
  const products = ["StaffAny", "HRAny", "HireAny", "PayrollAny", "EngageAny"];
  return products.filter((product) => new RegExp(`\\b${escapeRegExp(product)}\\b`, "i").test(raw));
}

function inferAudienceLabels(text) {
  const value = metadataValue(text, "Access Level");
  const raw = value || text;
  const labels = [];
  if (/\bowner(s)?\b/i.test(raw)) labels.push("Owner");
  if (/\bmanager(s)?\b/i.test(raw)) labels.push("Manager");
  if (/\bsupervisor(s)?\b/i.test(raw)) labels.push("Supervisor");
  if (/\bemployee(s)?\b|\bstaff\b|\bnew hire\b|\bnew joiner\b|\bany\b/i.test(raw)) labels.push("Employee");
  if (/\bpayroll\b/i.test(raw)) labels.push("Payroll");
  if (/\bhr\b|\badmin\b/i.test(raw)) labels.push("HR/Admin");
  return unique(labels);
}

function inferWorkflowTags(text) {
  const source = String(text || "").toLowerCase();
  const tags = [];
  const patterns = [
    ["setup", /\b(set ?up|setting up|configure|configuration)\b/],
    ["create", /\b(create|creating|add|adding)\b/],
    ["manage", /\b(manage|managing|edit|editing|archive|unarchive|delete|download)\b/],
    ["submit", /\b(submit|submitting|submission)\b/],
    ["approve", /\b(approve|approving|reject|decline)\b/],
    ["view", /\b(view|viewing|browse|browsing)\b/],
    ["redeem", /\b(redeem|redeeming|redemption)\b/],
    ["publish", /\b(publish|publishing|unpublish)\b/],
    ["payroll", /\b(payroll|payrun|payslip|bank file|iras|disbursement|wallet)\b/],
    ["import_export", /\b(import|export|report|csv)\b/],
    ["onboarding", /\b(onboard|onboarding|new hire|new joiner)\b/],
    ["acknowledgement", /\b(acknowledge|acknowledgement|acknowledging)\b/],
    ["permissions", /\b(permission|access level|role|group)\b/],
    ["scheduling", /\b(schedule|shift|availability)\b/],
    ["leave", /\bleave\b/],
    ["claims", /\bclaim(s)?\b/],
    ["timesheet", /\btimesheet(s)?\b/]
  ];
  for (const [tag, pattern] of patterns) {
    if (pattern.test(source)) tags.push(tag);
  }
  return tags;
}

function familyById(profile, familyId) {
  return (profile.families || []).find((family) => family.id === familyId) || null;
}

function defaultFamilyById(familyId) {
  return DEFAULT_ARTICLE_SHAPE_FAMILIES.find((family) => family.id === familyId) || null;
}

function inferFamilyId(article) {
  const text = `${article.title || ""}\n${visibleText(article.body || "")}`.toLowerCase();
  let best = null;
  for (const family of DEFAULT_ARTICLE_SHAPE_FAMILIES) {
    const score = family.keywords.reduce((count, keyword) => (
      text.includes(keyword.toLowerCase()) ? count + 1 : count
    ), 0);
    if (score > 0 && (!best || score > best.score)) best = { family, score };
  }
  return best?.family.id || "uncategorized";
}

function inferFamilyScore(article, family) {
  const text = `${article.title || ""}\n${visibleText(article.body || "")}`.toLowerCase();
  return family.keywords.reduce((count, keyword) => (
    text.includes(keyword.toLowerCase()) ? count + 1 : count
  ), 0);
}

function classifyInventoryArticle(record, profile = null) {
  const title = String(record.title || "");
  const text = `${title}\n${record.description || ""}`.toLowerCase();
  const inShapeProfile = Boolean(profileArticleById(profile || {}, record.id));
  const looksWeak = (
    record.state !== "published" ||
    /\b(deprecated|archive|archived|old|legacy|test|draft|copy)\b/i.test(text) ||
    (record.content_signals?.word_count || 0) < 120
  );
  if (inShapeProfile && record.content_signals?.has_audience_block && record.content_signals?.word_count >= 50) {
    return "strong_reference";
  }
  if (looksWeak) return "deprecated_or_weak";
  if (record.inferred_family === "uncategorized") return "needs-human-review";
  return "affected_search_only";
}

export function buildInventoryRecord(article, { appId = DEFAULT_INTERCOM_APP_ID, profile = null } = {}) {
  const body = article.body || "";
  const text = visibleText(body);
  const headings = extractHeadings(body);
  const familyScores = DEFAULT_ARTICLE_SHAPE_FAMILIES
    .map((family) => ({ family: family.id, score: inferFamilyScore(article, family) }))
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score);
  const inferredFamily = familyScores[0]?.family || "uncategorized";
  const record = {
    id: String(article.id || ""),
    title: article.title || "",
    description: article.description || "",
    url: article.url || "",
    state: article.state || "",
    created_at: article.created_at || null,
    updated_at: article.updated_at || null,
    author_id: article.author_id || null,
    parent_id: article.parent_id || null,
    parent_type: article.parent_type || "",
    parent_ids: article.parent_ids || [],
    direct_edit_url: directIntercomArticleUrl(article.id, appId),
    inferred_family: inferredFamily,
    family_scores: familyScores.slice(0, 3),
    content_signals: {
      heading_texts: headings.map((heading) => heading.text).filter(Boolean).slice(0, 24),
      heading_levels: headings.map((heading) => heading.level),
      word_count: wordCount(text),
      has_audience_block: hasAudienceBlock(text),
      has_guide_outline: hasGuideOutline(text),
      has_faq: hasFaq(text),
      product_labels: inferProductLabels(text),
      platform_labels: inferPlatformLabels(text),
      audience_labels: inferAudienceLabels(text),
      workflow_tags: inferWorkflowTags(`${article.title || ""}\n${headings.map((heading) => heading.text).join("\n")}\n${text}`)
    }
  };
  return {
    ...record,
    quality_label: classifyInventoryArticle(record, profile)
  };
}

export function buildArticleInventory(
  articles,
  { appId = DEFAULT_INTERCOM_APP_ID, profile = null, generatedAt = new Date().toISOString() } = {}
) {
  const records = articles.map((article) => buildInventoryRecord(article, { appId, profile }));
  const familyCounts = {};
  const qualityCounts = {};
  const stateCounts = {};
  for (const record of records) {
    familyCounts[record.inferred_family] = (familyCounts[record.inferred_family] || 0) + 1;
    qualityCounts[record.quality_label] = (qualityCounts[record.quality_label] || 0) + 1;
    stateCounts[record.state || "unknown"] = (stateCounts[record.state || "unknown"] || 0) + 1;
  }
  return {
    version: 1,
    inventory_status: records.length > 0 ? "live_intercom_metadata_inventory" : "empty_inventory",
    generated_at: generatedAt,
    source_strategy: "all_article_metadata_with_derived_content_signals",
    write_boundary: "read_stage_only",
    publish_mode: "draft_only",
    raw_body_committed: false,
    raw_cache_dir: ".cache/launch-superpower-bot/intercom-article-inventory/",
    live_intercom_usage: ["inventory_refresh", "affected_article_search", "pre_stage_stale_check"],
    aggregate: {
      article_count: records.length,
      family_counts: familyCounts,
      quality_counts: qualityCounts,
      state_counts: stateCounts
    },
    articles: records
  };
}

export function buildArticleShapeRecord(article, { family = "", appId = DEFAULT_INTERCOM_APP_ID } = {}) {
  const body = article.body || "";
  const text = visibleText(body);
  const headings = extractHeadings(body);
  const blockSequence = extractBlockSequence(body);
  const counts = tagCounts(body);
  const normalizedStructure = {
    headings,
    heading_levels: headings.map((heading) => heading.level),
    block_sequence_sample: blockSequence.slice(0, 80),
    tag_counts: counts,
    has_audience_block: hasAudienceBlock(text),
    has_guide_outline: hasGuideOutline(text),
    has_faq: hasFaq(text),
    word_count: wordCount(text)
  };
  const fingerprintSource = {
    ...normalizedStructure,
    block_sequence: blockSequence
  };
  return {
    id: String(article.id || ""),
    title: article.title || "",
    url: article.url || "",
    state: article.state || "",
    updated_at: article.updated_at || null,
    direct_edit_url: directIntercomArticleUrl(article.id, appId),
    family: family || inferFamilyId(article),
    product_labels: inferProductLabels(text),
    platform_labels: inferPlatformLabels(text),
    audience_labels: inferAudienceLabels(text),
    workflow_tags: inferWorkflowTags(`${article.title || ""}\n${headings.map((heading) => heading.text).join("\n")}\n${text}`),
    structure: {
      ...normalizedStructure,
      structural_fingerprint: stableHash(fingerprintSource)
    }
  };
}

export function buildArticlePlanningProfile(
  familyArticles,
  { appId = DEFAULT_INTERCOM_APP_ID, generatedAt = new Date().toISOString() } = {}
) {
  const records = familyArticles.map((item) =>
    buildArticleShapeRecord(item.article || item, {
      family: item.family || "",
      appId
    })
  );
  const byFamily = new Map();
  for (const record of records) {
    if (!byFamily.has(record.family)) byFamily.set(record.family, []);
    byFamily.get(record.family).push(record);
  }
  const families = DEFAULT_ARTICLE_SHAPE_FAMILIES.map((family) => {
    const articleRecords = byFamily.get(family.id) || [];
    return {
      id: family.id,
      label: family.label,
      keywords: family.keywords,
      split_rule: family.split_rule,
      default_mode: family.default_mode,
      planning_model: family.planning_model,
      reference_article_ids: family.article_ids,
      reference_articles: articleRecords
    };
  });
  return {
    version: 1,
    profile_status: records.length > 0 ? "curated_intercom_shape_profile" : "seeded_until_shape_refresh",
    generated_at: generatedAt,
    source_strategy: "karpathy_style_ingest_cached_profile_with_targeted_live_checks",
    live_intercom_usage: ["shape_refresh", "affected_article_search", "pre_stage_stale_check"],
    write_boundary: "read_stage_only",
    publish_mode: "draft_only",
    rules: {
      planning_source_hierarchy: [
        "live_target_intercom_article",
        "pantheon_product_behavior",
        "cached_intercom_planning_synthesis",
        "slack_jira_prd_context"
      ],
      require_cached_profile_before_draft: true,
      stale_cached_article_blocks_staging: true,
      raw_html_committed: false,
      default_language: "en"
    },
    aggregate: {
      family_count: families.length,
      reference_article_count: records.length,
      audience_block_count: records.filter((record) => record.structure.has_audience_block).length,
      guide_outline_count: records.filter((record) => record.structure.has_guide_outline).length,
      faq_count: records.filter((record) => record.structure.has_faq).length
    },
    planning_rules: [
      "Split when audiences perform different jobs.",
      "Split when platform flows differ materially.",
      "Split marketplace or multi-sided workflows by actor view.",
      "Keep one article when one audience completes one connected lifecycle.",
      "Create or keep overview articles only when they coordinate related subflows.",
      "Prefer updating an existing same-audience same-platform article over creating duplicates.",
      "Use FAQ for LaunchBot-generated articles even when older articles are inconsistent."
    ],
    families
  };
}

function scoreFamilyForTopic(family, topic) {
  const tokens = topicTokens(topic);
  const text = [
    family.id,
    family.label,
    ...(family.keywords || []),
    family.split_rule || "",
    ...(family.reference_articles || []).map((article) => `${article.title} ${article.workflow_tags?.join(" ")}`)
  ].join("\n").toLowerCase();
  return tokens.reduce((score, token) => score + (text.includes(token.toLowerCase()) ? 1 : 0), 0);
}

function buildPlanningTopicText(topic, intake = {}) {
  return [
    topic,
    intake.surface,
    intake.audience,
    intake.outcome,
    intake.desired_outcome,
    intake.change,
    intake.release_state,
    intake.feature_flag
  ]
    .filter(Boolean)
    .join(" ");
}

function selectArticleFamilyForTopic(profile, topicText) {
  const scored = (profile.families || [])
    .map((family) => ({ family, score: scoreFamilyForTopic(family, topicText) }))
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score || left.family.label.localeCompare(right.family.label));
  const bestScore = scored[0]?.score || 0;
  const topFamilies = scored.filter((item) => item.score === bestScore).map((item) => item.family);
  const selectedFamily = topFamilies.length === 1 ? topFamilies[0] : null;
  return { scored, bestScore, topFamilies, selectedFamily };
}

function profileArticleById(profile, articleId) {
  const id = String(articleId || "");
  for (const family of profile.families || []) {
    const match = (family.reference_articles || []).find((article) => String(article.id) === id);
    if (match) return { family, article: match };
  }
  return null;
}

function inventoryArticleById(inventory, articleId) {
  const id = String(articleId || "");
  return (inventory?.articles || []).find((article) => String(article.id) === id) || null;
}

function scoreInventoryArticleForTopic(article, topic, selectedFamily = null) {
  const tokens = topicTokens(topic);
  const text = [
    article.id,
    article.title,
    article.description,
    article.inferred_family,
    ...(article.content_signals?.heading_texts || []),
    ...(article.content_signals?.workflow_tags || []),
    ...(article.content_signals?.product_labels || []),
    ...(article.content_signals?.platform_labels || []),
    ...(article.content_signals?.audience_labels || [])
  ].join("\n").toLowerCase();
  let score = tokens.reduce((sum, token) => sum + (text.includes(token.toLowerCase()) ? 1 : 0), 0);
  if (selectedFamily && article.inferred_family === selectedFamily.id) score += 2;
  if (article.quality_label === "deprecated_or_weak") score -= 2;
  return score;
}

function findInventoryAffectedArticles({ inventory, topic, selectedFamily = null, appId = DEFAULT_INTERCOM_APP_ID, queryText = "" }) {
  if (!inventory?.articles?.length) return null;
  const articles = inventory.articles
    .map((article) => ({ article, score: scoreInventoryArticleForTopic(article, queryText || topic, selectedFamily) }))
    .filter(({ article, score }) => score > 0 && article.state === "published")
    .sort((left, right) => right.score - left.score)
    .slice(0, 12)
    .map(({ article, score }) => ({
      id: article.id,
      title: article.title,
      url: article.url || "",
      state: article.state || "",
      updated_at: article.updated_at || null,
      direct_edit_url: article.direct_edit_url || directIntercomArticleUrl(article.id, appId),
      highlight: null,
      confidence: score >= 5 ? "high" : "medium",
      inventory_quality_label: article.quality_label,
      inferred_family: article.inferred_family,
      approval_status: "not_requested"
    }));
  return {
    topic,
    state_used: "inventory",
    total_count: articles.length,
    articles
  };
}

function matchedPlanningModelItems(family, affectedArticles = []) {
  const affectedByTitle = new Map(
    affectedArticles.map((article) => [String(article.title || "").toLowerCase(), article])
  );
  return (family.planning_model || []).map((item) => {
    const exactAffected = affectedByTitle.get(String(item.title_pattern || "").toLowerCase());
    const reference = (family.reference_articles || []).find((article) =>
      String(article.title || "").toLowerCase() === String(item.title_pattern || "").toLowerCase()
    );
    const target = exactAffected || reference || null;
    return {
      title: item.title_pattern,
      audience: item.audience || target?.audience_labels || [],
      platform: item.platform || target?.platform_labels || [],
      workflow: item.workflow,
      create_or_update: target ? "update_existing" : (item.create_or_update === "update_existing" ? "create_new" : item.create_or_update || "create_new"),
      source_article_id: target?.id || null,
      source_url: target?.url || "",
      direct_intercom_edit_url: target?.direct_edit_url || "",
      reference_article_ids: target?.id ? [String(target.id)] : family.reference_article_ids || [],
      rationale: family.split_rule,
      required_pantheon_evidence: inferRequiredPantheonEvidence(item.platform || target?.platform_labels || []),
      approval_status: "not_requested"
    };
  });
}

function inferRequiredPantheonEvidence(platforms) {
  const apps = new Set(["kraken"]);
  for (const platform of platforms || []) {
    if (/^web$/i.test(platform)) apps.add("gryphon");
    if (/^mobile$/i.test(platform)) apps.add("pixie");
  }
  return [...apps];
}

function normalizeProvidedValue(value) {
  return String(value || "").trim();
}

function normalizeSearchText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function inferSurfaceFromText(text) {
  const normalized = normalizeSearchText(text);
  const surfaces = [];
  if (/\b(web|admin|dashboard|portal|browser|owner app)\b/.test(normalized)) surfaces.push("Web");
  if (/\b(mobile|app|ios|android|phone|employee app)\b/.test(normalized)) surfaces.push("Mobile");
  if (/\b(api|backend|integration|webhook|data sync)\b/.test(normalized)) surfaces.push("API");
  if (/\b(payroll|payment|pay item|payslip|cpf|statutory)\b/.test(normalized)) surfaces.push("Payroll");
  return unique(surfaces);
}

function inferAudienceFromText(text) {
  const normalized = normalizeSearchText(text);
  const audiences = [];
  if (/\b(owner|business owner|admin owner)\b/.test(normalized)) audiences.push("Owner");
  if (/\b(manager|hr|admin|operator)\b/.test(normalized)) audiences.push("Manager");
  if (/\b(supervisor|shift lead|approver)\b/.test(normalized)) audiences.push("Supervisor");
  if (/\b(employee|staff|team member|worker)\b/.test(normalized)) audiences.push("Employee");
  if (/\b(payroll admin|payroll manager|finance)\b/.test(normalized)) audiences.push("Payroll admin");
  return unique(audiences);
}

function inferOutcomeFromText(text) {
  const normalized = normalizeSearchText(text);
  const workflowTags = inferWorkflowTags(text);
  const actionMatch = normalized.match(
    /\b(manage|set up|setup|create|update|approve|reject|submit|track|configure|sync|export|import|view|assign|claim|schedule)\b[\w\s-]{0,80}/
  );
  if (actionMatch) return actionMatch[0].trim();
  if (workflowTags.length > 0) return workflowTags.join(", ");
  return "";
}

function inferFromPlanningModel(family, field) {
  const items = family?.planning_model || [];
  if (field === "surface") return unique(items.flatMap((item) => item.platform || []));
  if (field === "audience") return unique(items.flatMap((item) => item.audience || []));
  if (field === "desired_outcome") {
    const workflows = unique(items.map((item) => item.workflow).filter(Boolean));
    return workflows.length > 0 ? workflows.join("; ") : "";
  }
  return [];
}

function highConfidenceInventoryMatches(inventory, topicText, selectedFamily) {
  if (!inventory?.articles?.length) return [];
  return inventory.articles
    .map((article) => ({ article, score: scoreInventoryArticleForTopic(article, topicText, selectedFamily) }))
    .filter(({ score, article }) => score >= 5 && article.state === "published")
    .sort((left, right) => right.score - left.score)
    .slice(0, 5)
    .map(({ article }) => article);
}

function inferFromInventoryMatches(matches, field) {
  if (field === "surface") {
    return unique(matches.flatMap((article) => article.content_signals?.platform_labels || []));
  }
  if (field === "audience") {
    return unique(matches.flatMap((article) => article.content_signals?.audience_labels || []));
  }
  if (field === "desired_outcome") {
    const workflows = unique(matches.flatMap((article) => article.content_signals?.workflow_tags || []));
    return workflows.length > 0 ? workflows.join(", ") : "";
  }
  return [];
}

function intakeQuestionForField(field, topFamilies = []) {
  if (field === "article_family" && topFamilies.length > 1) {
    return `I found multiple likely article families: ${topFamilies.map((family) => family.label).join(", ")}. Which workflow family should this plan follow?`;
  }
  if (field === "article_family") return "Which feature or workflow family should this help article plan follow?";
  if (field === "surface") return "Which product surface changed: Web, Mobile, API, Payroll, or something else?";
  if (field === "audience") return "Who is this article for: Owner, Manager, Supervisor, Employee, Payroll admin, or another role?";
  if (field === "desired_outcome") return "What should the reader be able to do after reading it?";
  return `Please provide ${field}.`;
}

export function evaluateHelpArticleIntake({ topic, intake = {}, profile, inventory = null, selectedFamily = null, topFamilies = [] }) {
  assertString(topic, "topic");
  const topicText = buildPlanningTopicText(topic, intake);
  const provided = {};
  const rawProvided = {
    surface: normalizeProvidedValue(intake.surface),
    audience: normalizeProvidedValue(intake.audience),
    desired_outcome: normalizeProvidedValue(intake.outcome || intake.desired_outcome),
    change: normalizeProvidedValue(intake.change),
    jira: normalizeProvidedValue(intake.jira),
    prd: normalizeProvidedValue(intake.prd),
    release_state: normalizeProvidedValue(intake.release_state),
    feature_flag: normalizeProvidedValue(intake.feature_flag),
    reviewer: normalizeProvidedValue(intake.reviewer),
    screenshot_owner: normalizeProvidedValue(intake.screenshot_owner)
  };
  for (const [key, value] of Object.entries(rawProvided)) {
    if (value) provided[key] = value;
  }

  const inventoryMatches = highConfidenceInventoryMatches(inventory, topicText, selectedFamily);
  const inferred = {};
  if (selectedFamily) {
    inferred.article_family = {
      id: selectedFamily.id,
      label: selectedFamily.label,
      source: "cached_planning_profile"
    };
  }

  const topicSurfaces = inferSurfaceFromText(topicText);
  const modelSurfaces = inferFromPlanningModel(selectedFamily, "surface");
  const inventorySurfaces = inferFromInventoryMatches(inventoryMatches, "surface");
  const inferredSurface = unique([...topicSurfaces, ...modelSurfaces, ...inventorySurfaces]);
  if (!provided.surface && inferredSurface.length > 0) inferred.surface = inferredSurface;

  const topicAudiences = inferAudienceFromText(topicText);
  const modelAudiences = inferFromPlanningModel(selectedFamily, "audience");
  const inventoryAudiences = inferFromInventoryMatches(inventoryMatches, "audience");
  const inferredAudience = unique([...topicAudiences, ...modelAudiences, ...inventoryAudiences]);
  if (!provided.audience && inferredAudience.length > 0) inferred.audience = inferredAudience;

  const topicOutcome = inferOutcomeFromText(topicText);
  const modelOutcome = inferFromPlanningModel(selectedFamily, "desired_outcome");
  const inventoryOutcome = inferFromInventoryMatches(inventoryMatches, "desired_outcome");
  const inferredOutcome = topicOutcome || modelOutcome || inventoryOutcome;
  if (!provided.desired_outcome && inferredOutcome) inferred.desired_outcome = inferredOutcome;

  const missingFields = [];
  if (!selectedFamily || topFamilies.length > 1) missingFields.push("article_family");
  if (!provided.surface && !inferred.surface?.length) missingFields.push("surface");
  if (!provided.audience && !inferred.audience?.length) missingFields.push("audience");
  if (!provided.desired_outcome && !inferred.desired_outcome) missingFields.push("desired_outcome");

  const questions = unique(missingFields.map((field) => intakeQuestionForField(field, topFamilies)));
  const explicitCoreCount = ["surface", "audience", "desired_outcome"].filter((field) => provided[field]).length;
  const confidence = missingFields.length > 0 ? "low" : explicitCoreCount >= 2 ? "high" : "medium";

  return {
    status: missingFields.length === 0 ? "pass" : "needs-intake",
    provided,
    inferred,
    missing_fields: missingFields,
    questions,
    confidence
  };
}

export function planHelpArticles({ topic, profile, inventory = null, affectedArticles = null, intake = {}, generatedAt = new Date().toISOString() }) {
  assertString(topic, "topic");
  if (!profile || typeof profile !== "object") throw new Error("Article planning profile is required");

  const topicText = buildPlanningTopicText(topic, intake);
  const { bestScore, topFamilies, selectedFamily } = selectArticleFamilyForTopic(profile, topicText);
  const intakeResult = evaluateHelpArticleIntake({
    topic,
    intake,
    profile,
    inventory,
    selectedFamily,
    topFamilies
  });

  if (intakeResult.status === "needs-intake") {
    return {
      status: "needs-intake",
      topic,
      generated_at: generatedAt,
      planning_profile_status: profile.profile_status || "",
      selected_family: selectedFamily ? {
        id: selectedFamily.id,
        label: selectedFamily.label,
        score: bestScore,
        split_rule: selectedFamily.split_rule
      } : null,
      intake: intakeResult,
      inventory_lookup: inventory ? {
        inventory_status: inventory.inventory_status || "",
        article_count: inventory.aggregate?.article_count || inventory.articles?.length || 0,
        used_for_affected_articles: false
      } : null,
      affected_article_search: null,
      recommended_articles: [],
      errors: [],
      warnings: [],
      do_not_draft_reason: "Answer the intake questions before planning or drafting.",
      approval_status: "not_requested"
    };
  }

  const inventoryAffectedArticles = inventory && !affectedArticles
    ? findInventoryAffectedArticles({ inventory, topic, selectedFamily, queryText: topicText })
    : null;
  const effectiveAffectedArticles = affectedArticles || inventoryAffectedArticles;
  const affected = effectiveAffectedArticles?.articles || [];
  const errors = [];
  const warnings = [];

  if (!selectedFamily) errors.push("topic_not_matched_to_cached_article_shape_profile");
  if (topFamilies.length > 1) warnings.push(`ambiguous_article_family:${topFamilies.map((family) => family.id).join(",")}`);
  if (effectiveAffectedArticles?.state_used === "all") warnings.push("affected_article_search_used_all_states");
  if (!effectiveAffectedArticles) warnings.push("affected_article_lookup_not_provided");
  if (inventory && !affectedArticles && inventoryAffectedArticles) warnings.push("affected_articles_from_cached_inventory");

  const confidentAffected = affected.filter((article) => {
    if (article.confidence === "high") return true;
    const profileMatch = profileArticleById(profile, article.id);
    return Boolean(selectedFamily && profileMatch?.family?.id === selectedFamily.id);
  });

  const recommendedMode = confidentAffected.length > 0
    ? (selectedFamily?.default_mode === "mixed" ? "mixed" : "update_existing")
    : selectedFamily?.default_mode || "create_new";
  const familyRecommendations = selectedFamily
    ? matchedPlanningModelItems(selectedFamily, confidentAffected)
    : [];
  const affectedRecommendations = confidentAffected
    .filter((article) => !familyRecommendations.some((item) => String(item.source_article_id) === String(article.id)))
    .map((article) => {
      const profileMatch = profileArticleById(profile, article.id);
      const inventoryMatch = inventoryArticleById(inventory, article.id);
      return {
        title: article.title,
        audience: profileMatch?.article?.audience_labels || inventoryMatch?.content_signals?.audience_labels || [],
        platform: profileMatch?.article?.platform_labels || inventoryMatch?.content_signals?.platform_labels || [],
        workflow: profileMatch?.article?.workflow_tags?.join(", ") || inventoryMatch?.content_signals?.workflow_tags?.join(", ") || "affected article update",
        create_or_update: "update_existing",
        source_article_id: article.id,
        source_url: article.url || "",
        direct_intercom_edit_url: article.direct_edit_url || "",
        reference_article_ids: profileMatch?.article?.id ? [profileMatch.article.id] : [],
        rationale: "Live Intercom search found an existing affected article.",
        required_pantheon_evidence: inferRequiredPantheonEvidence(profileMatch?.article?.platform_labels || inventoryMatch?.content_signals?.platform_labels || []),
        approval_status: "not_requested"
      };
    });

  return {
    status: errors.length === 0 ? "pass" : "needs-check",
    topic,
    generated_at: generatedAt,
    planning_profile_status: profile.profile_status || "",
    recommended_mode: recommendedMode,
    selected_family: selectedFamily ? {
      id: selectedFamily.id,
      label: selectedFamily.label,
      score: bestScore,
      split_rule: selectedFamily.split_rule
    } : null,
    intake: intakeResult,
    inventory_lookup: inventory ? {
      inventory_status: inventory.inventory_status || "",
      article_count: inventory.aggregate?.article_count || inventory.articles?.length || 0,
      used_for_affected_articles: Boolean(inventoryAffectedArticles && !affectedArticles)
    } : null,
    affected_article_search: effectiveAffectedArticles ? {
      state_used: effectiveAffectedArticles.state_used,
      total_count: effectiveAffectedArticles.total_count || affected.length,
      article_count: affected.length
    } : null,
    recommended_articles: [...familyRecommendations, ...affectedRecommendations],
    errors: unique(errors),
    warnings: unique(warnings),
    do_not_draft_reason: errors.length > 0 ? "Refresh or expand the article planning profile before drafting." : "",
    approval_status: "not_requested"
  };
}

export function checkArticleShapeFreshness({ liveArticle, profile }) {
  if (!liveArticle || typeof liveArticle !== "object") throw new Error("liveArticle is required");
  if (!profile || typeof profile !== "object") {
    return {
      status: "not_checked",
      warnings: ["missing_article_planning_profile"],
      errors: [],
      source_article_id: String(liveArticle.id || ""),
      cached_updated_at: null,
      live_updated_at: liveArticle.updated_at || null
    };
  }
  const cached = profileArticleById(profile, liveArticle.id);
  if (!cached) {
    return {
      status: "pass",
      warnings: ["target_article_not_in_cached_shape_profile"],
      errors: [],
      source_article_id: String(liveArticle.id || ""),
      cached_updated_at: null,
      live_updated_at: liveArticle.updated_at || null
    };
  }
  const liveRecord = buildArticleShapeRecord(liveArticle, {
    family: cached.family.id,
    appId: liveArticle.app_id || DEFAULT_INTERCOM_APP_ID
  });
  const errors = [];
  if (cached.article.updated_at !== liveRecord.updated_at) errors.push("cached_article_updated_at_stale");
  if (cached.article.structure?.structural_fingerprint !== liveRecord.structure?.structural_fingerprint) {
    errors.push("cached_article_shape_fingerprint_stale");
  }
  return {
    status: errors.length === 0 ? "pass" : "needs-refresh",
    warnings: [],
    errors,
    source_article_id: String(liveArticle.id || ""),
    family: cached.family.id,
    cached_updated_at: cached.article.updated_at || null,
    live_updated_at: liveRecord.updated_at || null,
    cached_structural_fingerprint: cached.article.structure?.structural_fingerprint || "",
    live_structural_fingerprint: liveRecord.structure?.structural_fingerprint || ""
  };
}

function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderInlineMarkdown(text) {
  return escapeHtml(text).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

export function markdownToIntercomHtml(markdown) {
  const lines = String(markdown || "").replace(/\r/g, "").split("\n");
  const html = [];
  let listType = "";

  function closeList() {
    if (listType) {
      html.push(`</${listType}>`);
      listType = "";
    }
  }

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      closeList();
      continue;
    }
    const heading = trimmed.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      closeList();
      const level = Math.min(heading[1].length, 4);
      html.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
      continue;
    }
    const ordered = trimmed.match(/^\d+\.\s+(.+)$/);
    if (ordered) {
      if (listType !== "ol") {
        closeList();
        html.push("<ol>");
        listType = "ol";
      }
      html.push(`<li>${renderInlineMarkdown(ordered[1])}</li>`);
      continue;
    }
    const unordered = trimmed.match(/^[-*]\s+(.+)$/);
    if (unordered) {
      if (listType !== "ul") {
        closeList();
        html.push("<ul>");
        listType = "ul";
      }
      html.push(`<li>${renderInlineMarkdown(unordered[1])}</li>`);
      continue;
    }
    closeList();
    html.push(`<p>${renderInlineMarkdown(trimmed)}</p>`);
  }
  closeList();
  return html.join("\n");
}

function isHtmlInput(text, path = "") {
  return extname(path).toLowerCase() === ".html" || /^\s*</.test(text);
}

function prepareDraftHtml(draft, { path = "", title = "" } = {}) {
  return removeLeadingTitleHeading(isHtmlInput(draft, path) ? draft : markdownToIntercomHtml(draft), title);
}

function jaccard(left, right) {
  const a = new Set(left);
  const b = new Set(right);
  const union = new Set([...a, ...b]);
  if (union.size === 0) return 0;
  let intersection = 0;
  for (const value of a) if (b.has(value)) intersection += 1;
  return intersection / union.size;
}

function closestReference(draftFingerprint, profile) {
  let best = null;
  for (const reference of profile.reference_articles || []) {
    const score = jaccard(
      draftFingerprint.structure.block_sequence,
      reference.structure?.block_sequence || []
    );
    if (!best || score > best.score) {
      best = {
        id: reference.id,
        title: reference.title,
        url: reference.url,
        direct_edit_url: reference.direct_edit_url,
        score: Number(score.toFixed(3))
      };
    }
  }
  return best;
}

export function checkDraftFormat({ draft, title = "", profile = buildFormatProfile([]), previewPath = "" }) {
  const html = prepareDraftHtml(draft, { title });
  const draftFingerprint = fingerprintArticle({ id: "draft", title: title || "draft", body: html });
  const errors = detectForbiddenArtifacts({ html, title });
  const text = visibleText(html);
  const warnings = [];

  if (profile.rules?.require_faq !== false && !hasFaq(text)) errors.push("missing_faq");
  if (profile.rules?.require_outline_numbered_list !== false && !/<ol\b/i.test(html)) {
    errors.push("missing_numbered_outline");
  }

  const unsupportedBlocks = Object.keys(draftFingerprint.structure.tag_counts)
    .filter((tag) => draftFingerprint.structure.tag_counts[tag] > 0)
    .filter((tag) => !(profile.rules?.allowed_blocks || BLOCK_TAGS).includes(tag));
  if (unsupportedBlocks.length > 0) warnings.push(`unsupported_blocks:${unsupportedBlocks.join(",")}`);

  if ((profile.reference_articles || []).length === 0) {
    warnings.push("format_profile_has_no_live_reference_articles");
  }

  return {
    status: errors.length === 0 ? "pass" : "fail",
    errors: [...new Set(errors)],
    warnings,
    closest_reference_article: closestReference(draftFingerprint, profile),
    rendered_preview_path: previewPath,
    draft_fingerprint: draftFingerprint,
    approval_status: "not_requested"
  };
}

function audiencePlatforms(text) {
  const platformLine = String(text || "").match(/\bPlatform\s*:\s*(.+?)(?=\b(?:Tier|Product|Access Level)\s*:|$)/i)?.[1] || "";
  return unique(platformLine.split(/[,/|]+/).map((item) => item.trim()).filter(Boolean));
}

function significantSentenceTokens(sentence) {
  return topicTokens(sentence)
    .filter((token) => !["applicable", "following", "platform", "product", "access", "level"].includes(token))
    .slice(0, 20);
}

function unsupportedClaimSentences(text, evidence) {
  const evidenceTerms = new Set((evidence?.verified_terms || []).map((term) => term.toLowerCase()));
  const claimPattern = /\b(can|cannot|can't|will|only|must|automatically|appears?|visible|hidden|archive|unarchive|redeem|publish|create|update|delete|manage|active|inactive)\b/i;
  return String(text || "")
    .split(/(?<=[.!?])\s+|\n+/)
    .map((sentence) => sentence.trim())
    .filter((sentence) => sentence.length > 35 && claimPattern.test(sentence))
    .filter((sentence) => {
      if (/contents of this article are applicable|this guide will cover how to|^q\s*:/i.test(sentence)) return false;
      const tokens = significantSentenceTokens(sentence);
      if (tokens.length < 2) return false;
      return !tokens.some((token) => evidenceTerms.has(token));
    })
    .slice(0, 8);
}

export function checkPantheonEvidence({ draft, title = "", evidence, evidencePath = "" }) {
  if (!evidence || typeof evidence !== "object") throw new Error("Pantheon evidence object is required");
  const html = prepareDraftHtml(draft, { title });
  const text = visibleText(html);
  const errors = [];
  const warnings = [];

  if (evidence.status !== "pass") {
    errors.push(`pantheon_evidence_${evidence.status || "missing"}`);
  }
  if (!evidence.repo?.exists) errors.push("missing_pantheon_repo");
  if (evidence.repo?.dirty) errors.push("dirty_pantheon_repo");
  if (!Array.isArray(evidence.source_files) || evidence.source_files.length === 0) {
    errors.push("missing_pantheon_evidence");
  }
  if ((evidence.conflicts || []).length > 0) errors.push("pantheon_source_conflict");
  if (/\b(gryphon|pixie|kraken|manticore)\b/i.test(text)) errors.push("internal_pantheon_app_name_leakage");

  const apps = new Set(evidence.matched_apps || []);
  for (const platform of audiencePlatforms(text)) {
    if (/^web$/i.test(platform) && !apps.has("gryphon")) errors.push("missing_web_pantheon_evidence");
    if (/^mobile$/i.test(platform) && !apps.has("pixie")) errors.push("missing_mobile_pantheon_evidence");
  }

  const unsupportedClaims = unsupportedClaimSentences(text, evidence);
  if (unsupportedClaims.length > 0) {
    errors.push("unsupported_product_behavior_claim");
  }

  if ((evidence.errors || []).some((item) => String(item).startsWith("ambiguous_pantheon_app"))) {
    warnings.push("pantheon_app_scope_needs_explicit_app_or_paths");
  }

  return {
    status: errors.length === 0 ? "pass" : "needs-check",
    errors: unique(errors),
    warnings: unique(warnings),
    unsupported_claims: unsupportedClaims,
    pantheon_evidence_path: evidencePath,
    pantheon_repo: evidence.repo || null,
    matched_apps: evidence.matched_apps || [],
    source_files: (evidence.source_files || []).map((file) => file.path),
    approval_status: "not_requested"
  };
}

export function stageArticleUpdate({
  sourceArticle,
  draft,
  title = "",
  description = "",
  profile = buildFormatProfile([]),
  pantheonEvidence = null,
  pantheonEvidenceGate = null,
  pantheonEvidencePath = "",
  articleShapeFreshness = null,
  appId = DEFAULT_INTERCOM_APP_ID,
  previewPath = ""
}) {
  const proposedTitle = title || sourceArticle.title || "";
  const proposedBody = prepareDraftHtml(draft, { title: proposedTitle });
  const formatGate = checkDraftFormat({
    draft: proposedBody,
    title: proposedTitle,
    profile,
    previewPath
  });
  const evidenceGate = pantheonEvidenceGate || (
    pantheonEvidence
      ? checkPantheonEvidence({
        draft: proposedBody,
        title: proposedTitle,
        evidence: pantheonEvidence,
        evidencePath: pantheonEvidencePath
      })
      : {
        status: "needs-check",
        errors: ["missing_pantheon_evidence"],
        warnings: [],
        unsupported_claims: [],
        pantheon_evidence_path: pantheonEvidencePath,
        pantheon_repo: null,
        matched_apps: [],
        source_files: [],
        approval_status: "not_requested"
      }
  );
  const shapeFreshness = articleShapeFreshness || {
    status: "not_checked",
    warnings: ["article_shape_stale_check_not_run"],
    errors: [],
    source_article_id: sourceArticle.id
  };
  const shapeFreshnessPass = ["pass", "not_checked"].includes(shapeFreshness.status);
  const combinedStatus = formatGate.status === "pass" && evidenceGate.status === "pass" && shapeFreshnessPass
    ? "pass"
    : "needs-check";
  return {
    status: combinedStatus,
    source_article_id: sourceArticle.id,
    source_url: sourceArticle.url || "",
    direct_intercom_edit_url: directIntercomArticleUrl(sourceArticle.id, appId),
    source_state: sourceArticle.state || "",
    source_updated_at: sourceArticle.updated_at || null,
    proposed_title: proposedTitle,
    proposed_description: description || sourceArticle.description || "",
    proposed_body: proposedBody,
    pantheon_evidence_path: pantheonEvidencePath,
    pantheon_evidence_result: evidenceGate,
    format_gate_result: formatGate,
    article_shape_stale_check: shapeFreshness,
    approval_status: "not_requested",
    writes_to_intercom: false
  };
}

function loadProfile(profilePath = DEFAULT_PROFILE_PATH) {
  return JSON.parse(readFileSync(profilePath, "utf8"));
}

function loadPlanningProfile(profilePath = DEFAULT_ARTICLE_SHAPE_PROFILE_PATH) {
  return JSON.parse(readFileSync(profilePath, "utf8"));
}

function loadInventory(inventoryPath = DEFAULT_ARTICLE_INVENTORY_PATH) {
  return JSON.parse(readFileSync(inventoryPath, "utf8"));
}

function loadEvidence(evidencePath) {
  return JSON.parse(readFileSync(evidencePath, "utf8"));
}

function ensureDir(path) {
  mkdirSync(path, { recursive: true });
}

function writeJson(path, value) {
  ensureDir(dirname(path));
  writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

async function commandAffected(args) {
  const topic = args.topic || args._.join(" ");
  const client = IntercomArticleClient.fromEnv(process.env);
  const result = await findAffectedArticles({
    client,
    topic,
    helpCenterId: args["help-center-id"] || envValue("LAUNCH_INTERCOM_HELP_CENTER_ID"),
    appId: args["app-id"] || envValue("LAUNCH_STEP3_INTERCOM_APP_ID") || DEFAULT_INTERCOM_APP_ID
  });
  return result;
}

async function commandPull(args) {
  const sampleIds = csv(args["sample-ids"] || envValue("LAUNCH_INTERCOM_FORMAT_SAMPLE_IDS"));
  if (sampleIds.length === 0) throw new Error("Provide --sample-ids or LAUNCH_INTERCOM_FORMAT_SAMPLE_IDS");
  const client = IntercomArticleClient.fromEnv(process.env);
  const cacheDir = resolve(args["cache-dir"] || DEFAULT_CACHE_DIR);
  const appId = args["app-id"] || envValue("LAUNCH_STEP3_INTERCOM_APP_ID") || DEFAULT_INTERCOM_APP_ID;
  ensureDir(cacheDir);
  const articles = [];
  for (const id of sampleIds) {
    const article = await client.getArticle(id);
    articles.push(article);
    writeJson(join(cacheDir, `${id}.json`), article);
    writeFileSync(join(cacheDir, `${id}.html`), article.body || "", "utf8");
  }
  const profile = buildFormatProfile(articles, { appId });
  const profileOut = resolve(args["profile-out"] || DEFAULT_PROFILE_PATH);
  writeJson(profileOut, profile);
  return {
    status: "ok",
    pulled_count: articles.length,
    cache_dir: cacheDir,
    profile_path: profileOut,
    publish_mode: "draft_only"
  };
}

async function commandProfile(args) {
  const cacheDir = resolve(args["cache-dir"] || DEFAULT_CACHE_DIR);
  if (!existsSync(cacheDir)) throw new Error(`Cache directory not found: ${cacheDir}`);
  const sampleIds = csv(args["sample-ids"] || envValue("LAUNCH_INTERCOM_FORMAT_SAMPLE_IDS"));
  const ids = sampleIds.length > 0
    ? sampleIds
    : [];
  if (ids.length === 0) throw new Error("Provide --sample-ids to build a profile from cached article JSON");
  const articles = ids.map((id) => JSON.parse(readFileSync(join(cacheDir, `${id}.json`), "utf8")));
  const profile = buildFormatProfile(articles, {
    appId: args["app-id"] || envValue("LAUNCH_STEP3_INTERCOM_APP_ID") || DEFAULT_INTERCOM_APP_ID
  });
  const profileOut = resolve(args["profile-out"] || DEFAULT_PROFILE_PATH);
  writeJson(profileOut, profile);
  return {
    status: "ok",
    reference_count: profile.reference_articles.length,
    profile_path: profileOut
  };
}

function selectedShapeFamilies(args) {
  const requested = csv(args.families || envValue("LAUNCH_INTERCOM_SHAPE_FAMILIES") || "");
  const families = requested.length > 0
    ? DEFAULT_ARTICLE_SHAPE_FAMILIES.filter((family) => requested.includes(family.id))
    : DEFAULT_ARTICLE_SHAPE_FAMILIES;
  if (requested.length > 0 && families.length !== requested.length) {
    const known = new Set(DEFAULT_ARTICLE_SHAPE_FAMILIES.map((family) => family.id));
    const missing = requested.filter((family) => !known.has(family));
    throw new Error(`Unknown article shape families: ${missing.join(",")}`);
  }
  return families;
}

async function commandShapeRefresh(args) {
  const client = IntercomArticleClient.fromEnv(process.env);
  const cacheDir = resolve(args["cache-dir"] || DEFAULT_SHAPE_CACHE_DIR);
  const appId = args["app-id"] || envValue("LAUNCH_STEP3_INTERCOM_APP_ID") || DEFAULT_INTERCOM_APP_ID;
  const families = selectedShapeFamilies(args);
  ensureDir(cacheDir);
  const familyArticles = [];
  const pulled = [];

  for (const family of families) {
    for (const id of family.article_ids) {
      const article = await client.getArticle(id);
      familyArticles.push({ family: family.id, article });
      pulled.push({ family: family.id, id: String(id), title: article.title || "", state: article.state || "" });
      writeJson(join(cacheDir, `${family.id}-${id}.json`), article);
      writeFileSync(join(cacheDir, `${family.id}-${id}.html`), article.body || "", "utf8");
    }
  }

  const profile = buildArticlePlanningProfile(familyArticles, { appId });
  const profileOut = resolve(args["profile-out"] || DEFAULT_ARTICLE_SHAPE_PROFILE_PATH);
  writeJson(profileOut, profile);
  return {
    status: "ok",
    pulled_count: pulled.length,
    family_count: families.length,
    pulled_articles: pulled,
    cache_dir: cacheDir,
    profile_path: profileOut,
    raw_html_committed: false,
    live_intercom_usage: profile.live_intercom_usage,
    publish_mode: "draft_only"
  };
}

async function commandInventory(args) {
  const client = IntercomArticleClient.fromEnv(process.env);
  const cacheDir = resolve(args["cache-dir"] || DEFAULT_INVENTORY_CACHE_DIR);
  const appId = args["app-id"] || envValue("LAUNCH_STEP3_INTERCOM_APP_ID") || DEFAULT_INTERCOM_APP_ID;
  const perPage = Number(args["per-page"] || 50);
  const state = args.state || envValue("LAUNCH_INTERCOM_INVENTORY_STATE") || "";
  const profilePath = resolve(args.profile || DEFAULT_ARTICLE_SHAPE_PROFILE_PATH);
  const profile = existsSync(profilePath) ? loadPlanningProfile(profilePath) : null;
  ensureDir(cacheDir);

  const articles = [];
  const pages = [];
  let page = Number(args.page || 1);
  let totalPages = 1;
  do {
    const response = await client.listArticles({ perPage, page, state });
    const pageArticles = Array.isArray(response.data) ? response.data : response.data?.articles || [];
    articles.push(...pageArticles);
    pages.push({ page, count: pageArticles.length });
    writeJson(join(cacheDir, `page-${String(page).padStart(4, "0")}.json`), response);
    for (const article of pageArticles) {
      const id = String(article.id || "");
      if (!id) continue;
      writeJson(join(cacheDir, `${id}.json`), article);
      writeFileSync(join(cacheDir, `${id}.html`), article.body || "", "utf8");
    }
    totalPages = Number(response.pages?.total_pages || page);
    page += 1;
  } while (page <= totalPages);

  const inventory = buildArticleInventory(articles, { appId, profile });
  const inventoryOut = resolve(args.out || args["inventory-out"] || DEFAULT_ARTICLE_INVENTORY_PATH);
  writeJson(inventoryOut, inventory);
  return {
    status: "ok",
    pulled_count: articles.length,
    page_count: pages.length,
    cache_dir: cacheDir,
    inventory_path: inventoryOut,
    raw_body_committed: false,
    aggregate: inventory.aggregate,
    publish_mode: "draft_only"
  };
}

function intakeFromPlanArgs(args) {
  return {
    surface: args.surface || "",
    audience: args.audience || "",
    outcome: args.outcome || args["desired-outcome"] || "",
    change: args.change || "",
    jira: args.jira || "",
    prd: args.prd || "",
    release_state: args["release-state"] || args.release_state || "",
    feature_flag: args["feature-flag"] || args.feature_flag || "",
    reviewer: args.reviewer || "",
    screenshot_owner: args["screenshot-owner"] || args.screenshot_owner || ""
  };
}

async function commandPlan(args) {
  const topic = args.topic || args._.join(" ");
  if (!topic) throw new Error("Provide --topic <topic>");
  const profile = loadPlanningProfile(resolve(args.profile || DEFAULT_ARTICLE_SHAPE_PROFILE_PATH));
  const inventoryPath = resolve(args.inventory || DEFAULT_ARTICLE_INVENTORY_PATH);
  const inventory = existsSync(inventoryPath) ? loadInventory(inventoryPath) : null;
  const intake = intakeFromPlanArgs(args);
  const preliminary = planHelpArticles({
    topic,
    profile,
    inventory,
    intake
  });
  if (preliminary.status === "needs-intake" || inventory || args.offline === true || args.offline === "true") {
    return preliminary;
  }
  let affectedArticles = null;
  const client = IntercomArticleClient.fromEnv(process.env);
  affectedArticles = await findAffectedArticles({
    client,
    topic: buildPlanningTopicText(topic, intake),
    helpCenterId: args["help-center-id"] || envValue("LAUNCH_INTERCOM_HELP_CENTER_ID"),
    appId: args["app-id"] || envValue("LAUNCH_STEP3_INTERCOM_APP_ID") || DEFAULT_INTERCOM_APP_ID
  });
  return planHelpArticles({
    topic,
    profile,
    inventory,
    affectedArticles,
    intake
  });
}

async function commandFormatCheck(args) {
  const draftPath = args.draft;
  if (!draftPath) throw new Error("Provide --draft <path>");
  const absoluteDraftPath = resolve(draftPath);
  const draft = readFileSync(absoluteDraftPath, "utf8");
  const profile = loadProfile(resolve(args.profile || DEFAULT_PROFILE_PATH));
  const previewDir = resolve(args["preview-dir"] || DEFAULT_PREVIEW_DIR);
  ensureDir(previewDir);
  const html = prepareDraftHtml(draft, { path: absoluteDraftPath, title: args.title || "" });
  const previewPath = join(previewDir, `${basename(absoluteDraftPath).replace(/\.[^.]+$/, "")}.intercom-preview.html`);
  writeFileSync(previewPath, html, "utf8");
  const result = checkDraftFormat({
    draft: html,
    title: args.title || "",
    profile,
    previewPath
  });
  return result;
}

async function commandPantheonScan(args) {
  const topic = args.topic || args._.join(" ");
  if (!topic) throw new Error("Provide --topic <topic>");
  const evidenceDir = resolve(args["evidence-dir"] || DEFAULT_PANTHEON_EVIDENCE_DIR);
  ensureDir(evidenceDir);
  const evidence = scanPantheonEvidence({
    topic,
    app: args.app || args.apps || "",
    paths: args.paths || "",
    repoPath: args.repo || envValue("LAUNCH_PANTHEON_REPO", process.env) || DEFAULT_PANTHEON_REPO,
    conflict: args.conflict || ""
  });
  const outPath = resolve(args.out || join(evidenceDir, `${slugify(topic)}.pantheon-evidence.json`));
  writeJson(outPath, evidence);
  return {
    ...evidence,
    pantheon_evidence_path: outPath
  };
}

async function commandEvidenceCheck(args) {
  const draftPath = args.draft;
  const evidencePath = args.evidence;
  if (!draftPath) throw new Error("Provide --draft <path>");
  if (!evidencePath) throw new Error("Provide --evidence <path>");
  const absoluteDraftPath = resolve(draftPath);
  const absoluteEvidencePath = resolve(evidencePath);
  const draft = readFileSync(absoluteDraftPath, "utf8");
  const evidence = loadEvidence(absoluteEvidencePath);
  return checkPantheonEvidence({
    draft,
    title: args.title || "",
    evidence,
    evidencePath: absoluteEvidencePath
  });
}

async function commandStageUpdate(args) {
  const articleId = args["article-id"];
  const draftPath = args.draft;
  const evidencePath = args.evidence;
  if (!articleId) throw new Error("Provide --article-id <id>");
  if (!draftPath) throw new Error("Provide --draft <path>");
  if (!evidencePath) throw new Error("Provide --evidence <path>");
  const client = IntercomArticleClient.fromEnv(process.env);
  const sourceArticle = await client.getArticle(articleId);
  const absoluteDraftPath = resolve(draftPath);
  const absoluteEvidencePath = resolve(evidencePath);
  const draft = readFileSync(absoluteDraftPath, "utf8");
  const pantheonEvidence = loadEvidence(absoluteEvidencePath);
  const profile = loadProfile(resolve(args.profile || DEFAULT_PROFILE_PATH));
  const planningProfilePath = resolve(args["planning-profile"] || DEFAULT_ARTICLE_SHAPE_PROFILE_PATH);
  const planningProfile = existsSync(planningProfilePath) ? loadPlanningProfile(planningProfilePath) : null;
  const articleShapeFreshness = checkArticleShapeFreshness({
    liveArticle: sourceArticle,
    profile: planningProfile
  });
  const stageDir = resolve(args["stage-dir"] || DEFAULT_STAGED_UPDATE_DIR);
  const previewDir = resolve(args["preview-dir"] || DEFAULT_PREVIEW_DIR);
  ensureDir(stageDir);
  ensureDir(previewDir);
  const proposedTitle = args.title || sourceArticle.title || "";
  const html = prepareDraftHtml(draft, { path: absoluteDraftPath, title: proposedTitle });
  const previewPath = join(previewDir, `${articleId}.intercom-preview.html`);
  writeFileSync(previewPath, html, "utf8");
  const staged = stageArticleUpdate({
    sourceArticle,
    draft: html,
    title: proposedTitle,
    description: args.description || "",
    profile,
    pantheonEvidence,
    pantheonEvidencePath: absoluteEvidencePath,
    articleShapeFreshness,
    appId: args["app-id"] || envValue("LAUNCH_STEP3_INTERCOM_APP_ID") || DEFAULT_INTERCOM_APP_ID,
    previewPath
  });
  const stagePath = resolve(args.out || join(stageDir, `${articleId}.staged-update.json`));
  writeJson(stagePath, staged);
  return {
    status: staged.format_gate_result.status,
    staged_update_path: stagePath,
    ...staged
  };
}

function usage() {
  return [
    "Usage:",
    "  intercom-format-gate.mjs intercom:affected --topic <topic>",
    "  intercom-format-gate.mjs intercom:format:pull --sample-ids <id,id>",
    "  intercom-format-gate.mjs intercom:format:profile --sample-ids <id,id>",
    "  intercom-format-gate.mjs intercom:inventory [--state <state>]",
    "  intercom-format-gate.mjs help-article:shape-refresh [--families <family,family>]",
    "  intercom-format-gate.mjs help-article:shape-ingest [--families <family,family>]",
    "  intercom-format-gate.mjs help-article:plan --topic <topic> [--surface <surface>] [--audience <audience>] [--outcome <outcome>]",
    "  intercom-format-gate.mjs help-article:format-check --draft <path> [--title <title>]",
    "  intercom-format-gate.mjs help-article:pantheon-scan --topic <topic> [--app <app,app>] [--paths <paths>]",
    "  intercom-format-gate.mjs help-article:evidence-check --draft <path> --evidence <path>",
    "  intercom-format-gate.mjs intercom:stage-update --article-id <id> --draft <path> --evidence <path> [--title <title>]"
  ].join("\n");
}

export async function main(argv = process.argv.slice(2)) {
  const [command, ...rest] = argv;
  const args = parseArgs(rest);
  let result;
  if (command === "intercom:affected") result = await commandAffected(args);
  else if (command === "intercom:format:pull") result = await commandPull(args);
  else if (command === "intercom:format:profile") result = await commandProfile(args);
  else if (command === "intercom:inventory") result = await commandInventory(args);
  else if (command === "help-article:shape-refresh" || command === "help-article:shape-ingest") result = await commandShapeRefresh(args);
  else if (command === "help-article:plan") result = await commandPlan(args);
  else if (command === "help-article:format-check") result = await commandFormatCheck(args);
  else if (command === "help-article:pantheon-scan") result = await commandPantheonScan(args);
  else if (command === "help-article:evidence-check") result = await commandEvidenceCheck(args);
  else if (command === "intercom:stage-update") result = await commandStageUpdate(args);
  else {
    throw new Error(usage());
  }
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  if (result.status === "fail" || result.status === "needs-check") process.exitCode = 1;
  return result;
}

if (process.argv[1] === currentFile) {
  main().catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
}
