import asyncio
import unittest
from unittest import mock

from tests import blueprint_fixtures as fixtures
from tools.workflow import blueprint_inspect as b
from tools.workflow import workflow as tool

JIRA_DIR = fixtures.jira_dir()


def call(name, event, wait=False, inputs=None):
    return {"action": {
        "type": "Workflow",
        "asyncActionExecution": not wait,
        "reference": {"id": f"id-of-{name}", "name": name, "eventName": event, "inputs": inputs or []},
    }}


def workflow(name, activities=None, conditions=None, transitions=None):
    return {
        "metadata": {"name": name, "description": f"about {name}"},
        "spec": {"activities": activities or {}, "conditions": conditions or {}, "transitions": transitions or [], "states": {}},
    }


def chain(root, others):
    library = {d["metadata"]["name"]: d for d in [root, *others]}
    return b.chain_of(root, library)


class Literals(unittest.TestCase):
    def test_quoted_values_are_found_and_run_time_references_are_not(self):
        expr = 'assessmentName == "AC-UC-003" || x.contains(\'Company\') || {{Activity.A.Out}} == "{{Variable.v}}" || y == "{{Event.E.name}}"'
        self.assertEqual(b.literals_in(expr), ["AC-UC-003", "Company"])

    def test_empty_strings_are_not_values(self):
        self.assertEqual(b.literals_in('a == ""'), [])


class Triggers(unittest.TestCase):
    def test_each_event_transition_is_reported_with_its_filter_values_and_payload(self):
        doc = workflow("W", transitions=[
            {"from": "Start", "to": "A", "type": "Event", "event": {
                "displayable": "When a run completes", "type": "RESOURCE_BASED_EVENT",
                "desc": "Filters the runs that start this workflow.", "specInput": {"expr": 'assessmentName == "Okta MFA"'},
                "payload": [{"name": "assessmentName", "type": "Text", "desc": "The name of the assessment."}, {"name": "runId", "type": "Text"}]}},
            {"from": "S", "to": "B", "type": "Event", "event": {"displayable": "After days", "type": "INTERIM_STATE_WAITER_EVENT", "specInput": {"numberOfDays": 1}}},
            {"from": "A", "to": "End", "type": "PassThrough"},
        ])
        found = b.triggers(doc["spec"])
        self.assertEqual([t["event"] for t in found], ["When a run completes", "After days"])
        self.assertEqual(found[0]["literals"], ["Okta MFA"])
        self.assertEqual(found[0]["desc"], "Filters the runs that start this workflow.")
        self.assertEqual(found[0]["payload"], [{"name": "assessmentName", "type": "Text", "desc": "The name of the assessment."}, {"name": "runId", "type": "Text", "desc": None}])
        self.assertEqual(found[1]["literals"], [])


class Children(unittest.TestCase):
    def test_a_workflow_activity_is_reported_with_how_it_is_started_and_where_its_inputs_come_from(self):
        inputs = [
            {"name": "EvidenceName", "type": "Text", "desc": "d", "mapValueFrom": {"outputField": "ExtractedValue", "source": {"label": "Extract Evidence Name"}}},
            {"name": "Fixed", "type": "Text", "value": "x"},
        ]
        doc = workflow("W", activities={"Trigger WF2": call("WF2", "ProcessEvidence", inputs=inputs)})
        (child,) = b.children(doc["spec"])
        self.assertEqual((child["activity"], child["name"], child["id"], child["eventName"], child["async"]), ("Trigger WF2", "WF2", "id-of-WF2", "ProcessEvidence", True))
        self.assertEqual(child["inputs"][0]["from"], "Extract Evidence Name")
        self.assertEqual(child["inputs"][0]["outputField"], "ExtractedValue")
        self.assertIsNone(child["inputs"][1]["from"])

    def test_a_synchronous_call_is_not_async(self):
        doc = workflow("W", activities={"A": call("WF2", "E", wait=True)})
        self.assertFalse(b.children(doc["spec"])[0]["async"])

    def test_rules_and_functions_are_not_workflows(self):
        doc = workflow("W", activities={"R": {"action": {"type": "Rule", "reference": {"name": "ExtractDataUsingJQV2"}}}})
        self.assertEqual(b.children(doc["spec"]), [])


class FixedFiles(unittest.TestCase):
    def activity(self, inputs, desc=None):
        return workflow("W", activities={"Fetch config": {"action": {"type": "Rule", "desc": desc, "reference": {"appScopeName": "Scope A", "inputs": inputs}}}})["spec"]

    def test_only_a_file_with_content_of_its_own_is_fixed(self):
        spec = self.activity([
            {"name": "JQConfigFile", "type": "File", "value": "8cbccc", "fileName": "Generate-AC-UC-003.toml"},
            {"name": "InputFile", "type": "File", "value": "stale-hash", "mapValueFrom": {"outputField": "Out", "source": {"label": "Earlier"}}},
            {"name": "EmptyFile", "type": "File"},
            {"name": "Query", "type": "Text", "value": "x"},
        ], desc="Sample {a: 1}")
        (found,) = b.fixed_files(spec)
        self.assertEqual((found["activity"], found["input"], found["fileName"], found["value"], found["activityDesc"]), ("Fetch config", "JQConfigFile", "Generate-AC-UC-003.toml", "8cbccc", "Sample {a: 1}"))

    def test_app_scopes_are_listed_once(self):
        spec = workflow("W", activities={
            "A": {"action": {"reference": {"appScopeName": "Scope A"}}},
            "B": {"action": {"reference": {"appScopeName": "Scope A"}}},
            "C": {"action": {"reference": {"appScopeName": "Scope B"}}},
            "D": {"action": {"reference": {}}},
        })["spec"]
        self.assertEqual(b.app_scopes(spec), ["Scope A", "Scope B"])


class Templates(unittest.TestCase):
    def test_a_sample_in_the_node_description_or_a_file_description_is_a_template(self):
        spec = workflow("W", activities={
            "Sampled": {"action": {"desc": 'Config: {"EvidenceName": "x"}', "reference": {"inputs": []}}},
            "Plain": {"action": {"desc": "Fetches a file.", "reference": {"inputs": []}}},
            "Inputs": {"action": {"reference": {"inputs": [
                {"name": "Upload", "type": "File", "desc": "The JSON file with one entry per evidence; keep the keys of the example below as they are."},
                {"name": "Log", "type": "File", "desc": "Log file."},
                {"name": "Hint", "type": "Text", "desc": "Use this structure: a,b"},
                {"name": "Json", "type": "Text", "desc": 'Shape {"a": 1}'},
                {"name": "Long", "type": "Text", "desc": "x" * 300},
                {"name": "Mapped", "type": "File", "desc": "template", "mapValueFrom": {"outputField": "o", "source": {"label": "L"}}},
            ]}}},
        })["spec"]
        found = [(t["activity"], t["source"], t.get("input")) for t in b.templates(spec)]
        self.assertEqual(found, [("Sampled", "activity", None), ("Inputs", "input", "Upload"), ("Inputs", "input", "Hint"), ("Inputs", "input", "Json")])


class Rules(unittest.TestCase):
    def rule(self, name, scope="ScopeA"):
        return {"action": {"type": "Rule", "reference": {"id": f"id-{name}", "name": name, "appScopeName": scope, "inputs": []}}}

    def test_the_rules_the_workflow_runs_are_listed_once_each_by_name(self):
        doc = workflow("W", activities={"One": self.rule("Zeta"), "Two": self.rule("Alpha"), "Three": self.rule("Zeta"), "Four": self.rule("Mid")})
        self.assertEqual(b.inspect(doc)["rules"], ["Alpha", "Mid", "Zeta"])

    def test_activities_that_are_not_rules_are_not_listed(self):
        doc = workflow("W", activities={"One": self.rule("Alpha"), "Call": call("Child", "Evt"), "Fn": {"action": {"type": "Function", "reference": {"name": "Fn1", "id": "f"}}}})
        self.assertEqual(b.inspect(doc)["rules"], ["Alpha"])

    def test_a_workflow_without_rules_lists_none(self):
        self.assertEqual(b.inspect(workflow("W"))["rules"], [])


class Conditions(unittest.TestCase):
    def test_a_condition_comparing_with_a_fixed_value_is_reported(self):
        spec = workflow("W", conditions={
            "Is individual": {"action": {"type": "Expression", "expr": '{{Activity.T.ExtractedValue}} == "Individual"'}},
            "Has records": {"action": {"type": "Expression", "expr": "{{Variable.i}} < {{Activity.C.length}}"}},
        })["spec"]
        self.assertEqual(b.condition_literals(spec), [{"condition": "Is individual", "expr": '{{Activity.T.ExtractedValue}} == "Individual"', "literals": ["Individual"]}])


class LiteralInputs(unittest.TestCase):
    def test_listed_only_when_asked_and_always_counted(self):
        doc = workflow("W", activities={"A": {"action": {"reference": {"inputs": [
            {"name": "Q", "type": "Text", "value": "y" * 300},
            {"name": "M", "type": "Text", "mapValueFrom": {"outputField": "o", "source": {"label": "L"}}},
        ]}}}})
        quiet = b.inspect(doc)
        self.assertEqual(quiet["literalInputCount"], 1)
        self.assertNotIn("literalInputs", quiet)
        loud = b.inspect(doc, include_literals=True)
        self.assertEqual(len(loud["literalInputs"]), 1)
        self.assertTrue(loud["literalInputs"][0]["value"].endswith("..."))
        self.assertLess(len(loud["literalInputs"][0]["value"]), 200)


class Occurrences(unittest.TestCase):
    def doc(self):
        return workflow("W", activities={"Config": {"action": {"desc": "evidence Report-A and Report-A again", "reference": {"inputs": [{"name": "F", "fileName": "Report-A.toml"}]}}}},
                        transitions=[{"type": "Event", "event": {"specInput": {"expr": 'name == "Report-A"'}}}])

    def test_every_value_holding_the_string_is_found_with_its_path(self):
        found = b.occurrences(self.doc(), ["Report-A", "absent"])
        self.assertEqual(found["Report-A"]["count"], 4)
        self.assertEqual(sorted(w["path"] for w in found["Report-A"]["where"]), [
            "spec.activities.Config.action.desc",
            "spec.activities.Config.action.reference.inputs[0].fileName",
            "spec.transitions[0].event.specInput.expr",
        ])
        self.assertEqual(found["absent"], {"count": 0, "where": []})

    def test_a_snippet_shows_the_surroundings(self):
        found = b.occurrences({"v": "before Needle after"}, ["Needle"])
        self.assertEqual(found["Needle"]["where"][0]["snippet"], "before Needle after")

    def test_the_list_is_capped_but_the_count_is_not(self):
        found = b.occurrences({"items": [f"hit {i}" for i in range(80)]}, ["hit"])
        self.assertEqual(found["hit"]["count"], 80)
        self.assertEqual(len(found["hit"]["where"]), b.MAX_HITS_PER_NEEDLE)

    def test_inspect_looks_only_for_what_it_is_asked(self):
        self.assertNotIn("occurrences", b.inspect(self.doc()))
        self.assertIn("occurrences", b.inspect(self.doc(), find=["Report-A"]))


class InputDetails(unittest.TestCase):
    def spec(self):
        return workflow("W", activities={
            "Fetch config": {"action": {"type": "Rule", "desc": "Fetches the config file.", "reference": {"inputs": [
                {"name": "OutputFileName", "type": "Text", "desc": "Name of the output file.", "optional": True},
                {"name": "Mode", "type": "DropDown", "options": "A,B", "value": "A"},
                {"name": "InputFile", "type": "File", "mapValueFrom": {"outputField": "o", "source": {"label": "Earlier"}}},
                {"name": "Upload", "type": "File", "value": "hash"},
                {"name": "Long", "type": "Text", "value": "y" * 300},
            ]}}},
            "Other": {"action": {"type": "Rule", "reference": {"inputs": [{"name": "X", "type": "Text"}]}}},
        }, conditions={"Is it": {"action": {"type": "Function", "reference": {"desc": "Checks.", "inputs": [{"name": "C", "type": "Text"}]}}}})["spec"]

    def test_the_inputs_of_the_named_activities_are_described_in_full(self):
        found, unknown = b.input_details(self.spec(), ["Fetch config"])
        self.assertEqual(unknown, [])
        (activity,) = found
        self.assertEqual((activity["activity"], activity["kind"], activity["desc"]), ("Fetch config", "activity", "Fetches the config file."))
        by_name = {i["name"]: i for i in activity["inputs"]}
        self.assertEqual((by_name["OutputFileName"]["desc"], by_name["OutputFileName"]["optional"], by_name["OutputFileName"]["value"]), ("Name of the output file.", True, None))
        self.assertEqual((by_name["Mode"]["options"], by_name["Mode"]["value"]), ("A,B", "A"))
        self.assertTrue(by_name["Long"]["value"].endswith("..."))

    def test_an_input_taken_from_another_step_or_a_file_cannot_be_set(self):
        (activity,), _ = b.input_details(self.spec(), ["Fetch config"])
        by_name = {i["name"]: i for i in activity["inputs"]}
        self.assertEqual({n: i["settable"] for n, i in by_name.items()}, {"OutputFileName": True, "Mode": True, "InputFile": False, "Upload": False, "Long": True})
        self.assertEqual(by_name["InputFile"]["mappedFrom"], "Earlier")

    def test_conditions_are_described_too_and_unknown_labels_are_named(self):
        found, unknown = b.input_details(self.spec(), ["Is it", "Nope"])
        self.assertEqual([(f["activity"], f["kind"], f["desc"]) for f in found], [("Is it", "condition", "Checks.")])
        self.assertEqual(unknown, ["Nope"])

    def test_nothing_else_is_described(self):
        found, _ = b.input_details(self.spec(), ["Other"])
        self.assertEqual([f["activity"] for f in found], ["Other"])

    def test_the_details_come_only_when_asked_for(self):
        doc = {"metadata": {"name": "W"}, "spec": self.spec()}
        self.assertNotIn("inputDetails", b.inspect(doc))
        report = b.inspect(doc, activities=["Fetch config", "Nope"])
        self.assertEqual(len(report["inputDetails"]), 1)
        self.assertEqual(report["unknownActivities"], ["Nope"])


class Chain(unittest.TestCase):
    def test_a_workflow_is_created_after_the_ones_it_starts(self):
        wf4 = workflow("WF4")
        wf3 = workflow("WF3", activities={"Call 4": call("WF4", "E4")})
        wf2 = workflow("WF2", activities={"Call 3 async": call("WF3", "E3"), "Call 3 sync": call("WF3", "E3", wait=True)})
        wf1 = workflow("WF1", activities={"Call 2": call("WF2", "E2")})
        result = chain(wf1, [wf2, wf3, wf4])
        self.assertEqual(result["order"], ["WF4", "WF3", "WF2", "WF1"])
        self.assertEqual((result["missing"], result["cycle"]), ([], []))

    def test_a_workflow_started_twice_is_created_once(self):
        shared = workflow("Shared")
        left = workflow("Left", activities={"c": call("Shared", "E")})
        right = workflow("Right", activities={"c": call("Shared", "E")})
        root = workflow("Root", activities={"l": call("Left", "E"), "r": call("Right", "E")})
        self.assertEqual(chain(root, [left, right, shared])["order"], ["Shared", "Left", "Right", "Root"])

    def test_a_workflow_that_starts_nothing_is_alone(self):
        self.assertEqual(chain(workflow("Only"), [])["order"], ["Only"])

    def test_a_workflow_that_cannot_be_found_is_reported_and_the_rest_is_still_ordered(self):
        root = workflow("Root", activities={"a": call("Gone", "E"), "b": call("Here", "E")})
        result = chain(root, [workflow("Here")])
        self.assertEqual(result["missing"], ["Gone"])
        self.assertEqual(result["order"], ["Here", "Root"])

    def test_workflows_that_start_each_other_are_reported_as_a_cycle(self):
        a = workflow("A", activities={"c": call("B", "E")})
        bb = workflow("B", activities={"c": call("A", "E")})
        result = chain(a, [bb])
        self.assertEqual(result["cycle"], ["A", "B", "A"])


def entry(root, *subs):
    """One blueprint folder as the blueprint call returns it: the definition under `config`, the workflows it starts under `config.subworkflow` keyed by file name."""
    config = dict(root)
    if subs:
        config["subworkflow"] = {f"{d['metadata']['name']}-Subworkflow": d for d in subs}
    return {"binding": {"metadata": {"name": "bound"}}, "spec": {"metadata": {"name": "spec"}}, "config": config}


class Lookup(unittest.TestCase):
    def test_a_blueprint_is_found_by_its_folder_name_only(self):
        output = {"items": {"JiraFolder": entry(workflow("Root")), "JiraFolder2": entry(workflow("Other"))}, "totalItems": 2}
        self.assertIs(b.blueprint_named(output, "JiraFolder"), output["items"]["JiraFolder"])
        for name in ("Jira", "Root", "jirafolder"):
            self.assertIsNone(b.blueprint_named(output, name), name)

    def test_something_that_is_not_a_blueprint_listing_is_none(self):
        for junk in (None, "an error", [], {"items": []}, {"success": False, "error": "x"}, {"items": {"A": "text"}}):
            self.assertIsNone(b.blueprint_named(junk, "A"), junk)

    def test_the_folder_names_are_listed(self):
        self.assertEqual(b.names_in({"items": {"B": {}, "A": {}}}), ["A", "B"])
        self.assertEqual(b.names_in({"success": False}), [])

    def test_the_workflows_of_a_blueprint_are_found_by_their_own_names_not_their_file_names(self):
        root, library = b.library_of(entry(workflow("Root"), workflow("Child A"), workflow("Child B")))
        self.assertEqual(sorted(library), ["Child A", "Child B", "Root"])
        self.assertIs(library["Root"], root)

    def test_the_root_does_not_carry_the_workflows_it_starts(self):
        root, library = b.library_of(entry(workflow("Root"), workflow("Child")))
        self.assertNotIn("subworkflow", root)
        self.assertNotIn("subworkflow", library["Root"])

    def test_a_blueprint_without_a_definition_has_no_library(self):
        for junk in ({}, {"config": "text"}, {"config": {"metadata": {"name": "x"}}}, {"binding": {}}):
            self.assertEqual(b.library_of(junk), (None, {}), junk)

    def test_values_in_the_children_are_not_counted_for_the_root(self):
        child = workflow("Child", activities={"a": {"action": {"desc": "uses Report-A"}}})
        root, library = b.library_of(entry(workflow("Root"), child))
        self.assertEqual(b.inspect(library["Root"], find=["Report-A"])["occurrences"]["Report-A"]["count"], 0)
        self.assertEqual(b.inspect(library["Child"], find=["Report-A"])["occurrences"]["Report-A"]["count"], 1)


class TheTool(unittest.TestCase):
    """inspect_workflow_blueprint against a stand-in for the blueprint call."""

    def run_tool(self, responses, **kwargs):
        calls = []

        async def fake(uri, method=None, request_body=None, **_):
            calls.append((uri, method, request_body))
            return responses(request_body)

        with mock.patch.object(tool.utils, "make_API_call_to_CCow_and_get_response", fake):
            return asyncio.run(tool.inspect_workflow_blueprint(**kwargs)), calls

    def listing(self):
        folder = entry(workflow("Root", activities={"Start child": call("Child", "ChildEvent")}), workflow("Child"))
        return {"items": {"Folder": folder}, "totalItems": 1}

    def test_a_blueprint_is_inspected_with_one_call_and_its_children_come_with_it(self):
        result, calls = self.run_tool(lambda params: self.listing(), name="Folder", find=["x"])
        self.assertTrue(result["success"])
        self.assertEqual(result["chain"], {"order": ["Child", "Root"], "missing": [], "cycle": []})
        self.assertEqual(sorted(result["workflows"]), ["Child", "Root"])
        self.assertIn("occurrences", result["workflows"]["Root"])
        self.assertEqual(calls, [("/pc-api/v1/workflows", "GET", {"name": "Folder"})])

    def test_the_inputs_of_named_activities_come_back_in_full_for_every_workflow_that_has_them(self):
        folder = entry(workflow("Root", activities={"Start child": call("Child", "E"), "Fetch": {"action": {"type": "Rule", "reference": {"inputs": [{"name": "OutputFileName", "type": "Text"}]}}}}), workflow("Child", activities={"Fetch": {"action": {"type": "Rule", "reference": {"inputs": [{"name": "Other", "type": "Text"}]}}}}))
        result, _ = self.run_tool(lambda params: {"items": {"Folder": folder}}, name="Folder", activities=["Fetch"])
        self.assertEqual([i["name"] for i in result["workflows"]["Root"]["inputDetails"][0]["inputs"]], ["OutputFileName"])
        self.assertEqual([i["name"] for i in result["workflows"]["Child"]["inputDetails"][0]["inputs"]], ["Other"])

    def test_an_unknown_name_gets_the_names_that_exist(self):
        def responses(params):
            return {"items": {}} if "name" in params else {"items": {"B": {}, "A": {}}}

        result, calls = self.run_tool(responses, name="Nope")
        self.assertEqual((result["success"], result["available"]), (False, ["A", "B"]))
        self.assertEqual(calls[1][2], {"fields": "basic"})

    def test_a_refused_call_shows_what_the_platform_said_and_is_not_taken_for_an_unknown_name(self):
        refused = {"success": False, "error": {"Message": "UNAUTHORIZED", "Description": "Please check the Authorization header."}}
        result, calls = self.run_tool(lambda params: refused, name="Folder")
        self.assertEqual(result, {"success": False, "error": refused})
        self.assertEqual(len(calls), 1)
        self.assertNotIn("available", result)

    def test_a_folder_without_a_definition_is_reported(self):
        result, _ = self.run_tool(lambda params: {"items": {"Folder": {"binding": {}}}}, name="Folder")
        self.assertFalse(result["success"])
        self.assertIn("no workflow definition", result["error"])


BASIC = {"items": {
    "JiraGenericWorkflow": {"binding": {"metadata": {"name": "b"}}, "spec": {"metadata": {"name": "Generic", "description": "Generic"}}, "config": {"metadata": {"name": "Jira Generic Workflow - WF1", "description": "Creates a Jira ticket for every non-compliant record and sends Slack reminders. " + "x" * 600}}},
    "Policy Exception Approval Process": {"spec": {"metadata": {"name": "Policy Exception Approval Process", "description": "Assessment Run Completed"}}},
    "TriggerWizAssessmentForEvery30Days": {"binding": {"metadata": {"name": "t", "description": "Runs the Wiz assessment every 30 days"}}},
}, "totalItems": 3}


class ListingSummary(unittest.TestCase):
    def test_each_folder_is_one_short_row_that_says_whether_it_can_be_deployed(self):
        rows = b.summarize_listing(BASIC)
        self.assertEqual([r["folder"] for r in rows], ["JiraGenericWorkflow", "Policy Exception Approval Process", "TriggerWizAssessmentForEvery30Days"])
        jira = rows[0]
        self.assertEqual((jira["workflow"], jira["hasDefinition"]), ("Jira Generic Workflow - WF1", True))
        self.assertTrue(jira["description"].startswith("Creates a Jira ticket") and jira["description"].endswith("..."))
        self.assertLessEqual(len(jira["description"]), b.DESCRIPTION_LIMIT + 3)
        self.assertEqual((rows[1]["workflow"], rows[1]["hasDefinition"], rows[1]["description"]), (None, False, "Assessment Run Completed"))
        self.assertEqual(rows[2]["description"], "Runs the Wiz assessment every 30 days")

    def test_a_search_needs_every_word_in_the_folder_the_workflow_or_the_description(self):
        names = lambda q: [r["folder"] for r in b.summarize_listing(BASIC, q)]
        self.assertEqual(names("jira"), ["JiraGenericWorkflow"])
        self.assertEqual(names("JIRA ticket slack"), ["JiraGenericWorkflow"])
        self.assertEqual(names("jira wiz"), [])
        self.assertEqual(names("policy exception"), ["Policy Exception Approval Process"])
        self.assertEqual(names("30 days"), ["TriggerWizAssessmentForEvery30Days"])
        self.assertEqual(len(names("")), 3)
        self.assertEqual(len(names(None)), 3)

    def test_something_that_is_not_a_listing_gives_no_rows(self):
        for junk in (None, "text", {}, {"items": []}, {"success": False}):
            self.assertEqual(b.summarize_listing(junk), [], junk)


class TheListingTool(unittest.TestCase):
    def call(self, **kwargs):
        calls = []

        async def api(uri, method=None, request_body=None, **_):
            calls.append(request_body)
            return BASIC if request_body.get("fields") == "basic" else {"items": {"Folder": {"config": workflow("Root")}}}

        with mock.patch.object(tool.utils, "make_API_call_to_CCow_and_get_response", api):
            return asyncio.run(tool.list_workflow_blueprints(**kwargs)), calls

    def test_without_a_name_the_platform_is_asked_for_the_short_form_and_a_short_list_comes_back(self):
        result, calls = self.call()
        self.assertEqual(calls, [{"fields": "basic"}])
        self.assertEqual(len(result), 3)

    def test_a_search_narrows_the_list(self):
        result, _ = self.call(search="wiz")
        self.assertEqual([r["folder"] for r in result], ["TriggerWizAssessmentForEvery30Days"])

    def test_with_a_name_the_full_definition_of_that_folder_comes_back_unchanged(self):
        result, calls = self.call(name="Folder")
        self.assertEqual(calls, [{"name": "Folder"}])
        self.assertEqual(sorted(result["items"]), ["Folder"])

    def test_a_refused_call_is_not_taken_for_an_empty_list(self):
        async def api(uri, method=None, request_body=None, **_):
            return {"success": False, "error": {"Message": "UNAUTHORIZED"}}

        with mock.patch.object(tool.utils, "make_API_call_to_CCow_and_get_response", api):
            result = asyncio.run(tool.list_workflow_blueprints())
        self.assertFalse(result["success"])

    def test_an_answer_that_is_not_a_listing_is_not_taken_for_an_empty_list(self):
        for answer in ("gateway timeout", {"unexpected": True}, None):
            async def api(uri, method=None, request_body=None, _answer=answer, **_):
                return _answer

            with mock.patch.object(tool.utils, "make_API_call_to_CCow_and_get_response", api):
                result = asyncio.run(tool.list_workflow_blueprints())
            self.assertFalse(result["success"], answer)
            self.assertNotIsInstance(result, list)


class ListedBlueprintsReachAStrictClient(unittest.TestCase):
    """A client that validates results against the tool's declared type used to reject the dictionary the PolicyCow call returns."""

    def result_of(self, arguments):
        from fastmcp import Client
        from mcpconfig.config import mcp

        async def fake(uri, method=None, request_body=None, **_):
            return BASIC if request_body.get("fields") == "basic" else {"items": {"Folder": {"config": workflow("Root")}}, "totalItems": 1}

        async def run():
            async with Client(mcp) as client:
                return await client.call_tool("list_workflow_blueprints", arguments)

        with mock.patch.object(tool.utils, "make_API_call_to_CCow_and_get_response", fake):
            return asyncio.run(run())

    def test_the_full_definition_is_accepted(self):
        self.assertEqual(sorted(self.result_of({"name": "Folder"}).data["items"]), ["Folder"])

    def test_the_short_list_is_accepted(self):
        self.assertEqual(len(self.result_of({}).data), 3)


@unittest.skipUnless(JIRA_DIR, fixtures.HINT)
class RealJiraBlueprints(unittest.TestCase):
    """Structural checks on the real blueprint. Names and values are read from the files, which other people keep editing."""

    def setUp(self):
        config, subs = fixtures.load_jira(JIRA_DIR)
        config["subworkflow"] = subs
        self.output = {"items": {"JiraGenericWorkflow_PlaybookVersion": {"config": config}}, "totalItems": 1}
        self.root, self.library = b.library_of(b.blueprint_named(self.output, "JiraGenericWorkflow_PlaybookVersion"))

    def test_every_workflow_is_created_after_the_workflows_it_starts(self):
        chain = b.chain_of(self.root, self.library)
        self.assertEqual((chain["missing"], chain["cycle"]), ([], []))
        self.assertGreater(len(chain["order"]), 1)
        self.assertEqual(sorted(chain["order"]), sorted(self.library))
        self.assertEqual(chain["order"][-1], self.root["metadata"]["name"])
        for position, name in enumerate(chain["order"]):
            started = {c["name"] for c in b.children(self.library[name]["spec"])}
            self.assertLessEqual(started, set(chain["order"][:position]), name)

    def test_every_workflow_started_has_the_start_event_the_parent_names(self):
        for name, doc in self.library.items():
            for child in b.children(doc["spec"]):
                events = {t["event"] for t in b.triggers(self.library[child["name"]]["spec"])}
                self.assertIn(child["eventName"], events, f"{name} starts {child['name']}")

    def test_the_start_event_filter_is_reported_with_its_values_and_where_they_appear(self):
        trigger = b.triggers(self.root["spec"])[0]
        self.assertTrue(trigger["literals"])
        self.assertTrue(trigger["payload"] and all(p["name"] for p in trigger["payload"]))
        first = trigger["literals"][0]
        found = b.inspect(self.root, find=[first])["occurrences"][first]
        self.assertTrue(any(w["path"].endswith("specInput.expr") for w in found["where"]), found)

    def test_the_sample_a_file_must_follow_is_found(self):
        samples = [t for t in b.inspect(self.root)["templates"] if "EvidenceName" in t["desc"]]
        self.assertTrue(samples)
        activity = samples[0]["activity"]
        detail = b.inspect(self.root, activities=[activity])["inputDetails"][0]
        self.assertEqual(detail["activity"], activity)
        self.assertTrue(all(not i["settable"] for i in detail["inputs"] if i["mappedFrom"] or str(i["type"]).lower() == "file"))
        self.assertTrue(any(i["settable"] for i in detail["inputs"]))

    def test_no_file_description_that_is_only_its_name_is_taken_for_a_template(self):
        for name, doc in self.library.items():
            for t in b.inspect(doc)["templates"]:
                if t["source"] == "input":
                    self.assertTrue("{" in t["desc"] or len(t["desc"]) > b.FILE_DESC_MIN or b._TEMPLATE_WORD.search(t["desc"]), (name, t))


if __name__ == "__main__":
    unittest.main()
