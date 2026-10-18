"""Build the Unmatched strategy reference list (CSV + Markdown) from the collected sources."""
import csv, json, re, sys, datetime

S = sys.argv[1]
UPLOAD = sys.argv[2]
roster = json.load(open(S + "/roster.json"))          # [{id,name,set}]
oembed = json.load(open(S + "/dl/oembed.json"))
reddit = json.load(open(S + "/reddit-bodies.json"))

SET_NAMES = {
  'Battle of Legends, Volume One': 'Battle of Legends 1', 'Bruce Lee': 'Bruce Lee',
  'Robin Hood vs. Bigfoot': 'Robin Hood vs. Bigfoot', 'Jurassic Park - Ingen vs. Raptors': 'Jurassic Park: InGen vs. Raptors',
  'Cobble & Fog': 'Cobble & Fog', 'Buffy the Vampire Slayer': 'Buffy',
  'Little Red Riding Hood vs. Beowulf': 'Little Red vs. Beowulf', 'Deadpool': 'Deadpool',
  'Unmatched: Battle of Legends, Volume Two': 'Battle of Legends 2', 'Redemption Row': 'Marvel: Redemption Row',
  "Hell's Kitchen": "Marvel: Hell's Kitchen", 'Jurassic Park - Sattler vs. T-Rex': 'Jurassic Park: Sattler vs. T. Rex',
  'Houdini vs. The Genie': 'Houdini vs. The Genie', 'Teen Spirit': 'Marvel: Teen Spirit',
  'For King and Country': 'Marvel: For King and Country', 'Brains and Brawn': 'Marvel: Brains and Brawn',
  'Unmatched Adventures: Tales to Amaze': 'Tales to Amaze', "Sun's Origin": "Sun's Origin",
  'Slings and Arrows': 'Slings and Arrows', 'Steel and Silver': 'The Witcher: Steel & Silver',
  'Realms Fall': 'The Witcher: Realms Fall', 'Battle of Legends, Volume Three': 'Battle of Legends 3',
  'Lee vs Ali': 'Bruce Lee vs. Ali', 'Unmatched Adventures: Teenage Mutant Ninja Turtles': 'TMNT',
  'Unmatched Adventures: Teenage Mutant Ninja Turtles - Shredder and Krang': 'TMNT: Shredder & Krang',
  'Unmatched: Stars and Stripes': 'Stars and Stripes'}
DISPLAY = {'InGen': 'Robert Muldoon (InGen)', 'William Shakespeare': 'Shakespeare', 'Geralt of Rivia': 'Geralt',
           'Rosie The Riveter': 'Rosie the Riveter'}
fighters = [DISPLAY.get(f['name'], f['name']) for f in roster]
set_of = {DISPLAY.get(f['name'], f['name']): SET_NAMES.get(f['set'], f['set']) for f in roster}
by_set = {}
for f in fighters: by_set.setdefault(set_of[f], []).append(f)

rows = []
def add(fighter, source, title, url, fmt, focus, date='', checked='yes', note=''):
    assert fighter == 'GENERAL' or fighter in set_of, fighter
    rows.append(dict(fighter=fighter, set=set_of.get(fighter, ''), source=source, title=title, url=url,
                     format=fmt, focus=focus, date=date, checked=checked, note=note))

# ---------- General strategy ----------
G = 'GENERAL'
add(G, 'Round2Gaming', 'How to Play Unmatched: A Comprehensive Guide', 'https://round2gaming.com/2025/01/how-to-play-unmatched-a-comprehensive-guide-to-the-epic-skirmish-board-game/', 'written guide', 'general', '2025-01')
add(G, 'The Gaming Geek', 'Unmatched Tips and Strategies: Fighting Against the Best Fighters', 'https://thegaminggeek.net/unmatched-tips-and-strategies-fighting-against-the-best-fighters/', 'written guide', 'playing against', '2026-02-26', note='Collects the "Weekly Discussion: Battling X" Reddit threads listed under each fighter')
add(G, 'WarBand.ru (Russian)', 'Unmatched: basic strategy guide', 'https://warband.ru/52-unmatched-rukovodstvo-po-bazovoj-strategii.html', 'written guide', 'general', note='In Russian')
for vid, n, t in [('2LtdJEXUwqY', 1, 'Tempo and Initiative'), ('lu_F2WhrOfE', 2, 'Win Conditions and Play Patterns'),
                  ('wuin1gfiw5Q', 3, 'Advantage and Draft'), ('cKiqyf--mnw', 4, 'Mentality and Improving')]:
    add(G, 'Siki (YouTube)', f'Unmatched Advanced Fundamentals {n}: {t}', f'https://www.youtube.com/watch?v={vid}', 'video', 'general')
add(G, 'Reddit: d_Shirt', 'Advanced Fundamentals 1 (Reddit post for the video)', 'https://www.reddit.com/r/Unmatched/comments/1sduink/', 'discussion thread', 'general', '2026-04-06')
add(G, 'Reddit: d_Shirt', 'Advanced Fundamentals 2 (Reddit post for the video)', 'https://www.reddit.com/r/Unmatched/comments/1sk4ppk/', 'discussion thread', 'general', '2026-04-13')

GENERAL_REDDIT = {
 '1izj7fr': ('infographic', 'general', 'Two image guides: core strategies, and the directions a game can take'),
 '1hm0d2p': ('discussion thread', 'general', ''), '1rnnuq2': ('discussion thread', 'general', 'Winning by exhaustion'),
 '1qx8d8h': ('discussion thread', 'general', ''), '1wtmbms': ('discussion thread', 'general', ''),
 '1uztmz1': ('discussion thread', 'general', 'Playing aggro'),
 '1te4zpr': ('discussion thread', 'playing against', 'Asks for tips against each character'),
 '1tk0h6i': ('discussion thread', 'playing against', 'One-line tips against many fighters (67 comments)'),
}

# ---------- Reddit threads per fighter (curated by hand) ----------
# id: ([fighters], focus, format override or None)
R = {
 't2rkyi': (['Medusa', 'Sherlock Holmes'], 'both'), 'vky34y': (['Medusa'], 'playing as'),
 '1qvzo4n': (['Medusa'], 'playing against'), '1v0jgg7': (['Medusa'], 'playing against'),
 'wsqft5': (['Sinbad', 'Sherlock Holmes'], 'playing as'), '1r25uuq': (['Sinbad'], 'playing against'),
 '1t3hc83': (['Sinbad'], 'playing as'), '1w07mo8': (['Sinbad', 'The Genie'], 'both'),
 'xvfvl9': (['Alice'], 'playing as'),
 'nenz66': (['King Arthur'], 'playing as'), 'uzvrq6': (['King Arthur'], 'playing as'),
 '1dxmgn3': (['King Arthur'], 'playing as'), '1ktnoa2': (['King Arthur'], 'playing as'),
 'ob3suh': (['Bruce Lee'], 'playing against'), '1rn99wv': (['Bruce Lee'], 'playing as'),
 '1bdr0x1': (['Robin Hood'], 'playing as'),
 'f9f2w8': (['Bigfoot'], 'playing against'), '1r85rfa': (['Bigfoot'], 'playing against'),
 '1wrmvem': (['Bigfoot'], 'playing against'),
 '1au8cin': (['Robert Muldoon (InGen)'], 'playing as'), '1t3rga4': (['Robert Muldoon (InGen)', 'Dr. Sattler'], 'playing as'),
 '1oodwzq': (['Robert Muldoon (InGen)', 'Raptors'], 'both'),
 'mvb00p': (['Raptors'], 'playing as'), 'yypc6r': (['Raptors', 'T. Rex'], 'both'),
 'xau7ye': (['Invisible Man'], 'playing against'), '1svqxef': (['Invisible Man'], 'playing as'),
 '1ajd5cp': (['Dracula', 'Sherlock Holmes'], 'both'), '1av3glo': (['Dracula'], 'playing as'),
 '1jr0m7k': (['Dracula'], 'playing as'), '1m4yftz': (['Dracula'], 'playing as'), '1r3k26c': (['Dracula'], 'playing as'),
 '10osa00': (['Sherlock Holmes'], 'playing against'), '1ic00hv': (['Sherlock Holmes', 'Beowulf'], 'both'),
 '1mirepy': (['Sherlock Holmes', 'Sun Wukong'], 'both'), '1refj9o': (['Sherlock Holmes'], 'playing against'),
 '1g2srxm': (['Sherlock Holmes', 'Dracula', 'Invisible Man', 'Jekyll & Hyde'], 'playing as'),
 '1lt61bi': (['Buffy', 'Willow', 'Angel', 'Spike'], 'playing as'),
 '1d1y8tj': (['Beowulf'], 'playing as'), '1rha060': (['Beowulf'], 'playing as'),
 '1rr1gva': (['Sun Wukong'], 'playing against'), '1rzaalc': (['Sun Wukong', 'Yennenga'], 'both'),
 '1s3hv2c': (['Yennenga'], 'playing against'), '1tgso92': (['Yennenga'], 'playing as'),
 '1n30hpy': (['Achilles'], 'playing as'), '1puv37x': (['Achilles'], 'playing as'),
 '1rko49a': (['Achilles'], 'playing against'), '1e10p51': (['Achilles', 'Tomoe Gozen'], 'both'),
 '1uxkvf2': (['Achilles', 'Winter Soldier'], 'both'),
 '1km9dy9': (['Bloody Mary', 'Titania'], 'both'), '1s18nto': (['Bloody Mary'], 'playing as'),
 '1sp2e0n': (['Bloody Mary'], 'playing as'),
 '1t0p69f': (['Ghost Rider'], 'playing as'), '1plly3g': (['Ghost Rider'], 'playing as'),
 'uef0wg': (['Moon Knight'], 'playing against'),
 '1facpfu': (['Bullseye'], 'playing as'), '1i0drah': (['Bullseye'], 'playing as'), '1wz3e9q': (['Bullseye'], 'playing as'),
 '1b11b6o': (['Daredevil'], 'playing as'),
 '1pkyr6h': (['Elektra'], 'playing as'), '1s5e5m5': (['Elektra'], 'playing against'), '1sgv66c': (['Elektra'], 'playing against'),
 '1fjo69b': (['T. Rex'], 'playing against'),
 '18d2ok3': (['Houdini'], 'playing as'), '1c9gp10': (['Houdini', 'The Genie'], 'both'), '1sssmd3': (['Houdini'], 'playing against'),
 'zz4w4t': (['The Genie'], 'playing as'), '1ah1yk6': (['The Genie'], 'playing as'),
 '1rxdwrr': (['Squirrel Girl'], 'playing as'),
 '14uufd9': (['Cloak & Dagger'], 'playing as'), '154k23s': (['Cloak & Dagger'], 'playing as'), '1tf29n6': (['Cloak & Dagger'], 'playing as'),
 '1th0ed8': (['Ms. Marvel'], 'playing as'), '1ssooyg': (['Black Panther'], 'playing as'),
 '1ceg4f9': (['Winter Soldier'], 'playing against'),
 '14niiyy': (['Spider-Man'], 'playing as'), '1tim6y0': (['She-Hulk'], 'playing against'),
 '1t5ejf8': (['Doctor Strange'], 'playing against'), '1wxhkqw': (['Doctor Strange'], 'playing against'),
 '1pqfi0p': (['Doctor Strange'], 'playing as'),
 '1agp0k1': (['Nikola Tesla'], 'playing against'), '1taiaqs': (['Nikola Tesla'], 'playing as'),
 '1flizsf': (['Dr. Jill Trent'], 'playing as'), '1rl16ig': (['Dr. Jill Trent'], 'playing as'),
 '1tpeb5w': (['The Golden Bat'], 'playing against'),
 '1dwnu9r': (['Shakespeare', 'Hamlet'], 'playing as'),
 '1dxp4jn': (['The Wayward Sisters'], 'playing against'),
 '1fe4nyh': (['Hamlet'], 'playing as'), '1ozkzi3': (['Hamlet'], 'playing as'),
 '1is88el': (['Geralt'], 'playing as'), '1l6duj3': (['Geralt'], 'both'),
 '1l5jpgv': (['Ciri'], 'both'), '1ouwj01': (['Ciri'], 'playing as'),
 '1i25gqr': (['Ancient Leshen'], 'playing as'),
 '1jbbdha': (['Eredin'], 'playing as'), '1rryuh7': (['Eredin'], 'playing as'),
 '1n3cksy': (['Philippa'], 'playing as'),
 '1hch4gt': (['Yennefer & Triss'], 'playing as'), '1mc93cd': (['Yennefer & Triss'], 'playing as'),
 '1oylxqw': (['Yennefer & Triss'], 'playing against'),
 '1uzx2ta': (['Chupacabra'], 'playing as'), '1n9abh5': (['Blackbeard'], 'playing as'),
 '1n431fe': (['Pandora'], 'playing as'), '1oqwc2r': (['Pandora'], 'playing as'),
 '1mieh3j': (['Chupacabra', 'Blackbeard', 'Pandora', 'Loki'], 'playing as'),
 '1rpofab': (['Loki'], 'playing as'), '1ss8964': (['Loki'], 'playing as'),
 '1pigxgq': (['Muhammad Ali'], 'playing as'), '1q13k61': (['Muhammad Ali'], 'playing as'), '1r3if9o': (['Muhammad Ali'], 'playing as'),
 '1t7hmf0': (['Raphael'], 'playing as'), '1rx0oom': (['Raphael'], 'playing as'),
 '1q3wu0t': (['Donatello'], 'playing as'), '1rip96w': (['Shredder'], 'playing as'),
 '1tbidqb': (['Rosie the Riveter'], 'playing as'),
 '1ta506r': (['George Washington'], 'playing as'), '1tko47e': (['George Washington'], 'playing as'),
 '1t7jmvr': (['Wyatt Earp'], 'playing as'),
}
# Reddit posts that are really a video or image guide
REDDIT_MEDIA = {
 '1m5bis3': (['Ancient Leshen'], 'video + infographic'), '1n56dad': (['Yennefer & Triss'], 'video + infographic'),
 '1r5lb5m': (['Blackbeard'], 'video + infographic'),
}

def rpost(pid):
    p = reddit[pid]
    return p, str(datetime.date.fromtimestamp(p['created_utc'])), f"https://www.reddit.com/r/Unmatched/comments/{pid}/"

for pid, (fmt, focus, note) in GENERAL_REDDIT.items():
    p, d, u = rpost(pid)
    add(G, f"Reddit: {p['author']}", p['title'], u, fmt, focus, d, note=note)

for pid, (fs, focus) in R.items():
    p, d, u = rpost(pid)
    title = p['title'].strip()
    fmt = 'discussion thread'
    if pid in ('1ktnoa2',): fmt = 'written analysis'
    for f in fs:
        add(f, f"Reddit: {p['author']}", title, u, fmt, focus, d,
            note=f"{p['num_comments']} comments" + (' · covers the whole box' if len(fs) > 2 else ''))
for pid, (fs, fmt) in REDDIT_MEDIA.items():
    p, d, u = rpost(pid)
    for f in fs: add(f, f"Reddit: {p['author']}", p['title'], u, fmt, 'playing as', d, note='Infographic post; the video is on YouTube (Karma)')

# ---------- Gridbeast (written guides) ----------
GB_SW = {l.split()[1] for l in open(S + '/dl/gb-check.txt') if l.startswith('SW')}
names_map = {'Robert Muldoon': 'Robert Muldoon (InGen)', 'Little Red Riding Hood': 'Little Red Riding Hood'}
for m in re.finditer(r'\|\s*([^|]*?)\s*\|\s*(https://gridbeast\.gg/unmatched-[^\s|]+)', open(UPLOAD).read()):
    f = names_map.get(m.group(1), m.group(1))
    if f not in set_of: print('gridbeast unmatched name', f); continue
    sw = m.group(2) in GB_SW
    add(f, 'Gridbeast', f'Unmatched – {f}', m.group(2), 'written guide', 'both' if sw else 'playing as',
        note='Strategies and Tips (3 tips) + Strengths and Weaknesses' if sw else 'Overview, Hero Stats, Strategies and Tips (3 tips), Final Thoughts')

# ---------- Other written guides ----------
add('Little Red Riding Hood', 'Antlerflax Books', 'Unmatched – Hero Analysis: Little Red Riding Hood', 'https://antlerflaxbooks.wordpress.com/2022/09/06/unmatched-hero-analysis-little-red-riding-hood/', 'written analysis', 'both', '2022-09-06')
for f in by_set['Battle of Legends 1']:
    add(f, 'Antlerflax Books', "Tabletop Review 9: Battle of Legends (Volume 1)", 'https://antlerflaxbooks.wordpress.com/2019/12/31/board-game-review-9-unmatched-battle-of-legends-volume-1/', 'review (hero by hero)', 'playing as', '2019-12-31', note='From your list; a review, kept because it goes hero by hero')
    add(f, 'WarBand.ru (Russian)', 'How to win in Unmatched Vol. 1', 'https://warband.ru/85-kak-pobezhdat-v-unmatched-vol-1.html', 'written guide', 'playing against', note='In Russian; how to beat each Battle of Legends 1 hero')
MARVEL = [f for s in ('Marvel: Redemption Row', "Marvel: Hell's Kitchen", 'Marvel: Teen Spirit', 'Marvel: For King and Country', 'Marvel: Brains and Brawn', 'Deadpool') for f in by_set[s]]
for f in MARVEL:
    add(f, 'The Pop Insider', 'Unmatched: Marvel — Who to Play, How to Win', 'https://thepopinsider.com/unmatched-marvel-who-to-play-how-to-win-and-whats-coming-next/', 'written guide', 'playing as', note='Covers the Marvel roster as a whole')
for f in ('Bruce Lee', 'Muhammad Ali'):
    add(f, 'Restoration Games (official)', 'Design Diary: Bruce Lee vs Muhammad Ali', 'https://restorationgames.com/design-diary-lee-vs-ali/', 'official article', 'both', '2026-03-04', note='Includes the designers\' "Ringside Advice" tips')
for f in by_set['Stars and Stripes']:
    add(f, 'Restoration Games (official)', 'From Spycraft to Steam Power: The Gameplay of Unmatched: Stars and Stripes', 'https://restorationgames.com/gameplay-of-unmatched-stars-and-stripes/', 'official article', 'playing as', '2026-05-20')
for f in by_set['TMNT']:
    add(f, 'Restoration Games (official)', 'From Leader to Wild Card: The Turtles of Unmatched Adventures', 'https://restorationgames.com/leader-to-wild-card-turtles-of-unmatched-adventures/', 'official article', 'playing as', '2026-05-22', note='One section per Turtle playstyle')
for f in by_set['TMNT: Shredder & Krang']:
    add(f, 'Restoration Games (official)', 'A Villain or A Hero? Shredder and Krang', 'https://restorationgames.com/villain-or-hero-shredder-krang-unmatched-tmnt/', 'official article', 'playing as', '2026-09-15')

# BoardGameGeek: found by web search; BGG blocks automated access so these were not opened
BGG_ROSTER = [
 ('Humble Beginnings', 'https://boardgamegeek.com/thread/3090133/an-unmatched-roster-humble-beginnings', ['Battle of Legends 1', 'Robin Hood vs. Bigfoot', 'Bruce Lee'], 'Covers the first few boxes; exact boxes not confirmed'),
 ('Cobble and Fog', 'https://boardgamegeek.com/thread/3097271/an-unmatched-roster-cobble-and-fog', ['Cobble & Fog'], ''),
 ('Jurassic Park', 'https://boardgamegeek.com/thread/3101319/an-unmatched-roster-jurassic-park', ['Jurassic Park: InGen vs. Raptors', 'Jurassic Park: Sattler vs. T. Rex'], ''),
 ('The Opposite of Redemption', 'https://boardgamegeek.com/thread/3182025/an-unmatched-roster-the-opposite-of-redemption', ['Marvel: Redemption Row'], 'Box inferred from the title'),
 ("What's Cooking in Hell's Kitchen?", 'https://boardgamegeek.com/thread/3188799/an-unmatched-roster-whats-cooking-in-hells-kitchen', ["Marvel: Hell's Kitchen"], ''),
]
for t, u, sets, note in BGG_ROSTER:
    for s in sets:
        for f in by_set[s]:
            add(f, 'BoardGameGeek: Luke M. (@TFJ383)', f'An Unmatched Roster: {t}', u, 'written analysis', 'playing as', checked='search only', note=note)
BGG_UNKNOWN = [('It\'s Less Dangerous', 'https://boardgamegeek.com/thread/3205520/an-unmatched-roster-its-less-dangerous'),
               ('Messy Politics', 'https://boardgamegeek.com/thread/3221658/an-unmatched-roster-messy-politics'),
               ('Anything But Marvelous', 'https://boardgamegeek.com/thread/3250019/an-unmatched-roster-anything-but-marvelous'),
               ('Ferociously Fantastic', 'https://boardgamegeek.com/thread/3281478/an-unmatched-roster-ferociously-fantastic'),
               ('Twice the Pride, Double the Fall', 'https://boardgamegeek.com/thread/3286237/an-unmatched-roster-twice-the-pride-double-the-fal'),
               ('Cast a Spell on Me', 'https://boardgamegeek.com/thread/3302508/an-unmatched-roster-cast-a-spell-on-me')]
for t, u in BGG_UNKNOWN:
    add(G, 'BoardGameGeek: Luke M. (@TFJ383)', f'An Unmatched Roster: {t}', u, 'written analysis', 'playing as', checked='search only', note='Box not shown in search results')
for f, t, u, focus in [
 ('Medusa', 'Medusa: Noob Cannon, OP, or am I just not very good?', 'https://boardgamegeek.com/thread/2253704/medusa-noob-cannon-op-or-am-i-just-not-very-good', 'both'),
 ('Medusa', 'Is Medusa Fun?', 'https://boardgamegeek.com/thread/2604780/is-medusa-fun', 'playing as'),
 ('Raptors', 'Tips on Playing as the Raptors', 'https://boardgamegeek.com/thread/2450948/tips-on-playing-as-the-raptors', 'playing as'),
 ('Robin Hood', 'How can Robin Hood defeat the Bigfoot?', 'https://boardgamegeek.com/thread/2921690/how-can-robin-hood-defeat-the-bigfoot', 'both'),
 ('Bigfoot', 'How can Robin Hood defeat the Bigfoot?', 'https://boardgamegeek.com/thread/2921690/how-can-robin-hood-defeat-the-bigfoot', 'playing against'),
 ('Yennenga', 'Yennenga against vs Achilles', 'https://boardgamegeek.com/thread/3260485/yennenga-against-vs-achilles', 'both'),
 ('Achilles', 'Yennenga against vs Achilles', 'https://boardgamegeek.com/thread/3260485/yennenga-against-vs-achilles', 'both')]:
    add(f, 'BoardGameGeek', t, u, 'discussion thread', focus, checked='search only')

# ---------- Videos ----------
roster_rows = list(csv.DictReader(open(S + '/unmatched-fighters-dataset.csv')))
for r in roster_rows:
    f = DISPLAY.get(r['fighter'], r['fighter']).replace('Robert Muldoon (InGen)', 'Robert Muldoon (InGen)')
    for part in [p for p in r['video_guides'].split(' ; ') if p]:
        src, url = part.split(': ', 1)
        vid = re.search(r'(?:v=|youtu\.be/)([\w-]{11})', url).group(1)
        o = oembed.get(vid, {})
        add(f, f'{src} (YouTube)', o.get('title', ''), url, 'video', 'playing as', note='Link from the Unmatched Roster fan site; confirmed live')
KARMA = [('23fRvsJEaUU', 1, 'Little Red Riding Hood'), ('csXYxz_a3uQ', 2, 'Nikola Tesla'), ('6kjV3zcPuPk', 3, 'Tomoe Gozen'),
 ('GrNarUkqq9E', 4, 'Winter Soldier'), ('6JjrLDppsOg', 5, 'Cloak & Dagger'), ('4kmq5rqbwx8', 6, 'She-Hulk'), ('vxTNU0p0S10', 7, 'Black Widow'),
 ('E4xbtYc_daU', 8, 'Dr. Jill Trent'), ('TyjF2vJEJs4', 9, 'Oda Nobunaga'), ('wb3KdBzGq-M', 10, 'Daredevil'), ('1rEiFhIqnic', 11, 'Moon Knight'),
 ('GzUXGdCFmmw', 12, 'Doctor Strange'), ('Ief6ueYVL20', 13, 'Shakespeare'), ('m2gLIrx2IOw', 14, 'Robert Muldoon (InGen)'),
 ('LVh50o5bbsc', 15, 'The Wayward Sisters'), ('B6nC0b400-g', 16, 'Titania'), ('RTgu0pUEimQ', 17, 'The Golden Bat'), ('zSsvURmCCcE', 18, 'Luke Cage'),
 ('Y3MA0XRug58', 19, 'Black Panther'), ('mq3EwElOakM', 20, 'The Genie'), ('hWXYF-FodDQ', 21, 'Ciri'), ('8SLmr2URk9w', 22, 'Ancient Leshen'),
 ('3NQE7MBkwcA', 23, 'Yennefer & Triss'), ('nE-zWqU0Kp4', 24, 'Blackbeard')]
for vid, n, f in KARMA:
    t = f'Strategy Sunday Vol. {n}' if n > 2 else f'{f} Strategy Guide (Strategy Sunday playlist, #{n})'
    add(f, 'Karma (YouTube)', t, f'https://www.youtube.com/watch?v={vid}', 'video', 'playing as', note='From the "Strategy Sunday" playlist')
for vid, f in [('kTDlqoPUGwY', 'Muhammad Ali'), ('lGVIKX-Wvvg', 'Leonardo'), ('j-3lXW3PfD4', 'Wyatt Earp'), ('-9dJUO4tGII', 'Cloak & Dagger'),
               ('iaKRJfKkEKQ', 'Chupacabra'), ('6atiqWL0ef0', 'Donatello'), ('SziqNdowXA4', 'Bullseye')]:
    add(f, 'The Gaming Geek Net (YouTube)', f'{f} Advanced Strategy Guide', f'https://www.youtube.com/watch?v={vid}', 'video', 'playing as', note='Same author as The Gaming Geek / Reddit LabRat2329')
for vid, f, src, t in [('TzwOuXNmwGc', 'Bigfoot', 'I66Y (YouTube)', 'Master of Adaptation - Bigfoot strategy guide'),
                       ('-OxzK31iaGw', 'Muhammad Ali', 'PrinceOfAsphodelUnmatched (YouTube)', 'Unmatched Muhammad Ali Combo Guide'),
                       ('laLqE6bF8SY', 'Ghost Rider', 'HELPivFALLN (YouTube)', 'Unmatched Ghost Rider Guide'),
                       ('o9Do4HqSdLM', 'Moon Knight', 'HELPivFALLN (YouTube)', 'Unmatched Moon Knight Bronze Guide'),
                       ('iCcUIauWt5I', 'She-Hulk', 'CaptainCrockpot (YouTube)', 'Brains and Brawn Unboxing, Strategy & Overview Pt. 1: She-Hulk'),
                       ('DjQ-XlZm-Lk', 'Doctor Strange', 'CaptainCrockpot (YouTube)', 'Brains and Brawn Unboxing, Strategy & Overview Pt. 2: Doctor Strange'),
                       ('io-tEfPZJvY', 'Spider-Man', 'CaptainCrockpot (YouTube)', 'Brains and Brawn Unboxing, Tips & Overview Pt. 3: Spider-Man')]:
    add(f, src, t, f'https://www.youtube.com/watch?v={vid}', 'video', 'playing as')

# ---------- Write CSV ----------
FMT_ORDER = {'written guide': 0, 'written analysis': 1, 'official article': 2, 'review (hero by hero)': 3, 'infographic': 4,
             'video + infographic': 5, 'discussion thread': 6, 'video': 7}
order = {f: i for i, f in enumerate(fighters)}
seen = set(); out = []
for r in rows:
    k = (r['fighter'], r['url'])
    if k in seen: continue
    seen.add(k); out.append(r)
out.sort(key=lambda r: (-1 if r['fighter'] == 'GENERAL' else order[r['fighter']], FMT_ORDER.get(r['format'], 9), r['date'] or '9999'))
cols = ['fighter', 'set', 'format', 'focus', 'source', 'title', 'url', 'date', 'checked', 'note']
with open(S + '/unmatched-strategy-references.csv', 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(out)
json.dump(out, open(S + '/refs.json', 'w'), indent=1)
written = {'written guide', 'written analysis', 'official article', 'review (hero by hero)', 'infographic', 'video + infographic'}
print(len(out), 'rows')
for f in fighters:
    rs = [r for r in out if r['fighter'] == f]
    print(f"{f:28} written={sum(r['format'] in written for r in rs):2} threads={sum(r['format']=='discussion thread' for r in rs):2} videos={sum(r['format']=='video' for r in rs):2}")
