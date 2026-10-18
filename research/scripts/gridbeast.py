import csv, json, re, sys, html, time, urllib.request, os
OLD, NEW = sys.argv[1], sys.argv[2]
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
idmap = json.load(open(NEW + "/idmap.json"))
refs = [r for r in csv.DictReader(open(OLD + "/unmatched-strategy-references.csv")) if r['source'] == 'Gridbeast']
def clean(seg):
    seg = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', seg, flags=re.S)
    seg = re.sub(r'<h([1-6])[^>]*>(.*?)</h\1>', lambda m: f"\n\n## {re.sub('<[^>]+>','',m.group(2)).strip()}\n", seg, flags=re.S)
    seg = re.sub(r'<li[^>]*>', '\n- ', seg); seg = re.sub(r'</p>|<br\s*/?>', '\n', seg)
    t = html.unescape(re.sub(r'<[^>]+>', '', seg))
    t = re.sub(r'[ \t]+', ' ', t); t = re.sub(r'\n\s*\n\s*\n+', '\n\n', t)
    return t.strip()
for r in refs:
    fid = idmap[r['fighter']]
    os.makedirs(f"{NEW}/corpus/{fid}", exist_ok=True)
    t = urllib.request.urlopen(urllib.request.Request(r['url'], headers={"User-Agent": UA}), timeout=30).read().decode('utf-8', 'ignore')
    start = t.find('Overview'); start = t.rfind('<h', 0, start)
    end = t.find('Next:', start)
    end = t.rfind('<h', 0, end) if end > 0 else len(t)
    txt = clean(t[start:end])
    open(f"{NEW}/corpus/{fid}/gridbeast.txt", "w").write(f"SOURCE: {r['url']}\n\n{txt}\n")
    print(fid, len(txt.split()), "words")
    time.sleep(0.4)
