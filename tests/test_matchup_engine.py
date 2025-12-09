import pytest

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


def test_get_win_rate_defaults_to_even_when_missing(engine):
    assert engine._get_win_rate("alpha", "unknown") == 50.0


def test_get_win_rate_handles_reverse_lookup(engine):
    assert engine._get_win_rate("bravo", "alpha") == 40.0


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
