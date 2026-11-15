# After 6 — matching by meaning (I-14), and the vocabulary report (I-19)

The matching here is the same as After 5. Nothing about the score changed. This folder exists to
record what the last phase found, because the answer was "do not ship it yet", and that answer is
worth as much as a change would have been.

## I-14 — could we match a skill to a different wording?

The idea: a posting asks for "WMS"; the CV says "warehouse management system". Same thing, different
words, and today it counts as a gap. A meaning model would catch it.

It was tested on the real gaps, not on examples chosen to make it look good: the skills actually
missing from the top 20 postings for each of the four test CVs — 1,336 distinct skills, 494 / 509 /
568 / 425 per CV.

What a model could be used here. `multilingual-e5-small` could not be downloaded in this sandbox
(huggingface.co and the CDNs are blocked here; in production it would load in the applicant's own
browser, so this is a limit of the test bench, not of the plan). The substitute was trained on our
own corpus instead: 16,513 documents (15,613 posting texts, 900 occupation descriptions), TF-IDF
over 120,000 terms reduced to 300 dimensions. That is a weaker model than e5, so the numbers below
are a floor, not a verdict on e5.

What it gained, per posting, as the cut-off tightens:

| CV | gaps per posting | gain at 0.50 | at 0.60 | at 0.70 |
|---|---|---|---|---|
| CV1 | 24.7 | 5.00 | 1.50 | 0.55 |
| CV2 | 25.4 | 1.75 | 0.45 | 0.00 |
| CV3 | 28.4 | 1.60 | 0.55 | 0.30 |
| CV4 | 21.2 | 1.55 | 0.60 | 0.30 |
| all | 24.9 | 2.48 | **0.78** | 0.29 |

At 0.60 — the loosest cut-off that is defensible — a posting missing 25 skills gains 0.78 half
credits. Less than one.

And the mistakes are not below the catches, they are above them:

- "WMS" ≈ "Supply Chain Coordinator" — 0.793
- "Supply chain planning" ≈ "Supply Chain Coordinator" — 0.926

while the matches we actually want sit at 0.70–0.78. A job title on the CV is close, in this model,
to every skill of that job, which is exactly the I-04 mistake the earlier phases removed: being
called a coordinator is not evidence of any particular skill. One threshold cannot separate those
two groups, so there is no setting of this model that is both safe and worth having.

80% of the 1,336 missing skills had nothing on the CV even topically close (below 0.40). Only 39 —
3% — had a line at 0.60 or better. The gaps are mostly not paraphrases. They are skills the person
does not have, or words we do not know. Which leads to the next part.

`tools/meaning_pairs_to_label.csv` holds all 1,336 pairs with their closeness, for a person to label
same / related / not the same. That is the evidence any later attempt should be judged against, and
`multilingual-e5-small` should be tried somewhere that can reach it before I-14 is closed for good.

## I-19 — the words we do not know

`tools/unknown_report.js` reads every posting and every occupation profile, and lists the phrases
employers ask for that `skills.json` has no entry for. Three filters keep it readable: a single
common noun is not a skill, words about education are already read by the education part of the
score, and a phrase that every trade asks for is advert language ("track record", "core values",
"cutting edge") rather than a skill. What survives: 1,441 phrases asked for by at least five
postings and concentrated in a few kinds of job.

The top of that queue is not spread evenly. Of the first 300:

| share | kind of job |
|---|---|
| 14% | management and sales |
| 14% | food service |
| 10% | truck driving |
| 5% | health and care |
| 5% | **engineering and software** |
| 4% | trades and warehouse |
| 49% | other |

Engineering and software is 5%. That is the field all four test CVs sit in, and it is the field the
dictionary already covers — which is why the test CVs match well and why this gap was invisible until
now. The missing vocabulary belongs to the trades: `Record cargo information`, `transport hazardous
products`, `Obtain special permits`, `log books`, `long-combination vehicle`, `emergency roadside
repairs` (truck driving); `plan menus`, `order supplies`, `determine size` (cooking); `Frequent
lifting`, `Continuous standing`, `personal hygiene` (physical demands, asked by hundreds of postings
and unknown to us).

So an applicant from the trades is matched on a thinner dictionary than an engineering applicant is.
That is the real finding of this phase, and it is a bigger effect than the meaning model would have
been.

Nothing is added automatically. `tools/unknown_skills_queue.csv` is the review sheet — phrase, how
many postings asked, how many kinds of job, one example posting, and a column to mark *add as skill /
already covered / not a skill*. Approved rows go into `skills.json`, the same arrangement as the
credentials map: the machine proposes, a person signs.
