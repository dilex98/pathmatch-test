"""meaning_e5.py - I-14, step one, with the model the plan actually names.

The first run of this test used a stand-in trained on our own postings, because huggingface.co is
blocked in the build sandbox. This runs `intfloat/multilingual-e5-small`, which is the model in the
plan and the one that would load in the applicant's browser. Two differences matter:

  1. e5 is trained on paraphrase pairs, not on which words appear together. That is the whole
     question: the stand-in could only say "these belong to the same world", which is why a job
     title scored closer to a skill than the real evidence did.
  2. **e5 needs its prefixes.** Every text must start with "query: " or "passage: ". Leaving them
     off is the usual way this model is tested badly, and it costs real accuracy. The skill the
     posting asks for is the query; the CV line is the passage.

Nothing about the site changes. This prints the same table as the stand-in run, so the two can be
compared row for row, and writes the pairs for labelling.

Needs:  pip install -U sentence-transformers
Run:    python3 tools/meaning_e5.py <gaps.json> [out.csv]

The CVs stay on the machine this runs on. Nothing is uploaded: the model is downloaded and run
locally.
"""
import json, sys, collections
import numpy as np

gapsf = sys.argv[1]
outf = sys.argv[2] if len(sys.argv) > 2 else None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    sys.exit("needs sentence-transformers:  pip install -U sentence-transformers")

print("loading intfloat/multilingual-e5-small (about 470 MB the first time)...")
model = SentenceTransformer("intfloat/multilingual-e5-small")

def embed(texts, kind):
    """e5 wants every text prefixed. The skill asked for is the query, the CV line the passage."""
    return model.encode([kind + ": " + t for t in texts],
                        normalize_embeddings=True, batch_size=64, show_progress_bar=False)

def cv_lines(cv):
    """the same lines the stand-in used, so the comparison is fair"""
    out = []
    for raw in cv.split("\n"):
        s = raw.strip()
        if len(s) < 12 or len(s) > 400: continue
        if sum(c.isalpha() for c in s) < 8: continue
        out.append(s)
    return out

G = json.load(open(gapsf, encoding="utf-8"))
rows = []
for cv_name, d in G.items():
    lines = cv_lines(d["cv"])
    if not lines: continue
    L = embed(lines, "passage")
    gaps, where = [], collections.defaultdict(list)
    for j in d["jobs"]:
        for g in j["gaps"]:
            if g not in where: gaps.append(g)
            where[g].append(j.get("title", ""))
    if not gaps: continue
    Q = embed(gaps, "query")
    sims = Q @ L.T
    for i, g in enumerate(gaps):
        k = int(np.argmax(sims[i]))
        rows.append({"cv": cv_name, "skill": g, "line": lines[k],
                     "sim": float(sims[i][k]), "posting": where[g][0],
                     "n_postings": len(where[g])})

rows.sort(key=lambda r: -r["sim"])
print("\n%d distinct missing skills across %d CVs\n" % (len(rows), len(G)))

print("how close the best CV line is, for the skills the words miss")
edges = [0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.6, 0.5, 0.0]
for a, b in zip(edges, edges[1:]):
    n = sum(1 for r in rows if b <= r["sim"] < a)
    print("  %.2f - %.2f   %5d  %s" % (b, a, n, "#" * int(60 * n / max(1, len(rows)))))

print("\nthe 25 closest pairs - read these, they decide everything")
for r in rows[:25]:
    print("  %.3f  %-34s  %s" % (r["sim"], r["skill"][:34], r["line"][:62]))

print("\nwhat it would add, per posting")
print("  CV      gaps/posting   >=0.80   >=0.85   >=0.90")
tot = collections.Counter(); hit = collections.defaultdict(collections.Counter)
for cv_name, d in G.items():
    njobs = len(d["jobs"]) or 1
    tot[cv_name] = sum(len(j["gaps"]) for j in d["jobs"]) / njobs
    for r in rows:
        if r["cv"] != cv_name: continue
        for t in (0.80, 0.85, 0.90):
            if r["sim"] >= t: hit[cv_name][t] += r["n_postings"] / njobs
for cv_name in G:
    print("  %-8s %10.1f %8.2f %8.2f %8.2f" % (cv_name, tot[cv_name],
          hit[cv_name][0.80], hit[cv_name][0.85], hit[cv_name][0.90]))
n = len(G) or 1
print("  %-8s %10.1f %8.2f %8.2f %8.2f" % ("all", sum(tot.values()) / n,
      sum(hit[c][0.80] for c in G) / n, sum(hit[c][0.85] for c in G) / n,
      sum(hit[c][0.90] for c in G) / n))

print("""
Read it like this. The question is not whether the numbers are high - e5 scores everything higher
than the stand-in did, because that is how it is trained. The question is whether the pairs we WANT
sit above the pairs we do not. Look at the 25 closest: if a job title on the CV ("Supply Chain
Coordinator") is still scoring above a real piece of evidence, one cut-off cannot separate them and
the answer is the same as before, whatever the numbers say.""")

if outf:
    import csv
    with open(outf, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cv", "skill the posting asks for", "closest line on the CV", "how close",
                    "posting", "YOUR LABEL: same / related / not the same"])
        for r in rows:
            w.writerow([r["cv"], r["skill"], r["line"], "%.3f" % r["sim"], r["posting"], ""])
    print("\n%d pairs written to %s" % (len(rows), outf))
