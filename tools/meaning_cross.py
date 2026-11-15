"""meaning_cross.py - I-14, step two: does a cross-encoder do what the embedding could not?

e5 reads the two texts apart and compares summaries. A cross-encoder reads them together, which is
the whole difference. This scores exactly the pairs e5 already picked - the file you just made - so
the two can be compared row for row, on the same pairs, with no re-reading of the CVs.

Two models are tried:
  small        cross-encoder/ms-marco-MiniLM-L-6-v2      ~90 MB, English only
  multilingual cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 ~400 MB, handles the French

Size matters because this would have to download in an applicant's browser. If the small one is
good enough, the feature is cheap. If only the big one works, it may not be worth it.

Needs:  nothing new - the library you already installed has it
Run:    python3 meaning_cross.py e5_pairs.csv cross_pairs.csv

Nothing is uploaded. The models download and run on this machine.
"""
import csv, sys

inf = sys.argv[1]
outf = sys.argv[2] if len(sys.argv) > 2 else "cross_pairs.csv"

try:
    from sentence_transformers import CrossEncoder
except ImportError:
    sys.exit("needs sentence-transformers:  python3 -m pip install -U sentence-transformers")

rows = list(csv.DictReader(open(inf, encoding="utf-8")))
print("%d pairs to judge\n" % len(rows))
pairs = [(r["skill the posting asks for"], r["closest line on the CV"]) for r in rows]

MODELS = [("small", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
          ("multilingual", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")]
scores = {}
for label, name in MODELS:
    print("loading %s (%s) - downloads the first time..." % (label, name))
    try:
        m = CrossEncoder(name, max_length=256)
        scores[label] = m.predict(pairs, batch_size=32, show_progress_bar=True)
        print("  done\n")
    except Exception as e:
        print("  could not run %s: %s\n" % (label, e))

if not scores:
    sys.exit("neither model ran - send me the error above")

for label in scores:
    s = scores[label]
    order = sorted(range(len(rows)), key=lambda i: -s[i])
    print("\n=== %s: the 30 it is most sure about ===" % label)
    for i in order[:30]:
        print("  %7.2f | %-34s | %s" % (s[i], rows[i]["skill the posting asks for"][:34],
                                        rows[i]["closest line on the CV"][:64]))
    print("\n=== %s: the 10 it is most sure are NOT the same ===" % label)
    for i in order[-10:]:
        print("  %7.2f | %-34s | %s" % (s[i], rows[i]["skill the posting asks for"][:34],
                                        rows[i]["closest line on the CV"][:64]))

with open(outf, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    cols = list(scores)
    w.writerow(["cv", "skill the posting asks for", "closest line on the CV", "e5 score"] +
               [c + " cross-encoder score" for c in cols] + ["posting"])
    for i, r in enumerate(rows):
        w.writerow([r["cv"], r["skill the posting asks for"], r["closest line on the CV"],
                    r["how close"]] + ["%.3f" % float(scores[c][i]) for c in cols] + [r["posting"]])
print("\nwritten to %s - send me this file and everything printed above." % outf)
print("""
What this decides: e5 put job titles and section headings ABOVE real evidence. If the cross-encoder
puts the real evidence on top instead, the feature is worth building. If it makes the same mistakes,
I-14 is finished and we spend the time on the dictionary instead.""")
