"""
Collect per-game Unmatched results (fighters, map, turn order, end health) from
Tabletop League's public match pages, for the per-map stats (GitHub issue #42).

The pages are client-rendered, so they are opened in a headless browser
(Playwright). The listing gives match links; each match page lists every game
in the series with its map.

Writes (all relative to the repo root):
  input/ttl_games.jsonl         one normalized game per line
  input/ttl_scrape_state.json   matches already done (incremental + resumable)
  input/ttl_unmapped.json       TTL fighter / map names we could not map
  scratch/ttl_raw/<id>.html.gz  rendered match pages (gitignored), for --reparse

Usage:
  python scripts/scrape_ttl_matches.py                  # new matches, up to 500
  python scripts/scrape_ttl_matches.py --max-matches 50
  python scripts/scrape_ttl_matches.py --since 2026-09-01
  python scripts/scrape_ttl_matches.py --reparse        # rebuild jsonl from the raw cache

Needs `pip install playwright` and a Chromium (`playwright install chromium`,
or a local Chrome via --channel chrome). --reparse needs neither.
"""
import argparse
import datetime as dt
import gzip
import json
import os
import random
import re
import sys
import time
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIGHTERS_FILE = os.path.join(ROOT, "input", "fighters.json")
MAPS_FILE = os.path.join(ROOT, "input", "maps.json")
GAMES_FILE = os.path.join(ROOT, "input", "ttl_games.jsonl")
STATE_FILE = os.path.join(ROOT, "input", "ttl_scrape_state.json")
UNMAPPED_FILE = os.path.join(ROOT, "input", "ttl_unmapped.json")
RAW_DIR = os.path.join(ROOT, "scratch", "ttl_raw")

SITE = "https://www.tabletopleague.com"
LISTING_URL = SITE + "/games/unmatched/matches"
USER_AGENT = "unmatched-matcher-map-stats (+https://github.com/moudimash99/unmatched_matcher)"
MATCH_HREF = re.compile(r"/matches/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$")

DELAY_SECONDS = (2.0, 3.0)   # pause between page loads
MAX_RETRIES = 5
MAX_FAILURES_IN_A_ROW = 3

# TTL display names that don't match a fighter's name, id or Club key.
FIGHTER_ALIASES = {
    "yennefer": "yennefer_triss",
    "triss": "yennefer_triss",
    "ingen": "robert_muldoon",
}
# TTL map names that don't match a Club map name or key (spelling differences).
MAP_ALIASES = {
    "tsingshanmonestary": "tsing-shan-monastery",
}


# ---------------------------------------------------------------------------
# HTML -> raw match (TTL names only; no mapping)
# ---------------------------------------------------------------------------
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class _Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.children, self.parent = tag, dict(attrs), [], parent

    @property
    def cls(self):
        return self.attrs.get("class") or ""

    def elements(self):
        return [c for c in self.children if isinstance(c, _Node)]

    def iter(self):
        yield self
        for c in self.elements():
            yield from c.iter()

    def text(self):
        return "".join(c if isinstance(c, str) else c.text() for c in self.children)

    def own_text(self):
        return re.sub(r"\s+", " ", self.text()).strip()


class _TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("#root", {}, None)
        self.cur = self.root
        self._skip = 0  # inside <script>/<style>

    def handle_starttag(self, tag, attrs):
        if self._skip:
            return
        if tag in ("script", "style"):
            self._skip = 1
            return
        node = _Node(tag, attrs, self.cur)
        self.cur.children.append(node)
        if tag not in _VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        if not self._skip:
            self.cur.children.append(_Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = 0
            return
        if self._skip or tag in _VOID:
            return
        node = self.cur
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self.cur = node.parent

    def handle_data(self, data):
        if not self._skip:
            self.cur.children.append(data)


def _parse_html(html):
    builder = _TreeBuilder()
    builder.feed(html)
    builder.close()
    return builder.root


def _parse_side(side):
    """One player's half of a game card: fighter, player, turn order, end health, won."""
    side_info = {"fighter": None, "player": None, "went_first": None, "end_health": None, "won": False}
    for node in side.iter():
        cls = node.cls
        if node.tag == "span" and "truncate" in cls and "title" in node.attrs and side_info["fighter"] is None:
            side_info["fighter"] = node.attrs["title"].strip() or None
            side_info["won"] = "text-success" in (node.parent.cls if node.parent else "")
        elif node.tag == "span" and "uppercase" in cls and "tracking-wider" in cls and side_info["player"] is None:
            side_info["player"] = node.own_text() or None
        elif node.attrs.get("role") == "img" and node.attrs.get("aria-label", "").startswith("Ending health"):
            m = re.search(r"Ending health (-?\d+)", node.attrs["aria-label"])
            if m and side_info["end_health"] is None:
                side_info["end_health"] = int(m.group(1))
        elif node.tag == "div" and "bg-black/70" in cls:
            badge = node.own_text()
            if badge in ("P1", "P2"):
                side_info["went_first"] = badge == "P1"
    return side_info


def _parse_game_card(card):
    """A 'Game Details' card -> {index, map, a, b}, or None if it isn't one."""
    # The card has a desktop row (hidden sm:flex) and a mobile copy; read the desktop row.
    row = next((n for n in card.elements() if "sm:flex" in n.cls and "hidden" in n.cls.split()), None)
    if row is None or len(row.elements()) < 3:
        return None
    left, middle, right = row.elements()[:3]
    labels = [n.own_text() for n in middle.iter() if n.tag == "span"]
    index = next((int(m.group(1)) for t in labels for m in [re.match(r"Game (\d+)$", t, re.I)] if m), None)
    if index is None:
        return None
    map_name = next((t for t in labels if t and not re.match(r"Game \d+$", t, re.I)), None)
    return {"index": index, "map": map_name, "a": _parse_side(left), "b": _parse_side(right)}


def _parse_header(root):
    """Competition, format (BO1/BO3…), ruleset label and date from the match header."""
    header = {"competition": None, "organizer": None, "format": None, "ruleset": None, "played_at": None}
    link = next((n for n in root.iter() if n.tag == "a"
                 and re.match(r"^/o/[^/]+/[^/]+$", n.attrs.get("href", ""))
                 and n.parent is not None and any(c.tag == "span" for c in n.parent.elements())), None)
    if link is None:
        return header
    header["competition"] = link.own_text() or None
    header["organizer"] = link.attrs["href"].split("/")[2]
    texts = [n.own_text() for n in link.parent.iter() if n.tag == "span"]
    texts = [t for t in texts if t and t not in ("•", "/")]
    for i, t in enumerate(texts):
        if header["format"] is None and re.match(r"^(BO\d+|TWO[_ ]GAMES?)$", t, re.I):
            header["format"] = t.upper().replace(" ", "_")
            nxt = texts[i + 1] if i + 1 < len(texts) else None
            if nxt and not _parse_date(nxt):
                header["ruleset"] = nxt
        if header["played_at"] is None and _parse_date(t):
            header["played_at"] = _parse_date(t)
    return header


def _parse_date(text):
    m = re.match(r"^([A-Z][a-z]{2}) (\d{1,2}), (\d{4})", text or "")
    if not m:
        return None
    try:
        return dt.datetime.strptime(" ".join(m.groups()), "%b %d %Y").date().isoformat()
    except ValueError:
        return None


def parse_match_page(html):
    """Rendered match page -> raw match dict with TTL's own names (see normalize_match)."""
    root = _parse_html(html)
    h1 = next((n for n in root.iter() if n.tag == "h1"), None)
    status_node = h1.parent.parent if h1 is not None and h1.parent is not None else None
    status = None
    if status_node is not None:
        status = next((n.attrs["title"] for n in status_node.iter() if n.tag == "span" and "title" in n.attrs), None)
    raw = {
        "status": status,
        **_parse_header(root),
        # Team (2v2) and "double" matches put several fighters per side
        "team": bool(re.search(r'isTeamMatch\\*"\s*:\s*true', html)),
        "double": bool(re.search(r'isDoubleMatch\\*"\s*:\s*true', html)),
        "draft": any(n.own_text().lower() == "draft details" for n in root.iter() if n.tag in ("h2", "h3", "h4", "div", "span")
                     and len(n.elements()) == 0),
        "games": [],
    }
    seen = set()
    for node in root.iter():
        if node.tag == "div" and node.attrs.get("data-slot") == "card":
            game = _parse_game_card(node)
            if game and game["index"] not in seen:
                seen.add(game["index"])
                raw["games"].append(game)
    raw["games"].sort(key=lambda g: g["index"])
    return raw


# ---------------------------------------------------------------------------
# Raw match -> normalized games (our fighter ids, Club map keys)
# ---------------------------------------------------------------------------
def _norm(name):
    name = re.sub(r"\(.*?\)", "", name or "").lower().replace("&", "and")
    return re.sub(r"[^a-z0-9]", "", name)


class NameMapper:
    def __init__(self, fighters, maps):
        self.fighters = {}
        for f in fighters:
            for key in (f["name"], f["id"], f.get("club_key")):
                if key:
                    self.fighters.setdefault(_norm(key), f["id"])
            # "The Golden Bat" -> also "Golden Bat"
            if f["name"].lower().startswith("the "):
                self.fighters.setdefault(_norm(f["name"][4:]), f["id"])
        for alias, fid in FIGHTER_ALIASES.items():
            self.fighters[_norm(alias)] = fid
        self.maps = {}
        for key, m in maps.items():
            self.maps.setdefault(_norm(m["name"]), key)
            self.maps.setdefault(_norm(key), key)
        for alias, key in MAP_ALIASES.items():
            self.maps[_norm(alias)] = key

    def fighter(self, name):
        return self.fighters.get(_norm(name))

    def map(self, name):
        return self.maps.get(_norm(name))


def normalize_match(match_id, raw, mapper, skipped, unmapped):
    """Yields one record per usable game; counts the rest in `skipped` / `unmapped`."""
    def skip(reason, n=1):
        skipped[reason] = skipped.get(reason, 0) + n

    if raw["team"] or raw["double"]:
        skip("team_or_double", max(1, len(raw["games"])))
        return
    for g in raw["games"]:
        a, b = g["a"], g["b"]
        names = [a["fighter"], b["fighter"]]
        if not all(names) or any(n.lower() == "unknown" for n in names):
            skip("missing_fighter")
            continue
        if not g["map"]:
            skip("missing_map")
            continue
        fa, fb, map_key = mapper.fighter(a["fighter"]), mapper.fighter(b["fighter"]), mapper.map(g["map"])
        bad = False
        for name, fid in ((a["fighter"], fa), (b["fighter"], fb)):
            if fid is None:
                unmapped["fighters"][name] = unmapped["fighters"].get(name, 0) + 1
                bad = True
        if map_key is None:
            unmapped["maps"][g["map"]] = unmapped["maps"].get(g["map"], 0) + 1
            bad = True
        if bad:
            skip("unmapped_name")
            continue
        if fa == fb:
            skip("mirror")
            continue
        a_won, b_won = a["won"], b["won"]
        if a_won == b_won and a["end_health"] is not None and b["end_health"] is not None \
                and a["end_health"] != b["end_health"]:
            # No winner highlight: the fighter left standing won
            a_won, b_won = a["end_health"] > b["end_health"], b["end_health"] > a["end_health"]
        if a_won == b_won:
            skip("no_winner")
            continue
        went_first = (a["went_first"], b["went_first"])
        if went_first not in ((True, False), (False, True)):
            went_first = (None, None)
        yield {
            "match_id": match_id,
            "game_index": g["index"],
            "played_at": raw["played_at"],
            "competition": raw["competition"],
            "organizer": raw["organizer"],
            "format": raw["format"],
            "ruleset": raw["ruleset"],
            "selection": "pickBan" if raw["draft"] else None,
            "map": map_key,
            "a": {"fighter": fa, "went_first": went_first[0], "end_health": a["end_health"], "won": a_won},
            "b": {"fighter": fb, "went_first": went_first[1], "end_health": b["end_health"], "won": b_won},
        }


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------
def _load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def _raw_path(match_id):
    return os.path.join(RAW_DIR, match_id + ".html.gz")


def _load_mapper():
    fighters = _load_json(FIGHTERS_FILE, {}).get("fighters", [])
    maps = _load_json(MAPS_FILE, {})
    if not maps:
        sys.exit(f"{MAPS_FILE} is missing; run `python fetch_maps.py` first.")
    return NameMapper(fighters, maps)


def _empty_unmapped():
    return {"fighters": {}, "maps": {}}


def reparse():
    """Rebuilds ttl_games.jsonl and ttl_unmapped.json from the raw page cache only."""
    mapper = _load_mapper()
    state = _load_json(STATE_FILE, {})
    skipped, unmapped = {}, _empty_unmapped()
    files = sorted(f for f in os.listdir(RAW_DIR) if f.endswith(".html.gz")) if os.path.isdir(RAW_DIR) else []
    records = []
    for name in files:
        match_id = name[:-len(".html.gz")]
        with gzip.open(os.path.join(RAW_DIR, name), "rt", encoding="utf-8") as f:
            raw = parse_match_page(f.read())
        if raw["status"] != "Completed":
            continue
        records.extend(normalize_match(match_id, raw, mapper, skipped, unmapped))
    records.sort(key=lambda r: (r["played_at"] or "", r["match_id"], r["game_index"]))
    with open(GAMES_FILE, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    _write_json(UNMAPPED_FILE, unmapped)
    state["skipped"] = skipped
    _write_json(STATE_FILE, state)
    print(f"Reparsed {len(files)} cached matches -> {len(records)} games. Skipped: {skipped or 'none'}")
    _report_unmapped(unmapped)


def _report_unmapped(unmapped):
    for kind in ("fighters", "maps"):
        if unmapped[kind]:
            names = ", ".join(f"{n} ({c})" for n, c in sorted(unmapped[kind].items(), key=lambda x: -x[1]))
            print(f"UNMAPPED {kind}: {names}  -> add aliases in scripts/scrape_ttl_matches.py, then --reparse")


# ---------------------------------------------------------------------------
# Browser
# ---------------------------------------------------------------------------
def _pause():
    time.sleep(random.uniform(*DELAY_SECONDS))


def _launch(playwright, channel):
    from playwright.sync_api import Error as PlaywrightError
    try:
        return playwright.chromium.launch(channel=channel) if channel else playwright.chromium.launch()
    except PlaywrightError:
        if channel:
            raise
        # Playwright's bundled Chromium isn't installed: fall back to a local Chrome
        return playwright.chromium.launch(channel="chrome")


def _with_retries(action, what):
    for attempt in range(MAX_RETRIES):
        try:
            return action()
        except Exception as e:  # network errors, timeouts, 429/5xx raised below
            wait = 5 * 2 ** attempt
            print(f"  {what}: {e.__class__.__name__}: {str(e)[:120]} - retrying in {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"{what}: giving up after {MAX_RETRIES} tries")


def _read_listing(page):
    """Match links on the current listing page, with the date shown on each card."""
    rows = page.evaluate("""() => {
        const out = [];
        for (const a of document.querySelectorAll("a[href*='/matches/']")) {
            const href = a.getAttribute('href');
            if (!/\\/matches\\/[0-9a-f-]{36}$/.test(href)) continue;
            let card = a, text = '';
            for (let i = 0; i < 8 && card; i++, card = card.parentElement) {
                text = card.innerText || '';
                if (/[A-Z][a-z]{2} \\d{1,2}, \\d{4}/.test(text)) break;
            }
            out.push({href, text: text.slice(0, 300)});
        }
        return out;
    }""")
    entries, seen = [], set()
    for row in rows:
        m = MATCH_HREF.search(row["href"])
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        date = re.search(r"([A-Z][a-z]{2} \d{1,2}, \d{4})", row["text"])
        entries.append({"id": m.group(1), "href": row["href"], "date": _parse_date(date.group(1)) if date else None})
    return entries


def _page_position(page):
    text = page.inner_text("body")
    m = re.search(r"Page (\d+) of (\d+)", text)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def _next_listing_page(page):
    """Clicks 'next page'; False when there is no further page."""
    current, total = _page_position(page)
    if current is None or (total is not None and current >= total):
        return False
    button = page.get_by_text(re.compile(rf"^Page {current} of")).locator("xpath=following-sibling::button[1]")
    if button.count() == 0 or button.is_disabled():
        return False
    button.click()
    page.wait_for_function(
        "n => /Page (\\d+) of/.test(document.body.innerText) && "
        "+document.body.innerText.match(/Page (\\d+) of/)[1] === n", arg=current + 1, timeout=30000)
    page.wait_for_timeout(500)
    return True


def _fetch_match(page, href):
    def load():
        # Game cards are server-rendered: no need to wait for images and scripts
        resp = page.goto(SITE + href, wait_until="domcontentloaded", timeout=60000)
        if resp is not None and (resp.status == 429 or resp.status >= 500):
            raise RuntimeError(f"HTTP {resp.status}")
        try:
            page.wait_for_selector("text=Game Details", timeout=15000)
        except Exception:
            pass  # forfeits / unplayed matches have no game cards
        return page.content()
    return _with_retries(load, href)


def scrape(max_matches, since, channel):
    from playwright.sync_api import sync_playwright

    mapper = _load_mapper()
    state = _load_json(STATE_FILE, {})
    done = state.setdefault("done", {})
    pending = state.setdefault("pending", {})
    unmapped = _load_json(UNMAPPED_FILE, _empty_unmapped())
    skipped = state.setdefault("skipped", {})
    os.makedirs(RAW_DIR, exist_ok=True)
    today = dt.date.today().isoformat()
    fetched = new_games = failures = 0

    with sync_playwright() as p:
        browser = _launch(p, channel)
        ctx = browser.new_context(user_agent=USER_AGENT, timezone_id="UTC", locale="en-US")
        listing, detail = ctx.new_page(), ctx.new_page()
        _with_retries(lambda: listing.goto(LISTING_URL, wait_until="networkidle", timeout=60000), "listing")
        try:
            while fetched < max_matches:
                entries = _read_listing(listing)
                if not entries:
                    print("Listing page has no matches; stopping.")
                    break
                todo = [e for e in entries if e["id"] not in done
                        and pending.get(e["id"]) != today
                        and not (since and e["date"] and e["date"] < since)]
                for e in todo:
                    if fetched >= max_matches:
                        break
                    _pause()
                    try:
                        html = _fetch_match(detail, e["href"])
                        failures = 0
                    except RuntimeError as err:
                        failures += 1
                        print(f"  skip {e['id']}: {err}")
                        if failures >= MAX_FAILURES_IN_A_ROW:
                            raise
                        continue
                    fetched += 1
                    with gzip.open(_raw_path(e["id"]), "wt", encoding="utf-8") as f:
                        f.write(html)
                    raw = parse_match_page(html)
                    if raw["status"] != "Completed":
                        pending[e["id"]] = today  # look again on a later run
                        _write_json(STATE_FILE, state)
                        continue
                    records = list(normalize_match(e["id"], raw, mapper, skipped, unmapped))
                    with open(GAMES_FILE, "a", encoding="utf-8") as f:
                        for r in records:
                            f.write(json.dumps(r, ensure_ascii=False) + "\n")
                    new_games += len(records)
                    pending.pop(e["id"], None)
                    done[e["id"]] = {"played_at": raw["played_at"], "games": len(records)}
                    state["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
                    _write_json(STATE_FILE, state)
                    _write_json(UNMAPPED_FILE, unmapped)
                    print(f"[{fetched}/{max_matches}] {raw['played_at']} {raw['competition']}: "
                          f"{len(records)}/{len(raw['games'])} games", flush=True)

                if since and all(e["date"] and e["date"] < since for e in entries):
                    print(f"Reached matches before {since}; stopping.")
                    break
                if not todo and state.get("backfill_complete"):
                    print("Caught up with matches already scraped; stopping.")
                    break
                if fetched >= max_matches:
                    break
                _pause()
                if not _with_retries(lambda: _next_listing_page(listing), "next listing page"):
                    if not since:
                        # Walked the whole listing: later runs can stop at the first known page
                        state["backfill_complete"] = True
                        _write_json(STATE_FILE, state)
                    print("End of the listing.")
                    break
        finally:
            browser.close()

    print(f"Done: {fetched} matches fetched, {new_games} games added "
          f"({len(done)} matches in total). Skipped so far: {skipped or 'none'}")
    _report_unmapped(unmapped)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--max-matches", type=int, default=500, help="match pages to load this run (default 500)")
    ap.add_argument("--since", help="only matches played on or after YYYY-MM-DD")
    ap.add_argument("--reparse", action="store_true", help="rebuild the jsonl from scratch/ttl_raw only")
    ap.add_argument("--channel", help="browser channel to use, e.g. 'chrome' (default: Playwright's Chromium)")
    args = ap.parse_args(argv)
    if args.since:
        dt.date.fromisoformat(args.since)
    if args.reparse:
        reparse()
    else:
        scrape(args.max_matches, args.since, args.channel)


if __name__ == "__main__":
    main()
