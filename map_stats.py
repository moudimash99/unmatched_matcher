"""
Per-map estimates from Tabletop League match data (input/map_stats.json, built by
scripts/build_map_stats.py): how fighters and matchups do on each battlefield,
how much going first helps, and how close games end.

Every number is blended like the engine's matchup win rates: a record is fully
trusted from MAP_FULL_CONFIDENCE_GAMES games, and below that it leans on a
broader estimate.

- A fighter's *map lean* is how much better (in log-odds) they do on a map than
  in all of their scraped games. It is measured against their scraped record,
  not their overall win rate, so the scraped sample's own bias cancels out.
- A matchup on a map starts from the matchup's overall estimate, shifted by both
  fighters' leans, then blends in that matchup's own record on the map.
"""
import math

from matchup_engine import FULL_CONFIDENCE_GAMES, MatchupEngine

MAP_FULL_CONFIDENCE_GAMES = FULL_CONFIDENCE_GAMES
# "Fairest maps" only lists maps whose estimate is this close to 50%
FAIR_MAP_BAND = 10.0
# How many maps a matchup suggests; maps from the two fighters' own boxes are always among them
SUGGESTED_MAPS = 7
MIN_PCT, MAX_PCT = 1.0, 99.0


def _clamp(pct):
    return min(MAX_PCT, max(MIN_PCT, pct))


def _logit(pct):
    p = _clamp(pct) / 100.0
    return math.log(p / (1 - p))


def _sigmoid_pct(x):
    return _clamp(100.0 / (1 + math.exp(-x)))


def _confidence(games):
    return MatchupEngine.confidence(games, MAP_FULL_CONFIDENCE_GAMES)


def rounded(value):
    """Floats rounded to 2 decimals all through a JSON-ready structure (keeps the page small)."""
    if isinstance(value, float):
        return round(value, 2)
    if isinstance(value, dict):
        return {k: rounded(v) for k, v in value.items()}
    if isinstance(value, list):
        return [rounded(v) for v in value]
    return value


def _blend(observed, games, fallback):
    c = _confidence(games)
    return c * observed + (1 - c) * fallback


class MapStats:
    def __init__(self, engine, stats, maps):
        self.engine = engine
        self.maps = maps or {}
        stats = stats or {}
        self.fighter_map = stats.get("fighter_map", {})
        self.matchup_map = stats.get("matchup_map", {})
        self.first = stats.get("first_player", {})
        self.map_first = stats.get("map_first_player", {})
        self.closeness_counts = stats.get("closeness", {})
        self.meta = stats.get("meta", {})

        # Each fighter's record over all scraped games, the baseline for map leans
        self.sample = {}
        for fid, by_map in self.fighter_map.items():
            games = sum(c["games"] for c in by_map.values())
            wins = sum(c["wins"] for c in by_map.values())
            self.sample[fid] = (100.0 * wins / games if games else None, games)

        first_games = sum(c["games"] for c in self.map_first.values())
        first_wins = sum(c["first_wins"] for c in self.map_first.values())
        self.first_player_pct = 100.0 * first_wins / first_games if first_games else 50.0

        hp_games = hp_sum = 0
        for by_b in self.closeness_counts.values():
            for c in by_b.values():
                hp_games += c["games"]
                hp_sum += c["winner_health_sum"]
        # Pair tables hold every game twice (once from each side); the ratio is unaffected
        self.avg_winner_health = hp_sum / hp_games if hp_games else None

    @property
    def has_data(self):
        return bool(self.fighter_map)

    # -- fighters on maps --------------------------------------------------

    def lean(self, fighter_id, map_key):
        """Confidence-blended log-odds shift for this fighter on this map (0 = no different)."""
        base, _ = self.sample.get(fighter_id, (None, 0))
        cell = self.fighter_map.get(fighter_id, {}).get(map_key)
        if base is None or not cell or not cell["games"]:
            return 0.0
        on_map = _blend(100.0 * cell["wins"] / cell["games"], cell["games"], base)
        return _logit(on_map) - _logit(base)

    def fighter_on_map(self, fighter_id, map_key):
        """The fighter's overall win rate, shifted by their lean on this map."""
        cell = self.fighter_map.get(fighter_id, {}).get(map_key, {})
        games = cell.get("games", 0)
        overall = self.engine.overall_win_rate(fighter_id)
        if overall is None:
            overall = self.sample.get(fighter_id, (None, 0))[0] or 50.0
        pct = _sigmoid_pct(_logit(overall) + self.lean(fighter_id, map_key))
        return {"win_pct": pct, "games": games, "low_data": games < MAP_FULL_CONFIDENCE_GAMES,
                "lean_pts": pct - overall}

    def fighter_maps(self, fighter_id):
        """Every map the fighter has scraped games on, best first."""
        rows = []
        for map_key in self.fighter_map.get(fighter_id, {}):
            if map_key in self.maps:
                rows.append({"map": self.maps[map_key], **self.fighter_on_map(fighter_id, map_key)})
        return sorted(rows, key=lambda r: r["win_pct"], reverse=True)

    # -- matchups on maps --------------------------------------------------

    def matchup_on_map(self, id_a, id_b, map_key):
        """A's win % vs B on this map."""
        base = self.engine.estimate_win_rate(id_a, id_b)
        expected = _sigmoid_pct(_logit(base) + self.lean(id_a, map_key) - self.lean(id_b, map_key))
        cell = self.matchup_map.get(id_a, {}).get(id_b, {}).get(map_key)
        games = cell["games"] if cell else 0
        pct = _blend(100.0 * cell["wins_a"] / games, games, expected) if games else expected
        return {"win_pct": pct, "games": games, "low_data": games < MAP_FULL_CONFIDENCE_GAMES}

    def _has_map_data(self, id_a, id_b, map_key):
        return any(map_key in self.fighter_map.get(fid, {}) for fid in (id_a, id_b))

    def map_suggestions(self, id_a, id_b, owned_sets=None, n=3):
        """
        Fair maps (closest to 50% first), and the maps that favor each side, among maps in the owned
        sets (all maps when none are given) that either fighter has data on.
        """
        owned = set(owned_sets or [])
        rows = []
        for key, m in self.maps.items():
            if owned and m.get("set") not in owned:
                continue
            if not self._has_map_data(id_a, id_b, key):
                continue
            rows.append({"map": m, **self.matchup_on_map(id_a, id_b, key)})
        base = self.engine.estimate_win_rate(id_a, id_b)
        fairest = sorted((r for r in rows if abs(r["win_pct"] - 50.0) <= FAIR_MAP_BAND),
                         key=lambda r: abs(r["win_pct"] - 50.0))[:n]
        favor_a = [r for r in sorted(rows, key=lambda r: -r["win_pct"]) if r["win_pct"] > base + 0.5][:n]
        favor_b = [r for r in sorted(rows, key=lambda r: r["win_pct"]) if r["win_pct"] < base - 0.5][:n]
        return {"base": base, "fairest": fairest, "favor_a": favor_a, "favor_b": favor_b, "count": len(rows)}

    # -- turn order and closeness ------------------------------------------

    def first_player(self, id_a, id_b):
        """Win % for whoever goes first in this matchup, blended with the overall first-player rate."""
        cell = self.first.get(id_a, {}).get(id_b)
        games = cell["games"] if cell else 0
        pct = self.first_player_pct
        if games:
            pct = _blend(100.0 * cell["first_wins"] / games, games, pct)
        return {"win_pct": pct, "games": games, "low_data": games < MAP_FULL_CONFIDENCE_GAMES}

    def map_first_player(self, map_key):
        cell = self.map_first.get(map_key)
        games = cell["games"] if cell else 0
        pct = _blend(100.0 * cell["first_wins"] / games, games, self.first_player_pct) if games \
            else self.first_player_pct
        return {"win_pct": pct, "games": games, "low_data": games < MAP_FULL_CONFIDENCE_GAMES}

    def closeness(self, id_a, id_b):
        """Average health the winner ends on (lower = closer games), blended with the overall average."""
        if self.avg_winner_health is None:
            return None
        cell = self.closeness_counts.get(id_a, {}).get(id_b)
        games = cell["games"] if cell else 0
        avg = self.avg_winner_health
        if games:
            avg = _blend(cell["winner_health_sum"] / games, games, avg)
        return {"winner_health": avg, "games": games, "low_data": games < MAP_FULL_CONFIDENCE_GAMES}

    # -- explanations (the numbers behind each estimate, for the page's "how is this worked out") --

    def _explain_side(self, fighter_id, map_key):
        all_maps, all_games = self.sample.get(fighter_id, (None, 0))
        cell = self.fighter_map.get(fighter_id, {}).get(map_key) or {"games": 0, "wins": 0}
        games = cell["games"]
        on_map = 100.0 * cell["wins"] / games if games else None
        return {"wins": cell["wins"], "games": games, "on_map": on_map,
                "all_maps": all_maps, "all_games": all_games, "conf": _confidence(games),
                "blended": _blend(on_map, games, all_maps) if games and all_maps is not None else all_maps}

    def explain_on_map(self, id_a, id_b, map_key):
        """Every step of matchup_on_map(A, B, map): the overall matchup, each fighter's map record, the pair's own games."""
        base = self.engine.estimate_win_rate(id_a, id_b)
        lean_a, lean_b = self.lean(id_a, map_key), self.lean(id_b, map_key)
        cell = self.matchup_map.get(id_a, {}).get(id_b, {}).get(map_key) or {"games": 0, "wins_a": 0}
        return {
            "base": base,
            "a": self._explain_side(id_a, map_key),
            "b": self._explain_side(id_b, map_key),
            # What each fighter's map record alone does to A's win %
            "shift_a": _sigmoid_pct(_logit(base) + lean_a) - base,
            "shift_b": _sigmoid_pct(_logit(base) - lean_b) - base,
            "expected": _sigmoid_pct(_logit(base) + lean_a - lean_b),
            "pair_wins": cell["wins_a"], "pair_games": cell["games"], "pair_conf": _confidence(cell["games"]),
            "final": self.matchup_on_map(id_a, id_b, map_key)["win_pct"],
            "full_games": MAP_FULL_CONFIDENCE_GAMES,
        }

    def explain_first_player(self, id_a, id_b):
        cell = self.first.get(id_a, {}).get(id_b) or {"games": 0, "first_wins": 0}
        return {"overall": self.first_player_pct, "overall_games": sum(c["games"] for c in self.map_first.values()),
                "wins": cell["first_wins"], "games": cell["games"], "conf": _confidence(cell["games"]),
                "final": self.first_player(id_a, id_b)["win_pct"], "full_games": MAP_FULL_CONFIDENCE_GAMES}

    def explain_closeness(self, id_a, id_b):
        close = self.closeness(id_a, id_b)
        if close is None:
            return None
        cell = self.closeness_counts.get(id_a, {}).get(id_b) or {"games": 0, "winner_health_sum": 0}
        games = cell["games"]
        return {"overall": self.avg_winner_health, "pair": cell["winner_health_sum"] / games if games else None,
                "games": games, "conf": _confidence(games), "final": close["winner_health"],
                "full_games": MAP_FULL_CONFIDENCE_GAMES}

    # -- page data ---------------------------------------------------------

    def playable_maps(self, owned_sets=None, home_sets=()):
        """Map keys from the owned sets (every map with a set when none are given) plus the home boxes."""
        owned, home = set(owned_sets or []), set(home_sets)
        return [k for k, m in self.maps.items()
                if m.get("set") and (not owned or m["set"] in owned or m["set"] in home)]

    def suggested_maps(self, id_a, id_b, owned_sets=None, home_sets=((), ()), n=SUGGESTED_MAPS):
        """
        Up to n maps for A vs B, fairest first. home_sets holds each fighter's own boxes: the fairest
        map from each fighter's box always makes the list; the rest are the fairest other playable maps.
        """
        home = {s for sets in home_sets for s in sets}
        rows = [{"map": self.maps[k], "home": self.maps[k]["set"] in home, **self.matchup_on_map(id_a, id_b, k)}
                for k in self.playable_maps(owned_sets, home)]
        unfairness = lambda r: abs(r["win_pct"] - 50.0)  # noqa: E731
        rows.sort(key=unfairness)
        picked = []
        for sets in home_sets:
            own = [r for r in rows if r["map"]["set"] in set(sets)]
            if own and not any(r in picked for r in own):
                picked.append(own[0])
        picked += [r for r in rows if r not in picked][:max(n - len(picked), 0)]
        return sorted(picked[:n], key=unfairness)

    def matchup_panel(self, id_a, id_b, owned_sets=None, home_sets=((), ())):
        """Everything the results page shows about maps and turn order for A vs B (JSON-ready)."""
        def row(r):
            return {"key": r["map"]["key"], "name": r["map"]["name"], "set": r["map"].get("set"),
                    "pct": round(r["win_pct"]), "games": r["games"], "low": r["low_data"],
                    **({"home": r["home"]} if "home" in r else {})}

        sugg = self.map_suggestions(id_a, id_b, owned_sets)
        first = self.first_player(id_a, id_b)
        close = self.closeness(id_a, id_b)
        by_map, explain_maps = {}, {}
        for key in self.playable_maps(owned_sets, {s for sets in home_sets for s in sets}):
            m = self.matchup_on_map(id_a, id_b, key)
            by_map[key] = [round(m["win_pct"]), m["games"], m["low_data"]]
            explain_maps[key] = rounded(self.explain_on_map(id_a, id_b, key))
        return {
            "suggested": [row(r) for r in self.suggested_maps(id_a, id_b, owned_sets, home_sets)],
            "favor_a": [row(r) for r in sugg["favor_a"]],
            "favor_b": [row(r) for r in sugg["favor_b"]],
            "by_map": by_map,
            "maps_considered": sugg["count"],
            "first": {"pct": round(first["win_pct"]), "games": first["games"], "low": first["low_data"]},
            "closeness": None if close is None else {
                "hp": round(close["winner_health"], 1), "games": close["games"], "low": close["low_data"]},
            "explain": {"maps": explain_maps, "first": rounded(self.explain_first_player(id_a, id_b)),
                        "closeness": rounded(self.explain_closeness(id_a, id_b))},
        }

    def map_info(self, keys):
        """Name, box, image and layout of these maps, for the map picker."""
        fields = ("name", "set", "thumb", "size", "zones", "spaces")
        return {k: {f: self.maps[k].get(f) for f in fields} for k in sorted(keys) if k in self.maps}
