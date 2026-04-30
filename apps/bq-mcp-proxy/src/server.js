import http from "node:http";
import crypto from "node:crypto";
import { Readable } from "node:stream";

const DEFAULT_UPSTREAM_URL = "https://bigquery.googleapis.com/mcp";
const BIGQUERY_SCOPE = "https://www.googleapis.com/auth/bigquery";
const MAX_BODY_BYTES = 1024 * 1024;

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "content-length",
  "host",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

export function createServer(options = {}) {
  const sseSessions = new Map();
  const config = {
    upstreamUrl: options.upstreamUrl ?? process.env.UPSTREAM_MCP_URL ?? DEFAULT_UPSTREAM_URL,
    sharedSecret: options.sharedSecret ?? process.env.PROXY_SHARED_SECRET ?? "",
    allowUnauthenticated:
      options.allowUnauthenticated ??
      ["1", "true", "yes"].includes(String(process.env.ALLOW_UNAUTHENTICATED ?? "").toLowerCase()),
    enforceReadOnly:
      options.enforceReadOnly ??
      !["0", "false", "no"].includes(String(process.env.ENFORCE_READ_ONLY ?? "true").toLowerCase()),
    tokenProvider: options.tokenProvider ?? defaultAccessTokenProvider,
    fetchImpl: options.fetchImpl ?? fetch,
    logger: options.logger ?? console,
  };

  return http.createServer(async (req, res) => {
    try {
      if (req.url === "/" || req.url === "/healthz") {
        return sendJson(res, 200, { ok: true, service: "bq-mcp-proxy" });
      }

      const url = req.url ? new URL(req.url, "http://localhost") : undefined;
      if (!url) {
        return sendJson(res, 404, { error: "not_found" });
      }

      if (req.method === "OPTIONS") {
        res.writeHead(204, corsHeaders());
        res.end();
        return;
      }

      const authError = authenticate(req, config);
      if (authError) return sendJson(res, authError.status, { error: authError.message });

      if (url.pathname === "/sse" && req.method === "GET") {
        return openSseSession(req, res, sseSessions);
      }

      if (url.pathname === "/sse" && req.method === "POST") {
        const requestBody = await readRequestBody(req);
        return proxyMcpHttp(req, res, requestBody, config);
      }

      if (url.pathname === "/messages" && req.method === "POST") {
        return handleSseMessage(req, res, url, sseSessions, config);
      }

      if (!url.pathname.startsWith("/mcp")) {
        return sendJson(res, 404, { error: "not_found" });
      }

      const requestBody = await readRequestBody(req);
      await proxyMcpHttp(req, res, requestBody, config);
    } catch (error) {
      config.logger.error?.("bq-mcp-proxy request failed", error);
      sendJson(res, 502, { error: "proxy_error" });
    }
  });
}

function openSseSession(req, res, sessions) {
  const sessionId = crypto.randomUUID();
  res.writeHead(200, {
    ...corsHeaders(),
    "content-type": "text/event-stream",
    "cache-control": "no-cache, no-transform",
    connection: "keep-alive",
  });
  res.write(`event: endpoint\ndata: /messages?session_id=${sessionId}\n\n`);
  sessions.set(sessionId, res);
  req.on("close", () => sessions.delete(sessionId));
}

async function handleSseMessage(req, res, url, sessions, config) {
  const sessionId = url.searchParams.get("session_id");
  const session = sessionId ? sessions.get(sessionId) : undefined;
  if (!session) return sendJson(res, 404, { error: "unknown_sse_session" });

  const requestBody = await readRequestBody(req);
  const { status, body } = await proxyMcpPayload(req, requestBody, config);
  if (status < 200 || status >= 300) {
    return sendJson(res, status, body ?? { error: "proxy_error" });
  }

  if (body !== undefined) {
    session.write(`event: message\ndata: ${JSON.stringify(body)}\n\n`);
  }
  res.writeHead(202, corsHeaders());
  res.end();
}

async function proxyMcpHttp(req, res, requestBody, config) {
  const { status, headers, body, stream } = await proxyMcpPayload(req, requestBody, config);
  if (stream) {
    res.writeHead(status, headers);
    Readable.fromWeb(stream).pipe(res);
    return;
  }

  return sendJson(res, status, body);
}

async function proxyMcpPayload(req, requestBody, config) {
  if (config.enforceReadOnly) {
    const guard = validateReadOnlyRequest(requestBody);
    if (!guard.ok) return { status: 400, body: { error: "read_only_guard_rejected", reason: guard.reason } };
  }

  const upstreamBody = rewriteReadOnlyToolRequest(requestBody);
  const accessToken = await config.tokenProvider([BIGQUERY_SCOPE]);
  const upstream = await config.fetchImpl(config.upstreamUrl, {
    method: req.method,
    headers: buildUpstreamHeaders(req.headers, accessToken),
    body: req.method === "GET" || req.method === "HEAD" ? undefined : upstreamBody,
  });

  if (isJsonResponse(upstream)) {
    const text = await upstream.text();
    const payload = text.trim() ? JSON.parse(text) : undefined;
    const responseBody = payload && isToolsListRequest(requestBody) ? simplifyToolsList(payload) : payload;
    return {
      status: upstream.status,
      headers: { ...corsHeaders(), "content-type": "application/json" },
      body: responseBody,
    };
  }

  return {
    status: upstream.status,
    headers: responseHeaders(upstream.headers),
    stream: upstream.body,
  };
}

function authenticate(req, config) {
  if (!config.sharedSecret) {
    if (config.allowUnauthenticated) return null;
    return {
      status: 401,
      message: "proxy authentication is required; set PROXY_SHARED_SECRET or ALLOW_UNAUTHENTICATED=true for a short test",
    };
  }

  const expected = `Bearer ${config.sharedSecret}`;
  if (req.headers.authorization !== expected) {
    return { status: 401, message: "invalid proxy bearer token" };
  }

  return null;
}

async function readRequestBody(req) {
  if (req.method === "GET" || req.method === "HEAD") return undefined;

  const chunks = [];
  let total = 0;
  for await (const chunk of req) {
    total += chunk.length;
    if (total > MAX_BODY_BYTES) {
      throw new Error(`request body exceeds ${MAX_BODY_BYTES} bytes`);
    }
    chunks.push(chunk);
  }

  return Buffer.concat(chunks);
}

function validateReadOnlyRequest(body) {
  if (!body || body.length === 0) return { ok: true };

  let payload;
  try {
    payload = JSON.parse(body.toString("utf8"));
  } catch {
    return { ok: true };
  }

  const calls = Array.isArray(payload) ? payload : [payload];
  for (const call of calls) {
    const toolName = call?.params?.name;
    if (call?.method !== "tools/call" || !toolName) continue;

    if (String(toolName).startsWith("update_") || String(toolName).startsWith("create_") || String(toolName).startsWith("delete_")) {
      return { ok: false, reason: `tool ${toolName} is not allowed by read-only guard` };
    }

    if (toolName === "execute_sql") {
      const sql = call?.params?.arguments?.sql ?? call?.params?.arguments?.query ?? "";
      const sqlGuard = validateSqlReadOnly(String(sql));
      if (!sqlGuard.ok) return sqlGuard;
    }
  }

  return { ok: true };
}

function validateSqlReadOnly(sql) {
  const normalized = sql
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/--.*$/gm, " ")
    .trim()
    .toLowerCase();

  if (!normalized) return { ok: false, reason: "empty SQL is not allowed" };
  if (!/^(select|with)\b/.test(normalized)) {
    return { ok: false, reason: "only SELECT or WITH queries are allowed" };
  }

  const forbidden = /\b(insert|update|delete|merge|create|alter|drop|truncate|export|load|copy|grant|revoke|call)\b/;
  if (forbidden.test(normalized)) {
    return { ok: false, reason: "SQL contains a forbidden mutation or export keyword" };
  }

  return { ok: true };
}

function buildUpstreamHeaders(headers, accessToken) {
  const forwarded = new Headers();
  for (const [key, value] of Object.entries(headers)) {
    const lower = key.toLowerCase();
    if (HOP_BY_HOP_HEADERS.has(lower)) continue;
    if (lower === "authorization") continue;
    if (Array.isArray(value)) forwarded.set(key, value.join(", "));
    else if (value !== undefined) forwarded.set(key, value);
  }

  forwarded.set("authorization", `Bearer ${accessToken}`);
  forwarded.set("accept", forwarded.get("accept") ?? "application/json, text/event-stream");
  return forwarded;
}

async function writeUpstreamResponse(res, upstream, requestBody) {
  if (isToolsListRequest(requestBody) && isJsonResponse(upstream)) {
    const payload = await upstream.json();
    return sendJson(res, upstream.status, simplifyToolsList(payload));
  }

  const headers = responseHeaders(upstream.headers);
  res.writeHead(upstream.status, headers);

  if (!upstream.body) {
    res.end();
    return;
  }

  Readable.fromWeb(upstream.body).pipe(res);
}

function responseHeaders(upstreamHeaders) {
  const headers = {};
  upstreamHeaders.forEach((value, key) => {
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) headers[key] = value;
  });
  return headers;
}

function sendJson(res, status, body) {
  res.writeHead(status, { ...corsHeaders(), "content-type": "application/json" });
  res.end(JSON.stringify(body));
}

function corsHeaders() {
  return {
    "access-control-allow-origin": "*",
    "access-control-allow-headers": "authorization, content-type, accept, mcp-session-id",
    "access-control-allow-methods": "GET, POST, OPTIONS",
  };
}

function isJsonResponse(response) {
  return response.headers.get("content-type")?.includes("application/json");
}

function isToolsListRequest(body) {
  if (!body || body.length === 0) return false;
  try {
    const payload = JSON.parse(body.toString("utf8"));
    return !Array.isArray(payload) && payload?.method === "tools/list";
  } catch {
    return false;
  }
}

function rewriteReadOnlyToolRequest(body) {
  if (!body || body.length === 0) return body;

  let payload;
  try {
    payload = JSON.parse(body.toString("utf8"));
  } catch {
    return body;
  }

  const rewriteCall = (call) => {
    if (call?.method !== "tools/call" || call?.params?.name !== "execute_sql_readonly") return call;
    return {
      ...call,
      params: {
        ...call.params,
        name: "execute_sql",
      },
    };
  };

  const rewritten = Array.isArray(payload) ? payload.map(rewriteCall) : rewriteCall(payload);
  return Buffer.from(JSON.stringify(rewritten));
}

function simplifyToolsList(payload) {
  if (!payload?.result?.tools) return payload;

  return {
    ...payload,
    result: {
      ...payload.result,
      tools: [
        {
          name: "list_dataset_ids",
          description: "List BigQuery dataset IDs in a Google Cloud project.",
          annotations: {
            readOnlyHint: true,
            destructiveHint: false,
            idempotentHint: true,
            openWorldHint: false,
          },
          inputSchema: {
            type: "object",
            properties: {
              projectId: {
                type: "string",
                description: "Google Cloud project ID.",
              },
            },
            required: ["projectId"],
            additionalProperties: false,
          },
        },
        {
          name: "list_table_ids",
          description: "List table IDs in a BigQuery dataset.",
          annotations: {
            readOnlyHint: true,
            destructiveHint: false,
            idempotentHint: true,
            openWorldHint: false,
          },
          inputSchema: {
            type: "object",
            properties: {
              projectId: {
                type: "string",
                description: "Google Cloud project ID.",
              },
              datasetId: {
                type: "string",
                description: "BigQuery dataset ID.",
              },
            },
            required: ["projectId", "datasetId"],
            additionalProperties: false,
          },
        },
        {
          name: "get_table_info",
          description: "Get BigQuery table metadata and schema.",
          annotations: {
            readOnlyHint: true,
            destructiveHint: false,
            idempotentHint: true,
            openWorldHint: false,
          },
          inputSchema: {
            type: "object",
            properties: {
              projectId: {
                type: "string",
                description: "Google Cloud project ID.",
              },
              datasetId: {
                type: "string",
                description: "BigQuery dataset ID.",
              },
              tableId: {
                type: "string",
                description: "BigQuery table ID.",
              },
            },
            required: ["projectId", "datasetId", "tableId"],
            additionalProperties: false,
          },
        },
        {
          name: "execute_sql_readonly",
          description: "Run a read-only BigQuery Standard SQL query and return results.",
          annotations: {
            readOnlyHint: true,
            destructiveHint: false,
            idempotentHint: false,
            openWorldHint: true,
          },
          inputSchema: {
            type: "object",
            properties: {
              projectId: {
                type: "string",
                description: "Google Cloud project used for query execution and billing.",
              },
              query: {
                type: "string",
                description: "Read-only SELECT or WITH query.",
              },
              dryRun: {
                type: "boolean",
                description: "When true, validate the query without running it.",
              },
            },
            required: ["projectId", "query"],
            additionalProperties: false,
          },
        },
      ],
    },
  };
}

async function defaultAccessTokenProvider(scopes) {
  const { GoogleAuth, Impersonated } = await import("google-auth-library");
  const targetPrincipal = process.env.TARGET_SERVICE_ACCOUNT ?? "";
  const sourceScopes = targetPrincipal ? ["https://www.googleapis.com/auth/cloud-platform"] : scopes;
  const auth = new GoogleAuth({ scopes: sourceScopes });
  const sourceClient = await auth.getClient();
  const client = targetPrincipal
    ? new Impersonated({
        sourceClient,
        targetPrincipal,
        targetScopes: scopes,
        lifetime: 300,
      })
    : sourceClient;
  const token = await client.getAccessToken();
  if (!token.token) throw new Error("Google auth did not return an access token");
  return token.token;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const port = Number(process.env.PORT || 8080);
  createServer().listen(port, () => {
    console.log(`bq-mcp-proxy listening on :${port}`);
  });
}
