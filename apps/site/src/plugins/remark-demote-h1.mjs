// Demote body-level <h1> to <h2>.
//
// The emit-astro-md step writes the work's title as a leading `# Title`
// heading into 1,100+ primary-work bodies, which rendered a second <h1>
// under the layout's own <h1> (bad heading semantics; SEO auditors flag
// duplicate H1s). The page-level H1 belongs to the layout; body headings
// start at H2. Other collections' bodies carry no H1s, so this is a no-op
// for them. The raw .md siblings served to agents are generated from the
// unrendered body and are unaffected.
import { visit } from 'unist-util-visit';

export function remarkDemoteH1() {
  return (tree) => {
    visit(tree, 'heading', (node) => {
      if (node.depth === 1) node.depth = 2;
    });
  };
}
