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


class Select(unittest.TestCase):
    POOL = [{"id": f"s{i}"} for i in range(10)]

    def test_total_caps_the_fixed_order_and_done_is_skipped(self):
        got = ls.select_todo(self.POOL, {"s0", "s1"}, limit=100, total=5)
        self.assertEqual([x["id"] for x in got], ["s2", "s3", "s4"])

    def test_limit(self):
        self.assertEqual(len(ls.select_todo(self.POOL, set(), limit=3)), 3)

    def test_third_vote_only_where_the_two_disagree(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "a.jsonl", Path(d) / "b.jsonl"
            rec = lambda i, sk: json.dumps({"id": i, "dict": ["Welding"], "skills": [{"n": n} for n in sk]})
            a.write_text("\n".join([rec("s0", ["Welding", "Assembly"]), rec("s1", ["Assembly"]), rec("s2", ["Blueprints"])]))
            b.write_text("\n".join([rec("s0", ["Assembly"]), rec("s1", ["Assembly", "Painting"]), rec("s3", ["X"])]))
            got = ls.select_todo(self.POOL, set(), limit=100, disagree=(str(a), str(b)))
            # s0: same new skills (Welding is the dictionary's) -> agreed; s1 differs -> vote; s2, s3: only one answer
            self.assertEqual([x["id"] for x in got], ["s1"])


class SplitsUnreadableBatches(unittest.TestCase):
    """Nov 24: one batch of 20 came back unreadable fifteen times and stopped vote 2 for the day."""

    def test_one_poison_sentence_is_set_aside_and_the_rest_labelled(self):
        import types
        todo = [{"id": f"s{i}", "text": f"Weld steel frames number {i}.", "lang": "en", "tag": "", "emp": "e",
                 "dict": [], "cands": ["Welding"]} for i in range(20)]
        calls = []

        def fake_ask(key, models, prompt, log):
            ids = [x["id"] for x in todo if f'"id": "{x["id"]}"' in prompt]
            calls.append(len(ids))
            if "s13" in ids:
                raise ls.Unreadable("broken")
            return "fake-model", {"items": [{"id": i, "skills": [{"n": "Welding", "quote": "Weld"}], "cv": "Welded frames."} for i in ids]}, {}

        saved_ask, saved_sleep = ls.ask, ls.time.sleep
        ls.ask, ls.time.sleep = fake_ask, lambda s: None
        try:
            with tempfile.TemporaryDirectory() as d:
                path = Path(d) / "labels.jsonl"
                stats = {k: 0 for k in ("sentences", "requests", "tokens_in", "tokens_out", "skills_kept",
                                        "skills_dropped", "credentials", "education", "with_cv", "empty")}
                a = types.SimpleNamespace(batch=20, pause=0)
                stop = ls.run_batches(a, todo, "k", ["fake-model"], path, LOOK, stats, {})
                labelled = [json.loads(l)["id"] for l in path.open()]
                skipped = [json.loads(l)["id"] for l in (Path(d) / "skipped.jsonl").open()]
        finally:
            ls.ask, ls.time.sleep = saved_ask, saved_sleep
        self.assertEqual(stop, "done")
        self.assertEqual(skipped, ["s13"])
        self.assertEqual(sorted(labelled), sorted(x["id"] for x in todo if x["id"] != "s13"))
        self.assertEqual(stats["sentences"], 19)
        self.assertLess(len(calls), 15)          # 20 -> 10+10 -> 5+5 -> 2+3 -> 1+2 -> 1+1: a handful of calls


class TimeBudget(unittest.TestCase):
    """Nov 24: a vote crawled for 5.5 hours and GitHub cut the job off before saving. A budget ends it cleanly."""

    def test_the_vote_stops_cleanly_when_its_time_is_up(self):
        import types
        todo = [{"id": f"s{i}", "text": f"Weld steel frames number {i}.", "lang": "en", "tag": "", "emp": "e",
                 "dict": [], "cands": ["Welding"]} for i in range(100)]
        clock = [0.0]

        def fake_ask(key, models, prompt, log):
            clock[0] += 600                   # every request "takes" 10 minutes
            ids = [x["id"] for x in todo if f'"id": "{x["id"]}"' in prompt]
            return "m", {"items": [{"id": i, "skills": [], "cv": ""} for i in ids]}, {}

        saved = ls.ask, ls.time.sleep, ls.time.time
        ls.ask, ls.time.sleep, ls.time.time = fake_ask, (lambda s: None), (lambda: clock[0])
        try:
            with tempfile.TemporaryDirectory() as d:
                path = Path(d) / "labels.jsonl"
                stats = {k: 0 for k in ("sentences", "requests", "tokens_in", "tokens_out", "skills_kept",
                                        "skills_dropped", "credentials", "education", "with_cv", "empty")}
                stop = ls.run_batches(types.SimpleNamespace(batch=10, pause=0, max_minutes=25), todo, "k", ["m"], path, LOOK, stats, {})
                n = sum(1 for _ in path.open())
        finally:
            ls.ask, ls.time.sleep, ls.time.time = saved
        self.assertEqual(stop, "time budget used: the next run carries on")
        self.assertEqual(n, 30)               # 3 requests of 10 minutes fit before the 25-minute budget is passed


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
