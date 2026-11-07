import json
import unittest

from tools.workflow import blueprint_inspect as b


def report():
    return {
        "success": True,
        "chain": {"order": ["WF2", "WF1"]},
        "workflows": {
            "WF1": {"triggers": ["t"], "templates": ["x" * 500], "assessmentInputsRead": [{"inputName": "n", "sample": "s" * 500}], "requiredInputsUnset": [{"input": "Project"}],
                    "applicationScope": [{"scope": "s", "needs": ["jiracloud"]}]},
            "WF2": {"triggers": [], "templates": []},
        },
        "assessmentInputs": [{"inputName": "n", "readBy": ["WF1"], "sample": "s" * 500}],
        "prerequisitesMissing": ["x"],
    }


class Brief(unittest.TestCase):
    def test_the_heavy_parts_are_left_out(self):
        got = b.brief(report())
        self.assertNotIn("templates", got["workflows"]["WF1"])
        self.assertNotIn("assessmentInputsRead", got["workflows"]["WF1"])
        self.assertNotIn("sample", got["assessmentInputs"][0])

    def test_what_design_needs_stays(self):
        got = b.brief(report())
        self.assertEqual(got["chain"], {"order": ["WF2", "WF1"]})
        self.assertEqual(got["workflows"]["WF1"]["requiredInputsUnset"], [{"input": "Project"}])
        self.assertEqual(got["workflows"]["WF1"]["applicationScope"][0]["needs"], ["jiracloud"])
        self.assertEqual(got["assessmentInputs"][0]["inputName"], "n")
        self.assertEqual(got["prerequisitesMissing"], ["x"])

    def test_the_answer_says_it_is_brief(self):
        self.assertIn("without brief", b.brief(report())["brief"])

    def test_the_input_is_not_changed(self):
        original = report()
        b.brief(original)
        self.assertEqual(original, report())

    def test_it_is_about_half_the_size_or_less(self):
        self.assertLess(len(json.dumps(b.brief(report()))), len(json.dumps(report())) / 2)


if __name__ == "__main__":
    unittest.main()
