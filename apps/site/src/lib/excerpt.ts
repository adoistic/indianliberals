// Meta-description excerpt from a raw markdown body.
//
// Musings and opinions carry no frontmatter description; without this they
// all fell back to BaseLayout's sitewide default, giving 250+ pages an
// identical meta description (a duplicate-content signal and a wasted SERP
// snippet). Strategy: prefer the classification pass's pull_quote, else the
// first ~160 chars of prose with markdown syntax stripped.

export function metaExcerpt(md: string, max = 160): string {
  const text = md
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/^#{1,6}\s+.*$/gm, " ")
    .replace(/[*_>`]/g, "")
    .replace(/\s+/g, " ")
    .trim();
  if (text.length <= max) return text;
  const cut = text.slice(0, max);
  const atWord = cut.slice(0, cut.lastIndexOf(" "));
  return `${atWord}…`;
}
