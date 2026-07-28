/**
 * The structural check every entry passes before it is committed.
 *
 * Deliberately cheap: the real schema lives in the site's own build, and this
 * is not trying to reproduce it. What it catches is the class of mistake that
 * takes the whole archive offline, a frontmatter block that does not parse,
 * because the site is statically built and a file that breaks the build breaks
 * every page, not just its own.
 *
 * Shared by the single save and the batch publish so the two cannot come to
 * disagree about what a valid entry looks like.
 */
export function frontmatterProblems(content: string): string[] {
  const problems: string[] = [];

  if (!content.startsWith('---\n')) {
    problems.push('The file must open with a frontmatter block, three dashes on their own line.');
    return problems;
  }

  const end = content.indexOf('\n---', 4);
  if (end === -1) {
    problems.push('The frontmatter block is never closed with three dashes.');
    return problems;
  }

  const block = content.slice(4, end);
  if (!block.trim()) problems.push('The frontmatter block is empty.');

  block.split('\n').forEach((line, index) => {
    if (!line.trim() || line.startsWith('#')) return;
    // Tabs are the classic invisible YAML break, and the error a build gives
    // for one is not obviously about tabs.
    if (line.includes('\t')) {
      problems.push(`Line ${index + 1} of the frontmatter has a tab. YAML needs spaces.`);
    }
  });

  if (!/^id:\s*\S/m.test(block)) {
    problems.push('The frontmatter has no id, which every entry needs.');
  }

  return problems;
}
