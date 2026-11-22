# I-24: Gaps that are not skills

Built on `infer-before/` (the live site of Nov 20, 2026; jobs of Nov 18, 2026). Compare with that folder. Part 2 is not in here,
so each change can be judged on its own.

## The problem (found by Dilex on the live site)

1. **Single words in the posting table.** "data", "locations", "preparation", "tracking", "records", "policies", "assigned"
   showed as **Gap**. Besides dictionary skills, the site keeps loose phrases from the posting; when a phrase is cut down to
   one word, that word became a keyword. In the score each counted a third of a skill: 197,359 of them in 79% of the full
   postings, about 15% of what a typical score was measured against. Most are not skills ("bring", "least", "hands",
   "passion", "e.g", e-mail addresses, French form words). Nearly no CV "has" them, so they lowered almost every score.
2. **Degrees counted twice.** "university degree", "school diploma", "diplôme universitaire" (1,599 phrases) and the
   dictionary's "Engineering degrees", "Business degrees", "Technical college diplomas" were counted as skills to have, on top
   of the education part that already scores them.
3. **"Repairing", "Hearing Sensitivity" in the occupation reading.** For Job Bank postings without an employer text, the
   site compares the CV with the government's occupation profile. It listed OaSIS abilities ("Hearing Sensitivity", "Near
   Vision", "Trunk Strength"), work styles ("Attention to Detail") and knowledge areas ("Knowledge in Logistics") and
   called them **Gap**, though nobody writes those on a CV and this reading is not scored.

## The fixes

| | Before | After |
|---|---|---|
| Loose single word in a posting | counted 0.35 of a skill | **not counted**, listed under "Listed but not counted" |
| Phrase about a degree, and the 3 dictionary degree entries | counted as a skill | **not counted** (the education part scores it) |
| Dictionary skills, phrases of several words | 1 and 0.8 | unchanged |
| Occupation reading | skills, abilities, work styles, knowledge; "Gap" | **OaSIS skills only** (the 33 rated in every profile); "Not on CV", "Not scored" |

The posting table now counts exactly what the score counts (the filler the keyword list already dropped, like "assigned",
was still shown there as a Gap). The weekly skills list still reads single words, so a real one ("SaaS", "JSON", "REST")
can still reach the dictionary; until then it loses its small weight, the one real cost of the change (about 7 frequent
tool words, under 1% of the single words).

## Results: the four test CVs, before and after, in a browser (CVs not in this repo)

| CV | Keywords per posting | Gaps per posting | Average score, all postings | Top 10 kept |
|---|---|---|---|---|
| CV1 | 34.5 -> 24.7 | 28.1 -> 19.7 | 16.2 -> 15.4 | 7 of 10 |
| CV2 | 34.5 -> 24.7 | 28.3 -> 19.5 | 13.8 -> 13.3 | 8 of 10 |
| CV3 | 34.5 -> 24.7 | 31.9 -> 23.0 | 6.9 -> 5.7 | 6 of 10 |
| CV4 | 34.5 -> 24.7 | 27.7 -> 18.9 | 16.0 -> 16.2 | 8 of 10 |

About **30% fewer Gaps**, and **no score inflation**: averages stay level or dip, because the words removed were sometimes
matches too ("equipment", "quality"). The top 10 moves towards postings that ask for real skills the CV has: CV4's first job
is now "Shipping / Logistics Coordinator" (63, 8 gaps) instead of "production coordinator" (61, 21 gaps, 13 of them single
words). No page errors.

## Tests

`node tests/gaps.test.mjs` (40 checks; on `infer-before/` 28 of them fail, which shows the test sees the change). All earlier
suites pass unchanged on this folder: words 87, score 34, stage 31, read 31, creds 35, unknown 11.

## Not changed here

The same job sometimes appears twice in a top 10 ("Refinery Products Blend Scheduler", Shell). It was like that before; a
separate item.
