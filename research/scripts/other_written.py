import re, sys, html, json, urllib.request, os
NEW = sys.argv[1]
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
def get(u): return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=40).read().decode('utf-8', 'ignore')
def clean(seg):
    seg = re.sub(r'<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>', ' ', seg, flags=re.S)
    seg = re.sub(r'<h([1-6])[^>]*>(.*?)</h\1>', lambda m: f"\n\n## {re.sub('<[^>]+>','',m.group(2)).strip()}\n", seg, flags=re.S)
    seg = re.sub(r'<li[^>]*>', '\n- ', seg); seg = re.sub(r'</p>|<br\s*/?>', '\n', seg)
    t = html.unescape(re.sub(r'<[^>]+>', '', seg)); t = re.sub(r'[ \t]+', ' ', t)
    return re.sub(r'\n\s*\n\s*\n+', '\n\n', t).strip()
docs = {}
for slug in ['design-diary-lee-vs-ali', 'gameplay-of-unmatched-stars-and-stripes', 'leader-to-wild-card-turtles-of-unmatched-adventures', 'villain-or-hero-shredder-krang-unmatched-tmnt']:
    d = json.loads(get(f"https://restorationgames.com/wp-json/wp/v2/posts?slug={slug}&_fields=content,link"))[0]
    docs['rg-' + slug] = (d['link'], clean(d['content']['rendered']))
for key, slug in [('antler-lrrh', 'unmatched-hero-analysis-little-red-riding-hood'), ('antler-bol1', 'board-game-review-9-unmatched-battle-of-legends-volume-1')]:
    d = json.loads(get(f"https://public-api.wordpress.com/rest/v1.1/sites/antlerflaxbooks.wordpress.com/posts/slug:{slug}?fields=content,URL"))
    docs[key] = (d['URL'], clean(d['content']))
for key, u, a, b in [('warband-vol1', 'https://warband.ru/85-kak-pobezhdat-v-unmatched-vol-1.html', None, None),
                     ('warband-basic', 'https://warband.ru/52-unmatched-rukovodstvo-po-bazovoj-strategii.html', None, None),
                     ('popinsider-marvel', 'https://thepopinsider.com/unmatched-marvel-who-to-play-how-to-win-and-whats-coming-next/', None, None)]:
    t = get(u)
    m = re.search(r'<article.*?</article>', t, re.S) or re.search(r'<div[^>]+(?:full-story|entry-content|post-content|article-content)[^>]*>.*?(?=<footer|<div[^>]+(?:comments|related))', t, re.S)
    docs[key] = (u, clean(m.group(0) if m else t))
os.makedirs(NEW + "/corpus/_other", exist_ok=True)
for k, (u, txt) in docs.items():
    open(f"{NEW}/corpus/_other/{k}.txt", "w").write(f"SOURCE: {u}\n\n{txt}\n")
    print(k, len(txt.split()), "words")
