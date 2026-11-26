/* reader.js - our own skill reader (the "student"), running in the browser.
 *
 * skill_reader.json is made by tools/train_reader.py. For each skill it holds the clues that point to it
 * (words, pairs of words, 4-letter pieces of words) and how much each clue counts. Reading a CV line:
 *   1. the line becomes clues exactly as in Python (pieces() / fold() there; tests/reader.test.js checks it);
 *   2. each clue is weighted by how rare it is, and the line is scaled to length 1;
 *   3. each skill adds up its clues' weights; a skill whose score passes the cut is found.
 * Every skill found comes with the clues that weighed most, so the site can show why.
 * Nothing leaves the browser: the reader is a public file, the CV is read here.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.Reader = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function fold(s) {
    return String(s || "").toLowerCase().normalize("NFD").replace(/\p{Mn}/gu, "").replace(/[^a-z0-9]+/g, " ").trim();
  }

  function pieces(text) {
    const toks = fold(text).split(" ").filter(Boolean);
    const out = new Set();
    for (let i = 0; i < toks.length; i++) {
      const t = toks[i];
      out.add("w:" + t);
      if (i + 1 < toks.length) out.add("b:" + t + "_" + toks[i + 1]);
      if (t.length >= 4) {
        const g = "<" + t + ">";
        for (let j = 0; j + 4 <= g.length; j++) out.add("c:" + g.slice(j, j + 4));
      }
    }
    return out;
  }

  function load(model) {
    const clues = model.clues;                       /* clue -> rarity weight */
    const skills = model.skills;
    /* clue -> [[skill index, weight], ...], so a line only touches the skills its clues point to */
    const index = new Map();
    skills.forEach((s, k) => {
      for (const [c, w] of Object.entries(s.w)) {
        if (!index.has(c)) index.set(c, []);
        index.get(c).push([k, w]);
      }
    });

    function vector(text) {
      const v = new Map();
      let norm = 0;
      for (const p of pieces(text)) {
        const idf = clues[p];
        if (idf === undefined) continue;
        v.set(p, idf);
        norm += idf * idf;
      }
      norm = Math.sqrt(norm);
      if (norm > 0) for (const [p, x] of v) v.set(p, x / norm);
      return v;
    }

    /* scores of every skill for one line (Python's scores()) */
    function scores(text) {
      const v = vector(text);
      const z = skills.map((s) => s.b);
      const why = skills.map(() => []);
      for (const [p, x] of v) {
        for (const [k, w] of index.get(p) || []) {
          z[k] += w * x;
          if (w > 0) why[k].push([w * x, p]);
        }
      }
      return z.map((zz, k) => ({ n: skills[k].n, p: 1 / (1 + Math.exp(-zz)), why: why[k] }));
    }

    /* the skills found in one line, strongest first, each with its readable clues */
    function read(text, cut) {
      const c = cut != null ? cut : model.cut;
      return scores(text)
        .filter((s) => s.p >= c)
        .sort((a, b) => b.p - a.p || (a.n < b.n ? -1 : 1))
        .map((s) => ({
          n: s.n,
          p: Math.round(s.p * 1000) / 1000,
          clues: s.why.sort((a, b) => b[0] - a[0]).map((x) => x[1]).filter((x) => !x.startsWith("c:"))
            .slice(0, 3).map((x) => x.slice(2).replace(/_/g, " ")),
        }));
    }

    return { read, scores, cut: model.cut, size: skills.length, built: model.built, dictionary: model.dictionary };
  }

  return { load, pieces, fold };
});
