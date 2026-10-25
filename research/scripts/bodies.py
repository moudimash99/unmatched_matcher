import json, sys, time, urllib.request, urllib.parse
S = sys.argv[1]
d = json.load(open(S + "/reddit-candidates.json"))
ids = {r["id"] for r in d["general"]} | {r["id"] for v in d["fighters"].values() for r in v}
ids |= set(sys.argv[2:])
import os
prev = json.load(open(S + "/reddit-bodies.json")) if os.path.exists(S + "/reddit-bodies.json") else {}
ids = sorted(i for i in ids if i not in prev); out = dict(prev)
for i in range(0, len(ids), 50):
    q = urllib.parse.urlencode({"ids": ",".join(ids[i:i+50]), "fields": "id,title,author,created_utc,selftext,num_comments,score,url"})
    req = urllib.request.Request("https://arctic-shift.photon-reddit.com/api/posts/ids?" + q, headers={"User-Agent": "unmatched-guide-index/0.1 (personal research)"})
    for a in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as r: rows = json.load(r)["data"]; break
        except Exception as e: print("ERR", e, file=sys.stderr); time.sleep(5*(a+1)); rows = []
    for p in rows: out[p["id"]] = p
    time.sleep(2)
json.dump(out, open(S + "/reddit-bodies.json", "w"))
print(len(out), "of", len(ids))
