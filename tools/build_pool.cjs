/* build_pool.cjs - the study material for the inference engine's teacher step.
 *
 * Turns the public job postings of a frozen site copy into one sentence per line (JSON lines):
 *   {"id", "text", "lang", "tag", "dict", "emp"}
 * - only postings we hold in full; the same job posted many times is read once (employer + title);
 * - the "About us" / benefits part is skipped: it describes the employer, not the work;
 * - a sentence with an e-mail address, a web link or a phone number is dropped, so no personal
 *   detail is ever sent on to Gemini;
 * - the same sentence in many postings is kept once;
 * - "dict" = the dictionary skills the site already finds in it (what the model must add to);
 * - "emp"  = a short hash of the employer, so the test set can be kept apart from the training set.
 * No CV is read here. Usage: node tools/build_pool.cjs <site folder> <out.jsonl>
 */
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const [site, out] = process.argv.slice(2);
if (!site || !out) { console.error("usage: node tools/build_pool.cjs <site folder> <out.jsonl>"); process.exit(2); }
const eng = require(path.resolve(site, "matcher.js")).engine(JSON.parse(fs.readFileSync(path.join(site, "skills.json"), "utf8")));
const jobs = JSON.parse(fs.readFileSync(path.join(site, "jobs.json"), "utf8")).jobs;

const fold = (s) => String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
const h = (s, n = 12) => crypto.createHash("sha1").update(s).digest("hex").slice(0, n);
const PERSONAL = /@|https?:\/\/|www\.|\(\d{3}\)\s*\d{3}|\b\d{3}[-. ]\d{3}[-. ]\d{4}\b/i;
const FRENCH = /\b(le|la|les|des|du|et|vous|nous|une|pour|avec|dans|sur|est)\b/gi;
const ENGLISH = /\b(the|and|you|with|for|our|will|to|of|in|is)\b/gi;
const lang = (s) => ((s.match(FRENCH) || []).length > (s.match(ENGLISH) || []).length ? "fr" : "en");

/* the posting texts: d/<n>.json maps posting id -> text */
const text = new Map();
for (const f of fs.readdirSync(path.join(site, "d"))) {
  const d = JSON.parse(fs.readFileSync(path.join(site, "d", f), "utf8"));
  for (const [id, v] of Object.entries(d)) text.set(id, typeof v === "string" ? v : (v && (v.t || v.text)) || "");
}

const seenJob = new Set(), seen = new Set();
const fd = fs.openSync(out, "w");
let n = 0, personal = 0, repeated = 0, about = 0;
for (const j of jobs) {
  if (j.partial || !j.kw || !text.has(j.id)) continue;
  const key = fold(j.company) + "|" + fold(j.title);
  if (seenJob.has(key)) continue;
  seenJob.add(key);
  const t = text.get(j.id);
  const secs = eng.sections(t);
  let offset = 0;
  for (const line of t.split("\n")) {
    const lineStart = offset;
    offset += line.length + 1;
    /* a line may hold several sentences */
    let inLine = 0;
    for (const part of line.split(/(?<=[.;!?])\s+(?=[A-ZÀ-Ý])/)) {
      const at = lineStart + line.indexOf(part, inLine);
      inLine += part.length;
      const s = part.replace(/^[\s•\-*·▪●◦–—>]+/, "").replace(/\s+/g, " ").trim();
      if (s.length < 25 || s.length > 300 || s.split(" ").length < 4) continue;
      let tag = "";
      for (const x of secs) { if (x.pos <= at) tag = x.tag; else break; }
      if (tag === "ABOUT") { about++; continue; }
      if (PERSONAL.test(s)) { personal++; continue; }
      const k = fold(s);
      if (seen.has(k)) { repeated++; continue; }
      seen.add(k);
      const dict = Object.keys(eng.find(s)).sort();
      fs.writeSync(fd, JSON.stringify({ id: h(k), text: s, lang: lang(s), tag: tag.toLowerCase(), dict, emp: h(fold(j.company) || key, 8) }) + "\n");
      n++;
    }
  }
}
fs.closeSync(fd);
console.log(`${n} sentences from ${seenJob.size} distinct postings; dropped: ${repeated} repeated, ${about} in the About/benefits part, ${personal} with an e-mail, link or phone number -> ${out}`);
