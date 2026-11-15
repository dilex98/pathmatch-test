"""meaning_build.py - build a meaning model out of the postings we already hold.

I-14 asks whether matching by meaning finds skills the words miss. Before changing the site, the
question has to be answered with numbers, and for that we need vectors for phrases.

This builds them from the corpus itself: every posting we hold in full, plus the official
occupation descriptions. No model is downloaded, nothing leaves the machine, and the vocabulary is
exactly the one the job market uses - in both languages, because many Canadian postings carry their
English and French text in the same document, which is what ties the two together.

    tf-idf over the corpus -> truncated SVD (latent semantic analysis) -> a vector per term
    a phrase is the idf-weighted mean of its terms

Run: python3 tools/meaning_build.py after-6
"""
import json, os, re, sys, pickle
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize

site = sys.argv[1] if len(sys.argv) > 1 else "after-6"
out = os.path.join("tools", "meaning.pkl")

docs = []
dd = os.path.join(site, "d")
for f in sorted(os.listdir(dd)):
    with open(os.path.join(dd, f), encoding="utf-8") as fh:
        for _id, t in json.load(fh).items():
            if t and len(t) > 120:
                docs.append(t)
print(f"{len(docs)} posting texts")

lib = json.load(open(os.path.join(site, "noc", "noc_library.lite.json"), encoding="utf-8"))
for p in lib["profiles"].values():
    bits = []
    for lg in ("en", "fr"):
        if p.get("lead", {}).get(lg):
            bits.append(p["lead"][lg])
        for d in p.get("duties", []):
            bits.append(d.get(lg, "") if isinstance(d, dict) else str(d))
    t = "\n".join(x for x in bits if x)
    if len(t) > 120:
        docs.append(t)
print(f"{len(docs)} documents in all (postings + occupation descriptions)")

vec = TfidfVectorizer(lowercase=True, strip_accents="unicode", ngram_range=(1, 2),
                      min_df=5, max_df=0.4, max_features=120000, sublinear_tf=True)
X = vec.fit_transform(docs)
print(f"{X.shape[0]} documents x {X.shape[1]} terms")

svd = TruncatedSVD(n_components=300, random_state=0)
svd.fit(X)
print(f"300 dimensions keep {svd.explained_variance_ratio_.sum()*100:.1f}% of the variation")

# a term's vector is its row of the term-topic matrix
terms = vec.get_feature_names_out()
T = normalize(svd.components_.T)          # terms x 300
idf = vec.idf_
with open(out, "wb") as fh:
    pickle.dump({"terms": list(terms), "T": T.astype(np.float32), "idf": idf.astype(np.float32),
                 "ngram": 2}, fh, protocol=4)
print(f"written to {out}: {len(terms)} terms")
