import asyncio
import copy
import unittest
from unittest import mock

import yaml

from tools.workflow import blueprint_apply as a
from tools.workflow import blueprint_prerequisites as p
from tools.workflow import workflow as tool

BLUEPRINT_ID = "59d0ced8-0000-0000-0000-00000000000a"
TENANT_ID = "11111111-2222-3333-4444-555555555555"


def custom(identifier=BLUEPRINT_ID, name="JiraEvidenceTicketProcessing", category="7"):
    return {"id": identifier, "type": "CUSTOM_EVENT", "displayable": name, "categoryId": category, "label": name, "orgId": "", "groupId": ""}


def doc():
    return {
        "metadata": {"name": "Child"},
        "spec": {
            "activities": {
                "Fetch": {"action": {"type": "Rule", "reference": {"id": "rule-1", "inputs": [
                    {"name": "DataFile", "mapValueFrom": {"type": "Event", "source": custom()}},
                    {"name": "Other", "mapValueFrom": {"type": "Event", "source": custom()}},
                ]}}},
            },
            "transitions": [{"from": "Start", "to": "Fetch", "type": "Event", "event": custom()}],
        },
    }


def tenant(identifier=TENANT_ID, category="7", **over):
    return [dict({"displayable": "JiraEvidenceTicketProcessing", "id": identifier, "type": "CUSTOM_EVENT", "categoryId": category}, **over)]


class Binding(unittest.TestCase):
    def test_every_use_of_the_event_is_pointed_at_the_tenants_own_event(self):
        work = doc()
        rebound = a.bind_events(work, tenant())
        self.assertEqual(rebound, [{"event": "JiraEvidenceTicketProcessing", "was": BLUEPRINT_ID, "now": TENANT_ID, "places": 3}])
        self.assertEqual(work["spec"]["transitions"][0]["event"]["id"], TENANT_ID)
        for item in work["spec"]["activities"]["Fetch"]["action"]["reference"]["inputs"]:
            self.assertEqual(item["mapValueFrom"]["source"]["id"], TENANT_ID)

    def test_it_stays_a_custom_event_with_everything_else_as_it_was(self):
        work = doc()
        a.bind_events(work, tenant())
        expected = doc()
        expected["spec"]["transitions"][0]["event"]["id"] = TENANT_ID
        for item in expected["spec"]["activities"]["Fetch"]["action"]["reference"]["inputs"]:
            item["mapValueFrom"]["source"]["id"] = TENANT_ID
        self.assertEqual(work, expected)
        self.assertEqual(work["spec"]["transitions"][0]["event"]["type"], "CUSTOM_EVENT")

    def test_the_category_follows_the_tenants_event(self):
        work = doc()
        a.bind_events(work, tenant(category="9"))
        self.assertEqual(work["spec"]["transitions"][0]["event"]["categoryId"], "9")

    def test_an_event_that_already_has_the_tenants_id_is_left_and_not_reported(self):
        work = doc()
        self.assertEqual(a.bind_events(work, tenant(identifier=BLUEPRINT_ID)), [])
        self.assertEqual(work, doc())

    def test_events_are_matched_by_name(self):
        work = doc()
        self.assertEqual(a.bind_events(work, tenant(displayable="Another event")), [])
        self.assertEqual(work, doc())

    def test_only_a_custom_event_is_rebound(self):
        for kind in ("RESOURCE_BASED_EVENT", "INTERIM_STATE_WAITER_EVENT"):
            work = doc()
            work["spec"]["transitions"][0]["event"]["type"] = kind
            expected = copy.deepcopy(work)
            a.bind_events(work, tenant())
            self.assertEqual(work["spec"]["transitions"][0]["event"], expected["spec"]["transitions"][0]["event"], kind)

    def test_a_tenant_event_of_another_type_with_the_same_name_is_not_used(self):
        work = doc()
        self.assertEqual(a.bind_events(work, tenant(type="RESOURCE_BASED_EVENT")), [])
        self.assertEqual(work, doc())

    def test_something_that_only_looks_like_an_event_is_left_alone(self):
        work = doc()
        del work["spec"]["transitions"][0]["event"]["type"]
        a.bind_events(work, tenant())
        self.assertEqual(work["spec"]["transitions"][0]["event"]["id"], BLUEPRINT_ID)

    def test_no_tenant_events_changes_nothing(self):
        work = doc()
        self.assertEqual(a.bind_events(work, []), [])
        self.assertEqual(work, doc())

    def test_a_tenant_event_without_an_id_is_not_used(self):
        work = doc()
        self.assertEqual(a.bind_events(work, tenant(identifier=None)), [])
        self.assertEqual(work, doc())

    def test_the_tenant_listing_carries_the_category(self):
        listing = {"customEvents": [{"id": "x", "displayable": "E", "type": "CUSTOM_EVENT", "categoryId": "7"}]}
        self.assertEqual(p.tenant_events(listing), [{"displayable": "E", "id": "x", "type": "CUSTOM_EVENT", "categoryId": "7"}])


class TheTool(unittest.TestCase):
    def run_tool(self, events, dry_run=False):
        posts = []
        folder = {"items": {"Folder": {"config": doc()}}, "totalItems": 1}

        async def api(uri, method=None, request_body=None, **extra):
            if method == "GET":
                return folder
            posts.append(request_body)
            return {"status": {"id": "00000001-0000-0000-0000-000000000000"}}

        async def get(uri, ctx=None):
            return {"items": []}

        async def nothing_missing(specs, ctx):
            return {name: {"events": [], "rules": [], "functions": [], "missing": [], "unchecked": [], "publishedOnCreate": []} for name in specs}

        async def tenant_events(ctx):
            return events

        with mock.patch.object(tool.utils, "make_API_call_to_CCow_and_get_response", api), mock.patch.object(tool.utils, "make_GET_API_call_to_CCow", get), \
                mock.patch.object(tool, "_prerequisites_for", nothing_missing), mock.patch.object(tool, "_tenant_events", tenant_events):
            result = asyncio.run(tool.create_workflow_from_blueprint(name="Folder", new_name="Okta child", dry_run=dry_run))
        return result, posts

    def test_the_workflow_is_created_with_the_tenants_event_and_says_so(self):
        result, posts = self.run_tool(tenant())
        self.assertTrue(result["success"], result)
        self.assertEqual(result["eventsRebound"], [{"event": "JiraEvidenceTicketProcessing", "was": BLUEPRINT_ID, "now": TENANT_ID, "places": 3}])
        sent = yaml.safe_load(posts[0])
        self.assertEqual(sent["spec"]["transitions"][0]["event"]["id"], TENANT_ID)
        self.assertNotIn(BLUEPRINT_ID, posts[0])

    def test_a_dry_run_reports_it_and_creates_nothing(self):
        result, posts = self.run_tool(tenant(), dry_run=True)
        self.assertEqual(len(result["eventsRebound"]), 1)
        self.assertEqual(posts, [])

    def test_when_the_tenants_events_cannot_be_read_the_definition_is_sent_as_it_is(self):
        result, posts = self.run_tool(None)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["eventsRebound"], [])
        self.assertIn(BLUEPRINT_ID, posts[0])


if __name__ == "__main__":
    unittest.main()
