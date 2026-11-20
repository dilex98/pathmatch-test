/* infer.js - Part 2 of the inference engine: "skills that usually go with yours".
 *
 * skill_pairs.json (built by tools/skill_pairs.py from the postings) holds rules such as
 *   Welding -> [Assembly, 0.40, 19.5, 28]   = 40% of the postings asking for Welding also ask for Assembly,
 *                                             19.5 times more often than chance, in 28 postings.
 * Here, the skills read on the CV are the evidence. Every skill on the CV with a rule towards B is one piece;
 * the pieces are combined as "at least one of them is right":  p = 1 - (1 - c1)(1 - c2)...
 * A skill is suggested when p reaches show_min_p, strongest first, at most show_max of them.
 *
 * A suggestion is only a question to the person. It counts in the score after they tick it, and then it is
 * written under Profile extras as "a skill you confirmed", exactly like an item they typed themselves.
 * This is the same calculation as infer() in tools/skill_pairs.py; tests/infer.test.js checks they agree.
 * Nothing leaves the browser: the rules are a public file, the CV is read here.
 * opt: max, minP (default: the file's thresholds), skip (names not to ask again), readable(name) (see below).
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.Infer = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function suggest(cvSkills, pairs, opt) {
    opt = opt || {};
    const th = (pairs && pairs.thresholds) || {};
    const max = opt.max != null ? opt.max : th.show_max != null ? th.show_max : 8;
    const minP = opt.minP != null ? opt.minP : th.show_min_p != null ? th.show_min_p : 0.6;
    const rules = (pairs && pairs.rules) || {};
    const never = new Set((pairs && pairs.never_suggested) || []);
    const skip = new Set(opt.skip || []);           /* skills the person already turned down, or already added */
    const have = new Set(cvSkills || []);
    const ev = new Map();
    for (const a of [...have].sort()) {
      for (const [b, conf] of rules[a] || []) {
        if (have.has(b) || never.has(b)) continue;
        if (!ev.has(b)) ev.set(b, []);
        ev.get(b).push([conf, a]);
      }
    }
    const out = [];
    for (const [b, pieces] of ev) {
      if (skip.has(b)) continue;
      /* the site asks only about a skill it can read back when ticked: written by its name, the matcher must find that
         very skill ("Design and creative tools" is a group name nobody writes, so it is never asked) */
      if (opt.readable && !opt.readable(b)) continue;
      let miss = 1;
      for (const [c] of pieces) miss *= 1 - c;
      const p = 1 - miss;
      if (p + 1e-9 < minP) continue;
      pieces.sort((x, y) => y[0] - x[0] || (x[1] < y[1] ? -1 : x[1] > y[1] ? 1 : 0));
      out.push({ n: b, p: Math.round(p * 1000) / 1000, because: pieces.slice(0, 3).map((x) => x[1]) });
    }
    out.sort((x, y) => y.p - x.p || (x.n < y.n ? -1 : x.n > y.n ? 1 : 0));
    return out.slice(0, max);
  }

  return { suggest };
});
