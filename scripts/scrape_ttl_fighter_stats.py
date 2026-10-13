"""
Collect all-time fighter x map and matchup x map counts from Tabletop League's
public fighter stats pages (/games/unmatched/stats/characters/<slug>), for the
per-map stats (GitHub issue #42).

Each fighter page loads a "Battle Grid": the fighter's plays and wins against
every opponent on every map. The page fetches it itself after loading; this
script opens the page in a headless browser and keeps that response. One page
per fighter covers every game TTL has, so this replaces walking match pages
for map numbers. Turn order and end health aren't on these pages; they still
come from scrape_ttl_matches.py.

Writes (relative to the repo root):
  input/ttl_fighter_grids.json             counts per fighter, our ids and Club map keys
  scratch/ttl_fighter_raw/<slug>.txt.gz    raw grid responses (gitignored), for --reparse

Usage:
  python scripts/scrape_ttl_fighter_stats.py              # fighters not fetched in the last 7 days
  python scripts/scrape_ttl_fighter_stats.py --max-age-days 0   # refetch everyone
  python scripts/scrape_ttl_fighter_stats.py --only bruce-lee
  python scripts/scrape_ttl_fighter_stats.py --reparse    # rebuild the json from the raw cache
"""
import argparse
import datetime as dt
import gzip
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scrape_ttl_matches import (  # noqa: E402
    MAX_FAILURES_IN_A_ROW, ROOT, SITE, USER_AGENT,
    _launch, _load_json, _load_mapper, _pause, _with_retries, _write_json,
)

GRIDS_FILE = os.path.join(ROOT, "input", "ttl_fighter_grids.json")
RAW_DIR = os.path.join(ROOT, "scratch", "ttl_fighter_raw")
INDEX_URL = SITE + "/games/unmatched/stats/characters"
FIGHTER_HREF = re.compile(r"^/games/unmatched/stats/characters/([a-z0-9-]+)$")
GRID_WAIT_SECONDS = 30
# Alternate card versions ("Buffy - Alt 1.0") are their own TTL fighters; they're left out, not merged
ALT_VERSION = re.compile(r"\s-\s*alt\b", re.I)


# ---------------------------------------------------------------------------
# Raw grid response -> counts (our fighter ids, Club map keys)
# ---------------------------------------------------------------------------
def parse_grid_response(text):
    """The grid payload ({opponents, maps, grandTotal}) from a server-action response, or None."""
    for line in text.splitlines():
        _, sep, body = line.partition(":")
        if sep and body.startswith("{") and '"opponents"' in body:
            data = json.loads(body)
            if "opponents" in data and "maps" in data:
                return data
    return None


def normalize_grid(fighter_id, grid, mapper, unmapped):
    """
    {games, wins, maps: {map: {games, wins}}, vs: {opp: {map: {games, wins}}}} for one fighter.
    Cells with an unknown opponent or map are left out and counted in `unmapped`.
    """
    map_keys = {}
    for m in grid["maps"]:
        key = mapper.map(m["name"]) or mapper.map(m["slug"])
        if key is None:
            unmapped["maps"][m["name"]] = unmapped["maps"].get(m["name"], 0) + int(m.get("totalPlays") or 0)
        map_keys[m["id"]] = key

    out = {"games": 0, "wins": 0, "maps": {}, "vs": {}}
    for opp in grid["opponents"]:
        if ALT_VERSION.search(opp["name"]):
            alts = unmapped.setdefault("alt_versions", {})
            alts[opp["name"]] = alts.get(opp["name"], 0) + int(opp["totalPlays"])
            continue
        opp_id = mapper.fighter(opp["name"]) or mapper.fighter(opp["slug"])
        if opp_id is None:
            unmapped["fighters"][opp["name"]] = unmapped["fighters"].get(opp["name"], 0) + int(opp["totalPlays"])
            continue
        if opp_id == fighter_id:
            continue
        for map_id, c in opp["cells"].items():
            key = map_keys.get(map_id)
            plays, wins = int(c["plays"]), int(c["wins"])
            if key is None or not plays:
                continue
            for table in (out["maps"].setdefault(key, {"games": 0, "wins": 0}),
                          out["vs"].setdefault(opp_id, {}).setdefault(key, {"games": 0, "wins": 0})):
                table["games"] += plays
                table["wins"] += wins
            out["games"] += plays
            out["wins"] += wins
    return out


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------
def _raw_path(slug):
    return os.path.join(RAW_DIR, slug + ".txt.gz")


def _read_raw(slug):
    with gzip.open(_raw_path(slug), "rt", encoding="utf-8") as f:
        return f.read()


def _write_raw(slug, text):
    os.makedirs(RAW_DIR, exist_ok=True)
    tmp = _raw_path(slug) + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, _raw_path(slug))


def build_grids(slugs, mapper):
    """input/ttl_fighter_grids.json content from the cached raw responses of these slugs."""
    fighters, unmapped, sources = {}, {"fighters": {}, "maps": {}}, {}
    for slug in sorted(slugs):
        if ALT_VERSION.search(slug.replace("-alt-", " - alt ")):
            continue
        fid = mapper.fighter(slug)
        if fid is None:
            unmapped["fighters"][slug] = unmapped["fighters"].get(slug, 0) + 1
            continue
        grid = parse_grid_response(_read_raw(slug))
        if grid is None:
            continue
        fighters[fid] = normalize_grid(fid, grid, mapper, unmapped)
        sources[fid] = {"slug": slug, "fetched": dt.date.fromtimestamp(os.path.getmtime(_raw_path(slug))).isoformat()}
    dates = [s["fetched"] for s in sources.values()]
    return {
        "source": INDEX_URL,
        "fetched_from": min(dates) if dates else None,
        "fetched_to": max(dates) if dates else None,
        "pages": sources,
        "unmapped": unmapped,
        "fighters": fighters,
    }


def _cached_slugs():
    if not os.path.isdir(RAW_DIR):
        return []
    return [f[:-len(".txt.gz")] for f in os.listdir(RAW_DIR) if f.endswith(".txt.gz")]


def write_grids(mapper):
    data = build_grids(_cached_slugs(), mapper)
    _write_json(GRIDS_FILE, data)
    games = sum(f["games"] for f in data["fighters"].values()) // 2
    print(f"Wrote {GRIDS_FILE}: {len(data['fighters'])} fighters, ~{games:,} games "
          f"(pages fetched {data['fetched_from']} to {data['fetched_to']})")
    for kind in ("fighters", "maps"):
        if data["unmapped"][kind]:
            names = ", ".join(f"{n} ({c})" for n, c in sorted(data["unmapped"][kind].items(), key=lambda x: -x[1]))
            print(f"UNMAPPED {kind}: {names}  -> add aliases in scripts/scrape_ttl_matches.py, then --reparse")
    alts = data["unmapped"].get("alt_versions")
    if alts:
        print(f"Left out {len(alts)} alternate fighter versions ({sum(alts.values())} game-sides)")


# ---------------------------------------------------------------------------
# Browser
# ---------------------------------------------------------------------------
def _fighter_slugs(page):
    _with_retries(lambda: page.goto(INDEX_URL, wait_until="networkidle", timeout=60000), "fighter index")
    hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))")
    return sorted({m.group(1) for h in hrefs if (m := FIGHTER_HREF.match(h or ""))})


def _fetch_grid(page, slug, captured):
    url = f"{INDEX_URL}/{slug}"

    def load():
        captured.clear()
        resp = page.goto(url, wait_until="domcontentloaded", timeout=60000)
        if resp is None or resp.status >= 400:
            raise RuntimeError(f"HTTP {resp.status if resp else '?'}")
        deadline = time.time() + GRID_WAIT_SECONDS
        while time.time() < deadline:
            for text in captured:
                if parse_grid_response(text) is not None:
                    return text
            page.wait_for_timeout(250)
        raise TimeoutError("grid data never arrived")
    return _with_retries(load, slug)


def scrape(max_age_days, only, channel):
    from playwright.sync_api import sync_playwright

    mapper = _load_mapper()
    now = time.time()
    fetched = failures = 0
    with sync_playwright() as p:
        browser = _launch(p, channel)
        context = browser.new_context(user_agent=USER_AGENT, timezone_id="UTC", locale="en-US")
        page = context.new_page()
        captured = []

        def keep_grid(route):
            # The page's own grid request (a POST back to the fighter page): pass it through and
            # keep the body, which can't be read from a response event once the page moves on.
            if route.request.method != "POST":
                return route.continue_()
            resp = route.fetch()
            captured.append(resp.text())
            route.fulfill(response=resp)
        page.route(re.compile(r"/games/unmatched/stats/characters/[a-z0-9-]+$"), keep_grid)

        slugs = only or _fighter_slugs(page)
        print(f"{len(slugs)} fighter pages", flush=True)
        try:
            for slug in slugs:
                path = _raw_path(slug)
                if not only and os.path.exists(path) and now - os.path.getmtime(path) < max_age_days * 86400:
                    continue
                _pause()
                try:
                    text = _fetch_grid(page, slug, captured)
                except RuntimeError as e:
                    failures += 1
                    print(f"  {e}", flush=True)
                    if failures >= MAX_FAILURES_IN_A_ROW:
                        print("Too many failures in a row; stopping (rerun to resume).")
                        break
                    continue
                failures = 0
                _write_raw(slug, text)
                fetched += 1
                grid = parse_grid_response(text)
                print(f"  {slug}: {grid['grandTotal']['plays']} games", flush=True)
        finally:
            browser.close()
    print(f"Fetched {fetched} fighter pages.")
    write_grids(mapper)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-age-days", type=float, default=7, help="refetch pages older than this (0 = all)")
    ap.add_argument("--only", nargs="+", metavar="SLUG", help="fetch just these fighter slugs")
    ap.add_argument("--reparse", action="store_true", help="rebuild the json from the raw cache, no browsing")
    ap.add_argument("--channel", help="browser channel, e.g. chrome (default: Playwright's Chromium, then Chrome)")
    args = ap.parse_args(argv)
    if args.reparse:
        write_grids(_load_mapper())
    else:
        scrape(args.max_age_days, args.only, args.channel)


if __name__ == "__main__":
    main()
