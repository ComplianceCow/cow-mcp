import asyncio
import unittest

import yaml

from tools.playbook import usecase_check as u

EXTRAS = ["TerminationDate"]
TICKET = ["TicketID", "JiraTicketURL"]


def columns(extras=(), literal=(), first=None, last=None):
    items = list(first or u.FIRST_KEYS) + list(extras) + [f"'' AS {c}" for c in literal] + list(last or u.LAST_KEYS)
    return ", ".join(items)


def rule(step_id, evidence, select, source="Upstream", level="L2", prerequisites=()):
    return {"id": step_id, "type": "create_rule", "level": level, "prerequisiteSteps": list(prerequisites),
            "config": {"evidenceName": evidence, "sql": f"SELECT {select} FROM {source} WHERE ComplianceStatus = 'NON_COMPLIANT'"}}


def workflow(step_id, evidence, prerequisites, level="L2", folder="JiraGenericWorkflow_PlaybookVersion"):
    return {"id": step_id, "type": "create_workflow", "level": level, "prerequisiteSteps": list(prerequisites),
            "refs": {"workflow": folder}, "config": {"evidenceName": evidence}}


def doc(*steps):
    return {"spec": {"steps": list(steps)}}


def errors(document, rc=None, confirmed=True):
    return u.check(document, rc, confirmed)["errors"]


def messages(document, rc=None, confirmed=True):
    return [e["message"] for e in errors(document, rc, confirmed)]


class Parse(unittest.TestCase):
    def test_a_colon_followed_by_a_space_in_an_unquoted_value_is_found_with_its_line(self):
        _, problem = u.parse("spec:\n  steps:\n    - id: a\n      description: Creates 4 workflows from the blueprint X: A, B\n")
        self.assertEqual(problem["check"], "yaml")
        self.assertIn("line 4", problem["message"])
        self.assertIn("quotes", problem["message"])

    def test_valid_yaml_has_no_problem(self):
        self.assertIsNone(u.parse("spec: {steps: []}")[1])


class SelectList(unittest.TestCase):
    def test_names_come_from_the_alias_or_the_last_part_of_a_qualified_name(self):
        got = u.select_list("SELECT w.ResourceID, 'User' AS ResourceType, CASE WHEN a = 1 THEN 'x, y' ELSE 'z' END AS ComplianceStatus, COALESCE(a, b) AS Total FROM Foo f")
        self.assertEqual([(i["name"], i["bare"]) for i in got["items"]], [("ResourceID", True), ("ResourceType", False), ("ComplianceStatus", False), ("Total", False)])
        self.assertEqual(got["from"], "Foo")

    def test_commas_in_calls_and_quotes_do_not_split_a_column(self):
        got = u.select_list("SELECT CONCAT(a, ',', b) AS Full, 'a,b' AS Two FROM T")
        self.assertEqual([i["name"] for i in got["items"]], ["Full", "Two"])

    def test_a_star_is_reported_and_comments_are_ignored(self):
        got = u.select_list("SELECT * -- every column, FROM somewhere\nFROM Upstream")
        self.assertEqual((got["star"], got["items"], got["from"]), (True, [], "Upstream"))

    def test_a_with_query_is_read_at_its_final_select(self):
        got = u.select_list("WITH x AS (SELECT a, b FROM T) SELECT x.a AS One, x.b AS Two FROM x")
        self.assertEqual([i["name"] for i in got["items"]], ["One", "Two"])

    def test_an_expression_without_a_name_has_none(self):
        self.assertIsNone(u.select_list("SELECT a + b FROM T")["items"][0]["name"])

    def test_from_inside_a_function_is_not_the_end_of_the_list(self):
        got = u.select_list("SELECT EXTRACT(DAY FROM d) AS Day, e AS E FROM T")
        self.assertEqual([i["name"] for i in got["items"]], ["Day", "E"])


class EvidenceStructure(unittest.TestCase):
    def test_a_correct_list_passes(self):
        self.assertEqual(errors(doc(rule("r", "OkReport", columns(EXTRAS)))), [])

    def test_a_missing_mandatory_key_is_named(self):
        select = columns(last=[k for k in u.LAST_KEYS if k != "EvaluatedTime"])
        self.assertTrue(any("EvaluatedTime" in m for m in messages(doc(rule("r", "OkReport", select)))))

    def test_keys_out_of_order_are_reported(self):
        select = columns(first=["Source", "System"] + u.FIRST_KEYS[2:])
        self.assertTrue(any("first seven columns" in m for m in messages(doc(rule("r", "OkReport", select)))))

    def test_a_requirement_key_after_the_verdict_columns_is_reported(self):
        select = ", ".join(u.FIRST_KEYS + u.LAST_KEYS + ["Extra"])
        self.assertTrue(any("last eight columns" in m for m in messages(doc(rule("r", "OkReport", select)))))

    def test_a_filter_that_selects_everything_is_left_alone(self):
        self.assertEqual(errors(doc(rule("r", "Filtered", "*"))), [])

    def test_an_unnamed_expression_is_an_error(self):
        self.assertTrue(any("no AS name" in m for m in messages(doc(rule("r", "E", columns(EXTRAS) + ", a + b")))))


class Remediation(unittest.TestCase):
    def good(self):
        return doc(rule("r", "OkReport", columns(EXTRAS, TICKET)), workflow("w", "OkReport", ["r"]))

    def test_everything_in_place_is_valid(self):
        self.assertTrue(u.check(self.good(), {"OkReport": TICKET}, True)["valid"])

    def test_columns_that_were_not_declared_are_an_error(self):
        self.assertTrue(any("says nothing about 'OkReport'" in m for m in messages(self.good(), {})))

    def test_an_empty_declaration_is_accepted(self):
        self.assertEqual(errors(doc(rule("r", "OkReport", columns(EXTRAS)), workflow("w", "OkReport", ["r"])), {"OkReport": []}), [])

    def test_missing_columns_are_one_error_listing_them(self):
        document = doc(rule("r", "OkReport", columns(EXTRAS)), workflow("w", "OkReport", ["r"]))
        got = [m for m in messages(document, {"OkReport": TICKET}) if "required column" in m]
        self.assertEqual(len(got), 1)
        self.assertIn("TicketID, JiraTicketURL", got[0])

    def test_a_column_after_the_verdict_columns_is_not_at_position_8(self):
        select = ", ".join(u.FIRST_KEYS + u.LAST_KEYS + TICKET)
        self.assertTrue(any("not at position 8" in m for m in messages(doc(rule("r", "OkReport", select), workflow("w", "OkReport", ["r"])), {"OkReport": TICKET})))

    def test_select_star_on_an_anchored_evidence_is_an_error(self):
        self.assertTrue(any("SELECT *" in m for m in messages(doc(rule("r", "OkReport", "*"), workflow("w", "OkReport", ["r"])), {"OkReport": TICKET})))

    def test_a_bare_name_the_upstream_evidence_lacks_is_an_error(self):
        up = rule("up", "Upstream", columns(EXTRAS))
        down = rule("r", "OkReport", columns(EXTRAS, ["TicketID"]).replace("'' AS TicketID", "TicketID"), source="Upstream", prerequisites=["up"])
        got = messages(doc(up, down, workflow("w", "OkReport", ["r"])), {"OkReport": ["TicketID"]})
        self.assertTrue(any("bare name" in m and "upstream evidence 'Upstream' does not have it" in m for m in got))

    def test_a_bare_name_the_upstream_evidence_has_passes(self):
        up = rule("up", "Upstream", columns(EXTRAS, ["TicketID"]).replace("'' AS TicketID", "TicketID"))
        down = rule("r", "OkReport", columns(EXTRAS, ["TicketID"]).replace("'' AS TicketID", "TicketID"), source="Upstream", prerequisites=["up"])
        self.assertEqual(errors(doc(up, down, workflow("w", "OkReport", ["r"])), {"OkReport": ["TicketID"]}), [])

    def test_an_evidence_nothing_writes_is_an_error(self):
        self.assertTrue(any("no create_rule step writes" in m for m in messages(doc(workflow("w", "Nothing", [])), {"Nothing": []})))

    def test_the_rule_must_be_a_prerequisite(self):
        self.assertTrue(any("not in this step's prerequisiteSteps" in m for m in messages(doc(rule("r", "OkReport", columns()), workflow("w", "OkReport", [])), {"OkReport": []})))

    def test_both_layers_are_checked_not_only_the_first(self):
        l2 = rule("r2", "L2Report", columns(EXTRAS, TICKET), level="L2")
        l3 = rule("r3", "L3Report", columns(EXTRAS), level="L3")
        document = doc(l2, l3, workflow("w2", "L2Report", ["r2"], "L2"), workflow("w3", "L3Report", ["r3"], "L3"))
        got = errors(document, {"L2Report": TICKET, "L3Report": TICKET})
        self.assertEqual([e["step"] for e in got], ["r3"])

    def test_a_workflow_reference_with_spaces_is_an_error(self):
        document = doc(rule("r", "OkReport", columns()), workflow("w", "OkReport", ["r"], folder="Jira Generic Workflow"))
        self.assertTrue(any("no spaces" in m for m in messages(document, {"OkReport": []})))

    def test_a_remediation_at_another_layer_than_its_evidence_is_a_warning(self):
        document = doc(rule("r", "OkReport", columns(), level="L2"), workflow("w", "OkReport", ["r"], "L3"))
        result = u.check(document, {"OkReport": []}, True)
        self.assertTrue(result["valid"])
        self.assertTrue(any("produced at L2" in w["message"] for w in result["warnings"]))


class TheDecision(unittest.TestCase):
    def test_a_remediation_the_user_did_not_confirm_is_an_error(self):
        document = doc(rule("r", "OkReport", columns()), workflow("w", "OkReport", ["r"]))
        self.assertTrue(any("not confirmed" in m for m in messages(document, {"OkReport": []}, confirmed=False)))

    def test_findings_with_no_remediation_need_the_users_answer_too(self):
        self.assertTrue(any("not confirmed" in m for m in messages(doc(rule("r", "OkReport", columns())), confirmed=False)))
        self.assertEqual(errors(doc(rule("r", "OkReport", columns())), confirmed=True), [])


class Structure(unittest.TestCase):
    def test_empty_steps_are_invalid(self):
        self.assertFalse(u.check({"spec": {}}, None, True)["valid"])

    def test_duplicate_ids_and_unknown_prerequisites_are_reported(self):
        document = doc({"id": "a", "type": "create_control"}, {"id": "a", "type": "create_control", "prerequisiteSteps": ["ghost"]})
        got = messages(document)
        self.assertTrue(any("used twice" in m for m in got) and any("'ghost'" in m for m in got))


class TheTool(unittest.TestCase):
    def test_a_text_that_does_not_parse_is_reported_by_the_tool(self):
        result = asyncio.run(u.check_use_case_design("a: b: c"))
        self.assertFalse(result["valid"])
        self.assertEqual(result["errors"][0]["check"], "yaml")

    def test_a_valid_document_passes_through_the_tool(self):
        text = yaml.safe_dump(doc(rule("r", "OkReport", columns(EXTRAS, TICKET)), workflow("w", "OkReport", ["r"])), sort_keys=False)
        self.assertTrue(asyncio.run(u.check_use_case_design(text, {"OkReport": TICKET}, True))["valid"])


if __name__ == "__main__":
    unittest.main()
