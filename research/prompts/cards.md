You are writing the **Card by card** version of a strategy guide for the Unmatched fighter **{name}** (site id `{id}`): the long, detailed tab on the fighter page. Write it to `research/private/guides/{id}.cards.md`, and the evidence to `research/private/guides/{id}.cards.evidence.md`. Do not edit any other file.

The fighter's **Medium** guide is already written and approved: `research/private/guides/{id}.medium.md`, with its evidence in `research/private/guides/{id}.medium.evidence.md`. Keep this version consistent with it: the same win conditions, and no contradictions. Reuse its references (same reference lines) where you make the same claims.

## Sources (read all of them in full before writing)

1. `research/packs/{id}.md`: the deck, every written guide, forum thread and article about {name}, shared articles that cover {name} among others (only their {name} parts matter), and transcripts of the strategy videos (automatic captions: names are misspelled, "faint" = Feint). The videos and the forum replies are where most of the real strategy is; use them heavily.
2. `input/heroes.json`, key `{id}`: the deck. Card names, values, copies and effects come from there, except where `research/CODEX-PROMPT.md` (section "Card data corrections") says otherwise; the printed card wins.

## What the owner wants

The old guides were rejected as shallow: they restated card text ("combo your cards") instead of strategy. The reader sees every card's printed text in a deck table on the same page, so **never restate card text**. For each card say **when** to play it or hold it, **how** to use it (attack or defense, what to boost it with or whether to use it as a boost, what to play before or after it), and **what punishes or wastes it**.

**Every win condition must say what kind of opponent or game situation makes it the right choice** ("very important" to the owner). Name opponent *types*, never a specific fighter: "tanky, heavy-hitting fighters", "fighters with several 1-health sidekicks", "decks with many Feints or cancels". No other Unmatched fighter may be named anywhere, not even as an example. If a source names a fighter, turn it into the type that source means.

There is no section explaining the fighter's special ability; advice on using it goes inside the card entries and win conditions.

## Rules

- Every claim carries a numbered citation [n] pointing to the entry's own References list, numbered in order of first use.
- Reference formats (academic style):
  - Deck, only if you cite a card fact: Restoration Games. *<set name>*, {name} deck. Card text as recorded in `input/heroes.json`. (With backticks around the file name.)
  - Video: `Channel. "Video title." *YouTube*. URL`
  - Written guide or article: `Author or site. "Title." *Site*, date if known. URL`
  - Each forum commenter is their own reference: `u/name. Comment on "Thread title" by u/op. *r/Unmatched*, Reddit, D Month YYYY. URL`, or `name. Reply in "Thread" by op. *BoardGameGeek*, date. URL`. Later commenters in the same thread: `u/name. Comment on "Thread title" (see [n]).`
- Nothing beyond the sources; don't widen one source's point into a general rule. Where sources disagree, say so and cite both sides; name a source in the sentence only there.
- Write like a strong player explaining the fighter to a friend: direct, second person, concrete. No filler ("is a strong option", "can be useful").
- **Card names in full, every time**, spelled exactly as in the deck (no short forms such as "Eyes" or "Big Mouth"): the site turns each full card name into a hover card.
- Name a source in the text only where sources disagree, and then by site or channel ("Gridbeast", "Baked Goods"), never by forum username: write "one player… another…".
- Put a space before each citation, and write several as `[1][3]`, never `[1, 3]`: `finish. [1][3]`.
- Only these Markdown features: `###` headings, paragraphs, flat `- ` lists, `1. ` lists under References, `**bold**`, `*italic*`, links, [n] citations.

## Format

About 1,000 to 1,200 words before References (fewer if the sources are thin: never pad). Every bullet is one or two sentences.

```
<!-- id: {id} -->
## {name}

**In short:** two sentences: what kind of fighter this is and how they want the game to go.

### Win conditions
- **Name of win condition:** when to choose it (opponent type or situation), and the cards that carry it. (One bullet per win condition, matching the Medium guide.)

### Cards: when and how to use them
**Exact card name**
- **When:** the situations to play it, and when to hold it instead.
- **How:** attack or defense, what to boost it with or whether to boost with it, what to play before or after it.
- **Watch out:** what punishes it or wastes it.

(One block per card, or **Card A** and **Card B** together for near-identical cards. Cover every card in the deck, sidekick cards included, most important first; give the important cards more words. The bold line holds only the exact card name(s), nothing else.)

### How they lose
- **Threat.** What it does to them. **Answer:** what to do, with cards. (2 or 3 bullets)

### References
1. …

### Not cited
- links you read but didn't cite, as `- [Title](url): Site · kind (read; why not used)`, and videos you didn't use

---
```

## Then edit your own work

Reread as an editor: cut any sentence that only restates a card, check every claim against its source (fix or cut it if the source doesn't say it), check that no other fighter is named, check every card name against the deck, and smooth the wording. In the evidence file, list each cited bullet with a short supporting quote (up to 25 words) per source. Print the word count.
