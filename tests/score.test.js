/* score.test.js - phase 5: the new score, and what decides the list.
 * Run: node tests/score.test.js            (checks after-4 by default)
 */
const path = require("path");
const DIR = process.argv[2] || "after-4";
const S = require(path.join(__dirname, "..", DIR, "scoring.js"));
const J = require(path.join(__dirname, "..", DIR, "jobmeta.js"));

let pass = 0, fail = 0;
const ok = (what, cond, got) => {
  if (cond) { pass++; console.log("  ok   " + what); }
  else { fail++; console.log("  FAIL " + what + (got !== undefined ? "   got: " + got : "")); }
};
const row = (n, tag, st, o) => Object.assign({ n: n, tag: tag, st: st, kind: "s" }, o || {});
/* a posting asking for 10 specific skills */
const ten = (hits) => {
  const names = ["MRP", "SolidWorks", "PLC programming", "Inventory control", "Lean Six Sigma",
    "AutoCAD", "SAP", "Quality control", "Procurement", "Maintenance and reliability"];
  return names.map((n, i) => row(n, i < 4 ? "R" : "K", i < hits ? "M" : "G"));
};

console.log("the title and the level give no points");
ok("a word from the job title is worth nothing",
   S.weight(row("supply chain coordinator", "T", "M")) === 0);
ok("a required skill is worth the most", S.weight(row("MRP", "R", "M")) === 1);
ok("a nice-to-have is worth less", S.weight(row("MRP", "P", "M")) < S.weight(row("MRP", "R", "M")));
ok("a skill everyone has counts about a third",
   Math.abs(S.weight(row("Communication", "R", "M", { general: true })) - 0.35) < 0.01);

console.log("\nthe score follows the coverage");
const low = S.compute(ten(2), {}), mid = S.compute(ten(5), {}), high = S.compute(ten(9), {});
/* The bar for full skills points is 60% weighted coverage, set from the real spread: the best match
   any test CV had across 75,810 postings covered 32 to 46 per cent. */
ok("covering 2 of 10 scores low", low.total < 35, String(low.total));
ok("covering 5 of 10 scores in the middle", mid.total >= 50 && mid.total <= 75, String(mid.total));
ok("covering 9 of 10 scores high", high.total >= 85, String(high.total));
ok("more coverage is always more points", low.total < mid.total && mid.total < high.total);
ok("a posting covered half does not score 100", S.compute(ten(5), {}).total < 80, String(mid.total));
ok("a Close counts half a Match",
   S.compute(ten(0).map((x, i) => (i < 4 ? Object.assign({}, x, { st: "R" }) : x)), {}).total <
   S.compute(ten(4), {}).total);

console.log("\nout of what the posting asks for");
const noAsk = S.compute(ten(5), {});
ok("a posting naming no degree is scored out of 70", noAsk.available === 70, String(noAsk.available));
const withEdu = S.compute(ten(5), { eduAsked: 4, eduHave: 4, eduRelated: true });
ok("a posting naming a degree is scored out of 90", withEdu.available === 90, String(withEdu.available));
ok("the right degree in the right field earns all 20", withEdu.education === 20, String(withEdu.education));
ok("the right level in another field keeps most of it",
   S.compute(ten(5), { eduAsked: 4, eduHave: 4, eduRelated: false }).education === 14);
ok("one level short keeps half",
   S.compute(ten(5), { eduAsked: 4, eduHave: 3, eduRelated: true }).education === 10);
ok("two levels short earns none",
   S.compute(ten(5), { eduAsked: 4, eduHave: 2, eduRelated: true }).education === 0);
ok("a higher degree than asked is not punished",
   S.compute(ten(5), { eduAsked: 4, eduHave: 5, eduRelated: true }).education === 20);
const cred = S.compute(ten(5).concat([row("PMP certification", "R", "G", { cred: true })]), {});
ok("a posting naming a certificate is scored out of 80", cred.available === 80, String(cred.available));
ok("a certificate you do not have earns none of its 10", cred.credentials === 0);
const credGot = S.compute(ten(5).concat([row("PMP certification", "R", "M", { cred: true })]), {});
ok("a certificate you have earns all 10", credGot.credentials === 10);
ok("a certificate is not counted twice, once as a skill and once as a credential",
   credGot.skills === S.compute(ten(5), {}).skills, credGot.skills + " vs " + S.compute(ten(5), {}).skills);

console.log("\nreading the education from both sides");
ok("a posting asking for a bachelor reads as 4", J.eduAsked("Bachelor's degree in engineering required") === 4);
ok("a posting asking for a college diploma reads as 3", J.eduAsked("College diploma or DEC required") === 3);
ok("a posting naming no degree reads as 0", J.eduAsked("We will train the right person.") === 0);
const cv = "EDUCATION\nMaster of Engineering - Industrial Engineering\nConcordia University\n2025 - 2027\n" +
  "Relevant coursework: database systems, programming\nWORK EXPERIENCE\nMaintenance Engineer\n";
const e = J.cvEdu(cv);
ok("a master's on the CV reads as 5", e.level === 5, String(e.level));
ok("the field comes from the degree line, not from the courses beside it",
   e.fields.indexOf("engineering") >= 0 && e.fields.indexOf("software") < 0, JSON.stringify(e.fields));
ok("a degree in progress still counts", J.cvEdu("EDUCATION\nBachelor of Commerce\n2024 - Present\n").level === 4);

console.log("\nmandatory licences (I-11)");
const mh = J.mustHaves("A valid Water Treatment Operator Certificate is mandatory. Experience with pumps is an asset.");
ok("a mandatory certificate is found", mh.length === 1, JSON.stringify(mh));
ok("...and is named", mh.length === 1 && /Water Treatment Operator Certificate/.test(mh[0].what || ""), JSON.stringify(mh[0] || {}));
ok("a driver's licence is reported apart",
   (J.mustHaves("A valid driver's licence is required.")[0] || {}).driving === true);
ok("an asset is not a must-have", J.mustHaves("A PMP certification is an asset.").length === 0);
ok("a sentence with no licence word is not a must-have",
   J.mustHaves("Three years of experience is required.").length === 0);

console.log("\nwhat the CV says it wants");
ok("a certificate name is recognised", J.isCredential("Six Sigma Green Belt"));
ok("an ordinary skill is not a certificate", !J.isCredential("Inventory control"));

console.log("\n" + pass + " passed, " + fail + " failed");
process.exit(fail ? 1 : 0);
