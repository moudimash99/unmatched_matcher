import random
from itertools import combinations
from collections import defaultdict
def _pick_weighted_elite(score_list, k):
    """
    Selects up to k distinct fighters from score_list using
    weighted random sampling across the full list (no window).
    score_list items are dicts: {'id', 'score', 'obj'}.
    """
    # Work on a shallow copy so we don't mutate the original
    pool = list(score_list)
    elite = []
    used_ids = set()

    # Safety: if fewer fighters than k, just adapt
    max_picks = min(k, len(pool))

    for _ in range(max_picks):
        # Filter out already picked fighters
        candidates = [item for item in pool if item['id'] not in used_ids]
        if not candidates:
            break

        # Ensure non-negative weights (in case of odd scores)
        weights = [max(item['score'], 0.0) for item in candidates]

        # If all weights are zero, fall back to uniform
        if all(w == 0 for w in weights):
            chosen = random.choice(candidates)
        else:
            chosen = random.choices(candidates, weights=weights, k=1)[0]

        elite.append(chosen)
        used_ids.add(chosen['id'])

    return elite


class MatchupEngine:



    def __init__(self, fighters_db, win_rate_matrix):
        self.fighters_db = fighters_db
        self.win_rate_matrix = win_rate_matrix
        self.WEIGHT_FIT = 0.6
        self.WEIGHT_FAIRNESS = 0.4

        self.P1_POOL_SIZE = 4
        self.OPP_POOL_SIZE = 3
        
        # PRE-CALCULATION: Build the Fairness Map immediately (O(1) lookups later)
        # Maps FighterID -> Set of IDs they are fair against (40-60%)
        self.fairness_map = self._build_fairness_map()

        # RANGE SCALE MAPPING
        # Maps descriptive strings to the 1-5 scale for calculation.
        self.RANGE_INPUT_MAP = {
            "Melee": 1,
            "1": 1,
            1: 1,
            
            "Reach": 2,
            "2": 2,
            2: 2,
            
            "Hybrid": 3,
            "3": 3,
            3: 3,
            
            "Ranged Assist": 4,
            "4": 4,
            4: 4,
            
            "Ranged": 5,
            "5": 5,
            5: 5,
            
            "Any": None,
            "": None
        }

    def set_mode(self, mode, custom_fairness_weight=None):
        """
        Adjusts the relative weight of fairness vs fit.

        mode:
          - "discovery": prioritize fit / variety
          - "fairness":  prioritize balanced win rates
          - "custom":    use custom_fairness_weight in [0, 1]
        """
        mode = (mode or "").lower()

        if mode == "discovery":
            self.WEIGHT_FAIRNESS = 0.3
            self.WEIGHT_FIT = 0.7

        elif mode == "fairness":
            self.WEIGHT_FAIRNESS = 0.7
            self.WEIGHT_FIT = 0.3

        elif mode == "custom" and custom_fairness_weight not in (None, ""):
            try:
                w = float(custom_fairness_weight)
            except (TypeError, ValueError):
                w = 0.4  # fallback

            # clamp to [0, 1]
            w = max(0.0, min(1.0, w))
            self.WEIGHT_FAIRNESS = w
            self.WEIGHT_FIT = 1.0 - w

        else:
            # default behaviour
            self.WEIGHT_FAIRNESS = 0.4
            self.WEIGHT_FIT = 0.6

    def _get_win_rate(self, id_a, id_b):
        """
        Safely gets win rate from matrix (A vs B or B vs A). 
        Defaults to 50.0 (percent) if no data exists.
        This treats unknown matchups as 'Fair' (Benefit of the doubt).
        """
        if id_a in self.win_rate_matrix and id_b in self.win_rate_matrix[id_a]:
            return self.win_rate_matrix[id_a][id_b]
        if id_b in self.win_rate_matrix and id_a in self.win_rate_matrix[id_b]:
            return 100.0 - self.win_rate_matrix[id_b][id_a]
        return 50.0 # Default to fair if unknown

    def _build_fairness_map(self):
        """Generates the static map for the Fair Pool algorithm."""
        fair_map = defaultdict(set)
        all_ids = [f['id'] for f in self.fighters_db]
        
        for id_a in all_ids:
            for id_b in all_ids:
                if id_a == id_b: continue
                
                wr = self._get_win_rate(id_a, id_b)
                # Strict Fairness Definition for Pools (40% - 60%)
                if 1 <= wr <= 99:
                    fair_map[id_a].add(id_b)
        return fair_map

    def _calculate_individual_fit(self, fighter, requested_tags, range_pref=None):
        """
        Scores how well a fighter matches the requested playstyles AND range.
        
        Scoring Components:
        - Major playstyles: weighted 1.7x
        - Minor playstyles: weighted 1.0x
        - match_ratio (40% of tag score): Fighter's tag coverage
        - coverage_score (60% of tag score): Requested tag satisfaction
        - range_score: If range_pref provided, weighted 60% with tag_score at 40%
        
        Returns:
            float: Score between 0.0 and 1.0, higher is better match
        """
        # 1. TAG SCORE with Major/Minor weighting
        tag_score = 0.5 # Default neutral if no tags
        if requested_tags:
            # Extract major and minor playstyles from fighter
            major_tags = set(fighter.get('major', []))
            minor_tags = set(fighter.get('minor', []))
            
            if major_tags or minor_tags:
                # Calculate weighted matches
                # Major matches are worth 1.7x minor matches
                MAJOR_WEIGHT = 1.7
                MINOR_WEIGHT = 1.0
                
                major_matches = major_tags.intersection(requested_tags)
                minor_matches = minor_tags.intersection(requested_tags)
                
                weighted_matches = (len(major_matches) * MAJOR_WEIGHT + 
                                  len(minor_matches) * MINOR_WEIGHT)
                
                # Total possible weighted playstyles the fighter has
                total_weighted = (len(major_tags) * MAJOR_WEIGHT + 
                                len(minor_tags) * MINOR_WEIGHT)
                
                # Total requested tags (treat as if all were major for coverage comparison)
                total_requested_weighted = len(requested_tags) * MAJOR_WEIGHT
                
                if total_weighted > 0 and total_requested_weighted > 0:
                    # Match ratio: what fraction of the fighter's weighted tags match
                    match_ratio = weighted_matches / total_weighted
                    # Coverage score: what fraction of requested tags are covered (weighted)
                    # This ensures major matches contribute more to coverage
                    coverage_score = weighted_matches / total_requested_weighted
                    tag_score = (0.4 * match_ratio) + (0.6 * coverage_score)
                else:
                    tag_score = 0.0
            else:
                tag_score = 0.0

        # 2. RANGE SCORE (If preference exists)
        if not range_pref or range_pref == "Any" or range_pref == "":
            return tag_score # Only consider tags if no range pref
        
        # Parse User Preference (Handle both int and string inputs)
        p_val = self.RANGE_INPUT_MAP.get(range_pref, 1)
        
        # Get Fighter Range (Now an Integer in JSON, but safer to parse)
        f_raw = fighter.get('range', 1)
        f_val = self.RANGE_INPUT_MAP.get(f_raw, 1)
        
        # Calculate Proximity (Closer is better)
        # Max distance is 4 (5 - 1). 
        distance = abs(f_val - p_val)
        range_score = 1.0 - (distance / 4.0)

        # 3. COMBINED SCORE
        # We weight Range heavily (50%) to ensure it acts as a soft filter
        return (0.4 * tag_score) + (0.6 * range_score)

    def recommend_opponents(self, fighter, available_fighters, opponent_tags, opponent_range=None, quantity=5):
        """
        Recommends opponents for a given fighter based on opponent tags and range.
        Returns a list of fighter objects ranked by fairness and tag fit.
        """
        # Score all available fighters as potential opponents
        candidates = []
        for opp in available_fighters:
            if opp['id'] == fighter['id']:
                continue
            
            # Fairness score
            win_rate = self._get_win_rate(fighter['id'], opp['id'])
            dist_from_50 = abs(win_rate - 50.0)
            fairness = 1.0 - (dist_from_50 / 50.0)
            
            # Opponent tag and range fit
            tag_fit = self._calculate_individual_fit(opp, opponent_tags, opponent_range)
            
            # Combined score
            score = (self.WEIGHT_FAIRNESS * fairness) + (self.WEIGHT_FIT * tag_fit)
            
            candidates.append({
                'fighter': opp,
                'score': score,
                'win_rate': win_rate
            })
        
        # Sort by score and return top fighters
        candidates.sort(key=lambda x: x['score'], reverse=True)
        return [c['fighter'] for c in candidates[:quantity]]

    def _score_pair(self, p1_fighter, opp_fighter, p1_tags, opp_tags, p1_range=None, opp_range=None):
        """Scores a specific pairing on both Fit and Fairness."""
        # 1. Dual Fit Score (Now includes Range)
        score_p1 = self._calculate_individual_fit(p1_fighter, p1_tags, p1_range)
        score_opp = self._calculate_individual_fit(opp_fighter, opp_tags, opp_range)
        dual_fit = (score_p1 + score_opp) / 2.0

        # 2. Fairness Score (Target 50%)
        win_rate = self._get_win_rate(p1_fighter['id'], opp_fighter['id'])
        dist_from_50 = abs(win_rate - 50.0)
        fairness = 1.0 - (dist_from_50 / 50.0)

        total_score = (self.WEIGHT_FIT * dual_fit) + (self.WEIGHT_FAIRNESS * fairness)
        return total_score, win_rate

    # ==========================================
    # FEATURE 1: 1v1 MATCHUP BATCH GENERATION
    # ==========================================
    def generate_batch(self, available_fighters, p1_tags, opp_tags, p1_range=None, opp_range=None, quantity=10):
        """
        Generates a batch of matchups using Weighted Random Selection 
        and Frequency Capping. Matches both Tags and Range.
        """
        # 1. Pre-calculate score for EVERY valid pair
        all_candidates = []
        for f_a in available_fighters:
            for f_b in available_fighters:
                if f_a['id'] == f_b['id']: continue
                
                score, wr = self._score_pair(f_a, f_b, p1_tags, opp_tags, p1_range, opp_range)
                all_candidates.append({
                    'p1': f_a, 
                    'opp': f_b, 
                    'score': score, 
                    'win_rate': wr
                })
        
        # Sort master list by score once (High -> Low)
        all_candidates.sort(key=lambda x: x['score'], reverse=True)

        results = []
        batch_p1_counts = defaultdict(int)
        batch_opp_counts = defaultdict(int)
        MAX_REPEATS = 3

        # 2. Iterative Selection Loop
        for _ in range(quantity):
            # A. Filter: Remove pairs where a fighter is 'maxed out' in this batch
            valid_candidates = []
            for c in all_candidates:
                if (batch_p1_counts[c['p1']['id']] < MAX_REPEATS and 
                    batch_opp_counts[c['opp']['id']] < MAX_REPEATS):
                    valid_candidates.append(c)
            
            if not valid_candidates:
                break # Ran out of valid options
            
            # B. Top-N Ranking: Take top 10 from the filtered list
            top_10 = valid_candidates[:10]
            
            # C. Weighted Random Selection
            weights = [item['score'] for item in top_10]
            # random.choices returns a list, we need the first item
            selection = random.choices(top_10, weights=weights, k=1)[0]
            
            # D. Update Batch Counts & Add to results
            batch_p1_counts[selection['p1']['id']] += 1
            batch_opp_counts[selection['opp']['id']] += 1
            results.append(selection)

        return results

    # ==========================================
    # FEATURE 2: FAIR PLAY POOLS (4v4)
    # ==========================================
    
    def _calculate_matchup_fairness(self, fighter_id, opponent_id):
        """
        Calculate fairness score for a single matchup.
        
        Fairness is measured as proximity to 50% win rate (1.0 = perfectly fair).
        """
        win_rate = self._get_win_rate(fighter_id, opponent_id)
        dist_from_50 = abs(win_rate - 50.0)
        return 1.0 - (dist_from_50 / 50.0)
    
    def _calculate_pool_fitness(self, pool_a_ids, pool_b_ids, p1_score_map, opp_score_map, pool_a_size, pool_b_size):
        """
        Calculate the average fitness score for two pools.
        
        Returns the combined average fitness of both pools.
        """
        p1_fit = sum(p1_score_map[i] for i in pool_a_ids) 
        opp_fit = sum(opp_score_map[i] for i in pool_b_ids)
        return (p1_fit + opp_fit) / (pool_a_size + pool_b_size)
    
    def _calculate_pool_fairness(self, pool_a_ids, pool_b_ids):
        """
        Calculate the average fairness score across all matchups between two pools.
        
        Fairness is measured as proximity to 50% win rate (1.0 = perfectly fair).
        """
        fairness_scores = [
            self._calculate_matchup_fairness(p1_id, opp_id)
            for p1_id in pool_a_ids
            for opp_id in pool_b_ids
        ]
        return sum(fairness_scores) / len(fairness_scores)
    
    def _calculate_fighter_total_score(self, fighter, pool_type, score_map, pool_ids):
        """
        Calculate total score for a single fighter considering both fit and fairness.
        
        Args:
            fighter: The fighter object
            pool_type: 'p1' or 'opp' to determine which pool this fighter belongs to
            score_map: Dictionary mapping fighter IDs to their fit scores
            pool_ids: IDs of fighters in the opposite pool
            
        Returns the weighted combination of fitness and average fairness against the opposite pool.
        """
        fit_score = score_map[fighter['id']]
        
        # Calculate average fairness against all fighters in the opposite pool
        fairness_scores = [
            self._calculate_matchup_fairness(fighter['id'], opp_id)
            for opp_id in pool_ids
        ]
        avg_fairness = sum(fairness_scores) / len(fairness_scores)
        
        return (self.WEIGHT_FIT * fit_score) + (self.WEIGHT_FAIRNESS * avg_fairness)
    
    def generate_fair_pools(self, available_fighters, p1_tags, opp_tags, p1_range=None, opp_range=None):
        """
        Generates optimal pools using the Symmetric Elite Strategy,
        but with asymmetric pool sizes:
          - P1 pool: 5 fighters
          - Opp pool: 3 fighters
        Uses Set Intersection for O(1) fairness validation.
        """
        # CONFIGURE POOL SIZES HERE
        
        P1_POOL_SIZE = self.P1_POOL_SIZE
        OPP_POOL_SIZE = self.OPP_POOL_SIZE

        # 0. Safety Check: Need enough fighters to make the *bigger* pool
        if len(available_fighters) < max(P1_POOL_SIZE, OPP_POOL_SIZE):
            return None

        # 1. Score ALL fighters individually (With Range)
        p1_scores = []
        opp_scores = []
        
        for f in available_fighters:
            s_p1 = self._calculate_individual_fit(f, p1_tags, p1_range)
            s_opp = self._calculate_individual_fit(f, opp_tags, opp_range)
            p1_scores.append({'id': f['id'], 'score': s_p1, 'obj': f})
            opp_scores.append({'id': f['id'], 'score': s_opp, 'obj': f})
        
        # 2. Get Elite Candidates (Top 12 or any k you like)
                # 2. Get Elite Candidates (Weighted random across full list)
        ELITE_K = 12  # size of the elite pool
        p1_elite = _pick_weighted_elite(p1_scores, ELITE_K)
        opp_elite = _pick_weighted_elite(opp_scores, ELITE_K)

        # Extract IDs for combination generation
        p1_ids = [x['id'] for x in p1_elite]
        opp_ids = [x['id'] for x in opp_elite]

        p1_ids = [x['id'] for x in p1_elite]
        opp_ids = [x['id'] for x in opp_elite]
        # Extract IDs for combination generation
        p1_ids = [x['id'] for x in p1_elite]
        opp_ids = [x['id'] for x in opp_elite]
        
        # Create fast lookup map for scores
        p1_score_map = {x['id']: x['score'] for x in p1_scores}
        opp_score_map = {x['id']: x['score'] for x in opp_scores}
        
        best_result = None
        max_total_score = -1.0

        # 3. Generate Pools with ASYMMETRIC sizes
        p1_combos = list(combinations(p1_ids, P1_POOL_SIZE))
        opp_combos = list(combinations(opp_ids, OPP_POOL_SIZE))

        # 4. Matrix Validation
        for pool_a_ids in p1_combos:
            # OPTIMIZATION: Intersection Trick
            # Universe of opponents fair against ALL P1 fighters in this pool
            iterator = iter(pool_a_ids)
            first_id = next(iterator)
            valid_opp_universe = set(self.fairness_map[first_id])
            for fid in iterator:
                valid_opp_universe &= self.fairness_map[fid]
            
            # If universe is too small, no need to check Opp pools against it
            if len(valid_opp_universe) < OPP_POOL_SIZE:
                continue

            for pool_b_ids in opp_combos:
                # FAST SUBSET CHECK
                if not set(pool_b_ids).issubset(valid_opp_universe):
                    continue

                # 5. Global Scoring (Weighted combination of Fit and Fairness)
                avg_fit = self._calculate_pool_fitness(pool_a_ids, pool_b_ids, p1_score_map, opp_score_map, P1_POOL_SIZE, OPP_POOL_SIZE)
                avg_fairness = self._calculate_pool_fairness(pool_a_ids, pool_b_ids)
                total_score = (self.WEIGHT_FIT * avg_fit) + (self.WEIGHT_FAIRNESS * avg_fairness)


                if total_score > max_total_score:
                    max_total_score = total_score
                    # Retrieve actual fighter objects for the return
                    p1_objs = [f for f in available_fighters if f['id'] in pool_a_ids]
                    opp_objs = [f for f in available_fighters if f['id'] in pool_b_ids]
                    
                    best_result = {
                        'p1_pool': p1_objs,
                        'opp_pool': opp_objs,
                        'total_score': total_score,
                        'p1_ids': pool_a_ids,
                        'opp_ids': pool_b_ids
                    }

        # Sort the results internally if found
        if best_result:
            # Sort P1 pool by descending total score (fitness + fairness)
            best_result['p1_pool'].sort(
                key=lambda f: self._calculate_fighter_total_score(f, 'p1', p1_score_map, best_result['opp_ids']),
                reverse=True
            )

            # Sort Opponent pool by descending total score (fitness + fairness)
            best_result['opp_pool'].sort(
                key=lambda f: self._calculate_fighter_total_score(f, 'opp', opp_score_map, best_result['p1_ids']),
                reverse=True
            )

        return best_result