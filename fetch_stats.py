"""
Pull matchup stats from The Unmatched Club (https://www.the-unmatched.club/tools/matchups),
which aggregates Tabletop League (prev. UMLeague) and UnmatchedRu games.

Writes:
  - input/merged_games.json : games[f1][f2] = games played
  - input/merged_win_pct.json : win[f1][f2] = f1's win % vs f2, or -2 if no data
  - input/stats_meta.json   : when the stats were fetched, from which source, game count

Each fighter's hero key on the site is its "club_key" in input/fighters.json.

Usage:  python fetch_stats.py [tabletopleague|unmatchedru]   (default: all sources)
"""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

FIGHTERS_FILE = "input/fighters.json"
API_URL = "https://www.the-unmatched.club/api/matchup"

# Extra site heroes whose games are pooled into one of our fighters
# (the site splits these out as separate hero variants).
POOLED_SITE_KEYS = {
    "buffy-giles": "buffy",
    "buffy-xander": "buffy",
    "yennefer": "yennefer_triss",
    "triss": "yennefer_triss",
}


# ---------------------------------------------------
# 1. Fighters and site-key mapping
# ---------------------------------------------------

with open(FIGHTERS_FILE, "r", encoding="utf-8") as f:
    FIGHTERS = json.load(f)["fighters"]

FIGHTER_IDS = [f["id"] for f in FIGHTERS]
SITE_KEY_TO_FIGHTER_ID = {f["club_key"]: f["id"] for f in FIGHTERS}
SITE_KEY_TO_FIGHTER_ID.update(POOLED_SITE_KEYS)


def site_keys_for(fighter_id):
    """All site hero keys whose games count for one of our fighters."""
    return [k for k, v in SITE_KEY_TO_FIGHTER_ID.items() if v == fighter_id]


# ---------------------------------------------------
# 2. Fetch
# ---------------------------------------------------

def fetch_matchups(site_key, source=None):
    """Returns {opponent_site_key: {'winRate': int, 'plays': int}} for one hero."""
    params = {"h1": site_key}
    if source:
        params["source"] = source
    req = urllib.request.Request(
        f"{API_URL}?{urllib.parse.urlencode(params)}",
        headers={"User-Agent": "unmatched-matcher-stats-sync"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp).get("matchups", {})


# ---------------------------------------------------
# 3. Build fighter-id keyed matrices
# ---------------------------------------------------

def build_matrices(source=None):
    games = defaultdict(lambda: defaultdict(int))
    wins = defaultdict(lambda: defaultdict(float))

    for f1 in FIGHTER_IDS:
        for key in site_keys_for(f1):
            try:
                matchups = fetch_matchups(key, source)
            except urllib.error.HTTPError as e:
                print(f"  ! {key}: HTTP {e.code}, skipped")
                continue
            time.sleep(0.3)  # be polite to the site

            for opp_key, m in matchups.items():
                f2 = SITE_KEY_TO_FIGHTER_ID.get(opp_key)
                plays = int(m.get("plays") or 0)
                if f2 is None or f2 == f1 or plays == 0:
                    continue
                games[f1][f2] += plays
                wins[f1][f2] += m["winRate"] / 100.0 * plays

    merged_games = {}
    win_pct = {}
    for f1 in FIGHTER_IDS:
        merged_games[f1] = {}
        win_pct[f1] = {}
        for f2 in FIGHTER_IDS:
            g = games[f1][f2]
            merged_games[f1][f2] = g
            win_pct[f1][f2] = round(100.0 * wins[f1][f2] / g, 1) if g else -2

    return merged_games, win_pct


if __name__ == "__main__":
    source = sys.argv[1] if len(sys.argv) > 1 else None
    merged_games, win_pct = build_matrices(source)

    no_data = [f for f in FIGHTER_IDS if not any(merged_games[f].values())]
    total_games = sum(sum(row.values()) for row in merged_games.values()) // 2
    print(f"Fighters: {len(FIGHTER_IDS)}, games: {total_games}, without any games: {no_data or 'none'}")

    with open("input/merged_games.json", "w", encoding="utf-8") as f:
        json.dump(merged_games, f, indent=2, ensure_ascii=False, sort_keys=True)

    # The app reads its win-rate matrix from input/merged_win_pct.json
    with open("input/merged_win_pct.json", "w", encoding="utf-8") as f:
        json.dump(win_pct, f, indent=2, ensure_ascii=False, sort_keys=True)

    with open("input/stats_meta.json", "w", encoding="utf-8") as f:
        json.dump({
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "source": source or "all",
            "total_games": total_games,
        }, f, indent=2)
