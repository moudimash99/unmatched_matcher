"""Compile every source text gathered for the strategy write-ups into one Markdown file.

Usage: python3 -I build_sources.py OLD NEW SITE_REPO OUT
"""
import html, json, os, re, sys
from datetime import datetime, timezone

OLD, NEW, D, OUT = sys.argv[1:5]
site = json.load(open(D + "/input/fighters.json"))["fighters"]
refs = json.load(open(OLD + "/refs.json"))
idmap = json.load(open(NEW + "/idmap.json"))
bodies = json.load(open(OLD + "/reddit-bodies.json"))
comments = json.load(open(NEW + "/reddit-comments.json"))
WRITTEN = {"written guide", "written analysis", "official article", "review (hero by hero)", "infographic"}
names = {f["id"]: f["name"] for f in site}


def ukey(u):
    u = re.sub(r"^https?://(www\.)?", "", u.strip()).split("#")[0].split("?")[0]
    return u.rstrip("/").lower()


def demote(text):
    return re.sub(r"(?m)^#{1,6}\s+", "#### ", text)


def tidy(text):
    text = html.unescape(text).replace("​", "").replace("&#x200B;", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def strip_gridbeast(t):
    m = re.search(r"\n(?:## )?[^\n]*\n+\s*Using our affiliate links", t)
    if m: t = t[:m.start()]
    return t


# Which fighters each URL is filed under, and its reference row.
filed, rowfor = {}, {}
for r in refs:
    k = ukey(r["url"])
    fid = "GENERAL" if r["fighter"] == "GENERAL" else idmap.get(r["fighter"])
    if fid is None: sys.exit(f"unmapped fighter {r['fighter']!r}")
    filed.setdefault(k, [])
    if fid not in filed[k]: filed[k].append(fid)
    rowfor.setdefault(k, r)

# Source registry: key -> dict(kind, title, url, text, fighters)
sources = {}
for f in site:
    p = f"{NEW}/corpus/{f['id']}/gridbeast.txt"
    if not os.path.exists(p): continue
    raw = open(p).read()
    url = re.match(r"SOURCE: (\S+)", raw).group(1)
    r = rowfor.get(ukey(url), {})
    sources[ukey(url)] = dict(kind="Gridbeast", title=r.get("title", f"Unmatched – {f['name']}"), url=url,
                              meta="written guide", text=tidy(strip_gridbeast(raw.split("\n", 1)[1])))

OTHER = {"rg-design-diary-lee-vs-ali": "Restoration Games (official)",
         "rg-gameplay-of-unmatched-stars-and-stripes": "Restoration Games (official)",
         "rg-leader-to-wild-card-turtles-of-unmatched-adventures": "Restoration Games (official)",
         "rg-villain-or-hero-shredder-krang-unmatched-tmnt": "Restoration Games (official)",
         "antler-bol1": "Antlerflax Books", "antler-lrrh": "Antlerflax Books",
         "popinsider-marvel": "The Pop Insider",
         "warband-basic": "WarBand.ru (in Russian)", "warband-vol1.clean": "WarBand.ru (in Russian)",
         "tgg-best-fighters": "The Gaming Geek", "round2gaming-howto": "Round2Gaming"}
for fn, src in OTHER.items():
    raw = open(f"{NEW}/corpus/_other/{fn}.txt").read()
    url = re.match(r"SOURCE: (\S+)", raw).group(1)
    text = raw.split("\n", 1)[1]
    if fn == "popinsider-marvel": text = text.split("\n## Latest")[0]
    if fn == "round2gaming-howto": text = text.split("\n- Marvel Crisis Protocol")[0]
    r = rowfor.get(ukey(url), {})
    sources[ukey(url)] = dict(kind=src, title=r.get("title", url), url=url, meta=r.get("format", "article"),
                              text=tidy(text))


def render_comments(pid):
    cs = comments.get(pid, [])
    byid = {c["id"]: c for c in cs}
    kids = {}
    for c in cs:
        par = c.get("parent_id") or ""
        par = par[3:] if par.startswith("t1_") and par[3:] in byid else "ROOT"
        kids.setdefault(par, []).append(c)
    for v in kids.values(): v.sort(key=lambda c: -(c.get("score") or 0))
    out = []

    def walk(c, depth):
        body = tidy(c.get("body") or "")
        dead = body in ("[deleted]", "[removed]", "")
        if dead and not kids.get(c["id"]): return
        q = "> " * depth
        if out and depth > 1: out.append(("> " * (depth - 1)).rstrip())
        out.append(f"{q}**u/{c.get('author', '?')}** · {c.get('score', 0)} points")
        out.append(q.rstrip())
        for line in (["*[deleted]*"] if dead else body.split("\n")):
            out.append((q + line).rstrip())
        for k in kids.get(c["id"], []): walk(k, depth + 1)

    for c in kids.get("ROOT", []):
        if out: out.append("")
        walk(c, 1)
    return "\n".join(out), len(cs)


for k, fids in filed.items():
    m = re.search(r"reddit\.com/r/\w+/comments/([0-9a-z]+)", k)
    if not m: continue
    pid = m.group(1); b = bodies[pid]
    date = datetime.fromtimestamp(int(b["created_utc"]), timezone.utc).strftime("%Y-%m-%d")
    post = tidy(b.get("selftext") or "")
    if post in ("", "[removed]", "[deleted]"): post = "*(no post text: title only)*"
    ctext, n = render_comments(pid)
    text = f"**Post:**\n\n{post}\n\n**Comments ({n}):**\n\n{ctext or '*(no comments)*'}"
    sources[k] = dict(kind="Reddit", title=html.unescape(b["title"]), url=rowfor[k]["url"],
                      meta=f"thread by u/{b['author']}, {date}", text=text, reddit=True)


# BoardGameGeek threads, fetched through BGG's XML API (posts are flat, oldest first).
import xml.etree.ElementTree as ET
def html_text(seg):
    seg = re.sub(r'<br\s*/?>', '\n', seg)
    seg = re.sub(r'<li[^>]*>', '\n- ', seg); seg = re.sub(r'</p>|</div>|</center>', '\n', seg)
    seg = re.sub(r'<img[^>]*>', ' ', seg)
    seg = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', lambda m: m.group(2) if m.group(2).strip() else m.group(1), seg, flags=re.S)
    t = html.unescape(re.sub(r'<[^>]+>', '', seg)); t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'(?m)^ +', '', t)
    return re.sub(r'(?m)^https?://(www\.)?boardgamegeek\.com/image/\d+\S*\s*$', '', t)
BGGDIR = NEW + "/bgg"
n_bgg_posts = 0
for k, fids in filed.items():
    m = re.search(r"boardgamegeek\.com/thread/(\d+)", k)
    if not m: continue
    root = ET.parse(f"{BGGDIR}/t{m.group(1)}.xml").getroot()
    arts = root.findall("./articles/article")
    if not arts: continue
    n_bgg_posts += len(arts)
    first = arts[0]
    date = (first.get("postdate") or "")[:10]
    post = tidy(html_text(first.findtext("body") or ""))
    out = []
    for a in arts[1:]:
        if out: out.append("")
        out.append(f"> **{a.get('username')}** · {(a.get('postdate') or '')[:10]}")
        out.append(">")
        for line in tidy(html_text(a.findtext("body") or "")).split("\n"):
            out.append(("> " + line).rstrip())
    text = f"**Post:**\n\n{post}\n\n**Replies ({len(arts) - 1}):**\n\n{chr(10).join(out) or '*(no replies)*'}"
    sources[k] = dict(kind="BoardGameGeek", title=html.unescape(root.findtext("subject") or rowfor[k]["title"]),
                      url=rowfor[k]["url"], meta=f"thread by {first.get('username')}, {date}", text=text, bgg=True)

for k, s in sources.items(): s["fighters"] = filed.get(k, [])

# Shared = filed under 2+ fighters or under GENERAL.
shared = [k for k, s in sources.items() if len(s["fighters"]) != 1 or s["fighters"] == ["GENERAL"]]
order = {f["id"]: i for i, f in enumerate(site)}
shared.sort(key=lambda k: (sources[k]["kind"] in ("Reddit", "BoardGameGeek"),
                           min(order.get(x, -1) for x in sources[k]["fighters"]) if sources[k]["fighters"] else -1))
sid = {k: f"S{i + 1}" for i, k in enumerate(shared)}


def block(k, heading):
    s = sources[k]
    body = s["text"] if (s.get("reddit") or s.get("bgg")) else demote(s["text"])
    return f"{heading}\n\n**Source:** {s['url']} · {s['meta']}\n\n{body}\n"


def label(k):
    s = sources[k]
    return f"{s['kind']}: {s['title']}"


n_words = 0
own = {f["id"]: [] for f in site}
for k, s in sources.items():
    if k not in sid: own[s["fighters"][0]].append(k)

parts = []
for k in shared:
    s = sources[k]
    covers = ", ".join("general strategy" if x == "GENERAL" else names[x] for x in s["fighters"])
    parts.append(block(k, f"### {sid[k]} · {label(k)}") .replace("**Source:**", f"**Covers:** {covers}\n\n**Source:**", 1))

fighter_parts = []
empty = []
for f in site:
    ks = sorted(own[f["id"]], key=lambda k: (sources[k]["kind"] in ("Reddit", "BoardGameGeek"), sources[k]["title"]))
    sh = [k for k in shared if f["id"] in sources[k]["fighters"]]
    L = [f"## {f['name']}", "", f"*Set: {', '.join(f['set'])} · site id: `{f['id']}`*", ""]
    if sh:
        L += ["Also see in the shared sources: " + "; ".join(f"{sid[k]} ({label(k)})" for k in sh) + ".", ""]
    if not ks and not sh:
        empty.append(f["name"])
        L += ["*No source text was collected for this fighter. See the reference list for videos.*", ""]
    for k in ks: L.append(block(k, f"### {label(k)}"))
    fighter_parts.append("\n".join(L))

# Written links in the reference list whose text was never downloaded.
missing = {}
for k, r in rowfor.items():
    if r["format"] in WRITTEN and k not in sources:
        missing[k] = r
assert not missing, list(missing)
miss_lines = []
for k, r in sorted(missing.items(), key=lambda kv: (kv[1]["source"], kv[1]["title"])):
    fs = ", ".join("general" if x == "GENERAL" else names[x] for x in filed[k])
    miss_lines.append(f"- [{r['title']}]({r['url']}): {r['source']} · {r['format']} · {fs}")

n_grid = sum(1 for s in sources.values() if s["kind"] == "Gridbeast")
n_red = sum(1 for s in sources.values() if s.get("reddit"))
n_com = sum(len(comments.get(re.search(r"comments/([0-9a-z]+)", k).group(1), [])) for k, s in sources.items() if s.get("reddit"))
n_b = sum(1 for s in sources.values() if s.get("bgg"))
n_oth = len(sources) - n_grid - n_red - n_b

head = f"""# Unmatched fighter strategy: source texts

All the source text I gathered and wrote the strategy files from, in one place. It holds {n_grid} Gridbeast fighter guides, {n_oth} other articles, {n_red} Reddit threads with all {n_com} of their saved comments, and {n_b} BoardGameGeek threads ({n_bgg_posts} posts, including the 11-part "An Unmatched Roster" series).

**How it's organized.** Fighters appear in the site's order (`fighters.json`). A source about one fighter sits under that fighter. A source that covers several fighters (a box review, a thread about a whole set) appears once under **Shared sources** at the top with a number (S1, S2…); each fighter it covers points to it.

**What was changed.** The wording is untouched. I removed only page furniture (menus, "buy on Amazon" boxes, newsletter forms), turned the sources' own headings into small headings, and laid out Reddit replies under the comment they answer, highest points first. BoardGameGeek replies are in posting order, and image-only content from those posts is left out. The two WarBand articles are in Russian and kept that way.

**Not included.** Video transcripts: YouTube blocks this environment with a CAPTCHA page, so none could be downloaded.

These texts belong to their authors. Keep this file for your own reference rather than publishing it on the site.

"""
doc = (head + "---\n\n## Shared sources\n\n" + "\n---\n\n".join(parts) + "\n---\n\n"
       + "\n---\n\n".join(fighter_parts)
       + "\n")
open(OUT, "w").write(doc)
print(f"gridbeast {n_grid}, other {n_oth}, reddit {n_red} threads / {n_com} comments, bgg {n_b} threads / {n_bgg_posts} posts, shared {len(shared)}, "
      f"missing written {len(missing)}, no-source fighters {empty}, words {len(doc.split())}, bytes {len(doc.encode())}")
