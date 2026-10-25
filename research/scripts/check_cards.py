import json, re, sys, unicodedata
D = sys.argv[1]
heroes = json.load(open(D + "/input/heroes.json"))
fighters = json.load(open(D + "/input/fighters.json"))
LABELS = {"in short:", "goal:", "how to do it:", "watch out for:", "how:", "watch out:"}
def norm(s):
    s = unicodedata.normalize("NFKC", s).replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip().lower()
def entries(path):
    t = open(path).read()
    out = {}
    for m in re.finditer(r"<!-- id: (\S+) -->\n(.*?)(?=\n---\n|\Z)", t, re.S):
        out[m.group(1)] = m.group(2)
    return out
bad = 0
for path in sys.argv[2:]:
    es = entries(path)
    for fid, body in es.items():
        h = heroes.get(fid) if isinstance(heroes, dict) else None
        titles = [c["title"] for c in h["deck"]] if h else []
        nt = {norm(x): x for x in titles}
        # bold names in Key cards
        kc = body.split("### Key cards", 1)[1].split("###", 1)[0] if "### Key cards" in body else ""
        for b in re.findall(r"\*\*(.+?)\*\*", kc):
            names = re.split(r"\*\* and \*\*", b)
            if norm(b) in LABELS: continue
            if norm(b) not in nt:
                bad += 1; print(f"{path.split('/')[-1]} {fid}: key card not in deck: {b!r}")
        # case drift: deck title present case-insensitively but not exactly
        plain = re.sub(r"\*\*", "", body)
        for t in titles:
            if len(t) < 5: continue
            for m in re.finditer(re.escape(norm(t)), norm(plain)):
                pass
            if norm(t) in norm(plain) and t not in plain:
                print(f"  note {path.split('/')[-1]} {fid}: case/spelling differs from data: {t!r}")
print("bad key-card names:", bad)
