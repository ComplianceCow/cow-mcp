import asyncio
import base64
import unittest
from unittest import mock

from tools.workflow import blueprint_readmes as b
from tools.workflow import rule_lookup as r
from tools.workflow import workflow as tool


def rule_activity(name):
    return {"action": {"type": "Rule", "reference": {"name": name, "id": f"id-{name}"}}}


def spec_of(**activities):
    return {"activities": activities, "transitions": []}


SPECS = {
    "Parent": spec_of(Fetch=rule_activity("FetchEvidence"), Update=rule_activity("FetchAndUpdateEvidenceV2")),
    "Child": spec_of(Update=rule_activity("FetchAndUpdateEvidenceV2"), Jq=rule_activity("ExtractDataUsingJQV2")),
}


def catalog_row(name, readme=None, tags=("MCP",)):
    row = {"meta": {"name": name, "tags": list(tags)}, "spec": {"tasks": []}}
    if readme is not None:
        row["readmeData"] = base64.b64encode(readme.encode()).decode()
    return row


class Collect(unittest.TestCase):
    def test_rule_names_are_the_rules_of_every_workflow_once(self):
        self.assertEqual(b.rule_names(SPECS), ["ExtractDataUsingJQV2", "FetchAndUpdateEvidenceV2", "FetchEvidence"])

    def test_a_readme_comes_with_the_workflows_that_use_the_rule(self):
        got = b.collect(SPECS, {"FetchAndUpdateEvidenceV2": "columns: TicketID", "FetchEvidence": "", "ExtractDataUsingJQV2": ""})
        self.assertEqual(got["ruleReadmes"], {"FetchAndUpdateEvidenceV2": {"usedBy": ["Child", "Parent"], "readme": "columns: TicketID"}})

    def test_a_rule_without_a_readme_is_named_as_having_none(self):
        got = b.collect(SPECS, {"FetchAndUpdateEvidenceV2": "x", "FetchEvidence": "", "ExtractDataUsingJQV2": ""})
        self.assertEqual(got["rulesWithoutReadme"], ["ExtractDataUsingJQV2", "FetchEvidence"])
        self.assertEqual(got["ruleReadmesUnchecked"], [])

    def test_a_rule_that_could_not_be_looked_up_is_unchecked_and_not_taken_for_having_none(self):
        got = b.collect(SPECS, {"FetchAndUpdateEvidenceV2": None, "FetchEvidence": "", "ExtractDataUsingJQV2": "y"})
        self.assertEqual(got["ruleReadmesUnchecked"], ["FetchAndUpdateEvidenceV2"])
        self.assertEqual(got["rulesWithoutReadme"], ["FetchEvidence"])
        self.assertEqual(list(got["ruleReadmes"]), ["ExtractDataUsingJQV2"])

    def test_a_rule_missing_from_the_lookup_counts_as_unchecked(self):
        got = b.collect(SPECS, {})
        self.assertEqual(got["ruleReadmesUnchecked"], ["ExtractDataUsingJQV2", "FetchAndUpdateEvidenceV2", "FetchEvidence"])

    def test_the_readmes_are_listed_in_rule_name_order(self):
        got = b.collect(SPECS, {"FetchAndUpdateEvidenceV2": "a", "FetchEvidence": "b", "ExtractDataUsingJQV2": "c"})
        self.assertEqual(list(got["ruleReadmes"]), ["ExtractDataUsingJQV2", "FetchAndUpdateEvidenceV2", "FetchEvidence"])


class ReadmeOf(unittest.TestCase):
    def test_the_readme_of_the_named_rule(self):
        self.assertEqual(r.readme_of("A", [catalog_row("B", "other"), catalog_row("A", "mine")]), "mine")

    def test_none_when_the_rule_has_no_readme_or_is_not_there(self):
        self.assertIsNone(r.readme_of("A", [catalog_row("A")]))
        self.assertIsNone(r.readme_of("A", []))
        self.assertIsNone(r.readme_of("A", None))

    def test_the_other_copy_supplies_the_readme_when_the_listed_one_has_none(self):
        copies = [catalog_row("A", "from the untagged copy", tags=()), catalog_row("A", None, tags=("MCP",))]
        self.assertEqual(r.readme_of("A", copies), "from the untagged copy")


    def test_the_copy_discovery_lists_wins_when_both_copies_have_one(self):
        copies = [catalog_row("A", "untagged", tags=()), catalog_row("A", "tagged", tags=("MCP",))]
        self.assertEqual(r.readme_of("A", copies), "tagged")


class TheTool(unittest.TestCase):
    def run_tool(self, rows_by_name, **kwargs):
        asked = []

        async def api(uri, method=None, request_body=None, **_):
            if uri == tool.constants.URL_FETCH_RULES:
                asked.append(request_body)
                rows = rows_by_name.get(request_body["name"])
                return {"error": "502"} if rows is None else {"items": rows}
            return {"items": {"Folder": {"config": {"metadata": {"name": "Parent"}, "spec": SPECS["Parent"]}}}, "totalItems": 1}

        with mock.patch.object(tool.utils, "make_API_call_to_CCow_and_get_response", api):
            return asyncio.run(tool.inspect_workflow_blueprint(name="Folder", **kwargs)), asked

    ROWS = {"FetchAndUpdateEvidenceV2": [catalog_row("FetchAndUpdateEvidenceV2", "Note: TicketID")], "FetchEvidence": [catalog_row("FetchEvidence")]}

    def test_it_returns_the_readmes_when_asked(self):
        report, asked = self.run_tool(self.ROWS, include_rule_readmes=True)
        self.assertEqual(report["ruleReadmes"], {"FetchAndUpdateEvidenceV2": {"usedBy": ["Parent"], "readme": "Note: TicketID"}})
        self.assertEqual(report["rulesWithoutReadme"], ["FetchEvidence"])
        self.assertEqual(report["ruleReadmesUnchecked"], [])
        self.assertTrue(all(a["include_read_me"] == "true" for a in asked))

    def test_by_default_it_reads_no_readme_and_adds_nothing(self):
        report, asked = self.run_tool(self.ROWS)
        self.assertEqual(asked, [])
        for key in ("ruleReadmes", "rulesWithoutReadme", "ruleReadmesUnchecked"):
            self.assertNotIn(key, report)

    def test_a_failed_lookup_is_unchecked(self):
        report, _ = self.run_tool({"FetchAndUpdateEvidenceV2": None, "FetchEvidence": []}, include_rule_readmes=True)
        self.assertEqual(report["ruleReadmesUnchecked"], ["FetchAndUpdateEvidenceV2"])
        self.assertEqual(report["rulesWithoutReadme"], ["FetchEvidence"])


if __name__ == "__main__":
    unittest.main()
