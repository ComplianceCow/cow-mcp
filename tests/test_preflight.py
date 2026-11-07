import asyncio
import unittest

from tools.playbook import preflight as p


def app(name, app_type, validated=True, cred="APIKey"):
    return {"id": name, "credentialName": name, "appType": f"{app_type}::", "credentialType": cred, "isValidated": validated}


def plan(name, kind="generic", category="Integrations"):
    return {"id": name, "name": name, "type": kind, "categoryName": category}


def workflow(name):
    return {"status": {"id": name + "-id"}, "metadata": {"name": name}}


IDENTITY = {"domainName": "uat", "username": "Test User", "AuthToken": "never-copied"}


class Summarize(unittest.TestCase):
    def test_an_empty_tenant_is_reported_as_empty(self):
        got = p.summarize(IDENTITY, [], [], [], [{"name": "Integrations"}], [], [])
        self.assertTrue(got["isEmpty"])
        self.assertEqual(got["counts"], {"applications": 0, "applicationScopes": 0, "assessments": 0, "workflows": 0})
        self.assertEqual(got["categories"], ["Integrations"])
        self.assertEqual(got["tenant"], {"domain": "uat", "user": "Test User"})

    def test_the_token_never_appears_in_the_answer(self):
        self.assertNotIn("never-copied", str(p.summarize(IDENTITY, [], [], [], [], [], [])))

    def test_two_okta_applications_of_different_types_are_both_listed_by_type(self):
        apps = [app("Connect Okta application", "HttpRequest"), app("Connect Okta application via OktaConeector", "OktaConnector")]
        got = p.summarize(IDENTITY, apps, [], [], [], [], [])
        self.assertEqual(got["applicationsByType"], {"HttpRequest": ["Connect Okta application"], "OktaConnector": ["Connect Okta application via OktaConeector"]})
        self.assertFalse(got["isEmpty"])
        self.assertTrue(any("name and its type" in n for n in got["notes"]))

    def test_unvalidated_applications_are_called_out_but_a_no_credential_app_is_not(self):
        apps = [app("Jira", "JiraCloud", validated=False), app("NoCredApp", "NoCredApp", validated=False, cred="NoCred"), app("Workday", "HttpRequest")]
        notes = " ".join(p.summarize(IDENTITY, apps, [], [], [], [], [])["notes"])
        self.assertIn("Jira", notes)
        self.assertNotIn("NoCredApp,", notes)
        self.assertNotIn("Workday", notes.split("without validated credentials")[-1])

    def test_assessments_are_split_into_l1_assets_and_l2_l3_assessments(self):
        got = p.summarize(IDENTITY, [], [], [plan("Okta", "integration"), plan("NIST 800-53 v5", "generic", "Playbook case - 1")], [], [], [])
        self.assertEqual([(a["name"], a["level"]) for a in got["assessments"]], [("Okta", "L1 asset"), ("NIST 800-53 v5", "L2/L3 assessment")])

    def test_workflows_say_whether_they_have_a_binding(self):
        got = p.summarize(IDENTITY, [], [], [], [], [workflow("WF1"), workflow("WF2")], [workflow("WF1")])
        self.assertEqual([(w["name"], w["hasBinding"]) for w in got["workflows"]], [("WF1", True), ("WF2", False)])
        self.assertTrue(any("conflicts" in n for n in got["notes"]))

    def test_a_failed_lookup_is_unknown_not_empty(self):
        got = p.summarize(IDENTITY, None, [], [], [], [], None, [])
        self.assertEqual(got["lookupFailed"], ["applications", "workflowBindings"])


def config(name, *credentials, display=None):
    return {"meta": {"name": name, "displayName": display}, "spec": {"credentialTypes": [{"name": n, "version": v} for n, v in credentials]}}


def config_with_status(name, *pairs):
    return {"meta": {"name": name}, "spec": {"credentialTypes": None}, "status": {"internal": {"credentialTypes": [list(p) for p in pairs]}}}


class AvailableTypes(unittest.TestCase):
    def test_each_type_lists_its_credential_types_as_name_and_version(self):
        got = p.summarize(IDENTITY, [], [], [], [], [], [], [config("HttpRequest", ("BearerToken", "1.1.1"), ("APIKey", "1.1.2")), config("NoCredApp", ("NoCred", "1.1.1"))])
        self.assertEqual(got["availableApplicationTypes"][0], {"name": "HttpRequest", "displayName": None, "credentialTypes": ["BearerToken 1.1.1", "APIKey 1.1.2"]})
        self.assertEqual([t["name"] for t in got["availableApplicationTypes"]], ["HttpRequest", "NoCredApp"])
        self.assertTrue(any("not installed here" in n for n in got["notes"]))

    def test_a_failed_lookup_is_unknown_and_gives_no_claim_about_missing_types(self):
        got = p.summarize(IDENTITY, [], [], [], [], [], [], None)
        self.assertIn("availableApplicationTypes", got["lookupFailed"])
        self.assertFalse(any("not installed here" in n for n in got["notes"]))

    def test_credential_types_given_as_pairs_in_the_status_are_read(self):
        got = p.application_types_of([config_with_status("HttpRequest", ("BearerToken", "1.1.1"), ("APIKey", "1.1.1"))])
        self.assertEqual(got[0]["credentialTypes"], ["BearerToken 1.1.1", "APIKey 1.1.1"])

    def test_a_type_listed_more_than_once_is_merged(self):
        got = p.application_types_of([config_with_status("ComplianceCow", ("OAuth", "1.1.1")), config_with_status("ComplianceCow", ("OAuth", "1.1.1")), config_with_status("ComplianceCow", ("Basic", "2.0.0"))])
        self.assertEqual(got, [{"name": "ComplianceCow", "displayName": None, "credentialTypes": ["OAuth 1.1.1", "Basic 2.0.0"]}])

    def test_a_config_without_a_name_is_skipped(self):
        self.assertEqual(p.application_types_of([{"meta": {}}, config("X")]), [{"name": "X", "displayName": None, "credentialTypes": []}])


def control(number, name):
    return {"displayable": number, "name": name}


class ControlTree(unittest.TestCase):
    def test_controls_are_listed_in_number_order_with_parents_included(self):
        got = p.control_tree([control("3.2", "b"), control("1", "p"), control("1.1", "c"), control("3", "q"), control("3.10", "z"), control("3.9", "y")])
        self.assertEqual([c["number"] for c in got["controls"]], ["1", "1.1", "3", "3.2", "3.9", "3.10"])

    def test_the_next_free_number_under_each_parent(self):
        got = p.control_tree([control("1", "p"), control("1.1", "c"), control("3", "q"), control("3.1", "d"), control("3.2", "e")])
        self.assertEqual(got["nextFreeNumber"][""], "4")
        self.assertEqual(got["nextFreeNumber"]["1"], "1.2")
        self.assertEqual(got["nextFreeNumber"]["3"], "3.3")

    def test_a_gap_is_not_filled_the_number_after_the_highest_is_offered(self):
        got = p.control_tree([control("1", "p"), control("1.1", "a"), control("1.4", "b")])
        self.assertEqual(got["nextFreeNumber"]["1"], "1.5")

    def test_an_empty_assessment_starts_at_one(self):
        self.assertEqual(p.control_tree([])["nextFreeNumber"], {"": "1"})

    def test_the_alias_stands_in_for_a_missing_displayable(self):
        self.assertEqual(p.control_tree([{"alias": "2", "name": "x"}])["controls"], [{"number": "2", "name": "x"}])


class Rows(unittest.TestCase):
    def test_items_are_returned(self):
        self.assertEqual(p.rows_of({"items": [{"a": 1}], "TotalPage": 1}), [{"a": 1}])

    def test_a_plain_list_is_returned(self):
        self.assertEqual(p.rows_of([{"a": 1}, "x"]), [{"a": 1}])

    def test_error_shapes_are_none(self):
        for bad in ("Facing error  :  timeout", {"error": "Unexpected response status: 500"}, {"items": [], "error": "x"}, None):
            self.assertIsNone(p.rows_of(bad), bad)


class FetchAll(unittest.TestCase):
    def run_fetch(self, pages):
        seen = []

        async def get(path, query):
            seen.append(query["page"])
            return pages[query["page"] - 1]

        return asyncio.run(p.fetch_all(get, "/x")), seen

    def test_every_page_is_read(self):
        rows, seen = self.run_fetch([{"items": [{"n": 1}], "TotalPage": 2}, {"items": [{"n": 2}], "TotalPage": 2}])
        self.assertEqual(rows, [{"n": 1}, {"n": 2}])
        self.assertEqual(seen, [1, 2])

    def test_a_response_without_page_info_is_a_single_page(self):
        rows, seen = self.run_fetch([{"items": [{"n": 1}]}])
        self.assertEqual((rows, seen), ([{"n": 1}], [1]))

    def test_a_failing_page_makes_the_whole_list_unknown(self):
        rows, _ = self.run_fetch([{"items": [{"n": 1}], "TotalPage": 2}, {"error": "boom"}])
        self.assertIsNone(rows)


if __name__ == "__main__":
    unittest.main()
