import asyncio
import unittest
from unittest import mock

from tools.workflow import plan_inputs as p
from tools.workflow import workflow as tool

ID = "8abc9189-6492-4451-bd48-8714febba589"
PLAN = {"id": ID, "name": "ZZ L2", "inputs": {
    "AdminEmail": {"type": "string", "isrequired": True, "description": "Admin mailbox", "defaultvalue": "a@example.com"},
    "JiraWorkflowConfigFile": {"type": "file", "isrequired": True, "description": "Config", "defaultvalue": {"FileName": "c.json", "FileHash": "h", "FileContent": None}},
    "Empty": {"type": "string", "isrequired": False, "defaultvalue": ""},
    "EmptyFile": {"type": "file", "isrequired": True, "defaultvalue": {"FileName": "", "FileHash": ""}},
}}
NOT_FOUND = {"Message": "RESOURCE_NOT_FOUND", "Description": "Resource you requested for is not found"}


class Describe(unittest.TestCase):
    def test_each_input_is_listed_with_what_the_platform_stores(self):
        got = {i["key"]: i for i in p.describe(ID, PLAN)["inputs"]}
        self.assertEqual((got["AdminEmail"]["value"], got["AdminEmail"]["hasValue"], got["AdminEmail"]["required"]), ("a@example.com", True, True))
        self.assertEqual((got["JiraWorkflowConfigFile"]["fileName"], got["JiraWorkflowConfigFile"]["value"], got["JiraWorkflowConfigFile"]["hasValue"]), ("c.json", None, True))

    def test_an_input_with_nothing_in_it_has_no_value(self):
        got = {i["key"]: i["hasValue"] for i in p.describe(ID, PLAN)["inputs"]}
        self.assertEqual((got["Empty"], got["EmptyFile"]), (False, False))

    def test_a_plan_that_does_not_exist_is_a_failure_not_an_empty_list(self):
        self.assertFalse(p.describe(ID, NOT_FOUND)["success"])
        self.assertFalse(p.describe(ID, "Facing error")["success"])

    def test_a_different_plan_is_not_taken_for_the_one_asked_for(self):
        self.assertFalse(p.describe("8abc9189-6492-4451-bd48-8714bebba589", PLAN)["success"])

    def test_a_plan_without_inputs_is_an_empty_list(self):
        self.assertEqual(p.describe(ID, {"id": ID, "name": "x"})["inputs"], [])


class TheTool(unittest.TestCase):
    def call(self, response, plan_id=ID):
        with mock.patch.object(tool.utils, "make_API_call_to_CCow_and_get_response", mock.AsyncMock(return_value=response)):
            return asyncio.run(tool.list_assessment_inputs(plan_id))

    def test_it_returns_the_inputs(self):
        self.assertEqual([i["key"] for i in self.call(PLAN)["inputs"]], ["AdminEmail", "Empty", "EmptyFile", "JiraWorkflowConfigFile"])

    def test_a_missing_plan_is_an_error(self):
        result = self.call(NOT_FOUND, "no-such-id")
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
