/**
 * Minimal inline-markdown → HTML transformer for short single-line strings
 * (pull quotes, key concepts, etc.). Handles the three patterns that actually
 * occur in the corpus:
 *
 *   **bold**       → <strong>bold</strong>
 *   _italic_       → <em>italic</em>
 *   *italic*       → <em>italic</em>
 *
 * Everything else is HTML-escaped. The transform is safe to feed into
 * Astro's `set:html` because the only HTML it can produce is <strong> and
 * <em>; arbitrary HTML in the input is escaped, not passed through.
 *
 * Why not use a real markdown library here? `marked` / `remark` are great
 * for whole-document rendering, but for a single-sentence pull quote we
 * just need three patterns. Adding a dep would be over-engineering.
 */

const HTML_ESCAPES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => HTML_ESCAPES[c]);
}

/**
 * Convert a short string with inline markdown to safe HTML.
 *
 * The transform order matters:
 *   1. Escape HTML first (so user content is safe).
 *   2. Apply `**...**` before `*...*` so bold isn't half-eaten by italic.
 *   3. Apply `_..._` (the case-citation pattern in our corpus). The regex
 *      is anchored on word boundaries so it doesn't match snake_case slugs
 *      mid-token.
 */
export function inlineMd(s: string): string {
  if (!s) return "";
  let out = escapeHtml(s);
  // **bold** — non-greedy, must not span whitespace at the boundaries
  out = out.replace(/\*\*(\S(?:.*?\S)?)\*\*/g, "<strong>$1</strong>");
  // *italic* — same shape
  out = out.replace(/(^|[\s(\[])\*(\S(?:.*?\S)?)\*(?=[\s).,;:!?\]]|$)/g, "$1<em>$2</em>");
  // _italic_ — bounded by word breaks so snake_case in identifiers is left alone
  out = out.replace(/(^|[\s(\[])_(\S(?:.*?\S)?)_(?=[\s).,;:!?\]]|$)/g, "$1<em>$2</em>");
  return out;
}
