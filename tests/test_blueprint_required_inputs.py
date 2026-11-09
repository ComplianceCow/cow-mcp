import unittest

from tests import blueprint_fixtures as fixtures
from tools.workflow import blueprint_apply as a
from tools.workflow import blueprint_inspect as b

JIRA_DIR = fixtures.jira_dir()


def node(rule, inputs, outputs=None):
    reference = {"name": rule, "inputs": inputs}
    if outputs is not None:
        reference["outputs"] = [{"name": n} for n in outputs]
    return {"action": {"type": "Rule", "reference": reference}}


def spec(**activities):
    return {"activities": activities, "conditions": {}, "states": {}, "transitions": []}


MAPPED = {"outputField": "Out", "type": "Activity", "source": {"label": "Fetch"}}


class RequiredInputsUnset(unittest.TestCase):
    def listed(self, *inputs):
        return [(i["activity"], i["input"]) for i in b.required_inputs_unset(spec(Run=node("Rule", list(inputs))))]

    def test_a_required_input_with_nothing_is_listed(self):
        self.assertEqual(self.listed({"name": "SQLConfig", "type": "File"}), [("Run", "SQLConfig")])

    def test_an_empty_text_list_or_object_counts_as_nothing(self):
        for value in ("", None, [], {}):
            self.assertEqual(self.listed({"name": "X", "type": "Text", "value": value}), [("Run", "X")], repr(value))

    def test_false_and_zero_are_values(self):
        self.assertEqual(self.listed({"name": "A", "type": "Boolean", "value": "false"}, {"name": "B", "type": "Number", "value": 0}), [])

    def test_an_optional_input_is_not_listed(self):
        self.assertEqual(self.listed({"name": "OutputFileName", "type": "Text", "optional": True}), [])

    def test_an_input_taken_from_an_earlier_step_is_not_listed(self):
        self.assertEqual(self.listed({"name": "InputFile", "type": "File", "mapValueFrom": MAPPED}), [])

    def test_an_uploaded_file_is_not_listed(self):
        self.assertEqual(self.listed({"name": "Cfg", "type": "File", "value": "hash", "fileName": "a.toml"}, {"name": "Cfg2", "type": "File", "fileName": "b.toml"}), [])

    def test_a_file_cannot_be_set_with_set_inputs_and_a_text_can(self):
        got = {i["input"]: i["settable"] for i in b.required_inputs_unset(spec(Run=node("R", [{"name": "F", "type": "File"}, {"name": "T", "type": "Text"}])))}
        self.assertEqual(got, {"F": False, "T": True})

    def test_a_condition_is_checked_too(self):
        s = {"activities": {}, "conditions": {"Is it": node("Cond", [{"name": "Left", "type": "Text"}])}, "states": {}, "transitions": []}
        self.assertEqual([(i["kind"], i["input"]) for i in b.required_inputs_unset(s)], [("condition", "Left")])

    def test_setting_the_input_with_set_inputs_clears_it(self):
        doc = {"metadata": {"name": "W"}, "spec": spec(Run=node("R", [{"name": "T", "type": "Text"}]))}
        self.assertEqual(len(a.apply(doc)["requiredInputsUnset"]), 1)
        done = a.apply(doc, set_inputs=[{"activity": "Run", "input": "T", "value": "x"}])
        self.assertEqual(done["requiredInputsUnset"], [])

    def test_uploading_the_file_with_files_clears_it(self):
        doc = {"metadata": {"name": "W"}, "spec": spec(Run=node("R", [{"name": "F", "type": "File"}]))}
        done = a.apply(doc, files=[{"activity": "Run", "input": "F", "value": "hash", "fileName": "a.toml"}])
        self.assertEqual(done["requiredInputsUnset"], [])

    def test_the_list_does_not_change_ready(self):
        doc = {"metadata": {"name": "W"}, "spec": spec(Run=node("R", [{"name": "T", "type": "Text"}]))}
        self.assertTrue(a.apply(doc)["ready"])


class FilesForEmptyFileInputs(unittest.TestCase):
    def doc(self):
        return {"metadata": {"name": "W"}, "spec": spec(Run=node("R", [
            {"name": "Empty", "type": "File"},
            {"name": "Mapped", "type": "File", "mapValueFrom": MAPPED},
            {"name": "Text", "type": "Text"},
        ]))}

    def put(self, name):
        return a.apply(self.doc(), files=[{"activity": "Run", "input": name, "value": "newhash", "fileName": "cfg.toml"}])

    def test_a_file_input_with_nothing_takes_an_uploaded_file(self):
        result = self.put("Empty")
        self.assertEqual(result["problems"], [])
        stored = result["doc"]["spec"]["activities"]["Run"]["action"]["reference"]["inputs"][0]
        self.assertEqual((stored["value"], stored["fileName"]), ("newhash", "cfg.toml"))

    def test_a_file_taken_from_an_earlier_step_does_not(self):
        self.assertEqual(len(self.put("Mapped")["problems"]), 1)

    def test_an_input_that_is_not_a_file_does_not(self):
        self.assertEqual(len(self.put("Text")["problems"]), 1)


class TheDecisionGate(unittest.TestCase):
    def doc(self):
        runs = {f"Run {n}": node("Convert", [{"name": "LogFile", "type": "File"}, {"name": "Query", "type": "Text"}]) for n in (1, 2)}
        runs["Other"] = node("Mail", [{"name": "LogFile", "type": "File"}])
        return {"metadata": {"name": "W"}, "spec": spec(**runs)}

    def gate(self, kept, **more):
        return a.apply(self.doc(), kept_inputs=kept, **more)

    def test_without_the_list_nothing_is_enforced(self):
        self.assertTrue(a.apply(self.doc())["ready"])

    def test_an_undecided_input_makes_it_not_ready_and_the_problem_says_what_to_do(self):
        result = self.gate([])
        self.assertFalse(result["ready"])
        self.assertEqual(len(result["problems"]), 3)
        self.assertTrue(all("kept_inputs" in p for p in result["problems"]))
        self.assertIn("set it with set_inputs", next(p for p in result["problems"] if "'Query'" in p))
        self.assertIn("upload its file with files", next(p for p in result["problems"] if "'LogFile' of the rule 'Convert'" in p))

    def test_the_same_input_of_one_rule_on_many_activities_is_one_entry(self):
        undecided = {(u["rule"], u["input"]): u["activities"] for u in self.gate([])["requiredInputsUndecided"]}
        self.assertEqual(undecided[("Convert", "LogFile")], ["Run 1", "Run 2"])
        self.assertEqual(len(undecided), 3)

    def test_a_kept_input_with_a_reason_is_decided_for_every_activity_of_that_rule(self):
        result = self.gate([{"rule": "Convert", "input": "LogFile", "reason": "the rule supplies it"}])
        self.assertEqual({(u["rule"], u["input"]) for u in result["requiredInputsUndecided"]}, {("Convert", "Query"), ("Mail", "LogFile")})

    def test_a_kept_input_without_a_reason_is_not_a_decision(self):
        result = self.gate([{"rule": "Convert", "input": "LogFile", "reason": "  "}])
        self.assertTrue(any("say why 'LogFile' of 'Convert' stays empty" in p for p in result["problems"]))
        self.assertIn(("Convert", "LogFile"), {(u["rule"], u["input"]) for u in result["requiredInputsUndecided"]})

    def test_naming_an_activity_decides_only_that_activity(self):
        result = self.gate([{"rule": "Convert", "input": "LogFile", "activity": "Run 1", "reason": "supplied"}])
        entry = next(u for u in result["requiredInputsUndecided"] if (u["rule"], u["input"]) == ("Convert", "LogFile"))
        self.assertEqual(entry["activities"], ["Run 2"])

    def test_setting_or_uploading_decides_it_and_everything_decided_is_ready(self):
        kept = [{"rule": "Mail", "input": "LogFile", "reason": "supplied"}]
        files = [{"activity": a_, "input": "LogFile", "value": "h", "fileName": "x"} for a_ in ("Run 1", "Run 2")]
        sets = [{"activity": a_, "input": "Query", "value": "q"} for a_ in ("Run 1", "Run 2")]
        result = self.gate(kept, files=files, set_inputs=sets)
        self.assertEqual((result["problems"], result["requiredInputsUndecided"], result["ready"]), ([], [], True))

    def test_an_entry_with_no_rule_or_input_is_reported(self):
        self.assertTrue(any("needs a rule and an input" in p for p in self.gate([{"input": "LogFile", "reason": "x"}])["problems"]))


class AssessmentInputsRead(unittest.TestCase):
    SAMPLE = "Fetches the config assessment input. Sample Config: " + "x" * 80

    def fetch(self, name, **extra):
        reference = {"name": "FetchAssessmentInput", "inputs": [{"name": "InputName", "type": "Text", "value": name}]}
        return {"action": {"type": "Rule", "reference": reference, **extra}}

    def test_each_activity_that_reads_one_is_listed_with_its_name_and_sample(self):
        found = b.assessment_inputs_read(spec(One=self.fetch("JiraWorkflowConfigFile", desc=self.SAMPLE), Two=self.fetch("AdminEmail")))
        self.assertEqual([(f["activity"], f["inputName"], bool(f["sample"])) for f in found], [("One", "JiraWorkflowConfigFile", True), ("Two", "AdminEmail", False)])

    def test_a_name_taken_from_an_earlier_step_has_no_name(self):
        node_ = {"action": {"type": "Rule", "reference": {"name": "FetchAssessmentInput", "inputs": [{"name": "InputName", "type": "Text", "mapValueFrom": MAPPED}]}}}
        self.assertEqual(b.assessment_inputs_read(spec(One=node_))[0]["inputName"], None)

    def test_other_rules_are_not_listed(self):
        self.assertEqual(b.assessment_inputs_read(spec(Run=node("Convert", [{"name": "InputName", "type": "Text", "value": "x"}]))), [])

    def test_the_chain_lists_each_name_once_with_everything_that_reads_it(self):
        one = {"assessmentInputsRead": b.assessment_inputs_read(spec(A=self.fetch("Cfg", desc=self.SAMPLE)))}
        two = {"assessmentInputsRead": b.assessment_inputs_read(spec(B=self.fetch("Cfg"), C=self.fetch("AdminEmail")))}
        merged = {m["inputName"]: m for m in b.chain_assessment_inputs({"W1": one, "W2": two})}
        self.assertEqual(set(merged), {"Cfg", "AdminEmail"})
        self.assertEqual(merged["Cfg"]["readBy"], [{"workflow": "W1", "activity": "A"}, {"workflow": "W2", "activity": "B"}])
        self.assertTrue(merged["Cfg"]["sample"])


class MappingIssues(unittest.TestCase):
    def issues(self, **activities):
        return [(i["activity"], i["input"]) for i in b.mapping_issues(spec(**activities))]

    def test_a_mapping_to_an_activity_that_is_there_is_fine(self):
        self.assertEqual(self.issues(Fetch=node("A", [], ["Out"]), Run=node("B", [{"name": "In", "type": "File", "mapValueFrom": MAPPED}])), [])

    def test_a_source_activity_that_is_not_in_the_workflow_is_reported(self):
        self.assertEqual(self.issues(Run=node("B", [{"name": "In", "type": "File", "mapValueFrom": MAPPED}])), [("Run", "In")])

    def test_an_output_the_source_does_not_declare_is_reported(self):
        self.assertEqual(self.issues(Fetch=node("A", [], ["Other"]), Run=node("B", [{"name": "In", "type": "File", "mapValueFrom": MAPPED}])), [("Run", "In")])

    def test_a_source_that_declares_no_outputs_is_not_judged(self):
        self.assertEqual(self.issues(Fetch=node("A", []), Run=node("B", [{"name": "In", "type": "File", "mapValueFrom": MAPPED}])), [])

    def test_an_event_mapping_without_a_field_is_reported_and_with_one_is_not(self):
        event = {"type": "Event", "source": {"displayable": "Ev", "type": "CUSTOM_EVENT"}}
        self.assertEqual(self.issues(Run=node("B", [{"name": "Id", "type": "Text", "mapValueFrom": event}])), [("Run", "Id")])
        self.assertEqual(self.issues(Run=node("B", [{"name": "Id", "type": "Text", "mapValueFrom": {**event, "outputField": "runId"}}])), [])


@unittest.skipUnless(JIRA_DIR, fixtures.HINT)
class TheJiraBlueprint(unittest.TestCase):
    def test_only_the_known_event_mapping_is_reported(self):
        config, subworkflows = fixtures.load_jira(JIRA_DIR)
        specs = [config["spec"]] + [d["spec"] for d in subworkflows.values()]
        issues = [i for s in specs for i in b.mapping_issues(s)]
        self.assertEqual([(i["input"]) for i in issues], ["AssessmentRunID"])
        self.assertGreater(sum(len(b.required_inputs_unset(s)) for s in specs), 0)


if __name__ == "__main__":
    unittest.main()
