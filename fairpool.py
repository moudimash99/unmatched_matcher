import random
from itertools import combinations
from collections import defaultdict

class MatchupEngine:
    def __init__(self, fighters_db, win_rate_matrix):
        self.fighters_db = fighters_db
        self.win_rate_matrix = win_rate_matrix
        self.WEIGHT_FIT = 0.6
        self.WEIGHT_FAIRNESS = 0.4
        
        # PRE-CALCULATION: Build the Fairness Map immediately (O(1) lookups later)
        # Maps FighterID -> Set of IDs they are fair against (40-60%)
        self.fairness_map = self._build_fairness_map()

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

    def _calculate_individual_fit(self, fighter, requested_tags):
        """Scores how well a fighter matches the requested playstyles."""
        if not requested_tags: return 0.5
        fighter_tags = set(fighter.get('playstyles', []))
        if not fighter_tags: return 0.0
        
        intersection = fighter_tags.intersection(requested_tags)
        match_ratio = len(intersection) / len(fighter_tags)
        coverage_score = len(intersection) / len(requested_tags)
        
        return (0.4 * match_ratio) + (0.6 * coverage_score)

    def _score_pair(self, p1_fighter, opp_fighter, p1_tags, opp_tags):
        """Scores a specific pairing on both Fit and Fairness."""
        # 1. Dual Fit Score
        score_p1 = self._calculate_individual_fit(p1_fighter, p1_tags)
        score_opp = self._calculate_individual_fit(opp_fighter, opp_tags)
        dual_fit = (score_p1 + score_opp) / 2.0

        # 2. Fairness Score (Target 50%)
        win_rate = self._get_win_rate(p1_fighter['id'], opp_fighter['id'])
        dist_from_50 = abs(win_rate - 50.0)
        fairness = 1.0 - (dist_from_50 / 50.0)

        total_score = (self.WEIGHT_FIT * dual_fit) + (self.WEIGHT_FAIRNESS * fairness)
        return total_score, win_rate

    def recommend_opponents(self, fighter, available_fighters, opponent_tags, quantity=5):
        """
        Recommends opponents for a given fighter based on opponent tags.
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
            
            # Opponent tag fit
            tag_fit = self._calculate_individual_fit(opp, opponent_tags)
            
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

    # ==========================================
    # FEATURE 1: 1v1 MATCHUP BATCH GENERATION
    # ==========================================
    def generate_batch(self, available_fighters, p1_tags, opp_tags, quantity=10):
        """
        Generates a batch of matchups using Weighted Random Selection 
        and Frequency Capping (Max 3 repeats per batch).
        """
        # 1. Pre-calculate score for EVERY valid pair
        all_candidates = []
        for f_a in available_fighters:
            for f_b in available_fighters:
                if f_a['id'] == f_b['id']: continue
                
                score, wr = self._score_pair(f_a, f_b, p1_tags, opp_tags)
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
    def generate_fair_pools(self, available_fighters, p1_tags, opp_tags):
        """
        Generates optimal 4v4 pools using the Symmetric Elite Strategy.
        Uses Set Intersection for O(1) fairness validation.
        """
        # 0. Safety Check: Need at least 4 fighters to make a pool
        if len(available_fighters) < 4:
            return None

        # 1. Score ALL fighters individually
        p1_scores = []
        opp_scores = []
        
        for f in available_fighters:
            s_p1 = self._calculate_individual_fit(f, p1_tags)
            s_opp = self._calculate_individual_fit(f, opp_tags)
            p1_scores.append({'id': f['id'], 'score': s_p1, 'obj': f})
            opp_scores.append({'id': f['id'], 'score': s_opp, 'obj': f})
        
        # 2. Get Elite Candidates (Top 12)
        # Note: If len < 12, python slicing safely returns the entire list.
        p1_elite = sorted(p1_scores, key=lambda x: x['score'], reverse=True)[:12]
        opp_elite = sorted(opp_scores, key=lambda x: x['score'], reverse=True)[:12]
        
        # Extract IDs for combination generation
        p1_ids = [x['id'] for x in p1_elite]
        opp_ids = [x['id'] for x in opp_elite]
        
        # Create fast lookup map for scores
        p1_score_map = {x['id']: x['score'] for x in p1_scores}
        opp_score_map = {x['id']: x['score'] for x in opp_scores}
        
        best_result = None
        max_total_score = -1.0

        # 3. Generate Pools
        # Note: If len(p1_ids) < 4, this returns empty list (loop won't run)
        p1_combos = list(combinations(p1_ids, 4))
        opp_combos = list(combinations(opp_ids, 4))

        # 4. Matrix Validation
        for pool_a_ids in p1_combos:
            # OPTIMIZATION: Intersection Trick
            # Find the "universe" of opponents fair against ALL 4 P1 fighters
            valid_opp_universe = (
                self.fairness_map[pool_a_ids[0]] & 
                self.fairness_map[pool_a_ids[1]] & 
                self.fairness_map[pool_a_ids[2]] & 
                self.fairness_map[pool_a_ids[3]]
            )
            
            # If universe is too small, no need to check Opp pools against it
            if len(valid_opp_universe) < 4:
                continue

            for pool_b_ids in opp_combos:
                # FAST SUBSET CHECK
                # Is this specific Opp pool contained entirely within the valid universe?
                if not set(pool_b_ids).issubset(valid_opp_universe):
                    continue

                # 5. Global Scoring (Avg Fit A + Avg Fit B)
                avg_p1 = sum(p1_score_map[i] for i in pool_a_ids) / 4.0
                avg_opp = sum(opp_score_map[i] for i in pool_b_ids) / 4.0
                total_score = avg_p1 + avg_opp

                if total_score > max_total_score:
                    max_total_score = total_score
                    # Retrieve actual fighter objects for the return
                    p1_objs = [f for f in available_fighters if f['id'] in pool_a_ids]
                    opp_objs = [f for f in available_fighters if f['id'] in pool_b_ids]
                    
                    # Store the pool IDs for sorting matchups by best score
                    best_result = {
                        'p1_pool': p1_objs,
                        'opp_pool': opp_objs,
                        'total_score': total_score,
                        'p1_ids': pool_a_ids,
                        'opp_ids': pool_b_ids
                    }

        # Sort pools so the best matchup pair is at index 0
        if best_result:
            # Calculate score for each possible p1-opp pairing
            matchup_scores = []
            for p1_fighter in best_result['p1_pool']:
                for opp_fighter in best_result['opp_pool']:
                    score, _ = self._score_pair(p1_fighter, opp_fighter, p1_tags, opp_tags)
                    matchup_scores.append({
                        'p1': p1_fighter,
                        'opp': opp_fighter,
                        'score': score
                    })
            
            # Sort by score descending
            matchup_scores.sort(key=lambda x: x['score'], reverse=True)
            
            # Reorder pools: put best matchup fighters at index 0
            best_p1 = matchup_scores[0]['p1']
            best_opp = matchup_scores[0]['opp']
            
            # Reorder p1_pool
            p1_pool_reordered = [best_p1] + [f for f in best_result['p1_pool'] if f['id'] != best_p1['id']]
            # Reorder opp_pool
            opp_pool_reordered = [best_opp] + [f for f in best_result['opp_pool'] if f['id'] != best_opp['id']]
            
            best_result['p1_pool'] = p1_pool_reordered
            best_result['opp_pool'] = opp_pool_reordered

        return best_result