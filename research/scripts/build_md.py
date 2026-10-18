import json, sys
S = sys.argv[1]
rows = json.load(open(S + "/refs.json"))
written = ['written guide', 'written analysis', 'official article', 'review (hero by hero)', 'infographic', 'video + infographic']
def line(r):
    bits = [r['source'], r['format'], r['focus']]
    if r['date']: bits.append(r['date'])
    if r['note']: bits.append(r['note'])
    flag = ' ⚠️ not opened' if r['checked'] != 'yes' else ''
    return f"- [{r['title']}]({r['url']}) — {' · '.join(bits)}{flag}"
out = []
out.append("# Unmatched strategy references\n")
out.append("Links to guides on how each fighter wins and loses. Also in `unmatched-strategy-references.csv` (one row per fighter and link).\n")
out.append("**Columns / tags:** format = written guide, written analysis, official article, infographic, discussion thread (Reddit or BoardGameGeek question with answers in the comments), or video. Focus = *playing as* (how the fighter wins), *playing against* (how it loses), *both*, or *general*.\n")
out.append("**Checked:** every link opened or confirmed through the site's own data, except BoardGameGeek, which blocks automated access; those are marked ⚠️ not opened.\n")
out.append("**Left out:** reviews, counter-pick and \"worst matchup\" threads, rules questions, co-op (Adventures villain) threads, painting posts, memes and match reports.\n")
gen = [r for r in rows if r['fighter'] == 'GENERAL']
out.append("## General strategy\n")
out += [line(r) for r in gen]
cur_set = None
for f in dict.fromkeys(r['fighter'] for r in rows if r['fighter'] != 'GENERAL'):
    rs = [r for r in rows if r['fighter'] == f]
    if rs[0]['set'] != cur_set:
        cur_set = rs[0]['set']; out.append(f"\n## {cur_set}")
    out.append(f"\n### {f}")
    w = [r for r in rs if r['format'] in written]; t = [r for r in rs if r['format'] == 'discussion thread']; v = [r for r in rs if r['format'] == 'video']
    for label, group in (("Written", w), ("Threads", t), ("Videos", v)):
        if group: out.append(f"\n**{label}**\n"); out += [line(r) for r in group]
open(S + "/unmatched-strategy-references.md", "w").write("\n".join(out) + "\n")
print(len(out), "lines")
