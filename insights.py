"""
Collection-level insights built on MatchupEngine: fighter profiles, tier lists,
counter-picks, what to buy next, and game-night / 2v2 assignments.

All win rates are the engine's confidence-weighted estimates, and every
"fair" judgement uses its confidence-scaled fairness, so thinly tested
matchups never look better than proven ones.
"""
import itertools
import random

from matchup_engine import FULL_CONFIDENCE_GAMES

# A matchup counts as fair when its estimate is within this many points of 50%
FAIR_BAND = 10.0

# Tier thresholds on a fighter's average estimated win rate within a collection
TIERS = [("S", 56.0), ("A", 53.0), ("B", 50.0), ("C", 47.0), ("D", 0.0)]


def matchup_row(engine, fighter, opponent):
    """One matchup from fighter's side: estimate, games, confidence."""
    games = engine.games_played(fighter["id"], opponent["id"])
    return {
        "opponent": opponent,
        "win_pct": engine.estimate_win_rate(fighter["id"], opponent["id"]),
        "games": games,
        "confidence": engine.confidence(games),
    }


def is_proven_fair(engine, id_a, id_b):
    """Fair (within FAIR_BAND of 50%) and backed by FULL_CONFIDENCE_GAMES games."""
    games = engine.games_played(id_a, id_b)
    solid = games is None or games >= FULL_CONFIDENCE_GAMES
    return solid and abs(engine.estimate_win_rate(id_a, id_b) - 50.0) <= FAIR_BAND


# ---------------------------------------------------------------------------
# Fighter profile
# ---------------------------------------------------------------------------

def fighter_matchups(engine, fighter, fighters):
    """All of a fighter's matchups, strongest first."""
    rows = [matchup_row(engine, fighter, opp) for opp in fighters if opp["id"] != fighter["id"]]
    return sorted(rows, key=lambda r: r["win_pct"], reverse=True)


def best_and_worst(rows, n=5):
    """Top/bottom n matchups among those with full confidence."""
    solid = [r for r in rows if r["confidence"] >= 1.0]
    return solid[:n], list(reversed(solid[-n:])) if solid else []


def deck_summary(deck):
    """Card counts per type and the value spread of attack/defense-capable cards."""
    counts = {"attack": 0, "defense": 0, "versatile": 0, "scheme": 0}
    values = {}
    for card in deck:
        counts[card["type"]] = counts.get(card["type"], 0) + card["copies"]
        if card["type"] != "scheme" and card["value"] is not None:
            values[card["value"]] = values.get(card["value"], 0) + card["copies"]
    total = sum(counts.values())
    weighted = sum(v * n for v, n in values.items())
    combat = sum(values.values())
    return {
        "total": total,
        "counts": counts,
        "value_counts": dict(sorted(values.items())),
        "avg_value": weighted / combat if combat else None,
    }


# ---------------------------------------------------------------------------
# Tier list, counter-picks
# ---------------------------------------------------------------------------

def tier_for(avg):
    return next(letter for letter, floor in TIERS if avg >= floor)


def tier_list(engine, fighters):
    """Ranks fighters by their average estimated win rate against the rest of the list."""
    rows = []
    for f in fighters:
        others = [o for o in fighters if o["id"] != f["id"]]
        if not others:
            continue
        rates = [engine.estimate_win_rate(f["id"], o["id"]) for o in others]
        proven = sum(1 for o in others if (engine.games_played(f["id"], o["id"]) or 0) >= FULL_CONFIDENCE_GAMES)
        avg = sum(rates) / len(rates)
        rows.append({"fighter": f, "avg": avg, "tier": tier_for(avg), "proven": proven, "opponents": len(others)})
    return sorted(rows, key=lambda r: r["avg"], reverse=True)


def counter_picks(engine, target, candidates):
    """Candidates ranked by estimated win rate against the target (row["fighter"] = the candidate)."""
    rows = [matchup_row(engine, c, target) | {"fighter": c} for c in candidates if c["id"] != target["id"]]
    return sorted(rows, key=lambda r: (r["win_pct"], r["games"] or 0), reverse=True)


# ---------------------------------------------------------------------------
# What to buy next
# ---------------------------------------------------------------------------

def buy_next(engine, fighters, owned_sets, prices):
    """
    For every set not owned: what it adds to the collection.

    new_fair     proven-fair matchups gained (involving a new fighter)
    new_matchups all matchups gained
    new_styles   playstyles the collection doesn't cover yet
    new_ranges   ranges the collection doesn't cover yet
    """
    owned_sets = set(owned_sets)
    owned = [f for f in fighters if set(f["sets"]) & owned_sets]
    owned_ids = {f["id"] for f in owned}
    owned_styles = {t for f in owned for t in f["major"] + f["minor"]}
    owned_ranges = {f["range"] for f in owned}

    all_sets = sorted({s for f in fighters for s in f["sets"]})
    rows = []
    for set_name in all_sets:
        if set_name in owned_sets:
            continue
        new = [f for f in fighters if set_name in f["sets"] and f["id"] not in owned_ids]
        pool = owned + new
        new_ids = {f["id"] for f in new}
        pairs = [(a, b) for a, b in itertools.combinations(pool, 2) if a["id"] in new_ids or b["id"] in new_ids]
        new_fair = sum(1 for a, b in pairs if is_proven_fair(engine, a["id"], b["id"]))
        price = prices.get(set_name)
        rows.append({
            "set": set_name,
            "new_fighters": new,
            "new_matchups": len(pairs),
            "new_fair": new_fair,
            "new_styles": sorted({t for f in new for t in f["major"] + f["minor"]} - owned_styles),
            "new_ranges": sorted({f["range"] for f in new} - owned_ranges),
            "price": price,
            "fair_per_10": (new_fair / price["price"] * 10) if price and price["price"] else None,
        })
    return rows


BUY_SORTS = {
    "fair": lambda r: (r["new_fair"], len(r["new_styles"])),
    "value": lambda r: (r["fair_per_10"] or -1, r["new_fair"]),
    "variety": lambda r: (len(r["new_styles"]) + len(r["new_ranges"]), r["new_fair"]),
    "price": lambda r: (-(r["price"]["price"] if r["price"] else 1e9), r["new_fair"]),
}


def sort_buy_rows(rows, sort="fair", in_stock_only=False):
    if in_stock_only:
        rows = [r for r in rows if r["price"] and r["price"]["in_stock"]]
    return sorted(rows, key=BUY_SORTS.get(sort, BUY_SORTS["fair"]), reverse=True)


# ---------------------------------------------------------------------------
# Game night: N players, everyone vs everyone, all games as fair as possible
# ---------------------------------------------------------------------------

def _fairness(engine, a, b):
    return engine._calculate_matchup_fairness(a, b)


def _group_score(engine, ids):
    pairs = list(itertools.combinations(ids, 2))
    return sum(_fairness(engine, a, b) for a, b in pairs) / len(pairs)


def game_night(engine, fighters, players, rng=None, restarts=12):
    """
    Picks `players` distinct fighters whose round-robin matchups are as fair
    (and well tested) as possible. Local search from random starts; the best
    few groups are sampled so rerolls give variety.
    """
    rng = rng or random.Random()
    ids = [f["id"] for f in fighters]
    if len(ids) < players or players < 2:
        return None

    found = {}
    for _ in range(restarts):
        group = rng.sample(ids, players)
        score = _group_score(engine, group)
        improved = True
        while improved:
            improved = False
            for i in range(players):
                for cand in ids:
                    if cand in group:
                        continue
                    trial = group[:i] + [cand] + group[i + 1:]
                    s = _group_score(engine, trial)
                    if s > score + 1e-9:
                        group, score, improved = trial, s, True
        found[frozenset(group)] = score

    best = sorted(found.items(), key=lambda kv: kv[1], reverse=True)[:3]
    group, score = rng.choice(best)
    by_id = {f["id"]: f for f in fighters}
    picked = [by_id[i] for i in group]
    rng.shuffle(picked)
    games = [matchup_row(engine, a, b) | {"fighter": a} for a, b in itertools.combinations(picked, 2)]
    return {"fighters": picked, "score": score, "games": games}


def teams_2v2(engine, fighters, rng=None, restarts=12):
    """
    Two teams of two whose cross matchups average closest to 50%, preferring
    well-tested matchups. Team win estimate = mean of the four cross matchups.
    """
    rng = rng or random.Random()
    ids = [f["id"] for f in fighters]
    if len(ids) < 4:
        return None

    def split_score(a1, a2, b1, b2):
        cross = [(a1, b1), (a1, b2), (a2, b1), (a2, b2)]
        est = sum(engine.estimate_win_rate(x, y) for x, y in cross) / 4
        conf = sum(engine.confidence(engine.games_played(x, y)) for x, y in cross) / 4
        return (1.0 - abs(est - 50.0) / 50.0) * conf, est

    def best_split(four):
        a, b, c, d = four
        options = [((a, b), (c, d)), ((a, c), (b, d)), ((a, d), (b, c))]
        return max(((split_score(*t1, *t2)[0], t1, t2) for t1, t2 in options), key=lambda x: x[0])

    found = {}
    for _ in range(restarts):
        four = rng.sample(ids, 4)
        score, t1, t2 = best_split(four)
        improved = True
        while improved:
            improved = False
            for i in range(4):
                for cand in ids:
                    if cand in four:
                        continue
                    trial = four[:i] + [cand] + four[i + 1:]
                    s, u1, u2 = best_split(trial)
                    if s > score + 1e-9:
                        four, score, t1, t2, improved = trial, s, u1, u2, True
        found[frozenset(four)] = (score, t1, t2)

    best = sorted(found.values(), key=lambda v: v[0], reverse=True)[:3]
    score, t1, t2 = rng.choice(best)
    by_id = {f["id"]: f for f in fighters}
    _, est = split_score(*t1, *t2)
    return {
        "team_a": [by_id[i] for i in t1],
        "team_b": [by_id[i] for i in t2],
        "team_a_win_pct": est,
        "score": score,
        "cross": [matchup_row(engine, by_id[x], by_id[y]) | {"fighter": by_id[x]} for x in t1 for y in t2],
    }
