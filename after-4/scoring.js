/* scoring.js - the 0-100 match score, in one place so the page and the tests use the same rules.
 *
 *   score = Skills (0-70) + Education (0-20) + Credentials (0-10)
 *
 * What counts is what the person can do, what they studied and what they are certified for. The job
 * title gives no points: it only says which field a posting belongs to. The level gives no points
 * either: it decides whether a posting belongs in the list at all (see the stage filter on the page).
 * A posting that asks for no degree, or for no certificate, is scored out of the parts it does ask
 * for, so nobody loses points for something that was never wanted.
 *
 * It is a heuristic, not an applicant tracking system: scores that differ by 5 points or less are ties.
 * Language, work permit, security and term are shown as flags next to the score and never change it.
 * A mandatory licence the CV does not have is a red flag and takes the posting out of the top 10; it
 * is handled on the page, not here, because it is a yes/no gate and not a number.
 *
 * rows: the posting's keywords against the CV, [{n, kind: "s"|"t", tag: "T"|"R"|"K"|"N"|"P", st: "M"|"R"|"G"}]
 *   M = the same words are on the CV, R = close but not the same (half credit, never shown as a match), G = not on the CV.
 *   tag: T title, R required, K task, N not tagged, P preferred.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.Scoring = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const CAP = { skills: 70, education: 20, credentials: 10 };
  /* a posting whose skills are covered this far earns the full 70 (full coverage is not realistic) */
  const SKILL_FULL = 0.75;
  /* a posting with only a few keywords has not shown much: count a few absent keywords too, so 2 of 3 does not read as 67% */
  const PRIOR = 4;
  const TAGW = { T: 0, R: 1, K: 0.7, N: 0.7, P: 0.4 };
  const credit = (st) => (st === "M" ? 1 : st === "R" ? 0.5 : 0);

  const plain = (s) => String(s).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").trim();
  /* language is a flag beside the score (see the page), never part of it */
  const LANGUAGE = new Set(["bilingual (en/fr)", "bilingual", "bilingue", "english", "french", "anglais", "francais"]);

  /* how much a keyword counts: a dictionary skill counts fully; a phrase of several words a little less;
     a single ordinary word little. A word from the title counts nothing at all. */
  function weight(x) {
    const t = TAGW[x.tag] != null ? TAGW[x.tag] : 0.7;
    if (!t) return 0;
    if (x.cred) return 0;                       /* a certificate is scored in its own part, not twice */
    if (LANGUAGE.has(plain(x.n))) return 0;
    /* a skill nearly every posting asks for and nearly every CV has says little about this job */
    if (x.general) return t * 0.35;
    if (x.kind === "s") return t;
    return t * (/[\s-]/.test(String(x.n).trim()) ? 0.8 : 0.35);
  }

  /* Skills: how much of what the posting asks for is on the CV, weighted. */
  function skills(rows) {
    let w = 0, c = 0, matched = 0, close = 0, asked = 0;
    for (const x of rows) {
      const k = weight(x);
      if (k > 0) {
        asked++;
        if (x.st === "M") matched++; else if (x.st === "R") close++;
      }
      w += k; c += k * credit(x.st);
    }
    const cov = w ? c / (w + PRIOR) : 0;
    const pts = w ? Math.round(CAP.skills * Math.min(1, cov / SKILL_FULL)) : 0;
    return { pts, cov, matched, close, asked, n: rows.length, weighted: w };
  }

  /* Education, 0 to 6: none, high school, college/CEGEP/trade, bachelor, master, doctorate.
     Same level or higher in a related field is full marks. The same level in another field still
     shows the person can study at that level, so it keeps most of the points. One level short keeps
     half. Two levels short is a real gap. A degree in progress counts: the person will have it. */
  function education(asked, have, related) {
    if (!asked) return { pts: 0, asked: false };
    const gap = (have || 0) - asked;
    let share;
    if (gap >= 0) share = related === false ? 0.7 : 1;
    else if (gap === -1) share = related === false ? 0.35 : 0.5;
    else share = 0;
    return { pts: Math.round(CAP.education * share), asked: true, gap, share };
  }

  /* Credentials: the certificates and licences the posting names (rows marked cred), and how many
     of them are on the CV. A close match counts half, as everywhere else. */
  function credentials(rows) {
    const want = (rows || []).filter((x) => x.cred);
    if (!want.length) return { pts: 0, asked: false };
    let c = 0;
    for (const x of want) c += credit(x.st);
    const share = c / want.length;
    return { pts: Math.round(CAP.credentials * share), asked: true, got: want.filter((x) => x.st === "M").length, want: want.length, share };
  }

  /* The total is out of the parts the posting actually asks for. A posting that names no degree and
     no certificate is scored on its skills alone, out of 100. */
  function compute(rows, parts) {
    parts = parts || {};
    const s = skills(rows || []);
    const e = education(parts.eduAsked, parts.eduHave, parts.eduRelated);
    const c = credentials(rows || []);
    const available = CAP.skills + (e.asked ? CAP.education : 0) + (c.asked ? CAP.credentials : 0);
    const earned = s.pts + e.pts + c.pts;
    const total = available ? Math.round((100 * earned) / available) : 0;
    return {
      skills: s.pts, education: e.pts, credentials: c.pts,
      total: Math.max(0, Math.min(100, total)),
      cov: s.cov, matched: s.matched, close: s.close, asked: s.asked, n: s.n,
      eduAsked: e.asked, eduGap: e.gap, credAsked: c.asked, credGot: c.got, credWant: c.want,
      available: available
    };
  }

  return { CAP, SKILL_FULL, PRIOR, weight, skills, education, credentials, compute };
});
