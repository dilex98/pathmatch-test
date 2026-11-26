"""train_reader.py - trains our own skill reader (the "student") from the teacher's agreed labels.

IN PLAIN WORDS
    Gemini (the teacher) labelled 20,000 public job-posting sentences, three times. A skill counts as a label
    when at least 2 of the 3 votes agree. This script learns, for each skill, which words and word pieces point
    to it: "supplier quotes" -> Procurement. The result, skill_reader.json, is small enough to load in a
    browser; the website then reads CV lines with it, on the person's own device.

HOW
    1. Training examples: each posting sentence with its agreed skills, and the teacher's CV-style rewrite of it
       ("Requested supplier quotes...") with the same skills, so the reader also learns how CVs are worded.
    2. Words become numbers the same way here and in the browser (featurize(); reader.js does exactly the same):
       accents and case removed; single words, pairs of words, and 4-letter pieces of words (so "estimating"
       and "estimation" share pieces). Each piece is weighted by how rare it is (rare pieces say more).
    3. One small yes/no model per skill (logistic regression) for every skill with enough examples.
    4. Honest testing: employers are split 80 / 10 / 10. The reader learns from the first 80%, the cut-off
       ("how sure before saying yes") is set on the next 10%, and the final numbers come from the last 10%,
       sentences from employers it has never seen.
    5. To keep the file small, each skill keeps only its strongest clues; the test uses that small version,
       because that is what the website will run.

No CV is used anywhere here: the CVs are only used later, in the go / no-go test, on this machine.
Usage: python3 tools/train_reader.py --site gaps-after --out reader [--min-examples 15]
"""
import argparse
import hashlib
import json
import math
import re
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.linear_model import LogisticRegression

VOTES = ["labels/labels.jsonl", "labels-second/labels.jsonl", "labels-third/labels.jsonl"]


# ------------------------------------------------------------------ words -> numbers (mirrored in reader.js)
def fold(s):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def pieces(text):
    """The clues in a text: w:word, b:word_word, c:4-letter piece of a word (with < > marking its ends)."""
    toks = fold(text).split()
    out = set()
    for i, t in enumerate(toks):
        out.add("w:" + t)
        if i + 1 < len(toks):
            out.add("b:" + t + "_" + toks[i + 1])
        if len(t) >= 4:
            g = "<" + t + ">"
            for j in range(len(g) - 3):
                out.add("c:" + g[j:j + 4])
    return out


def vectorize(texts, vocab, idf):
    rows, cols, vals = [], [], []
    for r, t in enumerate(texts):
        idx = [vocab[p] for p in pieces(t) if p in vocab]
        if not idx:
            continue
        w = np.array([idf[i] for i in idx])
        w = w / math.sqrt(float((w * w).sum()))
        rows += [r] * len(idx); cols += idx; vals += list(w)
    return csr_matrix((vals, (rows, cols)), shape=(len(texts), len(vocab)), dtype=np.float32)


# ------------------------------------------------------------------ the agreed labels
def agreed(root):
    def load(p):
        p = root / p
        return {x["id"]: x for x in map(json.loads, p.open(encoding="utf-8"))} if p.exists() else {}
    A, B, C = (load(v) for v in VOTES)
    data = []
    for i, a in A.items():
        if i not in B:
            continue
        votes = Counter()
        for V in (A, B, C):
            if i in V:
                votes.update({s["n"] for s in V[i]["skills"]})
        keep = sorted(k for k, v in votes.items() if v >= 2)
        cvs = [x for x in {A[i].get("cv", ""), B[i].get("cv", "")} if x]
        data.append({"id": i, "text": a["text"], "cvs": sorted(cvs), "skills": keep, "dict": a.get("dict", []),
                     "emp": a.get("emp", i), "lang": a.get("lang", "en")})
    return data


def side(emp):
    h = int(hashlib.md5(emp.encode()).hexdigest(), 16) % 10
    return "test" if h == 0 else "valid" if h == 1 else "train"


# ------------------------------------------------------------------ predicting with the small (pruned) reader
def scores(X, W, b):
    return 1 / (1 + np.exp(-(X @ W + b)))


def prf(pred, gold):
    tp = sum(len(p & g) for p, g in zip(pred, gold))
    np_ = sum(len(p) for p in pred); ng = sum(len(g) for g in gold)
    return {"right": tp, "said": np_, "true": ng,
            "precision": round(tp / np_, 3) if np_ else 0.0, "recall": round(tp / ng, 3) if ng else 0.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--site", default="gaps-after")
    ap.add_argument("--out", default="reader")
    ap.add_argument("--min-examples", type=int, default=15)
    ap.add_argument("--min-df", type=int, default=3)
    ap.add_argument("--keep", type=int, default=150, help="strongest clues kept per skill")
    ap.add_argument("--target", type=float, default=0.85, help="precision the cut-off aims for on the validation 10%")
    a = ap.parse_args()
    root, out = Path(a.root), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    data = agreed(root)
    for d in data:
        d["side"] = side(d["emp"])
    train = [d for d in data if d["side"] == "train"]
    valid = [d for d in data if d["side"] == "valid"]
    test = [d for d in data if d["side"] == "test"]
    print(f"sentences: {len(data)} (train {len(train)}, validation {len(valid)}, test {len(test)})")

    # training documents: the sentence and its CV-style rewrites, with the same skills
    docs, labels = [], []
    for d in train:
        for t in [d["text"]] + d["cvs"]:
            docs.append(t); labels.append(set(d["skills"]))
    pos = Counter(s for d in train for s in d["skills"])
    skills = sorted(s for s, n in pos.items() if n >= a.min_examples)
    print(f"skills with {a.min_examples}+ training sentences: {len(skills)} of {len(pos)}")

    df = Counter()
    for t in docs:
        df.update(pieces(t))
    N = len(docs)

    def train_on(vocab_list):
        vocab = {p: i for i, p in enumerate(vocab_list)}
        idf = np.array([math.log((1 + N) / (1 + df[p])) + 1 for p in vocab_list])
        X = vectorize(docs, vocab, idf)
        W = np.zeros((len(vocab), len(skills)), dtype=np.float32)
        bias = np.zeros(len(skills), dtype=np.float32)
        for k, s in enumerate(skills):
            y = np.array([s in L for L in labels], dtype=int)
            m = LogisticRegression(C=4.0, solver="liblinear", max_iter=200)
            m.fit(X, y)
            w = m.coef_.ravel()
            top = np.argsort(-np.abs(w))[: a.keep]
            W[top, k] = w[top]
            bias[k] = m.intercept_[0]
            if (k + 1) % 100 == 0:
                print(f"  trained {k + 1}/{len(skills)} skills ({time.time() - t0:.0f} s)")
        return vocab, idf, W, bias

    # Stage 1: every clue seen 3+ times; each skill keeps its strongest clues.
    full = sorted(p for p, n in df.items() if n >= a.min_df)
    print(f"training documents {N}, clues {len(full)}; stage 1")
    _, _, W1, _ = train_on(full)
    used = sorted({full[i] for i in np.nonzero(W1.any(axis=1))[0]})
    # Stage 2: retrain on those clues only. The browser then needs only this short list (and its weights) to
    # turn a CV line into exactly the same numbers as here.
    print(f"stage 2 on the {len(used)} clues the skills use")
    vocab, idf, W, bias = train_on(used)
    vocab_list = used
    sk_set = set(skills)

    # the cut-off: the lowest score at which the validation sentences reach the target precision
    Xv = vectorize([d["text"] for d in valid], vocab, idf)
    Sv = scores(Xv.toarray(), W, bias)
    gold_v = [set(d["skills"]) & sk_set for d in valid]
    cut, best = 0.9, None
    for c in np.arange(0.30, 0.96, 0.025):
        pred = [{skills[j] for j in np.where(Sv[r] >= c)[0]} for r in range(len(valid))]
        m = prf(pred, gold_v)
        if m["said"] >= 30 and m["precision"] >= a.target:
            cut, best = float(round(c, 3)), m
            break
    print(f"cut-off {cut} (validation: {best})")

    # final test on employers it never saw: the sentences, and their CV-style rewrites
    def evaluate(rows, texts_of):
        texts, gold, dic = [], [], []
        for d in rows:
            for t in texts_of(d):
                texts.append(t); gold.append(set(d["skills"])); dic.append(set(d["dict"]))
        S = scores(vectorize(texts, vocab, idf).toarray(), W, bias)
        model = [{skills[j] for j in np.where(S[r] >= cut)[0]} for r in range(len(texts))]
        res = {"lines": len(texts),
               "model": prf(model, gold),
               "model_on_skills_it_knows": prf(model, [g & sk_set for g in gold])}
        if texts_of is not None:
            res["dictionary"] = prf(dic, gold)
            res["dictionary_plus_model"] = prf([m | d for m, d in zip(model, dic)], gold)
            new_gold = [g - d for g, d in zip(gold, dic)]
            new_pred = [m - d for m, d in zip(model, dic)]
            res["skills_the_dictionary_misses"] = {
                "true": sum(map(len, new_gold)),
                "found_by_model": sum(len(p & g) for p, g in zip(new_pred, new_gold)),
                "model_said_new": sum(map(len, new_pred)),
                "of_which_right": sum(len(p & g) for p, g in zip(new_pred, new_gold))}
            x = res["skills_the_dictionary_misses"]
            x["share_found"] = round(x["found_by_model"] / x["true"], 3) if x["true"] else 0
            x["precision_of_new"] = round(x["of_which_right"] / x["model_said_new"], 3) if x["model_said_new"] else 0
        return res, texts, model

    test_sent, ts, tm = evaluate(test, lambda d: [d["text"]])
    test_cv, cs, cm = evaluate([d for d in test if d["cvs"]], lambda d: d["cvs"][:1])
    # on CV-style lines the dictionary was not run here (it reads posting sentences); judge the model alone
    for k in ("dictionary", "dictionary_plus_model", "skills_the_dictionary_misses"):
        test_cv.pop(k, None)

    # the small reader the website will load: clue -> rarity weight, and per skill its clues and weights
    reader = {
        "_": "Our own skill reader (the student), trained by tools/train_reader.py on the skills 2 of 3 Gemini votes "
             "agreed on, in public job-posting sentences and their CV-style rewrites. Read by reader.js in the browser.",
        "built": time.strftime("%Y-%m-%d"),
        "dictionary": hashlib.sha1((Path(a.site) / "skills.json").read_bytes()).hexdigest()[:12],
        "cut": cut,
        "clues": {p: round(float(idf[i]), 4) for i, p in enumerate(vocab_list)},
        "skills": [{"n": s, "b": round(float(bias[k]), 4),
                    "w": {vocab_list[i]: round(float(W[i, k]), 4) for i in np.nonzero(W[:, k])[0]}}
                   for k, s in enumerate(skills)],
    }
    path = out / "skill_reader.json"
    path.write_text(json.dumps(reader, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    report = {"built": reader["built"], "minutes": round((time.time() - t0) / 60, 1),
              "sentences": {"train": len(train), "validation": len(valid), "test": len(test)},
              "training_documents": N, "skills_learned": len(skills), "skills_in_labels": len(pos),
              "clues": len(vocab), "kept_per_skill": a.keep, "cut": cut, "validation": best,
              "test_posting_sentences": test_sent, "test_cv_style_lines": test_cv,
              "file_kb": path.stat().st_size // 1024}
    (out / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    # a sample to read by hand: CV-style test lines and what the reader found
    sample = [{"line": t, "found": sorted(m)} for t, m in zip(cs, cm) if m][:60]
    (out / "sample_cv_lines.json").write_text(json.dumps(sample, indent=1, ensure_ascii=False))
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
