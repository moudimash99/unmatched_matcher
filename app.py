from flask import Flask, render_template, request
import random
import json

app = Flask(__name__)

# Load fighter data from the JSON file
try:
    with open('unmatched/fighters.json', 'r', encoding='utf-8') as f:
        json_data = json.load(f)
        FIGHTERS_DATA = json_data.get('fighters', [])
        PLAYSTYLE_DEFINITIONS = json_data.get('playstyle_definitions', {})
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"Error loading or parsing fighters.json: {e}")
    # Fallback to an empty list if the file is missing or corrupted
    FIGHTERS_DATA = []
    PLAYSTYLE_DEFINITIONS = {}


# --- The rest of your app logic now uses the loaded data ---
ALL_SETS_LIST = sorted(list(set(f['set'] for f in FIGHTERS_DATA)))
ALL_PLAYSTYLES = sorted(list(set(ps for f in FIGHTERS_DATA for ps in f['playstyles'])))
ALL_RANGES = sorted(list(set(f['range'] for f in FIGHTERS_DATA)))

def find_fighter_by_id(fighter_id):
    for fighter in FIGHTERS_DATA:
        if fighter['id'] == fighter_id:
            return fighter
    return None

def get_available_fighters(owned_set_names):
    if not owned_set_names:
        return []
    return [fighter for fighter in FIGHTERS_DATA if fighter['set'] in owned_set_names]

def score_fighter(fighter, preferred_playstyles, preferred_range):
    score = 1
    if preferred_playstyles and any(ps in fighter['playstyles'] for ps in preferred_playstyles):
        score += 10
    if preferred_range and fighter['range'].lower() == preferred_range.lower():
        score += 8
    score += random.uniform(0, 0.1)
    return score

def get_smart_suggestions(available_fighters, playstyles, prange, exclude_ids=None):
    if exclude_ids is None: exclude_ids = []
    eligible = [f for f in available_fighters if f['id'] not in exclude_ids]
    if not eligible: return {'main': None, 'alternatives': []}
    scored = sorted([{'fighter': f, 'score': score_fighter(f, playstyles, prange)} for f in eligible], key=lambda x: x['score'], reverse=True)
    if not scored: return {'main': None, 'alternatives': []}
    main_pick = scored[0]['fighter']
    alternatives = [s['fighter'] for s in scored[1:4]]
    return {'main': main_pick, 'alternatives': alternatives}

@app.template_filter('titlecase_custom')
def title_case_filter(s):
    return s.replace('_', ' ').title() if isinstance(s, str) else s

@app.context_processor
def utility_processor():
    def render_fighter_html_backend(fighter, is_main, player_prefix="p1", currently_locked_id=None):
        if not fighter: return ""
        playstyles_str = ', '.join(map(title_case_filter, fighter.get('playstyles', []))) or "N/A"
        fighter_name_str = fighter.get('name', "Unknown Fighter")
        fighter_id_str = fighter.get('id', "")
        is_this_fighter_locked = (fighter_id_str and fighter_id_str == currently_locked_id)
        
        action_button_html = ""
        # The main suggestion card shows a Lock/Unlock button
        if is_main:
            if is_this_fighter_locked:
                action_button_html = f"""<button type="submit" name="action" value="unlock_{player_prefix}" class="lock-button btn-unlock">🔓 Fighter Locked</button>"""
            else:
                action_button_html = f"""<button type="submit" name="action" value="lock_{player_prefix}:{fighter_id_str}" class="lock-button btn-lock">🔒 Lock Fighter</button>"""
        # Alternative cards show a 'Select' button
        else:
            action_button_html = f"""<button type="button" class="select-alternative-btn" data-fighter-id="{fighter_id_str}" data-player-prefix="{player_prefix}">Select for Matchup</button>"""

        # Add an ID to the main suggestion card for easier selection in JS
        card_id_attr = f'id="{player_prefix}-main-suggestion"' if is_main else ""
        card_class = 'main-suggestion' if is_main else 'alternative-suggestion'
        
        return f"""<div {card_id_attr} class="fighter-card {card_class}" data-fighter-name="{fighter_name_str}"><div class="fighter-card-body"><img src="{fighter.get('image_url', '')}" alt="{fighter_name_str}" class="fighter-image"><div class="fighter-details"><h3 class="fighter-name">{fighter_name_str}</h3><p><strong>Set:</strong> {fighter.get('set', 'N/A')}</p><p><strong>Range:</strong> {title_case_filter(fighter.get('range', 'N/A'))}</p><p><strong>Playstyles:</strong> {playstyles_str}</p></div></div><div class="fighter-card-footer">{action_button_html}</div></div>"""
    return dict(render_fighter_backend=render_fighter_backend, find_fighter_by_id=find_fighter_by_id)

@app.route('/', methods=['GET', 'POST'])
def index():
    selected_data = {
        'owned_sets': [], 'p1_selection_method': 'direct_choice', 'p1_chosen_fighter_id': None,
        'p1_playstyles': [], 'p1_range': '', 'opp_playstyles': [], 'opp_range': '',
        'locked_p1_id': None, 'locked_opp_id': None
    }
    results_data = None
    error_message = None
    # Sort all fighters alphabetically for the dropdown
    initial_all_fighters_for_p1_select = sorted(FIGHTERS_DATA, key=lambda x: x['name'])

    if request.method == 'POST':
        action = request.form.get('action', 'suggest_general')
        
        # Preserve state from form across submissions
        selected_data.update({
            'owned_sets': request.form.getlist('owned_sets'),
            'p1_selection_method': request.form.get('p1_selection_method', 'direct_choice'),
            'p1_playstyles': request.form.getlist('p1_playstyles'),
            'p1_range': request.form.get('p1_range'),
            'opp_playstyles': request.form.getlist('opp_playstyles'),
            'opp_range': request.form.get('opp_range'),
            'locked_p1_id': request.form.get('current_locked_p1_id'),
            'locked_opp_id': request.form.get('current_locked_opp_id')
        })

        # If user chose a fighter directly, lock them in
        if selected_data['p1_selection_method'] == 'direct_choice':
            p1_chosen_fighter_id_form = request.form.get('p1_chosen_fighter')
            if p1_chosen_fighter_id_form:
                selected_data['p1_chosen_fighter_id'] = p1_chosen_fighter_id_form
                # This action locks the chosen fighter
                action = f"lock_p1:{p1_chosen_fighter_id_form}"

        # Process lock/unlock actions from buttons
        if action.startswith('lock_p1:'): selected_data['locked_p1_id'] = action.split(':')[1]
        elif action == 'unlock_p1': selected_data['locked_p1_id'] = None
        elif action.startswith('lock_opp:'): selected_data['locked_opp_id'] = action.split(':')[1]
        elif action == 'unlock_opp': selected_data['locked_opp_id'] = None
        
        results_data = {'p1_main': None, 'p1_alternatives': [], 'opp_main': None, 'opp_alternatives': []}
        available_fighters = get_available_fighters(selected_data['owned_sets'])

        if not selected_data['owned_sets']:
            error_message = 'Please select at least one owned set to get suggestions.'
        elif not available_fighters:
            error_message = 'No fighters available from the selected sets.'
        else:
            # Generate suggestions
            exclude_ids = [fid for fid in [selected_data['locked_p1_id'], selected_data['locked_opp_id']] if fid]
            
            if selected_data['locked_p1_id']:
                results_data['p1_main'] = find_fighter_by_id(selected_data['locked_p1_id'])
            else:
                p1_sugg = get_smart_suggestions(available_fighters, selected_data['p1_playstyles'], selected_data['p1_range'], exclude_ids=exclude_ids)
                results_data.update(p1_main=p1_sugg['main'], p1_alternatives=p1_sugg['alternatives'])
                if p1_sugg['main']: exclude_ids.append(p1_sugg['main']['id'])
            
            if selected_data['locked_opp_id']:
                results_data['opp_main'] = find_fighter_by_id(selected_data['locked_opp_id'])
            else:
                opp_sugg = get_smart_suggestions(available_fighters, selected_data['opp_playstyles'], selected_data['opp_range'], exclude_ids=exclude_ids)
                results_data.update(opp_main=opp_sugg['main'], opp_alternatives=opp_sugg['alternatives'])

    return render_template('index.html',
                           all_sets_list=ALL_SETS_LIST, all_playstyles=ALL_PLAYSTYLES, all_ranges=ALL_RANGES,
                           all_fighters_for_select=initial_all_fighters_for_p1_select,
                           results=results_data, selected_data=selected_data, error_message=error_message)

if __name__ == '__main__':
    app.run(debug=True, port=5001)