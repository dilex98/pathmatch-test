"""answer_key.py - picks the 200 lines a person checks by hand, to measure the reader's TRUE accuracy.

The Gemini labels cannot prove 95%: when the reader finds a real skill the teacher forgot, the labels call it a
mistake. So a person judges. The lines are the CV-style rewrites of posting sentences from employers the reader
never saw in training (the test 10%), so they are fair. No real CV is used.

For each line it lists what the two readers found:
    strict reader (reader-strict) -> what could count automatically
    bold reader   (reader-bold)   -> extra finds, shown only as "please confirm"
Lines are chosen so that no skill takes over the sample (at most 3 lines with the same strongest skill), and
French lines keep their share. Usage: python3 tools/answer_key.py --out answer_key/draft.json [--n 200]
"""
import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_reader import agreed, pieces, side  # noqa: E402


def load_reader(path):
    m = json.load(open(path, encoding="utf-8"))

    def read(text):
        v = {p: m["clues"][p] for p in pieces(text) if p in m["clues"]}
        n = math.sqrt(sum(x * x for x in v.values())) or 1.0
        out = []
        for s in m["skills"]:
            z = s["b"] + sum(w * v[c] / n for c, w in s["w"].items() if c in v)
            p = 1 / (1 + math.exp(-z))
            if p >= m["cut"]:
                out.append((p, s["n"]))
        return [n for _, n in sorted(out, reverse=True)]
    return read


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="answer_key/draft.json")
    ap.add_argument("--n", type=int, default=200)
    a = ap.parse_args()
    strict, bold = load_reader("reader-strict/skill_reader.json"), load_reader("reader-bold/skill_reader.json")
    rows = []
    for d in agreed(Path(".")):
        if side(d["emp"]) != "test" or not d["cvs"]:
            continue
        line = d["cvs"][0]
        s, b = strict(line), bold(line)
        if not s and not b:
            continue
        rows.append({"line": line, "lang": d["lang"], "strict": s, "bold": [x for x in b if x not in s],
                     "teacher": d["skills"], "id": d["id"]})
    rows.sort(key=lambda r: hashlib.sha1(r["id"].encode()).hexdigest())
    picked, per = [], Counter()
    for r in rows:
        top = (r["strict"] or r["bold"])[0]
        if per[top] >= 3:
            continue
        per[top] += 1
        picked.append(r)
        if len(picked) >= a.n:
            break
    for i, r in enumerate(picked, 1):
        r["n"] = i
        r["skills"] = [{"tag": f"{i}{chr(97 + j)}", "n": n, "level": lvl, "teacher_agrees": n in r["teacher"]}
                       for j, (n, lvl) in enumerate([(x, "auto") for x in r["strict"]] + [(x, "confirm") for x in r["bold"]])]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(picked, indent=1, ensure_ascii=False))
    c = Counter(x["level"] for r in picked for x in r["skills"])
    print(f"{len(rows)} test lines with a find; picked {len(picked)} ({sum(r['lang'] == 'fr' for r in picked)} French); "
          f"skills to judge: {sum(c.values())} ({c['auto']} strict, {c['confirm']} bold-only)")


if __name__ == "__main__":
    main()
