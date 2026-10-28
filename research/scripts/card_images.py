"""
Write input/card_images.json: {fighter id: {card title as in heroes.json: image url}}.

    python -X utf8 research/scripts/card_images.py

The images are the card scans of the Unmatched card database (unmatched.cards). Some newer decks
have no cards there yet; their cards are left out and the site shows the card text instead.
"""
import json
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = "https://unmatched.cards/api/db/decks"


def norm(s):
    s = re.sub(r"\s*\d️?⃣", "", s)  # Shakespeare's titles end in a keycap value, "Horror 2️⃣"
    return re.sub(r"[^a-z0-9]", "", s.lower())


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "unmatched-matcher"}), timeout=30)


def works(url):
    for _ in range(3):  # the image server sometimes fails a request when sent many at once
        try:
            with get(url) as r:
                return r.headers.get("Content-Type", "").startswith("image")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False
        except (urllib.error.URLError, TimeoutError):
            pass
    return False


def main():
    with get(API) as r:
        decks = json.load(r)["decks"]
    fighters = json.loads((ROOT / "input/fighters.json").read_text(encoding="utf-8"))["fighters"]
    heroes = json.loads((ROOT / "input/heroes.json").read_text(encoding="utf-8"))
    by_name = {}
    for deck in decks:
        for key in [deck["name"], deck["slug"]] + [h[k] for h in deck["heroes"] for k in ("name", "slug")]:
            by_name.setdefault(norm(key), deck)
    out, missing = {}, []
    for f in fighters:
        # the database drops "The" and some surnames ("Golden Bat", "Philippa")
        keys = [f["name"], f["id"], re.sub(r"^The ", "", f["name"]), f["name"].split()[0]]
        deck = next((by_name[norm(k)] for k in keys if norm(k) in by_name), None)
        images = {norm(c["title"]): c["image"] for c in (deck or {}).get("cards", []) if c.get("image")}
        found = {c["title"]: images[norm(c["title"])] for c in heroes[f["id"]]["deck"] if norm(c["title"]) in images}
        if found:
            out[f["id"]] = found
        if len(found) < len({c["title"] for c in heroes[f["id"]]["deck"]}):
            missing.append(f["id"])
    urls = sorted({u for found in out.values() for u in found.values()})
    broken = {u for u, ok in zip(urls, ThreadPoolExecutor(16).map(works, urls)) if not ok}
    out = {fid: {t: u for t, u in found.items() if u not in broken} for fid, found in out.items()}
    print(f"{len(broken)} broken links left out: {', '.join(sorted(broken))}")
    (ROOT / "input/card_images.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(out)} fighters with card images; incomplete or none: {', '.join(missing)}")


if __name__ == "__main__":
    main()
