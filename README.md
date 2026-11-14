# Path Match: frozen test copy

A frozen copy of [Path Match](https://molu221.github.io/Path_Match_V1/) for measuring the matching, before and after each change.
It is **not** the live site and is never updated by the daily job collection.

| Folder | What it is |
|---|---|
| `before/` | Today's matching, frozen. Code from Molu221/Path_Match_V1 at `e4ff8af`, jobs from the Nov 13, 2026 refresh (79,062 postings). |

- The page clock is fixed to **Nov 14, 2026, 12:00 (Montreal)**, so rules based on dates (old postings, internship terms) give the same result every time.
- A bar at the bottom of every page says which version you are looking at.
- CVs are read in the browser and are never uploaded. **Never commit a CV to this repo.**
- Improvements are tested here first (`after-1/`, `after-2/`, ...) on the same jobs, then proposed to the live site by pull request.
