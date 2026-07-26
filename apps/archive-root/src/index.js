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

    const object = await env.ARCHIVE.get(key, options);

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
    // The landing page changes as the archive grows; the documents never do.
    headers.set(
      "cache-control",
      key === INDEX_KEY ? "public, max-age=300" : "public, max-age=31536000, immutable",
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
