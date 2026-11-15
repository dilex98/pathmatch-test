"""meaning_test.py - I-14, step one: does matching by meaning find skills the words miss?

For every skill a posting asks for and the CV does not have in words, this finds the line of the CV
closest in meaning, and prints the pair with how close it is. Nothing on the site changes. The pairs
are what a person labels - same skill / related / not the same - and the labels are what set the two
cut-offs. Until then no number here is a threshold.

Run: python3 tools/meaning_test.py <gaps.json> [out.csv]
"""
import json, pickle, re, sys
import numpy as np

gapsf = sys.argv[1]
outf = sys.argv[2] if len(sys.argv) > 2 else None
M = pickle.load(open("tools/meaning.pkl", "rb"))
terms = {t: i for i, t in enumerate(M["terms"])}
T, idf = M["T"], M["idf"]

def norm(s):
    return re.sub(r"[^a-z0-9+#/ ]+", " ", s.lower()).strip()

def vec(text):
    """a phrase is the idf-weighted mean of the terms it holds, single words and pairs"""
    w = norm(text).split()
    picks = []
    for i, x in enumerate(w):
        if x in terms: picks.append(terms[x])
        if i + 1 < len(w):
            bg = x + " " + w[i + 1]
            if bg in terms: picks.append(terms[bg])
    if not picks: return None
    wt = idf[picks][:, None]
    v = (T[picks] * wt).sum(0)
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else None

def cv_lines(cv):
    out = []
    for raw in cv.split("\n"):
        s = raw.strip()
        if len(s) < 12 or len(s) > 400: continue
        if sum(c.isalpha() for c in s) < 8: continue
        v = vec(s)
        if v is not None: out.append((s, v))
    return out

G = json.load(open(gapsf, encoding="utf-8"))
rows = []
for cv_name, d in G.items():
    lines = cv_lines(d["cv"])
    if not lines: continue
    L = np.vstack([v for _, v in lines])
    seen = set()
    for j in d["jobs"]:
        for g in j["gaps"]:
            if (cv_name, g) in seen: continue
            seen.add((cv_name, g))
            v = vec(g)
            if v is None: continue
            sims = L @ v
            k = int(np.argmax(sims))
            rows.append({"cv": cv_name, "skill": g, "sim": float(sims[k]),
                         "line": lines[k][0][:150], "job": j["title"][:60]})

rows.sort(key=lambda r: -r["sim"])
print(f"{len(rows)} distinct missing skills across the four CVs\n")
print("how close the best CV line is, for all of them:")
s = np.array([r["sim"] for r in rows])
for lo, hi in [(0.8, 1.01), (0.7, 0.8), (0.6, 0.7), (0.5, 0.6), (0.4, 0.5), (0.0, 0.4)]:
    n = int(((s >= lo) & (s < hi)).sum())
    print(f"   {lo:.1f} to {hi if hi<=1 else 1.0:.1f} : {n:5d}  {'#'*int(60*n/max(1,len(rows)))}")
print("\nthe 25 closest pairs - these are the ones worth labelling first:\n")
for r in rows[:25]:
    print(f"  {r['sim']:.3f}  {r['cv']}  posting wants “{r['skill']}”")
    print(f"           CV says “{r['line'][:110]}”")
if outf:
    import csv
    with open(outf, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["cv", "skill the posting asks for", "closest line on the CV", "how close",
                    "posting", "YOUR LABEL: same / related / not the same"])
        for r in rows: w.writerow([r["cv"], r["skill"], r["line"], f"{r['sim']:.3f}", r["job"], ""])
    print(f"\nwritten to {outf}")
