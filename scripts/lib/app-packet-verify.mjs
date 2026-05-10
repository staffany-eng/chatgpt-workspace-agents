import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

export function readJson(path, fail) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    fail(`Invalid JSON: ${path}: ${error.message}`);
    return null;
  }
}

export function assertFile(appRoot, relPath, fail) {
  const path = join(appRoot, relPath);
  if (!existsSync(path)) {
    fail(`Missing app file: ${relPath}`);
    return;
  }
  if (!statSync(path).isFile()) {
    fail(`Expected file, got non-file path: ${relPath}`);
  }
}

export function textOf(appRoot, relPath) {
  const path = join(appRoot, relPath);
  if (!existsSync(path) || !statSync(path).isFile()) return "";
  return readFileSync(path, "utf8");
}

export function scanForSecretPatterns(appRoot, relPath, fail) {
  const text = textOf(appRoot, relPath);
  if (!text) return;
  const patterns = [
    [/xox[baprs]-[A-Za-z0-9-]+/, "Slack token"],
    [/xapp-[A-Za-z0-9-]+/, "Slack app token"],
    [/sk-[A-Za-z0-9_-]{20,}/, "OpenAI-style API key"],
    [/pat-[a-z0-9]+-[A-Za-z0-9-]{20,}/, "HubSpot private app token"],
    [/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/, "private key"],
    [/AIza[0-9A-Za-z_-]{20,}/, "Google API key"]
  ];
  for (const [pattern, label] of patterns) {
    if (pattern.test(text)) fail(`${label} pattern found in ${relPath}`);
  }
}

export function assertManifestPaths(appRoot, paths, fail) {
  for (const value of Object.values(paths || {})) {
    if (Array.isArray(value)) {
      for (const relPath of value) assertFile(appRoot, relPath, fail);
    } else {
      assertFile(appRoot, value, fail);
    }
  }
}
