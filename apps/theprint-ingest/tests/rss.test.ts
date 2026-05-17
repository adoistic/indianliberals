import { describe, it, expect } from 'vitest';
import { parseRssFeed, slugFromUrl } from '../src/rss';

const SAMPLE_FEED = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:content="http://purl.org/rss/1.0/modules/content/"
  xmlns:wfw="http://wellformedweb.org/CommentAPI/"
  xmlns:dc="http://purl.org/dc/elements/1.1/"
  xmlns:atom="http://www.w3.org/2005/Atom"
  xmlns:sy="http://purl.org/rss/1.0/modules/syndication/"
  xmlns:slash="http://purl.org/rss/1.0/modules/slash/">
<channel>
  <title>Indian Liberals Matter</title>
  <link>https://theprint.in/category/opinion/indian-liberals-matter/</link>
  <item>
    <title><![CDATA[Socialism vs free enterprise: AD Shroff's diagnosis]]></title>
    <link>https://theprint.in/opinion/indian-liberals-matter/ad-shroff-socialism-free-enterprise/2794663/</link>
    <pubDate>Sat, 29 Nov 2025 11:23:28 +0000</pubDate>
    <dc:creator><![CDATA[AD Shroff]]></dc:creator>
    <guid isPermaLink="false">https://theprint.in/?p=2794663</guid>
    <description><![CDATA[Brief excerpt.]]></description>
    <content:encoded><![CDATA[<p>Full article body with <strong>bold</strong> and <a href="https://example.com">link</a>.</p>]]></content:encoded>
    <category><![CDATA[Socialism]]></category>
    <category><![CDATA[Free Enterprise]]></category>
  </item>
  <item>
    <title>Second post</title>
    <link>https://theprint.in/opinion/indian-liberals-matter/second-post/2794700/</link>
    <pubDate>Sun, 30 Nov 2025 09:00:00 +0000</pubDate>
    <dc:creator>Another Author</dc:creator>
    <guid>https://theprint.in/?p=2794700</guid>
    <description>excerpt</description>
    <content:encoded>body</content:encoded>
  </item>
</channel>
</rss>`;

describe('parseRssFeed', () => {
  it('extracts both items with CDATA-wrapped and plain fields', () => {
    const items = parseRssFeed(SAMPLE_FEED);
    expect(items).toHaveLength(2);

    const first = items[0];
    expect(first.title).toBe("Socialism vs free enterprise: AD Shroff's diagnosis");
    expect(first.link).toBe('https://theprint.in/opinion/indian-liberals-matter/ad-shroff-socialism-free-enterprise/2794663/');
    expect(first.author).toBe('AD Shroff');
    expect(first.categories).toEqual(['Socialism', 'Free Enterprise']);
    expect(first.contentHtml).toContain('<strong>bold</strong>');
    expect(first.pubDate.toISOString()).toBe('2025-11-29T11:23:28.000Z');

    const second = items[1];
    expect(second.title).toBe('Second post');
    expect(second.author).toBe('Another Author');
    expect(second.categories).toEqual([]);
  });

  it('returns empty array for a feed with no items', () => {
    expect(parseRssFeed('<rss><channel></channel></rss>')).toEqual([]);
  });

  it('decodes numeric and named HTML entities in titles', () => {
    const xml = '<rss><channel><item><title>Caf&#233; &amp; tea</title><link>https://x.test/y/</link></item></channel></rss>';
    const items = parseRssFeed(xml);
    expect(items[0].title).toBe('Café & tea');
  });
});

describe('slugFromUrl', () => {
  it('extracts the slug segment after indian-liberals-matter', () => {
    expect(
      slugFromUrl(
        'https://theprint.in/opinion/indian-liberals-matter/ad-shroff-socialism/2794663/',
        'fallback',
      ),
    ).toBe('ad-shroff-socialism');
  });

  it('falls back to a last-non-numeric segment for non-matching URLs', () => {
    expect(
      slugFromUrl('https://theprint.in/opinion/some-other-category/the-slug/12345/', 'fb'),
    ).toBe('the-slug');
  });

  it('uses title-derived slug when URL parse fails', () => {
    expect(slugFromUrl('not a url', 'My Title!!')).toBe('my-title');
  });
});
