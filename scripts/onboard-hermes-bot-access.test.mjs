import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  BOT_REGISTRY,
  CUSTOM_METADATA_ROLE,
  assertSafeRole,
  buildGrantPlan,
  commandsToRun,
} from "./onboard-hermes-bot-access.mjs";

function commandText(command) {
  return command.join(" ");
}

function isMutatingCommand(command) {
  const text = commandText(command);
  return text.includes(" add-iam-policy-binding ") || text.includes(" iam roles create ");
}

describe("Hermes bot deploy-access onboarding plan", () => {
  it("plans only PSM Ops VM and service-account grants for psm-ops-bot", () => {
    const plan = buildGrantPlan({ email: "jason@staffany.com", bot: "psm-ops-bot" });
    assert.deepEqual(plan.bots.map((bot) => bot.appSlug), ["psm-ops-bot"]);

    const instanceResources = new Set(
      plan.actions
        .filter((action) => action.type === "instanceBinding")
        .map((action) => action.resource),
    );
    assert.deepEqual(instanceResources, new Set(["hermes-psm-ops-bot-poc"]));

    const serviceAccounts = new Set(
      plan.actions
        .filter((action) => action.type === "serviceAccountBinding")
        .map((action) => action.resource),
    );
    assert.deepEqual(serviceAccounts, new Set(["hermes-psm-ops-bot@staffany-warehouse.iam.gserviceaccount.com"]));
    assert.equal([...instanceResources].includes("hermes-data-bot-poc"), false);
    assert.equal([...serviceAccounts].includes("hermes-data-bot@staffany-warehouse.iam.gserviceaccount.com"), false);
  });

  it("dedupes shared VM and service-account grants for all bots", () => {
    const plan = buildGrantPlan({ email: "jason@staffany.com", bot: "all" });
    assert.deepEqual(plan.bots.map((bot) => bot.appSlug), [
      "hermes-data-bot",
      "nurtureany-sales-bot",
      "psm-ops-bot",
      "launchbot",
    ]);

    const metadataVmGrants = plan.actions.filter((action) => (
      action.type === "instanceBinding" && action.role === CUSTOM_METADATA_ROLE
    ));
    assert.deepEqual(
      new Set(metadataVmGrants.map((action) => action.resource)),
      new Set(["hermes-data-bot-poc", "nurtureany-sales-bot-prod", "hermes-psm-ops-bot-poc"]),
    );

    const serviceAccountGrants = plan.actions.filter((action) => action.type === "serviceAccountBinding");
    assert.deepEqual(
      new Set(serviceAccountGrants.map((action) => action.resource)),
      new Set([
        BOT_REGISTRY["hermes-data-bot"].serviceAccount,
        BOT_REGISTRY["psm-ops-bot"].serviceAccount,
      ]),
    );
    assert.equal(serviceAccountGrants.length, 2);
  });

  it("does not include mutating gcloud commands without apply", () => {
    const plan = buildGrantPlan({ email: "jason@staffany.com", bot: "psm-ops-bot" });
    const dryRunCommands = commandsToRun(plan, { apply: false });
    assert.equal(dryRunCommands.some(isMutatingCommand), false);

    const applyCommands = commandsToRun(plan, { apply: true });
    assert.equal(applyCommands.some(isMutatingCommand), true);
  });

  it("refuses broad or secret-bearing roles", () => {
    assert.throws(() => assertSafeRole("roles/editor"), /Refusing to grant/);
    assert.throws(() => assertSafeRole("roles/compute.admin"), /Refusing to grant/);
    assert.throws(() => assertSafeRole("roles/secretmanager.secretAccessor"), /Refusing to grant/);
  });
});
