# Work completion email — draft

**To:** Kumar Anand, Arjun
**Cc:** (FNF, if the partnership contact should see it)
**Subject:** Indian Liberals — the rebuild is finished

---

Kumar, Arjun,

The Indian Liberals rebuild is done. Everything in the proposal is live, and
this note is the account of it.

**The archive.** 1,575 primary works, 725 thinkers, 195 excerpts, 79 ThePrint
pieces, 59 opinion pieces, 52 organisations, 12 contributors, 10 series. 1,457
PDFs serving from Cloudflare, 3.51 GB, none of them empty or truncated. Every
one of the 993 PDFs you sent us is accounted for — 65 of them arrived twice and
collapse to one record each, which is deduplication working rather than
anything lost. No duplicate ids, no drafts sitting unpublished, nothing filed
in two places.

**The site.** indianliberals.in, on Astro and Cloudflare. Search runs across
English, Hindi, Gujarati and Marathi with the right analyzer for each. Every
URL the old WordPress site ever had now redirects rather than 404s.

**The agent layer.** mcp.indianliberals.in exposes ten tools — two more than we
quoted, so the corpus answers to ChatGPT's deep research as well as Claude and
Cursor. Every page has a markdown sibling declaring which tier it belongs to,
and there are `/llms.txt`, `/llms-full.txt`, `/AGENTS.md` and `/SKILL.md` for
agents arriving without a client.

**The eval, at indianliberals.in/eval.** This was the last thing outstanding
and it is the piece I would most like you to look at. We quoted 200 questions;
it ships 255. Nothing is judged by a model — the grader is arithmetic, the
question pool is public, and anyone can re-run it and get the same number.

The headline is 70.8%. The number that matters more is the other one: across
255 questions, **zero answers quoted text the archive does not publish.** The
whole design rests on one line — that an agent may quote the clean content down
to the paragraph, and must summarise and link the scanned PDFs rather than
pretend to read them. That line held. Where the agent does worse is citation
discipline: it finds the right obscure fact and then sometimes cites the
paragraph without having actually fetched it. That is a real weakness and it is
written up rather than smoothed over. The method is at
indianliberals.in/eval/paper.

**The CMS, at cms.indianliberals.in.** We proposed an off-the-shelf editor and
built you a purpose-built one instead, at no change to the price. The reason is
that the off-the-shelf option would have shown an archivist a database schema.
This one asks what they want to do — put a document online, fix something that
is wrong, add a person — and works backwards from there. Sign in with Google or
a magic link. Four roles, with what each can and cannot do written out on the
page rather than in a manual. Every save becomes a commit in the archive's
history under the name of the person who made it, so nothing is anonymous and
nothing is unrecoverable.

Adnan is set up as super admin. Adding the rest of your team is two minutes in
the People screen — no code, no tickets to us.

One expectation worth setting with your editors: a save is instant, but the
site takes about half an hour to show it, because the whole archive rebuilds
and Cloudflare runs those builds one at a time. Nothing is lost in the wait and
nobody needs to sit watching the screen. The CMS says so on the page.

**Things we found and fixed along the way that were not in the brief.** The
extraction pipeline had a misjoin that put the wrong headings against the wrong
articles across the periodical corpus; it affected 7% of sections and is now at
0.1%, repaired without altering a single line of the underlying prose. A sweep
of all 1,799 prose documents found six periodicals carrying another issue's
content. One budget PDF had uploaded as a 36-page truncation of a 43-page
document — the full file now serves at the same address. We also built a video
transcription pipeline, which is where the 18 lectures came from, and branded
social cards for every page so links render properly when they are shared.

**One thing I want to flag rather than bury.** The API and the agent tools
currently list English records only. The 44 Marathi, Gujarati and Hindi primary
works are live and readable on the site, and search finds them — but an agent
asking for a catalogue will not see them listed. Removing that filter is
straightforward. Deciding whether an agent should be told to treat a Marathi
scan the same way it treats an English one is a judgement I would rather make
with you than for you. Say the word and it is a short piece of work.

Layout reconstruction of the scanned PDFs, paragraph-level citation inside the
primary works, and the wiki layer on top of them remain where the proposal put
them — waiting on vision models good enough that the work will not need doing
twice. When that changes I will tell you, and it will be a separate
conversation rather than an invoice arriving unannounced.

Three months of support run from today. Anything that breaks, anything that
reads wrongly, anything an editor gets stuck on — send it to me directly.

It has been a genuine pleasure. This is an archive worth the trouble.

Adnan Abbasi
Founder, Thothica
adnan@thothica.com

---

## Attachments / links to include

- The site — https://indianliberals.in
- The eval — https://indianliberals.in/eval
- The paper — https://indianliberals.in/eval/paper
- The CMS — https://cms.indianliberals.in
- The MCP server — https://mcp.indianliberals.in
- `docs/handoffs/2026-07-28-scope-vs-delivery.md` — the full scope-versus-delivery breakdown
- `docs/FINALISATION-2026-07-26.md` — the corpus reconciliation audit
