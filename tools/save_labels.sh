#!/usr/bin/env bash
# Commit whatever labels exist so far. Used after each vote, so a later step that runs long or is cut off
# by GitHub's time limit can never take the earlier votes' work with it.
set -u
git config user.name "github-actions[bot]"
git config user.email "41898299+github-actions[bot]@users.noreply.github.com"
for d in labels labels-second labels-third labels-flash; do
  if [ -d "$d" ]; then git add "$d"; fi
done
if git diff --cached --quiet; then echo "nothing new"; exit 0; fi
MSG=$(python3 - <<'PY'
import json, os
out = []
for d in ["labels", "labels-second", "labels-third"]:
    p = d + "/progress.json"
    if os.path.exists(p):
        j = json.load(open(p))
        out.append(f"{d} {j['sentences']} ({j['last_run']['stopped'][:40]})")
print("; ".join(out))
PY
)
git commit -q -m "Teacher labels: $MSG"
for i in 1 2 3; do
  git pull --rebase -q origin main && git push -q && { echo "saved: $MSG"; exit 0; }
  sleep 5
done
echo "could not push the labels"; exit 1
