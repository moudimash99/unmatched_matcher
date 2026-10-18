#!/bin/bash
# usage: show.sh <id> [reddit_char_limit]
B=/tmp/claude-0/-home-user/f54e2b79-817a-598f-9a80-001eae11ae4d/scratchpad/briefs/$1.md
L=${2:-9000}
sed -n '1,/^## SOURCE FILE\|^## REFERENCES/p' "$B" | grep -v '^## SOURCE FILE\|^## REFERENCES'
awk '/^## SOURCE FILE gridbeast/{f=1} f&&/^## Strategies and Tips/{g=1} /^## Unmatched:|^## SOURCE FILE reddit/{g=0} g' "$B" | grep -v '^\s*$' | cut -c1-1400
echo "==== REDDIT"
awk '/^## SOURCE FILE reddit/{f=1;next} /^## REFERENCES/{f=0} f' "$B" | grep -v '^\s*$' | grep -v -E '^\s*\[[0-9-]+\] [^:]+: .{0,70}$' | cut -c1-800 | head -c "$L"
