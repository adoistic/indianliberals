// archive.indianliberals.in — serve the bucket, with a real front page at "/".
//
// The hostname is an R2 custom domain, which maps a request path straight to an
// object key. R2 has no index-document resolution, so "/" maps to the empty key
// and 404s: the archive had no front door. This Worker sits on the hostname and
// does exactly two things.
//
//   1. "/" (and any "…/") -> the landing page object.
//   2. everything else    -> the object at that key, byte for byte.
//
// Rule 2 is the one that must not regress. 1,457 PDFs, 1,456 covers and the OG
// cards already serve from here and have to keep behaving identically —
// including Range requests, which PDF viewers use to seek instead of pulling
// whole files. So `range`/`onlyIf` are only forwarded when the client actually
// sent them: passing the whole header bag unconditionally makes R2 report a
// range on ordinary GETs and turns every 200 into a 206.

const INDEX_KEY = "index.html";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method Not Allowed", {
        status: 405,
        headers: { allow: "GET, HEAD" },
      });
    }

    // Object keys contain spaces and "&", so undo percent-encoding.
    let key;
    try {
      key = decodeURIComponent(url.pathname.slice(1));
    } catch {
      key = url.pathname.slice(1);
    }
    if (key === "" || key.endsWith("/")) key += INDEX_KEY;

    const rangeHeader = request.headers.get("range");
    const hasPrecondition =
      request.headers.has("if-none-match") || request.headers.has("if-modified-since");

    const options = {};
    if (rangeHeader) options.range = request.headers;
    if (hasPrecondition) options.onlyIf = request.headers;

    let object = await env.ARCHIVE.get(key, options);

    // Cover thumbnails for the Swatantra papers are packed.
    //
    // 6,355 covers as individual objects is not the problem — R2 has no file
    // cap — but PUTting them one at a time through wrangler is, at roughly a
    // second of process startup each. They therefore live in one blob with an
    // offset index, and are served from a byte range here so that the public
    // URL is unchanged: archive.indianliberals.in/covers/<slug>.webp resolves
    // whether the cover is an individual object (the 1,463 older ones) or a
    // slice of the pack.
    //
    // Individual objects win, so a cover can always be replaced by uploading
    // it normally without touching the pack.
    if (object === null && key.startsWith("covers/") && key.endsWith(".webp")) {
      const packed = await coverFromPack(env, key);
      if (packed) return packed;
    }

    if (object === null) {
      return new Response("Not Found", {
        status: 404,
        headers: { "content-type": "text/plain; charset=utf-8" },
      });
    }

    const headers = new Headers();
    object.writeHttpMetadata(headers);
    headers.set("etag", object.httpEtag);
    headers.set("accept-ranges", "bytes");
    // The full-text search bundle under search/ is imported cross-origin by
    // indianliberals.in (dynamic import of pagefind.js + fetch of its wasm and
    // fragment files), which the browser only allows with CORS. The archive is
    // public, so open it to any origin.
    headers.set("access-control-allow-origin", "*");
    // The landing page changes as the archive grows; the documents never do.
    // The search/ bundle sits in between: it is rebuilt after each ingestion.
    // Pagefind content-hashes the filenames under fragment/ and index/, so
    // those stay immutable; everything else in search/ (pagefind.js, the
    // entry json, the per-language wasm) is overwritten in place on rebuild
    // and must stay fresh.
    const isSearchMutable =
      key.startsWith("search/") &&
      !key.startsWith("search/fragment/") &&
      !key.startsWith("search/index/");
    // OG cards and covers are re-rendered in place when a title or picture
    // changes (the og-cards workflow, and cover replacement in the CMS), so
    // they must be allowed to go stale within a day rather than never.
    const isOverwritable = key.startsWith("og/") || key.startsWith("covers/");
    headers.set(
      "cache-control",
      key === INDEX_KEY || isSearchMutable
        ? "public, max-age=300"
        : isOverwritable
          ? "public, max-age=86400"
          : "public, max-age=31536000, immutable",
    );

    // A precondition that matched: R2 returns the metadata with no body.
    if (!("body" in object) || object.body === null) {
      return new Response(null, { status: 304, headers });
    }

    let status = 200;
    if (rangeHeader && object.range && "offset" in object.range) {
      const start = object.range.offset ?? 0;
      const length = object.range.length ?? object.size - start;
      headers.set("content-range", `bytes ${start}-${start + length - 1}/${object.size}`);
      headers.set("content-length", String(length));
      status = 206;
    } else {
      // writeHttpMetadata does NOT set content-length. Without this a HEAD —
      // which carries no body to infer the size from — advertises 0 bytes, so
      // crawlers and download managers see every document as empty.
      headers.set("content-length", String(object.size));
    }

    return new Response(request.method === "HEAD" ? null : object.body, { status, headers });
  },
};


// ---------------------------------------------------------------------------
// Packed cover lookup.
//
// The index is a flat { "covers/<slug>.webp": [offset, length] } map, small
// enough to hold in module scope between requests on a warm isolate. A cold
// isolate pays one extra GET.
let coverIndex = null;

async function coverFromPack(env, key) {
  if (coverIndex === null) {
    const idx = await env.ARCHIVE.get("covers/_pack.idx.json");
    // Cache the miss as an empty map too: without the pack uploaded, every
    // request for an un-covered work would otherwise re-fetch the index.
    coverIndex = idx ? await idx.json() : {};
  }
  const entry = coverIndex[key];
  if (!entry) return null;
  const [offset, length] = entry;
  const object = await env.ARCHIVE.get("covers/_pack.webpack", {
    range: { offset, length },
  });
  if (!object) return null;
  return new Response(object.body, {
    status: 200,
    headers: {
      "content-type": "image/webp",
      "cache-control": "public, max-age=31536000, immutable",
      "access-control-allow-origin": "*",
    },
  });
}
