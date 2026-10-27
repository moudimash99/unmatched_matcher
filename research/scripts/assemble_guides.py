"""
Join the per-fighter v2 guides into one file the site reads (see research/GUIDES-V2.md).

    python -X utf8 research/scripts/assemble_guides.py medium   # -> input/fighter_guides_medium.md

Entries follow input/fighters.json order; fighters without a guide yet are left out.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HEADERS = {
    "medium": "Medium strategy guides (the default tab on fighter pages).",
    "cards": "Card-by-card strategy guides.",
    "short": "Short strategy guides.",
}


def main():
    kind = sys.argv[1]
    fighters = json.loads((ROOT / "input/fighters.json").read_text(encoding="utf-8"))["fighters"]
    entries = []
    for f in fighters:
        path = ROOT / f"research/private/guides/{f['id']}.{kind}.md"
        if path.exists():
            entries.append(path.read_text(encoding="utf-8-sig").strip())
    out = ROOT / f"input/fighter_guides_{kind}.md"
    head = (f"# {HEADERS[kind]}\n\nWritten from player guides, videos and forum discussions; "
            "format and rules in research/GUIDES-V2.md. Each entry starts with its fighter id.\n\n")
    out.write_text(head + "\n\n".join(entries) + "\n", encoding="utf-8")
    print(f"{out.relative_to(ROOT)}: {len(entries)} of {len(fighters)} fighters")


if __name__ == "__main__":
    main()
