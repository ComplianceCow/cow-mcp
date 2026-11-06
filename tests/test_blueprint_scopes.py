import asyncio
import unittest
from unittest import mock

from tools.workflow import blueprint_scopes as s
from tools.workflow import workflow as tool


def rule_activity(name, scope="Blueprint scope"):
    reference = {"id": f"id-{name}", "name": name, "inputs": []}
    if scope:
        reference["appScopeName"] = scope
    return {"action": {"type": "Rule", "reference": reference}}


def spec_of(**activities):
    return {"activities": activities, "conditions": {}, "transitions": [], "states": {}}


def scope(*types):
    return {"types": set(types)}


ABSENT = {"types": None}


class Types(unittest.TestCase):
    def test_an_application_type_and_a_tag_are_the_same_type(self):
        self.assertEqual({s.normalize(x) for x in ("JiraCloud::", "jiracloud", " JIRACLOUD ", "JiraCloud::v2")}, {"jiracloud"})
        self.assertEqual(s.normalize(None), "")

    def test_a_rule_names_its_own_type_and_the_type_of_every_task(self):
        rule = {"meta": {"labels": {"appType": ["jiracloud"]}}, "spec": {"tasks": [{"appTags": {"appType": ["NoCredApp"]}}, {"appTags": {"appType": ["jiracloud"]}}, {"appTags": {"appType": ["compliancecow"]}}]}}
        self.assertEqual(s.rule_app_types(rule), {"jiracloud", "nocredapp", "compliancecow"})

    def test_a_task_type_counts_when_the_rule_has_no_label(self):
        self.assertEqual(s.rule_app_types({"spec": {"tasks": [{"appTags": {"appType": ["okta"]}}]}}), {"okta"})

    def test_a_label_given_as_text_and_missing_parts_do_not_break_it(self):
        self.assertEqual(s.rule_app_types({"meta": {"labels": {"appType": "Okta"}}, "spec": {"tasks": [None, {}, {"appTags": None}]}}), {"okta"})
        self.assertEqual(s.rule_app_types({}), set())


class Check(unittest.TestCase):
    def test_a_scope_with_an_application_for_every_type_is_fine(self):
        report = s.check(spec_of(A=rule_activity("FetchEvidence"), B=rule_activity("CreateJira")),
                         {"FetchEvidence": {"compliancecow"}, "CreateJira": {"jiracloud", "nocredapp"}}, {"Blueprint scope": scope("compliancecow", "jiracloud", "nocredapp")})
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["unchecked"], [])
        self.assertEqual(report["scopes"], [{"scope": "Blueprint scope", "needs": ["compliancecow", "jiracloud", "nocredapp"], "exists": True, "has": ["compliancecow", "jiracloud", "nocredapp"], "missing": []}])

    def test_a_type_the_scope_lacks_is_missing_and_names_the_rules_that_need_it(self):
        report = s.check(spec_of(A=rule_activity("FetchEvidence"), B=rule_activity("CreateJira")),
                         {"FetchEvidence": {"compliancecow"}, "CreateJira": {"jiracloud"}}, {"Blueprint scope": scope("jiracloud")})
        self.assertEqual(report["missing"], ["the application scope 'Blueprint scope' has no application of the type compliancecow (for FetchEvidence)"])
        self.assertEqual(report["scopes"][0]["missing"], ["compliancecow"])

    def test_a_scope_that_does_not_exist_is_missing_with_the_types_it_needs(self):
        report = s.check(spec_of(A=rule_activity("FetchEvidence"), B=rule_activity("CreateJira")),
                         {"FetchEvidence": {"compliancecow"}, "CreateJira": {"jiracloud"}}, {"Blueprint scope": ABSENT})
        self.assertEqual(len(report["missing"]), 1)
        self.assertIn("'Blueprint scope' does not exist", report["missing"][0])
        self.assertIn("compliancecow (for FetchEvidence); jiracloud (for CreateJira)", report["missing"][0])
        self.assertIs(report["scopes"][0]["exists"], False)

    def test_each_scope_is_checked_against_its_own_rules(self):
        report = s.check(spec_of(A=rule_activity("R1", "One"), B=rule_activity("R2", "Two")), {"R1": {"okta"}, "R2": {"jiracloud"}}, {"One": scope("okta"), "Two": scope("okta")})
        self.assertEqual(report["missing"], ["the application scope 'Two' has no application of the type jiracloud (for R2)"])

    def test_one_rule_used_twice_is_named_once(self):
        report = s.check(spec_of(A=rule_activity("R1"), B=rule_activity("R1")), {"R1": {"okta"}}, {"Blueprint scope": scope()})
        self.assertEqual(report["missing"], ["the application scope 'Blueprint scope' has no application of the type okta (for R1)"])

    def test_a_lookup_that_failed_is_unchecked_and_never_missing(self):
        report = s.check(spec_of(A=rule_activity("R1"), B=rule_activity("R2")), {"R1": None, "R2": {"okta"}}, {"Blueprint scope": None})
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["unchecked"], ["the application types of the rule 'R1'", "the application scope 'Blueprint scope'"])
        self.assertIsNone(report["scopes"][0]["exists"])

    def test_a_rule_with_no_scope_is_fine_when_it_needs_no_credential(self):
        report = s.check(spec_of(A=rule_activity("Convert", scope=None)), {"Convert": {"nocredapp"}}, {})
        self.assertEqual((report["missing"], report["scopes"]), ([], []))

    def test_a_rule_with_no_scope_that_needs_a_credential_is_missing(self):
        report = s.check(spec_of(A=rule_activity("CreateJira", scope=None)), {"CreateJira": {"jiracloud", "nocredapp"}}, {})
        self.assertEqual(report["missing"], ["rules without an application scope need applications: jiracloud (for CreateJira)"])

    def test_a_workflow_without_rules_needs_nothing(self):
        self.assertEqual(s.check(spec_of(), {}, {}), {"scopes": [], "missing": [], "unchecked": []})


class Lookups(unittest.TestCase):
    """The lookups against a stand-in for the platform."""

    def run_async(self, coroutine):
        return asyncio.run(coroutine)

    def test_a_catalog_rule_gives_its_types(self):
        item = {"meta": {"name": "R1", "labels": {"appType": ["jiracloud"]}}, "spec": {"tasks": [{"appTags": {"appType": ["nocredapp"]}}]}}

        async def api(uri, method=None, request_body=None, **_):
            return {"items": [{"meta": {"name": "Other"}}, item]}

        with mock.patch.object(tool.utils, "make_API_call_to_CCow_and_get_response", api):
            self.assertEqual(self.run_async(tool._rule_app_types("R1", None)), {"jiracloud", "nocredapp"})
            self.assertIsNone(self.run_async(tool._rule_app_types("Nope", None)))

    def test_a_rule_the_catalog_does_not_answer_for_is_unknown(self):
        async def api(uri, method=None, request_body=None, **_):
            return "boom"

        with mock.patch.object(tool.utils, "make_API_call_to_CCow_and_get_response", api):
            self.assertIsNone(self.run_async(tool._rule_app_types("R1", None)))

    def checks(self, rule_types, scopes, specs):
        async def rules(name, ctx):
            return rule_types[name]

        async def found(name, ctx):
            return scopes[name]

        with mock.patch.object(tool, "_rule_app_types", rules), mock.patch.object(tool, "_scope_found", found):
            return self.run_async(tool._scope_checks_for(specs, None))

    def test_every_workflow_is_checked_with_each_lookup_made_once(self):
        calls = []

        async def rules(name, ctx):
            calls.append(("rule", name))
            return {"okta"}

        async def found(name, ctx):
            calls.append(("scope", name))
            return scope("okta")

        specs = {"W1": spec_of(A=rule_activity("R1")), "W2": spec_of(A=rule_activity("R1"), B=rule_activity("R2"))}
        with mock.patch.object(tool, "_rule_app_types", rules), mock.patch.object(tool, "_scope_found", found):
            result = self.run_async(tool._scope_checks_for(specs, None))
        self.assertEqual(sorted(calls), [("rule", "R1"), ("rule", "R2"), ("scope", "Blueprint scope")])
        self.assertEqual({n: r["missing"] for n, r in result.items()}, {"W1": [], "W2": []})

    def test_a_lookup_that_raises_is_unchecked(self):
        async def rules(name, ctx):
            raise RuntimeError("down")

        async def found(name, ctx):
            raise RuntimeError("down")

        with mock.patch.object(tool, "_rule_app_types", rules), mock.patch.object(tool, "_scope_found", found):
            result = self.run_async(tool._scope_checks_for({"W": spec_of(A=rule_activity("R1"))}, None))["W"]
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["unchecked"], ["the application types of the rule 'R1'"])


class TheScopeLookup(unittest.TestCase):
    def lookup(self, scopes, applications):
        class Applications:
            async def list_application_scopes(self, name=None, ctx=None):
                return scopes

            async def list_applications(self, id=None, ctx=None):
                return applications(id)

        import sys
        import types

        module = types.ModuleType("tools.applications.applications")
        impl = Applications()
        module.list_application_scopes, module.list_applications = impl.list_application_scopes, impl.list_applications
        with mock.patch.dict(sys.modules, {"tools.applications.applications": module}), mock.patch("tools.applications.applications", module, create=True):
            return asyncio.run(tool._scope_found("Scope", None))

    def test_the_types_of_the_applications_in_the_scope(self):
        types_by_id = {"a1": "JiraCloud::", "a2": "NoCredApp::"}
        result = self.lookup({"items": [{"name": "Other", "applications": []}, {"name": "Scope", "applications": ["a1", "a2"]}]},
                             lambda i: {"applications": [{"applicationId": i, "applicationType": types_by_id[i]}]})
        self.assertEqual(result, {"types": {"jiracloud", "nocredapp"}})

    def test_a_scope_that_is_not_there(self):
        self.assertEqual(self.lookup({"items": [{"name": "Other", "applications": []}]}, lambda i: {}), {"types": None})

    def test_an_error_from_the_platform_is_unknown(self):
        self.assertIsNone(self.lookup({"error": "Facing internal error"}, lambda i: {}))

    def test_an_application_that_cannot_be_read_makes_the_scope_unknown(self):
        self.assertIsNone(self.lookup({"items": [{"name": "Scope", "applications": ["a1"]}]}, lambda i: {"error": "x"}))


class TheTools(unittest.TestCase):
    """create_workflow_from_blueprint and inspect_workflow_blueprint with the scope check."""

    def doc(self):
        return {"metadata": {"name": "Playbook"}, "spec": spec_of(Fetch=rule_activity("FetchEvidence"), Jira=rule_activity("CreateJira"))}

    def create(self, scope_report, **kwargs):
        posts = []

        async def api(uri, method=None, request_body=None, **_):
            if method == "GET":
                return {"items": {"Folder": {"config": self.doc()}}, "totalItems": 1}
            posts.append(request_body)
            return {"status": {"id": "00000001-0000-0000-0000-000000000000"}}

        async def get(uri, ctx=None):
            return {"items": []}

        async def nothing_missing(specs, ctx):
            return {name: {"events": [], "rules": [], "functions": [], "missing": [], "unchecked": [], "publishedOnCreate": []} for name in specs}

        async def events(ctx):
            return []

        seen = []

        async def scoped(specs, ctx):
            seen.append(specs)
            return {name: scope_report for name in specs}

        with mock.patch.object(tool.utils, "make_API_call_to_CCow_and_get_response", api), mock.patch.object(tool.utils, "make_GET_API_call_to_CCow", get), \
                mock.patch.object(tool, "_prerequisites_for", nothing_missing), mock.patch.object(tool, "_tenant_events", events), mock.patch.object(tool, "_scope_checks_for", scoped):
            result = asyncio.run(tool.create_workflow_from_blueprint(name="Folder", new_name="New", **kwargs))
        return result, posts, seen

    def test_a_missing_scope_stops_the_creation_and_says_what_is_missing(self):
        report = {"scopes": [{"scope": "Blueprint scope", "exists": False}], "missing": ["the application scope 'Blueprint scope' does not exist"], "unchecked": []}
        result, posts, _ = self.create(report, dry_run=False)
        self.assertFalse(result["success"])
        self.assertFalse(result["ready"])
        self.assertIn("the application scope 'Blueprint scope' does not exist", result["problems"])
        self.assertEqual(result["applicationScope"], report["scopes"])
        self.assertEqual(posts, [])

    def test_a_scope_that_covers_the_rules_lets_it_through(self):
        report = {"scopes": [{"scope": "Blueprint scope", "exists": True, "missing": []}], "missing": [], "unchecked": []}
        result, posts, _ = self.create(report, dry_run=False)
        self.assertTrue(result["success"], result)
        self.assertEqual(len(posts), 3)

    def test_the_scope_is_checked_after_the_replacements_not_before(self):
        replace = [{"from": "Blueprint scope", "to": "Okta flow scope"}]
        result, _, seen = self.create({"scopes": [], "missing": [], "unchecked": []}, replacements=replace)
        self.assertEqual(sorted(seen[0].values())[0]["activities"]["Fetch"]["action"]["reference"]["appScopeName"], "Okta flow scope")

    def test_a_lookup_that_failed_is_reported_but_does_not_stop_it(self):
        report = {"scopes": [], "missing": [], "unchecked": ["the application scope 'Blueprint scope'"]}
        result, _, _ = self.create(report)
        self.assertEqual(result["applicationScopeUnchecked"], ["the application scope 'Blueprint scope'"])
        self.assertTrue(result["ready"])

    def test_the_check_can_be_turned_off(self):
        report = {"scopes": [], "missing": ["the application scope 'Blueprint scope' does not exist"], "unchecked": []}
        result, _, seen = self.create(report, check_application_scope=False)
        self.assertEqual(seen, [])
        self.assertTrue(result["ready"])
        self.assertNotIn("applicationScope", result)

    def test_inspect_reports_a_missing_scope_with_the_other_missing_things(self):
        async def api(uri, method=None, request_body=None, **_):
            return {"items": {"Folder": {"config": self.doc()}}, "totalItems": 1}

        async def nothing_missing(specs, ctx):
            return {name: {"events": [], "rules": [], "functions": [], "missing": [], "unchecked": [], "publishedOnCreate": []} for name in specs}

        async def scoped(specs, ctx):
            return {name: {"scopes": [{"scope": "S", "exists": False}], "missing": ["the application scope 'S' does not exist"], "unchecked": ["the application scope 'T'"]} for name in specs}

        with mock.patch.object(tool.utils, "make_API_call_to_CCow_and_get_response", api), mock.patch.object(tool, "_prerequisites_for", nothing_missing), mock.patch.object(tool, "_scope_checks_for", scoped):
            report = asyncio.run(tool.inspect_workflow_blueprint(name="Folder", check_tenant=True))
        self.assertEqual(report["prerequisitesMissing"], ["Playbook: the application scope 'S' does not exist"])
        self.assertEqual(report["prerequisitesUnchecked"], ["the application scope 'T'"])
        self.assertEqual(report["workflows"]["Playbook"]["applicationScope"], [{"scope": "S", "exists": False}])


if __name__ == "__main__":
    unittest.main()
