import json, sys, time, urllib.request, urllib.parse, datetime
BASE = "https://arctic-shift.photon-reddit.com/api/posts/search"
def fetch(params):
    params = dict(params, subreddit="Unmatched", limit="100", fields="id,title,author,created_utc,score,num_comments,link_flair_text,url")
    out, before = [], None
    while True:
        p = dict(params)
        if before: p["before"] = before
        url = BASE + "?" + urllib.parse.urlencode(p)
        for attempt in range(4):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "unmatched-guide-index/0.1 (personal research)"})
                with urllib.request.urlopen(req, timeout=90) as r: d = json.load(r)
                break
            except Exception as e:
                time.sleep(5 * (attempt + 1)); d = {"data": None, "error": str(e)}
        rows = d.get("data") or []
        if d.get("error"): print("ERR", d["error"], file=sys.stderr)
        out += rows
        if len(rows) < 100: break
        before = min(r["created_utc"] for r in rows)
        time.sleep(2)
    return out
if __name__ == "__main__":
    params = dict(a.split("=", 1) for a in sys.argv[2:])
    rows = fetch(params)
    json.dump(rows, open(sys.argv[1], "w"))
    for p in sorted(rows, key=lambda p: p["created_utc"]):
        print(datetime.date.fromtimestamp(p["created_utc"]), p["id"], p["author"], p["score"], "|", p["title"])
