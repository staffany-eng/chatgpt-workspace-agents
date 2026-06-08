import test from "node:test";
import assert from "node:assert/strict";
import {
  MemoryStateStore,
  SHIPPED_STATUS,
  buildRunId,
  createWorkflow,
  isExactPublishConfirmation,
  launchBotMentioned,
} from "./launchbot_ker_help_article_on_shipped.mjs";

const baseEnv = {
  JIRA_BASE_URL: "https://staffany.atlassian.net",
  JIRA_FIELD_PRODUCT_LEAD: "customfield_12345",
  JIRA_FIELD_LAUNCH_PRIORITY: "customfield_10561",
  LAUNCHBOT_REVIEW_CHANNEL_ID: "C0B32M34J3W",
  LAUNCHBOT_INTERCOM_UPDATE_DRAFT_SUPPORTED: "true",
};

function shippedEvent(patch = {}) {
  return {
    event_source: "jira_automation",
    issue_key: "KER-123",
    issue_id: "10001",
    transition_from: "5 - In Delivery",
    transition_to: SHIPPED_STATUS,
    transitioned_at: "2026-06-02T10:00:00.000+0800",
    actor_account_id: "actor-1",
    ...patch,
  };
}

function jiraIssue(patch = {}) {
  return {
    id: "10001",
    key: "KER-123",
    url: "https://staffany.atlassian.net/browse/KER-123",
    status: SHIPPED_STATUS,
    summary: "Payroll approval export",
    description: "Add approval export",
    launchPriority: "P1",
    productLead: {
      accountId: "jira-lead-1",
      email: "lead@staffany.com",
      displayName: "Product Lead",
    },
    updated: "2026-06-02T09:59:00.000+0800",
    ...patch,
  };
}

function makeHarness({ issue = jiraIssue(), pipelinePatch = {}, env = {} } = {}) {
  const stateStore = new MemoryStateStore();
  const slackPosts = [];
  const intercomWrites = [];
  const published = [];
  let articleId = 1000;
  const jira = {
    async getIssue() {
      return issue;
    },
  };
  const slack = {
    async lookupUserByEmail(email) {
      return email === "lead@staffany.com" ? "U_LEAD" : "";
    },
    async postMessage(payload) {
      slackPosts.push(payload);
      return { channel: payload.channel, ts: payload.thread_ts || `1780000000.${String(slackPosts.length).padStart(6, "0")}` };
    },
  };
  const intercom = {
    async createDraftArticle(payload) {
      intercomWrites.push({ method: "create", payload });
      articleId += 1;
      return {
        id: String(articleId),
        url: `https://app.intercom.com/articles/${articleId}`,
        public_url: `https://help.staffany.com/articles/${articleId}`,
      };
    },
    async updateDraftArticle(payload) {
      intercomWrites.push({ method: "update", payload });
      return {
        id: payload.articleId,
        url: `https://app.intercom.com/articles/${payload.articleId}`,
      };
    },
    async readArticle(articleIdToRead) {
      return { id: String(articleIdToRead), state: "draft" };
    },
    async publishArticle(articleIdToPublish) {
      published.push(String(articleIdToPublish));
      return {
        id: String(articleIdToPublish),
        state: "published",
        public_url: `https://help.staffany.com/articles/${articleIdToPublish}`,
      };
    },
  };
  const articlePipeline = {
    async plan() {
      return {
        status: "pass",
        decision: "create",
        locales: {
          en: { action: "create", title: "Use Payroll Approval Export" },
          id: { action: "create", title: "Gunakan Ekspor Persetujuan Payroll" },
        },
      };
    },
    async scanPantheon() {
      return { status: "pass", evidence_paths: ["/tmp/pantheon-evidence.json"] };
    },
    async draftLocale({ locale }) {
      return { title: locale === "en" ? "Use Payroll Approval Export" : "Gunakan Ekspor Persetujuan Payroll", html: `<p>${locale} draft</p>` };
    },
    async evaluateLocale() {
      return { status: "pass" };
    },
    async applyFeedback() {
      return {
        locales: {
          en: { html: "<p>updated en draft</p>", gate_status: "pass" },
          id: { html: "<p>updated id draft</p>", gate_status: "pass" },
        },
      };
    },
    ...pipelinePatch,
  };
  const workflow = createWorkflow({
    env: { ...baseEnv, ...env },
    stateStore,
    jira,
    slack,
    intercom,
    articlePipeline,
    clock: () => new Date("2026-06-02T02:00:00.000Z"),
  });
  return { workflow, stateStore, slackPosts, intercomWrites, published };
}

test("helpers require Launch Bot mention and exact publish confirmation", () => {
  assert.equal(launchBotMentioned("@Launch Bot please update the English draft"), true);
  assert.equal(launchBotMentioned("please update the English draft"), false);
  assert.equal(isExactPublishConfirmation("@Launch Bot publish help articles KER-123", "KER-123"), true);
  assert.equal(isExactPublishConfirmation("@Launch Bot publish KER-123", "KER-123"), false);
});

test("duplicate webhook returns the existing run without regenerating drafts", async () => {
  const harness = makeHarness();
  const first = await harness.workflow.handleShippedWebhook(shippedEvent());
  const duplicate = await harness.workflow.handleShippedWebhook(shippedEvent());

  assert.equal(first.status, "review_requested");
  assert.equal(duplicate.status, "duplicate");
  assert.equal(harness.intercomWrites.length, 2);
  assert.equal(duplicate.run.run_id, buildRunId("KER-123", "2026-06-02T10:00:00.000+0800"));
});

test("missing launch priority blocks before drafting", async () => {
  const harness = makeHarness({ issue: jiraIssue({ launchPriority: "" }) });
  const result = await harness.workflow.handleShippedWebhook(shippedEvent());

  assert.equal(result.status, "blocked");
  assert.equal(result.run.status, "blocked");
  assert.equal(result.run.error_summary, "missing_launch_priority");
  assert.equal(harness.intercomWrites.length, 0);
  assert.match(harness.slackPosts[0].text, /missing_launch_priority/);
});

test("creates English and Indonesian Intercom drafts and posts product lead review", async () => {
  const harness = makeHarness();
  const result = await harness.workflow.handleShippedWebhook(shippedEvent());

  assert.equal(result.status, "review_requested");
  assert.equal(result.run.product_lead_slack_user_id, "U_LEAD");
  assert.equal(result.run.locales.en.action, "create");
  assert.equal(result.run.locales.id.action, "create");
  assert.equal(harness.intercomWrites.length, 2);
  assert.equal(harness.intercomWrites[0].payload.locale, "en");
  assert.equal(harness.intercomWrites[1].payload.locale, "id");
  assert.match(harness.slackPosts.at(-1).text, /<@U_LEAD>/);
  assert.match(harness.slackPosts.at(-1).text, /@Launch Bot publish help articles KER-123/);
});

test("feedback updates both locale drafts and asks for exact publish confirmation", async () => {
  const harness = makeHarness();
  const trigger = await harness.workflow.handleShippedWebhook(shippedEvent());
  const feedback = await harness.workflow.applyHelpArticleFeedback({
    run_id: trigger.run.run_id,
    slack_channel_id: trigger.run.slack_channel_id,
    slack_thread_ts: trigger.run.slack_thread_ts,
    slack_user_id: "U_LEAD",
    feedback_text: "@Launch Bot tighten the intro and update both locales",
  });

  assert.equal(feedback.status, "publish_confirmation_requested");
  assert.equal(harness.intercomWrites.filter((write) => write.method === "update").length, 2);
  assert.match(harness.slackPosts.at(-1).text, /publish help articles KER-123/);
});

test("non product lead publish confirmation is rejected", async () => {
  const harness = makeHarness();
  const trigger = await harness.workflow.handleShippedWebhook(shippedEvent());
  const rejected = await harness.workflow.publishHelpArticles({
    run_id: trigger.run.run_id,
    slack_user_id: "U_OTHER",
    confirmation_text: "@Launch Bot publish help articles KER-123",
  });

  assert.equal(rejected.status, "rejected");
  assert.equal(harness.published.length, 0);
});

test("exact product lead confirmation publishes both locales", async () => {
  const harness = makeHarness();
  const trigger = await harness.workflow.handleShippedWebhook(shippedEvent());
  const published = await harness.workflow.publishHelpArticles({
    run_id: trigger.run.run_id,
    slack_user_id: "U_LEAD",
    confirmation_text: "@Launch Bot publish help articles KER-123",
  });

  assert.equal(published.status, "published");
  assert.equal(harness.published.length, 2);
  assert.deepEqual(harness.published, [trigger.run.locales.en.intercom_article_id, trigger.run.locales.id.intercom_article_id]);
  assert.match(harness.slackPosts.at(-1).text, /Published both Help Center articles/);
});
