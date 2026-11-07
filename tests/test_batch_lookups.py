import asyncio
import unittest
from unittest import mock

from tools.applications import applications
from tools.workflow import workflow


def run(coro):
    return asyncio.run(coro)


class FindRulesByName(unittest.TestCase):
    def test_every_name_is_looked_up_once_and_returned_by_name(self):
        seen = []

        async def single(name, ctx=None):
            seen.append(name)
            return {"success": True, "name": name}

        with mock.patch.object(workflow, "find_rule_by_name", single):
            got = run(workflow.find_rules_by_name(["A", "B", "A", " B ", ""]))
        self.assertEqual(sorted(seen), ["A", "B"])
        self.assertEqual(got["rules"], {"A": {"success": True, "name": "A"}, "B": {"success": True, "name": "B"}})

    def test_one_failing_lookup_does_not_spoil_the_others(self):
        async def single(name, ctx=None):
            if name == "Bad":
                raise RuntimeError("boom")
            return {"success": True, "name": name}

        with mock.patch.object(workflow, "find_rule_by_name", single):
            got = run(workflow.find_rules_by_name(["Good", "Bad"]))
        self.assertTrue(got["rules"]["Good"]["success"])
        self.assertEqual(got["rules"]["Bad"]["where"], "unchecked")

    def test_more_than_the_limit_is_reported_not_silently_dropped(self):
        async def single(name, ctx=None):
            return {"success": True, "name": name}

        names = [f"R{i}" for i in range(workflow.MAX_BATCH_LOOKUP + 3)]
        with mock.patch.object(workflow, "find_rule_by_name", single):
            got = run(workflow.find_rules_by_name(names))
        self.assertEqual(len(got["rules"]), workflow.MAX_BATCH_LOOKUP)
        self.assertEqual(got["notLookedUp"], names[workflow.MAX_BATCH_LOOKUP:])

    def test_no_name_is_an_error(self):
        self.assertFalse(run(workflow.find_rules_by_name(["", "  "]))["success"])


class DescribeApplicationTypes(unittest.TestCase):
    def test_each_type_is_returned_under_its_name(self):
        async def single(name=None, version=None, ctx=None):
            return {"error": "Application type not found"} if name == "nope" else {"meta": {"name": name}}

        with mock.patch.object(applications, "list_application_types", single):
            got = run(applications.describe_application_types(["HttpRequest", "nope", "HttpRequest"]))
        self.assertEqual(list(got["applicationTypes"]), ["HttpRequest", "nope"])
        self.assertEqual(got["applicationTypes"]["nope"], {"error": "Application type not found"})

    def test_no_name_is_an_error(self):
        self.assertIn("error", run(applications.describe_application_types([])))


if __name__ == "__main__":
    unittest.main()
