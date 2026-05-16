import type { APIRoute } from "astro";
import { getCollection } from "astro:content";

export const GET: APIRoute = async () => {
  const thinkers = await getCollection("thinkers", (t) => !t.data.draft);
  const works = await getCollection("primary-works", (w) => !w.data.draft);

  const lines: string[] = [
    "# Indian Liberals",
    "",
    "> A modern digital archive of the Indian liberal tradition.",
    "> Maintained by the Centre for Civil Society (CCS) in partnership",
    "> with the Friedrich Naumann Foundation for Freedom.",
    "",
    "See /AGENTS.md for the citation policy and schema. The full archive",
    "in one file lives at /llms-full.txt.",
    "",
    "## Thinkers",
    "",
    ...thinkers.map(
      (t) => `- [${t.data.name.canonical}](/thinkers/${t.id}/) — ${t.data.tradition.replace(/_/g, " ")}${t.data.birth_year ? ` (${t.data.birth_year}–${t.data.death_year ?? ""})` : ""}`,
    ),
    "",
    "## Primary works",
    "",
    ...works.map(
      (w) => `- [${w.data.title.main}](/primary-works/${w.id}/) — ${w.data.work_type} (${w.data.publication.year ?? "n.d."})`,
    ),
    "",
  ];

  return new Response(lines.join("\n"), {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
};
