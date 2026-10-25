import json,re,sys
import os
R=os.path.abspath(os.path.join(os.path.dirname(__file__),'../..'))+'/'
S=R+'research/private/packs/'
src=open(R+'research/private/unmatched-fighter-sources.md').read()
fighters=json.load(open(R+'input/fighters.json'))['fighters']
heroes=json.load(open(R+'input/heroes.json'))
med=open(R+'input/fighter_strategies.md').read()
extra={'cloak_and_dagger':['S21'],'squirrel_girl':['S21'],'ms_marvel':['S21'],
'black_panther':['S22','S23'],'winter_soldier':['S22','S23'],'black_widow':['S22','S23'],
'doctor_strange':['S23'],'she_hulk':['S23'],'spider_man':['S23'],
'beowulf':['S24'],'little_red':['S24'],'sun_wukong':['S25'],'achilles':['S25'],'bloody_mary':['S25'],
'houdini':['S26'],'the_genie':['S26']}
shared={}
for m in re.finditer(r'^### (S\d+) · .*?(?=^### S\d+ · |^## (?!#))',src,re.S|re.M):
    shared[m.group(1)]=m.group(0)
secs={}
for m in re.finditer(r'^## (?!#)([^\n]*)\n\n\*Set: .*?site id: `(\w+)`\*.*?(?=^## (?!#)|\Z)',src,re.S|re.M):
    secs[m.group(2)]=m.group(0)
os.makedirs(S,exist_ok=True)
for f in fighters:
    i=f['id']; out=[]
    h=heroes.get(i)
    out.append('# PACK: %s (%s)\n'%(f['name'],i))
    if h:
        hh={k:v for k,v in h.items() if k!='deck'}
        out.append('## DECK DATA\n'+json.dumps(hh,ensure_ascii=False))
        for c in h.get('deck',[]):
            out.append('- %s | %s | val %s | boost %s | x%s | %s | %s'%(c.get('title'),c.get('type'),c.get('value'),c.get('boost'),c.get('copies'),c.get('character'),c.get('effect')))
    else: out.append('## NO DECK DATA')
    m=re.search(r'<!-- id: %s -->.*?\n---\n'%i,med,re.S)
    if m:
        fr=re.search(r'### Further reading\n(.*?)\n---',m.group(0),re.S)
        out.append('\n## OLD FURTHER READING\n'+(fr.group(1) if fr else '(none)'))
    sec=secs.get(i,'')
    out.append('\n## OWN SOURCES\n'+(sec or '(none)'))
    ids=re.findall(r'\b(S\d+) \(',sec.split('\n### ')[0]) + extra.get(i,[])
    for s in dict.fromkeys(ids):
        out.append('\n## SHARED '+shared.get(s,s+' MISSING'))
    open(S+i+'.md','w').write('\n'.join(out))
    print(i, len(' '.join(out).split()), ' '.join(dict.fromkeys(ids)), 'NOSEC' if not sec else '')
