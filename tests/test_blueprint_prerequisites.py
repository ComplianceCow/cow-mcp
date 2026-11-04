import asyncio
import unittest
from unittest import mock

from tests import blueprint_fixtures as fixtures
from tests.test_blueprint_apply import NEW_CHILD, blueprint, full
from tools.workflow import blueprint_inspect as b
from tools.workflow import blueprint_prerequisites as p
from tools.workflow import workflow as tool

JIRA_DIR = fixtures.jira_dir()


def rule(name, rid="r-1", scope="Scope A"):
    return {"action": {"type": "Rule", "reference": {"name": name, "id": rid, "appScopeName": scope, "inputs": []}}}


def function(name, displayable=None, fid="f-1"):
    return {"action": {"type": "Function", "reference": {"name": name, "id": fid, "displayable": displayable or name, "inputs": []}}}


def spec(**over):
    base = {
        "transitions": [{"from": "Start", "to": "A", "type": "Event", "event": {"id": "e-1", "displayable": "ChildEvent", "type": "CUSTOM_EVENT"}}],
        "activities": {"A": rule("FetchEvidence"), "B": rule("FetchEvidence"), "C": rule("ConvertFileFormatV2", "r-2"), "D": function("SetVariable")},
        "conditions": {"Is it": function("ValidateIfTodayIsWorkingDay", "Check the day", "f-2")},
        "states": {},
    }
    base.update(over)
    return base


EVENTS = [{"displayable": "ChildEvent", "id": "e-9", "type": "CUSTOM_EVENT"}]
FUNCTIONS = [{"name": "SetVariable", "displayable": "Set variable", "id": "f-1"}, {"name": "x", "displayable": "Check the day", "id": "f-2"}]
PLACES = {"FetchEvidence": "tenant", "ConvertFileFormatV2": "tenant"}


class Needs(unittest.TestCase):
    def test_each_thing_the_workflow_needs_is_listed_once(self):
        wanted = b.needs(spec())
        self.assertEqual([e["displayable"] for e in wanted["events"]], ["ChildEvent"])
        self.assertEqual([(r["name"], r["id"], r["appScope"]) for r in wanted["rules"]], [("FetchEvidence", "r-1", "Scope A"), ("ConvertFileFormatV2", "r-2", "Scope A")])
        self.assertEqual([f["name"] for f in wanted["functions"]], ["SetVariable", "ValidateIfTodayIsWorkingDay"])

    def test_workflows_and_tasks_are_not_rules(self):
        extra = {"W": {"action": {"type": "Workflow", "reference": {"name": "Child", "id": "c"}}}, "T": {"action": {"type": "Task", "reference": {"name": "Task1"}}}}
        wanted = b.needs(spec(activities=extra))
        self.assertEqual((wanted["rules"], [f["name"] for f in wanted["functions"]]), ([], ["ValidateIfTodayIsWorkingDay"]))


class TenantListings(unittest.TestCase):
    def test_system_and_custom_events_are_flattened(self):
        listing = {"systemEvents": [{"displayable": "Run done", "id": "1", "type": "RESOURCE_BASED_EVENT", "payload": [{"name": "runId"}]}], "customEvents": [{"displayable": "Mine", "id": "2", "type": "CUSTOM_EVENT"}]}
        self.assertEqual([(e["displayable"], e["type"]) for e in p.tenant_events(listing)], [("Run done", "RESOURCE_BASED_EVENT"), ("Mine", "CUSTOM_EVENT")])

    def test_functions_are_flattened_and_junk_gives_nothing(self):
        self.assertEqual(p.tenant_functions({"activities": [{"displayable": "Set variable", "name": "SetVariable", "id": "f"}]}), [{"name": "SetVariable", "displayable": "Set variable", "id": "f"}])
        for junk in (None, "text", {}, []):
            self.assertEqual(p.tenant_events(junk), [])


class Check(unittest.TestCase):
    def test_nothing_is_missing_when_the_tenant_has_it_all(self):
        report = p.check(spec(), EVENTS, FUNCTIONS, PLACES)
        self.assertEqual((report["missing"], report["unchecked"], report["publishedOnCreate"]), ([], [], []))
        self.assertEqual(report["events"][0]["tenantId"], "e-9")
        self.assertTrue(all(f["found"] for f in report["functions"]))

    def test_a_custom_event_that_does_not_exist_says_how_to_create_it(self):
        report = p.check(spec(), [], FUNCTIONS, PLACES)
        self.assertEqual(report["missing"], ["the custom event 'ChildEvent' does not exist in the tenant (create it with create_workflow_custom_event)"])

    def test_a_system_event_that_does_not_exist_cannot_be_created_and_says_nothing_about_it(self):
        sys_spec = spec(transitions=[{"from": "Start", "to": "A", "type": "Event", "event": {"displayable": "Run done", "type": "RESOURCE_BASED_EVENT"}}])
        self.assertEqual(p.check(sys_spec, [], FUNCTIONS, PLACES)["missing"], ["the event 'Run done' does not exist in the tenant"])

    def test_a_rule_only_in_the_catalog_is_published_on_creation_not_missing(self):
        report = p.check(spec(), EVENTS, FUNCTIONS, {**PLACES, "FetchEvidence": "catalog"})
        self.assertEqual((report["missing"], report["publishedOnCreate"]), ([], ["FetchEvidence"]))

    def test_a_rule_in_neither_place_is_missing(self):
        report = p.check(spec(), EVENTS, FUNCTIONS, {**PLACES, "ConvertFileFormatV2": "missing"})
        self.assertEqual(report["missing"], ["the rule 'ConvertFileFormatV2' is in neither the tenant nor the catalog"])

    def test_a_function_is_found_by_its_name_or_its_display_name(self):
        report = p.check(spec(), EVENTS, FUNCTIONS, PLACES)
        self.assertEqual([f["found"] for f in report["functions"]], [True, True])
        missing = p.check(spec(), EVENTS, FUNCTIONS[:1], PLACES)
        self.assertEqual(missing["missing"], ["the function 'ValidateIfTodayIsWorkingDay' does not exist in the tenant"])

    def test_a_lookup_that_failed_is_unchecked_and_never_reported_as_missing(self):
        report = p.check(spec(), None, None, {"FetchEvidence": "unchecked"})
        self.assertEqual(report["missing"], [])
        self.assertEqual(sorted(report["unchecked"]), sorted([
            "the event 'ChildEvent'", "the rule 'FetchEvidence'", "the rule 'ConvertFileFormatV2'", "the function 'SetVariable'", "the function 'ValidateIfTodayIsWorkingDay'",
        ]))

    def test_an_empty_listing_is_not_the_same_as_one_that_could_not_be_read(self):
        self.assertEqual(len(p.check(spec(), [], FUNCTIONS, PLACES)["missing"]), 1)

    def test_a_listing_with_nothing_in_it_at_all_is_taken_as_unreadable_because_a_platform_always_has_system_events(self):
        platform = Platform(tenant_rules={"FetchEvidence", "ConvertFileFormatV2"})
        platform.list_events = lambda ctx=None: asyncio.sleep(0, {"systemEvents": [], "customEvents": []})
        report = platform.run({"W": spec()})["W"]
        self.assertEqual(report["missing"], [])
        self.assertIn("the event 'ChildEvent'", report["unchecked"])


class Summarize(unittest.TestCase):
    def test_the_per_item_lists_become_counts_and_what_matters_stays(self):
        report = p.check(spec(), EVENTS, FUNCTIONS, {"FetchEvidence": "tenant", "ConvertFileFormatV2": "catalog"})
        self.assertEqual(p.summarize(report), {
            "events": "1 of 1 found", "rules": "2: 1 tenant, 1 catalog", "functions": "2 of 2 found",
            "publishedOnCreate": ["ConvertFileFormatV2"], "missing": [], "unchecked": [],
        })

    def test_what_is_missing_or_unchecked_is_named(self):
        summary = p.summarize(p.check(spec(), [], None, {"FetchEvidence": "missing", "ConvertFileFormatV2": "unchecked"}))
        self.assertEqual(summary["events"], "0 of 1 found")
        self.assertEqual(summary["rules"], "2: 1 missing, 1 unchecked")
        self.assertEqual(summary["functions"], "0 of 2 found")
        self.assertEqual(len(summary["missing"]), 2)
        self.assertTrue(any("function" in u for u in summary["unchecked"]))

    def test_a_workflow_with_no_rules_says_so(self):
        self.assertEqual(p.summarize(p.check(spec(activities={}, conditions={}), EVENTS, FUNCTIONS, {}))["rules"], "0")

    def test_the_summary_is_much_shorter_than_the_report(self):
        report = p.check(spec(), EVENTS, FUNCTIONS, PLACES)
        self.assertLess(len(str(p.summarize(report))), len(str(report)) / 2)


class Platform:
    """A stand-in for the platform lookups the tool makes."""

    def __init__(self, events=None, functions=None, tenant_rules=(), catalog_rules=(), events_fail=False, tenant_lookup_error=None, catalog_fail=False, catalog_returns_others=False):
        self.events = EVENTS if events is None else events
        self.functions = FUNCTIONS if functions is None else functions
        self.tenant_rules, self.catalog_rules = set(tenant_rules), set(catalog_rules)
        self.events_fail, self.tenant_lookup_error, self.catalog_fail = events_fail, tenant_lookup_error, catalog_fail
        self.catalog_returns_others = catalog_returns_others
        self.rule_lookups = []

    async def list_events(self, ctx=None):
        if self.events_fail:
            raise RuntimeError("down")
        return {"systemEvents": [{"displayable": "When an assessment run is completed", "id": "s-1", "type": "RESOURCE_BASED_EVENT", "payload": []}], "customEvents": self.events}

    async def list_functions(self, ctx=None):
        return {"activities": self.functions, "error": ""}

    async def fetch_rule(self, name, ctx=None):
        self.rule_lookups.append(name)
        if self.tenant_lookup_error:
            return {"rules": [], "error": self.tenant_lookup_error}
        if name in self.tenant_rules:
            return {"rules": [{"name": name}], "error": ""}
        return {"rules": [], "error": f"No workflow rule returned for name: {name}"}

    async def api(self, uri, method=None, request_body=None, **_):
        if uri == tool.constants.URL_FETCH_RULES:
            if self.catalog_fail:
                return {"error": "boom"}
            if self.catalog_returns_others:
                return {"items": [{"meta": {"name": "SomeOtherRule"}}]}
            return {"items": [{"meta": {"name": n}} for n in self.catalog_rules if n == request_body["name"]]}
        raise AssertionError(uri)

    def patched(self):
        return mock.patch.multiple(tool, list_workflow_events=self.list_events, list_workflow_functions=self.list_functions, fetch_workflow_rule=self.fetch_rule), \
            mock.patch.object(tool.utils, "make_API_call_to_CCow_and_get_response", self.api)

    def run(self, specs):
        first, second = self.patched()
        with first, second:
            return asyncio.run(tool._prerequisites_for(specs, None))


class TheLookups(unittest.TestCase):
    def test_a_rule_is_found_where_it_is(self):
        platform = Platform(tenant_rules={"FetchEvidence"}, catalog_rules={"ConvertFileFormatV2"})
        report = platform.run({"W": spec()})["W"]
        self.assertEqual({r["name"]: r["where"] for r in report["rules"]}, {"FetchEvidence": "tenant", "ConvertFileFormatV2": "catalog"})
        self.assertEqual((report["missing"], report["publishedOnCreate"]), ([], ["ConvertFileFormatV2"]))

    def test_a_rule_in_neither_place_is_missing(self):
        report = Platform(tenant_rules={"FetchEvidence"}).run({"W": spec()})["W"]
        self.assertEqual(report["missing"], ["the rule 'ConvertFileFormatV2' is in neither the tenant nor the catalog"])

    def test_a_catalog_that_answers_with_other_rules_does_not_count_as_having_it(self):
        report = Platform(tenant_rules={"FetchEvidence"}, catalog_returns_others=True).run({"W": spec()})["W"]
        self.assertEqual({r["name"]: r["where"] for r in report["rules"]}, {"FetchEvidence": "tenant", "ConvertFileFormatV2": "missing"})

    def test_a_failed_lookup_is_unchecked_not_missing(self):
        for platform in (Platform(tenant_lookup_error="A temporary server error occurred"), Platform(catalog_fail=True)):
            report = platform.run({"W": spec()})["W"]
            self.assertEqual([m for m in report["missing"] if "rule" in m], [], vars(platform))
            self.assertTrue(any("rule" in u for u in report["unchecked"]), vars(platform))

    def test_an_events_listing_that_fails_leaves_the_events_unchecked(self):
        report = Platform(events_fail=True, tenant_rules={"FetchEvidence", "ConvertFileFormatV2"}).run({"W": spec()})["W"]
        self.assertEqual(report["missing"], [])
        self.assertIn("the event 'ChildEvent'", report["unchecked"])

    def test_a_rule_used_by_several_workflows_is_looked_up_once(self):
        platform = Platform(tenant_rules={"FetchEvidence", "ConvertFileFormatV2"})
        platform.run({"W1": spec(), "W2": spec()})
        self.assertEqual(sorted(platform.rule_lookups), ["ConvertFileFormatV2", "FetchEvidence"])


class TheTools(unittest.TestCase):
    """The inspector and the create tool use the platform check."""

    def folder(self):
        child = {"metadata": {"name": "Child"}, "spec": {"activities": {}, "conditions": {}, "transitions": [], "states": {}}}
        return {"items": {"Folder": {"config": dict(blueprint(), subworkflow={"Child-Subworkflow": child})}}, "totalItems": 1}

    def run_tool(self, platform, function, **kwargs):
        posts = []

        async def api(uri, method=None, request_body=None, **extra):
            if uri == "/pc-api/v1/workflows":
                return self.folder()
            if uri == tool.constants.URL_FETCH_RULES:
                return await platform.api(uri, method, request_body)
            posts.append(uri)
            return {"status": {"id": f"{len(posts):08d}-0000-0000-0000-000000000000"}}

        async def get(uri, ctx=None):
            if uri.startswith("/v3/workflow-configs/"):
                return {"metadata": {"name": "Okta child"}} if uri.endswith(NEW_CHILD) else {"error": "not found"}
            return {"items": []}

        first, _ = platform.patched()
        with first, mock.patch.object(tool.utils, "make_API_call_to_CCow_and_get_response", api), mock.patch.object(tool.utils, "make_GET_API_call_to_CCow", get):
            return asyncio.run(function(name="Folder", **kwargs)), posts

    def create(self, platform, **kwargs):
        return self.run_tool(platform, tool.create_workflow_from_blueprint, **{**full(), **kwargs})

    def test_a_missing_custom_event_stops_the_creation_and_says_how_to_fix_it(self):
        child_event = {"displayable": "ChildEvent", "type": "CUSTOM_EVENT"}
        platform = Platform(events=[], tenant_rules={"ExtractDataUsingJQV2"})
        with mock.patch.object(tool.blueprint_inspect, "needs", lambda s: {"events": [dict(child_event, id="e")], "rules": [], "functions": []}):
            result, posts = self.create(platform, dry_run=False)
        self.assertFalse(result["success"])
        self.assertEqual(posts, [])
        self.assertEqual(result["prerequisites"]["missing"], ["the custom event 'ChildEvent' does not exist in the tenant (create it with create_workflow_custom_event)"])
        self.assertIn(result["prerequisites"]["missing"][0], result["problems"])

    def test_a_rule_only_in_the_catalog_does_not_stop_the_creation(self):
        result, posts = self.create(Platform(catalog_rules={"ExtractDataUsingJQV2"}), dry_run=False)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["prerequisites"]["publishedOnCreate"], ["ExtractDataUsingJQV2"])
        self.assertEqual(len(posts), 3)

    def test_a_rule_in_neither_place_stops_the_creation(self):
        result, posts = self.create(Platform(), dry_run=False)
        self.assertFalse(result["success"])
        self.assertEqual(posts, [])
        self.assertIn("the rule 'ExtractDataUsingJQV2' is in neither the tenant nor the catalog", result["problems"])

    def test_a_dry_run_reports_the_prerequisites_too(self):
        result, posts = self.create(Platform(tenant_rules={"ExtractDataUsingJQV2"}))
        self.assertTrue(result["dryRun"] and result["ready"], result)
        self.assertEqual(result["prerequisites"]["missing"], [])
        self.assertEqual(sorted(result["prerequisites"]), ["events", "functions", "missing", "publishedOnCreate", "rules", "unchecked"])
        self.assertIsInstance(result["prerequisites"]["rules"], str)
        self.assertEqual(posts, [])

    def test_the_check_can_be_turned_off(self):
        platform = Platform()
        result, _ = self.create(platform, check_prerequisites=False)
        self.assertEqual(platform.rule_lookups, [])
        self.assertNotIn("prerequisites", result)
        self.assertTrue(result["ready"], result)

    def test_the_inspector_checks_the_tenant_only_when_asked_and_names_the_workflow_of_each_missing_thing(self):
        platform = Platform(tenant_rules={"ExtractDataUsingJQV2"}, events=[])
        quiet, _ = self.run_tool(platform, tool.inspect_workflow_blueprint)
        self.assertNotIn("prerequisitesMissing", quiet)
        self.assertEqual(platform.rule_lookups, [])
        child_event = {"displayable": "ChildEvent", "type": "CUSTOM_EVENT", "id": "e"}
        with mock.patch.object(tool.blueprint_inspect, "needs", lambda s: {"events": [child_event] if s.get("activities") else [], "rules": [], "functions": []}):
            checked, _ = self.run_tool(platform, tool.inspect_workflow_blueprint, check_tenant=True)
        self.assertTrue(all("prerequisites" in w for w in checked["workflows"].values()))
        self.assertTrue(all(isinstance(w["prerequisites"]["events"], str) for w in checked["workflows"].values()))
        self.assertEqual(checked["prerequisitesMissing"], ["Playbook: the custom event 'ChildEvent' does not exist in the tenant (create it with create_workflow_custom_event)"])


@unittest.skipUnless(JIRA_DIR, fixtures.HINT)
class RealJiraBlueprint(unittest.TestCase):
    def test_every_workflow_of_the_real_blueprint_names_what_it_needs(self):
        config, subs = fixtures.load_jira(JIRA_DIR)
        for doc in [config, *subs.values()]:
            wanted = b.needs(doc["spec"])
            self.assertTrue(wanted["events"] and wanted["rules"], doc["metadata"]["name"])
            self.assertTrue(all(r["name"] and r["id"] for r in wanted["rules"]))
            self.assertTrue(all(e["type"] for e in wanted["events"]))


if __name__ == "__main__":
    unittest.main()
