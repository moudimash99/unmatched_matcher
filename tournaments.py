"""
Knockout tournaments of fighters: two or more players take turns playing the
matches, and whoever plays the winning fighter scores. Several tournaments can
run at once, and a bracket can be edited at any time without touching results
already played.

A tournament is plain JSON:

    {id, name, created, updated, version,
     players:  [{id: "P1", name}],
     scoring:  "standard" | "weighted",
     rounds:   [{id, name}],                      in play order
     matches:  [{id, round, label, top, bot,      in display order
                 winner, player, played_at}],
     bench:    [fighter ids]}                     added but not placed yet

A slot (top / bot) is {"fighter": id}, {"from": match id} (that match's winner)
or None (empty, to fill in later). Every change goes through apply_op(), which
works on a copy and rejects anything that leaves the bracket inconsistent, so a
bad edit can't corrupt a tournament.

TournamentStore keeps one JSON file per tournament plus a history of earlier
versions that can be restored.
"""
import copy
import datetime as dt
import itertools
import json
import os
import re
import secrets
import threading
import time
from contextlib import contextmanager

HISTORY_LIMIT = 60
# A matchup counts as balanced within this many points of 50% (shown on the cards)
BALANCED_BAND = 5.0


class TournamentError(ValueError):
    """An edit or result that isn't allowed; the message is shown to the user."""


def _now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


# ---------------------------------------------------------------------------
# Reading a bracket
# ---------------------------------------------------------------------------

def match_index(t):
    return {m["id"]: m for m in t["matches"]}


def round_index(t):
    return {r["id"]: i for i, r in enumerate(t["rounds"])}


def resolve(t, slot, matches=None, _depth=0):
    """The fighter in a slot, or None while it's still to be decided."""
    if not slot or _depth > 64:
        return None
    if "fighter" in slot:
        return slot["fighter"]
    src = (matches or match_index(t)).get(slot["from"])
    return src["winner"] if src else None


def sides(m):
    return (("top", m["top"]), ("bot", m["bot"]))


def consumers(t, mid):
    """(match, side) pairs that take this match's winner."""
    return [(m, side) for m in t["matches"] for side, slot in sides(m) if slot and slot.get("from") == mid]


def placed_fighters(t):
    """Fighter ids put straight into a slot (not via an earlier match)."""
    return [slot["fighter"] for m in t["matches"] for _, slot in sides(m) if slot and "fighter" in slot]


def losers(t):
    matches = match_index(t)
    out = set()
    for m in t["matches"]:
        if m["winner"]:
            for _, slot in sides(m):
                f = resolve(t, slot, matches)
                if f and f != m["winner"]:
                    out.add(f)
    return out


def all_fighters(t):
    return set(placed_fighters(t)) | set(t["bench"])


def open_winners(t):
    """Matches whose winner doesn't go anywhere yet (besides the final)."""
    final = final_match(t)
    return [m for m in t["matches"] if not consumers(t, m["id"]) and m is not final]


def final_match(t):
    """The match in the last round with no next match, if the bracket has one."""
    if not t["rounds"]:
        return None
    last = t["rounds"][-1]["id"]
    finals = [m for m in t["matches"] if m["round"] == last and not consumers(t, m["id"])]
    return finals[0] if len(finals) == 1 else None


def status(t, m, matches=None):
    if m["winner"]:
        return "played"
    a, b = resolve(t, m["top"], matches), resolve(t, m["bot"], matches)
    return "ready" if a and b else "waiting"


def current_round(t):
    """The first round with a match still to play, or None when every match is played."""
    for r in t["rounds"]:
        if any(m["round"] == r["id"] and not m["winner"] for m in t["matches"]):
            return r["id"]
    return None


def problems(t):
    """Everything that makes the bracket inconsistent (an empty list means it's fine)."""
    out = []
    matches = match_index(t)
    rounds = round_index(t)
    if len(matches) != len(t["matches"]):
        out.append("Two matches share an id.")
    seen = {}
    for f in placed_fighters(t):
        seen[f] = seen.get(f, 0) + 1
    for f, n in seen.items():
        if n > 1:
            out.append(f"{f} is placed in {n} slots.")
    for f in t["bench"]:
        if f in seen:
            out.append(f"{f} is both on the bench and in the bracket.")
    used_sources = {}
    for m in t["matches"]:
        if m["round"] not in rounds:
            out.append(f"{m['label']} is in a round that doesn't exist.")
            continue
        for side, slot in sides(m):
            if slot and "from" in slot:
                src = matches.get(slot["from"])
                if not src:
                    out.append(f"{m['label']} takes the winner of a match that doesn't exist.")
                    continue
                used_sources[src["id"]] = used_sources.get(src["id"], 0) + 1
                if rounds.get(src["round"], -1) >= rounds[m["round"]]:
                    out.append(f"{m['label']} takes the winner of {src['label']}, which isn't in an earlier round.")
        if m["winner"]:
            fighters = {resolve(t, slot, matches) for _, slot in sides(m)}
            if m["winner"] not in fighters:
                out.append(f"{m['label']} has a winner who isn't in it.")
        if m["player"] and m["player"] not in {p["id"] for p in t["players"]}:
            out.append(f"{m['label']} is credited to a player who isn't in the tournament.")
        if m.get("loser_player") and m["loser_player"] not in {p["id"] for p in t["players"]}:
            out.append(f"{m['label']} has a loser played by someone who isn't in the tournament.")
    player_ids = {p["id"] for p in t["players"]}
    for adj in t.get("adjustments", []):
        if adj["player"] not in player_ids:
            out.append("A score adjustment is for a player who isn't in the tournament.")
    for mid, n in used_sources.items():
        if n > 1:
            out.append(f"The winner of {matches[mid]['label']} is sent to {n} matches.")
    return out


def notes(t):
    """Things that aren't wrong but still need doing (shown to whoever is editing)."""
    out = []
    empty = [m["label"] for m in t["matches"] for _, slot in sides(m) if not slot]
    if empty:
        out.append(f"Empty slots in: {', '.join(dict.fromkeys(empty))}.")
    loose = [m["label"] for m in open_winners(t)]
    if loose:
        out.append(f"Winners not sent to a later match yet: {', '.join(loose)}.")
    if t["bench"]:
        out.append(f"{len(t['bench'])} fighter{'s' if len(t['bench']) != 1 else ''} on the bench, not in the bracket yet.")
    return out


# ---------------------------------------------------------------------------
# Scores and win chances
# ---------------------------------------------------------------------------

SCORING_MODES = ("standard", "weighted")


def win_reward(top_pct, side):
    """Weighted scoring: an upset is worth up to 1.8 points, a heavy favourite as little as 0.2."""
    if top_pct is None:
        return 1.0
    winner_pct = top_pct if side == "top" else 100.0 - top_pct
    return max(0.1, 1 + (50.0 - winner_pct) / 50.0 * 0.8)


def scores(t, win_pct=None):
    """{player id: {"standard": wins, "weighted": points}} from the played matches."""
    matches = match_index(t)
    out = {p["id"]: {"standard": 0, "weighted": 0.0} for p in t["players"]}
    for m in t["matches"]:
        if not m["winner"] or m["player"] not in out:
            continue
        top, bot = resolve(t, m["top"], matches), resolve(t, m["bot"], matches)
        side = "top" if m["winner"] == top else "bot"
        pct = win_pct(top, bot) if (win_pct and top and bot) else None
        out[m["player"]]["standard"] += 1
        out[m["player"]]["weighted"] += win_reward(pct, side)
    for adj in t.get("adjustments", []):
        if adj["player"] in out:
            for mode in SCORING_MODES if adj["scoring"] == "both" else (adj["scoring"],):
                out[adj["player"]][mode] += adj["points"]
    for s in out.values():
        s["weighted"] = round(s["weighted"], 2)
        s["standard"] = round(s["standard"], 2)
    return out


# History entries made by adding or removing a score adjustment (see op_add_adjustment and
# op_remove_adjustment). Adjustments are kept out of sight on the page, so these are left out of the
# history list too.
_ADJUSTMENT_SUMMARY = re.compile(r"^[+-]?[\d.]+ points for .+ \((both scorings|weighted scoring|standard scoring)\)$"
                                 r"|^Removed a score adjustment$")


def is_adjustment_change(summary):
    return bool(_ADJUSTMENT_SUMMARY.match(summary or ""))


def adjustment_totals(t):
    """{player id: {"standard": points, "weighted": points}} from score adjustments alone."""
    out = {p["id"]: {"standard": 0.0, "weighted": 0.0} for p in t["players"]}
    for adj in t.get("adjustments", []):
        if adj["player"] in out:
            for mode in SCORING_MODES if adj["scoring"] == "both" else (adj["scoring"],):
                out[adj["player"]][mode] = round(out[adj["player"]][mode] + adj["points"], 2)
    return out


# ---------------------------------------------------------------------------
# Building a bracket
# ---------------------------------------------------------------------------

def round_name(position, total_rounds):
    left = total_rounds - position  # 1 = final
    return {1: "Final", 2: "Semi-finals", 3: "Quarter-finals"}.get(left, f"Round {position + 1}")


def _fairest_pairs(fighters, n_pairs, fairness):
    """Greedy: the n_pairs fairest matchups that don't share a fighter."""
    scored = sorted(((fairness(a, b), a, b) for a, b in itertools.combinations(fighters, 2)),
                    key=lambda x: -x[0])
    used, pairs = set(), []
    for _, a, b in scored:
        if len(pairs) == n_pairs:
            break
        if a not in used and b not in used:
            pairs.append((a, b))
            used.update((a, b))
    return pairs


def new_tournament(name, player_names, fighter_ids, fairness=None):
    """
    A fresh knockout bracket. With a fighter count that isn't a power of two, round 1 has just
    enough matches to leave a power of two, and the rest get byes into round 2. Round 1 pairs the
    fairest matchups (fairness(a, b) in 0..1, higher = fairer); later rounds go in order.
    """
    fighters = list(dict.fromkeys(fighter_ids))
    players = [n.strip() for n in player_names if n and n.strip()]
    if len(fighters) < 2:
        raise TournamentError("Pick at least two fighters.")
    if len(players) < 1:
        raise TournamentError("Add at least one player.")
    fairness = fairness or (lambda a, b: 0.0)

    size = 1
    while size < len(fighters):
        size *= 2
    first_matches = len(fighters) - size // 2 if len(fighters) != size else size // 2
    total_rounds = size.bit_length() - 1
    rounds = [{"id": f"r{i + 1}", "name": round_name(i, total_rounds)} for i in range(total_rounds)]

    t = {
        "id": "t_" + secrets.token_hex(5),
        "name": (name or "").strip() or "Tournament",
        "created": _now(), "updated": _now(), "version": 0,
        "players": [{"id": f"P{i + 1}", "name": n} for i, n in enumerate(players)],
        "scoring": "standard",
        "rounds": rounds,
        "matches": [],
        "bench": [],
    }
    pairs = _fairest_pairs(fighters, first_matches, fairness)
    in_pairs = {f for p in pairs for f in p}
    byes = [f for f in fighters if f not in in_pairs]

    def add(round_no, top, bot):
        n = sum(1 for m in t["matches"] if m["round"] == f"r{round_no}") + 1
        mid = f"r{round_no}_{n}"
        t["matches"].append({"id": mid, "round": f"r{round_no}", "label": f"{rounds[round_no - 1]['name']} · Match {n}",
                             "top": top, "bot": bot, "winner": None, "player": None, "played_at": None})
        return mid

    first = [add(1, {"fighter": a}, {"fighter": b}) for a, b in pairs]
    if total_rounds >= 2 and len(fighters) != size:
        # Round 2: byes meet round-1 winners first, then whatever is left pairs up
        slots = []
        winners = [{"from": mid} for mid in first]
        bye_slots = [{"fighter": f} for f in byes]
        while bye_slots and winners:
            slots += [bye_slots.pop(0), winners.pop(0)]
        slots += bye_slots + winners
        prev = [add(2, slots[i], slots[i + 1]) for i in range(0, len(slots), 2)]
        start = 3
    else:
        prev, start = first, 2
    for round_no in range(start, total_rounds + 1):
        prev = [add(round_no, {"from": prev[i]}, {"from": prev[i + 1]}) for i in range(0, len(prev), 2)]
    _check(t)
    return t


# ---------------------------------------------------------------------------
# Importing the old Unmatched-Tournament app (bracket.json + state.json)
# ---------------------------------------------------------------------------

LEGACY_ROUND_NAMES = {1: "Round 1", 2: "Round 2", 3: "Round 3", 4: "Quarter-finals", 5: "Semi-finals", 6: "Final"}


def import_legacy(bracket, state, name="Imported tournament", player_names=None):
    """
    Converts the old app's files. Round layouts from its "rebalance" button (state["__layout"])
    are kept; a fighter moved by it who came out of an earlier match keeps that link.
    """
    player_names = player_names or {"P1": "P1", "P2": "P2"}
    layout = (state or {}).get("__layout", {})
    numbers = sorted({m["round"] for m in bracket.values()})
    t = {
        "id": "t_" + secrets.token_hex(5),
        "name": name, "created": _now(), "updated": _now(), "version": 0,
        "players": [{"id": pid, "name": pname} for pid, pname in player_names.items()],
        "scoring": "standard",
        "rounds": [{"id": f"r{n}", "name": LEGACY_ROUND_NAMES.get(n, f"Round {n}")} for n in numbers],
        "matches": [], "bench": [],
    }

    def order(mid):
        m = re.search(r"(\d+)$", mid)
        return (bracket[mid]["round"], int(m.group(1)) if m else 0)

    winners = {}
    for mid in bracket:
        w = bracket[mid].get("preset_winner") or (state.get(mid) or {}).get("winner")
        if w:
            winners[w] = winners.get(w, []) + [mid]

    def slot(mid, side):
        moved = (layout.get(mid) or {}).get(side)
        if moved and moved.get("id"):
            # Keep the link to the match this fighter won, if there is one before this round
            earlier = [s for s in winners.get(moved["id"], []) if bracket[s]["round"] < bracket[mid]["round"]]
            return {"from": max(earlier, key=order)} if earlier else {"fighter": moved["id"]}
        s = bracket[mid][side]
        if not s:
            return None
        return {"fighter": s["id"]} if s.get("type") == "known" else {"from": s["src"]}

    for mid in sorted(bracket, key=order):
        m = bracket[mid]
        st = state.get(mid) or {}
        t["matches"].append({
            "id": mid, "round": f"r{m['round']}", "label": m.get("label") or mid,
            "top": slot(mid, "top"), "bot": slot(mid, "bot"),
            "winner": m.get("preset_winner") or st.get("winner"),
            "player": st.get("player") or m.get("winner_player"),
            "played_at": None,
        })
    _check(t)
    return t


# ---------------------------------------------------------------------------
# Changes: results and edits
# ---------------------------------------------------------------------------

def _check(t):
    found = problems(t)
    if found:
        raise TournamentError(" ".join(found))


def _match(t, mid):
    m = match_index(t).get(mid)
    if not m:
        raise TournamentError("That match doesn't exist (it may have just been changed on another device).")
    return m


def _round(t, rid):
    if rid not in round_index(t):
        raise TournamentError("That round doesn't exist.")
    return rid


def _unplayed(m, what="change"):
    if m["winner"]:
        raise TournamentError(f"{m['label']} has already been played. Undo its result first to {what} it.")


def _take_slot(t, slot):
    """Validates a slot about to be placed and takes a benched fighter off the bench."""
    if slot is None:
        return None
    if "fighter" in slot:
        f = slot["fighter"]
        if f in placed_fighters(t):
            raise TournamentError("That fighter is already in the bracket.")
        if f in t["bench"]:
            t["bench"].remove(f)
        return {"fighter": f}
    if "from" in slot:
        src = _match(t, slot["from"])
        if consumers(t, src["id"]):
            raise TournamentError(f"The winner of {src['label']} already goes to another match.")
        return {"from": src["id"]}
    raise TournamentError("Unknown slot.")


def _release(t, slot):
    """A fighter taken out of a slot goes back to the bench."""
    if slot and "fighter" in slot and slot["fighter"] not in t["bench"]:
        t["bench"].append(slot["fighter"])


def _new_match_id(t, round_id):
    used = {m["id"] for m in t["matches"]}
    n = 1
    while f"{round_id}_m{n}" in used:
        n += 1
    return f"{round_id}_m{n}"


def _new_round_id(t):
    used = {r["id"] for r in t["rounds"]}
    n = len(t["rounds"]) + 1
    while f"r{n}" in used:
        n += 1
    return f"r{n}"


def _round_name(t, rid):
    return next(r["name"] for r in t["rounds"] if r["id"] == rid)


def _insert_match(t, m, after=None):
    """Adds a match after `after` (a match id), else at the end of its round."""
    idx = len(t["matches"])
    if after:
        idx = next(i for i, x in enumerate(t["matches"]) if x["id"] == after) + 1
    else:
        in_round = [i for i, x in enumerate(t["matches"]) if x["round"] == m["round"]]
        if in_round:
            idx = in_round[-1] + 1
        else:
            order = round_index(t)
            later = [i for i, x in enumerate(t["matches"]) if order[x["round"]] > order[m["round"]]]
            idx = later[0] if later else len(t["matches"])
    t["matches"].insert(idx, m)


def op_set_result(t, mid, winner, player=None):
    """winner is "top" or "bot"; player is optional (can be picked afterwards)."""
    m = _match(t, mid)
    if winner not in ("top", "bot"):
        raise TournamentError("Pick the top or bottom fighter as the winner.")
    matches = match_index(t)
    fighter = resolve(t, m[winner], matches)
    if not resolve(t, m["top"], matches) or not resolve(t, m["bot"], matches):
        raise TournamentError(f"Both fighters of {m['label']} need to be known first.")
    later = [c["label"] for c, _ in consumers(t, mid) if c["winner"]]
    if m["winner"] and m["winner"] != fighter and later:
        raise TournamentError(f"{', '.join(later)} already used this result. Undo that first.")
    m["winner"] = fighter
    if player is not None:
        m["player"] = player or None
    elif match_picks(t, m, matches).get(winner):  # picked beforehand: whoever was to play the winner scores
        m["player"] = match_picks(t, m, matches)[winner]
    loser_pick = match_picks(t, m, matches).get("bot" if winner == "top" else "top")
    if loser_pick and loser_pick != m["player"] and not m.get("loser_player"):
        m["loser_player"] = loser_pick
    m["played_at"] = m["played_at"] or _now()
    return f"{m['label']}: {fighter} won"


def match_picks(t, m, matches=None):
    """{"top"/"bot": player id} picked beforehand for the fighters now in the match (picks are kept per
    fighter, so ones for a fighter who has since been moved out no longer count)."""
    matches = matches or match_index(t)
    players = {p["id"] for p in t["players"]}
    picks = m.get("picks") or {}
    out = {}
    for side, slot in sides(m):
        fighter = resolve(t, slot, matches)
        if fighter and picks.get(fighter) in players:
            out[side] = picks[fighter]
    return out


def op_set_picks(t, mid, picks):
    """Who will play which fighter of a match not played yet: {"top"/"bot": player id or None}.
    With two players, picking one side gives the other side to the other player."""
    m = _match(t, mid)
    if m["winner"]:
        raise TournamentError(f"{m['label']} has already been played.")
    matches = match_index(t)
    fighters = {side: resolve(t, slot, matches) for side, slot in sides(m)}
    players = [p["id"] for p in t["players"]]
    picks = {side: pid or None for side, pid in (picks or {}).items() if side in ("top", "bot")}
    if any(pid and pid not in players for pid in picks.values()):
        raise TournamentError("That player isn't in this tournament.")
    if any(not fighters[side] for side, pid in picks.items() if pid):
        raise TournamentError(f"Both fighters of {m['label']} need to be known first.")
    if len(players) == 2 and len(picks) == 1:
        (side, pid), = picks.items()
        other = "bot" if side == "top" else "top"
        picks[other] = (players[1] if pid == players[0] else players[0]) if pid else None
    by_side = {**match_picks(t, m, matches), **picks}  # sides not mentioned keep their pick
    if by_side.get("top") and by_side.get("top") == by_side.get("bot"):
        raise TournamentError("One player can't play both fighters.")
    kept = {fighters[side]: pid for side, pid in by_side.items() if pid and fighters[side]}
    if not kept:
        m.pop("picks", None)
        return f"{m['label']}: no players picked"
    m["picks"] = kept
    return f"{m['label']}: " + ", ".join(f"{pid} plays {f}" for f, pid in kept.items())


def op_set_player(t, mid, player, role="winner"):
    """Who played the winning fighter (role "winner"), or the losing one (role "loser"; no player means
    "don't know", so it isn't asked again)."""
    m = _match(t, mid)
    if not m["winner"]:
        raise TournamentError("Pick the winning fighter first.")
    if player and player not in {p["id"] for p in t["players"]}:
        raise TournamentError("That player isn't in this tournament.")
    if role == "loser":
        if player and player == m["player"]:
            raise TournamentError("One player can't play both fighters.")
        m["loser_player"] = player or ""
        return f"{m['label']}: lost by {player or 'nobody known'}"
    m["player"] = player or None
    if player and m.get("loser_player") == player:
        m["loser_player"] = None  # they can't have played both; ask again
    return f"{m['label']}: played by {player or 'nobody'}"


def loser_player(t, m):
    """Who played the losing fighter: as recorded, or with two players, whoever didn't play the winner."""
    if m.get("loser_player"):
        return m["loser_player"]
    ids = [p["id"] for p in t["players"]]
    if len(ids) == 2 and m["player"] in ids:
        return ids[1] if m["player"] == ids[0] else ids[0]
    return None


def needs_loser_player(t, m):
    """With three or more players, a played match still has to say who played the loser (None: not asked
    yet; "": asked, and nobody knows)."""
    return bool(m["winner"] and m["player"] and len(t["players"]) > 2 and m.get("loser_player") is None)


def op_undo_result(t, mid):
    m = _match(t, mid)
    later = [c["label"] for c, _ in consumers(t, mid) if c["winner"]]
    if later:
        raise TournamentError(f"{', '.join(later)} already used this result. Undo that first.")
    m["winner"] = m["player"] = m["played_at"] = None
    m.pop("loser_player", None)
    return f"{m['label']}: result undone"


def op_rename(t, name):
    if not (name or "").strip():
        raise TournamentError("The name can't be empty.")
    t["name"] = name.strip()
    return f"Renamed to {t['name']}"


def op_set_players(t, names):
    """Renames players by position, adds new ones; players with results can't be removed."""
    names = [n.strip() for n in names]
    if not any(names):
        raise TournamentError("Keep at least one player.")
    credited = ({m["player"] for m in t["matches"] if m["player"]} | {m["loser_player"] for m in t["matches"] if m.get("loser_player")}
                | {a["player"] for a in t.get("adjustments", [])})
    players = []
    for i, n in enumerate(names):
        pid = t["players"][i]["id"] if i < len(t["players"]) else f"P{i + 1}"
        if n:
            players.append({"id": pid, "name": n})
        elif pid in credited:
            raise TournamentError(f"{t['players'][i]['name']} has results, so they can't be removed.")
    for p in t["players"][len(names):]:
        if p["id"] in credited:
            raise TournamentError(f"{p['name']} has results, so they can't be removed.")
    t["players"] = players
    return "Players: " + ", ".join(p["name"] for p in players)


def op_set_scoring(t, scoring):
    if scoring not in ("standard", "weighted"):
        raise TournamentError("Unknown scoring.")
    t["scoring"] = scoring
    return f"Scoring: {scoring}"


def op_add_adjustment(t, player, points, scoring="weighted", note=""):
    """Extra (or fewer, if negative) points for a player, in one scoring mode or both."""
    if player not in {p["id"] for p in t["players"]}:
        raise TournamentError("That player isn't in this tournament.")
    if scoring not in SCORING_MODES + ("both",):
        raise TournamentError("Pick standard, weighted or both.")
    try:
        points = round(float(points), 2)
    except (TypeError, ValueError):
        raise TournamentError("Points must be a number, like 0.8 or -1.") from None
    if not points or abs(points) > 1000:
        raise TournamentError("Points must be a number other than 0.")
    adjs = t.setdefault("adjustments", [])
    n = 1
    while any(a["id"] == f"adj{n}" for a in adjs):
        n += 1
    adjs.append({"id": f"adj{n}", "player": player, "points": points, "scoring": scoring,
                 "note": (note or "").strip()[:200], "at": _now()})
    name = next(p["name"] for p in t["players"] if p["id"] == player)
    where = "both scorings" if scoring == "both" else f"{scoring} scoring"
    return f"{'+' if points > 0 else ''}{points:g} points for {name} ({where})"


def op_remove_adjustment(t, adjustment_id):
    adjs = t.get("adjustments", [])
    if not any(a["id"] == adjustment_id for a in adjs):
        raise TournamentError("That adjustment isn't there any more.")
    t["adjustments"] = [a for a in adjs if a["id"] != adjustment_id]
    return "Removed a score adjustment"


def op_add_to_bench(t, fighters):
    have = all_fighters(t)
    added = [f for f in dict.fromkeys(fighters) if f not in have]
    t["bench"].extend(added)
    return f"Added to the bench: {', '.join(added) or 'nobody new'}"


def op_remove_fighter(t, fighter):
    """Takes a fighter out entirely: off the bench, or out of a slot of a match not played yet."""
    if fighter in t["bench"]:
        t["bench"].remove(fighter)
        return f"Removed {fighter}"
    for m in t["matches"]:
        for side, slot in sides(m):
            if slot and slot.get("fighter") == fighter:
                _unplayed(m, "remove a fighter from")
                m[side] = None
                return f"Removed {fighter} (its slot in {m['label']} is now empty)"
    raise TournamentError("That fighter isn't in this tournament, or only reached a match through an earlier win.")


def op_add_round(t, name, before=None):
    rid = _new_round_id(t)
    r = {"id": rid, "name": (name or "").strip() or "New round"}
    if before:
        t["rounds"].insert(round_index(t)[_round(t, before)], r)
    else:
        t["rounds"].append(r)
    return f"Added round {r['name']}"


def op_rename_round(t, round_id, name):
    _round(t, round_id)
    if not (name or "").strip():
        raise TournamentError("The name can't be empty.")
    for r in t["rounds"]:
        if r["id"] == round_id:
            r["name"] = name.strip()
    return f"Renamed a round to {name.strip()}"


def op_delete_round(t, round_id):
    _round(t, round_id)
    if any(m["round"] == round_id for m in t["matches"]):
        raise TournamentError("Delete or move this round's matches first.")
    t["rounds"] = [r for r in t["rounds"] if r["id"] != round_id]
    return "Deleted an empty round"


def op_add_match(t, round_id, top=None, bot=None, label=None):
    _round(t, round_id)
    mid = _new_match_id(t, round_id)
    m = {"id": mid, "round": round_id, "label": "", "top": _take_slot(t, top), "bot": None,
         "winner": None, "player": None, "played_at": None}
    m["bot"] = _take_slot(t, bot)
    n = sum(1 for x in t["matches"] if x["round"] == round_id) + 1
    m["label"] = (label or "").strip() or f"{_round_name(t, round_id)} · Match {n}"
    _insert_match(t, m)
    return f"Added {m['label']}"


def op_rename_match(t, mid, label):
    m = _match(t, mid)
    if not (label or "").strip():
        raise TournamentError("The name can't be empty.")
    m["label"] = label.strip()
    return f"Renamed a match to {m['label']}"


def op_set_slot(t, mid, side, slot):
    """Puts a benched fighter, an earlier match's winner, or nothing into a slot."""
    m = _match(t, mid)
    _unplayed(m)
    if side not in ("top", "bot"):
        raise TournamentError("Unknown side.")
    old = m[side]
    m[side] = None
    _release(t, old)
    m[side] = _take_slot(t, slot)
    return f"{m['label']}: changed a slot"


def op_swap_slots(t, mid_a, side_a, mid_b, side_b):
    a, b = _match(t, mid_a), _match(t, mid_b)
    _unplayed(a, "swap")
    _unplayed(b, "swap")
    if (mid_a, side_a) == (mid_b, side_b):
        return "Nothing to swap"
    a[side_a], b[side_b] = b[side_b], a[side_a]
    if mid_a == mid_b:
        return f"Swapped the two sides of {a['label']}"
    return f"Swapped a slot of {a['label']} with {b['label']}"


def op_insert_play_in(t, mid, side, challenger, round_id=None, round_name=None):
    """
    Makes whoever is in this slot earn it first: a new match between them and the challenger
    (a benched fighter or an earlier match's winner), whose winner takes the slot. The play-in
    match goes in round_id, or a new round just before this match's round.
    """
    m = _match(t, mid)
    _unplayed(m, "add a play-in to")
    current = m[side]
    if not current:
        raise TournamentError("That slot is empty; put someone in it directly instead.")
    if round_id is None:
        pos = round_index(t)[m["round"]]
        prev = t["rounds"][pos - 1] if pos > 0 else None
        if prev and prev["name"].lower().startswith("play-in"):
            round_id = prev["id"]  # reuse the play-in round already right before this one
        else:
            op_add_round(t, round_name or f"Play-in for {_round_name(t, m['round'])}", before=m["round"])
            round_id = t["rounds"][pos]["id"]
    _round(t, round_id)
    if round_index(t)[round_id] >= round_index(t)[m["round"]]:
        raise TournamentError("A play-in has to come in a round before the match it feeds.")
    new_id = _new_match_id(t, round_id)
    n = sum(1 for x in t["matches"] if x["round"] == round_id) + 1
    play_in = {"id": new_id, "round": round_id, "label": f"{_round_name(t, round_id)} · Match {n}",
               "top": current, "bot": None, "winner": None, "player": None, "played_at": None}
    m[side] = {"from": new_id}
    play_in["bot"] = _take_slot(t, challenger)
    _insert_match(t, play_in)
    return f"Added play-in {play_in['label']} for a slot in {m['label']}"


def op_delete_match(t, mid):
    """Removes a match not played yet: its fighters go to the bench, and its next match gets an empty slot."""
    m = _match(t, mid)
    _unplayed(m, "delete")
    for _, slot in sides(m):
        _release(t, slot)
    for c, side in consumers(t, mid):
        _unplayed(c, "delete the match before")
        c[side] = None
    t["matches"] = [x for x in t["matches"] if x["id"] != mid]
    return f"Deleted {m['label']}"


def op_move_match(t, mid, direction):
    """Moves a match up or down within its round (display order only)."""
    m = _match(t, mid)
    same = [i for i, x in enumerate(t["matches"]) if x["round"] == m["round"]]
    pos = same.index(next(i for i, x in enumerate(t["matches"]) if x["id"] == mid))
    other = pos - 1 if direction == "up" else pos + 1
    if 0 <= other < len(same):
        i, j = same[pos], same[other]
        t["matches"][i], t["matches"][j] = t["matches"][j], t["matches"][i]
    return f"Moved {m['label']}"


def op_move_to_round(t, mid, round_id, before=None):
    """
    Moves a match to another round (placed before match `before`, else at the end). Results stay;
    the move is refused if a match would then feed one in the same or an earlier round.
    """
    m = _match(t, mid)
    _round(t, round_id)
    if before == mid:
        return "Nothing to move"
    old_round = m["round"]
    t["matches"] = [x for x in t["matches"] if x["id"] != mid]
    m["round"] = round_id
    if before:
        idx = next((i for i, x in enumerate(t["matches"]) if x["id"] == before), None)
        if idx is None:
            raise TournamentError("That match doesn't exist (it may have just been changed on another device).")
        t["matches"].insert(idx, m)
    else:
        _insert_match(t, m)
    found = problems(t)
    if found:
        raise TournamentError(f"{m['label']} can't go there: " + " ".join(found))
    if old_round == round_id:
        return f"Moved {m['label']}"
    old_label = m["label"]
    if old_label.startswith(f"{_round_name(t, old_round)} · Match"):
        # Still the automatic name: name it after its new round
        n = sum(1 for x in t["matches"] if x["round"] == round_id)
        m["label"] = f"{_round_name(t, round_id)} · Match {n}"
    return f"Moved {old_label} from {_round_name(t, old_round)} to {_round_name(t, round_id)}"


def op_rebalance_round(t, round_id, win_pct):
    """
    Re-pairs the round's matches that are ready and not played, swapping slots between them while
    that brings the matchups closer to 50/50 overall. Slots keep where they came from.
    """
    _round(t, round_id)
    matches = match_index(t)
    ms = [m for m in t["matches"] if m["round"] == round_id and status(t, m, matches) == "ready"]
    if len(ms) < 2:
        raise TournamentError("Rebalancing needs at least two matches in this round that are ready and not played.")

    def dev(m):
        a, b = resolve(t, m["top"], matches), resolve(t, m["bot"], matches)
        pct = win_pct(a, b)
        return abs(pct - 50.0) if pct is not None else 25.0

    before = sum(dev(m) for m in ms)
    swaps = 0
    improved = True
    while improved:
        improved = False
        best = (0.05, None)
        for x, y in itertools.combinations(ms, 2):
            cur = dev(x) + dev(y)
            for sx, sy in (("top", "top"), ("top", "bot"), ("bot", "top"), ("bot", "bot")):
                x[sx], y[sy] = y[sy], x[sx]
                gain = cur - (dev(x) + dev(y))
                x[sx], y[sy] = y[sy], x[sx]
                if gain > best[0]:
                    best = (gain, (x, sx, y, sy))
        if best[1]:
            x, sx, y, sy = best[1]
            x[sx], y[sy] = y[sy], x[sx]
            swaps += 1
            improved = True
    after = sum(dev(m) for m in ms)
    return f"Rebalanced {_round_name(t, round_id)}: {swaps} swap{'s' if swaps != 1 else ''}, " \
           f"average {before / len(ms):.1f} → {after / len(ms):.1f} points from 50%"


def matches_played(t, fighter):
    matches = match_index(t)
    return sum(1 for m in t["matches"] if m["winner"] and fighter in (resolve(t, m["top"], matches), resolve(t, m["bot"], matches)))


def _gap(win_pct, a, b):
    """How far a vs b is from 50/50 (25 when unknown, e.g. a winner not decided yet)."""
    pct = win_pct(a, b) if (win_pct and a and b) else None
    return abs(pct - 50.0) if pct is not None else 25.0


def _fairest_matching(left, right, cost):
    """Greedy one-to-one pairing of left items with right items, lowest cost first."""
    pairs, used_l, used_r = [], set(), set()
    for _, i, j in sorted((cost(a, b), i, j) for i, a in enumerate(left) for j, b in enumerate(right)):
        if i in used_l or j in used_r:
            continue
        pairs.append((left[i], right[j]))
        used_l.add(i)
        used_r.add(j)
    return pairs


def op_pair_bench(t, win_pct, round_id=None, before=None, round_name="Qualifier", fighters=None):
    """
    Benched fighters fight each other: the fairest pairings among them become new matches in
    round_id, or in a new round (round_name) placed before `before`. Their winners can then be
    slotted into the bracket. With an odd number, one stays on the bench.
    """
    bench = [f for f in (fighters or t["bench"]) if f in t["bench"]]
    if len(bench) < 2:
        raise TournamentError("Put at least two fighters on the bench to pair them up.")
    if round_id is None:
        if not before:
            raise TournamentError("Pick a round, or which round the new qualifier round goes before.")
        op_add_round(t, round_name, before=_round(t, before))
        round_id = t["rounds"][round_index(t)[before] - 1]["id"]
    _round(t, round_id)
    # Fairest pairs: greedy over every pairing, closest to 50/50 first
    scored = sorted((_gap(win_pct, a, b), a, b) for a, b in itertools.combinations(bench, 2))
    used, pairs = set(), []
    for _, a, b in scored:
        if a not in used and b not in used:
            pairs.append((a, b))
            used.update((a, b))
    for a, b in pairs:
        op_add_match(t, round_id, {"fighter": a}, {"fighter": b})
    left = [f for f in bench if f not in used]
    return f"Paired the bench in {_round_name(t, round_id)}: " + ", ".join(f"{a} vs {b}" for a, b in pairs) + \
        (f" ({left[0]} stays on the bench)" if left else "")


def op_slot_in(t, round_id, win_pct, fighters=None):
    """
    Brings newcomers into a round without touching anything played: every benched fighter, and
    every winner not sent anywhere yet from an earlier round (e.g. a bench qualifier), gets a play-in
    against a fighter already in that round. It picks among those who have played the fewest
    matches (the ones who had byes), fairest pairings first. Anyone left over stays where they are.
    """
    _round(t, round_id)
    order = round_index(t)
    matches = match_index(t)
    challengers = [{"slot": {"fighter": f}, "fighter": f, "name": f}
                   for f in (fighters or t["bench"]) if f in t["bench"]]
    for m in open_winners(t):
        if order[m["round"]] < order[round_id]:
            challengers.append({"slot": {"from": m["id"]}, "fighter": m["winner"],
                                "name": m["winner"] or f"winner of {m['label']}"})
    if not challengers:
        raise TournamentError("Nobody to slot in: the bench is empty and every winner already goes somewhere.")
    holders = []
    for m in t["matches"]:
        if m["round"] != round_id or m["winner"]:
            continue
        for side, slot in sides(m):
            fighter = resolve(t, slot, matches)
            if fighter:
                holders.append({"mid": m["id"], "side": side, "fighter": fighter, "played": matches_played(t, fighter)})
    if not holders:
        raise TournamentError("Nobody in that round is decided yet; finish the round before it first, or use + play-in by hand.")
    # The fewest-played fighters first, widening to the next group until there's one per challenger
    pool = []
    for n in sorted({h["played"] for h in holders}):
        pool += [h for h in holders if h["played"] == n]
        if len(pool) >= len(challengers):
            break
    pairs = _fairest_matching(challengers, pool, lambda c, h: _gap(win_pct, c["fighter"], h["fighter"]))
    for c, h in pairs:
        op_insert_play_in(t, h["mid"], h["side"], c["slot"])
    placed = {id(c) for c, _ in pairs}
    left = [c["name"] for c in challengers if id(c) not in placed]
    names = ", ".join(f"{c['name']} vs {h['fighter']}" for c, h in pairs)
    return f"Slotted into {_round_name(t, round_id)}: {names}" + (f" (not placed: {', '.join(left)})" if left else "")


OPS = {
    "slot_in": op_slot_in, "pair_bench": op_pair_bench, "move_to_round": op_move_to_round,
    "set_picks": op_set_picks, "add_adjustment": op_add_adjustment, "remove_adjustment": op_remove_adjustment,
    "set_result": op_set_result, "set_player": op_set_player, "undo_result": op_undo_result,
    "rename": op_rename, "set_players": op_set_players, "set_scoring": op_set_scoring,
    "add_to_bench": op_add_to_bench, "remove_fighter": op_remove_fighter,
    "add_round": op_add_round, "rename_round": op_rename_round, "delete_round": op_delete_round,
    "add_match": op_add_match, "rename_match": op_rename_match, "delete_match": op_delete_match,
    "move_match": op_move_match, "set_slot": op_set_slot, "swap_slots": op_swap_slots,
    "insert_play_in": op_insert_play_in, "rebalance_round": op_rebalance_round,
}
# Ops that need the win-chance function
NEEDS_WIN_PCT = {"rebalance_round", "slot_in", "pair_bench"}


def apply_op(t, op, args, win_pct=None):
    """Applies one change to a copy of the tournament; returns (new tournament, summary)."""
    if op not in OPS:
        raise TournamentError(f"Unknown change: {op}")
    new = copy.deepcopy(t)
    args = dict(args or {})
    if op in NEEDS_WIN_PCT:
        args["win_pct"] = win_pct
    try:
        summary = OPS[op](new, **args)
    except TypeError as e:
        raise TournamentError(f"Bad request for {op}: {e}") from None
    _check(new)
    new["updated"] = _now()
    return new, summary


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

class VersionConflict(Exception):
    """Someone else saved first; the caller should reload."""


class TournamentStore:
    """One JSON file per tournament, plus <id>.history.json with earlier versions."""

    _thread_lock = threading.Lock()
    LOCK_WAIT_SECONDS = 10
    STALE_LOCK_SECONDS = 30

    def __init__(self, directory):
        self.dir = directory

    @contextmanager
    def _lock(self):
        """One writer at a time, across threads and the server's worker processes (a lock file)."""
        os.makedirs(self.dir, exist_ok=True)
        path = os.path.join(self.dir, ".lock")
        with self._thread_lock:
            deadline = time.time() + self.LOCK_WAIT_SECONDS
            while True:
                try:
                    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    break
                except FileExistsError:
                    try:
                        if time.time() - os.path.getmtime(path) > self.STALE_LOCK_SECONDS:
                            os.remove(path)  # left behind by a crashed worker
                            continue
                    except FileNotFoundError:
                        continue
                    if time.time() > deadline:
                        raise TimeoutError("The tournament files are busy; try again.")
                    time.sleep(0.02)
            try:
                yield
            finally:
                os.close(fd)
                os.remove(path)

    def _path(self, tid, suffix=".json"):
        if not re.fullmatch(r"t_[0-9a-f]{6,32}", tid or ""):
            raise KeyError(tid)
        return os.path.join(self.dir, tid + suffix)

    @staticmethod
    def _read(path, default=None):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return default

    @staticmethod
    def _write(path, data):
        tmp = path + f".{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, path)

    def list(self, owner=None):
        """Every tournament, or only those of one owner (a password's space)."""
        if not os.path.isdir(self.dir):
            return []
        out = []
        for name in os.listdir(self.dir):
            if name.startswith("t_") and name.endswith(".json") and not name.endswith(".history.json"):
                t = self._read(os.path.join(self.dir, name))
                if t and (owner is None or t.get("owner") == owner):
                    out.append(t)
        return sorted(out, key=lambda t: t["updated"], reverse=True)

    def get(self, tid):
        try:
            return self._read(self._path(tid))
        except KeyError:
            return None

    def create(self, t):
        os.makedirs(self.dir, exist_ok=True)
        with self._lock():
            t = dict(t, version=1, updated=_now())
            self._write(self._path(t["id"]), t)
            self._write(self._path(t["id"], ".history.json"),
                        [{"version": 1, "saved_at": t["updated"], "summary": "Created", "data": t}])
        return t

    def save(self, t, base_version, summary):
        """Writes the new version if nobody saved since base_version, and records it in the history."""
        with self._lock():
            current = self.get(t["id"])
            if current is None:
                raise KeyError(t["id"])
            if current["version"] != base_version:
                raise VersionConflict(current)
            t = dict(t, version=base_version + 1)
            self._write(self._path(t["id"]), t)
            hist_path = self._path(t["id"], ".history.json")
            history = self._read(hist_path, [])
            history.append({"version": t["version"], "saved_at": t["updated"], "summary": summary, "data": t})
            self._write(hist_path, history[-HISTORY_LIMIT:])
        return t

    def history(self, tid):
        return [{k: h[k] for k in ("version", "saved_at", "summary")}
                for h in reversed(self._read(self._path(tid, ".history.json"), []))]

    def version(self, tid, version):
        for h in self._read(self._path(tid, ".history.json"), []):
            if h["version"] == version:
                return h["data"]
        return None

    def delete(self, tid):
        with self._lock():
            for suffix in (".json", ".history.json"):
                try:
                    os.remove(self._path(tid, suffix))
                except FileNotFoundError:
                    pass


# ---------------------------------------------------------------------------
# Passwords ("spaces"): each password opens its own set of tournaments
# ---------------------------------------------------------------------------

class SpaceStore:
    """
    spaces.json next to the tournaments: {"pepper": hex, "spaces": {space id: {"key", "created"}}}.
    A space is found by key = HMAC-SHA256(pepper, password), so passwords are never stored and the
    lookup stays fast. The pepper is made once and lives with the data, so it moves with backups.
    """

    def __init__(self, directory):
        self.dir = directory
        self.path = os.path.join(directory, "spaces.json")
        self._lock_owner = TournamentStore(directory)

    def _load(self):
        data = TournamentStore._read(self.path, None)
        if data is None:
            data = {"pepper": secrets.token_hex(32), "spaces": {}}
        return data

    def _key(self, data, password):
        import hmac
        import hashlib
        return hmac.new(bytes.fromhex(data["pepper"]), password.encode("utf-8"), hashlib.sha256).hexdigest()

    def find(self, password):
        """The space id this password opens, or None."""
        data = self._load()
        key = self._key(data, password)
        return next((sid for sid, sp in data["spaces"].items() if sp["key"] == key), None)

    def exists(self, space_id):
        return space_id in self._load()["spaces"]

    def create(self, password):
        """Makes a space for a new password (or returns the one it already opens)."""
        with self._lock_owner._lock():
            data = self._load()
            key = self._key(data, password)
            for sid, sp in data["spaces"].items():
                if sp["key"] == key:
                    return sid
            sid = "s_" + secrets.token_hex(5)
            data["spaces"][sid] = {"key": key, "created": _now()}
            TournamentStore._write(self.path, data)
            return sid
