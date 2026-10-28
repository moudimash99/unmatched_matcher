You are writing the **Medium** version (the default one readers see) of a strategy guide for the Unmatched fighter **{name}** (site id `{id}`). Write it to `research/private/guides/{id}.medium.md`, and the evidence to `research/private/guides/{id}.medium.evidence.md`. Do not edit any other file.

## Sources (read all of them in full before writing)

1. `research/packs/{id}.md`: the deck, every written guide, forum thread and article about {name}, shared articles that cover {name} among others (only their {name} parts matter), and transcripts of the strategy videos (automatic captions: names are misspelled, "faint" = Feint). The videos and the forum replies are where most of the real strategy is; use them heavily.
2. `input/heroes.json`, key `{id}`: the deck. Card names, values, copies and effects come from there, except where `research/CODEX-PROMPT.md` (section "Card data corrections") says otherwise; the printed card wins.

## What the owner wants

The old guides were rejected as shallow: they restated card text ("combo your cards") instead of strategy. The reader sees every card's text in a deck table on the same page, so never restate card text. Don't go through the cards one by one: cards appear inside the discussion of how {name} wins and loses, in the order you'd play them.

**Every win condition must say what kind of opponent or game situation makes it the right choice.** The owner called this "very important". Name opponent *types*, never a specific fighter: "tanky, heavy-hitting fighters", "fighters with several 1-health sidekicks", "decks with many Feints or cancels", "fast melee fighters who close distance". No other Unmatched fighter may be named anywhere, not even as an example. If a source names a fighter, turn it into the type that source means. Where the sources talk about playing *against* {name}, use that for How they lose, written as threats and answers.

There is no section explaining the fighter's special ability; advice on using it goes inside the win conditions.

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

## Format: structure is the point

An earlier Medium draft written as paragraphs was rejected as hard to read for lack of structure; the owner approved the structured format below. Every win condition is a short labelled bullet list, and each bullet is one or two sentences. About 500 to 550 words for In short + How they win + How they lose, not counting citations.

```
<!-- id: {id} -->
## {name}

**In short:** two sentences: what kind of fighter this is and how they want the game to go.

### How they win

**Name of win condition 1**
- **Choose this when:** the opponent type or game situation that calls for it. (Always the first bullet.)
- **On your turn:** what to play, in order (setup, then payoff).
- **On their turn:** what to hold and play when they attack.
- **Positioning:** where the hero and sidekicks should stand.
- (Other labels as the plan needs, e.g. **Healing:**, **Protecting the sidekick:**, **Using the special ability:**. Leave out labels that have nothing to say.)
- **Sources disagree on X:** only where they do; both sides, cited.

**Name of win condition 2**
- … (2 or 3 win conditions in all)

### How they lose

- **Threat.** What it does to them. **Answer:** what to do, with cards. (2 or 3 bullets)

### Game arc

Optional, about 250 words, not counted above, only if the sources support it: bullets **Opening:**, **Midgame:**, **Closing it out:**. If the sources don't give enough, leave the whole section out.

### References
1. …

### Not cited
- links you read but didn't cite, as `- [Title](url): Site · kind (read; why not used)`, and videos you didn't use

---
```

## Then edit your own work

Reread as an editor: cut any sentence that only restates a card, check every claim against its source (fix or cut it if the source doesn't say it), check that no other fighter is named, check card names against the deck, and smooth the wording. In the evidence file, list each cited bullet with a short supporting quote (up to 25 words) per source. Print the word count.
