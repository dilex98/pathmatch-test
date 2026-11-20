"""skill_pairs.py - Part 2 of the inference engine: learn which skills go together in real job postings.

WHAT IT DOES, IN PLAIN WORDS
    Like "people who bought this also bought that", but for skills. It reads every job posting we
    collected in full and counts, for each pair of skills, how often employers ask for both. From
    that it writes rules such as:

        Procurement -> Supplier management   (asked together in 41% of postings that ask for Procurement,
                                              3.9 times more often than chance)

    The website reads those rules. When a CV shows Procurement, the site asks the person:
    "People with Procurement usually also have Supplier management. Do you?" Nothing is added
    without a tick from the person.

HOW A RULE IS KEPT (all four must hold)
    - support:    at least MIN_PAIR postings ask for both skills
    - base:       at least MIN_BASE postings ask for the first skill (so the rule rests on enough cases)
    - confidence: of the postings asking for A, at least MIN_CONF also ask for B
    - lift:       B is asked with A at least MIN_LIFT times more often than B is asked overall,
                  so a skill every posting wants (Communication) cannot ride along with everything

WHAT IS LEFT OUT ON PURPOSE
    - general skills (Communication, Teamwork, the 38 the site already counts a little): they say little
    - certificates, licences and permits: a credential is never guessed, it must be on the CV
    - languages (English, French): read from the CV and the posting, never guessed
    - postings we only know by their title (no full text, so no real skill list)
    - the same job posted many times (same employer and title): counted once, or one big employer
      posting the same advert 200 times would decide the rules

USAGE
    python3 tools/skill_pairs.py <site folder>            writes <site folder>/skill_pairs.json
    python3 tools/skill_pairs.py <site folder> --eval     also measures how well the rules guess (see evaluate())

Standard library only. The CVs are never read here: the rules come from public job postings only.
"""
import hashlib
import json
import math
import random
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

MIN_PAIR = 15      # postings that ask for both skills
MIN_BASE = 30      # postings that ask for the first skill
MIN_CONF = 0.30    # P(B | A)
MIN_LIFT = 3.0     # P(B | A) / P(B)
TOP_PER_SKILL = 12 # rules kept per skill, the strongest first

# what the website shows (the same numbers are in infer.js; test/infer checks they agree)
SHOW_MAX = 8       # suggestions shown at most
SHOW_MIN_P = 0.60  # a suggestion is shown only when the combined evidence reaches this

CREDENTIAL = re.compile(r"certif|licen[cs]|permit|red seal|certificate", re.I)
LANGUAGE = re.compile(r"^(english|french|bilingual \(en/fr\)|languages|other languages)$", re.I)
EDUCATION = re.compile(r"\bdegrees?\b|\bdiplomas?\b|bachelor|master'?s degree|doctora", re.I)


def fold(s):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def excluded_skills(dictionary):
    """The skills that are never learned or suggested: general ones, credentials, languages."""
    out = set(dictionary.get("general", [])) | set(dictionary.get("soft", []))
    out |= {x["n"] for x in (dictionary.get("general_learned") or {}).get("skills", [])}
    for s in dictionary["skills"]:
        if CREDENTIAL.search(s["n"]) or LANGUAGE.match(s["n"]) or EDUCATION.search(s["n"]):
            out.add(s["n"])
    return out


def posting_skill_sets(jobs, names, skip):
    """One skill set per distinct job. kw entries look like "Ks|Project management": tag, kind, name.
    Kind "s" is a dictionary skill; kind "t" is a free term and is not used."""
    seen, sets = set(), []
    for j in jobs:
        if j.get("partial") or not j.get("kw"):
            continue
        key = fold(j.get("company")) + "|" + fold(j.get("title"))
        if key in seen:
            continue
        seen.add(key)
        skills = {k.split("|", 1)[1] for k in j["kw"] if len(k) > 3 and k[1] == "s"}
        skills = {s for s in skills if s in names and s not in skip}
        if len(skills) >= 2:
            sets.append((key, skills))
    return sets


def learn(sets):
    """Count skills and pairs, then keep the rules that pass the four tests."""
    n = len(sets)
    one, two = Counter(), Counter()
    for _, s in sets:
        one.update(s)
        ss = sorted(s)
        for i, a in enumerate(ss):
            for b in ss[i + 1:]:
                two[(a, b)] += 1
    rules = defaultdict(list)
    for (a, b), nab in two.items():
        if nab < MIN_PAIR:
            continue
        for x, y in ((a, b), (b, a)):
            if one[x] < MIN_BASE:
                continue
            conf = nab / one[x]
            lift = conf / (one[y] / n)
            if conf >= MIN_CONF and lift >= MIN_LIFT:
                rules[x].append([y, round(conf, 3), round(lift, 1), nab])
    for x in rules:
        rules[x].sort(key=lambda r: (-r[1], -r[2], r[0]))
        del rules[x][TOP_PER_SKILL:]
    return dict(sorted(rules.items())), one, n


def infer(cv_skills, rules, show_max=SHOW_MAX, min_p=SHOW_MIN_P):
    """The guess the website makes (infer.js does exactly this; the test checks it).
    Each skill on the CV that has a rule towards B is a piece of evidence; the pieces are combined
    as "at least one of them is right": p = 1 - (1 - c1)(1 - c2)... Shown: p >= min_p, strongest first."""
    have = set(cv_skills)
    ev = defaultdict(list)
    for a in sorted(have):
        for b, conf, lift, nab in rules.get(a, []):
            if b not in have:
                ev[b].append((conf, a))
    out = []
    for b, pieces in ev.items():
        p = 1 - math.prod(1 - c for c, _ in pieces)
        if p + 1e-9 >= min_p:
            pieces.sort(key=lambda t: (-t[0], t[1]))
            # rounded half up, like Math.round in infer.js (Python's round() rounds halves to even)
            out.append({"n": b, "p": math.floor(p * 1000 + 0.5) / 1000, "because": [a for _, a in pieces[:3]]})
    out.sort(key=lambda x: (-x["p"], x["n"]))
    return out[:show_max]


def evaluate(sets, seed=7):
    """Does a guess turn out right? Measured on postings the rules never saw.
    1. Split the jobs 80/20 by a hash of employer and title (the same job never sits on both sides).
    2. Learn the rules on the 80%.
    3. For each test job with 6+ skills, hide a third of its skills and give the rest to infer().
    4. A shown suggestion is right when it is one of the hidden skills.
    Compared with a plain guess that needs no learning: the most common skills, as many as infer() showed."""
    test, train = [], []
    for key, s in sets:
        (test if int(hashlib.md5(key.encode()).hexdigest(), 16) % 5 == 0 else train).append((key, s))
    rules, one, _ = learn(train)
    popular = [s for s, _ in one.most_common()]
    rnd = random.Random(seed)
    rows = []
    for _, s in test:
        if len(s) < 6:
            continue
        ss = sorted(s)
        rnd.shuffle(ss)
        k = max(2, len(ss) // 3)
        hidden, shown_to = set(ss[:k]), set(ss[k:])
        guess = [g["n"] for g in infer(shown_to, rules)]
        pop = [p for p in popular if p not in shown_to][:len(guess)]
        rows.append((len(guess), sum(g in hidden for g in guess), sum(p in hidden for p in pop), len(hidden)))
    jobs = len(rows)
    with_guess = sum(1 for r in rows if r[0])
    shown = sum(r[0] for r in rows)
    right = sum(r[1] for r in rows)
    pop_right = sum(r[2] for r in rows)
    return {
        "train_jobs": len(train), "test_jobs": jobs,
        "jobs_with_a_suggestion": with_guess, "share_with_a_suggestion": round(with_guess / jobs, 3) if jobs else 0,
        "suggestions_shown": shown, "suggestions_right": right,
        "precision": round(right / shown, 3) if shown else 0,
        "popular_guess_right": pop_right,
        "popular_precision": round(pop_right / shown, 3) if shown else 0,
        "hidden_found": round(right / sum(r[3] for r in rows), 3) if rows else 0,
    }


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip().split("\n\n")[0]); print("usage: python3 tools/skill_pairs.py <site folder> [--eval]"); return 2
    site = Path(argv[1])
    dictionary = json.loads((site / "skills.json").read_text(encoding="utf-8"))
    jobs = json.loads((site / "jobs.json").read_text(encoding="utf-8"))
    names = {s["n"] for s in dictionary["skills"]}
    skip = excluded_skills(dictionary)
    sets = posting_skill_sets(jobs["jobs"], names, skip)
    rules, one, n = learn(sets)
    out = {
        "_": "Skills that go together in real job postings: A -> [B, share of A postings that also ask for B, "
             "times more often than chance, postings asking for both]. Built by tools/skill_pairs.py; read by infer.js. "
             "Used only to ASK the person; a suggestion counts only after they tick it.",
        "built": date.today().isoformat(),
        "jobs_as_of": jobs.get("updatedAt", ""),
        "postings_used": n,
        "thresholds": {"min_pair": MIN_PAIR, "min_base": MIN_BASE, "min_conf": MIN_CONF, "min_lift": MIN_LIFT,
                       "top_per_skill": TOP_PER_SKILL, "show_max": SHOW_MAX, "show_min_p": SHOW_MIN_P},
        "never_suggested": sorted(skip),
        "rules": rules,
    }
    if "--eval" in argv:
        out["evaluation"] = evaluate(sets)
    path = site / "skill_pairs.json"
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{n} distinct jobs with a full skill list; {len(one)} skills seen; "
          f"{len(rules)} skills with rules, {sum(len(v) for v in rules.values())} rules; "
          f"{path} ({path.stat().st_size // 1024} KB)")
    if "evaluation" in out:
        print("evaluation:", json.dumps(out["evaluation"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
