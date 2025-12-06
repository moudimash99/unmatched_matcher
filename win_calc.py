import pandas as pd
import json
import math
import re
from collections import defaultdict

EXCEL_FILE = "Unmatched stats.xlsx"
FIGHTERS_FILE = "fighters.json"   # save your big JSON here


# ---------------------------------------------------
# 1. Load fighters and build name -> id map
# ---------------------------------------------------

with open(FIGHTERS_FILE, "r", encoding="utf-8") as f:
    fighters_data = json.load(f)

# Map from fighter display name -> id, e.g. "King Arthur" -> "king_arthur"
FIGHTER_NAME_TO_ID = {
    f["name"]: f["id"]
    for f in fighters_data["fighters"]
}


# ---------------------------------------------------
# 2. Helpers for parsing Excel + deck name normalization
# ---------------------------------------------------

def normalize_main_col(name):
    """Strip the '\\n(Click to sort Ascending)' junk from column names."""
    if isinstance(name, str):
        return name.split("\n")[0].strip()
    return name

def parse_win_cell(x):
    """
    Parse a Win% cell.
    - Returns float(0–100) if real value.
    - Returns None for empty, '-', or the sentinel -2 (string or numeric).
    """
    try:
        if x is None:
            return None

        if isinstance(x, str):
            s = x.strip()
            if s == "" or s == "-":
                return None
            if s == "-2":
                return None
            s = s.replace("%", "").strip()
            v = float(s)
        else:
            v = float(x)

        if math.isnan(v):
            return None
        if v == -2:
            return None

        return v
    except Exception:
        return None


# Manual aliasing from Excel deck names -> *fighter display names*
# (after stripping " - Alt 1.0" suffix)
NAME_ALIAS_TO_FIGHTER_NAME = {
    # Buffy variants
    "Buffy (Giles)": "Buffy",
    "Buffy (Xander)": "Buffy",
    "Buffy Giles": "Buffy",
    "Buffy Xander": "Buffy",

    # Cloak & Dagger variants
    "Cloak & Dagger": "Cloak and Dagger",

    # Dr. Sattler variants
    "Dr. Ellie Sattler": "Dr. Sattler",

    # Houdini variants
    "Harry Houdini": "Houdini",

    # Shakespeare variants
    "Shakespeare": "William Shakespeare",

    # Witcher Yennefer/Triss variants
    "Triss (Yennefer)": "Yennefer & Triss",
    "Yennefer (Triss)": "Yennefer & Triss",
    "Triss": "Yennefer & Triss",
    "Yennefer": "Yennefer & Triss",
}


def slugify(name: str) -> str:
    """
    Fallback slug for decks that don't match any fighter.
    Example: 'Blackbeard - Alt 1.0' -> 'blackbeard_alt_1_0'
    """
    name = name.strip().lower()
    # replace non-alnum with underscore
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name


def deck_to_fighter_id(raw_name: str) -> str:
    """
    Take a raw Excel deck name and map it to a canonical fighter id.
    Steps:
      1) Strip '\n(Click to sort Ascending)' and whitespace.
      2) Strip ' - Alt ...' suffix.
      3) Apply NAME_ALIAS_TO_FIGHTER_NAME for known variants.
      4) If final display name matches a fighter, return that id.
      5) Otherwise, return a slug.
    """
    if raw_name is None:
        return None
    name = str(raw_name).strip()
    if name == "":
        return None

    # Remove Excel sort-suffix just in case
    name = normalize_main_col(name)

    # Remove alt suffixes like " - Alt 1.0", " - Alt 2.0", etc.
    name = re.sub(r"\s+-\s*Alt.*$", "", name).strip()

    # Apply manual alias to fighter display name
    fighter_display_name = NAME_ALIAS_TO_FIGHTER_NAME.get(name, name)

    # Try to map to fighter id
    fighter_id = FIGHTER_NAME_TO_ID.get(fighter_display_name)
    if fighter_id is not None:
        return fighter_id

    # Fallback: slug
    return slugify(name)


# ---------------------------------------------------
# 3. Load the four Excel matrices
# ---------------------------------------------------

def load_matrices(excel_file):
    xls = pd.ExcelFile(excel_file)

    # Overall Games Played
    gp_main_raw = pd.read_excel(xls, "Games Played", index_col=0)
    gp_main = gp_main_raw[gp_main_raw.index.map(lambda x: isinstance(x, str))].copy()
    gp_main.columns = [normalize_main_col(c) for c in gp_main.columns]

    # Keep only deck-vs-deck columns (drop 'Total' etc.)
    deck_names_main = set(gp_main.index)
    gp_main = gp_main.loc[:, [c for c in gp_main.columns if c in deck_names_main]]

    # Overall Win Percentage
    wp_main_raw = pd.read_excel(xls, "Win Percentage", index_col=0)
    wp_main = wp_main_raw[wp_main_raw.index.map(lambda x: isinstance(x, str))].copy()
    wp_main.columns = [normalize_main_col(c) for c in wp_main.columns]
    wp_main = wp_main.loc[wp_main.index.intersection(deck_names_main),
                          [c for c in wp_main.columns if c in deck_names_main]]

    # UMLeague Games Played
    gp_um = pd.read_excel(xls, "Games Played UMLeague", index_col=0)

    # UMLeague Win Percentage
    wp_um = pd.read_excel(xls, "Win Percentage UMLeague", index_col=0)

    return gp_main, wp_main, gp_um, wp_um


# ---------------------------------------------------
# 4. Merge into fighter-id keyed JSON
# ---------------------------------------------------

def merge_sources_to_fighter_ids(gp_main, wp_main, gp_um, wp_um):
    """
    Aggregate both sources directly into fighter-id keyed matrices:
      - merged_games[f1][f2] = total games
      - merged_win_pct[f1][f2] = weighted win% or -2
    Where f1, f2 are fighter ids (e.g. 'king_arthur', 'buffy', 'muhammad_ali')
    """
    merged_games = defaultdict(lambda: defaultdict(int))
    win_num = defaultdict(lambda: defaultdict(float))   # accumulated wins
    win_den = defaultdict(lambda: defaultdict(int))     # games where we have a win%

    def accumulate_from_source(gp, wp):
        # For each cell in this source, map row/col to fighter ids and accumulate
        for row_name in gp.index:
            f1 = deck_to_fighter_id(row_name)
            if f1 is None:
                continue

            for col_name in gp.columns:
                f2 = deck_to_fighter_id(col_name)
                if f2 is None:
                    continue

                g = gp.at[row_name, col_name]
                g = 0 if pd.isna(g) else int(g)

                # Always accumulate games (even 0 keeps entries present later if we want)
                merged_games[f1][f2] += g

                # Win%
                w = None
                if (row_name in wp.index) and (col_name in wp.columns):
                    w = parse_win_cell(wp.at[row_name, col_name])

                if w is not None and g > 0:
                    win_num[f1][f2] += (w / 100.0) * g
                    win_den[f1][f2] += g

    # Accumulate from both sources
    accumulate_from_source(gp_main, wp_main)
    accumulate_from_source(gp_um, wp_um)

    # Now build final win% matrix, filling -2 where we have no usable win% data
    merged_win_pct = defaultdict(dict)
    all_fighter_ids = set(FIGHTER_NAME_TO_ID.values()) | set(merged_games.keys())

    # Make the matrix full over all fighter ids seen + defined
    for f1 in all_fighter_ids:
        if f1 not in merged_games:
            merged_games[f1] = {}
        if f1 not in merged_win_pct:
            merged_win_pct[f1] = {}

        for f2 in all_fighter_ids:
            # Games: if never seen, default to 0
            g = merged_games[f1].get(f2, 0)
            merged_games[f1][f2] = g

            # Win%: use weighted avg if we have data, else -2
            if win_den[f1][f2] == 0:
                merged_win_pct[f1][f2] = -2
            else:
                merged_win_pct[f1][f2] = 100.0 * win_num[f1][f2] / win_den[f1][f2]

    return merged_games, merged_win_pct


# ---------------------------------------------------
# 5. Run + dump JSON
# ---------------------------------------------------

if __name__ == "__main__":
    gp_main, wp_main, gp_um, wp_um = load_matrices(EXCEL_FILE)
    merged_games, merged_win_pct = merge_sources_to_fighter_ids(
        gp_main, wp_main, gp_um, wp_um
    )

    with open("merged_games.json", "w", encoding="utf-8") as f:
        json.dump(merged_games, f, indent=2, ensure_ascii=False)

    with open("merged_win_pct.json", "w", encoding="utf-8") as f:
        json.dump(merged_win_pct, f, indent=2, ensure_ascii=False)
