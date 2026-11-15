/* apply_skill_fixes.js - apply skill_fixes.json to a copy of skills.json.
 * Run: node tools/apply_skill_fixes.js after-3
 * It prints every change, so a person can check it. It never guesses: a spelling it is told to
 * drop must exist, or it says so and stops.
 */
const fs = require("fs"), path = require("path");
const dir = process.argv[2] || "after-3";
const sp = path.join(dir, "skills.json"), fp = path.join(dir, "skill_fixes.json");
const d = JSON.parse(fs.readFileSync(sp, "utf8")), F = JSON.parse(fs.readFileSync(fp, "utf8"));
const fold = (s) => String(s).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").trim();
const by = {}; for (const s of d.skills) by[s.n] = s;
let dropped = 0, added = 0, miss = [];
for (const f of F.fix) {
  const s = by[f.skill];
  if (!s) { miss.push("no such skill: " + f.skill); continue; }
  for (const a of f.drop || []) {
    const i = s.a.indexOf(fold(a));
    if (i < 0) { miss.push(f.skill + ": nothing to drop for \"" + a + "\""); continue; }
    s.a.splice(i, 1); dropped++;
    console.log("  drop  " + f.skill.padEnd(32) + " ✕ " + a);
  }
  for (const a of f.add || []) {
    const v = fold(a);
    if (s.a.includes(v)) continue;
    s.a.push(v); added++;
    console.log("  add   " + f.skill.padEnd(32) + " + " + a);
  }
}
for (const n of F.new || []) {
  if (by[n.n]) { miss.push("already exists: " + n.n); continue; }
  d.skills.push({ n: n.n, a: n.a.map(fold), s: n.s || "curated" });
  console.log("  NEW   " + n.n + "  (" + n.a.length + " spellings)");
}
if (miss.length) { console.error("\nnot applied:\n - " + miss.join("\n - ")); process.exit(1); }
if (F.falseFriends && F.falseFriends.words) {
  d.terms = d.terms || {};
  d.terms.falseFriends = F.falseFriends.words.map(fold).sort();
  console.log("  terms  " + d.terms.falseFriends.length + " look-alike words that never match on their own (I-20)");
}
d.meta.skills = d.skills.length;
d.meta.aliases = d.skills.reduce((t, s) => t + s.a.length, 0);
d.meta.fixes = F.version;
fs.writeFileSync(sp, JSON.stringify(d, null, 0).replace(/\n/g, ""));
console.log("\n" + dropped + " spellings dropped, " + added + " added, " + (F.new || []).length + " new skills. " +
  d.meta.skills + " skills, " + d.meta.aliases + " spellings.");
