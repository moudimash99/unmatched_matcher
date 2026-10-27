"""
Run Codex to write one version of the v2 strategy guides, one fighter per run (see research/GUIDES-V2.md).

    python -X utf8 research/scripts/codex_guides.py medium --next 10     # next 10 fighters without one
    python -X utf8 research/scripts/codex_guides.py medium medusa bruce_lee

Prompts come from research/prompts/{kind}.md ({name} and {id} filled in). Output and evidence go to
research/private/guides/, logs to research/private/logs/. Fighters that already have output are skipped.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research/private/guides"
LOGS = ROOT / "research/private/logs"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["medium", "cards", "short"])
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--next", type=int, help="the next N fighters (fighters.json order) without output")
    args = ap.parse_args()

    fighters = json.loads((ROOT / "input/fighters.json").read_text(encoding="utf-8"))["fighters"]
    names = {f["id"]: f["name"] for f in fighters}
    template = (ROOT / f"research/prompts/{args.kind}.md").read_text(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

    todo = [i for i in (args.ids or names) if not (OUT / f"{i}.{args.kind}.md").exists()]
    unknown = [i for i in todo if i not in names]
    if unknown:
        sys.exit(f"unknown fighter ids: {unknown}")
    if args.next:
        todo = todo[: args.next]

    codex = shutil.which("codex") or sys.exit("codex not on PATH")
    for fid in todo:
        prompt = template.format(name=names[fid], id=fid)
        log = LOGS / f"{fid}.{args.kind}.log"
        start = time.time()
        with open(log, "w", encoding="utf-8") as fh:
            proc = subprocess.run([codex, "exec", "-s", "workspace-write", "-C", str(ROOT), "-"],
                                  input=prompt, text=True, encoding="utf-8", stdout=fh, stderr=subprocess.STDOUT)
        text = log.read_text(encoding="utf-8", errors="replace")
        tokens = re.findall(r"tokens used\s*\n?\s*([\d,]+)", text)
        done = (OUT / f"{fid}.{args.kind}.md").exists()
        print(f"{fid}: exit {proc.returncode}, {'written' if done else 'NO OUTPUT'}, "
              f"{(time.time() - start) / 60:.1f} min, {tokens[-1] if tokens else '?'} tokens", flush=True)
        if "usage limit" in text.lower():
            sys.exit("Codex usage limit reached; stopping")


if __name__ == "__main__":
    main()
