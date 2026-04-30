import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { once } from "node:events";

import { createServer } from "../src/server.js";

async function withServer(options, fn) {
  const server = createServer({ ...options, logger: { error() {} } });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const { port } = server.address();
  try {
    await fn(`http://127.0.0.1:${port}`);
  } finally {
    server.close();
    await once(server, "close");
  }
}

describe("bq-mcp-proxy", () => {
  it("rejects unauthenticated requests by default", async () => {
    await withServer({ tokenProvider: async () => "token" }, async (baseUrl) => {
      const response = await fetch(`${baseUrl}/mcp`, { method: "POST", body: "{}" });
      assert.equal(response.status, 401);
    });
  });

  it("forwards authorized requests with service account bearer token", async () => {
    const upstreamCalls = [];
    await withServer(
      {
        sharedSecret: "client-secret",
        tokenProvider: async () => "service-account-token",
        fetchImpl: async (url, init) => {
          upstreamCalls.push({ url, init });
          return new Response(JSON.stringify({ ok: true }), {
            status: 200,
            headers: { "content-type": "application/json" },
          });
        },
      },
      async (baseUrl) => {
        const response = await fetch(`${baseUrl}/mcp`, {
          method: "POST",
          headers: {
            authorization: "Bearer client-secret",
            "content-type": "application/json",
          },
          body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/list" }),
        });
        assert.equal(response.status, 200);
        assert.equal(upstreamCalls.length, 1);
        assert.equal(upstreamCalls[0].url, "https://bigquery.googleapis.com/mcp");
        assert.equal(upstreamCalls[0].init.headers.get("authorization"), "Bearer service-account-token");
      },
    );
  });

  it("rejects non-read-only SQL when guard is enabled", async () => {
    await withServer(
      {
        sharedSecret: "client-secret",
        tokenProvider: async () => "service-account-token",
        fetchImpl: async () => {
          throw new Error("should not forward");
        },
      },
      async (baseUrl) => {
        const response = await fetch(`${baseUrl}/mcp`, {
          method: "POST",
          headers: {
            authorization: "Bearer client-secret",
            "content-type": "application/json",
          },
          body: JSON.stringify({
            jsonrpc: "2.0",
            id: 1,
            method: "tools/call",
            params: {
              name: "execute_sql",
              arguments: { sql: "DELETE FROM dataset.table WHERE true" },
            },
          }),
        });
        assert.equal(response.status, 400);
        const body = await response.json();
        assert.equal(body.error, "read_only_guard_rejected");
      },
    );
  });

  it("returns a simplified tool list for ChatGPT connector creation", async () => {
    await withServer(
      {
        sharedSecret: "client-secret",
        tokenProvider: async () => "service-account-token",
        fetchImpl: async () =>
          new Response(
            JSON.stringify({
              jsonrpc: "2.0",
              id: 1,
              result: {
                tools: [
                  {
                    name: "execute_sql",
                    description: "Huge generated schema omitted",
                    inputSchema: { type: "object", properties: { mutation: { type: "string" } } },
                  },
                ],
              },
            }),
            {
              status: 200,
              headers: { "content-type": "application/json" },
            },
          ),
      },
      async (baseUrl) => {
        const response = await fetch(`${baseUrl}/mcp`, {
          method: "POST",
          headers: {
            authorization: "Bearer client-secret",
            "content-type": "application/json",
          },
          body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/list" }),
        });
        assert.equal(response.status, 200);
        const body = await response.json();
        assert.deepEqual(
          body.result.tools.map((tool) => tool.name),
          ["list_dataset_ids", "list_table_ids", "get_table_info", "execute_sql_readonly"],
        );
        assert.equal(body.result.tools.some((tool) => tool.name === "execute_sql"), false);
        assert.equal(body.result.tools[0].inputSchema.additionalProperties, false);
      },
    );
  });

  it("bridges ChatGPT SSE messages to upstream MCP HTTP", async () => {
    const upstreamCalls = [];
    await withServer(
      {
        sharedSecret: "client-secret",
        tokenProvider: async () => "service-account-token",
        fetchImpl: async (_url, init) => {
          upstreamCalls.push(JSON.parse(init.body.toString("utf8")));
          return new Response(
            JSON.stringify({
              jsonrpc: "2.0",
              id: upstreamCalls.at(-1).id,
              result: { ok: true },
            }),
            {
              status: 200,
              headers: { "content-type": "application/json" },
            },
          );
        },
      },
      async (baseUrl) => {
        const sse = await fetch(`${baseUrl}/sse`, {
          headers: {
            accept: "text/event-stream",
            authorization: "Bearer client-secret",
          },
        });
        assert.equal(sse.status, 200);
        const reader = sse.body.getReader();
        const firstChunk = new TextDecoder().decode((await reader.read()).value);
        const endpoint = firstChunk.match(/data: (\/messages\?session_id=[^\n]+)/)?.[1];
        assert.ok(endpoint);

        const response = await fetch(`${baseUrl}${endpoint}`, {
          method: "POST",
          headers: {
            authorization: "Bearer client-secret",
            "content-type": "application/json",
          },
          body: JSON.stringify({
            jsonrpc: "2.0",
            id: 7,
            method: "tools/call",
            params: {
              name: "execute_sql_readonly",
              arguments: { projectId: "gws-cli-260305163132", query: "SELECT 1" },
            },
          }),
        });
        assert.equal(response.status, 202);
        const secondChunk = new TextDecoder().decode((await reader.read()).value);
        assert.match(secondChunk, /event: message/);
        assert.match(secondChunk, /"id":7/);
        assert.equal(upstreamCalls[0].params.name, "execute_sql");
        assert.equal(upstreamCalls[0].params.arguments.query, "SELECT 1");
        assert.equal("sql" in upstreamCalls[0].params.arguments, false);
        await reader.cancel();
      },
    );
  });

  it("accepts direct POST probes to the configured SSE URL", async () => {
    await withServer(
      {
        sharedSecret: "client-secret",
        tokenProvider: async () => "service-account-token",
        fetchImpl: async () =>
          new Response(JSON.stringify({ jsonrpc: "2.0", id: 1, result: { ok: true } }), {
            status: 200,
            headers: { "content-type": "application/json" },
          }),
      },
      async (baseUrl) => {
        const response = await fetch(`${baseUrl}/sse`, {
          method: "POST",
          headers: {
            authorization: "Bearer client-secret",
            "content-type": "application/json",
          },
          body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "initialize" }),
        });
        assert.equal(response.status, 200);
        assert.deepEqual(await response.json(), { jsonrpc: "2.0", id: 1, result: { ok: true } });
      },
    );
  });

  it("does not crash when an SSE notification has no upstream response body", async () => {
    await withServer(
      {
        sharedSecret: "client-secret",
        tokenProvider: async () => "service-account-token",
        fetchImpl: async () =>
          new Response("", {
            status: 202,
            headers: { "content-type": "application/json" },
          }),
      },
      async (baseUrl) => {
        const sse = await fetch(`${baseUrl}/sse`, {
          headers: {
            accept: "text/event-stream",
            authorization: "Bearer client-secret",
          },
        });
        const reader = sse.body.getReader();
        const firstChunk = new TextDecoder().decode((await reader.read()).value);
        const endpoint = firstChunk.match(/data: (\/messages\?session_id=[^\n]+)/)?.[1];
        assert.ok(endpoint);

        const response = await fetch(`${baseUrl}${endpoint}`, {
          method: "POST",
          headers: {
            authorization: "Bearer client-secret",
            "content-type": "application/json",
          },
          body: JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }),
        });
        assert.equal(response.status, 202);
        await reader.cancel();
      },
    );
  });
});
