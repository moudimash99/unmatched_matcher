"""
Pull the battlefield list from The Unmatched Club (https://www.the-unmatched.club/maps):
name, size, zones, spaces, player count and the box each map comes in.

Writes input/maps.json, keyed by the Club's map key (e.g. "the-alamo"), with the
set named the way input/fighters.json names it so the app can tell which maps a
collection owns. Map images are saved, shrunk, to static/maps/<key>.webp (only
the ones not there yet; --images refetches them all).

Usage:  python fetch_maps.py [--images]
"""
import io
import json
import os
import sys
import urllib.request

from PIL import Image

MAPS_URL = "https://www.the-unmatched.club/maps/__data.json"
OUT_FILE = "input/maps.json"
IMAGE_DIR = os.path.join("static", "maps")
IMAGE_MAX_SIZE = (640, 640)

# The Club's set keys -> our set names (input/fighters.json "set").
CLUB_SET_TO_SET = {
    "adventures-tales-to-amaze": "Tales to Amaze",
    "battle-of-legends-volume-one": "Battle of Legends Vol. 1",
    "battle-of-legends-volume-two": "Battle of Legends Vol. 2",
    "battle-of-legends-volume-three": "Battle of Legends Vol. 3",
    "brains-and-brawn": "Brains and Brawn",
    "buffy-the-vampire-slayer": "Buffy the Vampire Slayer",
    "cobble-fog": "Cobble & Fog",
    "for-king-and-country": "For King and Country",
    "hells-kitchen": "Hell's Kitchen",
    "houdini-vs-the-genie": "Houdini vs. The Genie",
    "jurassic-park-ingen-vs-raptors": "InGen vs. Raptors",
    "jurassic-park-sattler-vs-trex": "Dr. Sattler vs. T-Rex",
    "little-red-riding-hood-vs-beowulf": "Beowulf vs. Little Red Riding Hood",
    "muhammad-ali-vs-bruce-lee": "Muhammad Ali vs. Bruce Lee",
    "redemption-row": "Redemption Row",
    "robin-hood-vs-bigfoot": "Robin Hood vs. Bigfoot",
    "slings-and-arrows": "Slings and Arrows",
    "stars-and-stripes": "Stars and Stripes",
    "suns-origin": "Sun's Origin",
    "teen-spirit": "Teen Spirit",
    "the-witcher-realms-fall": "The Witcher: Realms Fall",
    "the-witcher-steel-silver": "The Witcher: Steel and Silver",
}
# Maps played on Tabletop League that the Club doesn't list yet. Unknown details stay None.
EXTRA_MAPS = {
    "technodrome": {"name": "Technodrome", "set": "TMNT: Shredder vs. Krang"},
    "new-york-city": {"name": "New York City", "set": None},
}


def _decode(payload):
    """Unflattens the SvelteKit (devalue) payload and returns the maps list."""
    for node in payload["nodes"]:
        if not node or node.get("type") != "data":
            continue
        data = node["data"]

        def resolve(i):
            if not isinstance(i, int) or i < 0:
                return None
            v = data[i]
            if isinstance(v, dict):
                return {k: resolve(x) for k, x in v.items()}
            if isinstance(v, list):
                return [resolve(x) for x in v]
            return v

        root = data[0]
        if isinstance(root, dict) and "maps" in root:
            return resolve(0)["maps"]
    return []


def fetch_maps():
    req = urllib.request.Request(MAPS_URL, headers={"User-Agent": "unmatched-matcher-maps-sync"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return _decode(json.load(resp))


def build(raw_maps):
    maps, unknown_sets = {}, set()
    for m in raw_maps:
        if not m.get("isActive", True):
            continue
        club_set = (m.get("set") or {}).get("key")
        set_name = CLUB_SET_TO_SET.get(club_set)
        if club_set and not set_name:
            unknown_sets.add(club_set)
        entry = {
            "key": m["key"],
            "name": m["name"],
            "set": set_name,
            "size": m.get("size"),
            "zones": m.get("zonesCount"),
            "spaces": m.get("spacesCount"),
            "min_players": m.get("minPlayers"),
            "max_players": m.get("maxPlayers"),
            "image": m.get("image"),
        }
        maps[m["key"]] = entry
    for key, extra in EXTRA_MAPS.items():
        if key not in maps:
            maps[key] = {"key": key, "name": extra["name"], "set": extra.get("set"), "size": None, "zones": None,
                         "spaces": None, "min_players": None, "max_players": None, "image": None}
    return dict(sorted(maps.items())), unknown_sets


def _existing_image(key):
    for ext in ("webp", "avif"):
        if os.path.exists(os.path.join(IMAGE_DIR, f"{key}.{ext}")):
            return f"{key}.{ext}"
    return None


def save_images(maps, refetch=False):
    """Downloads each map's image into static/maps/ and points the entry's "thumb" at it."""
    os.makedirs(IMAGE_DIR, exist_ok=True)
    saved = 0
    for key, m in maps.items():
        if m.get("image") and (refetch or not _existing_image(key)):
            req = urllib.request.Request(m["image"], headers={"User-Agent": "unmatched-matcher-maps-sync"})
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = resp.read()
                try:
                    img = Image.open(io.BytesIO(data))
                    img.thumbnail(IMAGE_MAX_SIZE)
                    img.save(os.path.join(IMAGE_DIR, f"{key}.webp"), "WEBP", quality=80)
                except RuntimeError:
                    # AVIF without a decoder in this Pillow build: keep the original, browsers show it
                    with open(os.path.join(IMAGE_DIR, f"{key}.avif"), "wb") as f:
                        f.write(data)
                saved += 1
            except (OSError, ValueError) as e:
                print(f"  {key}: image not saved ({e})")
        found = _existing_image(key)
        m["thumb"] = f"maps/{found}" if found else None
    return saved


def main():
    maps, unknown_sets = build(fetch_maps())
    saved = save_images(maps, refetch="--images" in sys.argv[1:])
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(maps, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote {len(maps)} maps to {OUT_FILE} ({saved} images saved to {IMAGE_DIR})")
    if unknown_sets:
        print("Sets with no entry in CLUB_SET_TO_SET (their maps have set=None):", ", ".join(sorted(unknown_sets)))


if __name__ == "__main__":
    main()
