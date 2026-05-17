import { describe, it, expect } from 'vitest';
import { rssItemToMarkdown } from '../src/markdown';
import type { RssItem } from '../src/rss';

const baseItem: RssItem = {
  title: 'Socialism vs free enterprise',
  link: 'https://theprint.in/opinion/indian-liberals-matter/ad-shroff-socialism/2794663/',
  guid: 'https://theprint.in/?p=2794663',
  pubDate: new Date('2025-11-29T11:23:28.000Z'),
  author: 'AD Shroff',
  description: 'excerpt',
  contentHtml: '<p>First paragraph with <strong>bold</strong>.</p><p>Second paragraph.</p>',
  categories: ['Socialism', 'Free Enterprise'],
};

describe('rssItemToMarkdown', () => {
  it('emits frontmatter matching the existing theprint-mirror format', () => {
    const md = rssItemToMarkdown(baseItem, { mirroredOnIso: '2026-05-18', slug: 'ad-shroff-socialism' });
    expect(md).toContain('---\n');
    expect(md).toContain('id: "ad-shroff-socialism"');
    expect(md).toContain('title: "Socialism vs free enterprise"');
    expect(md).toContain('pubDate: 2025-11-29T11:23:28.000Z');
    expect(md).toContain('author_name: "AD Shroff"');
    expect(md).toContain('theprint_url: "https://theprint.in/opinion/indian-liberals-matter/ad-shroff-socialism/2794663/"');
    expect(md).toContain('themes: ["socialism", "free-enterprise"]');
    expect(md).toContain('noindex: true');
    expect(md).toContain('needs_review: true');
    expect(md).toContain('draft: false');
  });

  it('emits the body with attribution + heading + markdown paragraphs', () => {
    const md = rssItemToMarkdown(baseItem, { mirroredOnIso: '2026-05-18', slug: 'ad-shroff-socialism' });
    expect(md).toContain('# Socialism vs free enterprise');
    expect(md).toContain('_Mirrored from [ThePrint](https://theprint.in/');
    expect(md).toContain('Originally published 2025-11-29');
    // Bold inline conversion
    expect(md).toContain('First paragraph with **bold**.');
    // Paragraph separation
    expect(md).toContain('Second paragraph.');
  });

  it('emits empty themes array correctly (no malformed YAML)', () => {
    const item = { ...baseItem, categories: [] };
    const md = rssItemToMarkdown(item, { mirroredOnIso: '2026-05-18', slug: 'x' });
    // Must have space after the colon — js-yaml rejects "themes:[]"
    expect(md).toContain('themes: []');
  });

  it('escapes double quotes in titles', () => {
    const item = { ...baseItem, title: 'A "quoted" headline' };
    const md = rssItemToMarkdown(item, { mirroredOnIso: '2026-05-18', slug: 'x' });
    expect(md).toContain('title: "A \\"quoted\\" headline"');
  });

  it('converts blockquotes to >  markdown', () => {
    const item = { ...baseItem, contentHtml: '<blockquote>Quoted text here.</blockquote>' };
    const md = rssItemToMarkdown(item, { mirroredOnIso: '2026-05-18', slug: 'x' });
    expect(md).toContain('> Quoted text here.');
  });

  it('handles HTML entities in body', () => {
    const item = { ...baseItem, contentHtml: '<p>Caf&eacute; &amp; tea &mdash; Mr. Shroff&rsquo;s view.</p>' };
    const md = rssItemToMarkdown(item, { mirroredOnIso: '2026-05-18', slug: 'x' });
    // &eacute; isn't in our minimal table; that's fine — but core entities should resolve
    expect(md).toContain('& tea — Mr. Shroff’s view.');
  });
});
