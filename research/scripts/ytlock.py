import re, sys, json
t = open(sys.argv[1], encoding="utf-8", errors="ignore").read()
m = re.search(r'var ytInitialData = (\{.*?\});</script>', t, re.S); d = json.loads(m.group(1))
def walk(o):
    if isinstance(o, dict):
        if "lockupViewModel" in o: yield ("l", o["lockupViewModel"])
        if "videoRenderer" in o: yield ("v", o["videoRenderer"])
        if "richItemRenderer" in o: pass
        for v in o.values(): yield from walk(v)
    elif isinstance(o, list):
        for v in o: yield from walk(v)
seen = set()
for kind, v in walk(d):
    if kind == "l":
        cid = v.get("contentId"); tm = re.search(r'"title": \{"content": "([^"]+)"', json.dumps(v.get("metadata", {})))
        title = tm.group(1) if tm else "?"
    else:
        cid = v.get("videoId"); r = v.get("title", {}); title = r.get("simpleText") or "".join(x.get("text","") for x in r.get("runs", []))
    if cid and cid not in seen: seen.add(cid); print(cid, "|", title)
