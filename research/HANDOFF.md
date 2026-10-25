# Fighter strategy research: handoff notes

Everything the cloud session that wrote the fighter strategy files knew, so the work can continue anywhere. All of it is on the branch `claude/jolly-mayer-q2s9pw` of `moudimash99/unmatched_matcher`.

## 1. What's in the repo

| File | What it is |
|---|---|
| `input/fighter_strategies.md` | Medium write-up for all 74 fighters (about 420 words each, 36,000 total), with a Further reading list per fighter |
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
### Not yet reviewed (medium file only: links not used as sources)
```

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

**BoardGameGeek wasn't used for writing.** The 16 BGG threads, including the 11-part "An Unmatched Roster" analysis series, were downloaded after the entries were written. They're in the sources file and could improve many entries, especially Battle of Legends 1, Cobble & Fog, Jurassic Park, Hell's Kitchen, Redemption Row and the later Marvel boxes.

**YouTube transcripts aren't in yet.** Run the prompt in `research/youtube-transcripts/` on your own computer.

**The owner's open request:** "write more info and strategy, maybe correct some stuff". Not started. The natural next step: re-read each fighter's sources (now including BGG and, once you have them, the transcripts) and revise the two strategy files.

**Data errors in `input/heroes.json`:**
- Michelangelo's Nunchaku says "All of Bruce Lee's attacks this turn are +1 value". That looks copied from Bruce Lee, so the card was left out of his entry.
- Loki: "Shapershifter" should be "Shapeshifter"; Icy guile (Eredin) says "Red Riper".
- Rosie the Riveter: Loose Lips Sink Ships! says "BOOS value".
- Eredin: Portal defense says "That fighter is ow the defender".
- Philippa: Spymaster's ruse is credited to "Djkstra".
- Loki's and Pandora's card titles are all in capitals, unlike every other fighter.
- Little Red's card titles include their symbol emoji (for example "Once Upon a Time 🌹").

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

Open Claude Code in this repo, with `unmatched-fighter-sources.md` (and the transcripts, if you have them) in `research/private/`, which git ignores, then paste:

> Read `research/HANDOFF.md`. Then, for each fighter in `input/fighters.json`, read that fighter's section of `research/private/unmatched-fighter-sources.md` (including the shared sources it points to) and improve its entries in `input/fighter_strategies.md` and `input/fighter_strategies_short.md`. Add strategy the sources support that's missing, and correct anything they contradict. Follow the writing rules in section 3 and keep the format in section 2. Start with the fighters the BoardGameGeek "An Unmatched Roster" posts cover. Show me one fighter's changes before doing the rest.
