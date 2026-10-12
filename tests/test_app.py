import json
import os

import pytest

from app import (app, engine, FIGHTERS_DATA, ALL_SETS_LIST, WIN_MATRIX, PLAYSTYLE_DEFINITIONS,
                 RANGE_ORDER, get_available_fighters)
from matchup_engine import FULL_CONFIDENCE_GAMES

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_fighter_ids_and_names_are_unique():
    ids = [f["id"] for f in FIGHTERS_DATA]
    names = [f["name"] for f in FIGHTERS_DATA]
    assert len(ids) == len(set(ids))
    assert len(names) == len(set(names))


def test_every_fighter_image_exists_with_exact_case():
    # Linux (the Docker deploy) is case-sensitive, so compare exact filenames
    pics = set(os.listdir(os.path.join(ROOT_DIR, "static", "pics")))
    missing = [
        f["id"] for f in FIGHTERS_DATA
        if os.path.basename(f["image_url"]) not in pics
    ]
    assert missing == []


def test_every_fighter_is_in_the_win_matrix():
    assert {f["id"] for f in FIGHTERS_DATA} <= set(WIN_MATRIX)


def test_bruce_lee_is_one_fighter_in_both_sets():
    lees = [f for f in FIGHTERS_DATA if f["name"] == "Bruce Lee"]
    assert len(lees) == 1
    assert set(lees[0]["sets"]) == {"Bruce Lee", "Muhammad Ali vs. Bruce Lee"}
    assert "Muhammad Ali vs. Bruce Lee" in ALL_SETS_LIST

    for owned in (["Bruce Lee"], ["Muhammad Ali vs. Bruce Lee"],
                  ["Bruce Lee", "Muhammad Ali vs. Bruce Lee"]):
        ids = [f["id"] for f in get_available_fighters(owned)]
        assert ids.count("bruce_lee") == 1


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_ali_vs_lee_box_alone_builds_a_matchup(client):
    resp = client.post("/", data={"owned_sets": ["Muhammad Ali vs. Bruce Lee"]})
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'id="p1-main-suggestion"' in html
    assert 'id="opp-main-suggestion"' in html


def test_no_owned_sets_shows_error(client):
    resp = client.post("/", data={})
    assert "Please select at least one owned set." in resp.get_data(as_text=True)


def test_direct_choice_is_kept_selected(client):
    resp = client.post("/", data={
        "owned_sets": ALL_SETS_LIST,
        "p1_selection_method": "direct_choice",
        "p1_chosen_fighter": "loki",
    })
    html = resp.get_data(as_text=True)
    assert '<option value="loki" data-set="Battle of Legends Vol. 3" selected>' in html


def test_unknown_matchup_renders_estimate_not_sentinel(client):
    ids = [f["id"] for f in FIGHTERS_DATA]
    a, b = next((a, b) for a in ids for b in ids
                if a != b and engine.lookup_win_rate(a, b) is None)

    resp = client.post("/", data={
        "owned_sets": ALL_SETS_LIST,
        "current_locked_p1_id": a,
        "current_locked_opp_id": b,
    })
    html = resp.get_data(as_text=True)
    assert "-2%" not in html
    assert "estimate, no games yet" in html


def test_well_played_matchup_shows_games_and_club_link(client):
    resp = client.post("/", data={
        "owned_sets": ALL_SETS_LIST,
        "current_locked_p1_id": "medusa",
        "current_locked_opp_id": "sinbad",
    })
    html = resp.get_data(as_text=True)
    games = engine.games_played("medusa", "sinbad")
    assert games >= FULL_CONFIDENCE_GAMES
    assert f"{round(engine.estimate_win_rate('medusa', 'sinbad'))}% " in html
    assert f"{games:,} games" in html
    assert "tools/matchups?h1=medusa&amp;h2=sinbad" in html


def test_shared_link_reopens_the_matchup(client):
    resp = client.get("/?p1=loki&opp=krang")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'id="p1-main-suggestion" class="fighter-card main-suggestion" data-fighter-id="loki"' in html
    assert 'id="opp-main-suggestion" class="fighter-card main-suggestion" data-fighter-id="krang"' in html
    # Without sets in the link, the two fighters' own boxes are selected
    assert 'value="Battle of Legends Vol. 3" checked' in html
    assert 'value="TMNT: Shredder vs. Krang" checked' in html


def test_fighter_tags_and_ranges_use_defined_values():
    defs = PLAYSTYLE_DEFINITIONS
    for f in FIGHTERS_DATA:
        assert len(f["major"]) == 1 and set(f["major"]) <= set(defs["major"]), f["id"]
        assert 1 <= len(f["minor"]) <= 3 and set(f["minor"]) <= set(defs["minor"]), f["id"]
        assert not set(f["major"]) & set(f["minor"]), f["id"]
        assert f["range"] in RANGE_ORDER, f["id"]
        assert f["club_key"], f["id"]
