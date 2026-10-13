"""
Aggregate Tabletop League data into input/map_stats.json: fighter x map,
matchup x map, first-player and closeness counts.

- Fighter x map and matchup x map come from the all-time fighter page grids
  (input/ttl_fighter_grids.json, scrape_ttl_fighter_stats.py) when present,
  else from the scraped games.
- First player and closeness need turn order and end health, which only match
  pages show: they always come from input/ttl_games.jsonl (scrape_ttl_matches.py).

Everything is stored as counts (not percentages) so the app can blend them
exactly. Pair tables are stored in both directions: matchup_map[a][b][map] and
matchup_map[b][a][map] describe the same games from each side.

Usage:  python scripts/build_map_stats.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMES_FILE = os.path.join(ROOT, "input", "ttl_games.jsonl")
STATE_FILE = os.path.join(ROOT, "input", "ttl_scrape_state.json")
GRIDS_FILE = os.path.join(ROOT, "input", "ttl_fighter_grids.json")
OUT_FILE = os.path.join(ROOT, "input", "map_stats.json")


def read_games(path):
    """Unique games from the jsonl (a rerun after a crash can append a match twice)."""
    games, seen = [], set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            g = json.loads(line)
            key = (g["match_id"], g["game_index"])
            if key not in seen:
                seen.add(key)
                games.append(g)
    return games


def _bump(table, *keys, **counts):
    node = table
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    cell = node.setdefault(keys[-1], {k: 0 for k in counts})
    for k, v in counts.items():
        cell[k] += v


def map_tables_from_grids(grids):
    """
    fighter_map and matchup_map from the fighter page grids. Each fighter's own page gives their
    side; a pair whose other fighter has no page yet is filled in by flipping this side.
    """
    fighter_map, matchup_map = {}, {}
    for fid, g in grids.items():
        fighter_map[fid] = {m: dict(c) for m, c in g["maps"].items()}
        for opp, by_map in g["vs"].items():
            matchup_map.setdefault(fid, {})[opp] = {
                m: {"games": c["games"], "wins_a": c["wins"]} for m, c in by_map.items()}
    for fid, g in grids.items():
        for opp, by_map in g["vs"].items():
            if opp in grids:
                continue
            matchup_map.setdefault(opp, {})[fid] = {
                m: {"games": c["games"], "wins_a": c["games"] - c["wins"]} for m, c in by_map.items()}
            for m, c in by_map.items():
                _bump(fighter_map, opp, m, games=c["games"], wins=c["games"] - c["wins"])
    return fighter_map, matchup_map


def build(games, scrape_skipped=None, grids=None):
    stats = {"fighter_map": {}, "matchup_map": {}, "first_player": {},
             "map_first_player": {}, "closeness": {}}
    skipped = dict(scrape_skipped or {})
    dates = [g["played_at"] for g in games if g.get("played_at")]
    grid_fighters = (grids or {}).get("fighters") or {}
    if grid_fighters:
        stats["fighter_map"], stats["matchup_map"] = map_tables_from_grids(grid_fighters)
    for g in games:
        a, b, m = g["a"], g["b"], g["map"]
        fa, fb = a["fighter"], b["fighter"]
        a_won = 1 if a["won"] else 0
        if not grid_fighters:
            _bump(stats["fighter_map"], fa, m, games=1, wins=a_won)
            _bump(stats["fighter_map"], fb, m, games=1, wins=1 - a_won)
            _bump(stats["matchup_map"], fa, fb, m, games=1, wins_a=a_won)
            _bump(stats["matchup_map"], fb, fa, m, games=1, wins_a=1 - a_won)

        if a["went_first"] is not None and b["went_first"] is not None:
            first_won = 1 if (a["went_first"] == a["won"]) else 0
            _bump(stats["first_player"], fa, fb, games=1, first_wins=first_won)
            _bump(stats["first_player"], fb, fa, games=1, first_wins=first_won)
            _bump(stats["map_first_player"], m, games=1, first_wins=first_won)
        else:
            skipped["no_turn_order"] = skipped.get("no_turn_order", 0) + 1

        winner_hp = a["end_health"] if a["won"] else b["end_health"]
        if winner_hp is not None:
            _bump(stats["closeness"], fa, fb, games=1, winner_health_sum=winner_hp)
            _bump(stats["closeness"], fb, fa, games=1, winner_health_sum=winner_hp)
        else:
            skipped["no_end_health"] = skipped.get("no_end_health", 0) + 1

    # Every game appears in fighter_map once per side
    map_games = sum(c["games"] for by_map in stats["fighter_map"].values() for c in by_map.values()) // 2
    stats["meta"] = {
        # Map numbers
        "map_games": map_games,
        "map_source": "fighter_pages" if grid_fighters else "match_pages",
        "map_fetched": grids.get("fetched_to") if grid_fighters else None,
        # Turn order and closeness (the scraped match sample)
        "games": len(games),
        "matches": len({g["match_id"] for g in games}),
        "from": min(dates) if dates else None,
        "to": max(dates) if dates else None,
        "skipped": dict(sorted(skipped.items())),
        "source": "https://www.tabletopleague.com/games/unmatched/matches",
    }
    return stats


def main():
    grids = None
    if os.path.exists(GRIDS_FILE):
        with open(GRIDS_FILE, encoding="utf-8") as f:
            grids = json.load(f)
    if not os.path.exists(GAMES_FILE) and not grids:
        sys.exit(f"Neither {GRIDS_FILE} nor {GAMES_FILE} exists; run scripts/scrape_ttl_fighter_stats.py "
                 "and/or scripts/scrape_ttl_matches.py first.")
    games = read_games(GAMES_FILE) if os.path.exists(GAMES_FILE) else []
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            scrape_skipped = json.load(f).get("skipped", {})
    except (FileNotFoundError, json.JSONDecodeError):
        scrape_skipped = {}
    stats = build(games, scrape_skipped, grids)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, separators=(",", ":"), sort_keys=True)
        f.write("\n")
    meta = stats["meta"]
    print(f"Wrote {OUT_FILE}: map stats from {meta['map_games']:,} games ({meta['map_source']}); "
          f"turn order and closeness from {meta['games']} games in {meta['matches']} matches "
          f"({meta['from']} to {meta['to']}). Skipped: {meta['skipped'] or 'none'}")


if __name__ == "__main__":
    main()
