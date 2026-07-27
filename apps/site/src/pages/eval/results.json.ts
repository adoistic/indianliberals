import { readFileSync } from "node:fs";
import type { APIRoute } from "astro";

// The graded run, question by question, including every per-source verdict the
// grader reached. Absent until a run has been graded — 404 rather than an empty
// object, so a consumer cannot mistake "not run yet" for "scored zero".
let results: unknown = null;
try {
  results = JSON.parse(
    readFileSync(new URL("../../../../../data/eval/results.json", import.meta.url), "utf-8"),
  );
} catch {
  results = null;
}

export const GET: APIRoute = () => {
  if (!results) {
    return new Response(JSON.stringify({ error: "No eval run has been graded yet." }, null, 1), {
      status: 404,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Access-Control-Allow-Origin": "*",
      },
    });
  }
  return new Response(JSON.stringify(results, null, 1), {
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "public, max-age=300, s-maxage=300",
      "Access-Control-Allow-Origin": "*",
    },
  });
};
