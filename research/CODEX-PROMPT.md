# Prompt for Codex: write the fighter strategy entries

Before you start, put the full source text at `research/private/unmatched-fighter-sources.md`. Git ignores that folder; the file is other people's writing and must never be committed. Then give Codex the prompt below.

---

You are writing strategy guides for every Unmatched fighter on this site. Read `research/HANDOFF.md` first, especially sections 2 (format) and 3 (writing rules).

**The model entry is Daredevil** in `input/fighter_strategies.md` and `input/fighter_strategies_short.md`. Its facts and citations have been checked against the sources. Match its structure, citation style and length. The one thing to improve, there and everywhere, is the wording: it should read smoothly and naturally, like a well-edited strategy guide, not like a list of notes.

For each fighter in `input/fighters.json`, in that order:

1. Read that fighter's section of `research/private/unmatched-fighter-sources.md`, plus every shared source (S1, S2, …) it points to.
2. Read the fighter's deck in `input/heroes.json`. Card names, values, copies and effects come from there, cited as reference [1].
3. Rewrite the fighter's entry in both files.

**Rules. Breaking any of these makes the entry wrong, however well it reads:**
- **Every claim carries a numbered citation** [n] that points to the entry's own References list, academic style, numbered in order of first use. Cite each forum commenter as a separate reference (author, "Reply to [n]" or "Comment on <thread title>", site, date). Card facts cite the deck [1].
- **Nothing beyond the sources.** Don't add advice no source gives, and don't widen one source's point into a general rule. If sources disagree, say so and cite both sides.
- **No matchup tips at all.** Never name a specific opposing fighter. Describe the kind of opponent or the mechanic instead, such as "ranged fighters with sidekicks" or "heavy Feints".
- **Length:** about 500 words per medium entry and about 150 per short entry, not counting References. Let the citation numbers carry attribution; name a source in the sentence only where sources disagree. Don't repeat a point across Plans, Key cards and Tips.
- Keep the `<!-- id: ... -->` line, the headings and the `---` separators exactly as they are. Links you read but didn't cite, and videos, go under "Not cited" in the medium file.
- Polishing the wording must never change a claim or drop a citation.

Do Daredevil's wording first and show me the result before going on. After that, work in batches of about ten fighters, committing after each batch.
