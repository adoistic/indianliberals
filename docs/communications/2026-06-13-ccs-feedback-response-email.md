# Draft email — response to CCS feedback round (June 2026)

Status: draft for Adnan to review and send
To: Kumar Anand, Arjun (CCS)
Prepared: 2026-06-13

---

**Subject: Your feedback on indianliberals.pages.dev — all eight points addressed, site updated**

Dear Kumar and Arjun,

Thank you for the detailed review — it was exactly the kind of feedback we needed. We've worked through every point, and the updated site is live at https://indianliberals.pages.dev. Here's what we did, point by point.

**1. Periodicals section.** Fixed. Periodicals now have a dedicated, working section at /periodicals/ — the runs are grouped by series (Khoj, The Indian Libertarian, Liberal Times, Shetkari Sanghatak), each with a short history of the publication, cover thumbnails, and issue-level pages. It also has a prominent place in the main navigation and on the redesigned homepage.

**2.1 Authors page — retain only deceased liberal thinkers.** We took this advice, with one deliberate caveat I want to flag openly. The Thinkers page (/thinkers/) now shows exactly what you asked for: a small curated canon of deceased liberal thinkers, and nothing else. Mukesh Ambani, Joseph Stalin, and the like no longer appear there.

What we did *not* do is delete those entries from the archive — instead we moved them into a clearly separated full directory (/thinkers/directory/), where figures from outside the tradition sit under an explicit heading: "Referenced figures — not part of the liberal tradition." Their individual pages carry the same disclaimer.

My reasoning: the significance of an archive lies in preserving data, not curating it away. These people appear because liberal writers cited, debated, and criticised them — Stalin is in the corpus because Masani argued against him, Ambani because contemporary pieces discuss him. If we delete the entries, every one of those cross-references breaks, and a researcher tracing "who did the Indian liberals argue with?" loses the trail. The archive is more valuable as a complete historical record with honest labels than as a trimmed list. The presentation now makes the distinction impossible to miss — but I'd genuinely like to discuss this at our meeting and am open to adjusting further.

**2.1.1 Priority to names from the previous site; streamline to a curated list.** Done. The curated canon is seeded from the featured list on the previous version of indianliberals.in, with only a few additions. The "two sub-sections" issue is resolved: /thinkers/ is now a single curated page, and the comprehensive listing lives separately in the directory. We also added a search box on the Thinkers page that quietly covers the whole database — so a visitor searching for any name still finds the right page, clearly labelled, instead of a dead end.

**2.2 Consistent cartoon/illustrated portraits.** Done. The Thinkers page now uses a uniform illustrated duotone treatment for every portrait — no more mix of photographs and styles. Original photographs remain available on the individual profile pages.

**3. Organisation descriptions and logos.** Done. Every organisation now has a short description and a visual mark, both on the listing cards and the detail pages.

**4. "In Partnership with FNF" line.** Removed from the footer and everywhere else it appeared (about page and the machine-readable site descriptions).

**5. Duplicate opinion pieces.** Fixed. The first two pieces were WordPress double-imports; we merged each pair, keeping the more complete version, and audited the rest of the Opinion section for similar duplicates (four more were found and merged). Old URLs redirect to the right pages.

**6. More visuals across the site.** This round leaned into it: the homepage has been redesigned around the collection's own imagery — a slowly drifting mosaic of thinker portraits and periodical covers, visual doorway cards into each section, and a chronological portrait rail of the canon. The periodicals section shows cover art, the new Interviews section shows video stills, and organisation pages carry their marks. More suggestions welcome — there's room to extend this to theme pages next.

**7. Non-CCS works under CCS Publications.** Audited and fixed. The mislabelling came from our extraction pipeline, which had stamped the digitiser as the publisher. The CCS page now lists only the genuine CCS publications; the Khoj issues are correctly attributed to Pahel — Initiative for Open Society, Vadodara, and the other affected books have had the wrong publisher line removed.

**8. Site stats / highlights.** Done, as part of the homepage redesign: an "archive at a glance" band with the key numbers (primary works, periodical issues, interviews, thinkers profiled, excerpts & opinions, organisations) — each linking into its section — plus a small works-per-decade timeline showing the archive's spread from the 1850s to today. The numbers are computed from the live content at every build, so they'll never drift.

**One more thing we fixed while we were in there.** The interviews were all shelved under the "2020s" — the date they were uploaded, not when they were recorded. We've re-dated the whole collection from the evidence: Nani Palkhivala's Union Budget address is now correctly a 1992 recording, Sudha Shenoy's Mises Institute lectures sit in 2003–2006, the D.R. Pendse oral histories in 2016, and so on. The interviews also have a proper home now at /interviews/ — oral histories shelved by interviewee, historic lectures, talks, and the IL Explainers, each with transcripts and durations.

Please take the updated site for a spin — I'd be glad to walk through any of it at our Monday meeting, and the referenced-figures presentation in particular is something I'd like your read on.

Warm regards,
Adnan

---

## Notes for Adnan (not part of the email)

- The 2.1 paragraph is written to be candid but soft — "took this advice with a caveat… open to adjusting further." Tighten or loosen to taste.
- D.R. Pendse remains on the canon page via the legacy featured list but has no confirmed death year — if CCS pushes on strict deceased-only, that's the one name to resolve (canon checklist: docs/communications/2026-06-12-thinkers-canon-signoff.md).
- Live-site smoke checks for this round are in the session log; all 13 passed against the local build and the deploy was pushed 2026-06-13.
