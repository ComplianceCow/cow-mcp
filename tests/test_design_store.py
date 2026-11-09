import asyncio
import os
import tempfile
import unittest
from unittest import mock

from tools.playbook import design_store as d
from tools.playbook import usecase_check as u

YAML = """
spec:
  name: Demo
  inputs:
    slaHours: {type: integer, default: 24}
  steps:
    - id: app
      type: create_application
      name: Okta
      prerequisiteSteps: []
    - id: scope
      type: create_application_scope
      name: Okta scope
      prerequisiteSteps: [app]
"""


class Store(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        patcher = mock.patch.dict(os.environ, {"COW_MCP_DESIGN_DIR": self.dir.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.dir.cleanup)

    def test_the_id_comes_from_the_content_not_the_formatting(self):
        self.assertEqual(d.design_id(YAML), d.design_id(YAML.replace("{type: integer, default: 24}", "{default: 24, type: integer}")))
        self.assertNotEqual(d.design_id(YAML), d.design_id(YAML.replace("Demo", "Other")))

    def test_save_then_read_returns_the_yaml_and_an_outline(self):
        did = d.save(YAML, "uat", {"user_configurable": ["slaHours"]})
        got = d.read(did, "uat")
        self.assertTrue(got["success"])
        self.assertEqual(got["yaml"], YAML)
        self.assertEqual([s["id"] for s in got["outline"]], ["app", "scope"])
        self.assertEqual(got["outline"][1]["prerequisiteSteps"], ["app"])

    def test_asking_for_steps_returns_only_those_and_names_the_missing(self):
        did = d.save(YAML, "uat")
        got = d.read(did, "uat", ["scope", "nope"])
        self.assertEqual([s["id"] for s in got["steps"]], ["scope"])
        self.assertEqual(got["missing"], ["nope"])
        self.assertNotIn("yaml", got)
        self.assertEqual(got["inputs"]["slaHours"]["default"], 24)

    def test_another_tenant_cannot_read_it(self):
        did = d.save(YAML, "uat")
        self.assertFalse(d.read(did, "dev")["success"])

    def test_an_unknown_or_unsafe_id_is_an_error_not_a_file_read(self):
        self.assertFalse(d.read("nope", "uat")["success"])
        self.assertFalse(d.read("../../etc/passwd", "uat")["success"])
        self.assertFalse(d.read("", "uat")["success"])

    def test_text_that_is_not_yaml_is_not_stored(self):
        self.assertIsNone(d.save("a: [unclosed", "uat"))


class CheckStoresValidDesigns(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        patcher = mock.patch.dict(os.environ, {"COW_MCP_DESIGN_DIR": self.dir.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.dir.cleanup)

    def run_check(self, text):
        with mock.patch("tools.playbook.preflight.identity_of", return_value={"domainName": "uat"}):
            return asyncio.run(u.check_use_case_design(text))

    def test_a_valid_design_gets_an_id_and_can_be_read_back(self):
        result = self.run_check(YAML)
        self.assertTrue(result["valid"], result)
        self.assertEqual(result["designId"], d.design_id(YAML))
        with mock.patch("tools.playbook.preflight.identity_of", return_value={"domainName": "uat"}):
            got = asyncio.run(u.get_design(result["designId"]))
        self.assertEqual(got["yaml"], YAML)

    def test_an_invalid_design_is_not_stored(self):
        result = self.run_check(YAML.replace("[app]", "[missing-step]"))
        self.assertFalse(result["valid"])
        self.assertNotIn("designId", result)
        self.assertEqual(os.listdir(self.dir.name), [])


if __name__ == "__main__":
    unittest.main()


class PushByDesignId(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        patcher = mock.patch.dict(os.environ, {"COW_MCP_DESIGN_DIR": self.dir.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.dir.cleanup)

    def test_an_unknown_design_id_is_refused_without_calling_the_backend(self):
        from tools.playbook import usecase_tools as t
        with mock.patch("tools.playbook.preflight.identity_of", return_value={"domainName": "uat"}):
            got = asyncio.run(t.push_use_case(design_id="nope"))
        self.assertFalse(got["pushed"])
        self.assertIn("design_id", got["problem"])

    def test_a_stored_design_is_pushed_from_the_store(self):
        from tools.playbook import usecase_tools as t
        did = d.save(YAML, "uat")
        seen = {}

        def fake_prepare(text, source, replace):
            seen["yaml"] = text
            return {"prepared": True}

        async def fake_review(prepared, poster):
            return {"pushed": False, "needs_approval": True}

        with mock.patch("tools.playbook.preflight.identity_of", return_value={"domainName": "uat"}), \
                mock.patch.object(t.push_logic, "prepare", fake_prepare), mock.patch.object(t.push_logic, "review", fake_review):
            got = asyncio.run(t.push_use_case(design_id=did))
        self.assertEqual(seen["yaml"], YAML)
        self.assertTrue(got["needs_approval"])
