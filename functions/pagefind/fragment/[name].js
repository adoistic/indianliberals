// `/pagefind/fragment/<name>.pf_fragment` — one record of the site's own
// Pagefind index, the one behind the header quick search.
//
// These used to be ~9,700 files in the Pages deployment, nearly half of the
// 20,000-file limit. After the Quest ingestion added 595 thinker pages the
// build reached 20,478 files and the deploy stopped; the site kept serving the
// previous build. The bytes are unchanged and the URL is unchanged — only the
// storage moved, exactly as it did for /api/works/<id>.json and the .md
// siblings. See scripts/deploy/pack-agent-surfaces.mjs.
//
// Only the fragments moved. pagefind.js, the wasm, index/ and filter/ are
// still static files in the deployment, so a query resolves same-origin and at
// full speed; this route is hit only for the records of results actually shown.
import { serveFromPack } from "../../_agent/pack.js";

export async function onRequestGet({ params, next }) {
  const name = Array.isArray(params.name) ? params.name.join("/") : params.name;
  // Anything that is not a fragment request falls through untouched rather
  // than being answered here, on the same reasoning as functions/[collection].
  if (!name || !name.endsWith(".pf_fragment")) return next();
  const res = await serveFromPack(
    "pagefind-fragments",
    `/pagefind/fragment/${name}`,
    "application/octet-stream",
  );
  // A fragment the index does not know is a genuine 404, not a fall-through:
  // Pagefind asks for these by content hash, so a miss means a stale client.
  return res ?? new Response("Not found", { status: 404 });
}

// HEAD must agree with GET; see functions/api/works/[id].js.
export async function onRequestHead(context) {
  const res = await onRequestGet(context);
  return new Response(null, { status: res.status, headers: res.headers });
}
