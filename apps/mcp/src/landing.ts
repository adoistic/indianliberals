// Human-readable landing page at https://mcp.indianliberals.in/ —
// connection instructions for every client shape, with live counts.

import { Env, siteJson } from './data';
import { TOOLS } from './tools';

export async function landingPage(env: Env): Promise<Response> {
  let counts = '';
  try {
    const meta = await siteJson<any>(env, '/api/meta.json');
    const c = meta.counts;
    counts = `${c.primary_works} works · ${c.thinkers} thinkers · ${c.musings} musings · ${c.opinions} opinions · ${c.organisations} organisations · ${c.theprint_mirror} ThePrint columns`;
  } catch {
    counts = 'live counts unavailable right now';
  }

  const toolRows = TOOLS.map(
    (t) =>
      `<tr><td><code>${t.name}</code></td><td>${t.description.replace(/</g, '&lt;')}</td></tr>`,
  ).join('\n');

  const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Indian Liberals MCP server</title>
<style>
  :root { color-scheme: light dark; }
  body { font: 16px/1.6 ui-sans-serif, system-ui, sans-serif; max-width: 46rem; margin: 2rem auto 6rem; padding: 0 1.25rem; }
  h1 { font-size: 1.6rem; } h2 { font-size: 1.15rem; margin-top: 2.2rem; }
  code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .85em; }
  pre { background: rgba(125,125,125,.12); padding: .8rem 1rem; border-radius: 8px; overflow-x: auto; }
  code { background: rgba(125,125,125,.12); padding: .1em .35em; border-radius: 4px; }
  pre code { background: none; padding: 0; }
  table { border-collapse: collapse; width: 100%; font-size: .9rem; }
  td { border-top: 1px solid rgba(125,125,125,.25); padding: .45rem .5rem; vertical-align: top; }
  td:first-child { white-space: nowrap; }
  .muted { opacity: .7; }
  a { color: #b45309; }
</style>
</head>
<body>
<h1>Indian Liberals — MCP server</h1>
<p>Query the <a href="https://indianliberals.in">Indian Liberals archive</a> (Centre for Civil Society) from any AI client or agent framework. Read-only, no authentication, free.</p>
<p class="muted">${counts}</p>

<h2>Endpoints</h2>
<pre><code>MCP (Streamable HTTP):  https://mcp.indianliberals.in/mcp
REST:                   https://mcp.indianliberals.in/api/&lt;tool&gt;
OpenAPI 3.1 spec:       https://mcp.indianliberals.in/openapi.json</code></pre>

<h2>Claude (claude.ai, Desktop, mobile)</h2>
<p>Settings → Connectors → <b>Add custom connector</b> → URL:</p>
<pre><code>https://mcp.indianliberals.in/mcp</code></pre>

<h2>Claude Code</h2>
<pre><code>claude mcp add --transport http indian-liberals https://mcp.indianliberals.in/mcp</code></pre>

<h2>ChatGPT</h2>
<p><b>Connector</b> (Settings → Connectors → Advanced → Developer mode → Add): use the MCP URL above — the required <code>search</code> and <code>fetch</code> tools are provided.<br>
<b>Custom GPT Action</b>: in the GPT editor choose "Create new action" → "Import from URL" → <code>https://mcp.indianliberals.in/openapi.json</code> (auth: none).</p>

<h2>Cursor / Windsurf / VS Code / other MCP clients</h2>
<pre><code>{
  "mcpServers": {
    "indian-liberals": { "url": "https://mcp.indianliberals.in/mcp" }
  }
}</code></pre>
<p class="muted">Clients that only speak stdio: <code>npx mcp-remote https://mcp.indianliberals.in/mcp</code></p>

<h2>Anthropic API (server-side MCP)</h2>
<pre><code>"mcp_servers": [{ "type": "url", "url": "https://mcp.indianliberals.in/mcp", "name": "indian-liberals" }]</code></pre>

<h2>OpenAI Responses API</h2>
<pre><code>"tools": [{ "type": "mcp", "server_label": "indian-liberals", "server_url": "https://mcp.indianliberals.in/mcp", "require_approval": "never" }]</code></pre>

<h2>Gemini / OpenRouter / anything else</h2>
<p>Use the MCP URL with any MCP-capable SDK, or call the REST endpoints directly as function tools — try <a href="/api/search_corpus?query=swatantra%20party">/api/search_corpus?query=swatantra party</a>.</p>

<h2>Tools</h2>
<table>${toolRows}</table>

<h2>Citation policy</h2>
<p><b>Tier A</b> (thinker profiles, organisations, musings, opinions, interview transcripts, ThePrint mirror): quote freely, cite <code>&lt;url&gt;#p-xxxxxx</code> paragraph anchors.
<b>Tier B</b> (primary-work PDFs): tools return AI summaries — attribute claims as "Indian Liberals' summary of &lt;work&gt;" and link the PDF. Full policy: <a href="https://indianliberals.in/AGENTS.md">indianliberals.in/AGENTS.md</a>.</p>

<p class="muted">The server is a stateless proxy over the archive's build artifacts — it updates automatically as the collection grows. Maintained by CCS; rebuilt by <a href="https://thothica.com">Thothica</a>.</p>
</body>
</html>`;

  return new Response(html, {
    headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'public, max-age=300' },
  });
}
