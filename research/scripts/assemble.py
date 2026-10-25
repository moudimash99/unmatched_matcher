import csv, json, os, re, sys
OLD, NEW, D = sys.argv[1:4]
site = json.load(open(D + "/input/fighters.json"))['fighters']
idmap = json.load(open(NEW + "/idmap.json")); rev = {v: k for k, v in idmap.items()}
refs = list(csv.DictReader(open(OLD + "/unmatched-strategy-references.csv")))
FMT = {'written guide': 'written guide', 'written analysis': 'written analysis', 'official article': 'official article',
       'review (hero by hero)': 'written review', 'infographic': 'infographic', 'video + infographic': 'video + infographic',
       'discussion thread': 'thread', 'video': 'video'}
ORDER = list(FMT)
EXCLUDE = {'https://www.reddit.com/r/Unmatched/comments/xvfvl9/', 'https://www.reddit.com/r/Unmatched/comments/1oodwzq/', 'https://www.reddit.com/r/Unmatched/comments/1ic00hv/'}  # empty placeholder thread
def reading(fid):
    rs = [r for r in refs if r['fighter'] == rev.get(fid)]
    keep = []
    for r in rs:
        if r['format'] == 'discussion thread':
            m = re.search(r'(\d+) comments', r['note'])
            if m and int(m.group(1)) < 3: continue
        keep.append(r)
    keep.sort(key=lambda r: ORDER.index(r['format']))
    out, seen = [], set()
    for r in keep:
        if r['url'] in seen or r['url'] in EXCLUDE: continue
        seen.add(r['url'])
        src = r['source'].replace(' (YouTube)', '')
        title = r['title'].replace('[', '(').replace(']', ')')
        flag = ' (not checked: BoardGameGeek blocks automated access)' if r['checked'] != 'yes' else ''
        out.append(f"- [{title}]({r['url']}): {src} · {FMT[r['format']]}{flag}")
    return out
def build(entries_dir, header, out_path, with_reading):
    parts = [open(header).read().rstrip() + "\n"]
    done = 0
    for f in site:
        p = f"{entries_dir}/{f['id']}.md"
        if not os.path.exists(p): continue
        done += 1
        body = open(p).read().rstrip()
        block = f"<!-- id: {f['id']} -->\n{body}\n"
        if with_reading: block += "\n### Further reading\n" + "\n".join(reading(f['id'])) + "\n"
        parts.append(block)
    open(out_path, "w").write("\n---\n\n".join(parts))
    return done
a = build(NEW + "/entries", NEW + "/header.md", D + "/input/fighter_strategies.md", True)
b = build(NEW + "/entries_short", NEW + "/header_short.md", D + "/input/fighter_strategies_short.md", False)
print(a, "medium and", b, "short entries of", len(site))
