import pytest

import random

from matchup_engine import MatchupEngine


@pytest.fixture
def sample_fighters():
    return [
        {"id": "alpha", "major": ["aggressive"], "minor": [], "range": "Melee"},
        {"id": "bravo", "major": ["defensive"], "minor": [], "range": "Reach"},
        {"id": "charlie", "major": ["aggressive", "defensive"], "minor": [], "range": "Hybrid"},
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


def test_get_win_rate_defaults_to_even_when_missing(engine):
    assert engine._get_win_rate("alpha", "unknown") == 50.0


def test_get_win_rate_handles_reverse_lookup(engine):
    assert engine._get_win_rate("bravo", "alpha") == 40.0


def test_get_win_rate_ignores_sentinel_and_falls_back():
    """A -2 sentinel in the matrix should be treated as 'no data' (return 50.0)."""
    fighters = [{"id": "x", "major": [], "minor": [], "range": "Melee"},
                {"id": "y", "major": [], "minor": [], "range": "Melee"}]
    matrix_with_sentinel = {"x": {"y": -2}}
    eng = MatchupEngine(fighters, matrix_with_sentinel)
    assert eng._get_win_rate("x", "y") == 50.0
    assert eng._get_win_rate("y", "x") == 50.0


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
        {"id": "alpha", "major": ["aggressive"], "minor": [], "range": "Melee"},
        {"id": "bravo", "major": ["defensive"], "minor": [], "range": "Reach"},
        {"id": "charlie", "major": ["aggressive", "defensive"], "minor": [], "range": "Hybrid"},
        {"id": "delta", "major": ["defensive"], "minor": [], "range": "Melee"},
        {"id": "echo", "major": ["aggressive"], "minor": [], "range": "Reach"},
    ]


@pytest.fixture
def expanded_win_matrix(expanded_fighters):
    # Favor alpha over defensive, ensure non-symmetric entries exist
    return {
        "alpha": {"bravo": 65.0, "delta": 60.0},
        "bravo": {"alpha": 35.0, "charlie": 55.0},
        "charlie": {"delta": 52.0},
        # missing entries default to 50 via _get_win_rate
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

    # With strict 40-60% fairness, bravo is excluded (alpha beats bravo 65% of the time).
    # The best valid opp pool is charlie+delta: delta has higher fit, charlie has perfect fairness.
    assert set(opp_ids) == {"charlie", "delta"}
    assert opp_ids[0] == "delta"
