// Serve a record out of a packed blob on R2, over a byte range.
//
// The per-work agent surfaces (`/api/works/<id>.json` and `<page-url>.md`)
// used to be 16,835 separate files in the Pages deployment, which put the
// build at 35,841 files against a 20,000 limit. They now live in two packed
// blobs on R2 with an offset index; these helpers turn a URL back into the
// same bytes it used to serve.
//
// Fetched over HTTP from archive.indianliberals.in rather than through an R2
// binding: that host is already a Worker in front of the bucket
// (apps/archive-root) and it forwards Range headers, so this needs no new
// binding on the Pages project and no new credentials.

const ARCHIVE = "https://archive.indianliberals.in/agent";

// Module scope survives between requests on a warm isolate, so the index is
// fetched once per isolate rather than once per request. A cold isolate pays
// one extra round trip.
const indexCache = new Map();

async function loadIndex(family) {
  if (!indexCache.has(family)) {
    indexCache.set(family, (async () => {
      const r = await fetch(`${ARCHIVE}/${family}.idx.json`, {
        cf: { cacheTtl: 3600, cacheEverything: true },
      });
      if (!r.ok) throw new Error(`index ${family}: ${r.status}`);
      return r.json();
    })().catch((e) => { indexCache.delete(family); throw e; }));
  }
  return indexCache.get(family);
}

export async function serveFromPack(family, urlPath, contentType) {
  let idx;
  try {
    idx = await loadIndex(family);
  } catch {
    // A missing or unreachable index must not masquerade as a missing
    // document: 404 would tell an agent the work does not exist.
    return new Response("agent surface temporarily unavailable", {
      status: 503,
      headers: { "content-type": "text/plain; charset=utf-8" },
    });
  }
  const entry = idx[urlPath];
  if (!entry) return null;                 // genuinely not a known record
  const [offset, length] = entry;
  const r = await fetch(`${ARCHIVE}/${family}.pack`, {
    headers: { Range: `bytes=${offset}-${offset + length - 1}` },
  });
  if (!r.ok && r.status !== 206) {
    return new Response("agent surface temporarily unavailable", { status: 503 });
  }
  const headers = new Headers({
    "content-type": contentType,
    "cache-control": "public, max-age=3600",
    "access-control-allow-origin": "*",
  });
  return new Response(r.body, { status: 200, headers });
}
