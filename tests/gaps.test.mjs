/* gaps.test.mjs - I-24: Gaps that are not skills.
 * Run: node tests/gaps.test.mjs [folder]      (default folder: gaps-after; no browser needed)
 *
 * 1. A loose single word cut out of a sentence ("data", "tracking") counts nothing in the score.
 * 2. A phrase about a degree counts nothing as a skill: the education part scores it.
 * 3. Real skills are untouched: dictionary skills, phrases of several words.
 * 4. The occupation reading lists OaSIS skills only (no "Hearing Sensitivity"), and does not say "Gap".
 */
import fs from "fs";
import path from "path";
import { createRequire } from "module";
import { fileURLToPath } from "url";
const require = createRequire(import.meta.url);
const here = path.dirname(fileURLToPath(import.meta.url));
const dir = path.join(here, "..", process.argv[2] || "gaps-after");
const S = require(path.join(dir, "scoring.js"));
const M = require(path.join(dir, "matcher.js"));
const eng = M.engine(JSON.parse(fs.readFileSync(path.join(dir, "skills.json"), "utf8")));
const noc = await import(path.join(dir, "noc", "noc_library.js"));
const lib = JSON.parse(fs.readFileSync(path.join(dir, "noc", "noc_library.lite.json"), "utf8"));
const page = fs.readFileSync(path.join(dir, "index.html"), "utf8");

let pass = 0, fail = 0;
const ok = (what, cond, got) => { if (cond) { pass++; console.log("  ok   " + what); } else { fail++; console.log("  FAIL " + what + (got !== undefined ? "   got: " + JSON.stringify(got) : "")); } };
const w = (n, kind = "t", tag = "R") => S.weight({ n, kind, tag });

console.log("1. Loose single words count nothing");
for (const n of ["data", "tracking", "records", "policies", "locations", "preparation", "passion", "bring", "Technician", "SaaS"])
  ok(`"${n}" weighs 0`, w(n) === 0, w(n));
ok("a row of only single words gives no Gap in the count", S.counts([{ n: "data", kind: "t", tag: "R", st: "G" }, { n: "tracking", kind: "t", tag: "K", st: "G" }]).gap === 0);

console.log("2. Degrees are scored under Education, not as skills");
for (const n of ["university degree", "bachelor's degree in engineering", "Diplôme universitaire", "school diploma", "DEC en génie", "PhD degree", "masters degree"])
  ok(`"${n}" weighs 0`, w(n) === 0, w(n));
for (const n of ["Engineering degrees", "Business degrees", "Technical college diplomas"]) ok(`dictionary entry "${n}" weighs 0`, w(n, "s") === 0, w(n, "s"));

console.log("3. Real skills are untouched");
for (const [n, k, want] of [["Project management", "s", 1], ["Python", "s", 1], ["Diplomacy and tact", "s", 1], ["quality control", "t", 0.8],
  ["master data management", "t", 0.8], ["360 degree feedback", "t", 0.8], ["heavy-duty", "t", 0.8], ["calibration tracking", "t", 0.8]])
  ok(`"${n}" (${k === "s" ? "skill" : "phrase"}) weighs ${want}`, Math.abs(w(n, k) - want) < 1e-9, w(n, k));
ok("a title word still counts nothing, as before", w("quality control", "t", "T") === 0);
ok("the general-skill discount is unchanged", Math.abs(S.weight({ n: "Communication", kind: "s", tag: "R", general: true }) - 0.35) < 1e-9);
ok("the posting table counts what the score counts", /const scored=tag!=="About"&&DICT\.usefulKw\("Rt\|"\+e\.name\)&&!Scoring\.looseTerm\(e\.name\)/.test(page));
ok("the weekly list still sees single words (the keyword filter is unchanged)", eng.usefulKw("Rt|SaaS") === true);

console.log("4. The occupation reading");
const code = Object.keys(lib.profiles).find((k) => lib.profiles[k].core_competencies.some((c) => c.parts.includes("Hearing Sensitivity")) && lib.profiles[k].core_competencies.some((c) => c.parts.includes("Repairing")));
const r = noc.compare(lib, "Maintenance technician\nRepaired pumps and conveyors. Troubleshooting electrical faults.", code, {});
const sk = r.items.filter((x) => x.part === "skills").map((x) => x.en);
for (const n of ["Hearing Sensitivity", "Near Vision", "Attention to Detail", "Knowledge in Mechanics and Machinery"]) ok(`"${n}" is not listed`, !sk.includes(n), sk);
ok("\"Repairing\" is still read, and matched by \"Repaired\"", r.items.some((x) => x.en === "Repairing" && x.label === "Matched"), sk);
const allowed = new Set(Object.values(lib.profiles).flatMap((p) => p.skills.map((s) => s.en)));
let stray = [];
for (const k of Object.keys(lib.profiles).slice(0, 300)) for (const x of noc.compare(lib, "Engineer", k, {}).items) if (x.part === "skills" && !allowed.has(x.en)) stray.push(x.en);
ok("on 300 occupations, every listed skill is an OaSIS skill", stray.length === 0, stray.slice(0, 5));
ok("its label is \"Not on CV\", not \"Gap\"", /Missing:\["X","Not on CV"\]/.test(page) && /Not scored\.<\/b>/.test(page));

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
