# unmatched_matcher

## Win-rate stats

Matchup stats come from [The Unmatched Club](https://www.the-unmatched.club/tools/matchups),
which combines Tabletop League (prev. UMLeague) and UnmatchedRu games. Refresh them with:

```bash
python fetch_stats.py            # all sources
python fetch_stats.py tabletopleague   # or: unmatchedru
```

This writes `input/merged_win_pct.json`, `input/merged_games.json` and `input/stats_meta.json`.
The `Refresh win-rate stats` GitHub workflow does this weekly and opens a PR when the numbers change
(enable *Settings → Actions → Allow GitHub Actions to create pull requests*).
`scripts/win_calc.ipynb` builds the same two matrices offline from `input/Unmatched_Stats.xlsx`.

A matchup's own record is fully trusted from 10 games on. Below that, confidence climbs
logarithmically from 0 and the estimate is blended with what both fighters' overall win rates
predict (log5), so a 0% from a single game no longer counts as a blowout.

When adding a fighter to `input/fighters.json`, set its `club_key` to the hero's slug on
The Unmatched Club (e.g. `harry-houdini` for Houdini), then run `python fetch_heroes.py`.

## Map and turn-order stats

Per-map numbers come from [Tabletop League](https://www.tabletopleague.com/games/unmatched/stats/characters).
Their pages are client-rendered, so the scrapers drive a headless browser:

- **Fighter × map and matchup × map**: each fighter's stats page shows their all-time record on
  every map against every opponent (its "Battle Grid"). One page per fighter covers every game.
- **First-player win rate and how much health the winner has left**: only individual match pages
  show turn order and end health, so these come from a sample of recent matches.

```bash
pip install playwright && playwright install chromium   # or pass --channel chrome
python fetch_maps.py                              # input/maps.json + static/maps/ images (The Unmatched Club)
python scripts/scrape_ttl_fighter_stats.py        # all fighter pages -> input/ttl_fighter_grids.json (~5 min)
python scripts/scrape_ttl_matches.py              # up to 500 new matches -> input/ttl_games.jsonl
python scripts/build_map_stats.py                 # both -> input/map_stats.json
python scripts/validate_ttl_games.py              # compare the grids with the Club's Tabletop League rates
```

- The fighter page scraper skips pages fetched in the last 7 days (`--max-age-days 0` refetches
  all, `--only bruce-lee` fetches one), so an interrupted run picks up where it stopped. Raw
  responses are cached in `scratch/ttl_fighter_raw/`; `--reparse` rebuilds the json from them.
- The match scraper is incremental and resumable: done matches are kept in `input/ttl_scrape_state.json`
  after every match, so Ctrl-C loses nothing and a rerun only loads new matches (and keeps
  backfilling older ones until it has walked the whole listing). `--max-matches N`, `--since YYYY-MM-DD`.
  Rendered pages are cached in `scratch/ttl_raw/` (gitignored); `--reparse` rebuilds
  `input/ttl_games.jsonl` from the cache.
- Names that don't map to our fighters or maps are listed in `input/ttl_unmapped.json` (match
  scraper) and under `unmapped` in `input/ttl_fighter_grids.json`. Add fighter or map aliases in
  `FIGHTER_ALIASES` / `MAP_ALIASES` in `scripts/scrape_ttl_matches.py`, and maps the Club doesn't
  list in `EXTRA_MAPS` in `fetch_maps.py`. Alternate card versions ("Buffy - Alt 1.0") are left out.
- Team (2v2) games, mirrors and games with a missing map or fighter are skipped and counted in the
  stats' `meta.skipped`.

On the results page, each matchup suggests 7 maps from the owned sets, fairest first, always
including the fairest map from each fighter's own box. Picking a map (optional) shows every card's
win % on that map; the choice is kept in the form and in shared links (`&map=<key>`). Maps don't
change which fighters are suggested.

Estimates use the same confidence rule as matchups: a fighter's *lean* on a map (log-odds better
or worse than their own record across all maps) and a matchup's record on a map are fully trusted
from 10 games (`MAP_FULL_CONFIDENCE_GAMES` in `map_stats.py`), and blended toward no lean below that.

## Tournaments

`/tournaments` runs knockout tournaments of fighters: players take turns playing the matches, and
whoever plays the winning fighter scores (every win is 1 point, or weighted so upsets count more).
Several tournaments can run at once. They're saved on the server, so every phone sees the same
bracket (pages refresh every few seconds), and one shared password protects the whole area.

- **New tournament:** pick sets and fighters. Round 1 pairs the fairest matchups; if the number of
  fighters isn't a power of two, the rest get byes into round 2.
- **Edit bracket** (any time): matches already played never change. On unplayed matches you can
  change who's in a slot, swap two slots, add a **play-in** (whoever holds a slot has to beat a
  challenger first), and add, rename, move or delete matches and rounds. New fighters wait on the
  **bench**; "Slot them in" gives each one a play-in against the fighters in a round who have
  played the fewest matches (the ones who had byes), fairest pairings first.
- **History:** every change is a version; restoring one saves it as the newest version.
- The model and every change live in `tournaments.py` (each change is checked so a bad edit can't
  break a bracket); the pages and API are in `tournaments_web.py`.

### Setup

Secrets go in `.env` next to `app.py` (gitignored; the repo is public, and anyone with
`SECRET_KEY` could forge a login). See `.env.example`:

```bash
SECRET_KEY=<long random string>
TOURNAMENT_PASSWORD_HASH=<sha256 hex of the password>
```

`python app.py` and docker-compose both read it. docker-compose also mounts `./data` for the saved
tournaments, so on the server: copy `.env` next to `docker-compose.yml`, then `docker compose up -d --build`.
Without `.env`, local runs fall back to the password `dev`. Five wrong passwords from one address
lock it out for 15 minutes.

### Moving over from the old Unmatched-Tournament app

Either upload `data/bracket.json` and `data/state.json` on the `/tournaments` page, or on the
server (both repos side by side):

```bash
python scripts/import_old_tournament.py ../Unmatched-Tournament/data/bracket.json     ../Unmatched-Tournament/data/state.json --name "The big one" --p1 Ahmad --p2 Mohammad
```

Results, players, scores and layouts from its rebalance button all come across.

## Other data

| Script | Writes | Source |
|---|---|---|
| `fetch_heroes.py` | `input/heroes.json` – stats, special ability, sidekicks, deck list per fighter | The Unmatched Club hero pages |
| `fetch_prices.py` | `input/prices.json` – price, stock and store link per set | Restoration Games store (public WooCommerce Store API) |

New sets need their store product id added to `PRODUCT_TO_SET` in `fetch_prices.py`.
The weekly workflow refreshes prices along with the stats.

## Pages

| Path | What it does |
|---|---|
| `/` | Matchup generator |
| `/collection` | Pick the sets you own (stored in a cookie; every tool and the matcher use it) |
| `/fighters`, `/fighter/<id>` | Fighter list; profile with deck, ability, best/worst matchups |
| `/buy-next` | Ranks unowned sets by new fair matchups, value per $, new playstyles/ranges, with price and stock |
| `/tiers` | Tier list and matchup heatmap for your collection |
| `/counter?vs=<id>` | Your fighters ranked against the opponent's pick |
| `/game-night` | Fighters for 2–6 players so every round-robin game is fair; or two fair 2v2 teams |
| `/draft` | Ban / pick / blind-pick draft with win rates |
| `/log` | Personal game log (browser storage) with results vs. expected, plus underdog challenges |

Tool pages accept `?sets=<set>&sets=<set>` to use a specific collection (shareable links).

## Testing

Install dependencies and run the test suite with pytest:

```bash
pip install -r requirements.txt
pytest
```

Tests also run automatically in CI via GitHub Actions.
