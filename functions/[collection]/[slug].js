// `<page-url>.md` — the clean markdown body of any detail page.
//
// Published in public/SKILL.md (line 38) and AGENTS.md (lines 94, 128, 133).
// The bytes are unchanged; only the storage moved. See functions/_agent/pack.js.
//
// This route pattern matches every two-segment path on the site, so it has to
// be careful in two directions:
//
//   * Static assets win over Functions on Pages, so /musings/<slug>/ and every
//     other real page still serves from the deployment and never reaches this
//     code. That precedence is what docs/ccs-round-4-fixes-2026-08-14.md
//     relied on when the legacy redirect Functions were added.
//   * Anything that is not a `.md` request must fall through untouched rather
//     than be answered here, or this becomes the site's 404 handler and
//     swallows the legacy WordPress redirects.
import { serveFromPack } from "../_agent/pack.js";

export async function onRequestGet(context) {
  const { params, next } = context;
  const collection = params.collection;
  const slug = Array.isArray(params.slug) ? params.slug.join("/") : params.slug;
  if (!slug || !slug.endsWith(".md")) return next();
  const res = await serveFromPack("pages-md", `/${collection}/${slug}`, "text/markdown; charset=utf-8");
  return res ?? next();
}
