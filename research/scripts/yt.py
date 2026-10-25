import re, sys, json, urllib.request, urllib.parse
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
def get(u):
    req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9", "Cookie": "CONSENT=YES+1"})
    return urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "ignore")
def initial(t):
    m = re.search(r'var ytInitialData = (\{.*?\});</script>', t, re.S)
    return json.loads(m.group(1)) if m else {}
def walk(o, key):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key: yield v
            yield from walk(v, key)
    elif isinstance(o, list):
        for v in o: yield from walk(v, key)
def text(r):
    if not r: return ""
    return r.get("simpleText") or "".join(x.get("text", "") for x in r.get("runs", []))
if __name__ == "__main__":
    mode, arg = sys.argv[1], sys.argv[2]
    if mode == "video":
        t = get("https://www.youtube.com/watch?v=" + arg)
        ch = re.search(r'"channelId":"([^"]+)"', t); name = re.search(r'"ownerChannelName":"([^"]+)"', t)
        title = re.search(r'<title>(.*?)</title>', t)
        print(arg, ch and ch.group(1), name and name.group(1), title and title.group(1))
    elif mode == "search":
        d = initial(get("https://www.youtube.com/results?search_query=" + urllib.parse.quote(arg)))
        for v in walk(d, "videoRenderer"):
            print(v["videoId"], "|", text(v.get("ownerText")), "|", text(v.get("title")), "|", text(v.get("publishedTimeText")))
    elif mode == "channel":
        d = initial(get(f"https://www.youtube.com/channel/{arg}/videos"))
        for v in walk(d, "videoRenderer"):
            print(v["videoId"], "|", text(v.get("title")), "|", text(v.get("publishedTimeText")))
        for v in walk(d, "lockupViewModel"):
            pass
if __name__ == "__main__" and sys.argv[1] == "chid":
    d = initial(get("https://www.youtube.com/results?search_query=" + urllib.parse.quote(sys.argv[2])))
    for v in walk(d, "videoRenderer"):
        for r in v.get("ownerText", {}).get("runs", []):
            print(text(v.get("title")), "|", r.get("navigationEndpoint", {}).get("browseEndpoint", {}).get("browseId")); break
        break
if __name__ == "__main__" and sys.argv[1] == "playlists":
    d = initial(get(f"https://www.youtube.com/channel/{sys.argv[2]}/playlists"))
    for v in walk(d, "lockupViewModel"):
        t = list(walk(v, "title")); cid = v.get("contentId")
        print(cid, "|", json.dumps(t[0])[:120] if t else "")
    for v in walk(d, "gridPlaylistRenderer"):
        print(v.get("playlistId"), "|", text(v.get("title")))
if __name__ == "__main__" and sys.argv[1] == "playlist":
    d = initial(get(f"https://www.youtube.com/playlist?list={sys.argv[2]}"))
    for v in walk(d, "playlistVideoRenderer"):
        print(v["videoId"], "|", text(v.get("title")))
