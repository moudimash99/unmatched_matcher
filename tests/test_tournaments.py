import io
import json

import pytest

import tournaments as T
import tournaments_web


# ---------------------------------------------------------------------------
# Building brackets
# ---------------------------------------------------------------------------

def _ids(n):
    return [f"f{i:02d}" for i in range(n)]


@pytest.mark.parametrize("n, first_round, byes", [(2, 1, 0), (5, 1, 3), (8, 4, 0), (51, 19, 13)])
def test_new_bracket_uses_byes_to_reach_a_power_of_two(n, first_round, byes):
    t = T.new_tournament("Cup", ["Ann", "Ben"], _ids(n))
    r1 = [m for m in t["matches"] if m["round"] == "r1"]
    assert len(r1) == first_round
    in_r1 = {s["fighter"] for m in r1 for _, s in T.sides(m)}
    assert len(set(_ids(n)) - in_r1) == byes
    assert T.problems(t) == [] and T.final_match(t) is not None
    assert t["rounds"][-1]["name"] == "Final"
    assert sorted(T.all_fighters(t)) == _ids(n)


def test_first_round_pairs_the_fairest_matchups():
    fair = {frozenset(("a", "b")): 1.0, frozenset(("c", "d")): 0.9}
    t = T.new_tournament("Cup", ["Ann"], ["a", "c", "b", "d"], lambda x, y: fair.get(frozenset((x, y)), 0.1))
    pairs = {frozenset((m["top"]["fighter"], m["bot"]["fighter"])) for m in t["matches"] if m["round"] == "r1"}
    assert pairs == {frozenset(("a", "b")), frozenset(("c", "d"))}


def test_new_tournament_needs_fighters_and_players():
    with pytest.raises(T.TournamentError):
        T.new_tournament("Cup", ["Ann"], ["a"])
    with pytest.raises(T.TournamentError):
        T.new_tournament("Cup", [" "], ["a", "b"])


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

def _play(t, mid, side="top", player="P1"):
    t, _ = T.apply_op(t, "set_result", {"mid": mid, "winner": side, "player": player})
    return t


def test_results_flow_into_the_next_round_and_score():
    t = T.new_tournament("Cup", ["Ann", "Ben"], _ids(4))
    t = _play(t, "r1_1", "top", "P1")
    t = _play(t, "r1_2", "bot", "P2")
    final = T.final_match(t)
    assert T.status(t, final) == "ready"
    t = _play(t, final["id"], "bot", "P2")
    s = T.scores(t)
    assert s["P1"]["standard"] == 1 and s["P2"]["standard"] == 2
    assert T.final_match(t)["winner"] == "f03" or T.final_match(t)["winner"] in T.all_fighters(t)
    assert T.current_round(t) is None


def test_a_result_used_later_cant_be_undone_first():
    t = T.new_tournament("Cup", ["Ann"], _ids(4))
    t = _play(t, "r1_1")
    t = _play(t, "r1_2")
    t = _play(t, T.final_match(t)["id"])
    with pytest.raises(T.TournamentError, match="Undo that first"):
        T.apply_op(t, "undo_result", {"mid": "r1_1"})
    t, _ = T.apply_op(t, "undo_result", {"mid": T.final_match(t)["id"]})
    t, _ = T.apply_op(t, "undo_result", {"mid": "r1_1"})
    assert T.match_index(t)["r1_1"]["winner"] is None


def test_weighted_scoring_rewards_upsets():
    assert T.win_reward(30.0, "top") > 1 > T.win_reward(70.0, "top")
    assert T.win_reward(30.0, "bot") == pytest.approx(T.win_reward(70.0, "top"))
    assert T.win_reward(None, "top") == 1.0


# ---------------------------------------------------------------------------
# Editing (the Slings and Arrows case)
# ---------------------------------------------------------------------------

def test_new_fighters_join_through_play_ins_without_touching_results():
    t = T.new_tournament("Cup", ["Ann", "Ben"], _ids(8))
    for mid in ("r1_1", "r1_2", "r1_3", "r1_4"):
        t = _play(t, mid)
    played_before = {m["id"]: m["winner"] for m in t["matches"] if m["winner"]}

    t, _ = T.apply_op(t, "add_to_bench", {"fighters": ["new1", "new2", "new3"]})
    # A match the new fighters already played between themselves
    t, _ = T.apply_op(t, "add_match", {"round_id": "r1", "top": {"fighter": "new1"}, "bot": {"fighter": "new2"},
                                       "label": "Qualifier"})
    qualifier = next(m for m in t["matches"] if m["label"] == "Qualifier")
    t = _play(t, qualifier["id"], "top", "P2")
    semi = next(m for m in t["matches"] if m["round"] == "r2")
    t, _ = T.apply_op(t, "insert_play_in", {"mid": semi["id"], "side": "top", "challenger": {"fighter": "new3"}})
    t, _ = T.apply_op(t, "insert_play_in", {"mid": semi["id"], "side": "bot", "challenger": {"from": qualifier["id"]}})

    assert [r["name"] for r in t["rounds"]] == ["Quarter-finals", "Play-in for Semi-finals", "Semi-finals", "Final"]
    play_ins = [m for m in t["matches"] if m["round"] == t["rounds"][1]["id"]]
    assert len(play_ins) == 2  # both slots share one play-in round
    assert {m["id"]: m["winner"] for m in t["matches"] if m["winner"]} == {**played_before, qualifier["id"]: "new1"}
    assert t["bench"] == [] and T.problems(t) == []
    assert all(T.status(t, m) == "ready" for m in play_ins)


def test_edits_on_played_matches_are_refused_and_never_corrupt():
    t = T.new_tournament("Cup", ["Ann"], _ids(4))
    t = _play(t, "r1_1")
    for op, args in [("set_slot", {"mid": "r1_1", "side": "top", "slot": None}),
                     ("swap_slots", {"mid_a": "r1_1", "side_a": "top", "mid_b": "r1_2", "side_b": "top"}),
                     ("delete_match", {"mid": "r1_1"}),
                     ("insert_play_in", {"mid": "r1_1", "side": "top", "challenger": None})]:
        with pytest.raises(T.TournamentError):
            T.apply_op(t, op, args)
    # Sending one winner to two matches is caught by the bracket check
    final = T.final_match(t)
    with pytest.raises(T.TournamentError):
        T.apply_op(t, "set_slot", {"mid": final["id"], "side": "bot", "slot": {"from": "r1_1"}})


def test_changing_and_deleting_slots_moves_fighters_to_and_from_the_bench():
    t = T.new_tournament("Cup", ["Ann"], _ids(4))
    t, _ = T.apply_op(t, "add_to_bench", {"fighters": ["new"]})
    old = T.match_index(t)["r1_1"]["top"]["fighter"]
    t, _ = T.apply_op(t, "set_slot", {"mid": "r1_1", "side": "top", "slot": {"fighter": "new"}})
    assert t["bench"] == [old]
    t, _ = T.apply_op(t, "delete_match", {"mid": "r1_2"})
    assert len(t["bench"]) == 3 and T.final_match(t)["bot"] is None
    assert any("Empty slots" in n for n in T.notes(t))
    t, _ = T.apply_op(t, "remove_fighter", {"fighter": old})
    assert old not in T.all_fighters(t)


def test_rebalance_swaps_slots_toward_50_50():
    t = T.new_tournament("Cup", ["Ann"], ["a", "b", "c", "d"], lambda x, y: 1.0 if {x, y} in ({"a", "b"}, {"c", "d"}) else 0)
    pct = {("a", "b"): 90, ("c", "d"): 90, ("a", "c"): 50, ("b", "d"): 50, ("a", "d"): 70, ("b", "c"): 70}

    def win_pct(x, y):
        return pct.get((x, y)) or (100 - pct[(y, x)])
    t, summary = T.apply_op(t, "rebalance_round", {"round_id": "r1"}, win_pct)
    pairs = {frozenset((m["top"]["fighter"], m["bot"]["fighter"])) for m in t["matches"] if m["round"] == "r1"}
    assert pairs == {frozenset(("a", "c")), frozenset(("b", "d"))}
    assert "40.0 → 0.0" in summary


# ---------------------------------------------------------------------------
# Importing the old app
# ---------------------------------------------------------------------------

LEGACY_BRACKET = {
    "r1_1": {"id": "r1_1", "label": "Match 1", "round": 1, "top": {"type": "known", "id": "a"},
             "bot": {"type": "known", "id": "b"}, "preset_winner": "a", "winner_player": "P1"},
    "r1_2": {"id": "r1_2", "label": "Match 2", "round": 1, "top": {"type": "known", "id": "c"},
             "bot": {"type": "known", "id": "d"}, "preset_winner": None},
    "r2_1": {"id": "r2_1", "label": "R2 Match 1", "round": 2, "top": {"type": "known", "id": "e"},
             "bot": {"type": "from_match", "src": "r1_1"}, "preset_winner": None},
    "final": {"id": "final", "label": "FINAL", "round": 3, "top": {"type": "from_match", "src": "r2_1"},
              "bot": {"type": "from_match", "src": "r1_2"}, "preset_winner": None},
}


def test_import_legacy_keeps_results_players_and_layouts():
    state = {"r1_2": {"winner": "d", "side": "bot", "player": "P2"},
             "__layout": {"r2_1": {"top": {"id": "a"}, "bot": {"id": "e"}}}}
    t = T.import_legacy(LEGACY_BRACKET, state, "Old", {"P1": "Ahmad", "P2": "Mohammad"})
    ms = T.match_index(t)
    assert ms["r1_1"]["winner"] == "a" and ms["r1_1"]["player"] == "P1"
    assert ms["r1_2"]["winner"] == "d" and ms["r1_2"]["player"] == "P2"
    # The rebalance layout moved a (winner of r1_1) to the top: it keeps its link to r1_1
    assert ms["r2_1"]["top"] == {"from": "r1_1"} and ms["r2_1"]["bot"] == {"fighter": "e"}
    assert [r["name"] for r in t["rounds"]] == ["Round 1", "Round 2", "Round 3"]
    assert T.scores(t)["P1"]["standard"] == 1 and T.problems(t) == []


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def test_store_versions_conflicts_and_history(tmp_path):
    store = T.TournamentStore(str(tmp_path))
    t = store.create(T.new_tournament("Cup", ["Ann"], _ids(4)))
    assert t["version"] == 1 and store.list()[0]["id"] == t["id"]
    new, summary = T.apply_op(t, "rename", {"name": "Big cup"})
    saved = store.save(new, 1, summary)
    assert saved["version"] == 2
    with pytest.raises(T.VersionConflict):
        store.save(new, 1, summary)  # someone else saved version 2 first
    assert [h["summary"] for h in store.history(t["id"])] == ["Renamed to Big cup", "Created"]
    assert store.version(t["id"], 1)["name"] == "Cup"
    store.delete(t["id"])
    assert store.get(t["id"]) is None and store.list() == []
    assert store.get("../etc/passwd") is None


# ---------------------------------------------------------------------------
# Pages and API
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    import app as app_module
    flask_app = app_module.app
    monkeypatch.setattr(flask_app, "secret_key", "test-secret")
    monkeypatch.setitem(flask_app.config, "TOURNAMENT_PASSWORD_HASH", tournaments_web.password_hash("pw"))
    monkeypatch.setitem(flask_app.config, "TOURNAMENT_DATA_DIR", str(tmp_path))
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


def _login(c, password="pw"):
    return c.post("/tournaments/login", data={"password": password})


def test_tournaments_need_the_password(client):
    assert "Open my tournaments" in client.get("/tournaments").get_data(as_text=True)
    assert client.post("/tournaments/new", data={}).status_code == 401
    _login(client, "wrong")
    assert "Open my tournaments" in client.get("/tournaments").get_data(as_text=True)
    _login(client)
    assert "New tournament" in client.get("/tournaments").get_data(as_text=True)


def test_create_play_and_edit_over_the_api(client):
    _login(client)
    r = client.post("/tournaments/new", data={"name": "Cup", "players": ["Ann", "Ben"],
                                              "fighters": ["medusa", "sinbad", "alice", "king_arthur", "nope"]})
    tid = r.headers["Location"].rsplit("/", 1)[1]
    page = client.get(f"/tournaments/{tid}").get_data(as_text=True)
    assert "let TOURNAMENT = " in page
    view = client.get(f"/api/tournaments/{tid}").get_json()
    assert len(view["matches"]) == 3 and view["matches"][0]["win_pct"] is not None  # "nope" isn't a fighter
    assert client.get(f"/api/tournaments/{tid}?since={view['version']}").status_code == 204

    r = client.post(f"/api/tournaments/{tid}/op", json={"op": "set_result", "version": view["version"],
                                                          "args": {"mid": "r1_1", "winner": "top", "player": "P2"}})
    assert r.status_code == 200 and r.get_json()["tournament"]["scores"]["P2"]["standard"] == 1
    # A stale version is refused with the fresh tournament
    stale = client.post(f"/api/tournaments/{tid}/op", json={"op": "rename", "version": view["version"], "args": {"name": "X"}})
    assert stale.status_code == 409 and stale.get_json()["tournament"]["version"] == view["version"] + 1
    # A bad edit is refused with a message
    bad = client.post(f"/api/tournaments/{tid}/op", json={"op": "delete_match", "version": view["version"] + 1, "args": {"mid": "r1_1"}})
    assert bad.status_code == 400 and "already been played" in bad.get_json()["error"]

    history = client.get(f"/api/tournaments/{tid}/history").get_json()
    assert history[0]["summary"].startswith("Semi-finals · Match 1")  # 4 fighters: round 1 is the semis
    r = client.post(f"/api/tournaments/{tid}/restore", json={"restore": 1})
    assert r.status_code == 200 and r.get_json()["tournament"]["scores"]["P2"]["standard"] == 0


def test_import_the_old_app_over_the_page(client):
    _login(client)
    bracket = {k: dict(v) for k, v in LEGACY_BRACKET.items()}
    for m in bracket.values():
        for side in ("top", "bot"):
            if m[side].get("id"):
                m[side]["id"] = {"a": "medusa", "b": "sinbad", "c": "alice", "d": "king_arthur", "e": "dracula"}[m[side]["id"]]
    bracket["r1_1"]["preset_winner"] = "medusa"
    r = client.post("/tournaments/import", content_type="multipart/form-data", data={
        "bracket": (io.BytesIO(json.dumps(bracket).encode()), "bracket.json"),
        "state": (io.BytesIO(b"{}"), "state.json"), "name": "Old cup", "p1": "Ahmad", "p2": "Mohammad"})
    tid = r.headers["Location"].rsplit("/", 1)[1]
    view = client.get(f"/api/tournaments/{tid}").get_json()
    assert view["name"] == "Old cup" and [p["name"] for p in view["players"]] == ["Ahmad", "Mohammad"]
    assert view["scores"]["P1"]["standard"] == 1


# ---------------------------------------------------------------------------
# Slotting the bench in, logins, settings
# ---------------------------------------------------------------------------

def test_slot_in_challenges_the_fighters_who_played_least():
    # 6 fighters: round 1 has 2 matches, 2 fighters get byes into round 2
    t = T.new_tournament("Cup", ["Ann"], _ids(6))
    for m in [m for m in t["matches"] if m["round"] == "r1"]:
        t = _play(t, m["id"])
    byes = {f for f in _ids(6)} - {s["fighter"] for m in t["matches"] if m["round"] == "r1" for _, s in T.sides(m)}
    t, _ = T.apply_op(t, "add_to_bench", {"fighters": ["new1", "new2", "new3"]})
    t, summary = T.apply_op(t, "slot_in", {"round_id": "r2"}, lambda a, b: 50.0)
    newcomers = [{"fighter": f} for f in ("new1", "new2", "new3")]
    play_ins = [m for m in t["matches"] if m["bot"] in newcomers]
    challenged = {T.resolve(t, m["top"]) for m in play_ins}
    assert byes <= challenged  # both bye fighters have to play, then one winner of round 1
    assert len(challenged) == 3 and t["bench"] == [] and T.problems(t) == []
    assert "Slotted into" in summary and len(play_ins) == 3
    with pytest.raises(T.TournamentError, match="Nobody to slot in"):
        T.apply_op(t, "slot_in", {"round_id": "r2"}, lambda a, b: 50.0)


def test_wrong_passwords_lock_the_address_out_for_a_while():
    tournaments_web._failures.clear()
    addr = "203.0.113.9"
    for _ in range(tournaments_web.LOGIN_MAX_FAILURES):
        assert not tournaments_web.login_blocked(addr, now=1000)
        tournaments_web.record_failure(addr, now=1000)
    assert tournaments_web.login_blocked(addr, now=1001)
    assert not tournaments_web.login_blocked(addr, now=1000 + tournaments_web.LOGIN_WINDOW_SECONDS + 1)
    tournaments_web._failures.clear()


def test_login_lockout_over_the_page(client):
    tournaments_web._failures.clear()
    for _ in range(tournaments_web.LOGIN_MAX_FAILURES):
        _login(client, "wrong")
    r = _login(client)  # even the right password waits out the lockout
    assert "Too+many" in r.headers["Location"] or "Too%20many" in r.headers["Location"]
    tournaments_web._failures.clear()


def test_env_file_fills_missing_settings(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# comment\nUNMATCHED_TEST_A=from-file\nUNMATCHED_TEST_B='quoted'\n", encoding="utf-8")
    monkeypatch.setenv("UNMATCHED_TEST_A", "already-set")
    monkeypatch.delenv("UNMATCHED_TEST_B", raising=False)
    tournaments_web.load_env_file(str(env))
    import os
    assert os.environ["UNMATCHED_TEST_A"] == "already-set" and os.environ["UNMATCHED_TEST_B"] == "quoted"
    monkeypatch.delenv("UNMATCHED_TEST_B")


def test_store_lock_survives_a_stale_lock_file(tmp_path):
    store = T.TournamentStore(str(tmp_path))
    (tmp_path / ".lock").write_text("")
    import os
    old = os.path.getmtime(tmp_path / ".lock") - store.STALE_LOCK_SECONDS - 5
    os.utime(tmp_path / ".lock", (old, old))
    t = store.create(T.new_tournament("Cup", ["Ann"], _ids(2)))  # doesn't wait forever on the dead lock
    assert store.get(t["id"]) and not (tmp_path / ".lock").exists()


def test_bench_fights_itself_then_the_winners_slot_in():
    t = T.new_tournament("Cup", ["Ann"], _ids(6))
    for m in [m for m in t["matches"] if m["round"] == "r1"]:
        t = _play(t, m["id"])
    t, _ = T.apply_op(t, "add_to_bench", {"fighters": ["n1", "n2", "n3", "n4", "n5"]})
    fair = {frozenset(("n1", "n4")): 50.0, frozenset(("n2", "n3")): 51.0}

    def win_pct(a, b):
        return fair.get(frozenset((a, b)), 70.0)
    t, summary = T.apply_op(t, "pair_bench", {"before": "r2"}, win_pct)
    qual = t["rounds"][1]
    assert qual["name"] == "Qualifier" and t["rounds"][2]["id"] == "r2"
    pairs = {frozenset((m["top"]["fighter"], m["bot"]["fighter"])) for m in t["matches"] if m["round"] == qual["id"]}
    assert pairs == {frozenset(("n1", "n4")), frozenset(("n2", "n3"))}
    assert t["bench"] == ["n5"] and "n5 stays on the bench" in summary

    # Slot-in takes the leftover benched fighter and both qualifier winners (not decided yet)
    t, summary = T.apply_op(t, "slot_in", {"round_id": "r2"}, win_pct)
    assert t["bench"] == [] and T.open_winners(t) == [] and T.problems(t) == []
    assert summary.count(" vs ") == 3


def test_pair_bench_needs_two_and_a_place():
    t = T.new_tournament("Cup", ["Ann"], _ids(4))
    t, _ = T.apply_op(t, "add_to_bench", {"fighters": ["n1"]})
    with pytest.raises(T.TournamentError, match="at least two"):
        T.apply_op(t, "pair_bench", {"before": "r1"}, None)
    t, _ = T.apply_op(t, "add_to_bench", {"fighters": ["n2"]})
    with pytest.raises(T.TournamentError, match="Pick a round"):
        T.apply_op(t, "pair_bench", {}, None)
    t, _ = T.apply_op(t, "pair_bench", {"round_id": "r1"}, None)  # into an existing round
    assert sum(1 for m in t["matches"] if m["round"] == "r1") == 3 and t["bench"] == []


def test_matches_move_between_rounds_when_the_bracket_still_flows():
    t = T.new_tournament("Cup", ["Ann"], _ids(8))
    t = _play(t, "r1_1")
    t, _ = T.apply_op(t, "add_round", {"name": "Play-in", "before": "r2"})
    play_in_round = t["rounds"][1]["id"]
    t, _ = T.apply_op(t, "add_match", {"round_id": "r1"})
    added = t["matches"][-1] if t["matches"][-1]["round"] == "r1" else [m for m in t["matches"] if m["round"] == "r1"][-1]
    t, _ = T.apply_op(t, "move_to_round", {"mid": added["id"], "round_id": play_in_round})
    assert T.match_index(t)[added["id"]]["label"] == "Play-in · Match 1"  # automatic names follow the round
    t, _ = T.apply_op(t, "delete_match", {"mid": added["id"]})
    # A played round-1 match moves down to the new round: its result stays, it still feeds round 2
    t, summary = T.apply_op(t, "move_to_round", {"mid": "r1_1", "round_id": play_in_round})
    assert T.match_index(t)["r1_1"]["round"] == play_in_round and T.match_index(t)["r1_1"]["winner"]
    assert "to Play-in" in summary and T.problems(t) == []
    # Into the round it feeds (or later) is refused
    with pytest.raises(T.TournamentError, match="can't go there"):
        T.apply_op(t, "move_to_round", {"mid": "r1_2", "round_id": "r2"})
    # Reorder within a round by dropping before another match
    t, _ = T.apply_op(t, "move_to_round", {"mid": "r1_4", "round_id": "r1", "before": "r1_2"})
    assert [m["id"] for m in t["matches"] if m["round"] == "r1"] == ["r1_4", "r1_2", "r1_3"]


def test_lockout_is_per_visitor_behind_the_cloudflare_tunnel(client):
    tournaments_web._failures.clear()
    tunnel = {"X-Real-IP": "172.18.0.5"}  # what nginx sees for everyone coming through the tunnel
    for _ in range(tournaments_web.LOGIN_MAX_FAILURES):
        client.post("/tournaments/login", data={"password": "wrong"}, headers={**tunnel, "CF-Connecting-IP": "198.51.100.1"})
    r = client.post("/tournaments/login", data={"password": "pw"}, headers={**tunnel, "CF-Connecting-IP": "198.51.100.2"})
    assert "error" not in r.headers["Location"]  # someone else can still log in
    tournaments_web._failures.clear()



# ---------------------------------------------------------------------------
# Score adjustments
# ---------------------------------------------------------------------------

def test_adjustments_add_to_one_scoring_or_both():
    t = T.new_tournament("Cup", ["Ann", "Ben"], _ids(4))
    t = _play(t, "r1_1", "top", "P1")
    t, summary = T.apply_op(t, "add_adjustment", {"player": "P1", "points": 0.8, "scoring": "weighted", "note": "bonus"})
    assert summary == "+0.8 points for Ann (weighted scoring)"
    s = T.scores(t)
    assert s["P1"]["standard"] == 1 and s["P1"]["weighted"] == pytest.approx(1.8)
    t, _ = T.apply_op(t, "add_adjustment", {"player": "P2", "points": "-1", "scoring": "both"})
    s = T.scores(t)
    assert s["P2"]["standard"] == -1 and s["P2"]["weighted"] == -1
    assert T.adjustment_totals(t)["P1"] == {"standard": 0.0, "weighted": 0.8}
    # A player with an adjustment can't be removed; adjustments can
    with pytest.raises(T.TournamentError, match="can't be removed"):
        T.apply_op(t, "set_players", {"names": ["Ann", ""]})
    t, _ = T.apply_op(t, "remove_adjustment", {"adjustment_id": t["adjustments"][1]["id"]})
    assert T.scores(t)["P2"]["standard"] == 0
    for bad in ({"player": "P9", "points": 1}, {"player": "P1", "points": 0}, {"player": "P1", "points": "x"},
                {"player": "P1", "points": 1, "scoring": "odd"}):
        with pytest.raises(T.TournamentError):
            T.apply_op(t, "add_adjustment", bad)


# ---------------------------------------------------------------------------
# One password per person
# ---------------------------------------------------------------------------

def _new(client, name):
    r = client.post("/tournaments/new", data={"name": name, "players": ["Ann"], "fighters": ["medusa", "sinbad"]})
    return r.headers["Location"].rsplit("/", 1)[1]


def test_each_password_sees_only_its_own_tournaments(client):
    _login(client)  # the legacy password ("pw") makes the first space
    mine = _new(client, "Mine")
    client.get("/tournaments/logout")

    r = client.post("/tournaments/signup", data={"password": "friend123", "confirm": "friend123"})
    assert "error" not in r.headers["Location"]
    theirs = _new(client, "Theirs")
    page = client.get("/tournaments").get_data(as_text=True)
    assert "Theirs" in page and "Mine" not in page
    assert client.get(f"/api/tournaments/{mine}").status_code == 404  # not theirs
    assert client.get(f"/tournaments/{mine}").status_code == 404
    client.post(f"/tournaments/{mine}/delete")  # can't delete it either
    client.get("/tournaments/logout")

    _login(client)
    page = client.get("/tournaments").get_data(as_text=True)
    assert "Mine" in page and "Theirs" not in page
    assert client.get(f"/api/tournaments/{theirs}").status_code == 404
    client.get("/tournaments/logout")
    client.post("/tournaments/login", data={"password": "friend123"})
    assert "Theirs" in client.get("/tournaments").get_data(as_text=True)


def test_signup_rules(client):
    tournaments_web._signups.clear()
    r = client.post("/tournaments/signup", data={"password": "abc", "confirm": "abc"})
    assert "at+least" in r.headers["Location"] or "at%20least" in r.headers["Location"]
    r = client.post("/tournaments/signup", data={"password": "abcdef", "confirm": "abcdeg"})
    assert "match" in r.headers["Location"]
    client.post("/tournaments/login", data={"password": "nobody-has-this"})
    assert "Open my tournaments" in client.get("/tournaments").get_data(as_text=True)  # unknown password: not in


def test_signup_can_be_turned_off(client, monkeypatch):
    import app as app_module
    monkeypatch.setitem(app_module.app.config, "TOURNAMENT_SIGNUP", False)
    assert "Make my password" not in client.get("/tournaments").get_data(as_text=True)
    assert client.post("/tournaments/signup", data={"password": "abcdef", "confirm": "abcdef"}).status_code == 404


def test_legacy_password_claims_tournaments_without_an_owner(client, tmp_path):
    store = T.TournamentStore(str(tmp_path))
    old = store.create(T.new_tournament("From before", ["Ann"], _ids(2)))  # no owner
    _login(client)
    assert "From before" in client.get("/tournaments").get_data(as_text=True)
    assert store.get(old["id"])["owner"]
    # Restoring the version from before the claim keeps the owner
    r = client.post(f"/api/tournaments/{old['id']}/restore", json={"restore": 1})
    assert r.status_code == 200 and store.get(old["id"])["owner"]


def test_spaces_never_store_the_password(tmp_path):
    spaces = T.SpaceStore(str(tmp_path))
    sid = spaces.create("hunter22")
    assert spaces.find("hunter22") == sid and spaces.find("hunter23") is None
    assert spaces.create("hunter22") == sid  # same password, same space
    assert "hunter22" not in (tmp_path / "spaces.json").read_text()
    assert [t for t in T.TournamentStore(str(tmp_path)).list()] == []  # spaces.json isn't a tournament
