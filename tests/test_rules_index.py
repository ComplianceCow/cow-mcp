import unittest
from types import SimpleNamespace

from tools.playbook import rules_index as r


class IndexLines(unittest.TestCase):
    def test_one_line_per_rule_sorted_by_name_ignoring_case(self):
        got = r.index_lines([{"name": "beta", "purpose": "B"}, {"name": "Alpha", "purpose": "A"}])
        self.assertEqual(got, ["Alpha: A", "beta: B"])

    def test_the_description_stands_in_for_a_missing_purpose(self):
        self.assertEqual(r.index_lines([{"name": "X", "purpose": "", "description": "from description"}]), ["X: from description"])

    def test_a_purpose_that_only_repeats_the_name_gives_way_to_the_description(self):
        self.assertEqual(r.index_lines([{"name": "XReport", "purpose": "XReport", "description": "Lists X"}]), ["XReport: Lists X"])

    def test_a_name_repeated_by_both_is_listed_by_name_alone(self):
        self.assertEqual(r.index_lines([{"name": "XReport", "purpose": "XReport", "description": "xreport"}]), ["XReport"])

    def test_a_rule_with_neither_is_listed_by_name(self):
        self.assertEqual(r.index_lines([{"name": "X"}]), ["X"])

    def test_a_long_purpose_is_cut_and_whitespace_collapsed(self):
        line = r.index_lines([{"name": "X", "purpose": "word  " * 100}])[0]
        self.assertLessEqual(len(line), len("X: ") + r.PURPOSE_LIMIT)
        self.assertTrue(line.endswith("…"))
        self.assertNotIn("  ", line)

    def test_duplicates_by_name_keep_the_first_and_blank_names_are_dropped(self):
        got = r.index_lines([{"name": "X", "purpose": "first"}, {"name": "X", "purpose": "second"}, {"name": ""}])
        self.assertEqual(got, ["X: first"])

    def test_objects_with_attributes_work_like_dicts(self):
        self.assertEqual(r.index_lines([SimpleNamespace(name="X", purpose="p", description="d")]), ["X: p"])

    def test_it_is_far_smaller_than_the_full_summary(self):
        full = [{"name": f"Rule{i}", "purpose": "p" * 90, "description": "d" * 175, "readmeData": ""} for i in range(300)]
        import json
        self.assertLess(len("\n".join(r.index_lines(full))), len(json.dumps(full)) / 2.5)


if __name__ == "__main__":
    unittest.main()
