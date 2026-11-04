import asyncio
import copy
import unittest
from unittest import mock

import yaml

from tests import blueprint_fixtures as fixtures
from tools.workflow import blueprint_apply as a
from tools.workflow import blueprint_inspect as b
from tools.workflow import workflow as tool

JIRA_DIR = fixtures.jira_dir()
OLD_CHILD = "08d34016-0000-0000-0000-000000000001"
NEW_CHILD = "99999999-aaaa-bbbb-cccc-000000000001"


def blueprint():
    return {
        "apiVersion": "v3",
        "metadata": {"name": "Playbook", "description": "Runs for AC-UC-003"},
        "spec": {
            "variables": [{"name": "loopIndex", "type": "Number"}],
            "states": {"Start": {"groupName": "Ungrouped", "action": {}}},
            "activities": {
                "Fetch config": {"action": {"type": "Rule", "desc": "sample", "reference": {"id": "rule-id-1", "name": "ExtractDataUsingJQV2", "inputs": [
                    {"name": "JQConfigFile", "type": "File", "value": "8cbccc", "fileName": "Generate-AC-UC-003.toml"},
                    {"name": "Query", "type": "Text", "value": 'select(.EvidenceName == "{{Activity.A.Out}}") AC-UC-003'},
                    {"name": "Loop", "type": "Number", "value": "0", "dynamicTypeFrom": "variableType"},
                ]}}},
                "Start child": {"action": {"type": "Workflow", "asyncActionExecution": True, "reference": {
                    "id": OLD_CHILD, "name": "Child", "displayable": "Child shown", "eventName": "ChildEvent", "inputs": []}}},
                "Start child again": {"action": {"type": "Workflow", "reference": {"id": OLD_CHILD, "name": "Child", "eventName": "ChildEvent", "inputs": []}}},
            },
            "conditions": {},
            "transitions": [
                {"from": "Start", "to": "Fetch config", "type": "Event", "event": {"type": "RESOURCE_BASED_EVENT", "specInput": {"expr": 'assessmentName == "AC-UC-003" || assessmentName.contains("Company")'}}},
                {"from": "Fetch config", "to": "Start child", "type": "PassThrough"},
            ],
        },
    }


def full(**over):
    args = dict(
        new_name="Okta MFA playbook",
        replacements=[{"from": 'assessmentName == "AC-UC-003" || assessmentName.contains("Company")', "to": 'assessmentName == "Okta MFA Review"'}, {"from": "AC-UC-003", "to": "OktaMFA"}],
        children={"Child": {"id": NEW_CHILD, "name": "Okta child"}},
        files=[{"activity": "Fetch config", "input": "JQConfigFile", "value": "newhash", "fileName": "okta.toml"}],
    )
    args.update(over)
    return args


def paths_of(a_, b_, path="", out=None):
    out = [] if out is None else out
    if isinstance(a_, dict) and isinstance(b_, dict):
        for k in sorted(set(a_) | set(b_)):
            if k not in a_ or k not in b_:
                out.append(f"{path}.{k}")
            else:
                paths_of(a_[k], b_[k], f"{path}.{k}", out)
    elif isinstance(a_, list) and isinstance(b_, list) and len(a_) == len(b_):
        for i, (x, y) in enumerate(zip(a_, b_)):
            paths_of(x, y, f"{path}[{i}]", out)
    elif a_ != b_:
        out.append(path)
    return out


class Faithfulness(unittest.TestCase):
    def test_changing_nothing_changes_nothing(self):
        doc = blueprint()
        result = a.apply(doc)
        self.assertEqual(result["doc"], doc)
        self.assertEqual(paths_of(doc, result["doc"]), [])

    def test_the_blueprint_given_is_not_modified(self):
        doc, before = blueprint(), copy.deepcopy(blueprint())
        a.apply(doc, **full())
        self.assertEqual(doc, before)

    def test_only_what_was_asked_changes(self):
        doc = blueprint()
        result = a.apply(doc, **full())
        self.assertEqual(sorted(paths_of(doc, result["doc"])), sorted([
            ".metadata.name", ".metadata.description",
            ".spec.transitions[0].event.specInput.expr",
            ".spec.activities.Fetch config.action.reference.inputs[0].value",
            ".spec.activities.Fetch config.action.reference.inputs[0].fileName",
            ".spec.activities.Fetch config.action.reference.inputs[1].value",
            ".spec.activities.Start child.action.reference.id",
            ".spec.activities.Start child.action.reference.name",
            ".spec.activities.Start child again.action.reference.id",
            ".spec.activities.Start child again.action.reference.name",
        ]))
        self.assertTrue(result["ready"], result)


class Replacements(unittest.TestCase):
    def test_the_text_is_replaced_wherever_it_is_and_counted_with_its_places(self):
        result = a.apply(blueprint(), replacements=[{"from": "AC-UC-003", "to": "OktaMFA"}])
        (r,) = result["replacements"]
        self.assertEqual(r["count"], 4)
        self.assertIn("spec.transitions[0].event.specInput.expr", r["paths"])
        self.assertNotIn("AC-UC-003", str(result["doc"]))

    def test_ids_and_types_are_never_rewritten_by_a_text_replacement(self):
        result = a.apply(blueprint(), replacements=[{"from": "rule-id", "to": "changed"}, {"from": "Rule", "to": "Task"}])
        self.assertEqual(result["doc"]["spec"]["activities"]["Fetch config"]["action"]["reference"]["id"], "rule-id-1")
        self.assertEqual(result["doc"]["spec"]["activities"]["Fetch config"]["action"]["type"], "Rule")
        self.assertEqual(len(result["problems"]), 2)

    def test_text_that_is_not_there_is_a_problem_unless_optional(self):
        result = a.apply(blueprint(), replacements=[{"from": "nowhere", "to": "x"}])
        self.assertEqual(len(result["problems"]), 1)
        self.assertFalse(result["ready"])
        quiet = a.apply(blueprint(), replacements=[{"from": "nowhere", "to": "x", "optional": True}])
        self.assertEqual(quiet["problems"], [])

    def test_a_replacement_without_text_is_a_problem(self):
        for bad in ({"to": "x"}, {"from": "", "to": "x"}, {"from": "a"}, {"from": "a", "to": 3}):
            self.assertTrue(a.apply(blueprint(), replacements=[bad])["problems"], bad)

    def test_text_that_stays_after_a_replacement_is_reported(self):
        doc = blueprint()
        doc["spec"]["activities"]["Fetch config"]["action"]["reference"]["id"] = "rule-id-KEEPME"
        result = a.apply(doc, replacements=[{"from": "KEEPME", "to": "gone", "optional": True}, {"from": "AC-UC-003", "to": "x"}])
        self.assertEqual(result["leftovers"], [])
        doc["spec"]["activities"]["Fetch config"]["action"]["reference"]["id"] = "rule-id-AC-UC-003"
        result = a.apply(doc, replacements=[{"from": "AC-UC-003", "to": "x"}])
        self.assertEqual(result["leftovers"], ["AC-UC-003"])
        self.assertFalse(result["ready"])

    def test_the_new_name_is_not_touched_by_a_replacement(self):
        result = a.apply(blueprint(), new_name="AC-UC-003 copy", replacements=[{"from": "AC-UC-003", "to": "x"}])
        self.assertEqual(result["name"], "AC-UC-003 copy")


class Children(unittest.TestCase):
    def test_each_activity_starting_the_workflow_gets_its_new_id_and_nothing_else_changes(self):
        result = a.apply(blueprint(), children={"Child": {"id": NEW_CHILD, "name": "New child"}})
        for label in ("Start child", "Start child again"):
            ref = result["doc"]["spec"]["activities"][label]["action"]["reference"]
            self.assertEqual((ref["id"], ref["name"], ref["eventName"]), (NEW_CHILD, "New child", "ChildEvent"))
        self.assertTrue(result["doc"]["spec"]["activities"]["Start child"]["action"]["asyncActionExecution"])
        self.assertEqual(result["doc"]["spec"]["activities"]["Start child"]["action"]["reference"]["displayable"], "Child shown")
        self.assertEqual([c["was"] for c in result["workflowsStarted"]], [OLD_CHILD, OLD_CHILD])

    def test_the_display_name_changes_only_when_given(self):
        result = a.apply(blueprint(), children={"Child": {"id": NEW_CHILD, "displayable": "Shown now"}})
        self.assertEqual(result["doc"]["spec"]["activities"]["Start child"]["action"]["reference"]["displayable"], "Shown now")
        self.assertEqual(result["doc"]["spec"]["activities"]["Start child"]["action"]["reference"]["name"], "Child")

    def test_a_workflow_started_without_an_id_is_pending_and_keeps_the_blueprints_id(self):
        result = a.apply(blueprint())
        self.assertEqual([p["activity"] for p in result["pendingChildren"]], ["Start child", "Start child again"])
        self.assertEqual(result["doc"]["spec"]["activities"]["Start child"]["action"]["reference"]["id"], OLD_CHILD)
        self.assertFalse(result["ready"])

    def test_an_empty_id_is_a_problem(self):
        for empty in ("", "  ", None):
            self.assertTrue(a.apply(blueprint(), children={"Child": {"id": empty}})["problems"], empty)

    def test_a_workflow_that_is_not_started_is_a_problem(self):
        result = a.apply(blueprint(), children={"Child": {"id": NEW_CHILD}, "Typo": {"id": "x"}})
        self.assertEqual(result["problems"], ["this workflow does not start 'Typo'"])

    def test_the_blueprints_id_left_elsewhere_is_a_problem(self):
        doc = blueprint()
        doc["spec"]["activities"]["Fetch config"]["action"]["desc"] = f"triggers {OLD_CHILD}"
        result = a.apply(doc, children={"Child": {"id": NEW_CHILD}})
        self.assertEqual(len(result["problems"]), 1)
        self.assertIn(OLD_CHILD, result["problems"][0])

    def test_adopting_a_workflow_with_the_same_id_is_fine(self):
        result = a.apply(blueprint(), children={"Child": {"id": OLD_CHILD}})
        self.assertEqual(result["problems"], [])
        self.assertEqual(result["pendingChildren"], [])


class Files(unittest.TestCase):
    def test_an_uploaded_file_gets_its_hash_and_name(self):
        result = a.apply(blueprint(), files=[{"activity": "Fetch config", "input": "JQConfigFile", "value": "h2", "fileName": "n.toml"}])
        inp = result["doc"]["spec"]["activities"]["Fetch config"]["action"]["reference"]["inputs"][0]
        self.assertEqual((inp["value"], inp["fileName"]), ("h2", "n.toml"))
        self.assertEqual(result["unresolvedFiles"], [])

    def test_the_file_name_is_kept_when_not_given(self):
        result = a.apply(blueprint(), files=[{"activity": "Fetch config", "input": "JQConfigFile", "value": "h2"}])
        self.assertEqual(result["doc"]["spec"]["activities"]["Fetch config"]["action"]["reference"]["inputs"][0]["fileName"], "Generate-AC-UC-003.toml")

    def test_a_file_nobody_replaced_is_unresolved_until_kept_on_purpose(self):
        result = a.apply(blueprint())
        self.assertEqual(result["unresolvedFiles"], [{"activity": "Fetch config", "input": "JQConfigFile", "fileName": "Generate-AC-UC-003.toml"}])
        self.assertEqual(a.apply(blueprint(), keep_files=["Fetch config"])["unresolvedFiles"], [])
        self.assertEqual(len(a.apply(blueprint(), keep_files=["Another"])["unresolvedFiles"]), 1)

    def test_things_that_are_not_an_uploaded_file_are_problems(self):
        base = {"activity": "Fetch config", "value": "h"}
        for bad in (
            {**base, "input": "Query"},
            {**base, "input": "Missing"},
            {**base, "input": "JQConfigFile", "value": ""},
            {"activity": "Nowhere", "input": "JQConfigFile", "value": "h"},
        ):
            self.assertTrue(a.apply(blueprint(), files=[bad])["problems"], bad)

    def test_a_file_mapped_from_another_activity_cannot_be_replaced(self):
        doc = blueprint()
        doc["spec"]["activities"]["Fetch config"]["action"]["reference"]["inputs"][0]["mapValueFrom"] = {"outputField": "o", "source": {"label": "L"}}
        result = a.apply(doc, files=[{"activity": "Fetch config", "input": "JQConfigFile", "value": "h"}])
        self.assertTrue(result["problems"])


class SetInputs(unittest.TestCase):
    def doc(self):
        return {"metadata": {"name": "W"}, "spec": {"conditions": {}, "states": {}, "transitions": [], "activities": {
            "Convert": {"action": {"type": "Rule", "reference": {"inputs": [
                {"name": "OutputFileName", "type": "Text", "desc": "Name of the output file."},
                {"name": "PreserveType", "type": "Boolean"},
                {"name": "Retries", "type": "Number", "value": "1"},
                {"name": "Mode", "type": "DropDown", "options": "Increment, Decrement", "value": "Increment"},
                {"name": "Emails", "type": "TextArray"},
                {"name": "InputFile", "type": "File", "mapValueFrom": {"outputField": "o", "source": {"label": "Earlier"}}},
                {"name": "Upload", "type": "File", "value": "hash"},
            ]}}},
        }}}

    def put(self, input_name, value, **extra):
        return a.apply(self.doc(), set_inputs=[{"activity": "Convert", "input": input_name, "value": value, **extra}])

    def value_of(self, result, input_name):
        return next(i for i in result["doc"]["spec"]["activities"]["Convert"]["action"]["reference"]["inputs"] if i["name"] == input_name).get("value")

    def test_an_input_with_no_value_gets_one_and_nothing_else_changes(self):
        doc = self.doc()
        result = a.apply(doc, set_inputs=[{"activity": "Convert", "input": "OutputFileName", "value": "okta.json"}])
        self.assertEqual(paths_of(doc, result["doc"]), [".spec.activities.Convert.action.reference.inputs[0].value"])
        self.assertEqual(result["inputsSet"], [{"activity": "Convert", "input": "OutputFileName", "type": "Text", "was": None, "value": "okta.json"}])
        self.assertEqual(result["problems"], [])

    def test_an_input_with_a_value_is_replaced_and_the_old_value_is_reported(self):
        result = self.put("Retries", 3)
        self.assertEqual((self.value_of(result, "Retries"), result["inputsSet"][0]["was"]), ("3", "1"))

    def test_a_boolean_is_stored_as_true_or_false_text(self):
        for given in (True, "true", "True", " TRUE "):
            self.assertEqual(self.value_of(self.put("PreserveType", given), "PreserveType"), "true", given)
        for given in (False, "false", "False"):
            self.assertEqual(self.value_of(self.put("PreserveType", given), "PreserveType"), "false", given)

    def test_something_that_is_not_a_boolean_is_refused(self):
        for given in ("yes", 1, 0, "", None):
            result = self.put("PreserveType", given)
            self.assertEqual(len(result["problems"]), 1, given)
            self.assertIsNone(self.value_of(result, "PreserveType"))

    def test_a_number_is_stored_as_text_without_a_needless_decimal(self):
        for given, stored in ((5, "5"), ("5", "5"), ("5.0", "5"), (2.5, "2.5"), (" 7 ", "7")):
            self.assertEqual(self.value_of(self.put("Retries", given), "Retries"), stored, given)
        for given in ("abc", "", True, None, [1]):
            self.assertEqual(len(self.put("Retries", given)["problems"]), 1, given)

    def test_a_dropdown_takes_only_one_of_its_options(self):
        self.assertEqual(self.value_of(self.put("Mode", "Decrement"), "Mode"), "Decrement")
        result = self.put("Mode", "Reset")
        self.assertEqual(len(result["problems"]), 1)
        self.assertIn("Increment, Decrement", result["problems"][0])
        self.assertEqual(self.value_of(result, "Mode"), "Increment")

    def test_a_list_for_a_text_array_is_joined_with_commas(self):
        self.assertEqual(self.value_of(self.put("Emails", ["a@x.com", "b@x.com"]), "Emails"), "a@x.com,b@x.com")
        self.assertEqual(self.value_of(self.put("Emails", "a@x.com,b@x.com"), "Emails"), "a@x.com,b@x.com")

    def test_text_takes_text_and_numbers_but_not_structures(self):
        self.assertEqual(self.value_of(self.put("OutputFileName", 12), "OutputFileName"), "12")
        for given in ({"a": 1}, ["a"], True, None):
            self.assertEqual(len(self.put("OutputFileName", given)["problems"]), 1, given)

    def test_an_input_taken_from_another_step_or_a_file_is_refused(self):
        self.assertIn("another step", self.put("InputFile", "x")["problems"][0])
        self.assertIn("files", self.put("Upload", "x")["problems"][0])
        self.assertEqual(self.value_of(self.put("Upload", "x"), "Upload"), "hash")

    def test_an_input_or_activity_that_does_not_exist_and_a_missing_value_are_refused(self):
        self.assertIn("no input", self.put("Nope", "x")["problems"][0])
        self.assertIn("no input", a.apply(self.doc(), set_inputs=[{"activity": "Nowhere", "input": "OutputFileName", "value": "x"}])["problems"][0])
        self.assertIn("no value", a.apply(self.doc(), set_inputs=[{"activity": "Convert", "input": "OutputFileName"}])["problems"][0])

    def test_a_refused_value_leaves_the_rest_of_the_list_applied(self):
        result = a.apply(self.doc(), set_inputs=[{"activity": "Convert", "input": "Retries", "value": "x"}, {"activity": "Convert", "input": "OutputFileName", "value": "ok.json"}])
        self.assertEqual(len(result["problems"]), 1)
        self.assertEqual(self.value_of(result, "OutputFileName"), "ok.json")
        self.assertFalse(result["ready"])


class Yaml(unittest.TestCase):
    def test_what_is_submitted_reads_back_as_the_same_definition(self):
        doc = blueprint()
        doc["spec"]["activities"]["Fetch config"]["position"] = {"x": 0, "y": 150}
        doc["spec"]["states"]["Start"]["position"] = {"x": 0, "y": 0}
        self.assertEqual(yaml.safe_load(a.to_yaml(doc)), doc)

    def test_long_lines_are_not_folded(self):
        doc = {"metadata": {"name": "x" * 400}}
        self.assertEqual(yaml.safe_load(a.to_yaml(doc)), doc)


class TheTool(unittest.TestCase):
    """create_workflow_from_blueprint against a stand-in for the platform."""

    def folder(self):
        child = {"metadata": {"name": "Child"}, "spec": {"activities": {}, "conditions": {}, "transitions": [], "states": {}}}
        config = dict(blueprint(), subworkflow={"Child-Subworkflow": child})
        return {"items": {"Folder": {"config": config}}, "totalItems": 1}

    def run_tool(self, existing=None, name_lookup_fails=False, known_ids=None, **kwargs):
        known_ids = {NEW_CHILD: "Okta child"} if known_ids is None else known_ids
        posts = []

        async def api(uri, method=None, request_body=None, **extra):
            if method == "GET":
                return self.folder()
            posts.append((uri, request_body))
            return {"status": {"id": f"{len(posts):08d}-0000-0000-0000-000000000000"}}

        async def get(uri, ctx=None):
            if uri.startswith("/v3/workflow-configs/"):
                wid = uri.rsplit("/", 1)[1]
                return {"metadata": {"name": known_ids[wid]}} if wid in known_ids else {"error": "not found"}
            if name_lookup_fails:
                return {"error": "boom"}
            return {"items": [{"status": {"id": "e" * 8 + "-0000-0000-0000-000000000000"}, "metadata": {"name": "x"}}]} if existing else {"items": []}

        async def nothing_missing(specs, ctx):
            return {name: {"events": [], "rules": [], "functions": [], "missing": [], "unchecked": [], "publishedOnCreate": []} for name in specs}

        with mock.patch.object(tool.utils, "make_API_call_to_CCow_and_get_response", api), mock.patch.object(tool.utils, "make_GET_API_call_to_CCow", get), \
                mock.patch.object(tool, "_prerequisites_for", nothing_missing):
            result = asyncio.run(tool.create_workflow_from_blueprint(name="Folder", **kwargs))
        return result, posts

    def test_the_default_creates_nothing_and_says_what_is_missing(self):
        result, posts = self.run_tool(workflow="Playbook" if False else None, new_name="Okta playbook")
        self.assertEqual(posts, [])
        self.assertTrue(result["success"] and result["dryRun"] and not result["ready"])
        self.assertEqual(len(result["pendingChildren"]), 2)
        self.assertEqual(len(result["unresolvedFiles"]), 1)
        self.assertIs(result["nameTaken"], False)

    def test_a_complete_dry_run_is_ready_and_still_creates_nothing(self):
        result, posts = self.run_tool(**full())
        self.assertTrue(result["ready"], result)
        self.assertEqual(posts, [])

    def test_creating_submits_the_blueprint_with_only_the_listed_changes(self):
        result, posts = self.run_tool(dry_run=False, **full())
        self.assertTrue(result["success"], result)
        self.assertEqual(result["created"]["id"], "00000001-0000-0000-0000-000000000000")
        self.assertEqual(result["created"]["name"], "Okta MFA playbook")
        uri, body = posts[0]
        self.assertEqual(uri, tool.constants.URL_WORKFLOW_CREATE)
        sent = yaml.safe_load(body)
        original = blueprint()
        changed = paths_of(original, {k: v for k, v in sent.items() if k != "metadata"} | {"metadata": {k: v for k, v in sent["metadata"].items() if k != "tags"}})
        self.assertEqual(sorted(changed), sorted(paths_of(original, a.apply(original, **full())["doc"])))
        self.assertNotIn(OLD_CHILD, body)
        self.assertIn(NEW_CHILD, body)
        self.assertEqual(len(posts), 3)

    def test_a_child_id_that_belongs_to_no_workflow_is_refused(self):
        result, posts = self.run_tool(known_ids={}, dry_run=False, **full())
        self.assertFalse(result["success"])
        self.assertEqual(posts, [])
        self.assertEqual([p for p in result["problems"] if "no workflow has that id" in p], [f"'Okta child' was given the id {NEW_CHILD}, but no workflow has that id"])

    def test_a_child_id_that_belongs_to_another_workflow_is_refused(self):
        result, posts = self.run_tool(known_ids={NEW_CHILD: "Something else"}, dry_run=False, **full())
        self.assertFalse(result["success"])
        self.assertEqual(posts, [])
        self.assertIn("that id is the workflow 'Something else'", " ".join(result["problems"]))

    def test_a_made_up_id_makes_even_a_dry_run_not_ready(self):
        result, _ = self.run_tool(known_ids={}, **full())
        self.assertTrue(result["success"] and result["dryRun"])
        self.assertFalse(result["ready"])

    def test_the_child_is_checked_by_the_name_it_was_given_or_else_the_blueprints(self):
        kept = full(children={"Child": {"id": NEW_CHILD}})
        result, _ = self.run_tool(known_ids={NEW_CHILD: "Child"}, **kept)
        self.assertTrue(result["ready"], result)

    def test_inputs_are_set_in_what_is_submitted(self):
        # the blueprint fixture has a Text input "Query" on "Fetch config"
        result, posts = self.run_tool(dry_run=False, **full(set_inputs=[{"activity": "Fetch config", "input": "Query", "value": "set by the agent"}]))
        self.assertTrue(result["success"], result)
        self.assertEqual(result["inputsSet"][0]["value"], "set by the agent")
        sent = yaml.safe_load(posts[0][1])
        self.assertEqual(sent["spec"]["activities"]["Fetch config"]["action"]["reference"]["inputs"][1]["value"], "set by the agent")

    def test_a_refused_input_value_stops_the_creation(self):
        result, posts = self.run_tool(dry_run=False, **full(set_inputs=[{"activity": "Fetch config", "input": "Loop", "value": "not a number"}]))
        self.assertFalse(result["success"])
        self.assertEqual(posts, [])

    def test_nothing_is_created_when_it_is_not_ready(self):
        result, posts = self.run_tool(dry_run=False, new_name="x")
        self.assertFalse(result["success"])
        self.assertEqual(posts, [])

    def test_nothing_is_created_when_the_name_is_taken(self):
        result, posts = self.run_tool(existing=True, dry_run=False, **full())
        self.assertFalse(result["success"])
        self.assertIs(result["nameTaken"], True)
        self.assertEqual([p for p in result["problems"] if "already exists" in p], ["a workflow named 'Okta MFA playbook' already exists"])
        self.assertEqual(posts, [])

    def test_nothing_is_created_when_the_name_cannot_be_checked(self):
        result, posts = self.run_tool(name_lookup_fails=True, dry_run=False, **full())
        self.assertFalse(result["success"])
        self.assertIsNone(result["nameTaken"])
        self.assertEqual([p for p in result["problems"] if "could not check" in p], ["could not check whether a workflow named 'Okta MFA playbook' already exists"])
        self.assertEqual(posts, [])

    def test_a_workflow_that_is_not_in_the_blueprint_is_refused_with_the_names_that_are(self):
        result, posts = self.run_tool(workflow="Nope", dry_run=False, **full())
        self.assertFalse(result["success"])
        self.assertEqual(result["available"], ["Child", "Playbook"])
        self.assertEqual(posts, [])

    def test_a_workflow_inside_the_blueprint_can_be_created_by_its_name(self):
        result, _ = self.run_tool(workflow="Child", new_name="Okta child")
        self.assertEqual(result["name"], "Okta child")
        self.assertTrue(result["ready"], result)

    def test_a_refused_blueprint_call_shows_what_the_platform_said(self):
        async def api(uri, method=None, request_body=None, **_):
            return {"success": False, "error": {"Message": "UNAUTHORIZED"}}

        with mock.patch.object(tool.utils, "make_API_call_to_CCow_and_get_response", api):
            result = asyncio.run(tool.create_workflow_from_blueprint(name="Folder"))
        self.assertEqual(result["error"]["error"]["Message"], "UNAUTHORIZED")


@unittest.skipUnless(JIRA_DIR, fixtures.HINT)
class RealJiraBlueprints(unittest.TestCase):
    """Checks on the real blueprint. Names and values are read from the files, which other people keep editing."""

    def setUp(self):
        config, subs = fixtures.load_jira(JIRA_DIR)
        self.root = config
        self.docs = {config["metadata"]["name"]: config, **{d["metadata"]["name"]: d for d in subs.values()}}

    def test_every_workflow_survives_being_written_out_and_read_back(self):
        for name, doc in self.docs.items():
            self.assertEqual(yaml.safe_load(a.to_yaml(doc)), doc, name)

    def test_the_root_workflow_changes_only_where_it_was_told_to(self):
        doc, spec = self.root, self.root["spec"]
        event = next(i for i, t in enumerate(spec["transitions"]) if t.get("type") == "Event")
        expr = spec["transitions"][event]["event"]["specInput"]["expr"]
        started = b.children(spec)
        uploaded = b.fixed_files(spec)
        result = a.apply(
            doc,
            new_name="ZZ root",
            replacements=[{"from": expr, "to": 'assessmentName == "Okta MFA Review"'}],
            children={c["name"]: {"id": NEW_CHILD, "name": f"ZZ {c['name']}"} for c in started},
            files=[{"activity": f["activity"], "input": f["input"], "value": "newhash"} for f in uploaded],
        )
        self.assertTrue(result["ready"], {k: v for k, v in result.items() if k != "doc"})
        expected = [".metadata.name", f".spec.transitions[{event}].event.specInput.expr"]
        for c in started:
            expected += [f".spec.activities.{c['activity']}.action.reference.id", f".spec.activities.{c['activity']}.action.reference.name"]
        for f in uploaded:
            names = [i["name"] for i in doc["spec"]["activities"][f["activity"]]["action"]["reference"]["inputs"]]
            expected.append(f".spec.activities.{f['activity']}.action.reference.inputs[{names.index(f['input'])}].value")
        self.assertEqual(sorted(paths_of(doc, result["doc"])), sorted(expected))

    def test_an_input_with_no_value_can_be_set_and_nothing_else_moves(self):
        spec = self.root["spec"]
        details, _ = b.input_details(spec, list(spec["activities"]))
        label, empty = next((d["activity"], i) for d in details for i in d["inputs"] if i["settable"] and i["value"] is None and str(i["type"]).lower() == "text")
        names = [i["name"] for i in spec["activities"][label]["action"]["reference"]["inputs"]]
        result = a.apply(self.root, set_inputs=[{"activity": label, "input": empty["name"], "value": "set by a test"}])
        self.assertEqual(result["problems"], [])
        self.assertEqual(paths_of(self.root, result["doc"]), [f".spec.activities.{label}.action.reference.inputs[{names.index(empty['name'])}].value"])

    def test_an_input_taken_from_another_step_cannot_be_set(self):
        spec = self.root["spec"]
        details, _ = b.input_details(spec, list(spec["activities"]))
        label, mapped = next((d["activity"], i) for d in details for i in d["inputs"] if i["mappedFrom"])
        result = a.apply(self.root, set_inputs=[{"activity": label, "input": mapped["name"], "value": "x"}])
        self.assertEqual(len(result["problems"]), 1)
        self.assertEqual(paths_of(self.root, result["doc"]), [])


if __name__ == "__main__":
    unittest.main()
