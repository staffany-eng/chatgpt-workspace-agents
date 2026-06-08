#!/usr/bin/env node
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Buffer } from "node:buffer";

export const SHIPPED_STATUS = "6 - Shipped & Launching";
export const DEFAULT_REVIEW_CHANNEL_ID = "C0B32M34J3W";
export const DEFAULT_LAUNCH_PRIORITY_FIELD = "customfield_10561";
export const DEFAULT_STATE_PATH = "~/.hermes/profiles/launchbot/runtime/launchbot-help-article-runs.json";
export const REQUIRED_CONFIG = [
  "JIRA_BASE_URL",
  "JIRA_EMAIL",
  "JIRA_API_TOKEN",
  "JIRA_FIELD_LAUNCH_PRIORITY",
  "JIRA_FIELD_PRODUCT_LEAD",
  "SLACK_BOT_TOKEN",
  "LAUNCHBOT_REVIEW_CHANNEL_ID",
  "INTERCOM_ACCESS_TOKEN",
  "INTERCOM_AUTHOR_ID",
  "INTERCOM_HELP_ARTICLE_DEFAULT_PARENT_ID",
  "PANTHEON_REPO_PATH",
  "WINDMILL_WEBHOOK_TOKEN",
];

export const RUN_STATUSES = [
  "received",
  "blocked",
  "planning",
  "drafting",
  "drafted",
  "review_requested",
  "feedback_pending",
  "publish_confirmation_requested",
  "published",
  "failed",
];

export function buildRunId(issueKey, transitionedAt) {
  return `${String(issueKey || "").trim().toUpperCase()}:${String(transitionedAt || "").trim()}`;
}

export function isKerIssueKey(issueKey) {
  return /^KER-\d+$/i.test(String(issueKey || "").trim());
}

export function launchBotMentioned(text) {
  return /@Launch\s+Bot/i.test(String(text || "")) || /<@[A-Z0-9]+>/.test(String(text || ""));
}

export function isExactPublishConfirmation(text, issueKey) {
  const normalized = String(text || "")
    .replace(/<@[A-Z0-9]+>/g, "@Launch Bot")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
  return normalized === `@launch bot publish help articles ${String(issueKey || "").toLowerCase()}`;
}

export function parseJsonMap(raw) {
  if (!raw) return {};
  if (typeof raw === "object") return raw;
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function envValue(env, ...names) {
  for (const name of names) {
    const value = env?.[name];
    if (value !== undefined && String(value).trim()) return String(value).trim();
  }
  return "";
}

function requireEnv(env, ...names) {
  const value = envValue(env, ...names);
  if (!value) throw new Error(`Missing ${names.join(" or ")}.`);
  return value;
}

function compactText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function adfToText(node) {
  if (!node) return "";
  if (typeof node === "string") return node;
  if (Array.isArray(node)) return node.map(adfToText).filter(Boolean).join(" ");
  if (typeof node !== "object") return "";
  if (node.type === "text") return node.text || "";
  return adfToText(node.content || []);
}

function jiraFieldText(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return compactText(value);
  if (Array.isArray(value)) return value.map(jiraFieldText).filter(Boolean).join(", ");
  if (typeof value === "object") {
    return compactText(value.value || value.name || value.displayName || value.emailAddress || value.accountId || "");
  }
  return "";
}

export function normalizeJiraIssue(issue, { env = process.env } = {}) {
  const fields = issue?.fields || {};
  const launchPriorityField = envValue(env, "JIRA_FIELD_LAUNCH_PRIORITY") || DEFAULT_LAUNCH_PRIORITY_FIELD;
  const productLeadField = requireEnv(env, "JIRA_FIELD_PRODUCT_LEAD");
  const productLeadRaw = fields[productLeadField] || null;
  const key = issue?.key || "";
  const baseUrl = envValue(env, "JIRA_BASE_URL").replace(/\/$/, "");
  return {
    id: String(issue?.id || ""),
    key,
    url: baseUrl && key ? `${baseUrl}/browse/${key}` : "",
    status: fields.status?.name || "",
    summary: fields.summary || "",
    description: compactText(adfToText(fields.description)),
    launchPriority: jiraFieldText(fields[launchPriorityField]),
    productLead: {
      accountId: productLeadRaw?.accountId || "",
      email: productLeadRaw?.emailAddress || "",
      displayName: productLeadRaw?.displayName || jiraFieldText(productLeadRaw),
    },
    updated: fields.updated || "",
    raw: issue,
  };
}

function defaultLocaleState(locale, patch = {}) {
  return {
    locale,
    action: "",
    target_article_id: "",
    intercom_article_id: "",
    intercom_draft_url: "",
    public_url: "",
    gate_status: "not_started",
    approval_status: "not_requested",
    needs_refresh: false,
    ...patch,
  };
}

export function newRunFromEvent(event, now = new Date().toISOString()) {
  const runId = buildRunId(event.issue_key, event.transitioned_at);
  return {
    run_id: runId,
    issue_key: String(event.issue_key || "").toUpperCase(),
    jira_updated_at: "",
    launch_priority: "",
    product_lead_jira_account_id: "",
    product_lead_slack_user_id: "",
    status: "received",
    slack_channel_id: "",
    slack_thread_ts: "",
    locales: {
      en: defaultLocaleState("en"),
      id: defaultLocaleState("id"),
    },
    evidence_paths: [],
    error_summary: "",
    created_at: now,
    updated_at: now,
    event,
  };
}

function markRun(run, patch, clock) {
  return {
    ...run,
    ...patch,
    updated_at: clock().toISOString(),
  };
}

export class MemoryStateStore {
  constructor(initial = {}) {
    this.records = new Map(Object.entries(initial));
  }
  async get(runId) {
    const record = this.records.get(runId);
    return record ? JSON.parse(JSON.stringify(record)) : null;
  }
  async put(run) {
    this.records.set(run.run_id, JSON.parse(JSON.stringify(run)));
    return this.get(run.run_id);
  }
}

export class JsonFileStateStore {
  constructor(path = envValue(process.env, "LAUNCHBOT_HELP_ARTICLE_STATE_PATH") || DEFAULT_STATE_PATH) {
    this.path = resolve(path.replace(/^~(?=$|\/)/, process.env.HOME || ""));
  }
  readAll() {
    if (!existsSync(this.path)) return {};
    return JSON.parse(readFileSync(this.path, "utf8"));
  }
  writeAll(records) {
    mkdirSync(dirname(this.path), { recursive: true });
    writeFileSync(this.path, JSON.stringify(records, null, 2), "utf8");
  }
  async get(runId) {
    return this.readAll()[runId] || null;
  }
  async put(run) {
    const records = this.readAll();
    records[run.run_id] = run;
    this.writeAll(records);
    return run;
  }
}

export class SqlStateStore {
  constructor(query) {
    if (typeof query !== "function") throw new Error("SqlStateStore requires a query(sql, params) function.");
    this.query = query;
  }
  rowToRun(row) {
    if (!row) return null;
    return {
      run_id: row.run_id,
      issue_key: row.issue_key,
      jira_updated_at: row.jira_updated_at || "",
      launch_priority: row.launch_priority || "",
      product_lead_jira_account_id: row.product_lead_jira_account_id || "",
      product_lead_slack_user_id: row.product_lead_slack_user_id || "",
      status: row.status,
      slack_channel_id: row.slack_channel_id || "",
      slack_thread_ts: row.slack_thread_ts || "",
      locales: row.locales || { en: defaultLocaleState("en"), id: defaultLocaleState("id") },
      evidence_paths: row.evidence_paths || [],
      error_summary: row.error_summary || "",
      event: row.event_payload || {},
      created_at: row.created_at,
      updated_at: row.updated_at,
    };
  }
  async get(runId) {
    const result = await this.query("select * from launchbot_help_article_runs where run_id = $1", [runId]);
    const rows = Array.isArray(result) ? result : result?.rows || [];
    return this.rowToRun(rows[0]);
  }
  async put(run) {
    await this.query(
      `insert into launchbot_help_article_runs (
        run_id,
        issue_key,
        jira_updated_at,
        launch_priority,
        product_lead_jira_account_id,
        product_lead_slack_user_id,
        status,
        slack_channel_id,
        slack_thread_ts,
        locales,
        evidence_paths,
        error_summary,
        event_payload,
        created_at,
        updated_at
      ) values (
        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11::jsonb, $12, $13::jsonb, $14, $15
      )
      on conflict (run_id) do update set
        jira_updated_at = excluded.jira_updated_at,
        launch_priority = excluded.launch_priority,
        product_lead_jira_account_id = excluded.product_lead_jira_account_id,
        product_lead_slack_user_id = excluded.product_lead_slack_user_id,
        status = excluded.status,
        slack_channel_id = excluded.slack_channel_id,
        slack_thread_ts = excluded.slack_thread_ts,
        locales = excluded.locales,
        evidence_paths = excluded.evidence_paths,
        error_summary = excluded.error_summary,
        event_payload = excluded.event_payload,
        updated_at = excluded.updated_at`,
      [
        run.run_id,
        run.issue_key,
        run.jira_updated_at || null,
        run.launch_priority || null,
        run.product_lead_jira_account_id || null,
        run.product_lead_slack_user_id || null,
        run.status,
        run.slack_channel_id || null,
        run.slack_thread_ts || null,
        JSON.stringify(run.locales || {}),
        JSON.stringify(run.evidence_paths || []),
        run.error_summary || null,
        JSON.stringify(run.event || {}),
        run.created_at,
        run.updated_at,
      ],
    );
    return run;
  }
}

function requireFetch(fetchImpl) {
  const resolved = fetchImpl || globalThis.fetch;
  if (!resolved) throw new Error("fetch is required in this runtime.");
  return resolved;
}

async function readJsonResponse(response, service) {
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok || payload.ok === false) {
    throw new Error(`${service} API failed: ${response.status} ${payload.error || text}`.slice(0, 500));
  }
  return payload;
}

export function createJiraClient({ env = process.env, fetchImpl = globalThis.fetch } = {}) {
  const fetcher = requireFetch(fetchImpl);
  const baseUrl = requireEnv(env, "JIRA_BASE_URL").replace(/\/$/, "");
  const email = requireEnv(env, "JIRA_EMAIL", "JIRA_USER_EMAIL");
  const token = requireEnv(env, "JIRA_API_TOKEN", "JIRA_Token", "JIRA_TOKEN");
  const launchPriorityField = envValue(env, "JIRA_FIELD_LAUNCH_PRIORITY") || DEFAULT_LAUNCH_PRIORITY_FIELD;
  const productLeadField = requireEnv(env, "JIRA_FIELD_PRODUCT_LEAD");
  const auth = Buffer.from(`${email}:${token}`).toString("base64");
  return {
    async getIssue(issueKey) {
      const fields = ["status", "summary", "description", "updated", launchPriorityField, productLeadField].join(",");
      const url = `${baseUrl}/rest/api/3/issue/${encodeURIComponent(issueKey)}?fields=${encodeURIComponent(fields)}`;
      const response = await fetcher(url, {
        headers: {
          Authorization: `Basic ${auth}`,
          Accept: "application/json",
        },
      });
      return normalizeJiraIssue(await readJsonResponse(response, "Jira"), { env: { ...env, JIRA_BASE_URL: baseUrl } });
    },
  };
}

export function createSlackClient({ env = process.env, fetchImpl = globalThis.fetch } = {}) {
  const fetcher = requireFetch(fetchImpl);
  const token = requireEnv(env, "SLACK_BOT_TOKEN");
  async function post(method, body) {
    const response = await fetcher(`https://slack.com/api/${method}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    return readJsonResponse(response, "Slack");
  }
  return {
    async lookupUserByEmail(email) {
      if (!email) return null;
      const response = await fetcher(`https://slack.com/api/users.lookupByEmail?email=${encodeURIComponent(email)}`, {
        headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
      });
      const payload = await readJsonResponse(response, "Slack");
      return payload.user?.id || "";
    },
    async postMessage({ channel, text, thread_ts = "" }) {
      const payload = await post("chat.postMessage", { channel, text, thread_ts: thread_ts || undefined });
      return { channel: payload.channel || channel, ts: payload.ts };
    },
  };
}

export function createIntercomClient({ env = process.env, fetchImpl = globalThis.fetch } = {}) {
  const fetcher = requireFetch(fetchImpl);
  const token = requireEnv(env, "INTERCOM_ACCESS_TOKEN", "LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN");
  const authorId = requireEnv(env, "INTERCOM_AUTHOR_ID", "LAUNCH_STEP3_INTERCOM_AUTHOR_ID");
  const parentId = requireEnv(env, "INTERCOM_HELP_ARTICLE_DEFAULT_PARENT_ID");
  const baseUrl = envValue(env, "LAUNCHBOT_INTERCOM_API_BASE_URL") || "https://api.intercom.io";
  const headers = {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
    Accept: "application/json",
    "Intercom-Version": "2.15",
  };
  async function request(method, path, payload = null) {
    const response = await fetcher(`${baseUrl.replace(/\/$/, "")}${path}`, {
      method,
      headers,
      body: payload ? JSON.stringify(payload) : undefined,
    });
    const body = await readJsonResponse(response, "Intercom");
    return body.article || body;
  }
  return {
    async createDraftArticle({ title, html, locale = "en", description = "" }) {
      return request("POST", "/articles", {
        title,
        description,
        body: html,
        author_id: authorId,
        parent_id: parentId,
        locale,
        state: "draft",
      });
    },
    async updateDraftArticle({ articleId, title, html, description = "" }) {
      if (envValue(env, "LAUNCHBOT_INTERCOM_UPDATE_DRAFT_SUPPORTED") !== "true") {
        throw new Error("Intercom update draft behavior is not verified; update lane must use manual Intercom editor draft.");
      }
      return request("PUT", `/articles/${encodeURIComponent(articleId)}`, {
        title: title || undefined,
        description: description || undefined,
        body: html,
        state: "draft",
      });
    },
    async readArticle(articleId) {
      return request("GET", `/articles/${encodeURIComponent(articleId)}`);
    },
    async publishArticle(articleId) {
      return request("PUT", `/articles/${encodeURIComponent(articleId)}`, { state: "published" });
    },
  };
}

function fallbackArticlePipeline() {
  return {
    async plan({ jira }) {
      return {
        status: "pass",
        decision: "create",
        locales: {
          en: { action: "create", title: jira.summary, description: "" },
          id: { action: "create", title: jira.summary, description: "" },
        },
      };
    },
    async scanPantheon() {
      return {
        status: "blocked",
        reason: "missing_launchbot_article_pipeline",
        evidence_paths: [],
        message: "Configure a Windmill article-generation step or LAUNCHBOT_HELP_ARTICLE_* command adapters before drafting.",
      };
    },
  };
}

function gatePass(value) {
  return ["pass", "verified", "ready", "approved"].includes(String(value || "").toLowerCase());
}

function articleUrl(payload, env = process.env) {
  for (const key of ["url", "html_url", "admin_url", "public_url"]) {
    if (payload?.[key]) return payload[key];
  }
  const appId = envValue(env, "LAUNCH_STEP3_INTERCOM_APP_ID") || "y12ertqm";
  const id = payload?.id || payload?.article_id || "";
  return id ? `https://app.intercom.com/a/apps/${appId}/articles/articles/${id}/show` : "";
}

function normalizePlanLocale(plan, locale) {
  const localePlan = plan?.locales?.[locale] || {};
  const action = localePlan.action || plan?.decision || "create";
  return {
    action,
    target_article_id: String(localePlan.target_article_id || localePlan.article_id || ""),
    title: localePlan.title || plan?.title || "",
    description: localePlan.description || "",
  };
}

function reviewMessage({ run, jira, plan }) {
  const en = run.locales.en;
  const id = run.locales.id;
  return [
    "Launchbot automation: Help article drafts are ready for review.",
    `<@${run.product_lead_slack_user_id}> please validate the Intercom drafts for ${jira.key}.`,
    `Jira: ${jira.url || jira.key}`,
    `Launch Priority: ${jira.launchPriority}`,
    `Decision: ${plan.decision || "mixed/create/update"}`,
    `English (${en.action}): ${en.intercom_draft_url}`,
    `Indonesian (${id.action}): ${id.intercom_draft_url}`,
    "",
    `Reply in this thread with \`@Launch Bot <feedback>\` for changes.`,
    `When both drafts look good, reply exactly: \`@Launch Bot publish help articles ${jira.key}\`.`,
  ].join("\n");
}

function blockMessage(reason, run, jira = null) {
  const lead = run.product_lead_slack_user_id ? `<@${run.product_lead_slack_user_id}> ` : "";
  return `Launchbot automation: ${lead}${run.issue_key} help article workflow blocked: ${reason}${jira?.url ? `\nJira: ${jira.url}` : ""}`;
}

async function mapProductLeadToSlack({ jira, slack, env }) {
  if (!jira.productLead.accountId && !jira.productLead.email) return "";
  if (jira.productLead.email && slack.lookupUserByEmail) {
    const slackUserId = await slack.lookupUserByEmail(jira.productLead.email);
    if (slackUserId) return slackUserId;
  }
  const fallback = parseJsonMap(envValue(env, "LAUNCHBOT_JIRA_ACCOUNT_TO_SLACK_USER_MAP"));
  return fallback[jira.productLead.accountId] || "";
}

export function createWorkflow({
  env = process.env,
  stateStore = new JsonFileStateStore(),
  jira = createJiraClient({ env }),
  slack = createSlackClient({ env }),
  intercom = createIntercomClient({ env }),
  articlePipeline = fallbackArticlePipeline(),
  clock = () => new Date(),
} = {}) {
  const reviewChannelId = envValue(env, "LAUNCHBOT_REVIEW_CHANNEL_ID") || DEFAULT_REVIEW_CHANNEL_ID;
  const overrideReviewers = new Set(String(envValue(env, "LAUNCHBOT_PUBLISH_OVERRIDE_REVIEWER_IDS")).split(/[,\s]+/).filter(Boolean));

  async function save(run, patch) {
    return stateStore.put(markRun(run, patch, clock));
  }

  async function block(run, reason, jiraSnapshot = null) {
    const blocked = await save(run, { status: "blocked", error_summary: reason });
    await slack.postMessage({ channel: reviewChannelId, text: blockMessage(reason, blocked, jiraSnapshot) });
    return blocked;
  }

  async function fetchAndGateJira(run) {
    const jiraSnapshot = await jira.getIssue(run.issue_key);
    run = await save(run, {
      jira_updated_at: jiraSnapshot.updated,
      launch_priority: jiraSnapshot.launchPriority,
      product_lead_jira_account_id: jiraSnapshot.productLead.accountId,
    });
    if (jiraSnapshot.status !== SHIPPED_STATUS) return { run: await block(run, "stale_transition", jiraSnapshot), jiraSnapshot, ok: false };
    if (!jiraSnapshot.launchPriority) return { run: await block(run, "missing_launch_priority", jiraSnapshot), jiraSnapshot, ok: false };
    const slackUserId = await mapProductLeadToSlack({ jira: jiraSnapshot, slack, env });
    if (!slackUserId) return { run: await block(run, "missing_or_unmapped_product_lead", jiraSnapshot), jiraSnapshot, ok: false };
    run = await save(run, { product_lead_slack_user_id: slackUserId });
    return { run, jiraSnapshot, ok: true };
  }

  async function draftAndWrite(run, jiraSnapshot, plan) {
    run = await save(run, { status: "drafting" });
    for (const locale of ["en", "id"]) {
      const localePlan = normalizePlanLocale(plan, locale);
      const draft = await articlePipeline.draftLocale({ locale, jira: jiraSnapshot, plan, sourceLocale: locale === "id" ? "en" : "" });
      const evaluation = articlePipeline.evaluateLocale
        ? await articlePipeline.evaluateLocale({ locale, draft, jira: jiraSnapshot, plan })
        : { status: "pass" };
      if (!gatePass(evaluation.status)) {
        run.locales[locale] = defaultLocaleState(locale, {
          ...localePlan,
          gate_status: evaluation.status || "needs-check",
          approval_status: "blocked",
        });
        return block(run, `locale_${locale}_${evaluation.status || "needs-check"}`, jiraSnapshot);
      }
      const payload = localePlan.action === "update"
        ? await intercom.updateDraftArticle({
            articleId: localePlan.target_article_id,
            title: localePlan.title,
            html: draft.html,
            description: localePlan.description,
          })
        : await intercom.createDraftArticle({
            title: localePlan.title || draft.title || jiraSnapshot.summary,
            html: draft.html,
            description: localePlan.description || draft.description || "",
            locale,
          });
      run.locales[locale] = defaultLocaleState(locale, {
        ...localePlan,
        intercom_article_id: String(payload.id || localePlan.target_article_id || ""),
        intercom_draft_url: articleUrl(payload, env),
        public_url: payload.public_url || "",
        gate_status: "pass",
        approval_status: "pending_product_lead_review",
      });
      if (locale === "en" && run.locales.id.intercom_article_id) {
        run.locales.id.needs_refresh = true;
        run.locales.id.gate_status = "needs-refresh";
      }
      run = await save(run, { locales: run.locales });
    }
    return save(run, { status: "drafted" });
  }

  return {
    async handleShippedWebhook(event, { bearerToken = "" } = {}) {
      if (envValue(env, "WINDMILL_WEBHOOK_TOKEN") && bearerToken !== envValue(env, "WINDMILL_WEBHOOK_TOKEN")) {
        throw new Error("Invalid Windmill webhook token.");
      }
      if (event.transition_to !== SHIPPED_STATUS) return { status: "ignored", reason: "not_shipped_transition" };
      if (!isKerIssueKey(event.issue_key)) return { status: "ignored", reason: "not_ker_issue" };

      const runId = buildRunId(event.issue_key, event.transitioned_at);
      const existing = await stateStore.get(runId);
      if (existing) return { status: "duplicate", run: existing };

      let run = await stateStore.put(newRunFromEvent(event, clock().toISOString()));
      const gate = await fetchAndGateJira(run);
      run = gate.run;
      if (!gate.ok) return { status: "blocked", run };

      run = await save(run, { status: "planning" });
      const plan = await articlePipeline.plan({ jira: gate.jiraSnapshot, run });
      if (!gatePass(plan.status)) return { status: "blocked", run: await block(run, plan.reason || "help_article_plan_needs_check", gate.jiraSnapshot) };

      const pantheon = await articlePipeline.scanPantheon({ jira: gate.jiraSnapshot, plan, run });
      run = await save(run, { evidence_paths: pantheon.evidence_paths || [] });
      if (!gatePass(pantheon.status)) return { status: "blocked", run: await block(run, pantheon.reason || "pantheon_evidence_needs_check", gate.jiraSnapshot) };

      try {
        run = await draftAndWrite(run, gate.jiraSnapshot, plan);
      } catch (error) {
        return { status: "blocked", run: await block(run, String(error.message || error), gate.jiraSnapshot) };
      }
      const slackMessage = await slack.postMessage({ channel: reviewChannelId, text: reviewMessage({ run, jira: gate.jiraSnapshot, plan }) });
      run = await save(run, {
        status: "review_requested",
        slack_channel_id: slackMessage.channel || reviewChannelId,
        slack_thread_ts: slackMessage.ts,
      });
      return { status: "review_requested", run };
    },

    async applyHelpArticleFeedback(input) {
      const run = await stateStore.get(input.run_id);
      if (!run) throw new Error(`Run not found: ${input.run_id}`);
      if (!launchBotMentioned(input.feedback_text)) return { status: "ignored", reason: "missing_launchbot_mention", run };
      if (input.slack_thread_ts !== run.slack_thread_ts || input.slack_channel_id !== run.slack_channel_id) {
        return { status: "ignored", reason: "wrong_thread", run };
      }
      if (input.slack_user_id !== run.product_lead_slack_user_id && !overrideReviewers.has(input.slack_user_id)) {
        await slack.postMessage({ channel: run.slack_channel_id, thread_ts: run.slack_thread_ts, text: "Launchbot automation: Only the Jira Product Lead or configured override reviewers can update these drafts." });
        return { status: "rejected", reason: "unauthorized_reviewer", run };
      }
      const feedbackRun = await save(run, { status: "feedback_pending" });
      if (!articlePipeline.applyFeedback) {
        await slack.postMessage({ channel: run.slack_channel_id, thread_ts: run.slack_thread_ts, text: "Launchbot automation: Feedback recorded, but no draft feedback adapter is configured yet." });
        return { status: "blocked", run: await save(feedbackRun, { error_summary: "missing_feedback_adapter" }) };
      }
      const update = await articlePipeline.applyFeedback({ run: feedbackRun, feedbackText: input.feedback_text });
      const locales = { ...feedbackRun.locales };
      for (const locale of ["en", "id"]) {
        if (!update.locales?.[locale]) continue;
        const gate = update.locales[locale].gate_status || "pass";
        if (!gatePass(gate)) {
          locales[locale] = { ...locales[locale], gate_status: gate, needs_refresh: gate === "needs-refresh" };
          continue;
        }
        const payload = await intercom.updateDraftArticle({
          articleId: locales[locale].intercom_article_id,
          title: update.locales[locale].title || "",
          html: update.locales[locale].html,
          description: update.locales[locale].description || "",
        });
        locales[locale] = {
          ...locales[locale],
          intercom_draft_url: articleUrl(payload, env) || locales[locale].intercom_draft_url,
          gate_status: "pass",
          needs_refresh: false,
        };
      }
      if (update.locales?.en && !update.locales?.id) {
        locales.id = { ...locales.id, gate_status: "needs-refresh", needs_refresh: true };
      }
      const ready = ["en", "id"].every((locale) => gatePass(locales[locale].gate_status) && !locales[locale].needs_refresh);
      const status = ready ? "publish_confirmation_requested" : "feedback_pending";
      const updatedRun = await save(feedbackRun, { locales, status });
      await slack.postMessage({
        channel: run.slack_channel_id,
        thread_ts: run.slack_thread_ts,
        text: ready
          ? `Launchbot automation: Drafts updated and gates passed. Reply exactly \`@Launch Bot publish help articles ${run.issue_key}\` to publish both locales.`
          : "Launchbot automation: Drafts updated, but one or more locale gates still need checking before publishing.",
      });
      return { status, run: updatedRun };
    },

    async publishHelpArticles(input) {
      const run = await stateStore.get(input.run_id);
      if (!run) throw new Error(`Run not found: ${input.run_id}`);
      if (!isExactPublishConfirmation(input.confirmation_text, run.issue_key)) return { status: "ignored", reason: "confirmation_text_not_exact", run };
      if (input.slack_user_id !== run.product_lead_slack_user_id && !overrideReviewers.has(input.slack_user_id)) {
        await slack.postMessage({ channel: run.slack_channel_id, thread_ts: run.slack_thread_ts, text: "Launchbot automation: Publish rejected. Only the Jira Product Lead or configured override reviewers can publish." });
        return { status: "rejected", reason: "unauthorized_publisher", run };
      }
      const jiraSnapshot = await jira.getIssue(run.issue_key);
      if (jiraSnapshot.status !== SHIPPED_STATUS) return { status: "blocked", run: await block(run, "jira_no_longer_shipped", jiraSnapshot) };
      for (const locale of ["en", "id"]) {
        const localeRun = run.locales[locale];
        if (!localeRun?.intercom_article_id || !gatePass(localeRun.gate_status) || localeRun.needs_refresh) {
          return { status: "blocked", run: await block(run, `locale_${locale}_not_ready_to_publish`, jiraSnapshot) };
        }
      }
      const locales = { ...run.locales };
      for (const locale of ["en", "id"]) {
        const live = await intercom.readArticle(locales[locale].intercom_article_id);
        if (String(live.id || "") !== String(locales[locale].intercom_article_id)) {
          return { status: "blocked", run: await block(run, `locale_${locale}_draft_id_mismatch`, jiraSnapshot) };
        }
        const published = await intercom.publishArticle(locales[locale].intercom_article_id);
        locales[locale] = {
          ...locales[locale],
          approval_status: "published",
          public_url: published.public_url || published.url || locales[locale].public_url,
        };
      }
      const publishedRun = await save(run, { status: "published", locales });
      await slack.postMessage({
        channel: run.slack_channel_id,
        thread_ts: run.slack_thread_ts,
        text: [
          "Launchbot automation: Published both Help Center articles.",
          `English: ${locales.en.public_url || locales.en.intercom_draft_url}`,
          `Indonesian: ${locales.id.public_url || locales.id.intercom_draft_url}`,
          `Audit: ${run.run_id}`,
        ].join("\n"),
      });
      return { status: "published", run: publishedRun };
    },
  };
}

export async function main(payload = {}, context = {}) {
  const workflow = createWorkflow();
  return workflow.handleShippedWebhook(payload, { bearerToken: context.bearerToken || context.token || "" });
}

export async function apply_help_article_feedback(input = {}) {
  const workflow = createWorkflow();
  return workflow.applyHelpArticleFeedback(input);
}

export async function publish_help_articles(input = {}) {
  const workflow = createWorkflow();
  return workflow.publishHelpArticles(input);
}

const currentFile = fileURLToPath(import.meta.url);
if (process.argv[1] === currentFile) {
  const payload = process.argv[2] ? JSON.parse(process.argv[2]) : JSON.parse(readFileSync(0, "utf8"));
  main(payload).then((result) => {
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  }).catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
}
