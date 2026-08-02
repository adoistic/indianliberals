import type { APIRoute } from "astro";
import { getCollection } from "astro:content";
import { isListed } from "~/lib/listable";

export const GET: APIRoute = async () => {
  const thinkers = await getCollection("thinkers", (t) => !t.data.draft);
  const works = await getCollection("primary-works", isListed);

  const lines: string[] = [
    "# Indian Liberals",
    "",
    "> A modern digital archive of the Indian liberal tradition.",
    "> Maintained by the Centre for Civil Society (CCS).",
    "",
    "See /AGENTS.md for the citation policy and schema. The full archive",
    "in one file lives at /llms-full.txt.",
    "",
    "## Browse",
    "",
    "- [Curated thinker canon](/thinkers/)",
    "- [Full directory of people](/thinkers/directory/) — includes referenced",
    "  figures from outside the liberal tradition (cited or critiqued, not endorsed)",
    "- [Periodicals by series](/periodicals/)",
    "- [Interviews & oral history](/interviews/) — recordings with transcripts,",
    "  dated by when they were conducted (not when digitised)",
    "- [Organisations](/organisations/)",
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
