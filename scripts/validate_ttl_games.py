"""
Sanity-check scraped Tabletop League data against The Unmatched Club's Tabletop
League numbers: each fighter's overall win rate in the scrape should sit near
their Club win rate. A side swap or parsing bug shows up as fighters landing on
the wrong side of 50% (like the old transposed xlsx did).

Checks the fighter page grids (input/ttl_fighter_grids.json) by default, or the
scraped match games (input/ttl_games.jsonl) with --games. The match sample is
recent and the Club covers everything, so some drift is expected: a fighter is
flagged only when the gap is over --tolerance points AND over two standard
errors of their scraped record.

Usage:  python scripts/validate_ttl_games.py [--games] [--min-games 300] [--tolerance 3]
"""
import argparse
import json
import math
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)  # fetch_stats reads input/ with relative paths
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import fetch_stats  # noqa: E402
from build_map_stats import GAMES_FILE, GRIDS_FILE, read_games  # noqa: E402


def scraped_records(games):
    played, won = defaultdict(int), defaultdict(int)
    for g in games:
        for side in ("a", "b"):
            played[g[side]["fighter"]] += 1
            won[g[side]["fighter"]] += 1 if g[side]["won"] else 0
    return played, won


def grid_records(path):
    with open(path, encoding="utf-8") as f:
        fighters = json.load(f)["fighters"]
    return {k: g["games"] for k, g in fighters.items()}, {k: g["wins"] for k, g in fighters.items()}


def club_overall(fighter_id):
    """Fighter's games-weighted Tabletop League win % on The Unmatched Club."""
    games = wins = 0.0
    for key in fetch_stats.site_keys_for(fighter_id):
        for opp_key, m in fetch_stats.fetch_matchups(key, "tabletopleague").items():
            opp = fetch_stats.SITE_KEY_TO_FIGHTER_ID.get(opp_key)
            plays = int(m.get("plays") or 0)
            if opp is None or opp == fighter_id or not plays:
                continue
            games += plays
            wins += m["winRate"] / 100.0 * plays
    return (100.0 * wins / games if games else None), int(games)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-games", type=int, default=300, help="only fighters with this many scraped games")
    ap.add_argument("--tolerance", type=float, default=3.0, help="allowed gap in points")
    ap.add_argument("--games", action="store_true", help="check the scraped match games, not the grids")
    args = ap.parse_args()

    if args.games or not os.path.exists(GRIDS_FILE):
        played, won = scraped_records(read_games(GAMES_FILE))
    else:
        played, won = grid_records(GRIDS_FILE)
    fighters = sorted((f for f in played if played[f] >= args.min_games), key=lambda f: -played[f])
    if not fighters:
        sys.exit(f"No fighter has {args.min_games}+ scraped games yet "
                 f"(most: {max(played.values(), default=0)}). Try a lower --min-games.")

    flagged, same_side = [], 0
    print(f"{'fighter':<22}{'scraped':>9}{'games':>7}{'club TTL':>10}{'gap':>7}{'2 SE':>7}")
    for fid in fighters:
        pct = 100.0 * won[fid] / played[fid]
        se = 100.0 * math.sqrt(max(pct / 100 * (1 - pct / 100), 0.01) / played[fid])
        club, _ = club_overall(fid)
        if club is None:
            print(f"{fid:<22}{pct:>8.1f}%{played[fid]:>7}{'—':>10}")
            continue
        gap = pct - club
        same_side += (pct - 50) * (club - 50) >= 0
        bad = abs(gap) > args.tolerance and abs(gap) > 2 * se
        flagged += [fid] if bad else []
        print(f"{fid:<22}{pct:>8.1f}%{played[fid]:>7}{club:>9.1f}%{gap:>+7.1f}{2 * se:>7.1f}{'  <-- check' if bad else ''}")

    print(f"\n{len(fighters) - len(flagged)}/{len(fighters)} fighters within tolerance; "
          f"{same_side}/{len(fighters)} on the same side of 50% as the Club.")
    sys.exit(1 if flagged else 0)


if __name__ == "__main__":
    main()
