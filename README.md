# unmatched_matcher

## Win-rate stats

Matchup stats come from [The Unmatched Club](https://www.the-unmatched.club/tools/matchups),
which combines Tabletop League (prev. UMLeague) and UnmatchedRu games. Refresh them with:

```bash
python fetch_stats.py            # all sources
python fetch_stats.py tabletopleague   # or: unmatchedru
```

This writes `input/win_matrix.json`, `input/merged_games.json` and `input/stats_meta.json`.
The `Refresh win-rate stats` GitHub workflow does this weekly and opens a PR when the numbers change
(enable *Settings → Actions → Allow GitHub Actions to create pull requests*).

A matchup's own record is fully trusted from 10 games on. Below that, confidence climbs
logarithmically from 0 and the estimate is blended with what both fighters' overall win rates
predict (log5), so a 0% from a single game no longer counts as a blowout.

When adding a fighter to `input/fighters.json`, set its `club_key` to the hero's slug on
The Unmatched Club (e.g. `harry-houdini` for Houdini).

## Testing

Install dependencies and run the test suite with pytest:

```bash
pip install -r requirements.txt
pytest
```

Tests also run automatically in CI via GitHub Actions.
