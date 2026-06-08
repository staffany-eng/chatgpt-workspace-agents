import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";
import assert from "node:assert/strict";

const appRoot = fileURLToPath(new URL("..", import.meta.url));
const helper = join(appRoot, "runtime", "help-article-staging-auth-state.mjs");

test("staging auth blocks safely when credentials are missing", () => {
  const dir = mkdtempSync(join(tmpdir(), "launchbot-staging-auth-"));
  const result = spawnSync(process.execPath, [
    helper,
    "--source-url",
    "https://staging.staffany.com",
    "--output",
    join(dir, "state.json"),
    "--allow-blocked",
  ], {
    encoding: "utf8",
    env: {
      PATH: process.env.PATH || "",
      HOME: process.env.HOME || "",
    },
  });

  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.status, "blocked");
  assert.equal(output.values_printed, false);
  assert.match(output.blocker, /LAUNCHBOT_STAGING_EMAIL/);
});

test("staging auth refuses to write storage state into the repo", () => {
  const result = spawnSync(process.execPath, [
    helper,
    "--source-url",
    "https://staging.staffany.com",
    "--output",
    join(appRoot, "output", "unsafe-storage-state.json"),
    "--allow-blocked",
  ], {
    encoding: "utf8",
    env: {
      PATH: process.env.PATH || "",
      HOME: process.env.HOME || "",
      LAUNCHBOT_STAGING_EMAIL: "demo@example.com",
      LAUNCHBOT_STAGING_PASSWORD: "redacted",
    },
  });

  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.status, "blocked");
  assert.equal(output.values_printed, false);
  assert.match(output.blocker, /Refusing to write staging storage-state/);
});
