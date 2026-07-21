// Router for mcp.indianliberals.in — see wrangler.jsonc for deploy notes.
//
//   POST /mcp (or /)   MCP Streamable-HTTP JSON-RPC
//   GET  /             human landing page + connection instructions
//   GET  /api/<tool>   REST facade over the same tool registry
//   GET  /openapi.json OpenAPI 3.1 spec (ChatGPT Custom GPT Actions)
//   GET  /health       liveness + upstream check

import { Env, siteJson } from './data';
import { handleMcp } from './mcp';
import { handleRest, openApiSpec } from './rest';
import { landingPage } from './landing';

const CORS: Record<string, string> = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
  'Access-Control-Allow-Headers':
    'Content-Type, Authorization, Accept, Mcp-Session-Id, MCP-Protocol-Version, Last-Event-ID',
  'Access-Control-Expose-Headers': 'Mcp-Session-Id, MCP-Protocol-Version',
  'Access-Control-Max-Age': '86400',
};

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, '') || '/';

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS });
    }

    // MCP endpoint — canonical at /mcp; POST / accepted too so a pasted
    // bare domain works in connector dialogs. /sse redirects clients of
    // the legacy transport to the modern endpoint.
    if (path === '/mcp' || (path === '/' && request.method === 'POST')) {
      return handleMcp(request, env, CORS);
    }
    if (path === '/sse') {
      return new Response(
        JSON.stringify({
          error:
            'The legacy HTTP+SSE transport is not served. Use Streamable HTTP at https://mcp.indianliberals.in/mcp (all current MCP clients support it).',
        }),
        { status: 400, headers: { ...CORS, 'Content-Type': 'application/json' } },
      );
    }

    if (path === '/' ) {
      return landingPage(env);
    }

    if (path === '/openapi.json') {
      return new Response(JSON.stringify(openApiSpec(url.origin), null, 2), {
        headers: {
          ...CORS,
          'Content-Type': 'application/json; charset=utf-8',
          'Cache-Control': 'public, max-age=300',
        },
      });
    }

    if (path.startsWith('/api/')) {
      return handleRest(request, env, path.slice('/api/'.length), CORS);
    }

    if (path === '/health') {
      let upstream = 'ok';
      try {
        await siteJson(env, '/api/meta.json');
      } catch (e) {
        upstream = `degraded: ${(e as Error).message}`;
      }
      return new Response(JSON.stringify({ status: 'ok', upstream }), {
        headers: { ...CORS, 'Content-Type': 'application/json' },
      });
    }

    if (path === '/robots.txt') {
      return new Response('User-agent: *\nAllow: /\n', {
        headers: { 'Content-Type': 'text/plain' },
      });
    }

    return new Response(JSON.stringify({ error: 'Not found. Docs: https://mcp.indianliberals.in/' }), {
      status: 404,
      headers: { ...CORS, 'Content-Type': 'application/json' },
    });
  },
};
