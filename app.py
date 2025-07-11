from flask import Flask, render_template, request, jsonify
import random
import json
import hashlib

app = Flask(__name__)

# ---------------------------------------------------------
# 1.  DATA  ────────────────────────────────────────────────
# ---------------------------------------------------------
# Load fighter data from a JSON file so designers can tweak
# stats & images without changing Python.
# ---------------------------------------------------------
try:
    with open("fighters.json", "r", encoding="utf-8") as f:
        json_data = json.load(f)
        FIGHTERS_DATA = json_data.get("fighters", [])
        PLAYSTYLE_DEFINITIONS = json_data.get("playstyle_definitions", {})
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"Error loading or parsing fighters.json: {e}")
    # Empty fallback keeps the app running even if the file
    # is missing or corrupted.
    FIGHTERS_DATA = []
    PLAYSTYLE_DEFINITIONS = {}

ALL_SETS_LIST = sorted({f["set"] for f in FIGHTERS_DATA})
ALL_PLAYSTYLES = sorted({ps for f in FIGHTERS_DATA for ps in f["playstyles"]})
ALL_RANGES = sorted({f["range"] for f in FIGHTERS_DATA})

# ---------------------------------------------------------
# 2.  HELPER FUNCTIONS  ───────────────────────────────────
# ---------------------------------------------------------

def find_fighter_by_id(fid):
    return next((f for f in FIGHTERS_DATA if f["id"] == fid), None)

def get_available_fighters(owned_set_names):
    if not owned_set_names:
        return []
    return [f for f in FIGHTERS_DATA if f["set"] in owned_set_names]

def score_fighter(fighter, preferred_playstyles, preferred_range):
    score = 1
    if preferred_playstyles and any(ps in fighter["playstyles"] for ps in preferred_playstyles):
        score += 10
    if preferred_range and fighter["range"].lower() == preferred_range.lower():
        score += 8
    score += random.uniform(0, 0.1)  # small tie-breaker
    return score

def get_smart_suggestions(pool, playstyles, prange, exclude_ids=None):
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
    alternatives = [s["fighter"] for s in scored[1:4]]
    return {"main": main_pick, "alternatives": alternatives}

def calculate_win_percentage(id_a, id_b):
    """Deterministic pseudo win percentage for id_a against id_b."""
    if not id_a or not id_b:
        return None
    pair = tuple(sorted((id_a, id_b)))
    seed = int(hashlib.sha256(":".join(pair).encode()).hexdigest(), 16)
    rnd = random.Random(seed)
    base = rnd.uniform(0.3, 0.7)
    pct = base if id_a == pair[0] else 1 - base
    return round(pct * 100, 1)

def clone_fighter(f):
    return dict(f) if f else None

def attach_win_percentages(results):
    """Attach win percentages vs the other side to fighter dicts."""
    p1_team = [results.get("p1_main")] + results.get("p1_alternatives", [])
    opp_team = [results.get("opp_main")] + results.get("opp_alternatives", [])

    for f in p1_team:
        if not f:
            continue
        f["win_percentages"] = {
            o["id"]: calculate_win_percentage(f["id"], o["id"])
            for o in opp_team if o
        }

    for o in opp_team:
        if not o:
            continue
        o["win_percentages"] = {
            f["id"]: calculate_win_percentage(o["id"], f["id"])
            for f in p1_team if f
        }

def generate_suggestions(selected_data):
    """Return matchup suggestions and any error message."""
    results = {
        "p1_main": None,
        "p1_alternatives": [],
        "opp_main": None,
        "opp_alternatives": [],
    }
    error_message = None

    available_fighters = get_available_fighters(selected_data["owned_sets"])
    if not selected_data["owned_sets"]:
        error_message = "Please select at least one owned set to get suggestions."
    elif not available_fighters:
        error_message = "No fighters available from the selected sets."
    else:
        exclude_ids = [fid for fid in [selected_data["locked_p1_id"], selected_data["locked_opp_id"]] if fid]

        if selected_data["locked_p1_id"]:
            results["p1_main"] = find_fighter_by_id(selected_data["locked_p1_id"])
        else:
            p1_sugg = get_smart_suggestions(
                available_fighters,
                selected_data["p1_playstyles"],
                selected_data["p1_range"],
                exclude_ids=exclude_ids,
            )
            results["p1_main"] = p1_sugg["main"]
            results["p1_alternatives"] = p1_sugg["alternatives"]
            if p1_sugg["main"]:
                exclude_ids.append(p1_sugg["main"]["id"])

        if selected_data["locked_opp_id"]:
            results["opp_main"] = find_fighter_by_id(selected_data["locked_opp_id"])
        else:
            opp_sugg = get_smart_suggestions(
                available_fighters,
                selected_data["opp_playstyles"],
                selected_data["opp_range"],
                exclude_ids=exclude_ids,
            )
            results["opp_main"] = opp_sugg["main"]
            results["opp_alternatives"] = opp_sugg["alternatives"]

    return results, error_message

# ---------------------------------------------------------
# 3.  JINJA FILTERS / HELPERS  ────────────────────────────
# ---------------------------------------------------------
@app.template_filter("titlecase_custom")
def title_case_filter(s):
    return s.replace("_", " ").title() if isinstance(s, str) else s

@app.context_processor
def utility_processor():
    def render_fighter_html_backend(
        fighter,
        is_main,
        player_prefix="p1",
        currently_locked_id=None,
        vs_fighter_id=None,
    ):
        """Return the HTML for a fighter card used by both players."""
        if not fighter:
            return ""

        playstyles_str = ", ".join(map(title_case_filter, fighter.get("playstyles", []))) or "N/A"
        fighter_name = fighter.get("name", "Unknown Fighter")
        fighter_id = fighter.get("id", "")
        is_locked = fighter_id and fighter_id == currently_locked_id

        # MAIN card → Lock / Unlock toggle
        # ALT  card → JS-only "Select" button (promotes to main client-side)
        if is_main:
            if is_locked:
                btn_html = (
                    f'<button type="submit" name="action" value="unlock_{player_prefix}" '
                    f'class="lock-button btn-unlock">🔓 Fighter Locked</button>'
                )
            else:
                btn_html = (
                    f'<button type="submit" name="action" '
                    f'value="lock_{player_prefix}:{fighter_id}" '
                    f'class="lock-button btn-lock">🔒 Lock Fighter</button>'
                )
        else:
            btn_html = (
                f'<button type="button" class="select-alternative-btn" '
                f'data-fighter-id="{fighter_id}" data-player-prefix="{player_prefix}">'  # JS hook
                f'Select for Matchup</button>'
            )

        win_html = ""
        if vs_fighter_id:
            opponent = find_fighter_by_id(vs_fighter_id)
            if opponent:
                pct = calculate_win_percentage(fighter_id, vs_fighter_id)
                win_html = (
                    f'<p><strong>Win vs {opponent["name"]}:</strong> {pct}%</p>'
                )

        card_id_attr = f'id="{player_prefix}-main-suggestion"' if is_main else ""
        card_cls = "main-suggestion" if is_main else "alternative-suggestion"

        return (
            f'<div {card_id_attr} class="fighter-card {card_cls}" data-fighter-name="{fighter_name}">'  # wrapper
            f'  <div class="fighter-card-body">'
            f'    <img src="{fighter.get("image_url", "")}" alt="{fighter_name}" class="fighter-image">'
            f'    <div class="fighter-details">'
            f'      <h3 class="fighter-name">{fighter_name}</h3>'
            f'      <p><strong>Set:</strong> {fighter.get("set", "N/A")}</p>'
            f'      <p><strong>Range:</strong> {title_case_filter(fighter.get("range", "N/A"))}</p>'
            f'      <p><strong>Playstyles:</strong> {playstyles_str}</p>'
            f'      {win_html}'
            f'    </div>'
            f'  </div>'
            f'  <div class="fighter-card-footer">{btn_html}</div>'
            f'</div>'
        )

    return dict(render_fighter_backend=render_fighter_html_backend, find_fighter_by_id=find_fighter_by_id)

# ---------------------------------------------------------
# 4.  MAIN ROUTE  ─────────────────────────────────────────
# ---------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    """Home route handles form, suggestions, & rendering."""
    selected_data = {
        # Shared
        "owned_sets": [],
        # Player-1 controls
        "p1_selection_method": "direct_choice",  # direct_choice | preferences
        "p1_chosen_fighter_id": None,
        "p1_playstyles": [],
        "p1_range": "",
        # Player-2 controls  (ADDED BACK!)
        "opp_selection_method": "direct_choice",  # direct_choice | preferences
        "opp_chosen_fighter_id": None,
        "opp_playstyles": [],
        "opp_range": "",
        # Locks
        "locked_p1_id": None,
        "locked_opp_id": None,
    }

    results_data = None
    error_message = None

    # Dropdown list for direct choices (same for both players)
    all_fighters_sorted = sorted(FIGHTERS_DATA, key=lambda x: x["name"])

    if request.method == "POST":
        action = request.form.get("action", "suggest_general")

        # -------------------------------------------------
        # 4A.  Gather form inputs & preserve state
        # -------------------------------------------------
        selected_data.update({
            "owned_sets": request.form.getlist("owned_sets"),
            # Player-1
            "p1_selection_method": request.form.get("p1_selection_method", "direct_choice"),
            "p1_playstyles": request.form.getlist("p1_playstyles"),
            "p1_range": request.form.get("p1_range"),
            # Player-2 (opponent)
            "opp_selection_method": request.form.get("opp_selection_method", "direct_choice"),
            "opp_playstyles": request.form.getlist("opp_playstyles"),
            "opp_range": request.form.get("opp_range"),
            # Locks (hidden inputs in form)
            "locked_p1_id": request.form.get("current_locked_p1_id"),
            "locked_opp_id": request.form.get("current_locked_opp_id"),
        })

        # -------------------------------------------------
        # 4B.  Treat a direct choice as an implicit lock
        # -------------------------------------------------
        if selected_data["p1_selection_method"] == "direct_choice":
            p1_choice = request.form.get("p1_chosen_fighter")
            if p1_choice:
                selected_data["p1_chosen_fighter_id"] = p1_choice
                action = f"lock_p1:{p1_choice}"

        if selected_data["opp_selection_method"] == "direct_choice":
            opp_choice = request.form.get("opp_chosen_fighter")
            if opp_choice:
                selected_data["opp_chosen_fighter_id"] = opp_choice
                action = f"lock_opp:{opp_choice}"

        # -------------------------------------------------
        # 4C.  Handle lock / unlock actions
        # -------------------------------------------------
        if action.startswith("lock_p1:"):
            selected_data["locked_p1_id"] = action.split(":")[1]
        elif action == "unlock_p1":
            selected_data["locked_p1_id"] = None
        elif action.startswith("lock_opp:"):
            selected_data["locked_opp_id"] = action.split(":")[1]
        elif action == "unlock_opp":
            selected_data["locked_opp_id"] = None

        # -------------------------------------------------
        # 4D.  Build suggestions
        # -------------------------------------------------
        results_data, error_message = generate_suggestions(selected_data)

    # -----------------------------------------------------
    # 4E.  Render
    # -----------------------------------------------------
    return render_template(
        "index.html",
        all_sets_list=ALL_SETS_LIST,
        all_playstyles=ALL_PLAYSTYLES,
        all_ranges=ALL_RANGES,
        all_fighters_for_select=all_fighters_sorted,
        results=results_data,
        selected_data=selected_data,
        error_message=error_message,
    )


@app.route("/api/matchup", methods=["POST"])
def api_matchup():
    """JSON API for matchup suggestions."""
    payload = request.get_json(force=True)
    selected = {
        "owned_sets": payload.get("owned_sets", []),
        "p1_selection_method": payload.get("p1_selection_method", "direct_choice"),
        "p1_playstyles": payload.get("p1_playstyles", []),
        "p1_range": payload.get("p1_range"),
        "opp_selection_method": payload.get("opp_selection_method", "direct_choice"),
        "opp_playstyles": payload.get("opp_playstyles", []),
        "opp_range": payload.get("opp_range"),
        "locked_p1_id": payload.get("locked_p1_id"),
        "locked_opp_id": payload.get("locked_opp_id"),
    }

    results, error = generate_suggestions(selected)

    # Clone fighters so we don't mutate global data
    cloned = {
        "p1_main": clone_fighter(results.get("p1_main")),
        "p1_alternatives": [clone_fighter(f) for f in results.get("p1_alternatives", [])],
        "opp_main": clone_fighter(results.get("opp_main")),
        "opp_alternatives": [clone_fighter(f) for f in results.get("opp_alternatives", [])],
    }

    attach_win_percentages(cloned)

    return jsonify({"results": cloned, "error_message": error})

# ---------------------------------------------------------
# 5.  RUN  ────────────────────────────────────────────────
# ---------------------------------------------------------
if __name__ == "__main__":
    # Port 5001 avoids collisions with other Flask apps.
    app.run(debug=True, port=5001)
