import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { join } from "node:path";
import { tmpdir } from "node:os";
import test from "node:test";
import {
  IntercomArticleClient,
  buildArticleInventory,
  buildArticlePlanningProfile,
  buildInventoryRecord,
  buildArticleShapeRecord,
  buildFormatProfile,
  checkArticleShapeFreshness,
  checkPantheonEvidence,
  checkDraftFormat,
  directIntercomArticleUrl,
  evaluateHelpArticleIntake,
  findAffectedArticles,
  markdownToIntercomHtml,
  planHelpArticles,
  scanPantheonEvidence,
  stageArticleUpdate
} from "./intercom-format-gate.mjs";

function response(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    async json() {
      return body;
    },
    async text() {
      return JSON.stringify(body);
    }
  };
}

function goodArticle(overrides = {}) {
  return {
    id: "101",
    title: "Managing Brands",
    url: "https://help.staffany.com/en/articles/101-managing-brands",
    state: "published",
    updated_at: 1710000000,
    body: [
      "<p><strong>Contents of this article are applicable to the following users</strong></p>",
      "<p>Tier: Growth</p>",
      "<p>Product: StaffAny</p>",
      "<p>Platform: Web</p>",
      "<p>Access Level: Owner, Manager</p>",
      "<p>Use brands to manage employee-facing business profiles.</p>",
      "<p><strong>This guide will cover how to:</strong></p>",
      "<ol><li>Create brands</li><li>Manage perks</li></ol>",
      "<h2>Managing Brands</h2>",
      "<p>Brands are business profiles.</p>",
      "<h2>FAQ</h2>",
      "<p><strong>Q: Can staff see inactive brands?</strong></p>",
      "<p>No.</p>"
    ].join("\n"),
    ...overrides
  };
}

function newJoinerArticle(overrides = {}) {
  return goodArticle({
    id: "14460084",
    title: "Creating and Managing New Joiner Form",
    url: "https://help.staffany.com/en/articles/14460084-creating-and-managing-new-joiner-form",
    body: [
      "<p><strong>Contents of this article are applicable to the following users</strong></p>",
      "<p>Product: HRAny</p>",
      "<p>Platform: Web</p>",
      "<p>Access Level: Manager/Owner</p>",
      "<p>Use New Joiner Form to collect new hire details.</p>",
      "<p><strong>This guide will cover how to:</strong></p>",
      "<ol><li>Create a new joiner form</li><li>Edit an existing form</li></ol>",
      "<h1>Create a new joiner form</h1>",
      "<h2>Edit an Existing Form</h2>",
      "<h1>FAQ</h1>",
      "<p><strong>Q: Who can create forms?</strong></p>",
      "<p>Owners and managers.</p>"
    ].join("\n"),
    ...overrides
  });
}

function run(command, args, cwd) {
  const result = spawnSync(command, args, { cwd, encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  return result;
}

function createPantheonFixture({ dirty = false } = {}) {
  const repo = mkdtempSync(join(tmpdir(), "launchbot-pantheon-"));
  run("git", ["init"], repo);
  run("git", ["config", "user.email", "launchbot@example.com"], repo);
  run("git", ["config", "user.name", "Launchbot Test"], repo);
  for (const app of ["gryphon", "pixie", "kraken", "manticore"]) {
    mkdirSync(join(repo, "apps", app), { recursive: true });
    writeFileSync(join(repo, "apps", app, "AGENTS.md"), `# ${app} guide\n`, "utf8");
  }
  mkdirSync(join(repo, "apps", "gryphon", "src", "clubany"), { recursive: true });
  writeFileSync(
    join(repo, "apps", "gryphon", "src", "clubany", "BrandPerkPage.tsx"),
    [
      "export const ClubAnyBrandPerkPage = () => null",
      "const labels = ['ClubAny', 'Brand', 'Perk', 'Active', 'Inactive', 'Owner']",
      "const route = '/clubany/brands/:brandId/perks'",
      "const accessLevel = 'Owner'"
    ].join("\n"),
    "utf8"
  );
  mkdirSync(join(repo, "apps", "pixie", "src", "clubany"), { recursive: true });
  writeFileSync(
    join(repo, "apps", "pixie", "src", "clubany", "Catalogue.tsx"),
    [
      "export const ClubAnyCatalogue = () => null",
      "const labels = ['ClubAny', 'Mobile', 'redeem', 'active brand', 'active perk']",
      "const route = 'ClubAnyCatalogueScreen'"
    ].join("\n"),
    "utf8"
  );
  mkdirSync(join(repo, "apps", "kraken", "src", "server", "clubany"), { recursive: true });
  writeFileSync(
    join(repo, "apps", "kraken", "src", "server", "clubany", "routes.ts"),
    [
      "export const clubAnyRoutes = ['/club-blue/catalog/perks/{id}/redeem']",
      "export const models = ['ClubBlueBrands', 'ClubBluePerks', 'ClubBlueRedemptions']"
    ].join("\n"),
    "utf8"
  );
  run("git", ["add", "."], repo);
  run("git", ["commit", "-m", "fixture"], repo);
  if (dirty) {
    writeFileSync(join(repo, "apps", "gryphon", "src", "clubany", "dirty.ts"), "export const dirty = true\n", "utf8");
  }
  return repo;
}

test("Intercom client searches with safe read-only query parameters", async () => {
  const calls = [];
  const client = new IntercomArticleClient({
    token: "test-token",
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return response(200, { total_count: 0, data: { articles: [], highlights: [] } });
    }
  });

  await client.searchArticles({ phrase: "brand perks", state: "published", helpCenterId: "123", highlight: true });

  assert.equal(calls.length, 1);
  assert.equal(calls[0].options.method, "GET");
  assert.equal(calls[0].url.pathname, "/articles/search");
  assert.equal(calls[0].url.searchParams.get("phrase"), "brand perks");
  assert.equal(calls[0].url.searchParams.get("state"), "published");
  assert.equal(calls[0].url.searchParams.get("help_center_id"), "123");
  assert.equal(calls[0].options.headers.Authorization, "Bearer test-token");
});

test("findAffectedArticles falls back from published to all state", async () => {
  const states = [];
  const client = new IntercomArticleClient({
    token: "test-token",
    fetchImpl: async (url, options) => {
      states.push(url.searchParams.get("state"));
      if (url.searchParams.get("state") === "published") {
        return response(200, { total_count: 0, data: { articles: [], highlights: [] } });
      }
      return response(200, {
        total_count: 1,
        data: { articles: [goodArticle({ title: "Brand draft" })], highlights: ["brand"] }
      });
    }
  });

  const result = await findAffectedArticles({ client, topic: "brand", appId: "abc123" });

  assert.deepEqual(states, ["published", "all"]);
  assert.equal(result.state_used, "all");
  assert.equal(result.articles[0].confidence, "high");
  assert.equal(result.articles[0].direct_edit_url, "https://app.intercom.com/a/apps/abc123/articles/articles/101/show");
});

test("client surfaces Intercom auth and not-found failures", async () => {
  const client = new IntercomArticleClient({
    token: "test-token",
    fetchImpl: async () => response(401, { error: "unauthorized" })
  });

  await assert.rejects(
    () => client.getArticle("404"),
    /Intercom GET \/articles\/404 failed: 401/
  );
});

test("createStagingDraft only sends draft state", async () => {
  let payload;
  const client = new IntercomArticleClient({
    token: "test-token",
    fetchImpl: async (url, options) => {
      payload = JSON.parse(options.body);
      return response(200, { id: "202", state: "draft" });
    }
  });

  await client.createStagingDraft({
    title: "Draft",
    body: "<p>Body</p>",
    authorId: 1,
    parentId: 2
  });

  assert.equal(payload.state, "draft");
  assert.equal(payload.parent_type, "collection");
});

test("buildFormatProfile stores normalized fingerprints only", () => {
  const profile = buildFormatProfile([goodArticle()], {
    appId: "abc123",
    generatedAt: "2026-05-14T00:00:00.000Z"
  });

  assert.equal(profile.profile_status, "live_intercom_profile");
  assert.equal(profile.write_boundary, "read_stage_only");
  assert.equal(profile.publish_mode, "draft_only");
  assert.equal(profile.reference_articles[0].structure.has_audience_block, true);
  assert.equal(profile.reference_articles[0].structure.has_faq, true);
  assert.equal(profile.reference_articles[0].direct_edit_url, directIntercomArticleUrl("101", "abc123"));
  assert.equal(profile.reference_articles[0].body, undefined);
});

test("buildArticlePlanningProfile stores normalized shape evidence only", () => {
  const profile = buildArticlePlanningProfile([
    { family: "new_joiner_onboarding", article: newJoinerArticle() },
    { family: "clubany", article: goodArticle({ id: "14083228", title: "Managing Brands and Perks on ClubAny" }) }
  ], {
    appId: "abc123",
    generatedAt: "2026-05-14T00:00:00.000Z"
  });

  assert.equal(profile.profile_status, "curated_intercom_shape_profile");
  assert.equal(profile.source_strategy, "karpathy_style_ingest_cached_profile_with_targeted_live_checks");
  assert.deepEqual(profile.live_intercom_usage, ["shape_refresh", "affected_article_search", "pre_stage_stale_check"]);
  assert.equal(profile.rules.raw_html_committed, false);
  const newJoinerFamily = profile.families.find((family) => family.id === "new_joiner_onboarding");
  assert.equal(newJoinerFamily.reference_articles[0].body, undefined);
  assert.equal(newJoinerFamily.reference_articles[0].structure.has_audience_block, true);
  assert.equal(newJoinerFamily.reference_articles[0].structure.has_guide_outline, true);
  assert.ok(newJoinerFamily.reference_articles[0].structure.structural_fingerprint);
});

test("buildArticleShapeRecord infers family audience platform and workflow", () => {
  const record = buildArticleShapeRecord(newJoinerArticle(), { family: "new_joiner_onboarding" });

  assert.equal(record.family, "new_joiner_onboarding");
  assert.deepEqual(record.product_labels, ["HRAny"]);
  assert.deepEqual(record.platform_labels, ["Web"]);
  assert.ok(record.audience_labels.includes("Owner"));
  assert.ok(record.audience_labels.includes("Manager"));
  assert.ok(record.workflow_tags.includes("onboarding"));
  assert.ok(record.workflow_tags.includes("create"));
});

test("buildArticleInventory stores metadata and derived signals without body content", () => {
  const profile = buildArticlePlanningProfile([{ family: "new_joiner_onboarding", article: newJoinerArticle() }]);
  const inventory = buildArticleInventory([
    newJoinerArticle(),
    goodArticle({ id: "14083228", title: "Managing Brands and Perks on ClubAny" })
  ], {
    appId: "abc123",
    profile,
    generatedAt: "2026-05-14T00:00:00.000Z"
  });

  assert.equal(inventory.inventory_status, "live_intercom_metadata_inventory");
  assert.equal(inventory.raw_body_committed, false);
  assert.equal(inventory.aggregate.article_count, 2);
  assert.equal(inventory.articles[0].body, undefined);
  assert.equal(inventory.articles[0].body_markdown, undefined);
  assert.ok(inventory.articles[0].content_signals.heading_texts.includes("Create a new joiner form"));
  assert.equal(inventory.articles[0].quality_label, "strong_reference");
  assert.equal(inventory.articles[1].inferred_family, "clubany");
});

test("buildInventoryRecord marks weak or uncategorized articles for review", () => {
  const weak = buildInventoryRecord(goodArticle({
    id: "999",
    title: "Legacy Test Article",
    state: "draft",
    body: "<p>short</p>"
  }));

  assert.equal(weak.quality_label, "deprecated_or_weak");
  assert.equal(weak.content_signals.word_count, 1);
});

test("planHelpArticles recommends cached family split before drafting", () => {
  const profile = buildArticlePlanningProfile([
    { family: "new_joiner_onboarding", article: newJoinerArticle() }
  ]);
  const result = planHelpArticles({
    topic: "new joiner onboarding form",
    profile,
    affectedArticles: {
      state_used: "published",
      total_count: 1,
      articles: [{
        id: "14460084",
        title: "Creating and Managing New Joiner Form",
        url: "https://help.staffany.com/en/articles/14460084-creating-and-managing-new-joiner-form",
        state: "published",
        updated_at: 1778757112,
        direct_edit_url: "https://app.intercom.com/a/apps/abc/articles/articles/14460084/show",
        confidence: "high"
      }]
    },
    generatedAt: "2026-05-14T00:00:00.000Z"
  });

  assert.equal(result.status, "pass");
  assert.equal(result.selected_family.id, "new_joiner_onboarding");
  assert.equal(result.recommended_mode, "mixed");
  assert.ok(result.recommended_articles.some((article) => article.title === "Creating and Managing New Joiner Form"));
  assert.ok(result.recommended_articles.some((article) => article.workflow === "new hire form submission"));
});

test("planHelpArticles uses cached inventory when live affected search is absent", () => {
  const profile = buildArticlePlanningProfile([
    { family: "clubany", article: goodArticle({ id: "14083228", title: "Managing Brands and Perks on ClubAny" }) }
  ]);
  const inventory = buildArticleInventory([
    goodArticle({ id: "14083228", title: "Managing Brands and Perks on ClubAny" }),
    goodArticle({ id: "14083405", title: "Redeeming ClubAny Perks", body: goodArticle().body.replace("Platform: Web", "Platform: Mobile") })
  ], { profile });
  const result = planHelpArticles({
    topic: "ClubAny brands and perks",
    profile,
    inventory,
    generatedAt: "2026-05-14T00:00:00.000Z"
  });

  assert.equal(result.status, "pass");
  assert.equal(result.inventory_lookup.used_for_affected_articles, true);
  assert.equal(result.affected_article_search.state_used, "inventory");
  assert.ok(result.warnings.includes("affected_articles_from_cached_inventory"));
  assert.ok(result.recommended_articles.some((article) => article.source_article_id === "14083228"));
});

test("planHelpArticles passes broad clear ClubAny topic without explicit intake", () => {
  const profile = buildArticlePlanningProfile([
    { family: "clubany", article: goodArticle({ id: "14083228", title: "Managing Brands and Perks on ClubAny" }) },
    { family: "clubany", article: goodArticle({ id: "14083405", title: "Redeeming ClubAny Perks", body: goodArticle().body.replace("Platform: Web", "Platform: Mobile") }) }
  ]);
  const result = planHelpArticles({
    topic: "ClubAny brands and perks",
    profile,
    generatedAt: "2026-05-14T00:00:00.000Z"
  });

  assert.equal(result.status, "pass");
  assert.equal(result.intake.status, "pass");
  assert.equal(result.selected_family.id, "clubany");
  assert.equal(result.recommended_articles.length, 2);
  assert.ok(result.recommended_articles.some((article) => article.title === "Managing Brands and Perks on ClubAny"));
  assert.ok(result.recommended_articles.some((article) => article.title === "Redeeming ClubAny Perks"));
});

test("planHelpArticles returns needs-intake for vague topics", () => {
  const profile = buildArticlePlanningProfile([{ family: "clubany", article: goodArticle() }]);
  const result = planHelpArticles({
    topic: "new thing",
    profile
  });

  assert.equal(result.status, "needs-intake");
  assert.deepEqual(result.intake.missing_fields, ["article_family", "surface", "audience", "desired_outcome"]);
  assert.ok(result.intake.questions.some((question) => question.includes("Which feature or workflow family")));
  assert.equal(result.affected_article_search, null);
  assert.deepEqual(result.recommended_articles, []);
});

test("planHelpArticles accepts explicit high-impact intake for short topics", () => {
  const profile = buildArticlePlanningProfile([
    { family: "clubany", article: goodArticle({ id: "14083228", title: "Managing Brands and Perks on ClubAny" }) }
  ]);
  const result = planHelpArticles({
    topic: "perks",
    profile,
    intake: {
      surface: "Web",
      audience: "Owner",
      outcome: "manage brands and perks"
    }
  });

  assert.equal(result.status, "pass");
  assert.equal(result.intake.confidence, "high");
  assert.equal(result.intake.provided.surface, "Web");
  assert.equal(result.selected_family.id, "clubany");
});

test("planHelpArticles asks for family clarification when topic is ambiguous", () => {
  const profile = {
    profile_status: "test",
    families: [
      {
        id: "claims",
        label: "Claims",
        keywords: ["approval"],
        split_rule: "Split claim approval from submission.",
        default_mode: "mixed",
        planning_model: []
      },
      {
        id: "leave",
        label: "Leave",
        keywords: ["approval"],
        split_rule: "Split leave approval from request submission.",
        default_mode: "mixed",
        planning_model: []
      }
    ]
  };
  const result = planHelpArticles({
    topic: "approval",
    profile,
    intake: {
      surface: "Web",
      audience: "Manager"
    }
  });

  assert.equal(result.status, "needs-intake");
  assert.ok(result.intake.missing_fields.includes("article_family"));
  assert.ok(result.intake.questions.some((question) => question.includes("multiple likely article families")));
});

test("evaluateHelpArticleIntake returns stable contract fields", () => {
  const profile = buildArticlePlanningProfile([
    { family: "clubany", article: goodArticle({ id: "14083228", title: "Managing Brands and Perks on ClubAny" }) }
  ]);
  const result = evaluateHelpArticleIntake({
    topic: "ClubAny brands and perks",
    profile,
    selectedFamily: profile.families[0],
    topFamilies: [profile.families[0]]
  });

  assert.equal(result.status, "pass");
  assert.ok(result.inferred.surface.includes("Web"));
  assert.ok(result.inferred.audience.includes("Owner"));
  assert.deepEqual(result.missing_fields, []);
  assert.deepEqual(result.questions, []);
});

test("help-article:plan needs-intake does not call live Intercom search", async () => {
  const temp = mkdtempSync(join(tmpdir(), "launchbot-plan-intake-"));
  try {
    const profilePath = join(temp, "profile.json");
    const inventoryPath = join(temp, "missing-inventory.json");
    writeFileSync(
      profilePath,
      JSON.stringify(buildArticlePlanningProfile([{ family: "clubany", article: goodArticle() }]), null, 2),
      "utf8"
    );

    const { main } = await import("./intercom-format-gate.mjs");
    const originalWrite = process.stdout.write;
    const originalIntercomToken = process.env.INTERCOM_ACCESS_TOKEN;
    const originalStep3Token = process.env.LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN;
    delete process.env.INTERCOM_ACCESS_TOKEN;
    delete process.env.LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN;
    let output = "";
    process.stdout.write = (chunk) => {
      output += chunk;
      return true;
    };
    try {
      await main([
        "help-article:plan",
        "--topic",
        "new thing",
        "--profile",
        profilePath,
        "--inventory",
        inventoryPath
      ]);
    } finally {
      process.stdout.write = originalWrite;
      if (originalIntercomToken === undefined) delete process.env.INTERCOM_ACCESS_TOKEN;
      else process.env.INTERCOM_ACCESS_TOKEN = originalIntercomToken;
      if (originalStep3Token === undefined) delete process.env.LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN;
      else process.env.LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN = originalStep3Token;
    }

    const result = JSON.parse(output);
    assert.equal(result.status, "needs-intake");
    assert.equal(result.affected_article_search, null);
  } finally {
    rmSync(temp, { recursive: true, force: true });
  }
});

test("checkArticleShapeFreshness passes matching cached target article", () => {
  const article = newJoinerArticle({ updated_at: 123 });
  const profile = buildArticlePlanningProfile([{ family: "new_joiner_onboarding", article }]);
  const result = checkArticleShapeFreshness({ liveArticle: article, profile });

  assert.equal(result.status, "pass");
  assert.deepEqual(result.errors, []);
  assert.equal(result.cached_updated_at, 123);
  assert.equal(result.live_updated_at, 123);
});

test("checkArticleShapeFreshness blocks stale cached target article", () => {
  const cached = newJoinerArticle({ updated_at: 123 });
  const live = newJoinerArticle({
    updated_at: 456,
    body: cached.body.replace("<h1>FAQ</h1>", "<h1>Important FAQ</h1>")
  });
  const profile = buildArticlePlanningProfile([{ family: "new_joiner_onboarding", article: cached }]);
  const result = checkArticleShapeFreshness({ liveArticle: live, profile });

  assert.equal(result.status, "needs-refresh");
  assert.ok(result.errors.includes("cached_article_updated_at_stale"));
  assert.ok(result.errors.includes("cached_article_shape_fingerprint_stale"));
});

test("markdownToIntercomHtml converts headings and real lists", () => {
  const html = markdownToIntercomHtml("## Heading\n\n1. First\n2. Second\n\n**Bold line**");

  assert.match(html, /<h2>Heading<\/h2>/);
  assert.match(html, /<ol>/);
  assert.match(html, /<strong>Bold line<\/strong>/);
});

test("format gate passes a good StaffAny draft", () => {
  const profile = buildFormatProfile([goodArticle()]);
  const result = checkDraftFormat({
    title: "New StaffAny Article",
    profile,
    draft: [
      "<p><strong>Contents of this article are applicable to the following users</strong></p>",
      "<p>Tier: Growth</p>",
      "<p>Product: StaffAny</p>",
      "<p>Platform: Web</p>",
      "<p>Access Level: Owner</p>",
      "<p>Manage this workflow from StaffAny.</p>",
      "<p><strong>This guide will cover how to:</strong></p>",
      "<ol><li>Set up the feature</li></ol>",
      "<h2>Set up the feature</h2>",
      "<p>Use the setup page.</p>",
      "<h2>FAQ</h2>",
      "<p><strong>Q: Who can use this?</strong></p>",
      "<p>Owners can use it.</p>"
    ].join("\n")
  });

  assert.equal(result.status, "pass");
  assert.deepEqual(result.errors, []);
  assert.equal(result.closest_reference_article.id, "101");
});

test("format gate passes when Tier is omitted", () => {
  const result = checkDraftFormat({
    title: "No Tier",
    profile: buildFormatProfile([goodArticle()]),
    draft: [
      "<p><strong>Contents of this article are applicable to the following users</strong></p>",
      "<p>Product: StaffAny</p>",
      "<p>Platform: Web</p>",
      "<p>Access Level: Owner</p>",
      "<p><strong>This guide will cover how to:</strong></p>",
      "<ol><li>Set up the feature</li></ol>",
      "<h2>Set up the feature</h2>",
      "<p>Use the setup page.</p>",
      "<h2>FAQ</h2>",
      "<p><strong>Q: Who can use this?</strong></p>",
      "<p>Owners can use it.</p>"
    ].join("\n")
  });

  assert.equal(result.status, "pass");
});

test("format gate still fails when Product is omitted", () => {
  const result = checkDraftFormat({
    title: "No Product",
    profile: buildFormatProfile([goodArticle()]),
    draft: "<p><strong>Contents of this article are applicable to the following users</strong></p><p>Platform: Web</p><p>Access Level: Owner</p><ol><li>One</li></ol><h2>FAQ</h2><p><strong>Q: Test?</strong></p><p>Yes.</p>"
  });

  assert.equal(result.status, "fail");
  assert.ok(result.errors.includes("missing_audience_metadata"));
});

test("format gate fails missing audience metadata", () => {
  const result = checkDraftFormat({
    title: "Missing audience",
    profile: buildFormatProfile([goodArticle()]),
    draft: "<p>No audience block.</p><ol><li>One</li></ol><h2>FAQ</h2><p><strong>Q: Test?</strong></p><p>Yes.</p>"
  });

  assert.equal(result.status, "fail");
  assert.ok(result.errors.includes("missing_audience_metadata"));
});

test("format gate fails repeated title in body", () => {
  const result = checkDraftFormat({
    title: "Repeated Title",
    profile: buildFormatProfile([goodArticle()]),
    draft: "<p>Repeated Title</p><p><strong>Contents of this article are applicable to the following users</strong></p><p>Tier: Growth</p><p>Product: StaffAny</p><p>Platform: Web</p><p>Access Level: Owner</p><ol><li>One</li></ol><h2>FAQ</h2><p><strong>Q: Test?</strong></p><p>Yes.</p>"
  });

  assert.equal(result.status, "fail");
  assert.ok(result.errors.includes("repeated_title_in_body"));
});

test("format gate fails raw HTML or markdown leakage", () => {
  const result = checkDraftFormat({
    title: "Raw leak",
    profile: buildFormatProfile([goodArticle()]),
    draft: "<p>&lt;div style=\"text-align:center\"&gt;bad&lt;/div&gt;</p><p><strong>Contents of this article are applicable to the following users</strong></p><p>Tier: Growth</p><p>Product: StaffAny</p><p>Platform: Web</p><p>Access Level: Owner</p><ol><li>One</li></ol><h2>FAQ</h2><p><strong>Q: Test?</strong></p><p>Yes.</p>"
  });

  assert.equal(result.status, "fail");
  assert.ok(result.errors.includes("raw_html_or_markdown_leakage"));
});

test("format gate fails internal appendix content", () => {
  const result = checkDraftFormat({
    title: "Appendix",
    profile: buildFormatProfile([goodArticle()]),
    draft: "<p><strong>Contents of this article are applicable to the following users</strong></p><p>Tier: Growth</p><p>Product: StaffAny</p><p>Platform: Web</p><p>Access Level: Owner</p><ol><li>One</li></ol><h2>FAQ</h2><p><strong>Q: Test?</strong></p><p>Yes.</p><h2>Internal Appendix</h2><p>Last verified commit abc.</p>"
  });

  assert.equal(result.status, "fail");
  assert.ok(result.errors.includes("internal_appendix"));
});

test("format gate fails bad plain-text list numbering", () => {
  const result = checkDraftFormat({
    title: "Bad list",
    profile: buildFormatProfile([goodArticle()]),
    draft: "<p><strong>Contents of this article are applicable to the following users</strong></p><p>Tier: Growth</p><p>Product: StaffAny</p><p>Platform: Web</p><p>Access Level: Owner</p><p>1. This is not a real ordered list.</p><h2>FAQ</h2><p><strong>Q: Test?</strong></p><p>Yes.</p>"
  });

  assert.equal(result.status, "fail");
  assert.ok(result.errors.includes("bad_list_numbering"));
});

test("Pantheon scanner blocks missing repo", () => {
  const result = scanPantheonEvidence({
    topic: "ClubAny brands",
    repoPath: join(tmpdir(), "missing-pantheon-repo")
  });

  assert.equal(result.status, "needs-check");
  assert.ok(result.errors.includes("missing_pantheon_repo"));
});

test("Pantheon scanner blocks dirty repo", () => {
  const repo = createPantheonFixture({ dirty: true });
  try {
    const result = scanPantheonEvidence({
      topic: "ClubAny brands perks",
      app: "gryphon",
      repoPath: repo
    });

    assert.equal(result.status, "needs-check");
    assert.ok(result.errors.includes("dirty_pantheon_repo"));
  } finally {
    rmSync(repo, { recursive: true, force: true });
  }
});

test("Pantheon scanner marks broad multi-app topic as ambiguous", () => {
  const repo = createPantheonFixture();
  try {
    const result = scanPantheonEvidence({
      topic: "ClubAny brands perks",
      repoPath: repo
    });

    assert.equal(result.status, "needs-check");
    assert.ok(result.errors.some((error) => error.startsWith("ambiguous_pantheon_app")));
    assert.ok(result.matched_apps.includes("gryphon"));
    assert.ok(result.matched_apps.includes("pixie"));
    assert.ok(result.matched_apps.includes("kraken"));
  } finally {
    rmSync(repo, { recursive: true, force: true });
  }
});

test("Pantheon scanner passes with explicit Gryphon and Kraken scope", () => {
  const repo = createPantheonFixture();
  try {
    const result = scanPantheonEvidence({
      topic: "ClubAny brands perks",
      app: "gryphon,kraken",
      repoPath: repo,
      generatedAt: "2026-05-14T00:00:00.000Z"
    });

    assert.equal(result.status, "pass");
    assert.deepEqual(result.requested_apps, ["gryphon", "kraken"]);
    assert.ok(result.matched_apps.includes("gryphon"));
    assert.ok(result.matched_apps.includes("kraken"));
    assert.ok(result.app_guidance.every((item) => item.exists));
    assert.ok(result.evidence.api_data_touchpoints.length > 0);
    assert.ok(result.verified_terms.includes("clubany"));
  } finally {
    rmSync(repo, { recursive: true, force: true });
  }
});

test("Pantheon evidence check passes a supported Web article", () => {
  const repo = createPantheonFixture();
  try {
    const evidence = scanPantheonEvidence({
      topic: "ClubAny brands perks",
      app: "gryphon,kraken",
      repoPath: repo
    });
    const result = checkPantheonEvidence({
      title: "Managing ClubAny Brands",
      evidence,
      evidencePath: "/tmp/evidence.json",
      draft: [
        "<p><strong>Contents of this article are applicable to the following users</strong></p>",
        "<p>Product: StaffAny</p>",
        "<p>Platform: Web</p>",
        "<p>Access Level: Owner</p>",
        "<p>Owners can manage ClubAny brands and perks from Web.</p>",
        "<h2>FAQ</h2>"
      ].join("\n")
    });

    assert.equal(result.status, "pass");
    assert.equal(result.pantheon_evidence_path, "/tmp/evidence.json");
    assert.ok(result.source_files.some((path) => path.includes("BrandPerkPage")));
  } finally {
    rmSync(repo, { recursive: true, force: true });
  }
});

test("Pantheon evidence check blocks missing Mobile evidence", () => {
  const repo = createPantheonFixture();
  try {
    const evidence = scanPantheonEvidence({
      topic: "ClubAny brands perks",
      app: "gryphon",
      repoPath: repo
    });
    const result = checkPantheonEvidence({
      title: "Managing ClubAny Brands",
      evidence,
      draft: "<p>Product: StaffAny</p><p>Platform: Mobile</p><p>Access Level: Employee</p><p>Employees can redeem ClubAny perks.</p>"
    });

    assert.equal(result.status, "needs-check");
    assert.ok(result.errors.includes("missing_mobile_pantheon_evidence"));
  } finally {
    rmSync(repo, { recursive: true, force: true });
  }
});

test("Pantheon evidence check blocks internal app names and unsupported claims", () => {
  const repo = createPantheonFixture();
  try {
    const evidence = scanPantheonEvidence({
      topic: "ClubAny brands perks",
      app: "gryphon",
      repoPath: repo
    });
    const result = checkPantheonEvidence({
      title: "Managing ClubAny Brands",
      evidence,
      draft: [
        "<p>Product: StaffAny</p>",
        "<p>Platform: Web</p>",
        "<p>Access Level: Owner</p>",
        "<p>Gryphon users can manage ClubAny brands.</p>",
        "<p>Magic wallets automatically publish payroll reports for every outlet.</p>"
      ].join("\n")
    });

    assert.equal(result.status, "needs-check");
    assert.ok(result.errors.includes("internal_pantheon_app_name_leakage"));
    assert.ok(result.errors.includes("unsupported_product_behavior_claim"));
  } finally {
    rmSync(repo, { recursive: true, force: true });
  }
});

test("stageArticleUpdate emits safe staging contract without Intercom writes", () => {
  const repo = createPantheonFixture();
  let staged;
  try {
    const evidence = scanPantheonEvidence({
      topic: "ClubAny brands perks",
      app: "gryphon",
      repoPath: repo
    });
    staged = stageArticleUpdate({
      sourceArticle: goodArticle({ id: "303", description: "Old description" }),
      title: "Managing Brands Updated",
      description: "Updated description",
      profile: buildFormatProfile([goodArticle()]),
      pantheonEvidence: evidence,
      pantheonEvidencePath: "/tmp/pantheon-evidence.json",
      articleShapeFreshness: {
        status: "pass",
        errors: [],
        warnings: [],
        source_article_id: "303"
      },
      appId: "abc123",
      previewPath: "/tmp/preview.html",
      draft: [
        "<p><strong>Contents of this article are applicable to the following users</strong></p>",
        "<p>Tier: Growth</p>",
        "<p>Product: StaffAny</p>",
        "<p>Platform: Web</p>",
        "<p>Access Level: Owner</p>",
        "<p>Owners can manage ClubAny brands and perks from Web.</p>",
        "<p><strong>This guide will cover how to:</strong></p>",
        "<ol><li>Review brands</li></ol>",
        "<h2>Review brands</h2>",
        "<p>Check the brand setup.</p>",
        "<h2>FAQ</h2>",
        "<p><strong>Q: Does this publish?</strong></p>",
        "<p>No.</p>"
      ].join("\n")
    });
  } finally {
    rmSync(repo, { recursive: true, force: true });
  }

  assert.equal(staged.status, "pass");
  assert.equal(staged.source_article_id, "303");
  assert.equal(staged.direct_intercom_edit_url, "https://app.intercom.com/a/apps/abc123/articles/articles/303/show");
  assert.equal(staged.proposed_title, "Managing Brands Updated");
  assert.equal(staged.proposed_description, "Updated description");
  assert.equal(staged.format_gate_result.status, "pass");
  assert.equal(staged.pantheon_evidence_result.status, "pass");
  assert.equal(staged.article_shape_stale_check.status, "pass");
  assert.equal(staged.pantheon_evidence_path, "/tmp/pantheon-evidence.json");
  assert.equal(staged.approval_status, "not_requested");
  assert.equal(staged.writes_to_intercom, false);
});

test("format-check command writes preview under supplied cache path", async () => {
  const temp = mkdtempSync(join(tmpdir(), "launchbot-format-"));
  try {
    const draftPath = join(temp, "draft.md");
    const profilePath = join(temp, "profile.json");
    writeFileSync(
      draftPath,
      [
        "**Contents of this article are applicable to the following users**",
        "Tier: Growth",
        "Product: StaffAny",
        "Platform: Web",
        "Access Level: Owner",
        "",
        "**This guide will cover how to:**",
        "1. Do the thing",
        "",
        "## Main",
        "Use the page.",
        "",
        "## FAQ",
        "**Q: Test?**",
        "Yes."
      ].join("\n"),
      "utf8"
    );
    writeFileSync(profilePath, JSON.stringify(buildFormatProfile([goodArticle()]), null, 2), "utf8");

    const { main } = await import("./intercom-format-gate.mjs");
    const originalWrite = process.stdout.write;
    let output = "";
    process.stdout.write = (chunk) => {
      output += chunk;
      return true;
    };
    try {
      await main([
        "help-article:format-check",
        "--draft",
        draftPath,
        "--profile",
        profilePath,
        "--preview-dir",
        temp,
        "--title",
        "Draft"
      ]);
    } finally {
      process.stdout.write = originalWrite;
    }
    const result = JSON.parse(output);
    assert.equal(result.status, "pass");
    assert.equal(result.rendered_preview_path, join(temp, "draft.intercom-preview.html"));
    assert.match(readFileSync(result.rendered_preview_path, "utf8"), /<ol>/);
  } finally {
    rmSync(temp, { recursive: true, force: true });
  }
});
