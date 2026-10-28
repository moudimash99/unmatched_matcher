"""
Write input/card_images.json: {fighter id: {card title as in heroes.json: image url}}.

    python -X utf8 research/scripts/card_images.py

Two sources have card scans: The Unmatched Club (the deck data in input/heroes.json comes from it,
see fetch_heroes.py) and the Unmatched card database (unmatched.cards). Their scans differ in
size (some unmatched.cards decks are only 100 pixels wide), so each card gets the smallest scan
that's still sharp, or the largest it has. Broken links are left out, and the site shows those cards' text instead.
"""
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from fetch_heroes import _clean, fetch_hero  # noqa: E402

API = "https://unmatched.cards/api/db/decks"
SHARP = 380  # pixels wide: enough for the 250-pixel hover card on a high-resolution screen


def norm(s):
    s = re.sub(r"\s*\d️?⃣", "", s)  # Shakespeare's titles end in a keycap value, "Horror 2️⃣"
    return re.sub(r"[^a-z0-9]", "", s.lower())


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "unmatched-matcher"}), timeout=30)


def width(url):
    """The image's width in pixels, or 0 if it doesn't load."""
    for _ in range(3):  # the image servers sometimes fail a request when sent many at once
        try:
            with get(url) as r:
                return Image.open(io.BytesIO(r.read())).size[0]
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 0
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
    return 0


def club_images(fighters):
    """{fighter id: {title: url}} from The Unmatched Club's deck lists."""
    def one(f):
        time.sleep(0.2)  # be polite to the site
        page = fetch_hero(f["club_key"]) or {}
        return f["id"], {_clean((c.get("card") or {}).get("title")): c.get("image")
                         for c in page.get("fetchedDeck") or [] if c.get("image")}
    with ThreadPoolExecutor(4) as pool:
        return dict(pool.map(one, fighters))


def database_images(fighters):
    """{fighter id: {normalised title: url}} from the unmatched.cards database."""
    with get(API) as r:
        decks = json.load(r)["decks"]
    by_name = {}
    for deck in decks:
        for key in [deck["name"], deck["slug"]] + [h[k] for h in deck["heroes"] for k in ("name", "slug")]:
            by_name.setdefault(norm(key), deck)
    out = {}
    for f in fighters:
        # the database drops "The" and some surnames ("Golden Bat", "Philippa")
        keys = [f["name"], f["id"], re.sub(r"^The ", "", f["name"]), f["name"].split()[0]]
        deck = next((by_name[norm(k)] for k in keys if norm(k) in by_name), None)
        out[f["id"]] = {norm(c["title"]): c["image"] for c in (deck or {}).get("cards", []) if c.get("image")}
    return out


def main():
    fighters = json.loads((ROOT / "input/fighters.json").read_text(encoding="utf-8"))["fighters"]
    heroes = json.loads((ROOT / "input/heroes.json").read_text(encoding="utf-8"))
    club, database = club_images(fighters), database_images(fighters)

    # {fighter id: {title: (club url, database url)}}
    candidates = {f["id"]: {c["title"]: (club[f["id"]].get(c["title"]), database[f["id"]].get(norm(c["title"])))
                            for c in heroes.get(f["id"], {}).get("deck", [])} for f in fighters}
    urls = sorted({u for cards in candidates.values() for pair in cards.values() for u in pair if u})
    with ThreadPoolExecutor(16) as pool:
        widths = dict(zip(urls, pool.map(width, urls)))

    out, missing, small = {}, [], []
    for fid, cards in candidates.items():
        found = {}
        for title, pair in cards.items():
            # the smallest scan that's still sharp on a high-resolution screen, else the largest
            ok = [u for u in pair if u and widths[u]]
            sharp = [u for u in ok if widths[u] >= SHARP]
            url = min(sharp, key=widths.get) if sharp else max(ok, key=widths.get, default=None)
            if url:
                found[title] = url
        if found:
            out[fid] = found
            if min(widths[u] for u in found.values()) < 240:
                small.append(fid)
        if len(found) < len(cards):
            missing.append(f"{fid} ({len(found)}/{len(cards)})")
    (ROOT / "input/card_images.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(out)} fighters with card images; cards without one: {', '.join(missing) or 'none'}")
    print(f"decks with a scan under 240 pixels wide: {', '.join(small) or 'none'}")


if __name__ == "__main__":
    main()
