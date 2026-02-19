from flask import Flask, render_template, request, jsonify
from matchup_engine import MatchupEngine 
import random
import json
import hashlib

app = Flask(__name__)

# ---------------------------------------------------------
# 1.  DATA  ────────────────────────────────────────────────
# ---------------------------------------------------------
def load_json_data(filename, default):
    """Load JSON data from a file with error handling."""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading or parsing {filename}: {e}")
        return default


FIGHTERS_DATA = load_json_data("input/fighters.json", {}).get("fighters", [])
ATTRIBUTE_DEFINITIONS = load_json_data("input/fighters.json", {}).get("attribute_definitions", {})
# For backward compatibility, also support old field name
PLAYSTYLE_DEFINITIONS = load_json_data("input/fighters.json", {}).get("playstyle_definitions", ATTRIBUTE_DEFINITIONS)
WIN_MATRIX = load_json_data("input/win_matrix.json", {})
engine = MatchupEngine(FIGHTERS_DATA, WIN_MATRIX) 

ALL_SETS_LIST = sorted({f["set"] for f in FIGHTERS_DATA})
# Extract all unique playstyles from both macro and micro
all_playstyles_set = set()
for f in FIGHTERS_DATA:
    # New structure: macro.primary and micro.supporting
    all_playstyles_set.update(f.get("macro", {}).get("primary", []))
    all_playstyles_set.update(f.get("micro", {}).get("supporting", []))
    # Backward compatibility: old playstyles field
    all_playstyles_set.update(f.get("playstyles", []))
ALL_PLAYSTYLES = sorted(all_playstyles_set)

# Define Custom Sort Order for Range Dropdown
RANGE_ORDER = ["Melee", "Reach", "Hybrid", "Ranged Assist", "Ranged"]
ALL_RANGES = sorted(
    {f["range"] for f in FIGHTERS_DATA}, 
    key=lambda x: RANGE_ORDER.index(x) if x in RANGE_ORDER else 99
)

# ---------------------------------------------------------
# 2.  HELPER FUNCTIONS  ───────────────────────────────────
# ---------------------------------------------------------

def find_fighter_by_id(fid):
    """Finds a fighter dictionary by its ID."""
    return next((f for f in FIGHTERS_DATA if f["id"] == fid), None)

def get_available_fighters(owned_set_names):
    """Returns a list of fighters from the owned sets."""
    if not owned_set_names:
        return []
    return [f for f in FIGHTERS_DATA if f["set"] in owned_set_names]


def calculate_win_percentage(id_a, id_b):
    """Generates a deterministic, pseudo-random win percentage for id_a vs id_b."""
    if not id_a or not id_b:
        return None
    pair = tuple(sorted((id_a, id_b)))
    seed = int(hashlib.sha256(":".join(pair).encode()).hexdigest(), 16)
    rnd = random.Random(seed)
    base = rnd.uniform(0.3, 0.7)
    pct = base if id_a == pair[0] else 1 - base
    return round(pct, 1)

def generate_suggestions(selected_data):
    results = {"p1_main": None, "p1_alternatives": [], "opp_main": None, "opp_alternatives": []}
    error = None

    available = get_available_fighters(selected_data["owned_sets"])
    if not available:
        return results, "Please select at least one owned set."

    p1_tags = set(selected_data["p1_playstyles"])
    opp_tags = set(selected_data["opp_playstyles"])
    
    # Extract Range Preferences
    p1_range = selected_data.get("p1_range")
    opp_range = selected_data.get("opp_range")
    
    # CASE A: P1 is LOCKED (Direct Choice or Lock Button)
    if selected_data["locked_p1_id"]:
        p1_fighter = find_fighter_by_id(selected_data["locked_p1_id"])
        if p1_fighter:
            results["p1_main"] = p1_fighter
            # Ask Engine for Opponents tailored to P1
            opp_recs = engine.recommend_opponents(p1_fighter, available, opp_tags)
            
            # If Opponent is ALSO locked, just set them
            if selected_data["locked_opp_id"]:
                results["opp_main"] = find_fighter_by_id(selected_data["locked_opp_id"])
            # Otherwise, use the engine's recommendations
            elif opp_recs:
                results["opp_main"] = opp_recs[0]
                results["opp_alternatives"] = opp_recs[1:]

    # CASE B: Opponent is LOCKED (but P1 is not)
    elif selected_data["locked_opp_id"]:
        opp_fighter = find_fighter_by_id(selected_data["locked_opp_id"])
        if opp_fighter:
            results["opp_main"] = opp_fighter
            
            # Ask Engine for P1s tailored to Opponent
            p1_recs = engine.recommend_opponents(opp_fighter, available, p1_tags, p1_range, quantity=5)
            
            if p1_recs:
                results["p1_main"] = p1_recs[0]
                results["p1_alternatives"] = p1_recs[1:]

    # CASE C: Nobody Locked (Generate Fresh Matchups)
    else:
                # batch_1v1 = engine.generate_batch(available, p1_tags, opp_tags, p1_range, opp_range, quantity=5)

        pool_result = engine.generate_fair_pools(
            available,
            p1_tags,
            opp_tags,
            p1_range=p1_range,
            opp_range=opp_range
        )

        if pool_result:
            p1_pool = pool_result['p1_pool']
            opp_pool = pool_result['opp_pool']
            
            if p1_pool and opp_pool:
                results["p1_main"] = p1_pool[0]
                results["opp_main"] = opp_pool[0]
                
                # Extract alternatives (remaining fighters in each pool)
                results["p1_alternatives"] = p1_pool[1:]
                results["opp_alternatives"] = opp_pool[1:]

    return results, error

# ---------------------------------------------------------
# 3.  JINJA FILTERS / HELPERS  ────────────────────────────
# ---------------------------------------------------------
@app.template_filter("titlecase_custom")
def title_case_filter(s):
    """A custom Jinja filter to format strings nicely."""
    return s.replace("_", " ").title() if isinstance(s, str) else s

@app.context_processor
def utility_processor():
    def get_real_win_rate(id_a, id_b):
        if not id_a or not id_b: return 0
        # Access the internal method of the engine instance
        return round(engine._get_win_rate(id_a, id_b), 1)
    
    return dict(calculate_win_percentage=get_real_win_rate)
# ---------------------------------------------------------
# 4.  MAIN ROUTE  ─────────────────────────────────────────
# ---------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    """Handles the main page load and form submissions."""
    selected_data = {
        "owned_sets": [],
        "p1_selection_method": "suggest", "p1_chosen_fighter_id": None,
        "p1_playstyles": [], "p1_range": "",
        "opp_playstyles": [], "opp_range": "",
        "locked_p1_id": None, "locked_opp_id": None,
        "mode": "discovery",
        "fairness_weight": None,
    }
    results_data = None
    error_message = None
    win_percentage_matrix = {}

    all_fighters_sorted = sorted(FIGHTERS_DATA, key=lambda x: x["name"])

    if request.method == "POST":
        action = request.form.get("action", "suggest_general")

        selected_data.update({
            "owned_sets": request.form.getlist("owned_sets"),
            "p1_selection_method": request.form.get("p1_selection_method", "suggest"),
            "p1_playstyles": request.form.getlist("p1_playstyles"),
            "p1_range": request.form.get("p1_range"),
            "opp_playstyles": request.form.getlist("opp_playstyles"),
            "opp_range": request.form.get("opp_range"),
            "locked_p1_id": request.form.get("current_locked_p1_id"),
            "locked_opp_id": request.form.get("current_locked_opp_id"),
            "mode": request.form.get("mode", "discovery"),
            "fairness_weight": request.form.get("fairness_weight", "").strip() or None,
        })

        # Handle direct choices as implicit locks
        if selected_data["p1_selection_method"] == "direct_choice":
            p1_choice = request.form.get("p1_chosen_fighter")
            if p1_choice:
                selected_data["locked_p1_id"] = p1_choice
        
        # This is not an `elif` so both can be locked simultaneously
        if action.startswith("lock_p1:"):
            selected_data["locked_p1_id"] = action.split(":")[1]
        elif action == "unlock_p1":
            selected_data["locked_p1_id"] = None
        
        if action.startswith("lock_opp:"):
            selected_data["locked_opp_id"] = action.split(":")[1]
        elif action == "unlock_opp":
            selected_data["locked_opp_id"] = None

        # --- Apply matchup mode (discovery / fairness / custom) ---
        mode = selected_data.get("mode", "discovery")
        fw = selected_data.get("fairness_weight")
        effective_mode = "custom" if fw not in (None, "") else mode
        engine.set_mode(effective_mode, fw)
        # -----------------------------------------------------------

        results_data, error_message = generate_suggestions(selected_data)

    return render_template(
        "index.html",
        all_sets_list=ALL_SETS_LIST,
        all_playstyles=ALL_PLAYSTYLES,
        all_ranges=ALL_RANGES,
        all_fighters_for_select=all_fighters_sorted,
        results=results_data,
        selected_data=selected_data,
        error_message=error_message,
        win_percentage_matrix=win_percentage_matrix,
        win_matrix=WIN_MATRIX
    )

# ---------------------------------------------------------
# 5.  RUN  ────────────────────────────────────────────────
# ---------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5001)
