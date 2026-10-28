"""
Build Short guides from drafts that cite the fighter's Medium guide (see research/GUIDES-V2.md).

    python -X utf8 research/scripts/make_short.py drafts.md

drafts.md holds one block per fighter, starting with a line `=== <fighter id>`, followed by the Short
body (In short, How they win, How they lose) with citations numbered as in that fighter's Medium
guide. Each block becomes research/private/guides/<id>.short.md, with the Medium guide's reference
lines copied over and renumbered in order of first use.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUIDES = ROOT / "research/private/guides"


def main():
    names = {f["id"]: f["name"] for f in
             json.loads((ROOT / "input/fighters.json").read_text(encoding="utf-8"))["fighters"]}
    drafts = Path(sys.argv[1]).read_text(encoding="utf-8")
    for fid, body in re.findall(r"^=== (\S+)\n(.*?)(?=^=== |\Z)", drafts, re.M | re.S):
        medium = (GUIDES / f"{fid}.medium.md").read_text(encoding="utf-8-sig")
        refs = dict(re.findall(r"^(\d+)\. (.*)$", medium.split("### References", 1)[1], re.M))
        order = list(dict.fromkeys(re.findall(r"\[(\d+)\]", body)))
        missing = [n for n in order if n not in refs]
        if missing:
            sys.exit(f"{fid}: cites {missing}, not in its Medium guide")
        new = {old: str(i + 1) for i, old in enumerate(order)}
        body = re.sub(r"\[(\d+)\]", lambda m: f"[{new[m.group(1)]}]", body.strip())
        lines = []
        for old in order:
            line = re.sub(r"\(see \[(\d+)\]\)", lambda m: f"(see [{new.get(m.group(1), m.group(1))}])", refs[old])
            # a "see [n]" pointing at a reference this Short guide doesn't use needs that reference's full line
            line = re.sub(r'Comment on ("[^"]+") \(see \[\d+\]\)\.?$', lambda m: _full_thread(refs, m.group(1)), line)
            lines.append(f"{new[old]}. {line}")
        text = (f"<!-- id: {fid} -->\n## {names[fid]}\n\n{body}\n\n### References\n" + "\n".join(lines) + "\n\n---\n")
        (GUIDES / f"{fid}.short.md").write_text(text, encoding="utf-8")
        print(f"{fid}: {len(re.sub(r'\[\d+\]', '', body).split())} words, {len(order)} references")


def _full_thread(refs, title):
    """The thread part ("Comment on "T" by u/op. *Site*, date. URL") from the first reference to that thread."""
    for line in refs.values():
        m = re.search(r'Comment on ' + re.escape(title) + r' by .*$', line)
        if m:
            return m.group(0)
    return f"Comment on {title}."


if __name__ == "__main__":
    main()
