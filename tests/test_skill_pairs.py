"""test_skill_pairs.py - the Python side of Part 2, on small made-up data where every answer can be worked out by hand.
Run: python3 -m unittest tests/test_skill_pairs.py      (standard library only)
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import skill_pairs as sp  # noqa: E402


def job(company, title, skills, partial=False):
    return {"company": company, "title": title, "partial": partial, "kw": ["Ks|" + s for s in skills] + ["Tt|" + title]}


class Learn(unittest.TestCase):
    def setUp(self):
        self.saved = (sp.MIN_PAIR, sp.MIN_BASE, sp.MIN_CONF, sp.MIN_LIFT)
        sp.MIN_PAIR, sp.MIN_BASE, sp.MIN_CONF, sp.MIN_LIFT = 2, 2, 0.5, 1.5

    def tearDown(self):
        sp.MIN_PAIR, sp.MIN_BASE, sp.MIN_CONF, sp.MIN_LIFT = self.saved

    def test_counts_and_rule(self):
        # Welding with Assembly in 3 of 4 welding jobs; 10 jobs in all, Assembly in 3 of them
        sets = [("w%d" % i, {"Welding", "Assembly"}) for i in range(3)] + [("w3", {"Welding", "Blueprints"})]
        sets += [("o%d" % i, {"Sales", "Excel reports"}) for i in range(6)]
        rules, one, n = sp.learn(sets)
        self.assertEqual(n, 10)
        self.assertEqual(one["Welding"], 4)
        b, conf, lift, nab = rules["Welding"][0]
        self.assertEqual((b, conf, nab), ("Assembly", 0.75, 3))
        self.assertAlmostEqual(lift, 0.75 / 0.3, places=1)   # 3 of 10 jobs ask for Assembly
        self.assertNotIn("Blueprints", [r[0] for r in rules["Welding"]])   # 1 job only: below MIN_PAIR

    def test_lift_keeps_out_what_everyone_asks(self):
        # "Safety" is in every job: it goes with Welding as often as with anything, so no rule
        sets = [("j%d" % i, {"Welding", "Safety"}) for i in range(5)] + [("k%d" % i, {"Sales", "Safety"}) for i in range(5)]
        rules, _, _ = sp.learn(sets)
        self.assertNotIn("Safety", [r[0] for r in rules.get("Welding", [])])

    def test_same_job_counted_once_and_titles_only_skipped(self):
        jobs = [job("Acme", "Welder", ["Welding", "Assembly"])] * 50 + [job("Beta", "Welder", ["Welding"], partial=True)]
        sets = sp.posting_skill_sets(jobs, {"Welding", "Assembly"}, set())
        self.assertEqual(len(sets), 1)

    def test_excluded_never_learned(self):
        d = {"general": ["Communication"], "soft": [], "skills": [{"n": n} for n in
             ["Communication", "Forklift licence", "French", "Engineering degrees", "Welding", "Master production scheduling", "Diplomacy and tact"]]}
        skip = sp.excluded_skills(d)
        self.assertEqual(skip, {"Communication", "Forklift licence", "French", "Engineering degrees"})


class Infer(unittest.TestCase):
    RULES = {"Welding": [["Assembly", 0.4, 19.5, 28], ["Blueprints", 0.3, 8.0, 20]],
             "CNC and machining": [["Assembly", 0.5, 12.0, 30]]}

    def test_evidence_adds_up(self):
        # Welding alone: 0.40 < 0.60, nothing shown. With CNC as well: 1 - 0.6 x 0.5 = 0.70, shown
        self.assertEqual(sp.infer(["Welding"], self.RULES), [])
        got = sp.infer(["Welding", "CNC and machining"], self.RULES)
        self.assertEqual(got, [{"n": "Assembly", "p": 0.7, "because": ["CNC and machining", "Welding"]}])

    def test_never_guess_what_is_on_the_cv(self):
        self.assertEqual(sp.infer(["Welding", "CNC and machining", "Assembly"], self.RULES), [])

    def test_half_up_rounding_like_javascript(self):
        # 1 - (1 - 0.5)(1 - 0.0005)... is checked through the public function: p is rounded half up
        rules = {"A": [["X", 0.6125, 3.0, 20]]}
        self.assertEqual(sp.infer(["A"], rules, min_p=0.5)[0]["p"], 0.613)


if __name__ == "__main__":
    unittest.main()
