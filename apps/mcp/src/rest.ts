// REST facade + OpenAPI spec — the same tool registry exposed as plain
// GET/POST endpoints so ANY HTTP-capable agent stack can use the archive:
// ChatGPT Custom GPT Actions (which need OpenAPI, not MCP), OpenAI /
// Gemini / OpenRouter function calling, LangChain, plain curl.
//
//   GET  /api/<tool>?arg=value          (arrays: comma-separated)
//   POST /api/<tool>   {json args}
//   GET  /openapi.json                  (OpenAPI 3.1, import as GPT Action)

import { Env, ToolError } from './data';
import { TOOLS, findTool } from './tools';

/** Coerce query-string values per the tool's JSON-Schema property types. */
function coerceArgs(tool: { inputSchema: any }, params: URLSearchParams): Record<string, unknown> {
  const props = (tool.inputSchema.properties ?? {}) as Record<string, any>;
  const args: Record<string, unknown> = {};
  for (const [key, raw] of params.entries()) {
    const spec = props[key];
    if (!spec) continue;
    if (spec.type === 'integer' || spec.type === 'number') args[key] = Number(raw);
    else if (spec.type === 'boolean') args[key] = raw === 'true' || raw === '1';
    else if (spec.type === 'array') args[key] = raw.split(',').map((s) => s.trim()).filter(Boolean);
    else args[key] = raw;
  }
  return args;
}

export async function handleRest(
  request: Request,
  env: Env,
  toolName: string,
  cors: Record<string, string>,
): Promise<Response> {
  const tool = findTool(toolName);
  const jsonHeaders = { ...cors, 'Content-Type': 'application/json; charset=utf-8' };
  if (!tool) {
    return new Response(
      JSON.stringify({ error: `Unknown tool "${toolName}"`, available: TOOLS.map((t) => t.name) }),
      { status: 404, headers: jsonHeaders },
    );
  }

  let args: Record<string, unknown> = {};
  if (request.method === 'POST') {
    try {
      args = ((await request.json()) as Record<string, unknown>) ?? {};
    } catch {
      return new Response(JSON.stringify({ error: 'POST body must be JSON' }), { status: 400, headers: jsonHeaders });
    }
  } else {
    args = coerceArgs(tool, new URL(request.url).searchParams);
  }

  const required: string[] = (tool.inputSchema.required as string[]) ?? [];
  for (const req of required) {
    if (args[req] === undefined || args[req] === null || args[req] === '') {
      return new Response(
        JSON.stringify({ error: `Missing required parameter "${req}"`, schema: tool.inputSchema }),
        { status: 400, headers: jsonHeaders },
      );
    }
  }

  try {
    const result = await tool.handler(args as Record<string, any>, env);
    const body = result.json ?? { text: result.text };
    return new Response(JSON.stringify(body), {
      headers: { ...jsonHeaders, 'Cache-Control': 'public, max-age=120' },
    });
  } catch (e) {
    const status = e instanceof ToolError ? e.status : 500;
    const message = e instanceof ToolError ? e.message : `Internal error: ${(e as Error).message}`;
    return new Response(JSON.stringify({ error: message }), { status, headers: jsonHeaders });
  }
}

export function openApiSpec(origin: string): object {
  const paths: Record<string, unknown> = {};
  for (const tool of TOOLS) {
    const props = (tool.inputSchema as any).properties ?? {};
    const required: string[] = (tool.inputSchema as any).required ?? [];
    const parameters = Object.entries(props).map(([name, spec]: [string, any]) => ({
      name,
      in: 'query',
      required: required.includes(name),
      description:
        (spec.description ?? '') + (spec.type === 'array' ? ' (comma-separated list)' : ''),
      schema:
        spec.type === 'array'
          ? { type: 'string' }
          : { type: spec.type === 'integer' ? 'integer' : spec.type ?? 'string' },
    }));
    paths[`/api/${tool.name}`] = {
      get: {
        operationId: tool.name,
        summary: tool.description.split('. ')[0],
        description: tool.description,
        parameters,
        responses: {
          '200': {
            description: 'Tool result',
            content: { 'application/json': { schema: { type: 'object' } } },
          },
        },
      },
    };
  }
  return {
    openapi: '3.1.0',
    info: {
      title: 'Indian Liberals Archive API',
      description:
        'Read-only API over the Indian Liberals digital archive (indianliberals.in), maintained by the Centre for Civil Society. ' +
        'Tier A results are quotable full text; Tier B results are AI summaries of primary-work PDFs — attribute accordingly (see https://indianliberals.in/AGENTS.md). ' +
        'Same tools are available over MCP at https://mcp.indianliberals.in/mcp.',
      version: '1.0.0',
      contact: { url: 'https://indianliberals.in/about/' },
    },
    servers: [{ url: origin }],
    paths,
  };
}
