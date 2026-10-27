"""
Check the v2 guides in research/private/guides/ (see research/GUIDES-V2.md).

    python -X utf8 research/scripts/check_guides.py medium [ids...]

Per guide: id line and closing ---, every [n] defined and every reference cited, references numbered in
order of first use, clean rendering, no other fighter named, bold/quoted names are real cards, word count.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import strategies  # noqa: E402

GUIDES = ROOT / "research/private/guides"
LABELS = {"in short", "choose this when", "on your turn", "on their turn", "positioning", "answer",
          "opening", "midgame", "closing it out", "when", "how", "watch out", "setup", "payoff", "finishing"}
# words in fighter names that are also ordinary words or this game's terms
COMMON = {"Little", "Riding", "Hood", "Black", "Doctor", "King", "Ancient", "Golden", "Moon", "Ghost", "Winter",
          "Spider", "Squirrel", "Bloody", "Invisible", "Man", "Girl", "The", "Wayward", "Sisters", "Strange",
          "Christmas", "Knight", "Rider", "Soldier", "Panther", "Widow", "Cloak", "Dagger", "Rosie", "Riveter",
          "Henry", "John", "George", "Jill", "Trent", "Annie", "Sun", "Bruce", "Luke", "Cage", "Robert", "Nikola",
          "William", "Muhammad", "Wyatt", "Earp", "Oda", "Tomoe", "Gozen", "Hyde", "Jekyll", "Mary", "Ms", "Dr",
          "Genie", "Hamlet", "Titania", "Leshen", "Eredin", "Loki", "Pandora", "Krang", "Angel", "Spike",
          "Willow", "Alice", "Medusa", "Sinbad", "Dracula", "Raptors", "Beowulf", "Achilles", "Buffy"}


def clean(title):
    return re.sub(r"[^\w\s'\-\.,!?:\"&’]", "", title).strip().lower()


def main():
    kind, ids = sys.argv[1], sys.argv[2:]
    fighters = json.loads((ROOT / "input/fighters.json").read_text(encoding="utf-8"))["fighters"]
    heroes = json.loads((ROOT / "input/heroes.json").read_text(encoding="utf-8"))
    names = {f["id"]: f["name"] for f in fighters}
    files = [GUIDES / f"{i}.{kind}.md" for i in ids] if ids else sorted(GUIDES.glob(f"*.{kind}.md"))
    for path in files:
        fid = path.name.split(".")[0]
        text = path.read_text(encoding="utf-8-sig")
        problems = []
        if not text.startswith(f"<!-- id: {fid} -->\n"):
            problems.append("id line")
        if not text.rstrip().endswith("---"):
            problems.append("no closing ---")
        body, _, refs = text.partition("### References")
        cited = [int(n) for n in re.findall(r"\[(\d+)\]", body)]
        defined = {int(n) for n in re.findall(r"^(\d+)\. ", refs, re.M)}
        if set(cited) - defined:
            problems.append(f"undefined refs {sorted(set(cited) - defined)}")
        if defined - set(cited):
            problems.append(f"unused refs {sorted(defined - set(cited))}")
        first = list(dict.fromkeys(cited))
        if first != sorted(first):
            problems.append(f"refs not in order of first use {first}")
        if re.search(r"[^\s\]]\[\d+\]", body):
            problems.append("citation without a space before it")
        html = str(strategies.render(text, "x"))
        if re.search(r"\*\*|\]\(|`", html):
            problems.append("Markdown left after rendering")
        for oid, oname in names.items():
            if oid == fid:
                continue
            parts = {oname} | {p for p in re.split(r"[ &.]+", oname) if len(p) > 3 and p not in COMMON}
            for p in parts:
                if p not in names[fid] and re.search(r"\b%s\b" % re.escape(p), body):
                    problems.append(f"names another fighter? {p}")
        if kind == "cards":  # card entries are headed by the bold card name
            titles = {clean(c["title"]) for c in heroes.get(fid, {}).get("deck", [])}
            for b in re.findall(r"^\*\*([^*]+)\*\*\s*$", body, re.M):
                b = b.strip().lower()
                if not all(part in titles for part in re.split(r" and |, ", b)):
                    problems.append(f"bold name not a card? {b}")
        prose = re.sub(r"\[\d+\]", "", body.split("\n", 2)[2] if body.count("\n") > 2 else body)
        arc = prose.partition("### Game arc")
        words = len(arc[0].split())
        extra = f" + {len(arc[2].split())} game arc" if arc[1] else ""
        print(f"{fid}: {words} words{extra}" + ("" if not problems else "  <- " + "; ".join(problems)))


if __name__ == "__main__":
    main()
