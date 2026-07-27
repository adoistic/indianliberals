import type { APIRoute } from "astro";
import pool from "../../../../../data/eval/pool.json";

// The frozen question pool, served raw. Publishing it is the point: a score
// nobody can re-derive is an assertion, not a measurement.
export const GET: APIRoute = () =>
  new Response(JSON.stringify(pool, null, 1), {
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "public, max-age=300, s-maxage=300",
      "Access-Control-Allow-Origin": "*",
    },
  });
