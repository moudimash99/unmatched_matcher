"""
Pull each fighter's card data from The Unmatched Club (https://www.the-unmatched.club/heroes)
for the fighter pages: stats, special ability, sidekicks and full deck list.

Writes input/heroes.json, keyed by our fighter id (via "club_key" in input/fighters.json).

Usage:  python fetch_heroes.py
"""
import json
import re
import time
import urllib.request
from collections import Counter

FIGHTERS_FILE = "input/fighters.json"
HERO_URL = "https://www.the-unmatched.club/heroes/{key}/__data.json"

# The site's sidekick field is wrong for a few heroes (their decks have no
# sidekick cards); trust the deck over the field.
NO_SIDEKICK = {"bloody_mary", "the_genie", "the_golden_bat"}


def _decode(payload):
    """Unflattens the SvelteKit (devalue) payload and returns the hero page data."""
    for node in payload["nodes"]:
        if not node or node.get("type") != "data":
            continue
        data = node["data"]
        if "fetchedHero" not in json.dumps(data[0]):
            continue

        def resolve(i):
            if not isinstance(i, int) or i < 0:
                return None
            v = data[i]
            if isinstance(v, dict):
                return {k: resolve(x) for k, x in v.items()}
            if isinstance(v, list):
                return [resolve(x) for x in v]
            return v

        return resolve(0)
    return None


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _to_int(value):
    """The site stores some numbers as strings; None if not a number."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def fetch_hero(club_key):
    req = urllib.request.Request(HERO_URL.format(key=club_key), headers={"User-Agent": "unmatched-matcher-heroes-sync"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return _decode(json.load(resp))


def to_profile(fighter_id, page):
    hero = page["fetchedHero"]
    sidekicks = []
    if fighter_id not in NO_SIDEKICK:
        counts = Counter(
            (s.get("name"), s.get("attack"), s.get("startHealth"), s.get("move"))
            for s in hero.get("sidekicks") or [] if s.get("name")
        )
        sidekicks = [
            {"name": name, "count": n, "attack": attack, "hp": _to_int(hp), "move": _to_int(move)}
            for (name, attack, hp, move), n in counts.items()
        ]

    deck = []
    for c in page.get("fetchedDeck") or []:
        card = c.get("card") or {}
        effect = " ".join(filter(None, (card.get(k) for k in (
            "effectImmediately", "effectDuring", "effectAfter", "effect", "effectOngoing"))))
        deck.append({
            "title": _clean(card.get("title")),
            "type": c.get("type"),
            "value": c.get("value"),
            "boost": c.get("boostValue"),
            "copies": c.get("copies") or 1,
            "character": _clean(c.get("bannerName")),
            "effect": _clean(effect),
        })
    type_order = {"attack": 0, "defense": 1, "versatile": 2, "scheme": 3}
    deck.sort(key=lambda c: (type_order.get(c["type"], 9), -(c["value"] or 0), c["title"]))

    return {
        "attack": hero.get("attack"),
        "hp": hero.get("startHealth"),
        "move": hero.get("move"),
        "special_ability": _clean(hero.get("specialAbility")),
        "sidekicks": sidekicks,
        "deck": deck,
    }


if __name__ == "__main__":
    with open(FIGHTERS_FILE, "r", encoding="utf-8") as f:
        fighters = json.load(f)["fighters"]

    heroes = {}
    for f in fighters:
        page = fetch_hero(f["club_key"])
        time.sleep(0.5)  # be polite to the site
        if not page or not page.get("fetchedDeck"):
            print(f"  ! {f['id']}: no card data yet, skipped")
            continue
        heroes[f["id"]] = to_profile(f["id"], page)

    print(f"Heroes with card data: {len(heroes)}/{len(fighters)}")
    with open("input/heroes.json", "w", encoding="utf-8") as f:
        json.dump(heroes, f, indent=2, ensure_ascii=False, sort_keys=True)
