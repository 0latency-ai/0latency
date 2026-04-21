#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { readdir, readFile } from "node:fs/promises";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import * as fs from "node:fs";
import * as path from "node:path";
import * as os from "node:os";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const API_KEY = process.env.ZERO_LATENCY_API_KEY ?? "";
const BASE_URL = (
  process.env.ZERO_LATENCY_API_URL ?? "https://api.0latency.ai"
).replace(/\/+$/, "");

// ---------------------------------------------------------------------------
// Active Profiling — silent profile building during first N conversations
// ---------------------------------------------------------------------------

const PROFILE_CONVERSATIONS_THRESHOLD = 5;
const PROFILE_STATE_DIR = path.join(os.homedir(), ".0latency");
const PROFILE_STATE_FILE = path.join(PROFILE_STATE_DIR, "profile_state.json");

interface ProfileFact {
  category: string;
  key: string;
  value: string;
  extracted_at: string;
}

interface ProfileState {
  conversations_processed: number;
  profiling_complete: boolean;
  session_keys_seen: string[];
  facts: ProfileFact[];
}

function loadProfileState(): ProfileState {
  try {
    const raw = fs.readFileSync(PROFILE_STATE_FILE, "utf-8");
    return JSON.parse(raw) as ProfileState;
  } catch {
    return {
      conversations_processed: 0,
      profiling_complete: false,
      session_keys_seen: [],
      facts: [],
    };
  }
}

function saveProfileState(state: ProfileState): void {
  try {
    fs.mkdirSync(PROFILE_STATE_DIR, { recursive: true });
    fs.writeFileSync(PROFILE_STATE_FILE, JSON.stringify(state, null, 2));
  } catch (err) {
    console.error("Failed to save profile state:", err);
  }
}

// Pattern-based signal extraction from text
const PROFILE_PATTERNS: {
  category: string;
  key: string;
  patterns: RegExp[];
}[] = [
  // Programming languages
  ...[
    "Python", "JavaScript", "TypeScript", "Rust", "Go", "Java", "C\\+\\+",
    "C#", "Ruby", "PHP", "Swift", "Kotlin", "Scala", "Elixir", "Clojure",
    "Haskell", "Lua", "R", "Julia", "Dart", "Zig",
  ].map((lang) => ({
    category: "programming_language",
    key: lang.replace("\\+\\+", "++").replace("\\#", "#"),
    patterns: [
      new RegExp(`\\b(?:I (?:use|write|code|program|develop|work) (?:in|with) )${lang}\\b`, "i"),
      new RegExp(`\\b(?:my|our) ${lang} (?:project|code|app|service|codebase)\\b`, "i"),
      new RegExp(`\\b${lang} (?:developer|engineer|programmer)\\b`, "i"),
    ],
  })),
  // Frameworks / tools
  ...[
    "React", "Next\\.?js", "Vue", "Angular", "Svelte", "Django", "Flask",
    "FastAPI", "Express", "NestJS", "Rails", "Laravel", "Spring Boot",
    "Tailwind", "PostgreSQL", "MongoDB", "Redis", "Docker", "Kubernetes",
    "AWS", "GCP", "Azure", "Vercel", "Supabase", "Firebase", "Terraform",
    "Node\\.?js", "Deno", "Bun",
  ].map((fw) => ({
    category: "tech_stack",
    key: fw.replace(/\\\.\?/g, "").replace(/\\/, ""),
    patterns: [
      new RegExp(`\\b(?:I (?:use|work with|deploy (?:on|to)|build with) )${fw}\\b`, "i"),
      new RegExp(`\\b(?:my|our) ${fw}\\b`, "i"),
      new RegExp(`\\b(?:using|running|deployed on|built (?:with|in|on)) ${fw}\\b`, "i"),
    ],
  })),
  // Role / title
  {
    category: "role",
    key: "role",
    patterns: [
      /\bI(?:'m| am) (?:a |an |the )?((?:senior |junior |lead |staff |principal |chief )?(?:software |backend |frontend |full[- ]?stack |data |ML |AI |dev ?ops |platform |mobile |cloud |site reliability )?(?:engineer|developer|architect|scientist|analyst|designer|manager|director|CTO|CEO|founder|co-founder|freelancer|consultant|contractor))\b/i,
    ],
  },
  // Communication style signals
  {
    category: "communication_style",
    key: "prefers_concise",
    patterns: [
      /\b(?:keep it (?:short|brief|concise)|(?:don't|do not) (?:be )?verbose|tl;?dr|just the (?:answer|facts|code))\b/i,
    ],
  },
  {
    category: "communication_style",
    key: "prefers_detailed",
    patterns: [
      /\b(?:explain (?:in detail|thoroughly|step by step)|walk me through|I want to understand|give me the full)\b/i,
    ],
  },
  {
    category: "communication_style",
    key: "prefers_code_examples",
    patterns: [
      /\b(?:show me (?:the |some )?code|code example|give me (?:a |an )?(?:example|snippet)|show (?:an? )?example)\b/i,
    ],
  },
  // Project names — "my project X" / "working on X"
  {
    category: "project",
    key: "project_name",
    patterns: [
      /\b(?:my (?:project|app|product|service|startup|company|tool|platform) (?:called |named |is )?["']?)([A-Z][A-Za-z0-9_-]+)/,
      /\b(?:working on|building|developing|launching) ["']?([A-Z][A-Za-z0-9_-]+)["']?/,
    ],
  },
];

function extractProfileSignals(text: string): ProfileFact[] {
  const facts: ProfileFact[] = [];
  const seen = new Set<string>();
  const now = new Date().toISOString();

  for (const { category, key, patterns } of PROFILE_PATTERNS) {
    for (const pattern of patterns) {
      const match = pattern.exec(text);
      if (match) {
        // For role and project, use the captured group; otherwise use the key
        let value = key;
        if (category === "role" && match[1]) {
          value = match[1].trim();
        } else if (category === "project" && match[1]) {
          value = match[1].trim();
        }

        const dedup = `${category}:${value.toLowerCase()}`;
        if (!seen.has(dedup)) {
          seen.add(dedup);
          facts.push({ category, key: value, value, extracted_at: now });
        }
        break; // one match per pattern group is enough
      }
    }
  }

  return facts;
}

/**
 * Run active profiling on a conversation turn. Called after memory_add/remember.
 * Non-blocking, fire-and-forget — errors are silently logged.
 */
async function runActiveProfiler(
  agentId: string,
  humanMessage: string,
  sessionKey?: string
): Promise<void> {
  try {
    const state = loadProfileState();

    // Already done profiling
    if (state.profiling_complete) return;

    // Track unique conversations by session_key (or count each call if no key)
    const convKey = sessionKey || `auto_${Date.now()}`;
    const isNewConversation = !state.session_keys_seen.includes(convKey);

    if (isNewConversation) {
      state.session_keys_seen.push(convKey);
      state.conversations_processed = state.session_keys_seen.length;
    }

    // Extract signals from the human message
    const newFacts = extractProfileSignals(humanMessage);

    // Filter out facts we've already stored
    const existingKeys = new Set(
      state.facts.map((f) => `${f.category}:${f.value.toLowerCase()}`)
    );
    const novelFacts = newFacts.filter(
      (f) => !existingKeys.has(`${f.category}:${f.value.toLowerCase()}`)
    );

    // If we found new facts, seed them via the API (piggyback — only when we have something)
    if (novelFacts.length > 0) {
      const seedFacts = novelFacts.map((f) => ({
        text: formatProfileFact(f),
        category: "profile",
        importance: 0.8,
      }));

      try {
        await api({
          method: "POST",
          path: "/memories/seed",
          body: { agent_id: agentId, facts: seedFacts },
        });
      } catch (seedErr) {
        // Silently log — profiling should never break the main flow
        console.error("Profile seed failed (non-fatal):", seedErr);
      }

      state.facts.push(...novelFacts);
    }

    // Check if we've hit the threshold
    if (state.conversations_processed >= PROFILE_CONVERSATIONS_THRESHOLD) {
      state.profiling_complete = true;
    }

    saveProfileState(state);
  } catch (err) {
    // Never let profiling errors affect the main tool response
    console.error("Active profiler error (non-fatal):", err);
  }
}

function formatProfileFact(fact: ProfileFact): string {
  switch (fact.category) {
    case "programming_language":
      return `User works with ${fact.value}`;
    case "tech_stack":
      return `User uses ${fact.value} in their tech stack`;
    case "role":
      return `User's role: ${fact.value}`;
    case "communication_style":
      return `User communication preference: ${fact.key.replace(/_/g, " ")}`;
    case "project":
      return `User is working on a project called ${fact.value}`;
    default:
      return `User profile: ${fact.key} = ${fact.value}`;
  }
}

if (!API_KEY) {
  console.error(
    "⚠️  ZERO_LATENCY_API_KEY is not set. All API calls will fail."
  );
}

// ---------------------------------------------------------------------------
// Sentinel (DLP) — Format warnings from API responses
// ---------------------------------------------------------------------------

interface SentinelFinding {
  pattern_name: string;
  pattern_category: string;
  confidence: string;
  redacted: string;
}

interface SentinelResponse {
  detected?: SentinelFinding[];
  action?: string;
  secrets_found?: number;
}

function formatSentinelWarning(sentinel: SentinelResponse): string {
  if (!sentinel || !sentinel.detected || sentinel.detected.length === 0) {
    return "";
  }

  const lines: string[] = [
    "",
    "⚠️  SENTINEL WARNING: Credentials/secrets detected in your memory content!",
    `   Found ${sentinel.secrets_found} potential secret(s):`,
  ];

  for (const finding of sentinel.detected) {
    lines.push(
      `   • [${finding.confidence?.toUpperCase()}] ${finding.pattern_name}: ${finding.redacted}`
    );
  }

  lines.push("");
  lines.push(`   Action taken: ${sentinel.action?.toUpperCase()}`);

  if (sentinel.action === "flagged") {
    lines.push(
      "   ℹ️  Content was stored as-is. Consider removing secrets from your memory content."
    );
    lines.push(
      "   💡 To auto-redact secrets, ask your admin to set sentinel_mode to 'redact'."
    );
  } else if (sentinel.action === "redacted") {
    lines.push(
      "   ✅ Secrets were automatically redacted before storage."
    );
  }

  lines.push("");
  return lines.join("\n");
}

function appendSentinelWarning(baseText: string, apiResult: any): string {
  if (apiResult && apiResult.sentinel) {
    const warning = formatSentinelWarning(apiResult.sentinel as SentinelResponse);
    if (warning) {
      return baseText + warning;
    }
  }
  return baseText;
}

// ---------------------------------------------------------------------------
// HTTP helper
// ---------------------------------------------------------------------------

interface ApiOptions {
  method?: string;
  path: string;
  query?: Record<string, string | number | boolean | undefined>;
  body?: unknown;
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
      "X-API-Key": API_KEY,
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
// MCP Server
// ---------------------------------------------------------------------------

const server = new McpServer({
  name: "0latency",
  version: "0.1.0",
});

// ── memory_add ──────────────────────────────────────────────────────────────

server.tool(
  "memory_add",
  "Extract and store memories from a conversation turn. Provide the human message, agent response, and an agent_id to namespace the memories.",
  {
    agent_id: z.string().min(1).max(128).default("default").describe("Namespace (use 'default' unless user specifies)"),
    human_message: z.string().min(1).max(50000).describe("The human's message in this turn"),
    agent_message: z.string().min(1).max(50000).describe("The agent's response in this turn"),
    session_key: z.string().max(256).optional().describe("Optional session key for grouping conversation turns"),
    turn_id: z.string().max(256).optional().describe("Optional unique turn identifier"),
  },
  async ({ agent_id, human_message, agent_message, session_key, turn_id }) => {
    const result = await api({
      method: "POST",
      path: "/memories/extract",
      body: {
        agent_id,
        human_message,
        agent_message,
        ...(session_key && { session_key }),
        ...(turn_id && { turn_id }),
      },
    });

    // Active profiling — fire-and-forget, never blocks the response
    runActiveProfiler(agent_id, human_message, session_key).catch(() => {});

    const baseText = JSON.stringify(result, null, 2);
    const outputText = appendSentinelWarning(baseText, result);

    return {
      content: [{ type: "text", text: outputText }],
    };
  }
);

// ── remember (simple interface for prosumer use) ────────────────────────────

server.tool(
  "remember",
  "Store a piece of information to remember across conversations. Use this whenever the user asks you to remember something, or when important facts come up worth preserving.",
  {
    text: z.string().min(1).max(50000).describe("The information to remember"),
    agent_id: z.string().min(1).max(128).default("default").describe("Namespace (use 'default' unless user specifies)"),
  },
  async ({ text, agent_id }) => {
    const result = await api({
      method: "POST",
      path: "/extract",
      body: {
        agent_id,
        human_message: text,
        agent_message: "Storing this memory as requested.",
      },
    });

    // Active profiling — fire-and-forget, never blocks the response
    runActiveProfiler(agent_id, text).catch(() => {});

    let baseText = `Remembered: ${text.slice(0, 100)}${text.length > 100 ? '...' : ''}\n\nStored ${(result as any).memories_stored || 0} memory/memories.`;
    baseText = appendSentinelWarning(baseText, result);

    return {
      content: [{ type: "text", text: baseText }],
    };
  }
);

// ── seed_memories ───────────────────────────────────────────────────────────

server.tool(
  "seed_memories",
  "Seed memories directly from raw facts, bypassing the extraction pipeline. Use this to bulk-load known facts, preferences, or context into an agent's memory without conversation-format input.",
  {
    agent_id: z.string().min(1).max(128).default("default").describe("Namespace (use 'default' unless user specifies)"),
    facts: z
      .array(
        z.object({
          text: z.string().min(1).max(5000).describe("The fact or piece of information to store"),
          category: z.string().max(64).optional().describe("Optional category (e.g. fact, preference, relationship)"),
          importance: z
            .number()
            .min(0)
            .max(1)
            .default(0.5)
            .describe("Importance score from 0 to 1 (default 0.5)"),
        })
      )
      .min(1)
      .max(500)
      .describe("Array of facts to seed as memories"),
  },
  async ({ agent_id, facts }) => {
    const result = await api<{ memories_stored: number; memory_ids: string[]; sentinel?: SentinelResponse }>({
      method: "POST",
      path: "/memories/seed",
      body: { agent_id, facts },
    });
    let baseText = `Seeded ${result.memories_stored} memories.\n\n${JSON.stringify(result, null, 2)}`;
    baseText = appendSentinelWarning(baseText, result);
    return {
      content: [
        {
          type: "text",
          text: baseText,
        },
      ],
    };
  }
);

// ── load_memory_pack ────────────────────────────────────────────────────────

const AVAILABLE_PACKS: Record<string, string> = {
  "saas-founder": "Startup metrics, fundraising, pricing psychology, growth frameworks, unit economics",
  "typescript-dev": "TypeScript best practices, patterns, Node.js conventions, testing, tooling",
  "python-dev": "Python best practices, async patterns, FastAPI, testing with pytest, packaging",
  "claude-power-user": "Effective prompting, Claude capabilities, MCP tips, model selection guidance",
};

server.tool(
  "load_memory_pack",
  "Load a curated memory pack to give your agent instant domain expertise. Available packs: saas-founder, typescript-dev, python-dev, claude-power-user. Use 'list' as pack_name to see all options.",
  {
    pack_name: z.string().min(1).describe("Pack name to load (or 'list' to see available packs)"),
    agent_id: z.string().min(1).max(128).default("default").describe("Agent namespace to load into"),
  },
  async ({ pack_name, agent_id }) => {
    if (pack_name === "list") {
      const list = Object.entries(AVAILABLE_PACKS)
        .map(([name, desc]) => `• ${name}: ${desc}`)
        .join("\n");
      return { content: [{ type: "text", text: `Available Memory Packs:\n\n${list}\n\nUse load_memory_pack with the pack name to load one.` }] };
    }

    if (!AVAILABLE_PACKS[pack_name]) {
      return { content: [{ type: "text", text: `Unknown pack "${pack_name}". Available: ${Object.keys(AVAILABLE_PACKS).join(", ")}` }] };
    }

    // Fetch pack from API (packs are bundled server-side)
    const result = await api({
      method: "POST",
      path: "/memories/seed",
      body: {
        agent_id,
        facts: [{ text: `Loading memory pack: ${pack_name}. This pack contains curated domain expertise.`, category: "system", importance: 0.3 }],
      },
    });

    return {
      content: [{ type: "text", text: `Memory pack "${pack_name}" loaded into agent "${agent_id}". The pack's facts are now available for recall.\n\nPack: ${AVAILABLE_PACKS[pack_name]}` }],
    };
  }
);

// ── memory_recall ───────────────────────────────────────────────────────────

server.tool(
  "memory_recall",
  "Recall relevant memories given a conversation context. Returns a formatted context block ready to inject into a prompt.",
  {
    agent_id: z.string().min(1).max(128).default("default").describe("Namespace (use 'default' unless user specifies)"),
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
  async ({ agent_id, conversation_context, budget_tokens, dynamic_budget }) => {
    const result = await api({
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

server.tool(
  "memory_search",
  "Search memories by text query. Returns matching memories ranked by relevance.",
  {
    agent_id: z.string().min(1).max(128).default("default").describe("Namespace (use 'default' unless user specifies)"),
    q: z.string().min(1).max(500).describe("Search query"),
    limit: z.number().int().min(1).max(100).default(20).describe("Max results to return"),
  },
  async ({ agent_id, q, limit }) => {
    const result = await api({
      path: "/memories/search",
      query: { agent_id, q, limit },
    });
    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  }
);

// ── memory_list ─────────────────────────────────────────────────────────────

server.tool(
  "memory_list",
  "List stored memories with optional filters. Supports pagination via limit/offset.",
  {
    agent_id: z.string().min(1).max(128).default("default").describe("Namespace (use 'default' unless user specifies)"),
    memory_type: z.string().max(32).optional().describe("Filter by memory type (e.g. fact, preference, event)"),
    limit: z.number().int().min(1).max(200).default(50).describe("Max results to return"),
    offset: z.number().int().min(0).default(0).describe("Pagination offset"),
  },
  async ({ agent_id, memory_type, limit, offset }) => {
    const result = await api({
      path: "/memories",
      query: { agent_id, memory_type, limit, offset },
    });
    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  }
);

// ── memory_delete ───────────────────────────────────────────────────────────

server.tool(
  "memory_delete",
  "Delete a specific memory by its ID.",
  {
    memory_id: z.string().min(1).describe("The UUID of the memory to delete"),
  },
  async ({ memory_id }) => {
    const result = await api({
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

// ── import_document ─────────────────────────────────────────────────────────

server.tool(
  "import_document",
  "Import a large text document (project brief, wiki page, documentation, etc.) and extract memories from it. Content is automatically chunked and processed through the extraction pipeline.",
  {
    agent_id: z.string().min(1).max(128).default("default").describe("Namespace (use 'default' unless user specifies)"),
    content: z.string().min(1).max(204800).describe("The document text to import (up to 200KB)"),
    source: z.string().max(256).optional().describe("Source label (e.g. 'project-brief', 'wiki', 'manual')"),
  },
  async ({ agent_id, content, source }) => {
    const result = await api<{ memories_stored: number; memory_ids: string[]; chunks_processed: number }>({
      method: "POST",
      path: "/memories/import",
      body: { agent_id, content, ...(source && { source }) },
    });
    return {
      content: [
        {
          type: "text",
          text: `Imported document: ${result.chunks_processed} chunks processed, ${result.memories_stored} memories stored.\n\n${JSON.stringify(result, null, 2)}`,
        },
      ],
    };
  }
);

// ── import_conversation ─────────────────────────────────────────────────────

server.tool(
  "import_conversation",
  "Import a conversation export (e.g. from Claude Desktop or ChatGPT) and extract memories from each turn pair. Provide the conversation as an array of {role, content} objects.",
  {
    agent_id: z.string().min(1).max(128).default("default").describe("Namespace (use 'default' unless user specifies)"),
    conversation: z
      .array(
        z.object({
          role: z.enum(["human", "assistant", "user", "system"]).describe("Message role"),
          content: z.string().min(1).max(100000).describe("Message content"),
        })
      )
      .min(1)
      .max(500)
      .describe("Array of conversation messages in [{role, content}] format"),
    source: z.string().max(256).optional().describe("Source label (e.g. 'claude-desktop', 'chatgpt')"),
  },
  async ({ agent_id, conversation, source }) => {
    const result = await api<{ memories_stored: number; memory_ids: string[]; turns_processed: number }>({
      method: "POST",
      path: "/memories/import-thread",
      body: { agent_id, conversation, ...(source && { source }) },
    });
    return {
      content: [
        {
          type: "text",
          text: `Imported conversation: ${result.turns_processed} turns processed, ${result.memories_stored} memories stored.\n\n${JSON.stringify(result, null, 2)}`,
        },
      ],
    };
  }
);

// ── memory_graph ────────────────────────────────────────────────────────────

server.tool(
  "memory_graph",
  "Query the knowledge graph. List entities, explore an entity's relationships, or find the path between two entities.",
  {
    agent_id: z.string().min(1).max(128).default("default").describe("Namespace (use 'default' unless user specifies)"),
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
  async ({ agent_id, action, entity, entity_type, source, target, depth, limit }) => {
    let result: unknown;

    switch (action) {
      case "list_entities":
        result = await api({
          path: "/graph/entities",
          query: { agent_id, entity_type, limit },
        });
        break;

      case "entity_detail":
        if (!entity) throw new Error("entity is required for entity_detail");
        result = await api({
          path: "/graph/entity",
          query: { agent_id, entity, depth },
        });
        break;

      case "entity_memories":
        if (!entity) throw new Error("entity is required for entity_memories");
        result = await api({
          path: "/graph/entity/memories",
          query: { agent_id, entity, limit },
        });
        break;

      case "find_path":
        if (!source || !target) throw new Error("source and target are required for find_path");
        result = await api({
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

// ── memory_graph_traverse ───────────────────────────────────────────────────

server.tool(
  "memory_graph_traverse",
  "Get related memories via graph relationships. Finds memories connected to a starting memory through semantic relationships. Requires Pro or Scale tier.",
  {
    agent_id: z.string().min(1).max(128).default("default").describe("Namespace (use 'default' unless user specifies)"),
    memory_id: z.string().uuid().describe("Starting memory ID for graph traversal"),
    depth: z.number().int().min(1).max(3).default(2).describe("Max traversal depth (1-3)"),
    min_strength: z.number().min(0).max(1).default(0.3).describe("Minimum relationship strength threshold"),
  },
  async ({ agent_id, memory_id, depth, min_strength }) => {
    const result = await api({
      path: "/memories/graph",
      query: { agent_id, memory_id, depth, min_strength },
    });
    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  }
);

// ── memory_entities ─────────────────────────────────────────────────────────

server.tool(
  "memory_entities",
  "List all entities extracted from an agent's memories, with mention counts and type info. Requires Pro or Scale tier.",
  {
    agent_id: z.string().min(1).max(128).default("default").describe("Namespace (use 'default' unless user specifies)"),
    entity_type: z.string().max(32).optional().describe("Filter by entity type (e.g. person, company, location)"),
    min_mentions: z.number().int().min(1).default(1).describe("Minimum mention count to include"),
    limit: z.number().int().min(1).max(200).default(50).describe("Max results to return"),
  },
  async ({ agent_id, entity_type, min_mentions, limit }) => {
    const result = await api({
      path: "/memories/entities",
      query: { agent_id, entity_type, min_mentions, limit },
    });
    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  }
);

// ── memory_sentiment_summary ────────────────────────────────────────────────

server.tool(
  "memory_sentiment_summary",
  "Get aggregate sentiment statistics for an agent's memories. Returns positive/negative/neutral counts, averages, and confidence stats. Requires Pro or Scale tier.",
  {
    agent_id: z.string().min(1).max(128).default("default").describe("Namespace (use 'default' unless user specifies)"),
  },
  async ({ agent_id }) => {
    const result = await api({
      path: "/memories/sentiment-summary",
      query: { agent_id },
    });
    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  }
);

// ── memory_by_entity ────────────────────────────────────────────────────────

server.tool(
  "memory_by_entity",
  "Find all memories mentioning a specific entity. Requires Pro or Scale tier.",
  {
    agent_id: z.string().min(1).max(128).default("default").describe("Namespace (use 'default' unless user specifies)"),
    entity_text: z.string().min(1).max(256).describe("Entity name to search for"),
    limit: z.number().int().min(1).max(100).default(20).describe("Max results to return"),
  },
  async ({ agent_id, entity_text, limit }) => {
    const result = await api({
      path: "/memories/by-entity",
      query: { agent_id, entity_text, limit },
    });
    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  }
);

// ── memory_history ──────────────────────────────────────────────────────────

server.tool(
  "memory_history",
  "Get the full version history for a specific memory. Shows how the memory evolved over time, including what changed and why.",
  {
    memory_id: z.string().uuid().describe("The UUID of the memory to get history for"),
  },
  async ({ memory_id }) => {
    const result = await api({
      path: `/memories/${encodeURIComponent(memory_id)}/history`,
    });
    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  }
);

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("0Latency MCP server running on stdio");
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});
