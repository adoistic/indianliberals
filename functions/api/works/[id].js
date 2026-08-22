// `/api/works/<id>.json` — one work's detail record.
//
// Published in public/SKILL.md and AGENTS.md, and fetched by the MCP server
// (apps/mcp/src/tools.ts:226 and :457). The bytes are unchanged; only the
// storage moved off the Pages deployment. See functions/_agent/pack.js.
import { serveFromPack } from "../../_agent/pack.js";

export async function onRequestGet({ params }) {
  const id = Array.isArray(params.id) ? params.id.join("/") : params.id;
  if (!id || !id.endsWith(".json")) return new Response("Not found", { status: 404 });
  const res = await serveFromPack("api-works", `/api/works/${id}`, "application/json; charset=utf-8");
  return res ?? new Response("Not found", { status: 404 });
}
