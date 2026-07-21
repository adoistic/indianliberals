// Remark plugin: stamp every top-level paragraph with a stable
// content-hash anchor (id="p-xxxxxx") so Tier-A pages are deep-link
// citable at paragraph granularity — the citation primitive promised in
// /AGENTS.md and served by the MCP server's get_passage tool.
//
// ID derivation lives in ../lib/paragraph-id.mjs (shared with the .md
// sibling annotator so both surfaces mint identical IDs).

import { toString } from 'mdast-util-to-string';
import { paragraphIdsFor } from '../lib/paragraph-id.mjs';

export function remarkParagraphIds() {
  return (tree) => {
    const paragraphs = (tree.children ?? []).filter((n) => n.type === 'paragraph');
    const ids = paragraphIdsFor(paragraphs.map((n) => toString(n)));
    paragraphs.forEach((node, i) => {
      node.data ??= {};
      node.data.hProperties = { ...node.data.hProperties, id: ids[i] };
    });
  };
}
