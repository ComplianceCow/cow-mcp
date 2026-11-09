import unittest

from tools.playbook import match_rows as m


def row(use_case, step, description="Checks X", **extra):
    base = {"id": use_case, "version": "1.0.0", "name": use_case.title(), "description": description, "inScope": ["a", "b"], "outOfScope": ["c"],
            "blockingInputs": None, "levels": ["L1"], "detail": f"detail {step}", "config": {"id": step}, "requiresApplication": None, "steps": 1}
    base.update(extra)
    return base


class GroupByUseCase(unittest.TestCase):
    def test_one_row_per_use_case_with_its_steps_nested(self):
        got = m.group_by_use_case([row("uc-a", "s1"), row("uc-a", "s2"), row("uc-b", "s1")])
        self.assertEqual([g["id"] for g in got], ["uc-a", "uc-b"])
        self.assertEqual([s["config"]["id"] for s in got[0]["steps"]], ["s1", "s2"])
        self.assertEqual(got[0]["stepCount"], 2)

    def test_use_case_fields_appear_once_and_step_fields_only_inside_steps(self):
        got = m.group_by_use_case([row("uc-a", "s1"), row("uc-a", "s2")])[0]
        self.assertEqual(got["description"], "Checks X")
        for field in ("detail", "config", "requiresApplication"):
            self.assertNotIn(field, got)

    def test_a_field_missing_on_the_first_row_is_taken_from_a_later_one(self):
        got = m.group_by_use_case([row("uc-a", "s1", levels=None), row("uc-a", "s2", levels=["L1", "L2"])])[0]
        self.assertEqual(got["levels"], ["L1", "L2"])

    def test_a_use_case_without_steps_is_kept_with_zero_steps(self):
        got = m.group_by_use_case([row("uc-a", "s1", detail=None, config=None)])[0]
        self.assertEqual((got["stepCount"], got["steps"]), (0, []))

    def test_the_output_is_much_smaller_than_the_input_for_a_big_use_case(self):
        import json
        rows = [row("uc-a", f"s{i}", description="d" * 500) for i in range(40)]
        self.assertLess(len(json.dumps(m.group_by_use_case(rows))), len(json.dumps(rows)) / 3)


if __name__ == "__main__":
    unittest.main()


class NoUseCaseNote(unittest.TestCase):
    def test_a_catalog_without_a_use_case_says_full_is_impossible(self):
        note = m.no_use_case_note(0)
        self.assertIn("FULL is impossible", note)
        self.assertIn("invent", note)

    def test_a_catalog_with_a_use_case_adds_nothing(self):
        self.assertEqual(m.no_use_case_note(1), "")
