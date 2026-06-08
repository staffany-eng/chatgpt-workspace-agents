#!/usr/bin/env node
import { mkdir, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { tmpdir } from "node:os";

const allowedHostPatterns = [
  /(^|\.)staffany\.com$/i,
  /(^|\.)staffany\.com\.sg$/i,
  /^localhost$/i,
  /^127\.0\.0\.1$/,
];

function usage() {
  return `Usage:
  node apps/launchbot/runtime/help-article-staging-auth-state.mjs --output <state.json> [--source-url <url>] [--validate-route <route>] [--wait-for-text <text>] [--headless true|false] [--allow-blocked]

Environment:
  LAUNCHBOT_STAGING_URL or STAFFANY_STAGING_URL
  LAUNCHBOT_STAGING_EMAIL
  LAUNCHBOT_STAGING_PASSWORD
  LAUNCHBOT_STAGING_OTP optional, only for approved one-time use

The output storage-state file contains session material. Save it only in /tmp or a Hermes runtime profile path.
`;
}

function parseArgs(argv) {
  const args = {
    sourceUrl: process.env.LAUNCHBOT_STAGING_URL || process.env.STAFFANY_STAGING_URL || "",
    output: process.env.LAUNCHBOT_STAGING_STORAGE_STATE || "",
    validateRoute: "/",
    waitForText: "",
    emailSelector: 'input[type="email"], input[name="email"], input[id*="email" i]',
    passwordSelector: 'input[type="password"], input[name="password"]',
    submitSelector: 'button[type="submit"], button:has-text("Log in"), button:has-text("Login"), button:has-text("Sign in")',
    otpSelector: 'input[name="otp"], input[name="totp"], input[autocomplete="one-time-code"]',
    headless: true,
    timeoutMs: 60000,
    allowBlocked: false,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--source-url") args.sourceUrl = argv[++index] || "";
    else if (arg === "--output") args.output = argv[++index] || "";
    else if (arg === "--validate-route") args.validateRoute = argv[++index] || "";
    else if (arg === "--wait-for-text") args.waitForText = argv[++index] || "";
    else if (arg === "--email-selector") args.emailSelector = argv[++index] || "";
    else if (arg === "--password-selector") args.passwordSelector = argv[++index] || "";
    else if (arg === "--submit-selector") args.submitSelector = argv[++index] || "";
    else if (arg === "--otp-selector") args.otpSelector = argv[++index] || "";
    else if (arg === "--timeout-ms") args.timeoutMs = Number(argv[++index] || args.timeoutMs);
    else if (arg === "--headless") args.headless = String(argv[++index] || "true") !== "false";
    else if (arg === "--allow-blocked") args.allowBlocked = true;
    else if (arg === "--help" || arg === "-h") {
      process.stdout.write(usage());
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  return args;
}

function validateAllowedUrl(value) {
  if (!value) throw new Error("Missing --source-url or LAUNCHBOT_STAGING_URL.");
  const url = new URL(value);
  if (!["http:", "https:"].includes(url.protocol)) throw new Error(`Unsupported URL protocol: ${url.protocol}`);
  if (!allowedHostPatterns.some((pattern) => pattern.test(url.hostname))) {
    throw new Error(`Staging target host is not allowlisted: ${url.hostname}`);
  }
  return url;
}

function validateCredentialEnv() {
  const email = process.env.LAUNCHBOT_STAGING_EMAIL || "";
  const password = process.env.LAUNCHBOT_STAGING_PASSWORD || "";
  if (!email) throw new Error("Missing LAUNCHBOT_STAGING_EMAIL.");
  if (!password) throw new Error("Missing LAUNCHBOT_STAGING_PASSWORD.");
  return { email, password, otp: process.env.LAUNCHBOT_STAGING_OTP || "" };
}

function isSafeStorageOutput(path) {
  const absolute = resolve(path || "");
  const temp = resolve(tmpdir());
  return (
    absolute.startsWith(`${temp}/`) ||
    absolute.startsWith("/tmp/") ||
    absolute.startsWith("/private/tmp/") ||
    absolute.startsWith("/var/folders/") ||
    absolute.startsWith("/private/var/folders/") ||
    /\/\.hermes\/profiles\/[^/]+\/runtime\//.test(absolute) ||
    /\/\.cache\/launchbot\//.test(absolute)
  );
}

async function loadPlaywright() {
  try {
    return await import("playwright");
  } catch (firstError) {
    try {
      return await import("playwright-core");
    } catch {
      throw new Error(`Playwright is not installed in this runtime. Install Playwright/Chromium before staging auth. Original error: ${firstError.message}`);
    }
  }
}

async function fillFirstVisible(page, selector, value, label, timeoutMs) {
  const locator = page.locator(selector).first();
  await locator.waitFor({ state: "visible", timeout: timeoutMs });
  await locator.fill(value);
  return label;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const sourceUrl = validateAllowedUrl(args.sourceUrl);
  const output = resolve(args.output || "");
  if (!output) throw new Error("Missing --output or LAUNCHBOT_STAGING_STORAGE_STATE.");
  if (!isSafeStorageOutput(output)) {
    throw new Error("Refusing to write staging storage-state outside /tmp, .cache/launchbot, or a Hermes runtime profile path.");
  }
  const credentials = validateCredentialEnv();
  const playwright = await loadPlaywright();
  const browser = await playwright.chromium.launch({ headless: args.headless });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();

  try {
    await page.goto(sourceUrl.toString(), { waitUntil: "domcontentloaded", timeout: args.timeoutMs });
    await fillFirstVisible(page, args.emailSelector, credentials.email, "email", args.timeoutMs);
    await fillFirstVisible(page, args.passwordSelector, credentials.password, "password", args.timeoutMs);
    await page.locator(args.submitSelector).first().click({ timeout: args.timeoutMs });
    if (credentials.otp) {
      await fillFirstVisible(page, args.otpSelector, credentials.otp, "otp", args.timeoutMs);
      await page.locator(args.submitSelector).first().click({ timeout: args.timeoutMs }).catch(() => {});
    }
    await page.waitForLoadState("networkidle", { timeout: args.timeoutMs }).catch(() => {});
    if (args.validateRoute) {
      const validateUrl = new URL(args.validateRoute, sourceUrl);
      await page.goto(validateUrl.toString(), { waitUntil: "networkidle", timeout: args.timeoutMs });
    }
    if (args.waitForText) {
      await page.getByText(args.waitForText, { exact: false }).first().waitFor({ timeout: args.timeoutMs });
    }
    await mkdir(dirname(output), { recursive: true });
    await context.storageState({ path: output });
    await writeFile(`${output}.metadata.json`, `${JSON.stringify({
      status: "created",
      source_url: sourceUrl.origin,
      storage_state: output,
      values_printed: false,
      generated_at: new Date().toISOString(),
    }, null, 2)}\n`, "utf8");
    process.stdout.write(`${JSON.stringify({ status: "created", storage_state: output, values_printed: false }, null, 2)}\n`);
  } finally {
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
  }
}

main().catch(async (error) => {
  const message = error instanceof Error ? error.message : String(error);
  process.stdout.write(`${JSON.stringify({ status: "blocked", blocker: message, values_printed: false }, null, 2)}\n`);
  const allowBlocked = process.argv.includes("--allow-blocked");
  if (!allowBlocked) process.exitCode = 2;
});
