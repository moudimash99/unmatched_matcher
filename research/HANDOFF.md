# Fighter strategy research: handoff notes

Everything the cloud session that wrote the fighter strategy files knew, so the work can continue anywhere. All of it is on the branch `claude/jolly-mayer-q2s9pw` of `moudimash99/unmatched_matcher`.

## 0. Current status (October 2026)

**Research pass and wording pass complete on branch `claude/strategy-guide-format-n0n1vb`.** Every fighter was rewritten from their sources, with every claim cited (see sections 2 and 3), then reworded by Codex in batches of ten (`research/CODEX-PROMPT.md`). Each batch was checked against the previous commit: same sources cited per entry, reference lines unchanged except renumbering, no numbers lost. The card corrections in the Codex prompt (Washington's ruse effects and others) are now in the entries.

**On the site:** `strategies.py` renders both files onto each fighter page (`/fighter/<id>`): the short guide, then the full one behind "Read the full guide". Paragraphs after a References list (notes on the deck data) and "Not cited" links marked "(read; …)" are not shown.

**Done (74, all):** daredevil, king_arthur, alice, medusa, sinbad, robin_hood, bigfoot, bruce_lee, robert_muldoon, raptors, dracula, invisible_man, jekyll_hyde, sherlock_holmes, buffy, spike, willow, angel, little_red, beowulf, deadpool, achilles, bloody_mary, sun_wukong, yennenga, luke_cage, ghost_rider, moon_knight, elektra, bullseye, dr_sattler, t_rex, houdini, the_genie, ms_marvel, squirrel_girl, cloak_and_dagger, black_panther, black_widow, winter_soldier, she_hulk, spider_man, doctor_strange, nikola_tesla, annie_christmas, the_golden_bat, dr_jill_trent, oda_nobunaga, tomoe_gozen, william_shakespeare, hamlet, titania, the_wayward_sisters, geralt, ciri, yennefer_triss, philippa_eilhart, eredin, muhammad_ali, ancient_leshen, blackbeard, chupacabra, loki, pandora, leonardo, donatello, raphael, michelangelo, shredder, krang, wyatt_earp, john_henry, george_washington, rosie_the_riveter.

**Still to do:** nothing in this pass. Thinnest entries, with only the official Restoration Games article (or one guide) behind them, so "How they lose" says the sources don't cover it: leonardo, michelangelo, krang, john_henry; oda_nobunaga has only Gridbeast. Reviewing the YouTube videos listed under "Not cited" is the obvious next step for these.

**Note on `put.py`:** it expects every entry to end with `---`, but the last entry in each file (rosie_the_riveter) has none, so it can't splice that one. Rosie was spliced by hand.

**Workflow that worked (cheap on tokens):**
1. `python3 -I research/scripts/packs.py` builds `research/private/packs/{id}.md` for every fighter: deck data, old link list, the fighter's own sources and the shared sources that cover them (git ignores `research/private/`). Needs `research/private/unmatched-fighter-sources.md`.
2. Read one pack, then write `research/private/entries/{id}.med.md` and `{id}.short.md`, using any finished entry (e.g. Daredevil, Dracula) as the model.
3. `python3 -I research/scripts/put.py {id}` checks the pair (every [n] defined, bold names are real cards, no other fighter named in the body, word count) and splices both into the `input/` files. Add `--dry` to check only. "NAMES OTHER FIGHTER?" warnings must be fixed (rephrase); unused-ref warnings too.
4. Commit and push every few fighters.
Keep sessions short: a long conversation re-reads its whole history on every step, which is what made the first 47 expensive. About 10 fighters per session is a good size.

**Conventions used in the finished entries:**
- Medium entry about 500 words before References (the validator's count includes headings; 480–600 is fine). Short entry about 150.
- Card facts cite the deck as [1]: `Restoration Games. *Set name*, Hero deck. Card text as recorded in \`input/heroes.json\`.`
- Reddit: `u/name. Comment on "Thread title" by u/op. *r/Unmatched*, Reddit, D Month YYYY. URL`; later ones from the same thread: `u/name. Comment on "Thread title" (see [n]).` BGG: `name. Reply in "Thread" by op. *BoardGameGeek*, date. URL`. TFJ383's "An Unmatched Roster" posts are cited as articles.
- Where sources disagree, say so and cite both sides (e.g. "Gridbeast says X [2]; another player says Y [5]").
- "Not cited" lists: sources read but not used get "(read; reason)", videos get "(not yet reviewed)".
- When a guide disagrees with `heroes.json` on a value or copy count, the deck wins; note it below.
- Fighters the sources cover badly get a shorter entry rather than padding.

## 1. What's in the repo

| File | What it is |
|---|---|
| `input/fighter_strategies.md` | Medium write-up for all 74 fighters (about 420 words each, 36,000 total), with a Further reading list per fighter. Daredevil has been rewritten in the new cited format (about 500 words plus References) and is the model for the rest |
| `input/fighter_strategies_short.md` | Short write-up for all 74 fighters (about 145 words each), no links |
| `research/strategy-references.md` / `.csv` | 456 links (guides, threads, videos) filed by fighter. CSV columns: fighter, set, format, focus, source, title, url, date, checked, note |
| `research/youtube-transcripts/` | A prompt for Claude Code on your own computer, plus the 169 video links, to download transcripts (YouTube blocks cloud servers) |
| `research/scripts/` | Every script the session used, for reference (see section 5) |
| `research/drafts/` | The first, longer Daredevil sample (about 670 words), the headers of the two strategy files, and the map from reference-list fighter names to site ids |
| `research/HANDOFF.md` | This file |

**Not in the repo, on purpose:** `unmatched-fighter-sources.md`, the full text of every source (52 Gridbeast guides, 11 articles, 130 Reddit threads with 1,405 comments, 16 BoardGameGeek threads with 99 posts; about 236,000 words). It's other people's writing, so it shouldn't go in a public repo. It was sent as a download in the chat. Keep it on your computer in `research/private/` (git ignores that folder), or in a private repo, or rebuild it with the scripts (section 5).

## 2. Format of the strategy files

Each fighter entry starts with `<!-- id: {site id} -->` (ids from `input/fighters.json`) and follows this skeleton, which the owner chose:

```
## Fighter name
**In short:** one sentence on what kind of fighter this is and how they want the game to go.
### Plan A: name   (as many plans as the fighter really has, usually 2)
**Goal:** … **How to do it:** … **Watch out for:** …
### How they lose   (2–3 bullets)
### Key cards       (each: **Card name**: why it matters, when to play or hold it)
### Tips            (3–5 short practical tips)
### References       (numbered, academic style; short file keeps its own shorter list)
### Not cited       (medium file only: links read but not used, or not yet reviewed)
```

Length: aim for about 500 words per medium entry, not counting References and Not cited. Let the [n] numbers carry attribution; name a source in the sentence only where sources disagree. Don't repeat a point across Plans, Key cards and Tips.

The short file uses the same headings, with each plan on one line: `**Goal:** … · **How:** … · **Watch out:** …`, plus 2 bullets for How they lose, 2 key cards and 2–3 tips.

Entries were written one at a time in `entries/{id}.md` and `entries_short/{id}.md`, then joined by `assemble.py`. To edit them now, edit the two `input/` files directly.

## 3. Writing rules that were followed

- **In my own words, from sources only.** Nothing invented. If no source said it, it isn't there.
- **Numbers and card names come from `input/heroes.json`.** When a guide disagreed with the deck data (for example Gridbeast calling Tesla's Death Ray a 4 when the deck says 3), the deck data won.
- **Card names are spelled as in `heroes.json`**, except Loki's and Pandora's (written in normal capitals, the data has them in all caps) and Loki's "Shapeshifter" (spelled "Shapershifter" in the data).
- **No matchup tips at all.** The owner wants how each fighter wins and loses, not who beats whom. Never name a specific opposing fighter (no "against Bullseye…", no "such as Medusa"). Describe the kind of opponent or the mechanic instead (ranged fighters with sidekicks, heavy Feints, forced discards). "Playing against X" threads can still inform How they lose, written that way.
- **Cite everything, generalise nothing.** Every claim carries a numbered citation [n] pointing to the entry's References list, academic style. Card values and effects cite the deck ([1], `heroes.json`). Each forum commenter is cited as their own reference, not just the thread. Don't widen one source's point beyond what it says; where sources disagree, cite both sides. Links not used as sources go under "Not yet reviewed".
- **Written sources preferred**; reviews were not used as strategy sources.
- **Further reading** lists written guides first, then threads, then videos. Threads with fewer than 3 comments were left out, and so were three junk threads (an empty placeholder, a box-opening question, a rules question).

## 4. Known gaps and problems

**Thinner entries.** Leonardo, Michelangelo, Krang, John Henry and Annie Christmas had no player discussions. Their entries rest on official Restoration Games articles, Gridbeast (Annie only) and the deck data.

**BoardGameGeek wasn't used for the original entries.** (It is used in the new cited ones.) The 16 BGG threads, including the 11-part "An Unmatched Roster" analysis series, were downloaded after the entries were written. They're in the sources file and could improve many entries, especially Battle of Legends 1, Cobble & Fog, Jurassic Park, Hell's Kitchen, Redemption Row and the later Marvel boxes.

**YouTube transcripts aren't in yet.** Run the prompt in `research/youtube-transcripts/` on your own computer.

**The owner's open request:** "write more info and strategy, maybe correct some stuff". In progress; see section 0. The natural next step: re-read each fighter's sources (now including BGG and, once you have them, the transcripts) and revise the two strategy files.

**Data errors in `input/heroes.json`:**
- **Checked against card scans in October 2026; the full verified list is under "Card data corrections" in `research/CODEX-PROMPT.md`.** One of the guide disagreements below was the guide being right: What Big Eyes You Have is a 3.
- Michelangelo's Nunchaku says "All of Bruce Lee's attacks this turn are +1 value". That looks copied from Bruce Lee, so the card was left out of his entry.
- Loki: "Shapershifter" should be "Shapeshifter"; Icy guile (Eredin) says "Red Riper".
- Rosie the Riveter: Loose Lips Sink Ships! says "BOOS value".
- Eredin: Portal defense says "That fighter is ow the defender".
- Philippa: Spymaster's ruse is credited to "Djkstra".
- Loki's and Pandora's card titles are all in capitals, unlike every other fighter.
- Little Red's card titles include their symbol emoji (for example "Once Upon a Time 🌹").

- Alice's cards are credited to "Allice"; Sinbad's By Fortune and Fate to "The Potter".
- Houdini's boost effects (and probably other fighters' boost effects) are missing from the data; they were cited from Gridbeast.

**Guides that disagree with the deck data (deck used):** Gridbeast gives Claws That Catch (Alice) 2, What Big Eyes You Have (Little Red) 3, I'm Not Real (Moon Knight) 3, Double Identity 2 and Widow's Kiss 3 (Black Widow), 4 copies of Arrogant But Effective (Bullseye), Shuri 8 health, Elektra's resurrected health 9 (not in the data). Antlerflax says 2 Noble Sacrifice (deck: 3). Gridbeast's Willow reverts "in the same zone" as Tara (card: adjacent). Gridbeast adds a line to Luke Cage's ability (wins combat if he takes no damage) that isn't in the data.

**Thin sources in the new entries:** Buffy, Spike, Willow, Angel (Gridbeast plus one-line comments), Deadpool (Gridbeast only), Annie Christmas (Gridbeast plus one mention). Their entries are shorter.

**Fixed in the reference list:** the To The Table Top! review videos for Shredder and Krang were filed under each other. They were swapped back.

## 5. How the sources were gathered (to redo or extend)

| Source | How |
|---|---|
| Gridbeast (52 fighters) | Pages listed in the site's WordPress sitemap; article text pulled from each page. Only Dracula, Little Red and Squirrel Girl have a Strengths/Weaknesses section |
| Reddit (130 threads) | Reddit blocks automated requests, so threads came from the public arctic-shift archive: `https://arctic-shift.photon-reddit.com/api/posts/ids?ids=…` and `/api/comments/search?link_id=…&limit=100`. Send a custom User-Agent (the default one gets 403). A 422 means a timeout; retry or split the date range |
| BoardGameGeek (16 threads) | The website blocks bots, but the official XML API works with a token: `GET https://boardgamegeek.com/xmlapi2/thread?id={thread id}` with header `Authorization: Bearer $BGG_TOKEN`. Get a token at boardgamegeek.com/using_the_xml_api. Never commit the token |
| Restoration Games articles (4) | WordPress REST API: `https://restorationgames.com/wp-json/wp/v2/posts?slug={slug}&_fields=content,link` |
| Antlerflax Books (2) | WordPress.com API: `https://public-api.wordpress.com/rest/v1.1/sites/antlerflaxbooks.wordpress.com/posts/slug:{slug}` |
| The Gaming Geek, Round2Gaming | WordPress REST API, as for Restoration Games |
| WarBand.ru (2, in Russian), The Pop Insider | Plain page download |
| YouTube titles and channels | oEmbed: `https://www.youtube.com/oembed?url={video url}&format=json` (this works from the cloud) |
| YouTube transcripts | Blocked from cloud servers (CAPTCHA and "confirm you're not a bot"). Use the local prompt |

**Scripts in `research/scripts/`.** They ran in a temporary cloud folder, so their path arguments point at folders that no longer exist; read them as working examples.

- Reference list: `build_refs.py` builds the 456-row list, `build_md.py` turns it into Markdown, `classify.py` sorts Reddit candidates, `arctic.py` and `bodies.py` fetch Reddit posts, and `oembed.py`, `yt.py` and `ytlock.py` handle YouTube titles and playlists.
- Writing: `gridbeast.py`, `reddit_comments.py` and `other_written.py` fetch the source text. `briefs.py` makes one source pack per fighter, and `show.sh` prints a pack. `assemble.py` joins the entries into the two strategy files, and `check_cards.py` checks the card names against `heroes.json`.
- Sources file: `build_sources.py` builds `unmatched-fighter-sources.md` from the downloaded text.
- The small `.mjs` files are early helpers for the roster data.

## 6. Prompt to continue with Claude Code

Start a new session on branch `claude/strategy-guide-format-n0n1vb`, upload `unmatched-fighter-sources.md`, then paste:

> Read `research/HANDOFF.md`, sections 0, 2 and 3 first. Copy the uploaded `unmatched-fighter-sources.md` to `research/private/` (never commit it), then run `python3 -I research/scripts/packs.py`. Continue the research pass with the next 10 fighters from the "Still to do" list in section 0. For each one: read its pack in `research/private/packs/`, write the cited medium and short entries in `research/private/entries/` following the conventions in section 0 (use Daredevil or Dracula in `input/fighter_strategies.md` as the model), check and splice them with `python3 -I research/scripts/put.py <id>`, and fix any warnings. No matchup tips: never name another fighter. Don't add anything the sources don't say. Commit and push after every few fighters, and when you're done update the Done / Still to do lists in section 0.
