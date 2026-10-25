# usage: put.py ID  -> validates entries/ID.med.md and entries/ID.short.md, splices both into input files
import json,re,sys
import os
R=os.path.abspath(os.path.join(os.path.dirname(__file__),'../..'))+'/'
E=R+'research/private/entries/'
i=sys.argv[1]
fighters=json.load(open(R+'input/fighters.json'))['fighters']
heroes=json.load(open(R+'input/heroes.json'))
me=[f for f in fighters if f['id']==i][0]
others=set()
for f in fighters:
    if f['id']==i: continue
    n=f['name']; others.add(n)
    for part in re.split(r'[ &]+| and | of | the ',n):
        if len(part)>3 and part not in ('Doctor','Little','Ancient','William','Muhammad','Black','Nikola','Annie','Robert','Golden','Wayward','Sisters','Eilhart','Bréacc','Glas','Riding','Hood','Marvel','Knight','Rider','Soldier','Panther','Widow','Girl','Cloak','Dagger','King','Wolf','Moon','Ghost','Winter','Squirrel','Spider','Sherlock','Holmes','Christmas','Strange','Henry','John','George','Jill','Trent','Rosie','Riveter','Wyatt','Earp','Tomoe','Gozen','Oda','Nobunaga','Sattler','Rivia','Sun','Bruce','Luke','Cage','Muldoon','Invisible','Jekyll','Hyde','Bloody','Mary'): others.add(part)
deck=heroes.get(i,{}).get('deck',[])
titles={re.sub(r"[^\w\s'\-\.,!?:\"&’]",'',c['title']).strip().lower() for c in deck}
ok=True
for kind in ('med','short'):
    t=open(E+f'{i}.{kind}.md').read()
    assert t.startswith(f'<!-- id: {i} -->\n'), 'id line'
    assert t.rstrip().endswith('---'), 'separator'
    body,_,refs=t.partition('### References')
    cited=set(int(x) for x in re.findall(r'\[(\d+)\]',body))
    defined=set(int(x) for x in re.findall(r'^(\d+)\. ',refs,re.M))
    if cited-defined: print(kind,'UNDEFINED refs',cited-defined); ok=False
    if defined-cited: print(kind,'unused refs',defined-cited)
    for o in sorted(others):
        if re.search(r'\b%s\b'%re.escape(o),body): print(kind,'NAMES OTHER FIGHTER?',o)
    for b in re.findall(r'\*\*([^*]+)\*\*',body):
        bl=b.rstrip(':').lower()
        if bl in ('in short','goal','how to do it','watch out for','how','watch out') : continue
        bl=re.sub(r' \(\d copies\)$','',bl)
        if deck and bl not in titles: print(kind,'bold not a card:',b)
    words=len(re.sub(r'\[\d+\]','',body.split('\n',1)[1]).split())
    print(kind,'words',words)
if ok and '--dry' not in sys.argv:
    for kind,path in (('med','input/fighter_strategies.md'),('short','input/fighter_strategies_short.md')):
        new=open(E+f'{i}.{kind}.md').read()
        if not new.endswith('\n'): new+='\n'
        t=open(R+path).read()
        m=re.search(r'<!-- id: %s -->.*?\n---\n'%re.escape(i),t,re.S); assert m
        open(R+path,'w').write(t[:m.start()]+new+t[m.end():])
    print('spliced',i)
