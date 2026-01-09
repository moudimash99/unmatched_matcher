"""
Test to ensure no positional bias in fighter selection.
This test verifies that the generate_fair_pools method doesn't favor
fighters that appear earlier in the input list.
"""
import pytest
import random
from collections import Counter
from matchup_engine import MatchupEngine


@pytest.fixture
def many_similar_fighters():
    """
    Create a list of fighters where many have identical scores
    to test for positional bias.
    """
    fighters = []
    # Create 30 fighters with identical playstyles and ranges
    # This ensures they'll have identical fit scores
    for i in range(30):
        fighters.append({
            "id": f"fighter_{i}",
            "name": f"Fighter {i}",
            "set": f"Set {i // 5}",  # 5 fighters per set
            "playstyles": ["aggressive", "defensive"],
            "range": "Melee"
        })
    return fighters


@pytest.fixture
def empty_win_matrix():
    """Empty win matrix - all matchups default to 50%"""
    return {}


@pytest.fixture
def bias_test_engine(many_similar_fighters, empty_win_matrix):
    """Engine for testing positional bias"""
    return MatchupEngine(many_similar_fighters, empty_win_matrix)


def test_no_early_position_bias_in_fair_pools(bias_test_engine, many_similar_fighters):
    """
    Verify that fighters appearing earlier in the list are not
    disproportionately selected when scores are identical.
    
    With proper shuffling, fighters from all positions should have
    roughly equal chance of being selected as the main recommendation.
    """
    # Run the generation multiple times and track which positions appear
    first_p1_positions = []
    first_opp_positions = []
    
    num_runs = 100
    for i in range(num_runs):
        random.seed(i)  # Different seed each time
        result = bias_test_engine.generate_fair_pools(
            many_similar_fighters,
            p1_tags={'aggressive'},
            opp_tags={'defensive'},
            p1_range='Melee',
            opp_range='Melee'
        )
        
        if result and result['p1_pool'] and result['opp_pool']:
            # Find the position of the first P1 fighter in the original list
            first_p1_id = result['p1_pool'][0]['id']
            p1_position = int(first_p1_id.split('_')[1])
            first_p1_positions.append(p1_position)
            
            # Find the position of the first Opp fighter
            first_opp_id = result['opp_pool'][0]['id']
            opp_position = int(first_opp_id.split('_')[1])
            first_opp_positions.append(opp_position)
    
    # Analyze the distribution
    # We want to ensure early positions (0-9) don't dominate
    p1_early_count = sum(1 for pos in first_p1_positions if pos < 10)
    opp_early_count = sum(1 for pos in first_opp_positions if pos < 10)
    
    total_runs = len(first_p1_positions)
    
    # With no bias, roughly 1/3 of selections should be from positions 0-9
    # We allow some variance but check that it's not heavily biased (> 60%)
    p1_early_ratio = p1_early_count / total_runs if total_runs > 0 else 0
    opp_early_ratio = opp_early_count / total_runs if total_runs > 0 else 0
    
    # Assert that early positions don't appear more than 60% of the time
    # (which would indicate bias)
    assert p1_early_ratio < 0.6, (
        f"P1 selection shows bias towards early positions: "
        f"{p1_early_ratio:.1%} from positions 0-9"
    )
    assert opp_early_ratio < 0.6, (
        f"Opponent selection shows bias towards early positions: "
        f"{opp_early_ratio:.1%} from positions 0-9"
    )
    
    # Also verify we're getting good spread across different positions
    unique_p1_positions = len(set(first_p1_positions))
    unique_opp_positions = len(set(first_opp_positions))
    
    # With 100 runs and 30 fighters, we should see at least 10 different positions
    assert unique_p1_positions >= 10, (
        f"P1 selection shows limited diversity: only {unique_p1_positions} "
        f"unique positions selected"
    )
    assert unique_opp_positions >= 10, (
        f"Opponent selection shows limited diversity: only {unique_opp_positions} "
        f"unique positions selected"
    )


def test_fair_pools_with_varied_scores_still_selects_best():
    """
    Verify that when scores differ, the highest scoring fighters
    are still preferred (not just random selection).
    """
    # Create fighters with explicitly different scores
    # Need enough fighters for the pool sizes (at least 12 for elite selection)
    varied_fighters = []
    
    # Add 5 low-scoring fighters
    for i in range(5):
        varied_fighters.append({
            "id": f"low_{i}",
            "name": f"Low {i}",
            "set": f"Set Low {i}",
            "playstyles": [],
            "range": "Ranged"
        })
    
    # Add 10 high-scoring fighters
    for i in range(10):
        varied_fighters.append({
            "id": f"high_{i}",
            "name": f"High {i}",
            "set": f"Set High {i}",
            "playstyles": ["aggressive", "defensive"],
            "range": "Melee"
        })
    
    # Create engine with these fighters
    engine = MatchupEngine(varied_fighters, {})
    
    # Track selections across multiple runs
    selected_ids = []
    for i in range(20):
        random.seed(i)
        result = engine.generate_fair_pools(
            varied_fighters,
            p1_tags={'aggressive', 'defensive'},
            opp_tags={'aggressive'},
            p1_range='Melee',
            opp_range='Any'
        )
        
        if result and result['p1_pool']:
            selected_ids.extend([f['id'] for f in result['p1_pool']])
    
    # High-scoring fighters should appear more frequently than low-scoring ones
    id_counts = Counter(selected_ids)
    high_count = sum(id_counts.get(f"high_{i}", 0) for i in range(10))
    low_count = sum(id_counts.get(f"low_{i}", 0) for i in range(5))
    
    # High-scoring fighters should be selected significantly more often
    # Since there are 10 high vs 5 low, and high scores better, 
    # we expect at least 3x as many selections
    assert high_count > low_count * 3, (
        f"High-scoring fighters should dominate selection, but got "
        f"high={high_count}, low={low_count}"
    )
