# Prompt for Codex: write the fighter strategy entries

Before you start, put the full source text at `research/private/unmatched-fighter-sources.md` and run `python -X utf8 -I research/scripts/packs.py` (on Windows the `-X utf8` is needed). Git ignores that folder; the file is other people's writing and must never be committed. Then give Codex the prompt below.

---

You are writing strategy guides for every Unmatched fighter on this site. Read `research/HANDOFF.md` first, especially sections 2 (format) and 3 (writing rules).

**The model entry is Daredevil** in `input/fighter_strategies.md` and `input/fighter_strategies_short.md`. Its facts and citations have been checked against the sources. Match its structure, citation style and length. The one thing to improve, there and everywhere, is the wording: it should read smoothly and naturally, like a well-edited strategy guide, not like a list of notes.

For each fighter in `input/fighters.json`, in that order:

1. Read the fighter's pack, `research/private/packs/{id}.md`: their deck, their own sources and the shared sources (S1, S2, …) that cover them. The full text is in `research/private/unmatched-fighter-sources.md` if you need more.
2. Read the fighter's deck in `input/heroes.json`. Card names, values, copies and effects come from there, cited as reference [1], except where "Card data corrections" below says otherwise.
3. Rewrite the fighter's entry in both files.

**Rules. Breaking any of these makes the entry wrong, however well it reads:**
- **Every claim carries a numbered citation** [n] that points to the entry's own References list, academic style, numbered in order of first use. Cite each forum commenter as a separate reference (author, "Reply to [n]" or "Comment on <thread title>", site, date). Card facts cite the deck [1].
- **Nothing beyond the sources.** Don't add advice no source gives, and don't widen one source's point into a general rule. If sources disagree, say so and cite both sides.
- **No matchup tips at all.** Never name a specific opposing fighter. Describe the kind of opponent or the mechanic instead, such as "ranged fighters with sidekicks" or "heavy Feints".
- **Length:** about 500 words per medium entry and about 150 per short entry, not counting References. Let the citation numbers carry attribution; name a source in the sentence only where sources disagree. Don't repeat a point across Plans, Key cards and Tips.
- Keep the `<!-- id: ... -->` line, the headings and the `---` separators exactly as they are. Links you read but didn't cite, and videos, go under "Not cited" in the medium file.
- Polishing the wording must never change a claim or drop a citation.

**Card data corrections.** These were checked against scans of the printed cards; where `heroes.json` disagrees, the card wins (still cite [1]):
- **George Washington:** the ruse symbol is missing from the data. These effects happen only if a ruse token was used: Agent 711 (deal 7 damage after a won combat), Circumvent (ignore the value of the opponent's card), Sabotage (opponent discards 2 random cards after a won combat) and the "Washington recovers 3 health" part of Allies Everywhere (the free attack action is unconditional). The current entries state these as unconditional; fix that.
- **Little Red:** What Big Eyes You Have has value 3 (data: 2). Stones in the Belly has value 2 (data: none).
- **Luke Cage:** Skin Like Titanium has value 0.
- **Michelangelo:** Nunchaku reads "Add +1 to the value of Michelangelo's attacks this turn. Gain 1 action." (the data has Bruce Lee's text). It may now be described.
- **Pandora:** Aphrodite's Beauty can be played by any of her fighters (data: Pandora only).
- **Houdini:** boost effects are missing from the data. Flourish: "Draw 1 card." Set the Stage: "Look at an opponent's hand and choose a card for them to discard."
- **Donatello:** Short Circuit reads "Cancel all AFTER COMBAT effects on your opponent's card."
- **Spelling:** Alice (not Allice), Porter (not The Potter), Dijkstra (not Djkstra), Shapeshifter (not Shapershifter), "Eat, Sleep, and Breathe Ninjutsu" (not breath). Loki's and Pandora's card titles go in normal capitals, not all caps.

Do Daredevil's wording first and show me the result before going on. After that, work in batches of about ten fighters, committing after each batch.
