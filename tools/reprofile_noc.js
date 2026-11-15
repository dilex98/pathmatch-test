/* reprofile_noc.js - read the occupation keyword lists again with the current dictionary.
 *
 * The Job Bank occupations carry their keywords worked out in advance (jobs/noc/index.json). They
 * were written with the dictionary as it was, so after phase 3 they still asked for skills that
 * dictionary no longer finds ("Media production management" for a production coordinator). This
 * reads the official descriptions again (noc/noc_library.lite.json: lead, duties, requirements) and
 * writes the lists back.
 *
 * Run: node tools/reprofile_noc.js after-4
 */
const fs = require("fs"), path = require("path");
const dir = process.argv[2] || "after-4";
const M = require(path.join(__dirname, "..", dir, "matcher.js"));
const eng = M.engine(JSON.parse(fs.readFileSync(path.join(dir, "skills.json"), "utf8")));
const lib = JSON.parse(fs.readFileSync(path.join(dir, "noc", "noc_library.lite.json"), "utf8"));
const ip = path.join(dir, "jobs", "noc", "index.json");
const idx = JSON.parse(fs.readFileSync(ip, "utf8"));

/* every profile of one occupation, joined: the lead sentence, the duties and the requirements */
const byNoc = {};
for (const key in lib.profiles) {
  const p = lib.profiles[key];
  const n = String(p.noc || "").slice(0, 5);
  if (!n) continue;
  (byNoc[n] = byNoc[n] || []).push(p);
}
const textOf = (ps, lg) => {
  const out = [];
  for (const p of ps) {
    if (p.lead && p.lead[lg]) out.push(p.lead[lg]);
    for (const d of p.duties || []) out.push(typeof d === "string" ? d : (d[lg] || ""));
    /* requirements is one object: the written sentence says what the employer wants */
    const rq = p.requirements || {};
    for (const k in rq) {
      const v = rq[k];
      if (!v || typeof v !== "object") continue;
      const t = v["source_" + lg] || v[lg];
      if (typeof t === "string") out.push(t);
    }
    /* the OaSIS skill ratings are left out on purpose: they are the same general abilities
       ("Oral Communication", "Reading Comprehension") for almost every occupation, so they say
       nothing about one job and would crowd out the real duties. */
  }
  return out.filter(Boolean).join("\n");
};

let done = 0, missing = 0, changed = 0, before = 0, after = 0;
for (const code in idx.nocs) {
  const o = idx.nocs[code], ps = byNoc[String(code).slice(0, 5)];
  if (!ps || !ps.length) { missing++; continue; }
  const name = (ps[0].name && (ps[0].name.en || ps[0].name.fr)) || o.en || "";
  const nameFr = (ps[0].name && ps[0].name.fr) || o.fr || name;
  const en = eng.profile(name, textOf(ps, "en"), 40).kw;
  const fr = eng.profile(nameFr, textOf(ps, "fr"), 40).kw;
  const old = (o.kw && o.kw.en) || [];
  before += old.length; after += en.length;
  if (JSON.stringify(old) !== JSON.stringify(en)) changed++;
  o.kw = { en: en, fr: fr };
  done++;
}
idx.profileV = (idx.profileV || 0) + 1;
fs.writeFileSync(ip, JSON.stringify(idx));
console.log(done + " occupations read again, " + changed + " changed, " + missing + " had no description.");
console.log("keywords per occupation: " + (before / Math.max(1, done)).toFixed(1) + " before, " + (after / Math.max(1, done)).toFixed(1) + " after.");
