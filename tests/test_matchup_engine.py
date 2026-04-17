import pytest

import random

from matchup_engine import MatchupEngine


@pytest.fixture
def sample_fighters():
    return [
        {"id": "alpha", "playstyles": ["aggressive"], "range": "Melee"},
        {"id": "bravo", "playstyles": ["defensive"], "range": "Reach"},
        {"id": "charlie", "playstyles": ["aggressive", "defensive"], "range": "Hybrid"},
    ]


@pytest.fixture
def sample_win_matrix():
    # Explicit and reversed lookups cover both matrix directions
    return {
        "alpha": {"bravo": 60.0},
        "bravo": {"charlie": 55.0},
    }


@pytest.fixture
def engine(sample_fighters, sample_win_matrix):
    return MatchupEngine(sample_fighters, sample_win_matrix)


@pytest.fixture
def seeded_random():
    random.seed(0)


def test_set_mode_adjusts_weights_and_clamps(engine):
    engine.set_mode("discovery")
    assert engine.WEIGHT_FAIRNESS == pytest.approx(0.3)
    assert engine.WEIGHT_FIT == pytest.approx(0.7)

    engine.set_mode("fairness")
    assert engine.WEIGHT_FAIRNESS == pytest.approx(0.7)
    assert engine.WEIGHT_FIT == pytest.approx(0.3)

    engine.set_mode("custom", "1.5")  # clamps to 1.0
    assert engine.WEIGHT_FAIRNESS == pytest.approx(1.0)
    assert engine.WEIGHT_FIT == pytest.approx(0.0)

    engine.set_mode("custom", "bad")  # falls back to defaults
    assert engine.WEIGHT_FAIRNESS == pytest.approx(0.4)
    assert engine.WEIGHT_FIT == pytest.approx(0.6)


def test_get_win_rate_returns_none_when_missing(engine):
    assert engine._get_win_rate("alpha", "unknown") is None


def test_get_win_rate_handles_reverse_lookup(engine):
    assert engine._get_win_rate("bravo", "alpha") == 40.0


def test_get_win_rate_handles_invalid_values(sample_fighters):
    sentinel_matrix = {"alpha": {"bravo": -2}}
    local_engine = MatchupEngine(sample_fighters, sentinel_matrix)
    assert local_engine._get_win_rate("alpha", "bravo") is None
    assert local_engine._get_win_rate("bravo", "alpha") is None


def test_calculate_matchup_fairness_is_minimum_when_missing(engine):
    assert engine._calculate_matchup_fairness("alpha", "unknown") == pytest.approx(0.0)


def test_calculate_matchup_fairness_penalizes_low_sample_size(sample_fighters):
    local_engine = MatchupEngine(
        sample_fighters,
        {"alpha": {"bravo": 60.0}},
        {"alpha": {"bravo": 2}},
    )

    # Base fairness for 60% is 0.8, then multiplied by 2/5 (games_played/5) due to low sample size.
    assert local_engine._calculate_matchup_fairness("alpha", "bravo") == pytest.approx(0.32)


def test_calculate_matchup_fairness_no_penalty_at_five_games(sample_fighters):
    local_engine = MatchupEngine(
        sample_fighters,
        {"alpha": {"bravo": 60.0}},
        {"alpha": {"bravo": 5}},
    )

    assert local_engine._calculate_matchup_fairness("alpha", "bravo") == pytest.approx(0.8)


def test_individual_fit_accounts_for_range_and_tags(engine, sample_fighters):
    alpha = sample_fighters[0]
    score_with_range = engine._calculate_individual_fit(alpha, {"aggressive"}, "Melee")
    assert score_with_range == pytest.approx(1.0)

    score_without_tags = engine._calculate_individual_fit(alpha, set(), None)
    assert score_without_tags == pytest.approx(0.5)


def test_recommend_opponents_ranks_by_fairness_and_fit(engine, sample_fighters):
    picks = engine.recommend_opponents(
        fighter=sample_fighters[0],
        available_fighters=sample_fighters,
        opponent_tags={"defensive"},
        opponent_range="Reach",
        quantity=2,
    )

    assert [p["id"] for p in picks] == ["bravo", "charlie"]


@pytest.fixture
def expanded_fighters():
    return [
        {"id": "alpha", "playstyles": ["aggressive"], "range": "Melee"},
        {"id": "bravo", "playstyles": ["defensive"], "range": "Reach"},
        {"id": "charlie", "playstyles": ["aggressive", "defensive"], "range": "Hybrid"},
        {"id": "delta", "playstyles": ["defensive"], "range": "Melee"},
        {"id": "echo", "playstyles": ["aggressive"], "range": "Reach"},
    ]


@pytest.fixture
def expanded_win_matrix(expanded_fighters):
    # Favor alpha over defensive, ensure non-symmetric entries exist
    return {
        "alpha": {"bravo": 65.0, "delta": 60.0},
        "bravo": {"alpha": 35.0, "charlie": 55.0},
        "charlie": {"delta": 52.0},
        # missing entries are treated as unknown by _get_win_rate
    }


@pytest.fixture
def expanded_engine(expanded_fighters, expanded_win_matrix):
    return MatchupEngine(expanded_fighters, expanded_win_matrix)


def test_generate_batch_respects_repeat_limits(expanded_engine, expanded_fighters, seeded_random):
    quantity = 8
    batch = expanded_engine.generate_batch(
        expanded_fighters, {"aggressive"}, {"defensive"}, p1_range="Any", opp_range="Any", quantity=quantity
    )

    assert len(batch) == quantity
    p1_counts = {}
    opp_counts = {}
    for item in batch:
        p1_counts[item["p1"]["id"]] = p1_counts.get(item["p1"]["id"], 0) + 1
        opp_counts[item["opp"]["id"]] = opp_counts.get(item["opp"]["id"], 0) + 1

    assert all(count <= 3 for count in p1_counts.values())
    assert all(count <= 3 for count in opp_counts.values())


def test_generate_fair_pools_with_two_fighters_and_invalid_rate():
    fighters = [
        {"id": "a", "range": "Melee", "major": [], "minor": []},
        {"id": "b", "range": "Melee", "major": [], "minor": []},
    ]
    engine = MatchupEngine(fighters, {"a": {"b": -2}})

    result = engine.generate_fair_pools(fighters, p1_tags=set(), opp_tags=set())

    assert result is not None
    p1_ids = {f["id"] for f in result["p1_pool"]}
    opp_ids = {f["id"] for f in result["opp_pool"]}
    assert len(p1_ids) == 1
    assert len(opp_ids) == 1
    assert p1_ids != opp_ids
    assert p1_ids.union(opp_ids) == {"a", "b"}


def test_generate_fair_pools_returns_highest_fit(expanded_engine, expanded_fighters):
    # Reduce pool sizes to keep the test fast while exercising combination scoring
    expanded_engine.P1_POOL_SIZE = 2
    expanded_engine.OPP_POOL_SIZE = 2

    result = expanded_engine.generate_fair_pools(
        expanded_fighters,
        p1_tags={"aggressive"},
        opp_tags={"defensive"},
        p1_range="Melee",
        opp_range="Reach",
    )

    assert result is not None
    p1_ids = [f["id"] for f in result["p1_pool"]]
    opp_ids = [f["id"] for f in result["opp_pool"]]

    # Highest aggressive fit with Melee preference should lead
    assert set(p1_ids) == {"alpha", "echo"}
    assert p1_ids[0] == "alpha"

    # Now considers both fitness and fairness with weights (0.6 fit, 0.4 fairness)
    # The pool with bravo+charlie has better overall fairness, outweighing slightly lower fitness
    assert set(opp_ids) == {"bravo", "charlie"}
    assert opp_ids[0] == "bravo"


# ==========================================
# THEME FILTERING TESTS
# ==========================================

@pytest.fixture
def themed_fighters():
    return [
        {"id": "hero_a", "name": "Hero A", "set": "Heroes", "themes": ["superhero"], "range": "Melee", "major": [], "minor": []},
        {"id": "monster_a", "name": "Monster A", "set": "Monsters", "themes": ["halloween", "monster"], "range": "Melee", "major": [], "minor": []},
        {"id": "legend_a", "name": "Legend A", "set": "Legends", "themes": ["legend"], "range": "Melee", "major": [], "minor": []},
        {"id": "multi_a", "name": "Multi A", "set": "Heroes", "themes": ["superhero", "halloween"], "range": "Melee", "major": [], "minor": []},
    ]


def _filter_by_themes(fighters, theme_filter):
    """Mirrors the logic in app.get_available_fighters for theme filtering."""
    if not theme_filter:
        return fighters
    return [f for f in fighters if any(t in theme_filter for t in f.get("themes", []))]


def test_theme_filter_returns_only_matching_fighters(themed_fighters):
    result = _filter_by_themes(themed_fighters, ["halloween"])
    ids = [f["id"] for f in result]
    assert "monster_a" in ids
    assert "multi_a" in ids
    assert "hero_a" not in ids
    assert "legend_a" not in ids


def test_theme_filter_multiple_themes(themed_fighters):
    result = _filter_by_themes(themed_fighters, ["superhero", "legend"])
    ids = [f["id"] for f in result]
    assert "hero_a" in ids
    assert "legend_a" in ids
    assert "multi_a" in ids  # has superhero
    assert "monster_a" not in ids


def test_theme_filter_empty_returns_all(themed_fighters):
    result = _filter_by_themes(themed_fighters, [])
    assert len(result) == len(themed_fighters)


def test_theme_filter_no_matches_returns_empty(themed_fighters):
    result = _filter_by_themes(themed_fighters, ["witcher"])
    assert result == []
