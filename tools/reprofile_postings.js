/* reprofile_postings.js - read each Job Bank posting's own keywords again, from its title.
 *
 * Each open-data posting carries a short keyword list worked out from its title (postings.json, "k").
 * Those were written with the dictionary as it was, so a posting called "production coordinator" was
 * still asking for "Media production management" after phase 3 fixed that link. The occupation lists
 * were already rebuilt by reprofile_noc.js; this does the per-posting ones.
 *
 * Run: node tools/reprofile_postings.js after-4
 */
const fs = require("fs"), path = require("path");
const dir = process.argv[2] || "after-4";
const M = require(path.join(__dirname, "..", dir, "matcher.js"));
const eng = M.engine(JSON.parse(fs.readFileSync(path.join(dir, "skills.json"), "utf8")));
const pp = path.join(dir, "jobs", "noc", "postings.json");
const P = JSON.parse(fs.readFileSync(pp, "utf8"));

let n = 0, changed = 0, before = 0, after = 0;
const gone = {};
for (const noc in P) {
  for (const r of P[noc]) {
    n++;
    const old = r.k || [];
    /* the title is all we have for one posting: the occupation's own list is merged in on the page */
    const kw = eng.profile(r.t || "", "", 8).kw;
    before += old.length; after += kw.length;
    if (JSON.stringify(old) !== JSON.stringify(kw)) {
      changed++;
      for (const c of old) if (kw.indexOf(c) < 0) gone[c.slice(3)] = (gone[c.slice(3)] || 0) + 1;
    }
    r.k = kw;
  }
}
fs.writeFileSync(pp, JSON.stringify(P));
console.log(n + " postings read again, " + changed + " changed.");
console.log("keywords per posting: " + (before / n).toFixed(2) + " before, " + (after / n).toFixed(2) + " after.");
console.log("most often dropped: " + Object.entries(gone).sort((a, b) => b[1] - a[1]).slice(0, 12)
  .map((x) => x[0] + " (" + x[1] + ")").join(" | "));
