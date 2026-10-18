import json, re, sys, time, csv, urllib.request, urllib.parse
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
rows = list(csv.DictReader(open(sys.argv[1])))
ids = {}
for r in rows:
    for part in r["video_guides"].split(" ; "):
        if not part: continue
        m = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", part)
        if m: ids[m.group(1)] = part
out = {}
for vid in sorted(ids):
    u = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(f"https://www.youtube.com/watch?v={vid}")
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=20) as r:
            d = json.load(r); out[vid] = {"ok": True, "title": d["title"], "channel": d["author_name"]}
    except urllib.error.HTTPError as e:
        out[vid] = {"ok": False, "status": e.code}
    except Exception as e:
        out[vid] = {"ok": False, "status": str(e)}
    time.sleep(0.6)
json.dump(out, open(sys.argv[2], "w"), indent=1)
bad = {k: v for k, v in out.items() if not v["ok"]}
print(len(out), "checked,", len(bad), "unavailable"); print(json.dumps(bad, indent=1))
