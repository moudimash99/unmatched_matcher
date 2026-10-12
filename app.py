from flask import Flask, render_template, request, send_from_directory, send_file
from matchup_engine import MatchupEngine, FULL_CONFIDENCE_GAMES
import random
import json
import os
import glob
from io import BytesIO
from PIL import Image

app = Flask(__name__)

# ---------------------------------------------------------
# 1.  DATA  ────────────────────────────────────────────────
# ---------------------------------------------------------
# Cache the list of fighter image filenames at startup
_PICS_DIR = os.path.join(os.path.dirname(__file__), 'static', 'pics')
_FIGHTER_IMAGES_CACHE = [os.path.basename(f) for f in glob.glob(os.path.join(_PICS_DIR, '*.webp'))]
def load_json_data(filename, default):
    """Load JSON data from a file with error handling."""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading or parsing {filename}: {e}")
        return default


FIGHTERS_DATA = load_json_data("input/fighters.json", {}).get("fighters", [])
PLAYSTYLE_DEFINITIONS = load_json_data("input/fighters.json", {}).get("playstyle_definitions", {})
# Build a single alphabetically-sorted dict merging major and minor definitions.
# Major entries take precedence for type when a name appears in both.
_ps_combined: dict = {}
for _name, _desc in PLAYSTYLE_DEFINITIONS.get("minor", {}).items():
    _ps_combined[_name] = {"desc": _desc, "type": "minor"}
for _name, _desc in PLAYSTYLE_DEFINITIONS.get("major", {}).items():
    _ps_combined[_name] = {"desc": _desc, "type": "major"}
PLAYSTYLE_DEFINITIONS_COMBINED = dict(sorted(_ps_combined.items()))
WIN_MATRIX = load_json_data("input/merged_win_pct.json", {})
GAMES_MATRIX = load_json_data("input/merged_games.json", {})
STATS_META = load_json_data("input/stats_meta.json", {})
engine = MatchupEngine(FIGHTERS_DATA, WIN_MATRIX, GAMES_MATRIX)

CLUB_MATCHUP_URL = "https://www.the-unmatched.club/tools/matchups"

def get_fighter_sets(fighter):
    """Returns a fighter's set values as a normalized list."""
    sets = fighter.get("set", [])
    if isinstance(sets, list):
        return sets
    return [sets] if sets else []

# A fighter can ship in more than one box (e.g. Bruce Lee): one entry per
# fighter, with every box it comes in listed under "set".
for f in FIGHTERS_DATA:
    f["sets"] = get_fighter_sets(f)
    overall, total_games = engine.overall_stats.get(f["id"], (None, 0))
    f["overall_win_rate"] = None if overall is None else round(overall)
    f["total_games"] = total_games

# Every pairing's estimate for the page's JS: MATCHUPS[a][b] = [estimated win %, games]
MATCHUPS = {
    a["id"]: {
        b["id"]: [round(engine.estimate_win_rate(a["id"], b["id"])), engine.games_played(a["id"], b["id"])]
        for b in FIGHTERS_DATA if b["id"] != a["id"]
    }
    for a in FIGHTERS_DATA
}

ALL_SETS_LIST = sorted({set_name for f in FIGHTERS_DATA for set_name in get_fighter_sets(f)})
# Extract all unique playstyles from both major and minor
all_playstyles_set = set()
for f in FIGHTERS_DATA:
    all_playstyles_set.update(f.get("major", []))
    all_playstyles_set.update(f.get("minor", []))
ALL_PLAYSTYLES = sorted(all_playstyles_set)

# Extract all unique themes from fighters
all_themes_set = set()
for f in FIGHTERS_DATA:
    all_themes_set.update(f.get("themes", []))
ALL_THEMES = sorted(all_themes_set)

# Human-readable theme labels
THEME_LABELS = {
    "halloween": "🎃 Halloween",
    "superhero": "🦸 Superhero",
    "legend": "⚔️ Legend",
    "monster": "👹 Monster",
    "film": "🎬 Film",
}

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

def get_available_fighters(owned_set_names, theme_filter=None):
    """Returns a list of fighters from the owned sets, optionally filtered by themes."""
    if not owned_set_names:
        return []
    owned_set_names_set = set(owned_set_names)
    fighters = [
        f for f in FIGHTERS_DATA
        if any(set_name in owned_set_names_set for set_name in get_fighter_sets(f))
    ]
    if theme_filter:
        fighters = [f for f in fighters if any(t in theme_filter for t in f.get("themes", []))]
    return fighters


def club_matchup_url(fighter_a, fighter_b):
    """Link to this matchup on The Unmatched Club's matchup tool."""
    return f"{CLUB_MATCHUP_URL}?h1={fighter_a['club_key']}&h2={fighter_b['club_key']}"


def generate_suggestions(selected_data, engine=engine):
    results = {"p1_main": None, "p1_alternatives": [], "opp_main": None, "opp_alternatives": []}
    error = None

    theme_filter = selected_data.get("theme_filter")
    available = get_available_fighters(selected_data["owned_sets"], theme_filter)
    if not available:
        if theme_filter and get_available_fighters(selected_data["owned_sets"]):
            return results, "No fighters match the selected theme(s) in your owned sets. Try selecting different themes or more sets."
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
            opp_recs = engine.recommend_opponents(p1_fighter, available, opp_tags, opp_range, quantity=5)
            
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
        else:
            error = "Your owned sets need at least two fighters to build a matchup."

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
    def matchup_info(fighter, vs_fighter):
        """Estimated win % (rounded like the JS side), games played, and a link to the matchup."""
        games = engine.games_played(fighter["id"], vs_fighter["id"])
        return {
            "win_pct": round(engine.estimate_win_rate(fighter["id"], vs_fighter["id"])),
            "games": games,
            "low_data": games < FULL_CONFIDENCE_GAMES,
            "club_url": club_matchup_url(fighter, vs_fighter),
        }

    return dict(matchup_info=matchup_info)
# ---------------------------------------------------------
# 4.  MAIN ROUTE  ─────────────────────────────────────────
# ---------------------------------------------------------
_FAVICON_PNG_CACHE = {}

@app.route("/favicon.ico")
def favicon():
    """Serves a random fighter image as the favicon, converted to PNG for browser compatibility."""
    if _FIGHTER_IMAGES_CACHE:
        random_image_filename = random.choice(_FIGHTER_IMAGES_CACHE)
        image_path = os.path.join(_PICS_DIR, random_image_filename)

        try:
            # Convert each WebP to a 32x32 PNG once, then serve it from memory
            png = _FAVICON_PNG_CACHE.get(random_image_filename)
            if png is None:
                img = Image.open(image_path).resize((32, 32), Image.Resampling.LANCZOS)
                img_io = BytesIO()
                img.save(img_io, 'PNG')
                png = _FAVICON_PNG_CACHE[random_image_filename] = img_io.getvalue()

            # Send the PNG image with no-cache headers so each page load gets a new one
            response = send_file(BytesIO(png), mimetype='image/png')
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response
        except Exception as e:
            print(f"Error converting favicon from {random_image_filename}: {e}")
            return '', 404
    
    # Fallback if no images found
    return '', 404

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
        "theme_filter": [],
    }
    results_data = None
    error_message = None

    all_fighters_sorted = sorted(FIGHTERS_DATA, key=lambda x: x["name"])

    # Shared matchup link: /?p1=<id>&opp=<id>&sets=<set>&sets=<set>...
    shared_p1 = find_fighter_by_id(request.args.get("p1"))
    shared_opp = find_fighter_by_id(request.args.get("opp"))
    if request.method == "GET" and shared_p1 and shared_opp:
        owned = [s for s in request.args.getlist("sets") if s in ALL_SETS_LIST]
        selected_data.update({
            # Without sets in the link, assume the boxes these two fighters come in
            "owned_sets": owned or sorted(set(shared_p1["sets"]) | set(shared_opp["sets"])),
            "locked_p1_id": shared_p1["id"],
            "locked_opp_id": shared_opp["id"],
        })
        results_data, error_message = generate_suggestions(selected_data)

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
            "theme_filter": request.form.getlist("theme_filter"),
        })

        # Handle direct choices as implicit locks
        if selected_data["p1_selection_method"] == "direct_choice":
            p1_choice = request.form.get("p1_chosen_fighter")
            selected_data["p1_chosen_fighter_id"] = p1_choice or None
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
        # A per-request copy, so concurrent requests never share mode weights
        request_engine = engine.with_mode(effective_mode, fw)
        # -----------------------------------------------------------

        results_data, error_message = generate_suggestions(selected_data, request_engine)

    return render_template(
        "index.html",
        all_sets_list=ALL_SETS_LIST,
        all_playstyles=ALL_PLAYSTYLES,
        all_ranges=ALL_RANGES,
        all_themes=ALL_THEMES,
        theme_labels=THEME_LABELS,
        all_fighters_for_select=all_fighters_sorted,
        results=results_data,
        selected_data=selected_data,
        error_message=error_message,
        matchups=MATCHUPS,
        stats_meta=STATS_META,
        full_confidence_games=FULL_CONFIDENCE_GAMES,
        club_matchup_url=CLUB_MATCHUP_URL,
        playstyle_definitions=PLAYSTYLE_DEFINITIONS_COMBINED
    )

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/robots.txt")
def robots_txt():
    return send_from_directory("static", "robots.txt", mimetype="text/plain")

@app.route("/sitemap.xml")
def sitemap_xml():
    return send_from_directory("static", "sitemap.xml", mimetype="application/xml")

# ---------------------------------------------------------
# 5.  RUN  ────────────────────────────────────────────────
# ---------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5001)
