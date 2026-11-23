"""test_label_sentences.py - the checks on Gemini's answers decide what our model learns from, so they are tested.
Run: python3 -m unittest tests/test_label_sentences.py    (no key, nothing is sent)
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import label_sentences as ls  # noqa: E402

DICT = {"general": ["Communication"], "soft": [], "skills": [
    {"n": "Procurement", "a": ["purchasing", "sourcing"]},
    {"n": "Cost estimation", "a": ["estimating costs"]},
    {"n": "Communication", "a": []},
    {"n": "Welding", "a": ["soudage"]},
    {"n": "General Learning Ability", "a": ["learning ability"], "s": "OaSIS abilities"}]}
LOOK = ls.dictionary_lookup(DICT)
X = {"id": "a1", "text": "Request supplier quotes to build project cost estimates.", "cands": ["Cost estimation", "Welding"]}


class Check(unittest.TestCase):
    def test_keeps_a_proven_skill_from_the_list(self):
        kept, dropped, _ = ls.check(X, {"skills": [{"n": "Cost estimation", "quote": "cost estimates"}]}, LOOK)
        self.assertEqual(kept["skills"], [{"n": "Cost estimation", "quote": "cost estimates"}])
        self.assertEqual(dropped, [])

    def test_quote_must_be_in_the_sentence(self):
        kept, dropped, _ = ls.check(X, {"skills": [{"n": "Cost estimation", "quote": "budget forecasting"}]}, LOOK)
        self.assertEqual(kept["skills"], [])
        self.assertEqual(dropped[0][2], "quote not in the sentence")

    def test_quote_matches_whole_words_and_ignores_accents_and_case(self):
        x = {"id": "b", "text": "Expérience en soudage MIG.", "cands": ["Welding"]}
        self.assertEqual(ls.check(x, {"skills": [{"n": "Welding", "quote": "experience en SOUDAGE"}]}, LOOK)[0]["skills"][0]["n"], "Welding")
        self.assertEqual(ls.check(x, {"skills": [{"n": "Welding", "quote": "souda"}]}, LOOK)[0]["skills"], [])

    def test_off_list_name_kept_only_if_the_dictionary_knows_it(self):
        kept, dropped, _ = ls.check(X, {"skills": [{"n": "purchasing", "quote": "supplier quotes"},
                                                   {"n": "Vendor wizardry", "quote": "supplier quotes"}]}, LOOK)
        self.assertEqual([k["n"] for k in kept["skills"]], ["Procurement"])     # a spelling -> the skill's name
        self.assertEqual(dropped[0][2], "not a dictionary skill")

    def test_general_skills_are_never_kept_off_the_list(self):
        kept, _, _ = ls.check(X, {"skills": [{"n": "Communication", "quote": "Request"}]}, LOOK)
        self.assertEqual(kept["skills"], [])

    def test_credentials_and_degrees_need_a_quote_too(self):
        x = {"id": "c", "text": "Bachelor's degree in engineering and a valid PMP certification.", "cands": []}
        kept, dropped, _ = ls.check(x, {"credentials": [{"n": "PMP", "quote": "PMP certification"}, {"n": "CPA", "quote": "CPA"}],
                                        "education": [{"n": "Bachelor's degree in engineering", "quote": "Bachelor's degree in engineering"}]}, LOOK)
        self.assertEqual([k["n"] for k in kept["credentials"]], ["PMP"])
        self.assertEqual(len(kept["education"]), 1)
        self.assertEqual(len(dropped), 1)

    def test_cv_line_never_keeps_a_link_or_email(self):
        self.assertEqual(ls.check(X, {"cv": "Requested quotes; see www.example.com"}, LOOK)[2], "")
        self.assertEqual(ls.check(X, {"cv": "Requested supplier quotes."}, LOOK)[2], "Requested supplier quotes.")

    def test_bad_shapes_do_not_crash(self):
        kept, dropped, cv = ls.check(X, {"skills": ["Procurement", {"n": ""}], "cv": None}, LOOK)
        self.assertEqual(kept["skills"], [])
        self.assertEqual(len(dropped), 2)
        self.assertEqual(cv, "")


class Teachable(unittest.TestCase):
    def test_government_ability_labels_are_never_offered_or_accepted(self):
        self.assertNotIn("General Learning Ability", [s["n"] for s in ls.teachable(DICT)])
        kept, dropped, _ = ls.check(X, {"skills": [{"n": "General Learning Ability", "quote": "Request"}]}, LOOK)
        self.assertEqual(kept["skills"], [])
        self.assertEqual(dropped[0][2], "not a dictionary skill")


class DryRun(unittest.TestCase):
    def test_dry_run_sends_nothing_and_needs_no_key(self):
        with tempfile.TemporaryDirectory() as d:
            pool = Path(d) / "pool.jsonl"
            pool.write_text("\n".join(json.dumps({"id": f"s{i}", "text": f"Weld steel frames to blueprint number {i}.",
                                                  "lang": "en", "tag": "task", "dict": ["Welding"], "emp": "e"}) for i in range(5)))
            r = subprocess.run([sys.executable, str(ROOT / "tools" / "label_sentences.py"), "--pool", str(pool),
                                "--site", str(ROOT / "gaps-after"), "--out", str(Path(d) / "out"), "--limit", "5", "--dry"],
                               capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("nothing sent", r.stdout)
            self.assertFalse((Path(d) / "out" / "labels.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
