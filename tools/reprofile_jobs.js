/* reprofile_jobs.js - read the employer postings again: their keywords, the degree they ask for,
 * and any licence they call mandatory.
 *
 * The 20,507 postings we hold in full carry a keyword list worked out when they were collected, with
 * the dictionary as it was: a supplier quality role was still asking for "Healthcare and clinical".
 * Their text is not in jobs.json (it is fetched per posting from d/*.json when a card is opened), so
 * the page cannot read a degree or a mandatory licence out of it while it scores. Both are worked out
 * here, once, and written onto the posting:
 *    kw  the keywords, read again with the current dictionary
 *    ea  the degree asked for, 0 to 6 (0 = the posting does not say)
 *    mh  the licences and certificates the posting calls mandatory
 *
 * Run: node tools/reprofile_jobs.js after-4
 */
const fs = require("fs"), path = require("path");
const dir = process.argv[2] || "after-4";
const M = require(path.join(__dirname, "..", dir, "matcher.js"));
const JM = require(path.join(__dirname, "..", dir, "jobmeta.js"));
const eng = M.engine(JSON.parse(fs.readFileSync(path.join(dir, "skills.json"), "utf8")));
const jp = path.join(dir, "jobs.json");
const J = JSON.parse(fs.readFileSync(jp, "utf8"));
const arr = J.jobs || J;

/* every posting's text, from the shards the page fetches */
const TEXT = {};
const dd = path.join(dir, "d");
for (const f of fs.readdirSync(dd)) {
  const o = JSON.parse(fs.readFileSync(path.join(dd, f), "utf8"));
  for (const id in o) TEXT[id] = o[id];
}
console.log(Object.keys(TEXT).length + " posting texts found.");

let n = 0, noText = 0, changed = 0, edu = 0, must = 0, before = 0, after = 0;
const gone = {};
for (const j of arr) {
  n++;
  const t = TEXT[j.id];
  if (!t) { noText++; continue; }
  const kw = eng.profile(j.title || "", t, 40).kw;
  const old = j.kw || [];
  before += old.length; after += kw.length;
  if (JSON.stringify(old) !== JSON.stringify(kw)) {
    changed++;
    for (const c of old) if (kw.indexOf(c) < 0) gone[c.slice(3)] = (gone[c.slice(3)] || 0) + 1;
  }
  j.kw = kw;
  const ea = JM.eduAsked(j.title + "\n" + t);
  if (ea) { j.ea = ea; edu++; } else delete j.ea;
  const mh = JM.mustHaves(t);
  if (mh.length) { j.mh = mh; must++; } else delete j.mh;
}
fs.writeFileSync(jp, JSON.stringify(J));
console.log(n + " postings, " + noText + " without text, " + changed + " whose keywords changed.");
console.log("keywords per posting: " + (before / Math.max(1, n - noText)).toFixed(1) + " before, " + (after / Math.max(1, n - noText)).toFixed(1) + " after.");
console.log("a degree was read in " + edu + " postings; a mandatory licence in " + must + ".");
console.log("most often dropped: " + Object.entries(gone).sort((a, b) => b[1] - a[1]).slice(0, 10)
  .map((x) => x[0] + " (" + x[1] + ")").join(" | "));
