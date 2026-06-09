import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { countMissingConfiguredPaths, decideActions, expandPath, parseProfilesYaml, summarizeFacts } from "../caretaker.mjs";

describe("Hermes caretaker registry parsing", () => {
  it("parses profile registry lists and nested maps", () => {
    const profiles = parseProfilesYaml(`
profiles:
  - name: demo
    live_profile: demo-live
    aliases: [old-demo]
    required_mcp:
      demo_mcp: 2
    expected_crons:
      - name: demo health
        schedule: "*/5 * * * *"
        mode: no-agent
`);
    assert.equal(profiles.length, 1);
    assert.equal(profiles[0].name, "demo");
    assert.deepEqual(profiles[0].aliases, ["old-demo"]);
    assert.equal(profiles[0].required_mcp.demo_mcp, 2);
    assert.equal(profiles[0].expected_crons[0].schedule, "*/5 * * * *");
  });

  it("does not claim PS WEE aliases after Customer 360 migration", () => {
    const profiles = parseProfilesYaml(readFileSync(new URL("../profiles.yaml", import.meta.url), "utf8"));
    const nurtureAny = profiles.find((profile) => profile.name === "nurtureanysalesbot");
    const psmOps = profiles.find((profile) => profile.name === "psmopsbot");

    assert.ok(nurtureAny);
    assert.equal(psmOps, undefined);
    assert.equal((nurtureAny.workflow_aliases || []).some((alias) => /ps\s+wee/i.test(alias)), false);
  });

  it("keeps StaffAny Slack app profiles cloud-only from Mac operator hosts", () => {
    const profiles = parseProfilesYaml(readFileSync(new URL("../profiles.yaml", import.meta.url), "utf8"));
    const cloudOnlyProfiles = new Map([
      ["staffanydatabot", "hermes-data-bot-poc"],
      ["launchbot", "hermes-data-bot-poc"],
      ["nurtureanysalesbot", "nurtureany-sales-bot-prod"],
    ]);

    for (const [profileName, deployHost] of cloudOnlyProfiles) {
      const profile = profiles.find((candidate) => candidate.name === profileName);
      assert.ok(profile, `${profileName} profile must exist`);
      assert.equal(profile.deploy_host, deployHost);
      assert.equal(profile.local_profile_policy, "cloud_only");
      assert.equal(profile.service?.launchd_label, undefined);
    }
  });

  it("expands home placeholders without touching other strings", () => {
    assert.equal(expandPath("${HOME}/.hermes/profiles/x", { HOME: "/tmp/home" }), "/tmp/home/.hermes/profiles/x");
    assert.equal(expandPath("~/x", { HOME: "/tmp/home" }), "/tmp/home/x");
    assert.equal(expandPath("apps/hermes-data-bot", { HOME: "/tmp/home" }), "apps/hermes-data-bot");
  });

  it("counts missing paths only for required MCP server blocks", () => {
    const root = mkdtempSync(join(tmpdir(), "hermes-caretaker-"));
    try {
      const profileDir = join(root, "profile");
      const existingPath = join(profileDir, "runtime", "mcp", "required.py");
      mkdirSync(join(profileDir, "runtime", "mcp"), { recursive: true });
      writeFileSync(existingPath, "");
      writeFileSync(join(profileDir, "config.yaml"), `
mcp_servers:
  required_mcp:
    enabled: true
    args:
    - ${existingPath}
  optional_mcp:
    enabled: false
    args:
    - ${profileDir}/runtime/mcp/missing-optional.py
`);
      assert.equal(countMissingConfiguredPaths(profileDir, { required_mcp: { required_mcp: 1 } }), 0);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });
});

describe("Hermes caretaker decisions", () => {
  const profile = {
    name: "nurtureanysalesbot",
    live_profile: "nurtureanysalesbot",
    deploy_host: "nurtureany-sales-bot-prod",
    recovery: {},
  };

  it("does not repair remote-only profiles from a Mac operator host", () => {
    const actions = decideActions(profile, {
      remoteOnly: true,
      needsProfileAlias: true,
      serviceDisabled: false,
      gatewayRunning: false,
      socketStale: false,
      profileDrift: "",
      missingConfiguredPathCount: 0,
      unsafeCrons: [],
      missingChannelMembership: [],
      staleSessionCount: 0,
      activeAgents: 0,
    });
    assert.deepEqual(actions, []);
  });

  it("repairs missing profile alias and stale gateway when explicitly allowed", () => {
    const actions = decideActions({
      name: "demo",
      live_profile: "demo-live",
      recovery: { create_profile_alias: true },
    }, {
      needsProfileAlias: true,
      serviceDisabled: false,
      gatewayRunning: false,
      socketStale: false,
      profileDrift: "",
      missingConfiguredPathCount: 0,
      unsafeCrons: [],
      missingChannelMembership: [],
      staleSessionCount: 0,
      activeAgents: 0,
    });
    assert.deepEqual(actions.map((action) => action.type), ["create_profile_alias", "start_gateway", "report"]);
  });

  it("pauses unsafe cron jobs and reports blocked channel membership", () => {
    const actions = decideActions(profile, {
      needsProfileAlias: false,
      serviceDisabled: false,
      gatewayRunning: true,
      socketStale: false,
      profileDrift: "",
      missingConfiguredPathCount: 0,
      unsafeCrons: [{ id: "abc", name: "event-roi-job1-daily-signup-update" }],
      missingChannelMembership: ["C06CD9B6LDU"],
      staleSessionCount: 0,
      activeAgents: 0,
    });
    assert.deepEqual(actions.map((action) => action.type), ["pause_cron", "report_blocked_channel", "report"]);
    assert.equal(actions[0].jobId, "abc");
  });

  it("does not clear stale sessions while an agent is active", () => {
    const actions = decideActions(profile, {
      needsProfileAlias: false,
      serviceDisabled: false,
      gatewayRunning: true,
      socketStale: false,
      profileDrift: "",
      missingConfiguredPathCount: 0,
      unsafeCrons: [],
      missingChannelMembership: [],
      staleSessionCount: 3,
      activeAgents: 1,
    });
    assert.equal(actions.length, 0);
  });

  it("enables a disabled launchd service before restart", () => {
    const actions = decideActions(profile, {
      needsProfileAlias: false,
      serviceDisabled: true,
      gatewayRunning: false,
      socketStale: false,
      profileDrift: "",
      missingConfiguredPathCount: 0,
      unsafeCrons: [],
      missingChannelMembership: [],
      staleSessionCount: 0,
      activeAgents: 0,
    });
    assert.deepEqual(actions.map((action) => action.type), ["enable_launchd_service", "start_gateway", "report"]);
  });

  it("refreshes a stale managed service definition while the gateway is running", () => {
    const actions = decideActions(profile, {
      needsProfileAlias: false,
      serviceDisabled: false,
      serviceDefinitionStale: true,
      gatewayRunning: true,
      socketStale: false,
      profileDrift: "",
      missingConfiguredPathCount: 0,
      unsafeCrons: [],
      missingChannelMembership: [],
      staleSessionCount: 0,
      activeAgents: 0,
    });
    assert.deepEqual(actions.map((action) => action.type), ["refresh_gateway_service", "report"]);
  });

  it("summarizes repair actions for ledger and dry-run output", () => {
    const actions = decideActions(profile, {
      needsProfileAlias: false,
      serviceDisabled: false,
      gatewayRunning: true,
      socketStale: true,
      profileDrift: "profile-drift:soul",
      missingConfiguredPathCount: 2,
      unsafeCrons: [],
      missingChannelMembership: [],
      staleSessionCount: 0,
      activeAgents: 0,
    });
    const summary = summarizeFacts(profile, {
      gatewayRunning: true,
      socketStale: true,
      profileDrift: "profile-drift:soul",
      missingConfiguredPathCount: 2,
      unsafeCrons: [],
      missingChannelMembership: [],
    }, actions);
    assert.equal(summary.profile, "nurtureanysalesbot");
    assert.deepEqual(summary.actions.map((action) => action.type), ["restart_gateway", "sync_profile", "repair_profile_paths", "report"]);
  });
});
