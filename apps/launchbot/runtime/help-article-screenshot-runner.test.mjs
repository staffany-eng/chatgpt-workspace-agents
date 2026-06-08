import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";
import assert from "node:assert/strict";

const appRoot = fileURLToPath(new URL("..", import.meta.url));
const runner = join(appRoot, "runtime", "help-article-screenshot-runner.mjs");

test("dry-run writes a planned screenshot manifest", () => {
  const dir = mkdtempSync(join(tmpdir(), "launchbot-screenshots-"));
  const planPath = join(dir, "plan.json");
  const outputDir = join(dir, "assets");
  writeFileSync(
    planPath,
    JSON.stringify({
      article_slug: "demo-article",
      article_title: "Demo Article",
      shots: [
        {
          id: "general-setting",
          label: "General Setting",
          placement: "After step 1",
          route: "/payroll/payments/1/disbursements/editor",
          waitForText: "Scheduled for",
        },
      ],
    }),
  );

  const result = spawnSync(process.execPath, [runner, "--plan", planPath, "--output-dir", outputDir, "--dry-run"], {
    encoding: "utf8",
  });

  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.status, "planned");
  const manifest = JSON.parse(readFileSync(join(outputDir, "screenshot-manifest.json"), "utf8"));
  assert.equal(manifest.status, "planned");
  assert.equal(manifest.shots[0].id, "general-setting");
});

test("capture blocks safely when Playwright is unavailable or source is missing", () => {
  const dir = mkdtempSync(join(tmpdir(), "launchbot-screenshots-"));
  const planPath = join(dir, "plan.json");
  const outputDir = join(dir, "assets");
  writeFileSync(
    planPath,
    JSON.stringify({
      article_slug: "demo-article",
      shots: [
        {
          id: "unsafe",
          label: "Unsafe Host",
          placement: "After step 1",
          url: "https://example.com/not-allowed",
        },
      ],
    }),
  );

  const result = spawnSync(process.execPath, [runner, "--plan", planPath, "--output-dir", outputDir, "--allow-blocked"], {
    encoding: "utf8",
  });

  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.status, "blocked");
  const manifest = JSON.parse(readFileSync(join(outputDir, "screenshot-manifest.json"), "utf8"));
  assert.equal(manifest.status, "blocked");
  assert.match(manifest.blocker, /not installed|not allowlisted/);
});
