# Work completion email

**To:** kumar@ccs.in, arjun@ccs.in, aayushi@ccs.in, harsh.singh@ccs.in
**From:** adnan@thothica.com
**Subject:** Indian Liberals is done, and you can all log in now

---

Kumar, Arjun, Aayushi, Harsh,

The rebuild is finished. I've already set all four of you up as admins, so you
don't need anything from me to start poking at it. Go to
cms.indianliberals.in, sign in with your CCS Google address, and you're in. If
it refuses you, tell me and I'll sort it out the same day.

Start with the CMS, since that's the part you'll actually live with. It doesn't
ask you what kind of database record you want to create. It asks what you came
to do: put a document online, fix something that's wrong, add a person, get
through a folder of scans. Every save becomes a commit in the archive's history
under your name, so nothing is anonymous and nothing is unrecoverable.

Two things in there worth knowing about before you try them. Anything you start
can be put down and picked up later, on a shelf that readers never see, with a
note of what it still needs. And you can drop a whole folder of scans in at
once: each file goes onto the archive server first so nothing is ever lost if
the reading fails, then they're read one at a time and wait on that same shelf
until somebody has checked them. Publishing the lot is one action.

One expectation to set with whoever else ends up using it: the save is instant,
but the site takes about half an hour to show it. The whole archive rebuilds
and Cloudflare runs those builds one after another. Nothing is lost in the wait
and nobody has to sit watching the screen. It's also why a batch publishes in
one go rather than fifty; fifty separate saves would tie the thing up until the
next day.

The archive itself: 1,575 primary works, 725 people, 195 excerpts, 79 ThePrint
pieces, 59 opinion pieces, 52 organisations, 10 series. 1,457 PDFs, 3.5 GB,
none of them empty or truncated. Every one of the 993 files you sent us is
accounted for. Sixty-five of them arrived twice and collapse to a single record
each, which is deduplication doing its job rather than anything going missing.

The piece I'd most like you to look at is indianliberals.in/eval. We quoted a
200-question evaluation; it ships with 255. Nothing in it is judged by a model.
The grader is arithmetic, the questions are public, and anyone can re-run it
and get the same number.

The headline is 70.8%, which I'd call decent rather than good. The number I
actually care about is the other one: across 255 questions, zero answers quoted
text the archive doesn't publish. The whole design rests on one line, that an
agent may quote the clean content down to the paragraph and must summarise and
link the scanned PDFs instead of pretending to have read them. That line held.
Where it does worse is citation discipline. It finds the right obscure fact and
then sometimes cites the paragraph without having actually fetched it. That's a
real weakness and it's written up rather than smoothed over, at
indianliberals.in/eval/paper.

A few things we found and fixed that weren't in the brief. The extraction
pipeline had a fault that attached the wrong headings to the wrong articles
across the periodical corpus; it affected 7% of sections and is now at 0.1%,
repaired without altering a line of the underlying text. A sweep of all 1,799
prose documents turned up six periodicals carrying another issue's content. One
budget PDF had uploaded as a 36-page truncation of a 43-page document, and the
full file now serves at the same address. We also built a transcription
pipeline for video, which is where the 18 lectures came from.

One thing I want to flag rather than bury. The API and the agent tools
currently list English records only. The 44 Marathi, Gujarati and Hindi works
are live and readable on the site and search finds them, but an agent asking
for a catalogue won't see them listed. Taking that filter out is easy. Deciding
whether an agent should treat a Marathi scan under the same citation rules as
an English one is a judgement I'd rather make with you than for you. Say the
word and it's a short piece of work.

Layout reconstruction of the scanned PDFs, paragraph-level citation inside the
primary works, and the wiki layer on top of them are all still where the
proposal left them, waiting on vision models good enough that the work won't
need doing twice. When that changes I'll tell you, and it'll be a conversation
rather than an invoice arriving unannounced.

Three months of support starts today. Anything that breaks, anything that reads
wrongly, anything one of your editors gets stuck on, send it straight to me.

Thanks for a genuinely good project. I've enjoyed this one.

Adnan

Adnan Abbasi
Thothica
adnan@thothica.com

---

## Links to include

- The site: https://indianliberals.in
- The CMS: https://cms.indianliberals.in
- The eval: https://indianliberals.in/eval
- The method: https://indianliberals.in/eval/paper
- The MCP server: https://mcp.indianliberals.in

## Attach or link if you want the detail

- `docs/2026-07-28-final-report.md` — everything built, against everything promised
- `docs/FINALISATION-2026-07-26.md` — the corpus reconciliation audit
