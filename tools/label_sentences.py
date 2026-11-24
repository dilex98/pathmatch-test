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
# Government labels that sit in the dictionary but are not skills a CV states: abilities ("General Learning
# Ability"), work activities ("Establishing and Maintaining Interpersonal Relationships"), knowledge areas and
# personal attributes. The trial showed the teacher picking them for vague sentences; they are never offered.
NOT_TEACHABLE = {"OaSIS abilities", "OaSIS work_activities", "OaSIS knowledge", "OaSIS personal_attributes"}


def teachable(dictionary):
    never = set(dictionary.get("general", [])) | set(dictionary.get("soft", []))
    return [s for s in dictionary["skills"] if s["n"] not in never and s.get("s") not in NOT_TEACHABLE]


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
        self.skills = teachable(dictionary)
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
  related, and do not include general traits (communication, teamwork, motivation). Be strict:
  * only a skill the worker USES or MUST HAVE in this job, not a word that merely appears;
  * not a word used in another sense ("réseaux" of people is not computer networking; "infrastructures" of a
    fraud scheme is not IT infrastructure);
  * not a skill named only in a job title or team name ("Manager, Business Finance" alone is not financial analysis);
  * not a product or platform name, unless that name is in the list.
  When unsure, leave it out: a missing skill costs less than a wrong one.
- "credentials": a certificate, licence, permit, card or professional designation the sentence names, as written.
- "education": a degree, diploma or field of study the sentence names, as written.
For EVERY item give "quote": the exact words from the sentence that prove it (copy them exactly, 1 to 8 words).
Also give "cv": the same work rewritten as one CV bullet line, in the past tense, in the same language as the
sentence (an English sentence gets an English line, a French sentence a French line), with no company name.
Only when the sentence is in French: start with a past participle and no subject ("Identifié les…", not
"A identifié les…"). If the sentence is not about work tasks or requirements (pay, benefits, how to
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
    look = {}
    for s in teachable(dictionary):
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
                       "generationConfig": {"temperature": 0, "responseMimeType": "application/json",
                                            "maxOutputTokens": 8192}}).encode()
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


class Unreadable(RuntimeError):
    """Every attempt came back, but not as readable JSON: the batch itself is the trouble, not Google."""


def ask(key, model_list, prompt, log):
    """One batch. Busy (503/500) -> wait and retry, then the next model. Per-minute limit (429) -> wait a
    minute, up to 3 times. A model's daily allowance used up -> that model is set aside for this run and
    the next one takes over (each model has its own allowance); all used up -> Quota, which ends the run cleanly."""
    only_unreadable = True                     # did every failure come back as an unreadable answer?
    for model in list(model_list):
        for attempt in range(4):
            try:
                return model, *call(key, model, prompt)
            except urllib.error.HTTPError as e:
                only_unreadable = False
                msg = e.read().decode(errors="replace")[:600]
                if e.code == 429:
                    if re.search(r"per ?day|PerDay|daily", msg, re.I):
                        log(f"  {model}: daily allowance used up")
                        model_list.remove(model)
                        break
                    log(f"  per-minute limit on {model}, waiting 65 s")
                    time.sleep(65)
                    continue
                if e.code == 404:                    # retired or not open to this project: the next model takes over
                    log(f"  {model} not available ({msg[:120]}), using the next model")
                    model_list.remove(model)
                    break
                if e.code in (500, 503):
                    wait = 15 * 2 ** attempt               # 15, 30, 60, 120 s: Google's busy spells last minutes
                    log(f"  {model} busy ({e.code}), waiting {wait} s")
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"{model}: HTTP {e.code} {msg}")
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                log(f"  unreadable answer from {model} ({e.__class__.__name__}), retrying")
                time.sleep(5)
        else:
            log(f"  giving up on {model}, trying the next model")
    if not model_list:
        raise Quota("every model's daily allowance is used up")
    if only_unreadable:
        raise Unreadable("the answers to this batch could not be read")
    raise RuntimeError("every model failed on this batch")


# ------------------------------------------------------------------ which sentences this run labels
def new_skills(rec):
    return {s["n"] for s in rec.get("skills", [])} - set(rec.get("dict", []))


def select_todo(pool, done, limit, total=0, disagree=None):
    """The pool is in a fixed order, so every run and every model walks the same sentences.
    total: only the first N sentences of that order. disagree: only the sentences two earlier label files
    both answered but disagree on (the skills beyond the dictionary), for a deciding third vote."""
    if total:
        pool = pool[:total]
    if disagree:
        def load(p):
            return {r["id"]: r for r in map(json.loads, open(p, encoding="utf-8"))} if Path(p).exists() else {}
        A, B = load(disagree[0]), load(disagree[1])
        pool = [x for x in pool if x["id"] in A and x["id"] in B and new_skills(A[x["id"]]) != new_skills(B[x["id"]])]
    return [x for x in pool if x["id"] not in done][:limit]


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
    ap.add_argument("--model", default="", help="use this model first (a second opinion: label the same sentences with another model)")
    ap.add_argument("--only-model", action="store_true", help="never fall back to another model (keeps each vote independent)")
    ap.add_argument("--total", type=int, default=0, help="label only the first N sentences of the fixed order (0 = all)")
    ap.add_argument("--only-disagree", nargs=2, metavar=("A", "B"),
                    help="third vote: only sentences that labels files A and B both answered but disagree on")
    a = ap.parse_args(argv)

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    labels_path, progress_path = out / "labels.jsonl", out / "progress.json"
    done = set()
    if labels_path.exists():
        for line in labels_path.open(encoding="utf-8"):
            if line.strip():
                done.add(json.loads(line)["id"])
    skipped_path = out / "skipped.jsonl"            # single sentences whose answer could never be read
    if skipped_path.exists():
        for line in skipped_path.open(encoding="utf-8"):
            if line.strip():
                done.add(json.loads(line)["id"])

    pool = [json.loads(l) for l in open(a.pool, encoding="utf-8") if l.strip()]
    # a fixed shuffle, so every run walks the pool in the same order and simply carries on
    pool.sort(key=lambda x: hashlib.sha1((str(a.seed) + x["id"]).encode()).hexdigest())
    todo = select_todo(pool, done, a.limit, a.total, a.only_disagree)
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
    if a.model:
        model_list = [a.model] if a.only_model else [a.model] + [m for m in model_list if m != a.model]
    print("models, cheapest first:", ", ".join(model_list))

    prog = json.loads(progress_path.read_text()) if progress_path.exists() else {}
    stats = {k: prog.get(k, 0) for k in ("sentences", "requests", "tokens_in", "tokens_out", "skills_kept",
                                          "skills_dropped", "credentials", "education", "with_cv", "empty")}
    reasons = prog.get("dropped_why", {})
    stop = None
    t0 = time.time()
    try:
        stop = run_batches(a, todo, key, model_list, labels_path, lookup, stats, reasons)
    finally:
        stats["dropped_why"] = reasons
        stats["last_run"] = {"date": time.strftime("%Y-%m-%d %H:%M"), "stopped": stop if isinstance(stop, str) else "crashed",
                             "minutes": round((time.time() - t0) / 60, 1)}
        progress_path.write_text(json.dumps(stats, indent=1, ensure_ascii=False))
        print(json.dumps(stats, indent=1, ensure_ascii=False))
    return 0


def run_batches(a, todo, key, model_list, labels_path, lookup, stats, reasons):
    stop = "done"
    # A batch whose answer cannot be read (Nov 24: one batch of 20 broke vote 2 fifteen times) is split in two
    # and each half asked again, down to single sentences; a single sentence that still fails is set aside in
    # skipped.jsonl, so it is never asked again and never stops the run.
    queue = [todo[i:i + a.batch] for i in range(0, len(todo), a.batch)]
    handled = 0
    skipped_path = labels_path.parent / "skipped.jsonl"
    with labels_path.open("a", encoding="utf-8") as fo:
        while queue:
            batch = queue.pop(0)
            # Google's servers are sometimes overloaded (503) for a while. One busy spell must not end the day's run
            # (on Nov 23 it did, after two minutes, with the whole daily allowance unused): rest 5 minutes and try
            # the same batch again, up to 3 times, before stopping until the next run.
            answer, err = None, None
            for rest in range(4):
                try:
                    answer = ask(key, model_list, build_prompt(batch), print)
                    break
                except Quota:
                    err = "quota"; break
                except Unreadable:
                    err = "unreadable"; break
                except RuntimeError as e:
                    err = e
                    if rest < 3:
                        print(f"  still busy; resting 5 minutes before trying this batch again ({rest + 1}/3)")
                        time.sleep(300)
                except Exception as e:         # anything unexpected in one batch: skip it, its sentences stay to do
                    err = "skip"
                    print(f"  batch skipped ({e.__class__.__name__}: {str(e)[:200]})"); break
            if err == "quota":
                stop = "daily allowance used up: the next run carries on"
                print("  " + stop); break
            if err == "skip":
                continue
            if err == "unreadable":
                if len(batch) > 1:
                    half = len(batch) // 2
                    print(f"  unreadable answers for {len(batch)} sentences: asking in two halves")
                    queue[:0] = [batch[:half], batch[half:]]
                else:
                    with skipped_path.open("a", encoding="utf-8") as fs:
                        fs.write(json.dumps({"id": batch[0]["id"], "text": batch[0]["text"], "why": "answer never readable",
                                             "at": time.strftime("%Y-%m-%d")}, ensure_ascii=False) + "\n")
                    stats["skipped"] = stats.get("skipped", 0) + 1
                    handled += 1
                    print("  one sentence set aside: its answer could never be read")
                continue
            if answer is None:
                stop = f"stopped on an error: {err}"
                print("  " + stop); break
            model, ans, usage = answer
            stats["requests"] += 1
            stats["tokens_in"] += usage.get("promptTokenCount", 0)
            stats["tokens_out"] += usage.get("candidatesTokenCount", 0)
            # the agreed shape is {"items": [...]}; Gemini sometimes answers the bare list, which is fine too
            items = ans.get("items") if isinstance(ans, dict) else ans if isinstance(ans, list) else []
            by_id = {str(it.get("id")): it for it in (items or []) if isinstance(it, dict)}
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
            handled += len(batch)
            print(f"  {handled}/{len(todo)} sentences ({model})")
            time.sleep(a.pause)
    return stop


if __name__ == "__main__":
    sys.exit(main())
