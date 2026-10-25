import csv, json, re, sys, time, os, urllib.request, urllib.parse
OLD, NEW = sys.argv[1], sys.argv[2]
UA = {"User-Agent": "unmatched-guide-index/0.1 (personal research)"}
idmap = json.load(open(NEW + "/idmap.json"))
bodies = json.load(open(OLD + "/reddit-bodies.json"))
refs = [r for r in csv.DictReader(open(OLD + "/unmatched-strategy-references.csv")) if r['url'].startswith('https://www.reddit.com/')]
cache_f = NEW + "/reddit-comments.json"
cache = json.load(open(cache_f)) if os.path.exists(cache_f) else {}
def get(url):
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r: return json.load(r)
        except Exception as e:
            print("retry", url[-40:], e, file=sys.stderr); time.sleep(6 * (a + 1))
    return {"data": []}
ids = sorted({re.search(r'/comments/([0-9a-z]+)/', r['url']).group(1) for r in refs})
for pid in ids:
    if pid in cache: continue
    d = get("https://arctic-shift.photon-reddit.com/api/comments/search?" + urllib.parse.urlencode({"link_id": pid, "limit": 100, "fields": "id,author,body,score,parent_id"}))
    cache[pid] = d.get("data") or []
    time.sleep(1.5)
json.dump(cache, open(cache_f, "w"))
# write per-fighter files
per = {}
for r in refs:
    pid = re.search(r'/comments/([0-9a-z]+)/', r['url']).group(1)
    fid = idmap.get(r['fighter'], 'GENERAL') if r['fighter'] != 'GENERAL' else 'GENERAL'
    per.setdefault(fid, []).append((pid, r))
for fid, items in per.items():
    os.makedirs(f"{NEW}/corpus/{fid}", exist_ok=True)
    out = []
    for pid, r in items:
        p = bodies.get(pid, {})
        out.append(f"=== THREAD {r['url']} | {r['title']} | {r['date']} | focus: {r['focus']}\n{(p.get('selftext') or '').strip()[:1500]}\n")
        cs = [c for c in cache.get(pid, []) if c.get('body') and c['body'] not in ('[deleted]', '[removed]')]
        cs.sort(key=lambda c: -(c.get('score') or 0))
        for c in cs[:30]:
            out.append(f"  [{c.get('score')}] {c['author']}: {re.sub(r'\s+', ' ', c['body'])[:1200]}")
        out.append("")
    open(f"{NEW}/corpus/{fid}/reddit.txt", "w").write("\n".join(out))
print("threads", len(ids), "fighters", len(per), "comments", sum(len(v) for v in cache.values()))
