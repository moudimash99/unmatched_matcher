import json, glob, re, sys, datetime
S = sys.argv[1]
posts = {}
for f in glob.glob(S + "/dl/t_*.json") + glob.glob(S + "/dl/a_*.json") + [S + "/dl/karma.json"]:
    try: rows = json.load(open(f))
    except Exception: continue
    for p in rows: posts[p["id"]] = p
FIGHTERS = {
 "Medusa":[r"medusa"], "Sinbad":[r"sinbad", r"simbad"], "Alice":[r"alice"], "King Arthur":[r"king arthur", r"\barthur\b"],
 "Bruce Lee":[r"bruce"], "Robin Hood":[r"robin hood", r"\brobin\b"], "Bigfoot":[r"big ?foot"], "Robert Muldoon (InGen)":[r"muldoon", r"ingen"],
 "Raptors":[r"raptor"], "Invisible Man":[r"invisible man"], "Jekyll & Hyde":[r"jekyll", r"\bhyde\b"], "Dracula":[r"dracula"],
 "Sherlock Holmes":[r"sherlock", r"holmes"], "Buffy":[r"\bbuffy\b(?! set)"], "Willow":[r"willow"], "Angel":[r"\bangel\b"], "Spike":[r"\bspike\b"],
 "Little Red Riding Hood":[r"little red", r"red riding"], "Beowulf":[r"beowulf", r"\bbeo\b"], "Deadpool":[r"deadpool"],
 "Sun Wukong":[r"wukong"], "Yennenga":[r"yennenga"], "Achilles":[r"achill"], "Bloody Mary":[r"bloody mary"],
 "Ghost Rider":[r"ghost ?rider"], "Luke Cage":[r"luke cage"], "Moon Knight":[r"moon ?knight"], "Bullseye":[r"bullseye"],
 "Daredevil":[r"daredevil"], "Elektra":[r"elektra"], "T. Rex":[r"t\.? ?-?rex", r"rexy"], "Dr. Sattler":[r"sattler"],
 "Houdini":[r"houdini"], "The Genie":[r"\bgenie\b"], "Squirrel Girl":[r"squirrel girl"], "Cloak & Dagger":[r"cloak"],
 "Ms. Marvel":[r"ms\.? marvel"], "Black Widow":[r"black widow"], "Black Panther":[r"black panther"], "Winter Soldier":[r"winter soldier"],
 "Spider-Man":[r"spider-?\s?man"], "She-Hulk":[r"she-? ?hulk"], "Doctor Strange":[r"(doctor|dr\.?) strange"],
 "Nikola Tesla":[r"tesla"], "Dr. Jill Trent":[r"\bjill\b"], "The Golden Bat":[r"golden bat"], "Annie Christmas":[r"annie"],
 "Oda Nobunaga":[r"nobunaga", r"\boda\b"], "Tomoe Gozen":[r"tomoe", r"gozen"], "Shakespeare":[r"shakespeare"],
 "The Wayward Sisters":[r"wayward"], "Hamlet":[r"hamlet"], "Titania":[r"titania"], "Geralt":[r"geralt"], "Ciri":[r"\bciri\b"],
 "Ancient Leshen":[r"leshen"], "Eredin":[r"eredin"], "Philippa":[r"philippa"], "Yennefer & Triss":[r"yennefer", r"\btriss\b"],
 "Chupacabra":[r"chupacabra"], "Blackbeard":[r"black ?beard"], "Pandora":[r"pandora"], "Loki":[r"\bloki\b"],
 "Muhammad Ali":[r"\bali\b", r"muhammad"], "Raphael":[r"raphael", r"\braph\b"], "Donatello":[r"donatello", r"donnie"],
 "Michelangelo":[r"mich(a)?elangelo", r"mikey"], "Leonardo":[r"leonardo"], "Shredder":[r"shredder"], "Krang":[r"krang"],
 "John Henry":[r"john henry"], "Rosie the Riveter":[r"\brosie\b"], "George Washington":[r"washington"], "Wyatt Earp":[r"wyatt"],
}
STRAT = re.compile(r"tips?\b|strateg|guide|how to (play|beat|counter|win|use)|play(ing)? (as|with)|\bplay\b.*\?|playing|beat|counter|advice|struggl|analysis|deep dive|effectively|battling|mulligan|matchups?|against|\bvs\.?\b|work\b|help|win(ning)?\b|losing|lose", re.I)
NOISE = re.compile(r"paint|mini(s|ature)|custom|fan ?(made|deck)|homebrew|storage|print|proxy|card ?back|art\b|artwork|foil|unbox|buy|shipping|order|sleev|3d|fanart|cosplay|meme|rule|ruling|question|errata|faq|clarif|resolve|what happens|does .* work|interaction|stl|deck maker|tts|tabletop sim|sculpt|base\b|figure|tournament results|bracket|tier ?list|poll|which .* buy", re.I)
GENERAL = re.compile(r"fundamentals|visual introduction|basic strategy|exhaustion tips|how to improve|how to learn strategies|2v2 strateg|tempo|win conditions|aggro|dealing with sidekicks|one sentence tip|any tips vs each|counterpicks against the top|battling the top", re.I)
out = {"general": [], "fighters": {k: [] for k in FIGHTERS}}
for p in posts.values():
    t = p["title"]; tl = t.lower()
    row = {"id": p["id"], "date": str(datetime.date.fromtimestamp(p["created_utc"])), "title": t, "author": p["author"],
           "score": p.get("score"), "comments": p.get("num_comments"), "url": f"https://www.reddit.com/r/Unmatched/comments/{p['id']}/"}
    if GENERAL.search(t) and not NOISE.search(t): out["general"].append(row); continue
    if NOISE.search(t) or not STRAT.search(t): continue
    hits = [k for k, pats in FIGHTERS.items() if any(re.search(x, tl) for x in pats)]
    for k in hits: out["fighters"][k].append(row)
json.dump(out, open(S + "/reddit-candidates.json", "w"), indent=1)
print("posts", len(posts), "general", len(out["general"]))
for k, v in out["fighters"].items(): print(f"{k}: {len(v)}")
