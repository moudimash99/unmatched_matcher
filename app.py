from flask import Flask, render_template, request, jsonify
import random
import json
import hashlib

app = Flask(__name__)

# ---------------------------------------------------------
# 1.  DATA  ────────────────────────────────────────────────
# ---------------------------------------------------------
try:
    with open("fighters.json", "r", encoding="utf-8") as f:
        json_data = json.load(f)
        FIGHTERS_DATA = json_data.get("fighters", [])
        PLAYSTYLE_DEFINITIONS = json_data.get("playstyle_definitions", {})
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"Error loading or parsing fighters.json: {e}")
    FIGHTERS_DATA = []
    PLAYSTYLE_DEFINITIONS = {}

ALL_SETS_LIST = sorted({f["set"] for f in FIGHTERS_DATA})
ALL_PLAYSTYLES = sorted({ps for f in FIGHTERS_DATA for ps in f["playstyles"]})
ALL_RANGES = sorted({f["range"] for f in FIGHTERS_DATA})

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

def score_fighter(fighter, preferred_playstyles, preferred_range):
    """Calculates a relevance score for a fighter based on preferences."""
    score = 1
    if preferred_playstyles and any(ps in fighter["playstyles"] for ps in preferred_playstyles):
        score += 10
    if preferred_range and fighter["range"].lower() == preferred_range.lower():
        score += 8
    score += random.uniform(0, 0.1)  # Small tie-breaker
    return score

def get_smart_suggestions(pool, playstyles, prange, exclude_ids=None):
    """Returns a main suggestion and alternatives from a pool of fighters."""
    exclude_ids = exclude_ids or []
    eligible = [f for f in pool if f["id"] not in exclude_ids]
    if not eligible:
        return {"main": None, "alternatives": []}

    scored = sorted(
        ({"fighter": f, "score": score_fighter(f, playstyles, prange)} for f in eligible),
        key=lambda x: x["score"],
        reverse=True,
    )
    main_pick = scored[0]["fighter"]
    # Ensure alternatives don't include the main pick
    alternatives = [s["fighter"] for s in scored[1:5] if s["fighter"]["id"] != main_pick["id"]]
    return {"main": main_pick, "alternatives": alternatives[:4]}

def calculate_win_percentage(id_a, id_b):
    """Generates a deterministic, pseudo-random win percentage for id_a vs id_b."""
    if not id_a or not id_b:
        return None
    pair = tuple(sorted((id_a, id_b)))
    seed = int(hashlib.sha256(":".join(pair).encode()).hexdigest(), 16)
    rnd = random.Random(seed)
    base = rnd.uniform(0.3, 0.7)
    pct = base if id_a == pair[0] else 1 - base
    return round(pct * 100, 1)

def generate_suggestions(selected_data):
    """Core logic to generate matchup suggestions for both players."""
    results = {
        "p1_main": None, "p1_alternatives": [],
        "opp_main": None, "opp_alternatives": [],
    }
    error_message = None

    available_fighters = get_available_fighters(selected_data["owned_sets"])
    if not selected_data["owned_sets"]:
        error_message = "Please select at least one owned set to get suggestions."
    elif not available_fighters:
        error_message = "No fighters available from the selected sets."
    else:
        exclude_ids = [fid for fid in [selected_data["locked_p1_id"], selected_data["locked_opp_id"]] if fid]

        # --- Player 1 ---
        if selected_data["locked_p1_id"]:
            results["p1_main"] = find_fighter_by_id(selected_data["locked_p1_id"])
            p1_alt_sugg = get_smart_suggestions(
                available_fighters, selected_data["p1_playstyles"], selected_data["p1_range"], exclude_ids=exclude_ids
            )
            results["p1_alternatives"] = p1_alt_sugg["alternatives"]
        else:
            p1_sugg = get_smart_suggestions(
                available_fighters, selected_data["p1_playstyles"], selected_data["p1_range"], exclude_ids=exclude_ids
            )
            results["p1_main"] = p1_sugg["main"]
            results["p1_alternatives"] = p1_sugg["alternatives"]
            if p1_sugg["main"]:
                exclude_ids.append(p1_sugg["main"]["id"])

        # --- Opponent ---
        if selected_data["locked_opp_id"]:
            results["opp_main"] = find_fighter_by_id(selected_data["locked_opp_id"])
            opp_alt_sugg = get_smart_suggestions(
                available_fighters, selected_data["opp_playstyles"], selected_data["opp_range"], exclude_ids=exclude_ids
            )
            results["opp_alternatives"] = opp_alt_sugg["alternatives"]
        else:
            opp_sugg = get_smart_suggestions(
                available_fighters, selected_data["opp_playstyles"], selected_data["opp_range"], exclude_ids=exclude_ids
            )
            results["opp_main"] = opp_sugg["main"]
            results["opp_alternatives"] = opp_sugg["alternatives"]

    return results, error_message

# ---------------------------------------------------------
# 3.  JINJA FILTERS / HELPERS  ────────────────────────────
# ---------------------------------------------------------
@app.template_filter("titlecase_custom")
def title_case_filter(s):
    """A custom Jinja filter to format strings nicely."""
    return s.replace("_", " ").title() if isinstance(s, str) else s

@app.context_processor
def utility_processor():
    """Make helper functions available in all templates."""
    return dict(calculate_win_percentage=calculate_win_percentage)

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

        results_data, error_message = generate_suggestions(selected_data)

        if results_data:
            p1_team = [f for f in [results_data.get("p1_main")] + results_data.get("p1_alternatives", []) if f]
            opp_team = [f for f in [results_data.get("opp_main")] + results_data.get("opp_alternatives", []) if f]

            for p1_fighter in p1_team:
                for opp_fighter in opp_team:
                    key = ":".join(sorted((p1_fighter["id"], opp_fighter["id"])))
                    if key not in win_percentage_matrix:
                        win_percentage_matrix[key] = {
                            p1_fighter["id"]: calculate_win_percentage(p1_fighter["id"], opp_fighter["id"]),
                            opp_fighter["id"]: calculate_win_percentage(opp_fighter["id"], opp_fighter["id"])
                        }

    return render_template(
        "index.html",
        all_sets_list=ALL_SETS_LIST,
        all_playstyles=ALL_PLAYSTYLES,
        all_ranges=ALL_RANGES,
        all_fighters_for_select=all_fighters_sorted,
        results=results_data,
        selected_data=selected_data,
        error_message=error_message,
        win_percentage_matrix=win_percentage_matrix
    )

# ---------------------------------------------------------
# 5.  RUN  ────────────────────────────────────────────────
# ---------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5001)
