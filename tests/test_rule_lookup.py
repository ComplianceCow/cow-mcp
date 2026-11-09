import asyncio
import base64
import unittest
from unittest import mock

from tools.workflow import rule_lookup as r
from tools.workflow import workflow as tool


def catalog_rule(name="FetchWorkdayWorkers", tags=("MCP",), label="HTTPRequest", tasks=("nocredapp",)):
    return {"meta": {"name": name, "purpose": "Fetch the workers", "description": "Workers from Workday", "tags": list(tags), "labels": {"appType": [label]}},
            "spec": {"tasks": [{"appTags": {"appType": [t]}} for t in tasks]}}


def tenant_rule(name="FetchWorkdayWorkers", app_type=("httprequest",), inputs=None, outputs=None):
    return {"name": name, "description": "from the tenant", "type": "rule", "tags": {"appType": list(app_type)}, "ruleInputs": inputs or {}, "ruleOutputs": outputs or {}}


def with_spec(rule, inputs_meta=None, inputs=None, outputs_meta=None, io_map=None, readme=None):
    rule["spec"].update({"inputsMeta__": inputs_meta, "inputs": inputs, "outputsMeta__": outputs_meta, "ioMap": io_map or []})
    if readme is not None:
        rule["readmeData"] = base64.b64encode(readme.encode()).decode()
    return rule


class Describe(unittest.TestCase):
    def test_a_rule_in_the_tenant_is_published(self):
        found = r.describe("FetchWorkdayWorkers", [tenant_rule()], [])
        self.assertEqual((found["success"], found["where"]), (True, "tenant"))

    def test_a_rule_only_in_the_catalog_is_published_when_the_workflow_is_created(self):
        found = r.describe("FetchWorkdayWorkers", [], [catalog_rule()])
        self.assertEqual((found["success"], found["where"]), (True, "catalog"))

    def test_a_rule_in_both_places_counts_as_published(self):
        self.assertEqual(r.describe("FetchWorkdayWorkers", [tenant_rule()], [catalog_rule()])["where"], "tenant")

    def test_a_rule_in_neither_place_is_missing(self):
        found = r.describe("Nope", [], [])
        self.assertEqual(found, {"success": False, "name": "Nope", "where": "missing"})

    def test_the_name_must_match_exactly(self):
        self.assertEqual(r.describe("FetchWorkday", [tenant_rule()], [catalog_rule()])["where"], "missing")

    def test_a_failed_lookup_is_not_taken_for_a_missing_rule(self):
        self.assertEqual(r.describe("X", None, [])["where"], "unchecked")
        self.assertEqual(r.describe("X", [], None)["where"], "unchecked")

    def test_a_rule_found_in_one_place_stands_when_the_other_lookup_failed(self):
        self.assertEqual(r.describe("FetchWorkdayWorkers", None, [catalog_rule()])["where"], "catalog")
        self.assertEqual(r.describe("FetchWorkdayWorkers", [tenant_rule()], None)["where"], "tenant")

    def test_application_types_cover_the_rule_label_and_every_task(self):
        found = r.describe("FetchWorkdayWorkers", [], [catalog_rule(label="JiraCloud::", tasks=("jiracloud", "nocredapp"))])
        self.assertEqual(found["appTypes"], ["jiracloud", "nocredapp"])

    def test_a_rule_only_in_the_tenant_takes_its_types_from_the_tenant_tags(self):
        self.assertEqual(r.describe("FetchWorkdayWorkers", [tenant_rule(app_type=("HTTPRequest",))], [])["appTypes"], ["httprequest"])

    def test_the_catalog_types_win_over_the_tenant_tags(self):
        found = r.describe("FetchWorkdayWorkers", [tenant_rule(app_type=("generic",))], [catalog_rule(label="JiraCloud", tasks=())])
        self.assertEqual(found["appTypes"], ["jiracloud"])

    def test_tags_in_an_unexpected_shape_give_no_types(self):
        row = tenant_rule()
        row["tags"] = "appType"
        self.assertEqual(r.describe("FetchWorkdayWorkers", [row], [])["appTypes"], [])

    def test_it_says_whether_the_rule_is_one_the_summary_lists(self):
        self.assertTrue(r.describe("FetchWorkdayWorkers", [], [catalog_rule(tags=("MCP",))])["discoverable"])
        self.assertFalse(r.describe("FetchWorkdayWorkers", [], [catalog_rule(tags=())])["discoverable"])
        self.assertIsNone(r.describe("FetchWorkdayWorkers", [tenant_rule()], [])["discoverable"])

    def test_a_rule_kept_in_two_catalogs_is_discoverable_when_either_copy_is_tagged(self):
        copies = [catalog_rule(tags=(), label="Other"), catalog_rule(tags=("MCP",), label="JiraCloud", tasks=())]
        found = r.describe("FetchWorkdayWorkers", [], copies)
        self.assertTrue(found["discoverable"])
        self.assertEqual(found["appTypes"], ["jiracloud"])
        self.assertTrue(r.describe("FetchWorkdayWorkers", [], copies[::-1])["discoverable"])

    def test_purpose_and_description_come_from_the_catalog_else_the_tenant(self):
        found = r.describe("FetchWorkdayWorkers", [tenant_rule()], [catalog_rule()])
        self.assertEqual((found["purpose"], found["description"]), ("Fetch the workers", "Workers from Workday"))
        found = r.describe("FetchWorkdayWorkers", [tenant_rule()], [])
        self.assertEqual((found["purpose"], found["description"]), (None, "from the tenant"))


class TheRuleInformation(unittest.TestCase):
    def test_the_readme_is_returned_as_text(self):
        found = r.describe("FetchWorkdayWorkers", [], [with_spec(catalog_rule(), readme="# Workers\nColumns: ID")])
        self.assertEqual(found["readme"], "# Workers\nColumns: ID")

    def test_a_rule_without_a_readme_says_so(self):
        self.assertIsNone(r.describe("FetchWorkdayWorkers", [tenant_rule()], [with_spec(catalog_rule())])["readme"])
        self.assertIsNone(r.describe("FetchWorkdayWorkers", [tenant_rule()], [])["readme"])

    def test_the_readme_is_taken_from_the_other_copy_when_the_preferred_one_has_none(self):
        copies = [with_spec(catalog_rule(tags=(), label="Other"), readme="from the untagged copy"), with_spec(catalog_rule(tags=("MCP",)))]
        self.assertEqual(r.describe("FetchWorkdayWorkers", [], copies)["readme"], "from the untagged copy")

    def test_the_preferred_copys_readme_wins(self):
        copies = [with_spec(catalog_rule(tags=(), label="Other"), readme="untagged"), with_spec(catalog_rule(tags=("MCP",)), readme="tagged")]
        self.assertEqual(r.describe("FetchWorkdayWorkers", [], copies)["readme"], "tagged")

    def test_a_readme_that_is_not_base64_is_skipped(self):
        broken = with_spec(catalog_rule())
        broken["readmeData"] = "***not base64***"
        self.assertIsNone(r.describe("FetchWorkdayWorkers", [], [broken])["readme"])

    def test_inputs_come_from_the_catalog_definition(self):
        rule = with_spec(catalog_rule(), inputs_meta=[{"name": "Users", "dataType": "FILE", "required": True}, {"name": "Days", "dataType": "INT"}])
        self.assertEqual(r.describe("FetchWorkdayWorkers", [], [rule])["inputs"], [
            {"name": "Users", "type": "FILE", "required": True}, {"name": "Days", "type": "INT", "required": False}])

    def test_an_input_known_only_by_name_is_still_listed(self):
        rule = with_spec(catalog_rule(), inputs={"Users": "<<MINIO_FILE_PATH>>"})
        self.assertEqual(r.describe("FetchWorkdayWorkers", [], [rule])["inputs"], [{"name": "Users", "type": None, "required": False}])

    def test_the_tenants_published_inputs_override_the_catalogs(self):
        rule = with_spec(catalog_rule(), inputs_meta=[{"name": "Users", "dataType": "FILE", "required": False}])
        row = tenant_rule(inputs={"Users": {"name": "Users", "type": "STRING", "isrequired": True, "defaultvalue": "x" * 500}})
        found = r.describe("FetchWorkdayWorkers", [row], [rule])
        self.assertEqual(found["inputs"], [{"name": "Users", "type": "STRING", "required": True}])

    def test_a_rule_only_in_the_tenant_lists_its_inputs_and_outputs(self):
        row = tenant_rule(inputs={"JQ": {"name": "JQ", "type": "STRING", "isrequired": True}}, outputs={"FinalOutput": {"type": "FILE"}, "LogFile": {}})
        found = r.describe("FetchWorkdayWorkers", [row], [])
        self.assertEqual(found["inputs"], [{"name": "JQ", "type": "STRING", "required": True}])
        self.assertEqual([o["name"] for o in found["outputs"]], ["FinalOutput", "LogFile"])

    def test_outputs_come_from_the_mapping_with_the_detail_from_the_metadata(self):
        rule = with_spec(catalog_rule(), io_map=["t1.Input.A:=*.Input.A", "*.Output.OktaLogs:=t1.Output.OktaLogs", "*.Output.LogFile:=t1.Output.LogFile"],
                         outputs_meta=[{"name": "OktaLogs", "dataType": "FILE", "description": "the logs"}])
        self.assertEqual(r.describe("FetchWorkdayWorkers", [], [rule])["outputs"], [
            {"name": "OktaLogs", "type": "FILE", "description": "the logs"}, {"name": "LogFile", "type": None, "description": None}])

    def test_an_output_in_two_places_is_listed_once(self):
        rule = with_spec(catalog_rule(), io_map=["*.Output.OktaLogs:=t1.Output.OktaLogs"], outputs_meta=[{"name": "OktaLogs", "dataType": "FILE"}])
        found = r.describe("FetchWorkdayWorkers", [tenant_rule(outputs={"OktaLogs": {}})], [rule])
        self.assertEqual([o["name"] for o in found["outputs"]], ["OktaLogs"])

    def test_a_failed_lookup_is_named_so_a_missing_readme_is_not_taken_for_none(self):
        self.assertEqual(r.describe("FetchWorkdayWorkers", [tenant_rule()], None)["lookupFailed"], ["catalog"])
        self.assertEqual(r.describe("FetchWorkdayWorkers", None, [catalog_rule()])["lookupFailed"], ["tenant"])
        self.assertEqual(r.describe("FetchWorkdayWorkers", [tenant_rule()], [catalog_rule()])["lookupFailed"], [])

    def test_a_rule_with_no_definition_has_empty_lists(self):
        found = r.describe("FetchWorkdayWorkers", [], [catalog_rule()])
        self.assertEqual((found["inputs"], found["outputs"]), ([], []))


class TheTool(unittest.TestCase):
    def run_tool(self, tenant, catalog, name="FetchWorkdayWorkers"):
        calls = []

        async def get(uri, ctx=None, query_params=None):
            calls.append(("tenant", uri, query_params))
            return tenant

        async def api(uri, method=None, request_body=None, **extra):
            calls.append(("catalog", uri, request_body))
            return catalog

        with mock.patch.object(tool.utils, "make_GET_API_call_to_CCow", get), mock.patch.object(tool.utils, "make_API_call_to_CCow_and_get_response", api):
            return asyncio.run(tool.find_rule_by_name(name=name)), calls

    def test_it_asks_the_tenant_and_the_catalog_for_the_name_without_the_discovery_tag(self):
        found, calls = self.run_tool({"items": [tenant_rule()]}, {"items": [catalog_rule(tags=())]})
        self.assertEqual(found["where"], "tenant")
        self.assertEqual(sorted(c[0] for c in calls), ["catalog", "tenant"])
        sent = {kind: params for kind, _, params in calls}
        self.assertEqual(sent["tenant"], {"name": "FetchWorkdayWorkers"})
        self.assertEqual(sent["catalog"], {"name": "FetchWorkdayWorkers", "include_read_me": "true"})
        for params in sent.values():
            self.assertNotIn("tags", params)

    def test_an_untagged_catalog_rule_is_found(self):
        found, _ = self.run_tool({"items": []}, {"items": [catalog_rule(tags=())]})
        self.assertEqual((found["where"], found["discoverable"]), ("catalog", False))

    def test_an_error_response_is_unchecked_not_missing(self):
        found, _ = self.run_tool({"error": "boom"}, "Bad gateway")
        self.assertEqual(found["where"], "unchecked")

    def test_both_empty_is_missing(self):
        found, _ = self.run_tool({"items": []}, {"items": []})
        self.assertEqual(found["where"], "missing")


if __name__ == "__main__":
    unittest.main()


class LocalCatalogRules(unittest.TestCase):
    def test_a_local_catalog_rule_without_a_readme_is_unvetted(self):
        local = catalog_rule("FetchOktaDeprovisionedUsersWithGroups")
        local["catalog"] = "localcatalog"
        found = r.describe(local["meta"]["name"], [], [local])
        self.assertEqual((found["catalogScope"], found["unvetted"]), ("local", True))

    def test_a_global_catalog_rule_is_not_unvetted_even_without_a_readme(self):
        glob = catalog_rule("GetOktaUsers")
        glob["catalog"] = "globalcatalog"
        found = r.describe("GetOktaUsers", [], [glob])
        self.assertEqual((found["catalogScope"], found["unvetted"]), ("global", False))

    def test_a_local_rule_with_a_readme_is_trusted(self):
        local = with_spec(catalog_rule("MyRule"), readme="# My rule")
        local["catalog"] = "localcatalog"
        self.assertFalse(r.describe("MyRule", [], [local])["unvetted"])
