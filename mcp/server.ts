import express from "express";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { z } from "zod";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const PORT = parseInt(process.env.PORT || "3100", 10);
const BASE_URL = (
  process.env.ZERO_LATENCY_API_URL ?? "https://api.0latency.ai"
).replace(/\/+$/, "");

// ---------------------------------------------------------------------------
// HTTP helper (same as stdio version)
// ---------------------------------------------------------------------------

interface ApiOptions {
  method?: string;
  path: string;
  query?: Record<string, string | number | boolean | undefined>;
  body?: unknown;
  apiKey: string;
}

async function api<T = unknown>(opts: ApiOptions): Promise<T> {
  const url = new URL(opts.path, BASE_URL);
  if (opts.query) {
    for (const [k, v] of Object.entries(opts.query)) {
      if (v !== undefined && v !== null && v !== "") {
        url.searchParams.set(k, String(v));
      }
    }
  }

  const res = await fetch(url.toString(), {
    method: opts.method ?? "GET",
    headers: {
      "X-API-Key": opts.apiKey,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });

  const text = await res.text();

  if (!res.ok) {
    throw new Error(`0Latency API ${res.status}: ${text}`);
  }

  try {
    return JSON.parse(text) as T;
  } catch {
    return text as unknown as T;
  }
}

// ---------------------------------------------------------------------------
// Create MCP Server with tools
// ---------------------------------------------------------------------------

function createMcpServer(apiKey: string): McpServer {
  const server = new McpServer({
    name: "0latency",
    version: "0.1.0",
  });

  // ── memory_add ──────────────────────────────────────────────────────────────

  server.registerTool(
    "memory_add",
    {
      description: "Extract and store memories from a conversation turn. Provide the human message, agent response, and an agent_id to namespace the memories.",
      inputSchema: {
        agent_id: z.string().min(1).max(128).describe("Agent / namespace identifier"),
        human_message: z.string().min(1).max(50000).describe("The human's message in this turn"),
        agent_message: z.string().min(1).max(50000).describe("The agent's response in this turn"),
        session_key: z.string().max(256).optional().describe("Optional session key for grouping conversation turns"),
        turn_id: z.string().max(256).optional().describe("Optional unique turn identifier"),
      },
    },
    async ({ agent_id, human_message, agent_message, session_key, turn_id }) => {
      // Format content as required by the API
      const content = `Human: ${human_message}

Agent: ${agent_message}`;

      const result = await api({
        apiKey,
        method: "POST",
        path: "/memories/extract",
        body: {
          agent_id,
          content,
          ...(session_key && { session_key }),
          ...(turn_id && { turn_id }),
        },
      });
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    }

  // ── memory_recall ───────────────────────────────────────────────────────────

  server.registerTool(
    "memory_recall",
    {
      description: "Recall relevant memories given a conversation context. Returns a formatted context block ready to inject into a prompt.",
      inputSchema: {
        agent_id: z.string().min(1).max(128).describe("Agent / namespace identifier"),
        conversation_context: z
          .string()
          .min(1)
          .max(50000)
          .describe("Current conversation context to match against stored memories"),
        budget_tokens: z
          .number()
          .int()
          .min(500)
          .max(16000)
          .default(4000)
          .describe("Maximum tokens for the returned context block"),
        dynamic_budget: z
          .boolean()
          .default(false)
          .describe("Let the API auto-size the budget based on relevance"),
      },
    },
    async ({ agent_id, conversation_context, budget_tokens, dynamic_budget }) => {
      const result = await api({
        apiKey,
        method: "POST",
        path: "/recall",
        body: { agent_id, conversation_context, budget_tokens, dynamic_budget },
      });
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    }
  );

  // ── memory_search ───────────────────────────────────────────────────────────

  server.registerTool(
    "memory_search",
    {
      description: "Search memories by text query. Returns matching memories ranked by relevance.",
      inputSchema: {
        agent_id: z.string().min(1).max(128).describe("Agent / namespace identifier"),
        q: z.string().min(1).max(500).describe("Search query"),
        limit: z.number().int().min(1).max(100).default(20).describe("Max results to return"),
      },
    },
    async ({ agent_id, q, limit }) => {
      const result = await api({
        apiKey,
        path: "/memories/search",
        query: { agent_id, q, limit },
      });
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    }
  );

  // ── memory_list ─────────────────────────────────────────────────────────────

  server.registerTool(
    "memory_list",
    {
      description: "List stored memories with optional filters. Supports pagination via limit/offset.",
      inputSchema: {
        agent_id: z.string().min(1).max(128).describe("Agent / namespace identifier"),
        memory_type: z.string().max(32).optional().describe("Filter by memory type (e.g. fact, preference, event)"),
        limit: z.number().int().min(1).max(200).default(50).describe("Max results to return"),
        offset: z.number().int().min(0).default(0).describe("Pagination offset"),
      },
    },
    async ({ agent_id, memory_type, limit, offset }) => {
      const result = await api({
        apiKey,
        path: "/memories/extract",
        query: { agent_id, memory_type, limit, offset },
      });
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    }
  );

  // ── memory_delete ───────────────────────────────────────────────────────────

  server.registerTool(
    "memory_delete",
    {
      description: "Delete a specific memory by its ID.",
      inputSchema: {
        memory_id: z.string().min(1).describe("The UUID of the memory to delete"),
      },
    },
    async ({ memory_id }) => {
      const result = await api({
        apiKey,
        method: "DELETE",
        path: `/memories/${encodeURIComponent(memory_id)}`,
      });
      return {
        content: [
          {
            type: "text",
            text:
              typeof result === "string" && result === ""
                ? "Memory deleted successfully."
                : JSON.stringify(result, null, 2),
          },
        ],
      };
    }
  );

  // ── memory_graph ────────────────────────────────────────────────────────────

  server.registerTool(
    "memory_graph",
    {
      description: "Query the knowledge graph. List entities, explore an entity's relationships, or find the path between two entities.",
      inputSchema: {
        agent_id: z.string().min(1).max(128).describe("Agent / namespace identifier"),
        action: z
          .enum(["list_entities", "entity_detail", "entity_memories", "find_path"])
          .describe("Graph operation to perform"),
        entity: z.string().max(256).optional().describe("Entity name (required for entity_detail, entity_memories)"),
        entity_type: z.string().max(32).optional().describe("Filter entities by type (for list_entities)"),
        source: z.string().max(256).optional().describe("Source entity (for find_path)"),
        target: z.string().max(256).optional().describe("Target entity (for find_path)"),
        depth: z.number().int().min(1).max(4).default(2).describe("Relationship traversal depth"),
        limit: z.number().int().min(1).max(200).default(50).describe("Max results"),
      },
    },
    async ({ agent_id, action, entity, entity_type, source, target, depth, limit }) => {
      let result: unknown;

      switch (action) {
        case "list_entities":
          result = await api({
            apiKey,
            path: "/graph/entities",
            query: { agent_id, entity_type, limit },
          });
          break;

        case "entity_detail":
          if (!entity) throw new Error("entity is required for entity_detail");
          result = await api({
            apiKey,
            path: "/graph/entity",
            query: { agent_id, entity, depth },
          });
          break;

        case "entity_memories":
          if (!entity) throw new Error("entity is required for entity_memories");
          result = await api({
            apiKey,
            path: "/graph/entity/memories",
            query: { agent_id, entity, limit },
          });
          break;

        case "find_path":
          if (!source || !target) throw new Error("source and target are required for find_path");
          result = await api({
            apiKey,
            path: "/graph/path",
            query: { agent_id, source, target, max_depth: depth },
          });
          break;
      }

      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    }
  );

  return server;
}

// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// Express + StreamableHTTP Transport
// ---------------------------------------------------------------------------

const app = express();
app.use(express.json());

// Health check
app.get("/health", (_req, res) => {
  res.json({ status: "ok", service: "0latency-mcp-sse", version: "0.1.0" });
});

// MCP endpoint - POST handler
app.post("/mcp", async (req, res) => {
  // Extract API key from header
  const apiKey = req.headers["x-api-key"] as string | undefined;

  if (!apiKey || !apiKey.startsWith("zl_")) {
    res.status(401).json({ error: "Invalid or missing API key. Use x-api-key header" });
    return;
  }

  // Validate API key
  try {
    await api({
      apiKey,
      path: "/health",
    });
  } catch (err) {
    console.error("API key validation failed:", err);
    res.status(401).json({ error: "Invalid API key" });
    return;
  }

  console.log(`[MCP POST] Request from ${req.ip} with valid API key`);

  // Create MCP server instance for this connection
  const mcpServer = createMcpServer(apiKey);

  // Create StreamableHTTP transport
  const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
  
  // Connect MCP server to transport
  await mcpServer.connect(transport);
  
  // Handle the request
  await transport.handleRequest(req, res, req.body);

  console.log(`[MCP POST] Request handled for ${req.ip}`);
});

// MCP endpoint - GET handler
app.get("/mcp", async (req, res) => {
  // Extract API key from header
  const apiKey = req.headers["x-api-key"] as string | undefined;

  if (!apiKey || !apiKey.startsWith("zl_")) {
    res.status(401).json({ error: "Invalid or missing API key. Use x-api-key header" });
    return;
  }

  // Validate API key
  try {
    await api({
      apiKey,
      path: "/health",
    });
  } catch (err) {
    console.error("API key validation failed:", err);
    res.status(401).json({ error: "Invalid API key" });
    return;
  }

  console.log(`[MCP GET] Request from ${req.ip} with valid API key`);

  // Create MCP server instance for this connection
  const mcpServer = createMcpServer(apiKey);

  // Create StreamableHTTP transport
  const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
  
  // Connect MCP server to transport
  await mcpServer.connect(transport);
  
  // Handle the request
  await transport.handleRequest(req, res);

  console.log(`[MCP GET] Request handled for ${req.ip}`);
});


app.listen(PORT, () => {
  console.log(`✓ 0Latency MCP SSE server listening on http://localhost:${PORT}`);
  console.log(`✓ MCP endpoint: http://localhost:${PORT}/mcp`);
  console.log(`✓ Health check: http://localhost:${PORT}/health`);
});
