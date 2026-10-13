"""
Brings a tournament over from the old Unmatched-Tournament app into the matcher's
tournaments (the same thing as the import form on /tournaments).

Usage (on the server, with both repos side by side):
  python scripts/import_old_tournament.py ../Unmatched-Tournament/data/bracket.json \\
      ../Unmatched-Tournament/data/state.json --name "The big one" --p1 Ahmad --p2 Mohammad

Writes to TOURNAMENT_DATA_DIR (default data/tournaments, which docker-compose mounts).
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import tournaments as T  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bracket")
    ap.add_argument("state", nargs="?")
    ap.add_argument("--name", default="Imported tournament")
    ap.add_argument("--p1", default="P1")
    ap.add_argument("--p2", default="P2")
    ap.add_argument("--data-dir", default=os.environ.get("TOURNAMENT_DATA_DIR", os.path.join(ROOT, "data", "tournaments")))
    args = ap.parse_args(argv)

    with open(args.bracket, encoding="utf-8") as f:
        bracket = json.load(f)
    state = {}
    if args.state:
        with open(args.state, encoding="utf-8") as f:
            state = json.load(f)
    t = T.import_legacy(bracket, state, args.name, {"P1": args.p1, "P2": args.p2})

    with open(os.path.join(ROOT, "input", "fighters.json"), encoding="utf-8") as f:
        known = {x["id"] for x in json.load(f)["fighters"]}
    unknown = sorted(T.all_fighters(t) - known)
    if unknown:
        sys.exit(f"Unknown fighter ids in the bracket: {', '.join(unknown)}")

    t = T.TournamentStore(args.data_dir).create(t)
    s = T.scores(t)
    played = sum(1 for m in t["matches"] if m["winner"])
    print(f"Imported {t['name']} as {t['id']} into {args.data_dir}: {played}/{len(t['matches'])} matches played, "
          + " – ".join(f"{p['name']} {s[p['id']]['standard']}" for p in t["players"]))
    missing = [m["label"] for m in t["matches"] if m["winner"] and not m["player"]]
    if missing:
        print(f"No player recorded for: {', '.join(missing)} (pick one on the tournament page).")


if __name__ == "__main__":
    main()
