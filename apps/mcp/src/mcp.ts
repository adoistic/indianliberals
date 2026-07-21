// MCP Streamable-HTTP transport, stateless mode.
//
// Implements the JSON-RPC surface every MCP client needs from a public
// read-only server: initialize / ping / tools/list / tools/call (plus
// empty resources/ and prompts/ lists for clients that probe them).
// No sessions, no server-initiated streams — the spec explicitly allows
// both for stateless servers, and it is what keeps this Worker trivially
// scalable and maintenance-free.
//
// Works with: Claude (claude.ai custom connectors, Claude Code, Claude
// Desktop, Anthropic API mcp_servers), ChatGPT connectors, OpenAI
// Responses API remote MCP, Cursor, Codex, Windsurf, Gemini SDK,
// mcp-remote for stdio-only clients.

import { Env, ToolError } from './data';
import { TOOLS, findTool } from './tools';

const SUPPORTED_VERSIONS = ['2025-06-18', '2025-03-26', '2024-11-05'];
const LATEST_VERSION = SUPPORTED_VERSIONS[0];

const SERVER_INFO = {
  name: 'indian-liberals-archive',
  title: 'Indian Liberals Archive',
  version: '1.0.0',
};

const INSTRUCTIONS =
  'Digital archive of the Indian liberal tradition (Centre for Civil Society). ' +
  'Two-tier corpus: Tier A (clean full text — thinkers, organisations, musings, opinions, interviews, ThePrint mirror) ' +
  'may be quoted with paragraph-anchor citations; Tier B (primary-work PDFs) exposes AI summaries only — ' +
  'attribute those as "Indian Liberals\' summary of <work>" and link the PDF. ' +
  'Typical flow: read_index → search_corpus / list_works / list_thinkers → ' +
  'read_clean_content or get_work_metadata → get_passage for exact citations.';

interface JsonRpcMessage {
  jsonrpc?: string;
  id?: number | string | null;
  method?: string;
  params?: any;
  result?: any;
  error?: any;
}

function rpcResult(id: number | string | null | undefined, result: unknown) {
  return { jsonrpc: '2.0', id: id ?? null, result };
}

function rpcError(id: number | string | null | undefined, code: number, message: string) {
  return { jsonrpc: '2.0', id: id ?? null, error: { code, message } };
}

function toolDefs() {
  return TOOLS.map((t) => ({
    name: t.name,
    description: t.description,
    inputSchema: t.inputSchema,
    annotations: { readOnlyHint: true, openWorldHint: false },
  }));
}

async function dispatch(msg: JsonRpcMessage, env: Env): Promise<object | null> {
  const { id, method, params } = msg;

  // Notifications (no id): acknowledge silently.
  if (id === undefined && method?.startsWith('notifications/')) return null;

  switch (method) {
    case 'initialize': {
      const requested = params?.protocolVersion;
      const protocolVersion = SUPPORTED_VERSIONS.includes(requested) ? requested : LATEST_VERSION;
      return rpcResult(id, {
        protocolVersion,
        capabilities: { tools: { listChanged: false } },
        serverInfo: SERVER_INFO,
        instructions: INSTRUCTIONS,
      });
    }
    case 'ping':
      return rpcResult(id, {});
    case 'tools/list':
      return rpcResult(id, { tools: toolDefs() });
    case 'tools/call': {
      const name = params?.name;
      const tool = name && findTool(name);
      if (!tool) return rpcError(id, -32602, `Unknown tool: ${name}`);
      const args = params?.arguments ?? {};
      // Minimal required-field validation
      const required: string[] = (tool.inputSchema.required as string[]) ?? [];
      for (const req of required) {
        if (args[req] === undefined || args[req] === null || args[req] === '') {
          return rpcResult(id, {
            content: [{ type: 'text', text: `Missing required argument "${req}".` }],
            isError: true,
          });
        }
      }
      try {
        const result = await tool.handler(args, env);
        return rpcResult(id, { content: [{ type: 'text', text: result.text }] });
      } catch (e) {
        const message = e instanceof ToolError ? e.message : `Internal error: ${(e as Error).message}`;
        return rpcResult(id, { content: [{ type: 'text', text: message }], isError: true });
      }
    }
    case 'resources/list':
      return rpcResult(id, { resources: [] });
    case 'resources/templates/list':
      return rpcResult(id, { resourceTemplates: [] });
    case 'prompts/list':
      return rpcResult(id, { prompts: [] });
    case 'logging/setLevel':
      return rpcResult(id, {});
    default:
      if (id === undefined) return null; // unknown notification — ignore
      return rpcError(id, -32601, `Method not found: ${method}`);
  }
}

/** Wrap a JSON payload as a single-event SSE stream (for clients that only accept text/event-stream). */
function sseResponse(payload: unknown, headers: Record<string, string>): Response {
  const body = `event: message\ndata: ${JSON.stringify(payload)}\n\n`;
  return new Response(body, {
    status: 200,
    headers: { ...headers, 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-store' },
  });
}

export async function handleMcp(request: Request, env: Env, cors: Record<string, string>): Promise<Response> {
  if (request.method === 'GET') {
    // Stateless server: no server-initiated SSE stream to offer.
    return new Response(
      JSON.stringify({
        jsonrpc: '2.0',
        error: {
          code: -32000,
          message: 'This MCP endpoint is stateless: open no GET stream, POST JSON-RPC messages here instead. Human-readable docs: https://mcp.indianliberals.in/',
        },
        id: null,
      }),
      { status: 405, headers: { ...cors, 'Content-Type': 'application/json', Allow: 'POST, OPTIONS' } },
    );
  }
  if (request.method === 'DELETE') {
    // No sessions to delete in stateless mode.
    return new Response(null, { status: 405, headers: { ...cors, Allow: 'POST, OPTIONS' } });
  }
  if (request.method !== 'POST') {
    return new Response('Method Not Allowed', { status: 405, headers: { ...cors, Allow: 'POST, OPTIONS' } });
  }

  let parsed: unknown;
  try {
    parsed = await request.json();
  } catch {
    return new Response(
      JSON.stringify(rpcError(null, -32700, 'Parse error: body must be JSON-RPC')),
      { status: 400, headers: { ...cors, 'Content-Type': 'application/json' } },
    );
  }

  const messages: JsonRpcMessage[] = Array.isArray(parsed) ? parsed : [parsed as JsonRpcMessage];
  const responses: object[] = [];
  for (const msg of messages) {
    if (!msg || typeof msg !== 'object' || (msg.method === undefined && msg.result === undefined && msg.error === undefined)) {
      responses.push(rpcError(null, -32600, 'Invalid request'));
      continue;
    }
    if (msg.method === undefined) continue; // client → server response; nothing to do
    const res = await dispatch(msg, env);
    if (res) responses.push(res);
  }

  // Only notifications/responses → 202 Accepted, no body (per spec).
  if (responses.length === 0) {
    return new Response(null, { status: 202, headers: cors });
  }

  const payload = Array.isArray(parsed) ? responses : responses[0];
  const accept = request.headers.get('Accept') ?? '';
  const wantsSseOnly = accept.includes('text/event-stream') && !accept.includes('application/json');
  if (wantsSseOnly) return sseResponse(payload, cors);

  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { ...cors, 'Content-Type': 'application/json' },
  });
}
