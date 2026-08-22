// `/llms-full.txt` — the whole Tier-A corpus plus every Tier-B summary.
//
// Published in public/SKILL.md (line 40) and AGENTS.md (line 132). At 29 MB it
// exceeds Cloudflare Pages' 25 MiB per-file limit, so it is stored on R2 and
// streamed through here. Range requests are forwarded so a client can resume
// or seek rather than re-pull 29 MB.
const ARCHIVE = "https://archive.indianliberals.in/agent/llms-full.txt";

export async function onRequestGet({ request }) {
  const range = request.headers.get("range");
  const upstream = await fetch(ARCHIVE, range ? { headers: { Range: range } } : {});
  if (!upstream.ok && upstream.status !== 206) {
    return new Response("llms-full.txt temporarily unavailable", {
      status: 503,
      headers: { "content-type": "text/plain; charset=utf-8" },
    });
  }
  const headers = new Headers({
    "content-type": "text/plain; charset=utf-8",
    "cache-control": "public, max-age=3600",
    "access-control-allow-origin": "*",
    "accept-ranges": "bytes",
  });
  for (const h of ["content-range", "content-length", "etag"]) {
    const v = upstream.headers.get(h);
    if (v) headers.set(h, v);
  }
  return new Response(upstream.body, { status: upstream.status, headers });
}
