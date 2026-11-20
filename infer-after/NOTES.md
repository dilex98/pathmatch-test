# Inference engine, Part 2: skills that usually go with yours

Built on `infer-before/` (the live site of Nov 20, 2026; jobs of Nov 18, 2026). Everything else is unchanged.

## What it does

1. **Learning (Python, `tools/skill_pairs.py`).** Reads the 12,207 distinct postings we hold in full (the same job posted many
   times counts once) and learns which skills employers ask for together. A rule is kept only when 15+ postings ask for both
   skills, 30+ ask for the first, at least 30% of the postings asking for the first also ask for the second, and that happens
   at least 3 times more often than chance. Result: 955 rules for 351 skills, in `skill_pairs.json` (43 KB).
2. **Guessing (in the browser, `infer.js`).** The skills read on the CV are the evidence. Each one with a rule towards a
   skill the CV lacks is a piece of evidence; pieces combine as "at least one is right". A skill is asked about when the
   combined chance reaches 60%, at most 8 of them.
3. **Asking.** "How we read your CV" now has a box *Skills that usually go with yours*, with a reason for each ("often asked with
   AutoCAD and Tendering, which are on your CV"). Nothing counts until the person ticks it. A ticked skill is saved in their
   browser as a Profile extra ("Skill you confirmed"), is read by the same matcher as the CV, and shows as "you confirmed".

Never suggested: general skills (Communication, Teamwork...), certificates, licences and permits, languages, degrees, and group
names the matcher would not read back as themselves ("Design and creative tools").

## How well it guesses

Measured on postings the rules never saw (learned on 80%, tested on 20%): hide a third of a posting's skills, guess from the rest.

| | |
|---|---|
| Test postings that got at least one suggestion | 47.5% |
| Suggestions that were one of the hidden skills | **31.5%** |
| The same number of guesses taken from the most common skills | 11.2% |

So a suggestion is about **2.8 times more likely to be right** than a plain popular guess. The test is strict: a posting that
does not name a skill does not mean the person lacks it.

## The four test CVs (run in a browser on this machine; the CVs are not in this repo)

| CV | Skills read | Asked about |
|---|---|---|
| CV1 | 48 | Health and safety, Food safety and hospitality, Manufacturing experience, Python |
| CV2 | 48 | Construction and estimating, Python, Data analysis |
| CV3 | 19 | nothing strong enough |
| CV4 | 42 | nothing strong enough |

Checked: before any tick, every top 10 is identical to `infer-before/`; a tick is saved, counted ("you confirmed"), survives a
redraw, and an untick removes it; the Profile extras page lists it; no errors in the page; the box reads well at phone width.

Looser settings (30% -> 20% share, 3x -> 2x chance) would ask CV3 and CV4 too, but with weak guesses such as "Machine learning
and AI" from "Prototyping" and "Patents". Kept strict on purpose.

## Found on the way

- "Construction and estimating" is a group skill whose spellings include "devis" and "estimator", so it is read in postings far
  from construction (a pharmacometrics director job). A dictionary clean-up item, not a Part 2 issue.
- Part 2 infers from what the CV already says. It cannot see a skill the dictionary does not know: that is Part 1 (reading the
  CV by meaning).

## Tests

`node tests/infer.test.js` (18 checks: the browser and Python agree on 3,000 random CVs; nothing forbidden is suggested; a
ticked skill is read back; every rule meets its thresholds) and `python3 -m unittest tests/test_skill_pairs.py` (7 checks on
small hand-worked data). All earlier suites pass unchanged on this folder: words 87, score 34, stage 31, read 31, creds 35,
unknown 11.

Rebuild the rules: `python3 tools/skill_pairs.py infer-after --eval`
