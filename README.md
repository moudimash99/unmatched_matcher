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
