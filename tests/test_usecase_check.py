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


def errors(document, rc=None, confirmed=True, user_configurable=None, rule_systems=None):
    return u.check(document, rc, confirmed, user_configurable, rule_systems)["errors"]


def messages(document, rc=None, confirmed=True, user_configurable=None, rule_systems=None):
    return [e["message"] for e in errors(document, rc, confirmed, user_configurable, rule_systems)]


def l1_rule(step_id, name, description, assessment="A"):
    return {"id": step_id, "type": "create_rule", "level": "L1", "name": name, "description": description, "prerequisiteSteps": [], "refs": {"rule": name}, "config": {"assessmentName": assessment}}


def action(step_id, evidence, prerequisites, assessment="A"):
    return {"id": step_id, "type": "create_action", "level": "L1", "prerequisiteSteps": list(prerequisites), "config": {"evidenceName": evidence, "assessmentName": assessment}}


class L1Producer(unittest.TestCase):
    def check(self, document, rc, new_rules=None):
        return u.check(document, rc, True, None, None, new_rules)

    def test_an_l1_rule_before_the_action_is_the_producer(self):
        document = doc(l1_rule("r", "CheckX", "Produces XReport with one verdict per bucket"), action("a", "XReport", ["r"]))
        self.assertEqual(self.check(document, {"XReport": []})["errors"], [])

    def test_the_rule_is_found_through_a_control_step(self):
        control = {"id": "c", "type": "create_control", "level": "L1", "prerequisiteSteps": ["r"]}
        document = doc(l1_rule("r", "CheckX", "Produces XReport"), control, action("a", "XReport", ["c"]))
        self.assertEqual(self.check(document, {"XReport": []})["errors"], [])

    def test_no_rule_before_the_action_is_an_error(self):
        got = self.check(doc(action("a", "XReport", [])), {"XReport": []})["errors"]
        self.assertTrue(any("no rule step before this one" in e["message"] for e in got))

    def test_a_new_rule_must_state_the_required_columns(self):
        document = doc(l1_rule("r", "CheckX", "Produces XReport with one verdict per bucket"), action("a", "XReport", ["r"]))
        got = self.check(document, {"XReport": ["AssignedToUserID", "CallerID"]}, ["CheckX"])["errors"]
        self.assertTrue(any("new rule" in e["message"] and "AssignedToUserID, CallerID" in e["message"] for e in got))

    def test_a_new_rule_that_states_them_passes(self):
        document = doc(l1_rule("r", "CheckX", "Produces XReport; AssignedToUserID and CallerID at position 8"), action("a", "XReport", ["r"]))
        self.assertEqual(self.check(document, {"XReport": ["AssignedToUserID", "CallerID"]}, ["CheckX"])["errors"], [])

    def test_an_existing_rule_only_gets_a_warning(self):
        document = doc(l1_rule("r", "CheckX", "Produces XReport"), action("a", "XReport", ["r"]))
        got = self.check(document, {"XReport": ["CallerID"]})
        self.assertEqual(got["errors"], [])
        self.assertTrue(any("existing rule" in w["message"] for w in got["warnings"]))

    def test_columns_must_still_be_declared(self):
        document = doc(l1_rule("r", "CheckX", "Produces XReport"), action("a", "XReport", ["r"]))
        self.assertTrue(any("says nothing about" in e["message"] for e in self.check(document, {})["errors"]))


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


class SelectListEdgeCases(unittest.TestCase):
    def names(self, sql):
        return [i["name"] for i in u.select_list(sql)["items"]]

    def test_an_alias_without_as_gives_the_name(self):
        self.assertEqual(self.names("SELECT w.ResourceName ResourceName, 'x' Source, 1 \"Total\" FROM T w"), ["ResourceName", "Source", "Total"])

    def test_an_expression_that_only_looks_like_an_alias_has_no_name(self):
        for sql in ("SELECT a + b FROM T", "SELECT a AND b FROM T", "SELECT x IS NULL FROM T", "SELECT CASE WHEN a THEN b END FROM T",
                    "SELECT NOT a FROM T", "SELECT a, b DESC FROM T"):
            self.assertIn(None, self.names(sql), sql)

    def test_a_union_takes_its_names_from_the_first_select(self):
        got = u.select_list("SELECT a AS One, b AS Two FROM X UNION ALL SELECT c AS Three, d AS Four FROM Y")
        self.assertEqual(([i["name"] for i in got["items"]], got["from"], got["setOperation"]), (["One", "Two"], "X", True))

    def test_a_union_of_selects_without_from_stops_at_the_operator(self):
        got = u.select_list("SELECT 1 AS One UNION SELECT 2 AS Two")
        self.assertEqual(([i["name"] for i in got["items"]], got["from"]), (["One"], None))

    def test_a_with_query_with_a_union_in_its_final_select(self):
        got = u.select_list("WITH x AS (SELECT a FROM T) SELECT a AS One FROM x UNION ALL SELECT a AS Two FROM x")
        self.assertEqual([i["name"] for i in got["items"]], ["One"])

    def test_quoted_and_backtick_aliases_are_read_without_their_quotes(self):
        self.assertEqual(self.names('SELECT a AS "Resource Name", b AS `Col` FROM T'), ["Resource Name", "Col"])

    def test_a_plain_query_has_no_set_operation(self):
        self.assertFalse(u.select_list("SELECT a AS A FROM T")["setOperation"])


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

    def test_an_expression_that_cannot_be_named_is_a_warning_and_the_evidence_is_not_judged(self):
        result = u.check(doc(rule("r", "E", columns(EXTRAS) + ", a + b")), None, True)
        self.assertEqual(result["errors"], [])
        self.assertTrue(any("no column name could be told" in w["message"] for w in result["warnings"]))

    def test_columns_that_cannot_be_read_are_not_reported_as_missing(self):
        document = doc(rule("r", "E", columns(EXTRAS) + ", a + b"), workflow("w", "E", ["r"]))
        result = u.check(document, {"E": ["TicketID"]}, True)
        self.assertEqual(result["errors"], [])


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
        self.assertTrue(any("no rule step before this one writes" in m for m in messages(doc(workflow("w", "Nothing", [])), {"Nothing": []})))

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

    def test_a_workflow_that_starts_on_another_assessment_than_its_evidence_is_an_error(self):
        producer = rule("r", "OkReport", columns())
        producer["config"]["assessmentName"] = "ZZ L2"
        step = workflow("w", "OkReport", ["r"])
        step["config"]["assessmentName"] = "NIST 800-53 v5"
        got = messages(doc(producer, step), {"OkReport": []})
        self.assertTrue(any("never see its evidence" in m and "'ZZ L2'" in m for m in got))

    def test_the_same_assessment_passes(self):
        producer = rule("r", "OkReport", columns())
        producer["config"]["assessmentName"] = "ZZ L2"
        step = workflow("w", "OkReport", ["r"])
        step["config"]["assessmentName"] = "ZZ L2"
        self.assertEqual(errors(doc(producer, step), {"OkReport": []}), [])

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


class UserInputs(unittest.TestCase):
    def doc_with(self, inputs, sql_extra="", config=None):
        step = rule("r", "OkReport", columns(EXTRAS))
        step["config"]["sql"] += sql_extra
        if config:
            step["config"].update(config)
        document = doc(step)
        document["spec"]["inputs"] = inputs
        return document

    def test_an_input_that_is_declared_and_used_passes(self):
        document = self.doc_with({"slaHours": {"type": "integer", "default": 24}}, " AND age < ${{ inputs.slaHours }}")
        self.assertEqual(errors(document, user_configurable=["slaHours"]), [])

    def test_an_input_used_but_not_declared_is_an_error_naming_the_step(self):
        got = errors(self.doc_with({}, " AND age < ${{ inputs.slaHours }}"))
        self.assertEqual([(e["check"], e["step"]) for e in got], [("inputs", "r")])
        self.assertIn("slaHours", got[0]["message"])

    def test_an_input_in_refs_or_config_other_than_sql_counts_too(self):
        document = self.doc_with({"slaHours": {"type": "integer"}}, config={"note": "limit ${{inputs.slaHours}}"})
        self.assertEqual(errors(document, user_configurable=["slaHours"]), [])

    def test_a_configurable_value_the_use_case_does_not_declare_is_an_error(self):
        self.assertTrue(any("does not declare it" in m for m in messages(self.doc_with({}), user_configurable=["slaHours"])))

    def test_a_declared_value_that_no_step_uses_is_an_error_when_the_requirement_makes_it_configurable(self):
        got = messages(self.doc_with({"slaHours": {"type": "integer"}}), user_configurable=["slaHours"])
        self.assertTrue(any("would change nothing" in m for m in got))

    def test_a_declared_input_nobody_uses_is_only_a_warning_without_a_requirement(self):
        result = u.check(self.doc_with({"spare": {"type": "string"}}), None, True)
        self.assertEqual(result["errors"], [])
        self.assertTrue(any("spare" in w["message"] for w in result["warnings"]))

    def test_no_configurable_values_and_no_inputs_is_fine(self):
        self.assertEqual(errors(self.doc_with({}), user_configurable=[]), [])

    def test_an_input_used_only_in_message_text_is_an_error(self):
        message = ", 'Grace period of ${{ inputs.slaHours }} hours' AS Note"
        got = messages(self.doc_with({"slaHours": {"type": "integer"}}, message))
        self.assertTrue(any("only used inside message text" in m for m in got))

    def test_an_input_concatenated_into_text_is_still_only_message_text(self):
        message = ", 'Grace period: ' || ${{ inputs.slaHours }} || ' hours' AS Note"
        got = messages(self.doc_with({"slaHours": {"type": "integer"}}, message))
        self.assertTrue(any("only used inside message text" in m for m in got))

    def test_an_input_inside_an_interval_comparison_is_applied(self):
        sql = " AND o.StatusChanged > w.TerminationDate + INTERVAL '${{ inputs.slaHours }}' HOUR"
        self.assertEqual(errors(self.doc_with({"slaHours": {"type": "integer"}}, sql)), [])

    def test_an_input_applied_in_one_rule_and_quoted_in_another_passes(self):
        sql = " AND age < ${{ inputs.slaHours }} AND '${{ inputs.slaHours }} hours' <> ''"
        self.assertEqual(errors(self.doc_with({"slaHours": {"type": "integer"}}, sql)), [])


class SingleSystemL1(unittest.TestCase):
    def l1(self, step_id, rule, assessment):
        return {"id": step_id, "type": "create_rule", "level": "L1", "name": rule, "refs": {"rule": rule}, "config": {"assessmentName": assessment}}

    def test_one_system_per_l1_assessment_passes(self):
        document = doc(self.l1("a", "FetchUsersFromWorkday", "Workday"), self.l1("b", "GetOktaUsers", "Okta"))
        self.assertEqual(errors(document, rule_systems={"FetchUsersFromWorkday": "httprequest", "GetOktaUsers": "oktaconnector"}), [])

    def test_two_systems_in_one_l1_assessment_is_an_error_that_names_them(self):
        document = doc(self.l1("a", "FetchUsersFromWorkday", "Okta Termination"), self.l1("b", "GetOktaUsers", "Okta Termination"))
        got = messages(document, rule_systems={"FetchUsersFromWorkday": "httprequest", "GetOktaUsers": "oktaconnector"})
        self.assertEqual(len(got), 1)
        self.assertIn("'Okta Termination'", got[0])
        self.assertIn("httprequest, oktaconnector", got[0])

    def test_two_connector_types_of_one_product_are_one_system(self):
        document = doc(self.l1("a", "GetOktaUsers", "Okta"), self.l1("b", "GetOktaUsersGroupsFactorsV2", "Okta"))
        self.assertEqual(errors(document, rule_systems={"GetOktaUsers": "okta", "GetOktaUsersGroupsFactorsV2": "okta"}), [])

    def test_a_rule_that_needs_no_application_does_not_count_as_a_system(self):
        document = doc(self.l1("a", "GetOktaUsers", "Okta"), self.l1("b", "ReconcileTerminatedUsersOktaWorkday", "Okta"))
        self.assertEqual(errors(document, rule_systems={"GetOktaUsers": "oktaconnector", "ReconcileTerminatedUsersOktaWorkday": "nocredapp"}), [])

    def test_a_rule_missing_from_the_map_is_an_error(self):
        got = messages(doc(self.l1("a", "GetOktaUsers", "Okta")), rule_systems={})
        self.assertTrue(any("no entry for the L1 rule 'GetOktaUsers'" in m for m in got))

    def test_without_the_map_nothing_is_checked(self):
        document = doc(self.l1("a", "FetchUsersFromWorkday", "X"), self.l1("b", "GetOktaUsers", "X"))
        self.assertEqual(errors(document), [])

    def test_sql_rules_and_other_levels_are_not_l1_rules(self):
        document = doc(rule("r", "OkReport", columns(EXTRAS), level="L2"))
        self.assertEqual(errors(document, rule_systems={}), [])


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


class RuleApplicationTypes(unittest.TestCase):
    def rule(self, name, assessment="a"):
        return {"id": f"r-{name}", "type": "create_rule", "level": "L1", "name": name, "refs": {"rule": name, "assessment": assessment}, "config": {"assessmentName": assessment}}

    def app(self, app_id, app_type):
        return {"id": app_id, "type": "create_application", "config": {"applicationType": app_type}}

    def scope(self, apps, assessment="a"):
        return {"id": f"scope-{assessment}", "type": "create_application_scope", "prerequisiteSteps": list(apps), "config": {"assessment": assessment}}

    def run_check(self, document, types):
        return u.check(document, None, True, None, None, None, types)

    def test_a_scope_holding_the_type_passes(self):
        document = doc(self.app("o", "OktaConnector"), self.scope(["o"]), self.rule("GetOktaUsers"))
        self.assertEqual(self.run_check(document, {"GetOktaUsers": "oktaconnector"})["errors"], [])

    def test_a_rule_whose_type_the_scope_lacks_is_an_error_that_names_what_it_holds(self):
        document = doc(self.app("o", "OktaConnector"), self.scope(["o"]), self.rule("GetOktaUsers"), self.rule("GetOktaUsersGroupsFactorsV2"))
        got = self.run_check(document, {"GetOktaUsers": "OktaConnector", "GetOktaUsersGroupsFactorsV2": "HttpRequest"})["errors"]
        self.assertEqual(len(got), 1)
        self.assertIn("GetOktaUsersGroupsFactorsV2", got[0]["message"])
        self.assertIn("OktaConnector", got[0]["message"])

    def test_any_of_several_acceptable_types_is_enough(self):
        document = doc(self.app("o", "HttpRequest"), self.scope(["o"]), self.rule("X"))
        self.assertEqual(self.run_check(document, {"X": ["OktaConnector", "HttpRequest"]})["errors"], [])

    def test_a_rule_without_an_entry_is_an_error(self):
        document = doc(self.app("o", "HttpRequest"), self.scope(["o"]), self.rule("X"))
        self.assertTrue(any("no entry for the L1 rule 'X'" in e["message"] for e in self.run_check(document, {})["errors"]))

    def test_a_missing_scope_is_only_a_warning(self):
        got = self.run_check(doc(self.rule("X")), {"X": "HttpRequest"})
        self.assertEqual(got["errors"], [])
        self.assertTrue(got["warnings"])

    def test_nothing_is_checked_without_the_map(self):
        self.assertEqual(u.check(doc(self.rule("X")), None, True)["errors"], [])


class ExistingApplications(unittest.TestCase):
    def app(self, name, ref=True):
        return {"id": name, "type": "create_application", "name": name, "refs": {"application": name} if ref else {}, "config": {"applicationType": "Okta"}}

    def run_check(self, document, existing):
        return u.check(document, None, True, None, None, None, None, existing)["errors"]

    def test_a_reference_to_an_application_the_tenant_has_passes(self):
        self.assertEqual(self.run_check(doc(self.app("Okta")), ["Okta"]), [])

    def test_a_reference_the_tenant_lacks_is_an_error(self):
        got = self.run_check(doc(self.app("Okta")), [])
        self.assertEqual(len(got), 1)
        self.assertIn("clear refs", got[0]["message"])

    def test_an_application_to_create_has_no_reference_and_passes(self):
        self.assertEqual(self.run_check(doc(self.app("Okta", ref=False)), []), [])

    def test_without_the_list_nothing_is_checked(self):
        self.assertEqual(u.check(doc(self.app("Okta")), None, True)["errors"], [])

    def test_a_reference_whose_type_differs_is_an_error(self):
        got = self.run_check(doc(self.app("Okta")), [{"name": "Okta", "type": "HttpRequest"}])
        self.assertTrue(any("is of type httprequest but the step needs okta" in e["message"] for e in got))

    def test_a_reference_of_the_right_type_passes(self):
        self.assertEqual(self.run_check(doc(self.app("Okta")), [{"name": "Okta", "type": "Okta"}]), [])

    def test_creating_an_application_under_a_name_the_tenant_has_is_an_error(self):
        got = self.run_check(doc(self.app("Connect Okta application", ref=False)), [{"name": "Connect Okta application", "type": "HttpRequest"}])
        self.assertEqual(len(got), 1)
        self.assertIn("already has an application with that name (type httprequest)", got[0]["message"])

    def test_a_new_name_passes(self):
        self.assertEqual(self.run_check(doc(self.app("Okta via connector", ref=False)), [{"name": "Connect Okta application", "type": "HttpRequest"}]), [])


class ExistingControls(unittest.TestCase):
    def control(self, number, name, assessment="Okta User Inventory"):
        return {"id": f"c{number}", "type": "create_control", "name": name, "level": "L1", "config": {"assessmentName": assessment, "displayable": number}}

    def run_check(self, step, held):
        return u.check(doc(step), None, True, None, None, None, None, None, held)

    HELD = {"Okta User Inventory": [{"number": "1", "name": "Terminated User Access Revocation"}, {"number": "3.2", "name": "Okta Users with Group Memberships"}]}

    def test_a_number_held_by_another_control_is_an_error(self):
        got = self.run_check(self.control("3.2", "Okta Suspended Users Inventory"), self.HELD)["errors"]
        self.assertEqual(len(got), 1)
        self.assertIn("held by 'Okta Users with Group Memberships'", got[0]["message"])

    def test_a_parent_number_is_checked_too(self):
        self.assertEqual(len(self.run_check(self.control("1", "Residual Group Membership Check"), self.HELD)["errors"]), 1)

    def test_a_free_number_passes(self):
        self.assertEqual(self.run_check(self.control("3.3", "Okta Suspended Users Inventory"), self.HELD)["errors"], [])

    def test_reusing_a_control_with_the_same_number_and_name_passes(self):
        self.assertEqual(self.run_check(self.control("3.2", "Okta Users with Group Memberships"), self.HELD)["errors"], [])

    def test_the_same_name_under_another_number_is_a_warning(self):
        got = self.run_check(self.control("3.4", "Okta Users with Group Memberships"), self.HELD)
        self.assertEqual(got["errors"], [])
        self.assertTrue(got["warnings"])

    def test_a_new_assessment_is_not_checked(self):
        self.assertEqual(self.run_check(self.control("1", "Anything", assessment="Brand New"), self.HELD)["errors"], [])

    def test_without_the_map_nothing_is_checked(self):
        self.assertEqual(u.check(doc(self.control("3.2", "x")), None, True)["errors"], [])
