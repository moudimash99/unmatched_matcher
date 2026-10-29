# Strategy guides v2: handoff

Everything agreed with the owner (October 2026) for rewriting the fighter strategy guides, so the work can continue in any session. Tracked in GitHub issue #50. The earlier research and wording passes are described in `HANDOFF.md`; this file supersedes its format section.

## Why

The owner judged the current guides "very basic": they restate card text ("little red riding hood is combo your cards. WOW no shit sherlock"). The reader sees every card's printed text in the deck table on the same page, so a guide must say **when** to play a card, **how**, and **what punishes it**, never what it says.

The real strategy is in the video transcripts and forum replies, which the first pass barely used. `research/packs/{id}.md` (gitignored: other people's writing) holds, per fighter: the deck, every written guide, forum thread and shared article, and the transcripts of the strategy videos (71 of 74 fighters have at least one).

## The three versions

On the fighter page, three tabs: **Short · Medium · Card by card**, with **Medium open by default**.

| Version | Length | Made from |
|---|---|---|
| Medium (default) | ~550 words, plus an optional Game arc of ~250 | the fighter's pack |
| Card by card | ~1,000–1,200 words | the pack plus the finished Medium |
| Short | ~150 words | the finished Medium only |

### Medium skeleton (approved, owner liked Codex's output as is)

```
**In short:** two sentences: what kind of fighter, how they want the game to go.

### How they win
**Win condition name**
- **Choose this when:** opponent type or game situation that calls for it. ALWAYS first; the owner calls this "very important".
- **On your turn:** what to play, in order (setup, then payoff).
- **On their turn:** what to hold and play when they attack.
- **Positioning:** hero and sidekicks.
- other labels as the plan needs (**Healing:**, **Protecting the sidekick:**, **Finishing:** …); leave out empty ones
- **Sources disagree on X:** only where they do, both sides cited.
(2 or 3 win conditions)

### How they lose
- **Threat.** What it does. **Answer:** what to do, with cards. (2 or 3 bullets)

### Game arc            (optional, ~250 words, not counted in the 550; only if the sources support it)
- **Opening:** … **Midgame:** … **Closing it out:** …

### References
### Not cited
```

A paragraph version was rejected ("harder to read, no structure"): every bullet is one or two sentences.

### Card by card skeleton (the Little Red sample)

```
**In short:** two sentences.
### Win conditions   – one bullet each, with its "choose this when"
### Cards: when and how to use them
**Card name**
- **When:** … - **How:** … - **Watch out:** …
(every card, most important first)
### How they lose
### References
### Not cited
```

### Short skeleton

```
**In short:** one sentence.
### How they win    – 2 bullets, each naming its key card or two
### How they lose   – 2 bullets: threat + answer
### References
```

## Rules (all versions)

- **Never name another fighter**, not even as an example. Name types instead: "tanky, heavy-hitting fighters", "fighters with several 1-health sidekicks", "decks with many Feints". The owner: "absolutely not for naming fighters, yes for naming fighter types".
- **No section explaining the fighter's special ability**: it would only repeat the card. Advice on using it goes inside the win conditions.
- **Every claim is sourced**, with numbered [n] citations to the entry's own References, academic style (formats in `HANDOFF.md` section 0). Nothing beyond the sources; where sources disagree, cite both sides.
- **Card names in full**, exactly as in `input/heroes.json` (corrections in `CODEX-PROMPT.md`), every time, no short forms ("Eyes", "Big Mouth"): the site turns full card names into hover cards automatically.
- Name a source in the text only where sources disagree, and then by site or channel, not by forum username ("one player… another…").
- A space before each citation: `finish. [1]`.
- Card data corrections from the printed cards still apply (list in `CODEX-PROMPT.md`).

## Card hover (site)

The site finds each of the fighter's full card names in the guide text when rendering and turns it into a hover/tap card (type, value, boost, copies, effect) from `input/heroes.json`. **No markup in the guide files**: Codex writes plain text. A test fails if a bolded or quoted name isn't a card in the fighter's deck.

## Workflow

Codex writes, I (Claude) check. One fighter per Codex run (each pack is 20–50k words); Medusa took ~2.5 minutes and ~74k tokens, Bruce Lee ~2 minutes and ~52k. A whole pass of 74 fighters is ~3 hours and ~4–5M Codex tokens, so run in **batches of 10** and commit after each, in case the ChatGPT usage limit hits.

1. `python -X utf8 research/scripts/codex_guides.py medium <ids…>` (or `--next 10`): builds the prompt from `research/prompts/medium.md` for each fighter and runs `codex exec -s workspace-write -C .`. Output: `research/private/guides/{id}.medium.md` plus `{id}.medium.evidence.md` (a supporting quote per cited bullet). Skips fighters that already have output.
2. `python -X utf8 research/scripts/check_guides.py medium` : citations defined and in order, renders cleanly, no other fighter named, word count. Then read each guide against its evidence file and the pack, fix wording or unsupported claims by hand.
3. `python -X utf8 research/scripts/assemble_guides.py medium` : joins the per-fighter files (fighters.json order) into `input/fighter_guides_medium.md`. Commit and push that, never the private folder.

## Order (agreed 2026-10-27)

1. **Medium pass** for all 74 fighters.
2. **Card by card** for the three examples (Little Red done; Medusa, Bruce Lee).
3. **Site**: three tabs (Medium default) and card hovers, shown to the owner on the three examples.
4. If the owner is happy: **Short pass**, then **Card by card pass** for everyone.

Until a fighter has a v2 guide, the page keeps showing its current one (`input/fighter_strategies*.md`).

## Samples (approved)

In `research/private/sample/` (gitignored): `little_red.long.md` (card by card), `little_red.medium.codex.md` (approved Medium; uses short card names, convert to full names), `little_red.short.md` (old short skeleton), `medusa.medium.md`, `bruce_lee.medium.md`, each with an evidence file.

## Status

- [x] Format agreed, samples approved
- [x] Medium pass (74 / 74; donatello has no evidence file: checked by hand against its pack)
- [x] Card by card for Medusa and Bruce Lee
- [x] Site: tabs + card hovers (on guides-v2, not deployed)
- [x] Short pass (74 / 74, written by Claude from each Medium guide via research/scripts/make_short.py; drafts in research/private/short-drafts/)
- [x] Card by card pass (74 / 74, done 29 Oct, 5:10 AM; 31 of them merged and deployed in PR #51, the other 43 on `guides-v2`)

## Notes from the first batch

- Codex sometimes writes a UTF-8 byte-order mark; the scripts read with `utf-8-sig`.
- It sometimes groups citations as `[1, 3]` or spaces them `[1] [3]`; normalise to `[1][3]` before assembling (the prompt now asks for this).
- It mostly keeps full card names, but check for short forms (e.g. "Gaze" for Gaze of Stone).
- Card hover: several card names are ordinary words ("Again", "Feint", "Exploit", "Disengage", "Feeding"), so link only this fighter's own cards and only on an exact, case-sensitive match.
- Low memory on this PC kills long background runs (Claude Code stops them). Close heavy apps first, or start Claude Code with `CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP=1`. A killed batch loses only the fighter in progress; rerun with `--next`.
- Running 3–4 Codex jobs side by side, each a foreground call of 3 fighters (`codex_guides.py medium id1 id2 id3`, timeout 10 min), does about one fighter a minute and isn't stopped by the low-memory guard.
- The ChatGPT usage limit hit after about 60 fighters (~3M tokens) on 28 October; it resets after a few hours (the log says when).
