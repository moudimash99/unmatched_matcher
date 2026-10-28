import random

import pytest

import insights
from matchup_engine import MatchupEngine


def _fighter(fid, sets, major="burst", minor=("combo",), rng="Melee"):
    return {"id": fid, "name": fid.title(), "sets": list(sets), "major": [major], "minor": list(minor), "range": rng}


@pytest.fixture
def fighters():
    return [
        _fighter("ace", ["Box A"]),
        _fighter("bea", ["Box A"], major="control"),
        _fighter("cal", ["Box B"], major="swarm", rng="Ranged"),
        _fighter("dee", ["Box B"], major="evasion"),
        _fighter("eve", ["Box C"], major="stance", minor=("technical",)),
    ]


@pytest.fixture
def engine(fighters):
    # ace is strong, eve is weak; cal-dee and bea-cal are fair; most pairs well tested
    win = {
        "ace": {"bea": 60.0, "cal": 65.0, "dee": 62.0, "eve": 80.0},
        "bea": {"cal": 50.0, "dee": 52.0, "eve": 70.0},
        "cal": {"dee": 49.0, "eve": 66.0},
        "dee": {"eve": 64.0},
    }
    games = {
        "ace": {"bea": 40, "cal": 40, "dee": 40, "eve": 40},
        "bea": {"cal": 40, "dee": 3, "eve": 40},
        "cal": {"dee": 40, "eve": 40},
        "dee": {"eve": 40},
    }
    return MatchupEngine(fighters, win, games)


def test_proven_fair_needs_band_and_games(engine):
    assert insights.is_proven_fair(engine, "cal", "dee")        # 49%, 40 games
    assert not insights.is_proven_fair(engine, "bea", "dee")    # 52% but only 3 games
    assert not insights.is_proven_fair(engine, "ace", "cal")    # 65% is outside the band


def test_fighter_matchups_and_best_worst(engine, fighters):
    ace = fighters[0]
    rows = insights.fighter_matchups(engine, ace, fighters)
    assert [r["opponent"]["id"] for r in rows][0] == "eve"
    best, worst = insights.best_and_worst(rows, n=2)
    assert [r["opponent"]["id"] for r in best] == ["eve", "cal"]
    assert [r["opponent"]["id"] for r in worst] == ["bea", "dee"]


def test_deck_summary_counts_copies_and_values():
    deck = [
        {"type": "attack", "value": 4, "copies": 3},
        {"type": "versatile", "value": 2, "copies": 2},
        {"type": "scheme", "value": None, "copies": 2},
    ]
    s = insights.deck_summary(deck)
    assert s["total"] == 7
    assert s["counts"]["attack"] == 3 and s["counts"]["scheme"] == 2
    assert s["value_counts"] == {2: 2, 3: 0, 4: 3}  # a gap shows as 0
    assert s["avg_value"] == pytest.approx((4 * 3 + 2 * 2) / 5)


def test_tier_list_orders_by_average(engine, fighters):
    rows = insights.tier_list(engine, fighters)
    assert rows[0]["fighter"]["id"] == "ace"
    assert rows[-1]["fighter"]["id"] == "eve"
    assert rows[0]["tier"] == "S" and rows[-1]["tier"] == "D"


def test_counter_picks_keep_the_candidate(engine, fighters):
    rows = insights.counter_picks(engine, fighters[0], fighters)
    assert all(r["opponent"]["id"] == "ace" for r in rows)
    assert rows[0]["fighter"]["id"] == "bea"  # 40% is the best anyone does vs ace


def test_buy_next_counts_what_a_set_adds(engine, fighters):
    prices = {"Box B": {"price": 20.0, "in_stock": True}, "Box C": {"price": 10.0, "in_stock": False}}
    rows = {r["set"]: r for r in insights.buy_next(engine, fighters, ["Box A"], prices)}
    assert set(rows) == {"Box B", "Box C"}

    b = rows["Box B"]
    assert [f["id"] for f in b["new_fighters"]] == ["cal", "dee"]
    assert b["new_matchups"] == 5            # cal & dee vs ace, bea, and each other
    assert b["new_fair"] == 2                # bea-cal 50%, cal-dee 49% (bea-dee has 3 games)
    assert b["new_ranges"] == ["Ranged"]
    assert b["fair_per_10"] == pytest.approx(1.0)

    in_stock = insights.sort_buy_rows(list(rows.values()), "fair", in_stock_only=True)
    assert [r["set"] for r in in_stock] == ["Box B"]


def test_game_night_prefers_fair_well_tested_groups(engine, fighters):
    result = insights.game_night(engine, fighters, 3, rng=random.Random(0))
    ids = {f["id"] for f in result["fighters"]}
    assert len(ids) == 3
    assert "eve" not in ids                   # loses badly to everyone
    assert len(result["games"]) == 3
    assert insights.game_night(engine, fighters, 6) is None


def test_teams_2v2_split_is_balanced(engine, fighters):
    result = insights.teams_2v2(engine, fighters, rng=random.Random(0))
    team_a = {f["id"] for f in result["team_a"]}
    team_b = {f["id"] for f in result["team_b"]}
    assert len(team_a | team_b) == 4 and not team_a & team_b
    assert abs(result["team_a_win_pct"] - 50.0) < 10.0
    assert len(result["cross"]) == 4


def test_rerolls_vary_and_avoid_the_last_fighters(engine, fighters):
    rng = random.Random(1)
    first = {f["id"] for f in insights.game_night(engine, fighters, 2, rng=rng)["fighters"]}
    seen = {frozenset(first)}
    prev = first
    for _ in range(8):
        r = insights.game_night(engine, fighters, 2, rng=rng, avoid=prev)
        prev = {f["id"] for f in r["fighters"]}
        seen.add(frozenset(prev))
    assert len(seen) > 1
    assert all("eve" not in g for g in seen)  # variety never brings in the lopsided fighter


def test_buy_rows_are_grouped_by_whether_you_can_buy_them(engine, fighters):
    prices = {"Box B": {"price": 20.0, "in_stock": True, "status": "in_stock"},
              "Box C": {"price": 10.0, "in_stock": False, "status": "not_released"}}
    groups = insights.group_buy_rows(insights.buy_next(engine, fighters, [], prices))
    assert [r["set"] for r in groups["buyable"]] == ["Box B"]
    assert [r["set"] for r in groups["not_released"]] == ["Box C"]
    assert [r["set"] for r in groups["not_sold"]] == ["Box A"]  # no store entry
    assert insights.stock_info({"in_stock": False})["label"] == "Sold out"  # older prices.json
    assert insights.stock_info(None)["status"] == "not_sold"
