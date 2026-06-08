#!/usr/bin/env node
import { spawn } from "node:child_process";
import { createServer } from "node:net";
import { mkdir, writeFile } from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import { basename, join, resolve } from "node:path";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";

const defaultViewport = { width: 1440, height: 1000 };
const defaultChromeExecutable = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const allowedHostPatterns = [
  /^localhost$/i,
  /^127\.0\.0\.1$/,
  /^0\.0\.0\.0$/,
  /^::1$/,
  /(^|\.)staffany\.com$/i,
  /(^|\.)staffany\.com\.sg$/i,
];

function usage() {
  return `Usage:
  node apps/launchbot/runtime/help-article-screenshot-runner.mjs --plan <plan.json> --output-dir <dir> [--source-url <url>] [--storage-state <file>] [--param key=value] [--browser playwright|chrome-cdp] [--dry-run] [--allow-blocked]

The plan must contain { article_slug, shots: [{ id, route, waitForText, cropSelector }] }.
`;
}

function parseArgs(argv) {
  const args = {
    plan: "",
    outputDir: "",
    sourceUrl: "",
    storageState: "",
    browser: "playwright",
    chromeExecutable: defaultChromeExecutable,
    params: {},
    dryRun: false,
    allowBlocked: false,
    timeoutMs: 30000,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--plan") args.plan = argv[++index] || "";
    else if (arg === "--output-dir") args.outputDir = argv[++index] || "";
    else if (arg === "--source-url") args.sourceUrl = argv[++index] || "";
    else if (arg === "--storage-state") args.storageState = argv[++index] || "";
    else if (arg === "--browser") args.browser = argv[++index] || "playwright";
    else if (arg === "--chrome-executable") args.chromeExecutable = argv[++index] || defaultChromeExecutable;
    else if (arg === "--param") {
      const pair = argv[++index] || "";
      const equalIndex = pair.indexOf("=");
      if (equalIndex <= 0) throw new Error("--param must use key=value");
      args.params[pair.slice(0, equalIndex)] = pair.slice(equalIndex + 1);
    }
    else if (arg === "--timeout-ms") args.timeoutMs = Number(argv[++index] || args.timeoutMs);
    else if (arg === "--dry-run") args.dryRun = true;
    else if (arg === "--allow-blocked") args.allowBlocked = true;
    else if (arg === "--help" || arg === "-h") {
      process.stdout.write(usage());
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  if (!args.plan) throw new Error("Missing --plan");
  if (!args.outputDir) throw new Error("Missing --output-dir");
  if (!["playwright", "chrome-cdp"].includes(args.browser)) throw new Error("--browser must be playwright or chrome-cdp");
  return args;
}

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function asSlug(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

function validatePlan(plan) {
  const errors = [];
  if (!plan || typeof plan !== "object") errors.push("Plan must be a JSON object.");
  if (!Array.isArray(plan?.shots) || plan.shots.length === 0) errors.push("Plan must include at least one shot.");
  for (const [index, shot] of (plan?.shots || []).entries()) {
    if (!shot.id) errors.push(`shots[${index}] is missing id.`);
    if (!shot.label) errors.push(`shots[${index}] is missing label.`);
    if (!shot.placement) errors.push(`shots[${index}] is missing placement.`);
    if (!shot.route && !shot.url) errors.push(`shots[${index}] is missing route or url.`);
  }
  if (errors.length) throw new Error(errors.join(" "));
}

function substituteParams(value, params) {
  return String(value || "").replace(/\{([A-Za-z0-9_]+)\}/g, (match, key) => {
    if (params[key] === undefined || params[key] === "") return match;
    return encodeURIComponent(params[key]);
  });
}

function safeUrlForShot(sourceUrl, shot, params = {}) {
  const raw = substituteParams(shot.url || shot.route, params);
  if (!raw) throw new Error(`Shot ${shot.id} has no route/url.`);
  const unresolved = raw.match(/\{[A-Za-z0-9_]+\}/g);
  if (unresolved) {
    throw new Error(`Shot ${shot.id} has unresolved route parameter(s): ${unresolved.join(", ")}. Pass --param key=value for demo data IDs.`);
  }
  let url;
  if (/^https?:\/\//i.test(raw) || /^file:\/\//i.test(raw)) {
    url = new URL(raw);
  } else if (sourceUrl) {
    url = new URL(raw, sourceUrl.endsWith("/") ? sourceUrl : `${sourceUrl}/`);
  } else {
    throw new Error(`Shot ${shot.id} uses a relative route but --source-url was not provided.`);
  }
  if (url.protocol === "file:") return url;
  if (!["http:", "https:"].includes(url.protocol)) {
    throw new Error(`Shot ${shot.id} uses unsupported URL protocol: ${url.protocol}`);
  }
  if (!allowedHostPatterns.some((pattern) => pattern.test(url.hostname))) {
    throw new Error(`Shot ${shot.id} target host is not allowlisted: ${url.hostname}`);
  }
  return url;
}

function buildManifest({ plan, planPath, outputDir, status, blocker, screenshots = [] }) {
  return {
    status,
    blocker: blocker || null,
    generated_at: new Date().toISOString(),
    plan_path: planPath,
    output_dir: outputDir,
    article_slug: plan.article_slug || asSlug(plan.article_title || basename(planPath, ".json")),
    article_title: plan.article_title || "",
    article_url: plan.article_url || "",
    feature: plan.feature || "",
    source_policy: plan.source_policy || {},
    screenshots,
    shots: plan.shots.map((shot) => ({
      id: shot.id,
      label: shot.label,
      placement: shot.placement,
      route: shot.route || shot.url || "",
      waitForText: shot.waitForText || "",
      cropSelector: shot.cropSelector || "",
      redactionNotes: shot.redactionNotes || [],
      status: screenshots.find((item) => item.id === shot.id)?.status || status,
    })),
  };
}

async function writeManifest(outputDir, manifest) {
  await mkdir(outputDir, { recursive: true });
  const path = join(outputDir, "screenshot-manifest.json");
  await writeFile(path, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
  return path;
}

async function loadPlaywright() {
  try {
    return await import("playwright");
  } catch (firstError) {
    try {
      return await import("playwright-core");
    } catch {
      throw new Error(
        `Playwright is not installed in this runtime. Install the browser runtime before capture. Original error: ${firstError.message}`,
      );
    }
  }
}

function httpJson(url, options = {}) {
  return new Promise((resolvePromise, rejectPromise) => {
    fetch(url, options)
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status} for ${url}`);
        resolvePromise(await response.json());
      })
      .catch(rejectPromise);
  });
}

function wait(ms) {
  return new Promise((resolvePromise) => setTimeout(resolvePromise, ms));
}

function waitForProcessExit(child, timeoutMs = 3000) {
  return new Promise((resolvePromise) => {
    if (child.exitCode !== null || child.killed) {
      resolvePromise();
      return;
    }
    const timer = setTimeout(resolvePromise, timeoutMs);
    child.once("exit", () => {
      clearTimeout(timer);
      resolvePromise();
    });
  });
}

function getFreePort() {
  return new Promise((resolvePromise, rejectPromise) => {
    const server = createServer();
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : 0;
      server.close(() => resolvePromise(port));
    });
    server.on("error", rejectPromise);
  });
}

async function waitForChromeVersion(port, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let lastError;
  while (Date.now() < deadline) {
    try {
      return await httpJson(`http://127.0.0.1:${port}/json/version`);
    } catch (error) {
      lastError = error;
      await wait(100);
    }
  }
  throw new Error(`Chrome DevTools did not become ready: ${lastError?.message || "timeout"}`);
}

function createCdpClient(webSocketDebuggerUrl) {
  const socket = new WebSocket(webSocketDebuggerUrl);
  let nextId = 1;
  const pending = new Map();
  const events = new Map();

  socket.addEventListener("message", (message) => {
    const payload = JSON.parse(message.data);
    if (payload.id && pending.has(payload.id)) {
      const { resolve: resolvePromise, reject: rejectPromise } = pending.get(payload.id);
      pending.delete(payload.id);
      if (payload.error) rejectPromise(new Error(payload.error.message || JSON.stringify(payload.error)));
      else resolvePromise(payload.result || {});
      return;
    }
    if (payload.method && events.has(payload.method)) {
      for (const listener of events.get(payload.method)) listener(payload.params || {});
    }
  });

  return {
    async ready() {
      if (socket.readyState === WebSocket.OPEN) return;
      await new Promise((resolvePromise, rejectPromise) => {
        socket.addEventListener("open", resolvePromise, { once: true });
        socket.addEventListener("error", rejectPromise, { once: true });
      });
    },
    send(method, params = {}) {
      const id = nextId;
      nextId += 1;
      socket.send(JSON.stringify({ id, method, params }));
      return new Promise((resolvePromise, rejectPromise) => {
        pending.set(id, { resolve: resolvePromise, reject: rejectPromise });
      });
    },
    once(method, timeoutMs = 30000) {
      return new Promise((resolvePromise, rejectPromise) => {
        const timer = setTimeout(() => rejectPromise(new Error(`Timed out waiting for ${method}`)), timeoutMs);
        const listener = (params) => {
          clearTimeout(timer);
          events.set(
            method,
            (events.get(method) || []).filter((item) => item !== listener),
          );
          resolvePromise(params);
        };
        events.set(method, [...(events.get(method) || []), listener]);
      });
    },
    close() {
      socket.close();
    },
  };
}

async function navigateCdp(client, url, timeoutMs) {
  const load = client.once("Page.loadEventFired", timeoutMs).catch(() => null);
  await client.send("Page.navigate", { url });
  await load;
}

async function waitForTextCdp(client, text, timeoutMs) {
  if (!text) return;
  const deadline = Date.now() + timeoutMs;
  const needle = JSON.stringify(String(text));
  while (Date.now() < deadline) {
    const result = await client.send("Runtime.evaluate", {
      expression: `document.body && document.body.innerText && document.body.innerText.includes(${needle})`,
      returnByValue: true,
    });
    if (result.result?.value === true) return;
    await wait(250);
  }
  throw new Error(`Timed out waiting for text: ${text}`);
}

async function setStorageStateCdp(client, statePath) {
  if (!statePath) return;
  if (!existsSync(statePath)) throw new Error(`Storage state not found: ${statePath}`);
  const state = readJson(statePath);
  if (Array.isArray(state.cookies) && state.cookies.length) {
    await client.send("Network.setCookies", {
      cookies: state.cookies.map((cookie) => ({
        name: cookie.name,
        value: cookie.value,
        domain: cookie.domain,
        path: cookie.path || "/",
        expires: cookie.expires && cookie.expires > 0 ? cookie.expires : undefined,
        httpOnly: cookie.httpOnly,
        secure: cookie.secure,
        sameSite: cookie.sameSite,
      })),
    });
  }
  for (const origin of state.origins || []) {
    if (!origin.origin || !Array.isArray(origin.localStorage)) continue;
    const url = new URL(origin.origin);
    if (!allowedHostPatterns.some((pattern) => pattern.test(url.hostname))) continue;
    await navigateCdp(client, origin.origin, 30000);
    const entries = JSON.stringify(origin.localStorage);
    await client.send("Runtime.evaluate", {
      expression: `for (const item of ${entries}) localStorage.setItem(item.name, item.value);`,
      awaitPromise: true,
    });
  }
}

async function applyRedactionsCdp(client, selectors) {
  const expression = `(() => {
    const selectors = ${JSON.stringify(selectors || [])};
    let count = 0;
    for (const selector of selectors) {
      for (const node of document.querySelectorAll(selector)) {
        const box = node.getBoundingClientRect();
        if (!box.width || !box.height) continue;
        const cover = document.createElement("div");
        cover.setAttribute("data-launchbot-redaction", "true");
        Object.assign(cover.style, {
          position: "absolute",
          left: (box.x + window.scrollX) + "px",
          top: (box.y + window.scrollY) + "px",
          width: box.width + "px",
          height: box.height + "px",
          background: "#1f2937",
          zIndex: "2147483647",
          borderRadius: "4px",
        });
        document.body.appendChild(cover);
        count += 1;
      }
    }
    return count;
  })()`;
  const result = await client.send("Runtime.evaluate", { expression, returnByValue: true });
  return Number(result.result?.value || 0);
}

async function screenshotCdp(client, selector, path) {
  let clip;
  if (selector) {
    const result = await client.send("Runtime.evaluate", {
      expression: `(() => {
        const node = document.querySelector(${JSON.stringify(selector)});
        if (!node) return null;
        const box = node.getBoundingClientRect();
        return { x: box.x + window.scrollX, y: box.y + window.scrollY, width: box.width, height: box.height, scale: 1 };
      })()`,
      returnByValue: true,
    });
    const value = result.result?.value;
    if (value && value.width > 0 && value.height > 0) clip = value;
  }
  const screenshot = await client.send("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
    ...(clip ? { clip } : {}),
  });
  writeFileSync(path, Buffer.from(screenshot.data, "base64"));
}

async function captureWithChromeCdp(plan, args) {
  for (const shot of plan.shots) safeUrlForShot(args.sourceUrl, shot, args.params);
  if (!existsSync(args.chromeExecutable)) throw new Error(`Chrome executable not found: ${args.chromeExecutable}`);
  const port = await getFreePort();
  const profileDir = mkdtempSync(join(tmpdir(), "launchbot-chrome-"));
  const chrome = spawn(args.chromeExecutable, [
    "--headless=new",
    "--no-first-run",
    "--disable-gpu",
    "--disable-dev-shm-usage",
    "--window-size=1440,1000",
    `--user-data-dir=${profileDir}`,
    `--remote-debugging-port=${port}`,
    "--remote-debugging-address=127.0.0.1",
    "about:blank",
  ]);
  chrome.stderr.on("data", () => {});
  chrome.stdout.on("data", () => {});

  let client;
  try {
    await waitForChromeVersion(port, 15000);
    const targets = await httpJson(`http://127.0.0.1:${port}/json/list`);
    const pageTarget = targets.find((target) => target.type === "page" && target.webSocketDebuggerUrl);
    if (!pageTarget) throw new Error("Chrome DevTools page target not found.");
    client = createCdpClient(pageTarget.webSocketDebuggerUrl);
    await client.ready();
    await client.send("Page.enable");
    await client.send("Runtime.enable");
    await client.send("Network.enable");
    await client.send("Emulation.setDeviceMetricsOverride", {
      width: plan.viewport?.width || defaultViewport.width,
      height: plan.viewport?.height || defaultViewport.height,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await setStorageStateCdp(client, args.storageState);

    const screenshots = [];
    for (const [index, shot] of plan.shots.entries()) {
      const url = safeUrlForShot(args.sourceUrl, shot, args.params);
      const filename = `${String(index + 1).padStart(2, "0")}-${asSlug(shot.id || shot.label)}.png`;
      const path = join(args.outputDir, filename);
      await navigateCdp(client, url.toString(), args.timeoutMs);
      await waitForTextCdp(client, shot.waitForText, args.timeoutMs);
      const redactionCount = await applyRedactionsCdp(client, shot.redactSelectors || []);
      await screenshotCdp(client, shot.cropSelector, path);
      screenshots.push({
        id: shot.id,
        status: "captured",
        file: path,
        source_url: url.toString(),
        placement: shot.placement,
        redactions_applied: redactionCount,
      });
    }
    return screenshots;
  } finally {
    if (client) client.close();
    chrome.kill("SIGTERM");
    await waitForProcessExit(chrome);
    try {
      rmSync(profileDir, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 });
    } catch {
      // Temporary Chrome profile cleanup must not mask the capture result.
    }
  }
}

async function applyRedactions(page, selectors) {
  const applied = [];
  for (const selector of selectors || []) {
    const handles = await page.locator(selector).elementHandles().catch(() => []);
    for (const handle of handles) {
      const box = await handle.boundingBox().catch(() => null);
      if (!box) continue;
      applied.push({ selector, box });
    }
  }
  if (!applied.length) return applied;
  await page.evaluate((boxes) => {
    for (const item of boxes) {
      const cover = document.createElement("div");
      cover.setAttribute("data-launchbot-redaction", "true");
      Object.assign(cover.style, {
        position: "absolute",
        left: `${item.box.x + window.scrollX}px`,
        top: `${item.box.y + window.scrollY}px`,
        width: `${item.box.width}px`,
        height: `${item.box.height}px`,
        background: "#1f2937",
        zIndex: "2147483647",
        borderRadius: "4px",
      });
      document.body.appendChild(cover);
    }
  }, applied);
  return applied;
}

async function capture(plan, args) {
  for (const shot of plan.shots) {
    safeUrlForShot(args.sourceUrl, shot, args.params);
  }
  const playwright = await loadPlaywright();
  const browser = await playwright.chromium.launch({ headless: true });
  const contextOptions = { viewport: plan.viewport || defaultViewport };
  if (args.storageState) {
    if (!existsSync(args.storageState)) throw new Error(`Storage state not found: ${args.storageState}`);
    contextOptions.storageState = args.storageState;
  }
  const context = await browser.newContext(contextOptions);
  const page = await context.newPage();
  const screenshots = [];

  try {
    for (const [index, shot] of plan.shots.entries()) {
      const url = safeUrlForShot(args.sourceUrl, shot, args.params);
      const filename = `${String(index + 1).padStart(2, "0")}-${asSlug(shot.id || shot.label)}.png`;
      const path = join(args.outputDir, filename);
      await page.goto(url.toString(), { waitUntil: "networkidle", timeout: args.timeoutMs });
      if (shot.waitForText) {
        await page.getByText(shot.waitForText, { exact: false }).first().waitFor({ timeout: args.timeoutMs });
      }
      for (const action of shot.actions || []) {
        if (action.type === "click" && action.selector) await page.locator(action.selector).first().click();
        else if (action.type === "clickText" && action.text) await page.getByText(action.text, { exact: false }).first().click();
        else if (action.type === "fill" && action.selector) await page.locator(action.selector).fill(action.value || "");
        else throw new Error(`Unsupported action for ${shot.id}: ${JSON.stringify(action)}`);
      }
      const redactions = await applyRedactions(page, shot.redactSelectors || []);
      const target = shot.cropSelector ? page.locator(shot.cropSelector).first() : page;
      await target.screenshot({ path });
      screenshots.push({
        id: shot.id,
        status: "captured",
        file: path,
        source_url: url.toString(),
        placement: shot.placement,
        redactions_applied: redactions.length,
      });
    }
  } finally {
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
  }

  return screenshots;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const planPath = resolve(args.plan);
  const outputDir = resolve(args.outputDir);
  const plan = readJson(planPath);
  validatePlan(plan);
  await mkdir(outputDir, { recursive: true });

  if (args.dryRun) {
    const manifest = buildManifest({ plan, planPath, outputDir, status: "planned" });
    const manifestPath = await writeManifest(outputDir, manifest);
    process.stdout.write(`${JSON.stringify({ status: "planned", manifest: manifestPath }, null, 2)}\n`);
    return;
  }

  try {
    const screenshots =
      args.browser === "chrome-cdp"
        ? await captureWithChromeCdp(plan, { ...args, outputDir })
        : await capture(plan, { ...args, outputDir });
    const manifest = buildManifest({ plan, planPath, outputDir, status: "captured", screenshots });
    const manifestPath = await writeManifest(outputDir, manifest);
    process.stdout.write(`${JSON.stringify({ status: "captured", manifest: manifestPath, screenshots }, null, 2)}\n`);
  } catch (error) {
    const manifest = buildManifest({
      plan,
      planPath,
      outputDir,
      status: "blocked",
      blocker: error instanceof Error ? error.message : String(error),
    });
    const manifestPath = await writeManifest(outputDir, manifest);
    process.stdout.write(`${JSON.stringify({ status: "blocked", manifest: manifestPath, blocker: manifest.blocker }, null, 2)}\n`);
    if (!args.allowBlocked) process.exitCode = 2;
  }
}

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.stack || error.message : String(error)}\n`);
  process.exit(1);
});
