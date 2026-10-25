import csv, json, os, sys
OLD, NEW, D = sys.argv[1:4]
site = json.load(open(D + "/input/fighters.json"))
heroes = json.load(open(D + "/input/heroes.json"))
idmap = json.load(open(NEW + "/idmap.json")); rev = {v: k for k, v in idmap.items()}
refs = list(csv.DictReader(open(OLD + "/unmatched-strategy-references.csv")))
os.makedirs(NEW + "/briefs", exist_ok=True)
for f in site['fighters']:
    fid = f['id']; h = heroes.get(fid, {})
    L = [f"# {f['name']} ({fid}) — set: {', '.join(f['set'])}",
         f"site tags: range={f['range']} major={f['major']} minor={f['minor']} mechanism={f['foundational_mechanism']!r}",
         f"stats: hp={h.get('hp')} move={h.get('move')} attack={h.get('attack')}",
         f"sidekicks: {json.dumps(h.get('sidekicks'), ensure_ascii=False)}",
         f"special ability: {h.get('special_ability')}", "", "## DECK (title | type value/boost | copies | character | effect)"]
    total = 0
    for c in h.get('deck', []):
        total += c.get('copies', 0)
        L.append(f"- {c['title']} | {c['type']} {c.get('value','-')}/{c.get('boost','-')} | x{c.get('copies')} | {c.get('character')} | {c.get('effect') or ''}")
    L.append(f"(deck size {total})")
    for name in ('gridbeast.txt', 'reddit.txt'):
        p = f"{NEW}/corpus/{fid}/{name}"
        if os.path.exists(p): L += ["", f"## SOURCE FILE {name}", open(p).read()]
    L += ["", "## REFERENCES (for Further reading)"]
    for r in refs:
        if r['fighter'] == rev.get(fid): L.append(f"- {r['format']} | {r['focus']} | {r['source']} | {r['title']} | {r['url']} | {r['note']}")
    open(f"{NEW}/briefs/{fid}.md", "w").write("\n".join(L) + "\n")
print(len(site['fighters']), "briefs")
