/* infer.test.js - Part 2 of the inference engine: skills that usually go with yours.
 * Run: node tests/infer.test.js [folder]        (default folder: infer-after; no browser needed)
 *
 * Checks that:
 *   1. the website (infer.js) and the Python builder (tools/skill_pairs.py) make exactly the same guesses;
 *   2. a guess is never a skill already on the CV, a general skill, a credential or a language;
 *   3. a ticked suggestion, written under Profile extras, is read back by the matcher as that very skill;
 *   4. the rules file is sane: thresholds hold for every rule, nothing points to itself.
 */
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const dir = path.join(__dirname, "..", process.argv[2] || "infer-after");
const Infer = require(path.join(dir, "infer.js"));
const M = require(path.join(dir, "matcher.js"));
const dict = JSON.parse(fs.readFileSync(path.join(dir, "skills.json"), "utf8"));
const eng = M.engine(dict);
const pairs = JSON.parse(fs.readFileSync(path.join(dir, "skill_pairs.json"), "utf8"));

let pass = 0, fail = 0;
function ok(what, cond, got) {
  if (cond) { pass++; console.log("  ok   " + what); }
  else { fail++; console.log("  FAIL " + what + (got !== undefined ? "   got: " + JSON.stringify(got).slice(0, 300) : "")); }
}

console.log("1. The website and the Python builder agree");
/* random CVs made of skills that have rules, plus a few that do not: same seed on both sides */
const sources = Object.keys(pairs.rules);
const allNames = dict.skills.map((s) => s.n);
let seed = 12345;
const rnd = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);
const cvs = [];
for (let i = 0; i < 3000; i++) {
  const k = 2 + Math.floor(rnd() * 25), s = new Set();
  while (s.size < k) s.add(rnd() < 0.7 ? sources[Math.floor(rnd() * sources.length)] : allNames[Math.floor(rnd() * allNames.length)]);
  cvs.push([...s]);
}
const tmp = path.join(require("os").tmpdir(), "infer_cvs_" + process.pid + ".json");
fs.writeFileSync(tmp, JSON.stringify(cvs));
const py = JSON.parse(execFileSync("python3", ["-I", "-c",
  "import json,sys; sys.path.insert(0, sys.argv[1]); import skill_pairs as sp; " +
  "r=json.load(open(sys.argv[2],encoding='utf-8'))['rules']; cvs=json.load(open(sys.argv[3])); " +
  "print(json.dumps([sp.infer(c, r) for c in cvs]))",
  path.join(__dirname, "..", "tools"), path.join(dir, "skill_pairs.json"), tmp], { encoding: "utf8", maxBuffer: 64e6 }));
fs.unlinkSync(tmp);
const js = cvs.map((c) => Infer.suggest(c, pairs));
let same = 0, firstDiff = null, withGuess = 0;
for (let i = 0; i < cvs.length; i++) {
  if (JSON.stringify(js[i]) === JSON.stringify(py[i])) same++;
  else if (!firstDiff) firstDiff = { cv: cvs[i], js: js[i], py: py[i] };
  if (js[i].length) withGuess++;
}
ok(`same guesses on ${cvs.length} random CVs (${same} identical)`, same === cvs.length, firstDiff);
ok(`the random CVs do get guesses (${withGuess} of ${cvs.length})`, withGuess > 50, withGuess);

console.log("2. What is never guessed");
const never = new Set(pairs.never_suggested);
let bad = [];
for (let i = 0; i < cvs.length; i++) for (const g of js[i]) {
  if (cvs[i].includes(g.n)) bad.push(["already on the CV", g.n]);
  if (never.has(g.n)) bad.push(["never suggested", g.n]);
  if (/certif|licen[cs]|permit|red seal|certificate/i.test(g.n)) bad.push(["credential", g.n]);
  if (g.p < pairs.thresholds.show_min_p - 1e-9) bad.push(["too weak", g.n, g.p]);
}
ok("no guess is on the CV already, general, a credential, a language or too weak", bad.length === 0, bad.slice(0, 5));
ok("at most show_max guesses", js.every((g) => g.length <= pairs.thresholds.show_max));
for (const n of ["Communication", "Teamwork", "English", "French", "Leadership"]) ok(`"${n}" is in the never-suggested list`, never.has(n) || !allNames.includes(n));
ok("an empty CV gets no guess", Infer.suggest([], pairs).length === 0);
ok("a skill the person turned down is not asked again", (() => {
  const c = cvs.find((x, i) => js[i].length), first = Infer.suggest(c, pairs)[0].n;
  return !Infer.suggest(c, pairs, { skip: [first] }).some((g) => g.n === first);
})());
/* every guess explains itself with skills that are really on the CV */
ok("every guess names its reasons, all from the CV", js.every((g, i) => g.every((x) => x.because.length && x.because.every((b) => cvs[i].includes(b)))));

console.log("3. A ticked suggestion is read back as that skill");
/* the site writes a ticked skill under a SKILLS heading after the CV, the same as a Profile extra */
const targets = [...new Set(Object.values(pairs.rules).flat().map((r) => r[0]))];
const readsBack = (n) => Object.prototype.hasOwnProperty.call(eng.findCv("SKILLS\n" + n), n);   /* the site's readsBack() */
const lost = targets.filter((n) => !readsBack(n));
console.log(`     (${lost.length} of ${targets.length} are group names nobody writes, e.g. ${lost.slice(0, 3).join("; ")}: never asked)`);
ok("most skills that can be suggested are read back by their name", lost.length < targets.length * 0.25, lost.length);
const asked = cvs.map((c) => Infer.suggest(c, pairs, { readable: readsBack }));
ok("with the site's filter, every suggestion is read back as itself when ticked", asked.every((g) => g.every((x) => readsBack(x.n))));
ok("a ticked skill is read in a real CV, after the person's own SKILLS section", (() => {
  const n = targets.find(readsBack);
  const cv = "Jane Doe\nMontreal\n\nEXPERIENCE\nWelder, Acme, 2020 - 2024\n- Welded frames\n\nSKILLS\nMIG welding\n\nSKILLS\n" + n;
  return Object.keys(eng.findCv(cv)).includes(n);
})());

console.log("4. The rules file");
const th = pairs.thresholds;
const off = [];
for (const [a, list] of Object.entries(pairs.rules)) {
  if (list.length > th.top_per_skill) off.push([a, "too many"]);
  for (const [b, conf, lift, n] of list) {
    if (a === b) off.push([a, "points to itself"]);
    if (conf < th.min_conf - 1e-9 || lift < th.min_lift - 1e-9 || n < th.min_pair) off.push([a, b, conf, lift, n]);
    if (!allNames.includes(b) || !allNames.includes(a)) off.push([a, b, "not a dictionary skill"]);
  }
}
ok("every rule passes its thresholds and names dictionary skills", off.length === 0, off.slice(0, 5));
ok(`built from ${pairs.postings_used} distinct postings (at least 5,000)`, pairs.postings_used >= 5000);
ok("the evaluation is stored with the rules", !!pairs.evaluation && pairs.evaluation.precision > pairs.evaluation.popular_precision, pairs.evaluation);

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
