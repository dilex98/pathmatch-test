"""label_sentences.py - the teacher step: Gemini writes the answer key our own model will learn from.

IN PLAIN WORDS
    We give Gemini a sentence from a public job posting, for example
        "Request supplier quotes to build project cost estimates."
    and a short list of skills from our dictionary that might fit. Gemini answers:
        skills:      Procurement ("supplier quotes"), Cost estimation ("cost estimates")
        credentials: (none)        education: (none)
        cv:          "Requested supplier quotes to build project cost estimates."
    Thousands of such answers are the study material. Our own small model learns from them
    (tools/train_reader.py, next step), and then reads CVs by itself, in the browser.

WHAT IS SENT: public job-posting sentences only, with e-mails, links and phone numbers already
removed (tools/build_pool.cjs). Never a CV.

WHAT IS KEPT: an answer is checked before it is kept.
    - a skill must be one of the names on that sentence's list (no invented skill names);
    - every skill, credential and degree must quote words that really are in the sentence;
    - anything else is dropped and counted, so the quality of the teacher can be measured.

RESUMABLE: the answers are appended to labels.jsonl. A sentence already answered is never sent
again. When Google's free daily allowance runs out, the run stops cleanly and the next run carries on.

Usage:
    python3 tools/label_sentences.py --pool pool.jsonl --site gaps-after --out labels \
        [--limit 500] [--batch 20] [--pairs infer-after/skill_pairs.json] [--dry]
    Key: the environment variable GEMINI_LABEL_KEY (a GitHub secret). --dry sends nothing.
"""
import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

API = "https://generativelanguage.googleapis.com/v1beta"
N_CANDIDATES = 30


def fold(s):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


# ------------------------------------------------------------------ the shortlist per sentence
class Shortlist:
    """Up to 30 skills that might fit a sentence: the ones the dictionary already finds, their usual
    partners (Part 2), and the dictionary skills whose names and spellings look most like the
    sentence (character pieces, so 'quotes' still meets 'quotation'). Gemini picks only from these."""

    def __init__(self, dictionary, pairs=None):
        from sklearn.feature_extraction.text import TfidfVectorizer
        never = set(dictionary.get("general", [])) | set(dictionary.get("soft", []))
        self.skills = [s for s in dictionary["skills"] if s["n"] not in never]
        self.names = [s["n"] for s in self.skills]
        docs = [s["n"] + " " + " ".join(s.get("a", [])[:40]) for s in self.skills]
        self.vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1, sublinear_tf=True,
                                   preprocessor=fold)
        self.m = self.vec.fit_transform(docs)
        self.pairs = (pairs or {}).get("rules", {})

    def __call__(self, text, found):
        out = [n for n in found if n in self.names]
        for n in found:
            for b in self.pairs.get(n, [])[:4]:
                if b[0] not in out:
                    out.append(b[0])
        sims = (self.m @ self.vec.transform([text]).T).toarray().ravel()
        for i in sims.argsort()[::-1]:
            if len(out) >= N_CANDIDATES:
                break
            if self.names[i] not in out:
                out.append(self.names[i])
        return out[:N_CANDIDATES]


# ------------------------------------------------------------------ the question to Gemini
RULES = """You label sentences from public Canadian job postings (English or French) for a job-matching tool.
For each sentence, list what it says a worker does or must have, in three kinds:
- "skills": abilities or know-how used at work. Prefer names from that sentence's "candidates" list, spelled exactly
  as listed. Include a skill when the sentence clearly shows it, even if its name is not written (for example
  "request supplier quotes" shows Procurement). If a skill the sentence clearly shows is missing from the list, you
  may give its usual name; it is kept only if our dictionary knows it. Do not include a skill that is only loosely
  related, and do not include general traits (communication, teamwork, motivation).
- "credentials": a certificate, licence, permit, card or professional designation the sentence names, as written.
- "education": a degree, diploma or field of study the sentence names, as written.
For EVERY item give "quote": the exact words from the sentence that prove it (copy them exactly, 1 to 8 words).
Also give "cv": the same work rewritten as one CV bullet line, in the past tense, in the same language as the
sentence, with no company name. If the sentence is not about work tasks or requirements (pay, benefits, how to
apply, company description), give "cv": "" and empty lists.
Answer with JSON only: {"items":[{"id":"...","skills":[{"n":"...","quote":"..."}],"credentials":[{"n":"...","quote":"..."}],
"education":[{"n":"...","quote":"..."}],"cv":"..."}]} with one item per sentence, same ids."""


def build_prompt(batch):
    lines = [RULES, "", "Sentences:"]
    for x in batch:
        lines.append(json.dumps({"id": x["id"], "sentence": x["text"], "candidates": x["cands"]}, ensure_ascii=False))
    return "\n".join(lines)


# ------------------------------------------------------------------ checking an answer
def dictionary_lookup(dictionary):
    """Every name and spelling the dictionary knows -> the skill's name (to accept a skill named off the list)."""
    never = set(dictionary.get("general", [])) | set(dictionary.get("soft", []))
    look = {}
    for s in dictionary["skills"]:
        if s["n"] in never:
            continue
        for a in [s["n"]] + list(s.get("a", [])):
            look.setdefault(fold(a), s["n"])
    return look


def check(x, ans, lookup=None):
    """Keep only what can be verified against the sentence, the shortlist and the dictionary."""
    t = " " + fold(x["text"]) + " "
    kept = {"skills": [], "credentials": [], "education": []}
    dropped = []
    for kind in kept:
        for it in (ans.get(kind) or []):
            if not isinstance(it, dict):
                dropped.append([kind, str(it), "not an object"]); continue
            n, q = str(it.get("n", "")).strip(), str(it.get("quote", "")).strip()
            if not n or not q:
                dropped.append([kind, n, "no name or no quote"]); continue
            if fold(q) == "" or (" " + fold(q) + " ") not in t:
                dropped.append([kind, n, "quote not in the sentence"]); continue
            if kind == "skills" and n not in x["cands"]:
                known = (lookup or {}).get(fold(n))
                if not known:
                    dropped.append([kind, n, "not a dictionary skill"]); continue
                n = known                       # named off the list, but a skill (or spelling) the dictionary knows
            if any(k["n"] == n for k in kept[kind]):
                continue
            kept[kind].append({"n": n, "quote": q})
    cv = str(ans.get("cv") or "").strip()
    if re.search(r"@|https?://|www\.", cv):
        cv = ""
    return kept, dropped, cv[:400]


# ------------------------------------------------------------------ talking to Gemini
class Quota(Exception):
    pass


def call(key, model, prompt):
    body = json.dumps({"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                       "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}}).encode()
    req = urllib.request.Request(f"{API}/models/{model}:generateContent", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode())
    text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
    usage = data.get("usageMetadata", {})
    return json.loads(text), usage


def models(key):
    req = urllib.request.Request(f"{API}/models?pageSize=200", headers={"x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=60) as r:
        names = [m["name"].split("/", 1)[1] for m in json.loads(r.read().decode())["models"]
                 if "generateContent" in m.get("supportedGenerationMethods", [])]
    ranked = []
    for pat in (r"flash-lite", r"flash", r"pro"):
        for n in names:
            if re.search(pat, n) and not re.search(r"preview|exp|tts|image|audio|live|thinking", n) and n not in ranked:
                ranked.append(n)
    return ranked[:4] or names[:1]


def ask(key, model_list, prompt, log):
    """One batch. Busy (503/500) -> wait and retry, then the next model. Per-minute limit (429) -> wait a
    minute, up to 3 times. A model's daily allowance used up -> that model is set aside for this run and
    the next one takes over (each model has its own allowance); all used up -> Quota, which ends the run cleanly."""
    for model in list(model_list):
        for attempt in range(4):
            try:
                return model, *call(key, model, prompt)
            except urllib.error.HTTPError as e:
                msg = e.read().decode(errors="replace")[:600]
                if e.code == 429:
                    if re.search(r"per ?day|PerDay|daily", msg, re.I):
                        log(f"  {model}: daily allowance used up")
                        model_list.remove(model)
                        break
                    log(f"  per-minute limit on {model}, waiting 65 s")
                    time.sleep(65)
                    continue
                if e.code in (500, 503):
                    log(f"  {model} busy ({e.code}), waiting {10 * (attempt + 1)} s")
                    time.sleep(10 * (attempt + 1))
                    continue
                raise RuntimeError(f"{model}: HTTP {e.code} {msg}")
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                log(f"  unreadable answer from {model} ({e.__class__.__name__}), retrying")
                time.sleep(5)
        else:
            log(f"  giving up on {model}, trying the next model")
    if not model_list:
        raise Quota("every model's daily allowance is used up")
    raise RuntimeError("every model failed on this batch")


# ------------------------------------------------------------------ the run
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True)
    ap.add_argument("--site", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pairs")
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--batch", type=int, default=20)
    ap.add_argument("--pause", type=float, default=5.0, help="seconds between requests (free tier: a few per minute)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args(argv)

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    labels_path, progress_path = out / "labels.jsonl", out / "progress.json"
    done = set()
    if labels_path.exists():
        for line in labels_path.open(encoding="utf-8"):
            if line.strip():
                done.add(json.loads(line)["id"])

    pool = [json.loads(l) for l in open(a.pool, encoding="utf-8") if l.strip()]
    # a fixed shuffle, so every run walks the pool in the same order and simply carries on
    pool.sort(key=lambda x: hashlib.sha1((str(a.seed) + x["id"]).encode()).hexdigest())
    todo = [x for x in pool if x["id"] not in done][: a.limit]
    print(f"pool {len(pool)} sentences; already labelled {len(done)}; this run: {len(todo)}")
    if not todo:
        return 0

    dictionary = json.loads((Path(a.site) / "skills.json").read_text(encoding="utf-8"))
    pairs = json.loads(Path(a.pairs).read_text(encoding="utf-8")) if a.pairs and Path(a.pairs).exists() else None
    short = Shortlist(dictionary, pairs)
    lookup = dictionary_lookup(dictionary)
    for x in todo:
        x["cands"] = short(x["text"], x.get("dict", []))

    if a.dry:
        print(build_prompt(todo[: min(3, len(todo))])[:4000])
        print(f"\n(dry run: nothing sent; {len(todo)} sentences would go in {-(-len(todo) // a.batch)} requests)")
        return 0

    key = os.environ.get("GEMINI_LABEL_KEY", "").strip()
    if not key:
        print("GEMINI_LABEL_KEY is not set"); return 2
    model_list = models(key)
    print("models, cheapest first:", ", ".join(model_list))

    prog = json.loads(progress_path.read_text()) if progress_path.exists() else {}
    stats = {k: prog.get(k, 0) for k in ("sentences", "requests", "tokens_in", "tokens_out", "skills_kept",
                                          "skills_dropped", "credentials", "education", "with_cv", "empty")}
    reasons = prog.get("dropped_why", {})
    stop = "done"
    t0 = time.time()
    with labels_path.open("a", encoding="utf-8") as fo:
        for i in range(0, len(todo), a.batch):
            batch = todo[i:i + a.batch]
            try:
                model, ans, usage = ask(key, model_list, build_prompt(batch), print)
            except Quota as e:
                stop = "daily allowance used up: the next run carries on"
                print("  " + stop); break
            except RuntimeError as e:
                stop = f"stopped on an error: {e}"
                print("  " + stop); break
            stats["requests"] += 1
            stats["tokens_in"] += usage.get("promptTokenCount", 0)
            stats["tokens_out"] += usage.get("candidatesTokenCount", 0)
            by_id = {str(it.get("id")): it for it in (ans.get("items") or []) if isinstance(it, dict)}
            for x in batch:
                it = by_id.get(x["id"])
                if it is None:
                    continue                      # not answered: stays to do, sent again next run
                kept, dropped, cv = check(x, it, lookup)
                rec = {"id": x["id"], "text": x["text"], "lang": x["lang"], "tag": x["tag"], "emp": x["emp"],
                       "dict": x.get("dict", []), "cands": x["cands"], **kept, "cv": cv, "dropped": dropped,
                       "model": model, "at": time.strftime("%Y-%m-%d")}
                fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
                stats["sentences"] += 1
                stats["skills_kept"] += len(kept["skills"])
                stats["credentials"] += len(kept["credentials"])
                stats["education"] += len(kept["education"])
                stats["with_cv"] += bool(cv)
                stats["empty"] += not (kept["skills"] or kept["credentials"] or kept["education"])
                for d in dropped:
                    stats["skills_dropped"] += d[0] == "skills"
                    reasons[d[2]] = reasons.get(d[2], 0) + 1
            fo.flush()
            print(f"  {min(i + a.batch, len(todo))}/{len(todo)} sentences ({model})")
            time.sleep(a.pause)
    stats["dropped_why"] = reasons
    stats["last_run"] = {"date": time.strftime("%Y-%m-%d %H:%M"), "stopped": stop, "minutes": round((time.time() - t0) / 60, 1)}
    progress_path.write_text(json.dumps(stats, indent=1, ensure_ascii=False))
    print(json.dumps(stats, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
