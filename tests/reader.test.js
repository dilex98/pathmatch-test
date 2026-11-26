/* reader.test.js - the browser reader (tools/reader.js) must read a line exactly like the Python trainer.
 * Run: node tests/reader.test.js      (needs reader/skill_reader.json; no browser, no CV)
 *   1. the same clues for 400 real sentences, French included (accents, apostrophes, digits);
 *   2. the same score for every skill on those sentences (to 1e-4);
 *   3. the same skills found at the cut;
 *   4. small things a CV can hold: an empty line, a line of symbols, a very long line.
 */
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const R = require(path.join(__dirname, "..", "tools", "reader.js"));
const model = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "reader", "skill_reader.json"), "utf8"));
const reader = R.load(model);

let pass = 0, fail = 0;
const ok = (what, cond, got) => { if (cond) { pass++; console.log("  ok   " + what); } else { fail++; console.log("  FAIL " + what + (got !== undefined ? "   got: " + JSON.stringify(got).slice(0, 400) : "")); } };

/* 400 sentences: every 50th of the labels, plus their CV-style rewrites */
const lines = fs.readFileSync(path.join(__dirname, "..", "labels", "labels.jsonl"), "utf8").split("\n").filter(Boolean)
  .filter((_, i) => i % 100 === 0).slice(0, 200).flatMap((l) => { const x = JSON.parse(l); return [x.text, x.cv].filter(Boolean); });
lines.push("Gestion de l’approvisionnement, élaboration des soumissions — coûts & échéanciers (C++/C#, 5 ans).");
const tmp = path.join(require("os").tmpdir(), "reader_lines_" + process.pid + ".json");
fs.writeFileSync(tmp, JSON.stringify(lines));
const py = JSON.parse(execFileSync("python3", ["-c", `
import json, math, sys
sys.path.insert(0, sys.argv[1])
from train_reader import pieces
m = json.load(open(sys.argv[2], encoding="utf-8")); lines = json.load(open(sys.argv[3], encoding="utf-8"))
out = []
for t in lines:
    ps = sorted(pieces(t)); v = {p: m["clues"][p] for p in ps if p in m["clues"]}
    n = math.sqrt(sum(x * x for x in v.values())) or 1.0
    sc = []
    for s in m["skills"]:
        z = s["b"] + sum(w * v[c] / n for c, w in s["w"].items() if c in v)
        sc.append(1 / (1 + math.exp(-z)))
    out.append({"pieces": ps, "scores": sc})
print(json.dumps(out))
`, path.join(__dirname, "..", "tools"), path.join(__dirname, "..", "reader", "skill_reader.json"), tmp], { encoding: "utf8", maxBuffer: 512e6 }));
fs.unlinkSync(tmp);

console.log("1. The same clues");
let diffP = null;
lines.forEach((t, i) => { const js = [...R.pieces(t)].sort(); if (!diffP && JSON.stringify(js) !== JSON.stringify(py[i].pieces)) diffP = { t, js: js.slice(0, 12), py: py[i].pieces.slice(0, 12) }; });
ok(`identical clues on ${lines.length} lines (French and symbols included)`, !diffP, diffP);

console.log("2. The same scores");
let worst = 0, where = null;
lines.forEach((t, i) => reader.scores(t).forEach((s, k) => { const d = Math.abs(s.p - py[i].scores[k]); if (d > worst) { worst = d; where = { t, skill: s.n, js: s.p, py: py[i].scores[k] }; } }));
ok(`every skill's score agrees to 1e-4 (largest gap ${worst.toExponential(1)})`, worst < 1e-4, where);

console.log("3. The same skills found");
let diffF = null;
lines.forEach((t, i) => {
  const js = reader.read(t).map((x) => x.n).sort();
  const pyf = model.skills.map((s, k) => [s.n, py[i].scores[k]]).filter((x) => x[1] >= model.cut).map((x) => x[0]).sort();
  if (!diffF && JSON.stringify(js) !== JSON.stringify(pyf)) diffF = { t, js, py: pyf };
});
ok("the same skills pass the cut on every line", !diffF, diffF);
ok("some lines do find skills (the test is not empty)", lines.some((t) => reader.read(t).length > 0));
ok("every skill found names readable clues", lines.every((t) => reader.read(t).every((s) => Array.isArray(s.clues))));

console.log("4. Odd lines");
ok("an empty line finds nothing and does not crash", reader.read("").length === 0);
ok("a line of symbols finds nothing", reader.read("— • ★ ··· !!!").length === 0);
const long = lines.slice(0, 40).join(" ");
const t0 = Date.now(); reader.read(long); const ms = Date.now() - t0;
ok(`a very long line reads in under 200 ms (${ms} ms)`, ms < 200);

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
