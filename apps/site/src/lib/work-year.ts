// The year a work belongs to, for histograms and spans.
//
// publication.year is the cover date for most works, but for the digitised
// periodical runs it often records the scan year, so an issue's year is read
// from its slug, which encodes the cover date. The slug fallback takes the
// LAST plausible year in the slug, never the first: the Swatantra papers
// carry a numeric id prefix ("1811-the-kerala-satyagraha-...-1959") that the
// old first-match rule read as the year 1811, and the homepage histogram
// grew a phantom 1810s.

type YearWork = {
  id: string;
  data: { work_type?: string; publication?: { year?: number | null } };
};

const THIS_YEAR = new Date().getFullYear();

function plausible(y: number | null | undefined): y is number {
  return typeof y === 'number' && y >= 1800 && y <= THIS_YEAR;
}

function slugYear(id: string): number | null {
  // The Swatantra papers' slugs open with a running number ("1839-swatantra-
  // party-rajasthan-constituency"), which is an id, not a date.
  const all = id.replace(/^\d+-/, '').match(/(?:18|19|20)\d{2}/g);
  if (!all) return null;
  for (let i = all.length - 1; i >= 0; i--) {
    const y = Number(all[i]);
    if (plausible(y)) return y;
  }
  return null;
}

export function workYear(w: YearWork): number | null {
  if (w.data.work_type === 'periodical_issue') {
    return slugYear(w.id) ?? (plausible(w.data.publication?.year) ? w.data.publication!.year! : null);
  }
  const y = w.data.publication?.year;
  return plausible(y) ? y : slugYear(w.id);
}
