import json
import sys
from pathlib import Path

import pytest

import map_stats
from map_stats import MapStats
from matchup_engine import MatchupEngine

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_map_stats  # noqa: E402
import scrape_ttl_fighter_stats as ttl_grid  # noqa: E402
import scrape_ttl_matches as ttl  # noqa: E402


# ---------------------------------------------------------------------------
# Scraper: page parsing and name mapping
# ---------------------------------------------------------------------------

def _side(fighter, player, badge, health, won, align="left"):
    name_cls = "text-lg font-bold" + (" text-success" if won else " text-muted-foreground")
    return f'''<div class="flex items-center gap-4 flex-1 {align}">
      <div class="relative"><div class="absolute top-0 z-10 bg-black/70 text-[10px]">{badge}</div></div>
      <div class="flex flex-col">
        <span class="{name_cls}"><span class="truncate min-w-0" title="{fighter}">{fighter}</span></span>
        <span class="text-xs text-muted-foreground uppercase tracking-wider font-medium truncate">{player}</span>
        <div><span role="img" aria-label="Ending health {health}{', defeated' if health <= 0 else ''}"><span aria-hidden="true">HP: {health}</span></span></div>
      </div></div>'''


def _game(index, map_name, a, b):
    return f'''<div data-slot="card" class="rounded-xl">
      <div class="relative z-10 p-4 hidden sm:flex items-center">
        {_side(*a)}
        <div class="relative shrink-0"><div><div>
          <span class="text-[10px] uppercase tracking-widest">Game {index}</span>
          <span class="text-[9px]">{map_name}</span>
        </div></div></div>
        {_side(*b, align="right")}
      </div>
      <div class="relative z-10 p-3 sm:hidden space-y-3">{_side(*a)}</div>
    </div>'''


def _page(games, draft=False, team=False):
    flight = '{\\"isTeamMatch\\":%s}' % ("true" if team else "false")
    return f'''<html><body>
    <div><div><h1>QF 2</h1><span title="Completed"><svg></svg></span><div>Completed</div></div></div>
    <div><a href="/o/some-org/summer-cup">Summer Cup</a><span>•</span><span>BO3</span><span>•</span>
      <span>Banquest +1 (2/5/2)</span><span><span>•</span><span>Oct 12, 2026, 4:33 PM UTC</span></span></div>
    <h3>Game Details</h3>{"".join(games)}
    {"<h3>Draft Details</h3>" if draft else ""}
    <script>self.__next_f.push([1,"{flight}"])</script>
    </body></html>'''


@pytest.fixture
def mapper():
    fighters = [
        {"id": "yennefer_triss", "name": "Yennefer & Triss", "club_key": "yennefer-triss"},
        {"id": "michelangelo", "name": "Michelangelo", "club_key": "michelangelo"},
        {"id": "the_golden_bat", "name": "The Golden Bat", "club_key": "golden-bat"},
        {"id": "cloak_and_dagger", "name": "Cloak and Dagger", "club_key": "cloak-dagger"},
    ]
    maps = {"the-white-house": {"key": "the-white-house", "name": "The White House"},
            "tsing-shan-monastery": {"key": "tsing-shan-monastery", "name": "Tsing Shan Monastery"}}
    return ttl.NameMapper(fighters, maps)


def test_parse_match_page_reads_every_game():
    html = _page([
        _game(1, "The White House", ("Yennefer", "domingo", "P1", 3, True), ("Michelangelo", "SledeB", "P2", 0, False)),
        _game(2, "Tsing Shan Monestary", ("Golden Bat", "domingo", "P2", 7, True), ("Michelangelo", "SledeB", "P1", -3, False)),
    ], draft=True)
    raw = ttl.parse_match_page(html)
    assert raw["status"] == "Completed"
    assert (raw["competition"], raw["organizer"], raw["format"]) == ("Summer Cup", "some-org", "BO3")
    assert raw["ruleset"] == "Banquest +1 (2/5/2)"
    assert raw["played_at"] == "2026-10-12"
    assert raw["draft"] and not raw["team"]
    assert [g["index"] for g in raw["games"]] == [1, 2]  # the mobile copy isn't read twice
    g2 = raw["games"][1]
    assert g2["map"] == "Tsing Shan Monestary"
    assert g2["a"] == {"fighter": "Golden Bat", "player": "domingo", "went_first": False, "end_health": 7, "won": True}
    assert g2["b"]["end_health"] == -3 and g2["b"]["went_first"] is True and not g2["b"]["won"]


def test_normalize_maps_names_and_aliases(mapper):
    html = _page([
        _game(1, "The White House", ("Yennefer", "x", "P1", 3, True), ("Michelangelo", "y", "P2", 0, False)),
        _game(2, "Tsing Shan Monestary", ("Golden Bat", "x", "P2", 7, True), ("Cloak & Dagger", "y", "P1", 0, False)),
    ], draft=True)
    skipped, unmapped = {}, ttl._empty_unmapped()
    games = list(ttl.normalize_match("m1", ttl.parse_match_page(html), mapper, skipped, unmapped))
    assert [(g["a"]["fighter"], g["b"]["fighter"], g["map"]) for g in games] == [
        ("yennefer_triss", "michelangelo", "the-white-house"),
        ("the_golden_bat", "cloak_and_dagger", "tsing-shan-monastery"),
    ]
    assert games[0]["selection"] == "pickBan" and games[0]["game_index"] == 1
    assert skipped == {} and unmapped == {"fighters": {}, "maps": {}}


def test_normalize_logs_unknown_names_and_skips_bad_games(mapper):
    html = _page([
        _game(1, "Moon Base", ("Michelangelo", "x", "P1", 3, True), ("Yennefer", "y", "P2", 0, False)),
        _game(2, "The White House", ("Hellboy", "x", "P1", 3, True), ("Michelangelo", "y", "P2", 0, False)),
        _game(3, "The White House", ("Michelangelo", "x", "P1", 3, True), ("Michelangelo", "y", "P2", 0, False)),
        _game(4, "The White House", ("Unknown", "x", "P1", 0, False), ("Michelangelo", "y", "P2", 0, False)),
    ])
    skipped, unmapped = {}, ttl._empty_unmapped()
    assert list(ttl.normalize_match("m1", ttl.parse_match_page(html), mapper, skipped, unmapped)) == []
    assert unmapped == {"fighters": {"Hellboy": 1}, "maps": {"Moon Base": 1}}
    assert skipped == {"unmapped_name": 2, "mirror": 1, "missing_fighter": 1}


def test_normalize_infers_winner_from_health_and_skips_team_matches(mapper):
    no_highlight = _game(1, "The White House", ("Yennefer", "x", "P1", 4, False), ("Michelangelo", "y", "P2", 0, False))
    [game] = ttl.normalize_match("m", ttl.parse_match_page(_page([no_highlight])), mapper, {}, ttl._empty_unmapped())
    assert game["a"]["won"] and not game["b"]["won"]

    skipped = {}
    team = ttl.parse_match_page(_page([no_highlight], team=True))
    assert list(ttl.normalize_match("m", team, mapper, skipped, ttl._empty_unmapped())) == []
    assert skipped == {"team_or_double": 1}


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _rec(match, idx, a, b, m, a_won, a_first=True, a_hp=None, b_hp=None):
    if a_hp is None:
        a_hp, b_hp = (5, 0) if a_won else (0, 5)
    return {"match_id": match, "game_index": idx, "played_at": f"2026-10-{10 + idx:02d}", "map": m,
            "a": {"fighter": a, "went_first": a_first, "end_health": a_hp, "won": a_won},
            "b": {"fighter": b, "went_first": not a_first, "end_health": b_hp, "won": not a_won}}


def test_build_counts_are_symmetric(tmp_path):
    games = [
        _rec("m1", 1, "ace", "bea", "alamo", True, a_first=True, a_hp=6, b_hp=0),
        _rec("m1", 2, "bea", "ace", "alamo", True, a_first=True, a_hp=2, b_hp=-1),
        _rec("m2", 1, "ace", "bea", "venice", True, a_first=False, a_hp=4, b_hp=0),
    ]
    path = tmp_path / "games.jsonl"
    path.write_text("\n".join(json.dumps(g) for g in games + games[:1]) + "\n")  # one duplicate line
    stats = build_map_stats.build(build_map_stats.read_games(path))

    assert stats["meta"]["games"] == 3 and stats["meta"]["matches"] == 2
    assert (stats["meta"]["from"], stats["meta"]["to"]) == ("2026-10-11", "2026-10-12")
    assert stats["fighter_map"]["ace"]["alamo"] == {"games": 2, "wins": 1}
    assert stats["fighter_map"]["bea"]["alamo"] == {"games": 2, "wins": 1}
    mm = stats["matchup_map"]
    for a, b in (("ace", "bea"), ("bea", "ace")):
        for m in mm[a][b]:
            assert mm[a][b][m]["games"] == mm[b][a][m]["games"]
            assert mm[a][b][m]["wins_a"] + mm[b][a][m]["wins_a"] == mm[a][b][m]["games"]
    assert mm["ace"]["bea"]["venice"] == {"games": 1, "wins_a": 1}
    # First player won games 1 and 2; went second and won game 3
    assert stats["first_player"]["ace"]["bea"] == stats["first_player"]["bea"]["ace"] == {"games": 3, "first_wins": 2}
    assert stats["map_first_player"] == {"alamo": {"games": 2, "first_wins": 2}, "venice": {"games": 1, "first_wins": 0}}
    assert stats["closeness"]["ace"]["bea"] == {"games": 3, "winner_health_sum": 12}


# ---------------------------------------------------------------------------
# Estimates
# ---------------------------------------------------------------------------

FIGHTERS = [{"id": fid, "name": fid.title(), "sets": ["Box"]} for fid in ("ace", "bea", "cal")]
MAPS = {"alamo": {"key": "alamo", "name": "The Alamo", "set": "Box A"},
        "venice": {"key": "venice", "name": "Venice", "set": "Box B"},
        "empty": {"key": "empty", "name": "Empty", "set": "Box A"}}


@pytest.fixture
def engine():
    win = {"ace": {"bea": 60.0, "cal": 50.0}, "bea": {"cal": 50.0}}
    games = {"ace": {"bea": 100, "cal": 100}, "bea": {"cal": 100}}
    return MatchupEngine(FIGHTERS, win, games)


def _stats(games):
    return build_map_stats.build(games)


def test_no_map_data_falls_back_to_overall_numbers(engine):
    ms = MapStats(engine, {}, MAPS)
    assert not ms.has_data
    assert ms.lean("ace", "alamo") == 0.0
    assert ms.matchup_on_map("ace", "bea", "alamo")["win_pct"] == pytest.approx(engine.estimate_win_rate("ace", "bea"))
    assert ms.map_suggestions("ace", "bea")["fairest"] == []
    assert ms.first_player("ace", "bea") == {"win_pct": 50.0, "games": 0, "low_data": True}
    assert ms.closeness("ace", "bea") is None


def test_lean_is_relative_to_the_fighters_scraped_record(engine):
    # ace wins 10/10 on alamo and 0/10 on venice: 50% in the sample overall
    games = [_rec("a", i, "ace", "cal", "alamo", True) for i in range(10)] + \
            [_rec("v", i, "ace", "cal", "venice", False) for i in range(10)]
    ms = MapStats(engine, _stats(games), MAPS)
    assert ms.lean("ace", "alamo") > 3 and ms.lean("ace", "venice") < -3
    assert ms.lean("ace", "alamo") == pytest.approx(-ms.lean("ace", "venice"))
    # Full confidence at 10 games: the 100% is clamped to 99%, then applied to ace's overall rate
    on_alamo = ms.fighter_on_map("ace", "alamo")
    assert on_alamo["win_pct"] == pytest.approx(99.0) and not on_alamo["low_data"]
    assert ms.fighter_maps("ace")[0]["map"]["key"] == "alamo"


def test_thin_map_data_is_blended_toward_no_lean(engine):
    games = [_rec("a", 1, "ace", "cal", "alamo", True), _rec("v", 1, "ace", "cal", "venice", False)]
    ms = MapStats(engine, _stats(games), MAPS)
    one_game = ms.fighter_on_map("ace", "alamo")
    assert one_game["low_data"] and one_game["games"] == 1
    c = MatchupEngine.confidence(1, map_stats.MAP_FULL_CONFIDENCE_GAMES)
    assert one_game["win_pct"] - engine.overall_win_rate("ace") < 50 * c + 1  # far from a 100% blowout


def test_matchup_on_map_uses_leans_then_its_own_record(engine):
    # ace strong on alamo vs cal, bea weak on alamo vs cal; ace and bea never met on alamo
    games = [_rec("a", i, "ace", "cal", "alamo", True) for i in range(5)] + \
            [_rec("b", i, "bea", "cal", "alamo", False) for i in range(5)] + \
            [_rec("c", i, "ace", "cal", "venice", False) for i in range(5)] + \
            [_rec("d", i, "bea", "cal", "venice", True) for i in range(5)]
    ms = MapStats(engine, _stats(games), MAPS)
    base = engine.estimate_win_rate("ace", "bea")
    on_alamo = ms.matchup_on_map("ace", "bea", "alamo")
    assert on_alamo["games"] == 0 and on_alamo["win_pct"] > base
    assert ms.matchup_on_map("ace", "bea", "venice")["win_pct"] < base
    # Symmetric: B's view is the complement
    assert ms.matchup_on_map("bea", "ace", "alamo")["win_pct"] == pytest.approx(100 - on_alamo["win_pct"])

    sugg = ms.map_suggestions("ace", "bea")
    assert sugg["count"] == 2  # "empty" has no data for either fighter
    assert [r["map"]["key"] for r in sugg["favor_a"]] == ["alamo"]
    assert [r["map"]["key"] for r in sugg["favor_b"]] == ["venice"]
    # Only maps from owned sets
    owned_b = ms.map_suggestions("ace", "bea", ["Box B"])
    assert owned_b["count"] == 1 and [r["map"]["key"] for r in owned_b["favor_b"]] == ["venice"]
    # Lopsided maps are never listed as fair
    assert all(abs(r["win_pct"] - 50) <= map_stats.FAIR_MAP_BAND for r in sugg["fairest"])
    assert "alamo" not in [r["map"]["key"] for r in sugg["fairest"]]


def test_first_player_and_closeness_blend_with_overall(engine):
    games = [_rec("m", i, "ace", "bea", "alamo", True, a_first=True, a_hp=2, b_hp=0) for i in range(3)] + \
            [_rec("n", i, "bea", "cal", "alamo", True, a_first=False, a_hp=8, b_hp=0) for i in range(3)]
    ms = MapStats(engine, _stats(games), MAPS)
    assert ms.first_player_pct == 50.0
    fp = ms.first_player("ace", "bea")
    assert fp["games"] == 3 and fp["low_data"] and 50.0 < fp["win_pct"] < 100.0
    close = ms.closeness("ace", "bea")
    assert ms.avg_winner_health == pytest.approx(5.0)
    assert 2.0 < close["winner_health"] < 5.0
    panel = ms.matchup_panel("ace", "bea", ["Box A"])
    assert panel["first"]["games"] == 3 and panel["closeness"]["games"] == 3
    assert {r["key"] for r in panel["suggested"]} <= {"alamo", "empty"}  # Box A's maps only
    assert set(panel["by_map"]) == {"alamo", "empty"}


def test_suggested_maps_include_one_map_from_each_fighters_box(engine):
    many = {f"m{i}": {"key": f"m{i}", "name": f"Map {i}", "set": "Big Box"} for i in range(10)}
    many["home1"] = {"key": "home1", "name": "Home 1", "set": "Ace Box"}
    many["home2"] = {"key": "home2", "name": "Home 2", "set": "Ace Box"}
    # ace crushes bea on both home maps (home2 a bit less), so they're the least fair maps
    games = [_rec("h", i, "ace", "bea", "home1", True) for i in range(10)] +             [_rec("j", i, "ace", "bea", "home2", i < 8) for i in range(10)] +             [_rec(f"g{i}", 1, "ace", "bea", f"m{i}", i % 2 == 0) for i in range(10)]
    ms = MapStats(engine, _stats(games), many)
    unfair = {k: abs(ms.matchup_on_map("ace", "bea", k)["win_pct"] - 50) for k in many}
    plain = [r["map"]["key"] for r in ms.suggested_maps("ace", "bea", ["Big Box", "Ace Box"])]
    assert plain == sorted(unfair, key=unfair.get)[:map_stats.SUGGESTED_MAPS]  # just the fairest 7
    assert "home1" not in plain  # 10-0 is the least fair map
    # Only Big Box owned: ace's box still gets in, with just its fairer map; bea's box has no maps
    with_home = ms.suggested_maps("ace", "bea", ["Big Box"], home_sets=(["Ace Box"], ["Bea Box"]))
    keys = [r["map"]["key"] for r in with_home]
    assert len(keys) == map_stats.SUGGESTED_MAPS
    assert [k for k in keys if k.startswith("home")] == ["home2"]
    others = sorted((k for k in many if not k.startswith("home")), key=unfair.get)
    assert sorted(k for k in keys if k != "home2") == sorted(others[:map_stats.SUGGESTED_MAPS - 1])
    gaps = [abs(r["win_pct"] - 50) for r in with_home]
    assert gaps == sorted(gaps)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@pytest.fixture
def client_with_maps(monkeypatch):
    import app as app_module
    maps = {"globe-theatre": {"key": "globe-theatre", "name": "Globe Theatre", "set": "Slings and Arrows"},
            "marmoreal": {"key": "marmoreal", "name": "Marmoreal", "set": "Battle of Legends Vol. 1"}}
    games = [_rec("m", i, "medusa", "alice", "marmoreal", i % 3 != 0) for i in range(6)] + \
            [_rec("n", i, "medusa", "sinbad", "globe-theatre", i % 2 == 0) for i in range(4)]
    ms = MapStats(app_module.engine, _stats(games), maps)
    monkeypatch.setattr(app_module, "map_engine", ms)
    monkeypatch.setattr(app_module, "MAP_META", ms.meta)
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def test_matchup_page_embeds_map_panels_for_every_pairing(client_with_maps):
    resp = client_with_maps.get("/?p1=medusa&opp=alice&sets=Battle of Legends Vol. 1")
    html = resp.get_data(as_text=True)
    assert 'id="map-panel"' in html
    panels = json.loads(html.split("const MAP_PANELS = ", 1)[1].split(";\n", 1)[0])
    assert "medusa|alice" in panels
    panel = panels["medusa|alice"]
    listed = {r["key"] for kind in ("suggested", "favor_a", "favor_b") for r in panel[kind]}
    assert panel["maps_considered"] == 1 and listed <= {"marmoreal"}  # Globe Theatre's set isn't owned
    assert set(panel["by_map"]) == {"marmoreal"} and panel["suggested"][0]["home"]
    info = json.loads(html.split("const MAP_INFO = ", 1)[1].split(";\n", 1)[0])
    assert info["marmoreal"]["name"] == "Marmoreal"
    # A chosen map (from a shared link) is kept in the form
    html = client_with_maps.get("/?p1=medusa&opp=alice&map=marmoreal").get_data(as_text=True)
    assert 'name="map" value="marmoreal"' in html
    assert panel["first"]["games"] == 6
    assert "Map and turn-order stats from 10 games" in html


def test_fighter_page_lists_maps(client_with_maps):
    html = client_with_maps.get("/fighter/medusa").get_data(as_text=True)
    assert "<h2>Maps</h2>" in html and "Globe Theatre" in html and "Marmoreal" in html
    assert "Map and turn-order stats from 10 games" in html


def test_footer_credits_fighter_pages_and_the_turn_order_sample(client_with_maps, monkeypatch):
    import app as app_module
    meta = {"map_source": "fighter_pages", "map_games": 123456, "map_fetched": "2026-10-13",
            "games": 204, "from": "2026-10-09", "to": "2026-10-12"}
    monkeypatch.setattr(app_module, "MAP_META", meta)
    for url in ("/?p1=medusa&opp=alice", "/fighter/medusa"):
        html = " ".join(client_with_maps.get(url).get_data(as_text=True).split())
        assert "Map stats from 123,456 games (all time, as of 2026-10-13); turn order from 204 recent games" in html


def test_pages_render_without_map_data(monkeypatch):
    import app as app_module
    monkeypatch.setattr(app_module, "map_engine", MapStats(app_module.engine, {}, {}))
    monkeypatch.setattr(app_module, "MAP_META", {})
    with app_module.app.test_client() as c:
        home = c.get("/?p1=medusa&opp=alice").get_data(as_text=True)
        assert 'id="map-panel"' not in home and "const MAP_PANELS = {}" in home
        assert "<h2>Maps</h2>" not in c.get("/fighter/medusa").get_data(as_text=True)


# ---------------------------------------------------------------------------
# Fighter page grids
# ---------------------------------------------------------------------------

def _grid_response(opponents, maps):
    """A server-action response the way a fighter stats page receives it."""
    grid = {"opponents": opponents, "maps": maps, "grandTotal": {"plays": 0, "wins": 0}}
    return '0:{"a":"$@1","q":"","i":false}\n1:' + json.dumps(grid) + "\n"


def _opp(name, slug, cells):
    plays = sum(c["plays"] for c in cells.values())
    return {"id": slug, "name": name, "slug": slug, "totalPlays": plays, "cells": cells}


GRID_MAPS = [{"id": "m-wh", "name": "The White House", "slug": "the-white-house", "totalPlays": 12},
             {"id": "m-tsm", "name": "Tsing Shan Monestary", "slug": "tsing-shan-monestary", "totalPlays": 5},
             {"id": "m-moon", "name": "Moon Base", "slug": "moon-base", "totalPlays": 2}]


def test_parse_grid_response_finds_the_grid_line():
    text = _grid_response([], GRID_MAPS)
    assert ttl_grid.parse_grid_response(text)["maps"][0]["name"] == "The White House"
    assert ttl_grid.parse_grid_response('0:{"a":"$@1"}\n1:{"other":1}\n') is None


def test_normalize_grid_maps_names_and_logs_the_rest(mapper):
    grid = ttl_grid.parse_grid_response(_grid_response([
        _opp("Yennefer & Triss", "yennefer-triss", {"m-wh": {"plays": 10, "wins": 6}, "m-tsm": {"plays": 5, "wins": 1}}),
        _opp("Golden Bat", "golden-bat", {"m-wh": {"plays": 2, "wins": 2}, "m-moon": {"plays": 2, "wins": 1}}),
        _opp("Hellboy", "hellboy", {"m-wh": {"plays": 3, "wins": 0}}),
        _opp("Golden Bat - Alt 1.0", "golden-bat-alt-1-0", {"m-wh": {"plays": 1, "wins": 1}}),
    ], GRID_MAPS))
    unmapped = ttl._empty_unmapped()
    out = ttl_grid.normalize_grid("michelangelo", grid, mapper, unmapped)

    assert out["vs"]["yennefer_triss"] == {"the-white-house": {"games": 10, "wins": 6},
                                           "tsing-shan-monastery": {"games": 5, "wins": 1}}
    assert out["vs"]["the_golden_bat"] == {"the-white-house": {"games": 2, "wins": 2}}  # Moon Base left out
    assert out["maps"] == {"the-white-house": {"games": 12, "wins": 8}, "tsing-shan-monastery": {"games": 5, "wins": 1}}
    assert (out["games"], out["wins"]) == (17, 9)
    assert unmapped == {"fighters": {"Hellboy": 3}, "maps": {"Moon Base": 2},
                        "alt_versions": {"Golden Bat - Alt 1.0": 1}}


def test_grid_tables_use_each_fighters_page_and_fill_in_missing_sides():
    grids = {
        "ace": {"games": 5, "wins": 3, "maps": {"alamo": {"games": 5, "wins": 3}},
                "vs": {"bea": {"alamo": {"games": 4, "wins": 3}}, "cal": {"alamo": {"games": 1, "wins": 0}}}},
        "bea": {"games": 4, "wins": 1, "maps": {"alamo": {"games": 4, "wins": 1}},
                "vs": {"ace": {"alamo": {"games": 4, "wins": 1}}}},
    }
    games = [_rec("m1", 1, "ace", "bea", "venice", True)]
    stats = build_map_stats.build(games, grids={"fighters": grids, "fetched_to": "2026-10-13"})

    mm = stats["matchup_map"]
    assert mm["ace"]["bea"]["alamo"] == {"games": 4, "wins_a": 3}
    assert mm["bea"]["ace"]["alamo"] == {"games": 4, "wins_a": 1}
    # cal has no page: its side comes from ace's page, flipped
    assert mm["cal"]["ace"]["alamo"] == {"games": 1, "wins_a": 1}
    assert stats["fighter_map"]["cal"] == {"alamo": {"games": 1, "wins": 1}}
    # Map tables ignore the match sample (venice); turn order still uses it
    assert "venice" not in stats["fighter_map"]["ace"]
    assert stats["first_player"]["ace"]["bea"]["games"] == 1
    meta = stats["meta"]
    assert (meta["map_source"], meta["map_fetched"], meta["map_games"], meta["games"]) == \
        ("fighter_pages", "2026-10-13", 5, 1)


# ---------------------------------------------------------------------------
# Explanations
# ---------------------------------------------------------------------------

def test_explanations_reach_the_numbers_shown(engine):
    games = [_rec("a", i, "ace", "cal", "alamo", True) for i in range(5)] + \
            [_rec("b", i, "bea", "cal", "alamo", False) for i in range(5)] + \
            [_rec("c", i, "ace", "bea", "alamo", i < 2) for i in range(3)] +             [_rec("d", i, "ace", "cal", "empty", False) for i in range(5)]
    ms = MapStats(engine, _stats(games), MAPS)
    e = ms.explain_on_map("ace", "bea", "alamo")
    assert e["final"] == pytest.approx(ms.matchup_on_map("ace", "bea", "alamo")["win_pct"])
    assert e["base"] == pytest.approx(engine.estimate_win_rate("ace", "bea"))
    assert (e["pair_wins"], e["pair_games"]) == (2, 3) and 0 < e["pair_conf"] < 1
    own = 100 * 2 / 3
    assert e["final"] == pytest.approx(e["pair_conf"] * own + (1 - e["pair_conf"]) * e["expected"])
    assert e["a"]["games"] == 8 and e["shift_a"] > 0  # ace does better on alamo than in all its games
    # Never played on a map: the estimate is just the overall matchup moved by both fighters' records
    none = ms.explain_on_map("ace", "bea", "venice")
    assert none["pair_games"] == 0 and none["final"] == pytest.approx(none["expected"]) == pytest.approx(none["base"])

    fp = ms.explain_first_player("ace", "bea")
    assert fp["final"] == pytest.approx(ms.first_player("ace", "bea")["win_pct"]) and fp["games"] == 3
    close = ms.explain_closeness("ace", "bea")
    assert close["final"] == pytest.approx(ms.closeness("ace", "bea")["winner_health"])

    base = engine.explain_estimate("ace", "bea")
    assert base["final"] == pytest.approx(engine.estimate_win_rate("ace", "bea"))
    assert base["games"] == 100 and base["conf"] == 1.0


def test_matchup_page_embeds_explanations(client_with_maps):
    html = client_with_maps.get("/?p1=medusa&opp=alice&sets=Battle of Legends Vol. 1").get_data(as_text=True)
    explain = json.loads(html.split("const MATCHUP_EXPLAIN = ", 1)[1].split(";\n", 1)[0])
    assert {"medusa|alice", "alice|medusa"} <= set(explain)
    panel = json.loads(html.split("const MAP_PANELS = ", 1)[1].split(";\n", 1)[0])["medusa|alice"]
    assert set(panel["explain"]["maps"]) == set(panel["by_map"])
    assert panel["explain"]["first"]["games"] == 6
    assert 'id="explain-modal"' in html
