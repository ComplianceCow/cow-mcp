import unittest

from tools.playbook import design_resolve as r


def doc(*steps):
    return {"spec": {"steps": list(steps)}}


def app(sid, name, app_type):
    return {"id": sid, "type": "create_application", "name": name, "config": {"applicationType": app_type}}


def control(sid, name, number, assessment="Okta Inventory", **config):
    return {"id": sid, "type": "create_control", "name": name, "level": "L1", "config": {"assessmentName": assessment, "displayable": number, **config}}


def rule(sid, name, **config):
    return {"id": sid, "type": "create_rule", "level": "L1", "name": name, "refs": {"rule": name}, "config": config}


TENANT = {
    "applications": [{"id": "a1", "name": "Okta app", "type": "OktaConnector", "validated": True}, {"id": "a2", "name": "Jira app", "type": "JiraCloud", "validated": False}],
    "availableTypes": ["OktaConnector", "JiraCloud", "HttpRequest", "NoCredApp"],
    "scopes": {"Okta scope": "s1"},
    "categories": ["Integrations", "Playbook case - 1"],
    "assessments": {"Okta Inventory": {"id": "p1", "controls": [{"number": "1", "name": "Revocation", "id": "c1"}, {"number": "3", "name": "Inventory", "id": "c3"}, {"number": "3.2", "name": "Group inventory", "id": "c32"}],
                                       "nextFreeNumber": {"": "4", "3": "3.3"}}},
    "rules": {"GetOktaUsers": {"where": "tenant"}, "NewFetch": {"where": "missing"}, "Odd": {"where": "unchecked"}},
    "workflows": {"WF1": "w1", "WF2": "w2"},
    "chains": {"Jira": ["WF4", "WF1", "WF2"], "Fresh": ["F1", "F2"], "Unknown": None},
}


def one(step, tenant=TENANT):
    return r.resolve(doc(step), tenant)["steps"][0]


class Applications(unittest.TestCase):
    def test_same_name_and_type_is_adopted_with_its_id(self):
        got = one(app("x", "Okta app", "OktaConnector"))
        self.assertEqual((got["action"], got["existingId"]), (r.ADOPT, "a1"))

    def test_same_name_with_another_type_is_a_conflict(self):
        got = one(app("x", "Okta app", "HttpRequest"))
        self.assertEqual(got["action"], r.CONFLICT)
        self.assertIn("OktaConnector", got["reason"])

    def test_a_type_that_is_not_installed_is_blocked(self):
        self.assertEqual(one(app("x", "AWS", "AWSAppConnector"))["action"], r.BLOCKED)

    def test_a_new_application_is_created_and_needs_credentials_unless_it_needs_none(self):
        got = r.resolve(doc(app("x", "Http app", "HttpRequest"), app("y", "No cred", "NoCredApp")), TENANT)
        self.assertEqual([s["action"] for s in got["steps"]], [r.CREATE, r.CREATE])
        self.assertEqual([c["application"] for c in got["credentialsNeeded"]], ["Http app"])

    def test_an_existing_unvalidated_application_needs_credentials(self):
        got = r.resolve(doc(app("x", "Jira app", "JiraCloud")), TENANT)
        self.assertEqual(got["steps"][0]["action"], r.ADOPT)
        self.assertEqual(got["credentialsNeeded"][0]["application"], "Jira app")


class Controls(unittest.TestCase):
    def test_a_number_held_by_another_control_is_a_conflict_with_the_next_free_number(self):
        got = one(control("c", "Suspended", "3.2"))
        self.assertEqual(got["action"], r.CONFLICT)
        self.assertIn("held by 'Group inventory'", got["reason"])
        self.assertIn("3.3", got["reason"])

    def test_a_parent_number_conflict_names_the_top_level_free_number(self):
        got = one(control("c", "Residual", "1"))
        self.assertEqual(got["action"], r.CONFLICT)
        self.assertIn("next free number: 4", got["reason"])

    def test_same_number_and_name_is_adopted_with_the_control_id(self):
        got = one(control("c", "Group inventory", "3.2"))
        self.assertEqual((got["action"], got["existingId"]), (r.ADOPT, "c32"))

    def test_a_control_with_the_same_name_at_another_number_is_adopted_and_the_difference_said(self):
        got = one(control("c", "Group inventory", "3.9"))
        self.assertEqual((got["action"], got["existingId"]), (r.ADOPT, "c32"))
        self.assertIn("exists in 'Okta Inventory' as number 3.2", got["reason"])

    def test_the_same_name_wins_even_when_the_designed_number_is_held_by_another_control(self):
        got = one(control("c", "Group inventory", "1"))
        self.assertEqual((got["action"], got["existingId"]), (r.ADOPT, "c32"))

    def test_a_name_that_exists_twice_falls_back_to_the_number(self):
        tenant = {**TENANT, "assessments": {"Okta Inventory": {"id": "p1", "controls": [{"number": "1", "name": "Dup", "id": "a"}, {"number": "2", "name": "Dup", "id": "b"}], "nextFreeNumber": {}}}}
        self.assertEqual(one(control("c", "Dup", "3"), tenant)["action"], r.CREATE)

    def test_a_free_number_is_created_in_the_existing_assessment(self):
        self.assertEqual(one(control("c", "New", "3.3"))["action"], r.CREATE)

    def test_a_control_in_a_new_assessment_is_created(self):
        self.assertEqual(one(control("c", "Root", "1", assessment="Brand New", categoryName="Integrations"))["action"], r.CREATE)

    def test_a_category_that_does_not_exist_is_created_with_the_new_assessment(self):
        got = r.resolve(doc(control("c", "Root", "1", assessment="Brand New", categoryName="Identity")), TENANT)
        self.assertEqual(got["steps"][0]["action"], r.CREATE)
        self.assertIn("category 'Identity' does not exist and is created", got["steps"][0]["reason"])
        self.assertTrue(got["ready"])


class Rules(unittest.TestCase):
    def test_an_existing_rule_is_adopted(self):
        self.assertEqual(one(rule("r", "GetOktaUsers"))["action"], r.ADOPT)

    def test_a_missing_rule_is_created_and_flagged_unproven(self):
        got = r.resolve(doc(rule("r", "NewFetch")), TENANT)
        self.assertEqual(got["steps"][0]["action"], r.CREATE)
        self.assertTrue(got["steps"][0]["unproven"])
        self.assertTrue(any("unproven" in x for x in got["risks"]))

    def test_a_rule_that_could_not_be_looked_up_is_blocked(self):
        self.assertEqual(one(rule("r", "Odd"))["action"], r.BLOCKED)

    def test_a_sql_rule_is_created(self):
        self.assertEqual(one(rule("r", "Join", sql="SELECT 1"))["action"], r.CREATE)

    def test_links_and_sql_evidence_say_that_their_existence_is_not_looked_up(self):
        self.assertIn("not looked up", one(rule("r", "Join", sql="SELECT 1"))["reason"])
        self.assertIn("not looked up", one({"id": "l", "type": "link_control", "config": {}})["reason"])


class Workflows(unittest.TestCase):
    def wf(self, folder):
        return {"id": "w", "type": "create_workflow", "name": "Jira workflow", "refs": {"workflow": folder}}

    def test_names_already_taken_are_a_conflict_that_lists_them(self):
        got = one(self.wf("Jira"))
        self.assertEqual(got["action"], r.CONFLICT)
        self.assertEqual(got["taken"], ["WF1", "WF2"])

    def test_a_chain_with_no_name_taken_is_created(self):
        self.assertEqual(one(self.wf("Fresh"))["action"], r.CREATE)

    def test_an_unlisted_chain_is_created_with_a_risk_noted(self):
        got = r.resolve(doc(self.wf("Unknown")), TENANT)
        self.assertEqual(got["steps"][0]["action"], r.CREATE)
        self.assertTrue(got["risks"])


class Overall(unittest.TestCase):
    def test_a_dependency_on_a_conflicting_control_is_noted(self):
        steps = [control("a", "Suspended", "3.2"), {"id": "l", "type": "link_control", "config": {"sourceControl": "a", "targetControl": "z"}}]
        got = r.resolve(doc(*steps), TENANT)
        self.assertIn("not resolved", got["steps"][1]["note"])

    def test_ready_only_when_nothing_conflicts_or_is_blocked(self):
        self.assertTrue(r.resolve(doc(app("x", "Okta app", "OktaConnector"), control("c", "New", "3.3")), TENANT)["ready"])
        self.assertFalse(r.resolve(doc(control("c", "Suspended", "3.2")), TENANT)["ready"])

    def test_the_ids_of_the_existing_assessments_of_the_design_are_returned(self):
        got = r.resolve(doc(control("c", "New", "3.3")), TENANT)
        self.assertEqual(got["assessments"], [{"name": "Okta Inventory", "id": "p1"}])

    def test_an_assessment_the_design_does_not_mention_is_left_out(self):
        got = r.resolve(doc(app("x", "Okta app", "OktaConnector")), TENANT)
        self.assertEqual(got["assessments"], [])

    def test_unknown_type_lists_do_not_block(self):
        tenant = {**TENANT, "availableTypes": None}
        self.assertEqual(one(app("x", "AWS", "AWSAppConnector"), tenant)["action"], r.CREATE)


if __name__ == "__main__":
    unittest.main()


class ValuesNeeded(unittest.TestCase):
    STEP = {"id": "w", "type": "create_workflow", "name": "Jira flow", "refs": {"workflow": "Jira"}, "config": {}}

    def resolve(self, inputs):
        return r.resolve(doc(self.STEP), {**TENANT, "blueprintInputs": {"Jira": inputs}})["valuesNeeded"]

    def test_the_addresses_a_sample_names_are_shown_for_confirmation(self):
        got = self.resolve([{"inputName": "Config", "sample": "Assignee: a@x.com, support: s@x.com, again s@x.com"}])
        self.assertEqual(got[0]["addressesInSample"], ["a@x.com", "s@x.com"])
        self.assertEqual((got[0]["workflow"], got[0]["input"], got[0]["kind"]), ("Jira", "Config", "file"))

    def test_an_input_without_a_sample_asks_what_it_must_hold(self):
        got = self.resolve([{"inputName": "AdminEmail", "sample": None}])
        self.assertEqual((got[0]["input"], got[0]["kind"]), ("AdminEmail", "value"))

    def test_a_sample_without_addresses_needs_nothing_from_a_person(self):
        self.assertEqual(self.resolve([{"inputName": "Config", "sample": "a file with no contact data"}]), [])

    def test_nothing_is_asked_without_a_workflow_step(self):
        self.assertEqual(r.resolve(doc(app("x", "Okta app", "OktaConnector")), {**TENANT, "blueprintInputs": {"Jira": [{"inputName": "A", "sample": None}]}})["valuesNeeded"], [])


class Scopes(unittest.TestCase):
    def scope_doc(self):
        scope = {"id": "sc", "type": "create_application_scope", "name": "Okta scope", "prerequisiteSteps": ["ok"], "config": {}}
        return doc(app("ok", "Okta app", "OktaConnector"), scope)

    def resolve(self, bound):
        return r.resolve(self.scope_doc(), {**TENANT, "scopeApplications": {"Okta scope": bound}})["steps"][1]

    def test_a_scope_bound_to_the_designs_applications_is_adopted(self):
        self.assertEqual(self.resolve({"a1", "other"})["action"], r.ADOPT)

    def test_a_scope_bound_to_other_applications_is_a_conflict(self):
        got = self.resolve({"zz"})
        self.assertEqual(got["action"], r.CONFLICT)
        self.assertIn("Okta app", got["reason"])


class CredentialChoices(unittest.TestCase):
    def test_a_new_application_reports_its_credential_type_and_the_alternatives(self):
        step = {"id": "j", "type": "create_application", "name": "Jira new", "config": {"applicationType": "JiraCloud", "creadentialType": "OAuth 1.1.1"}}
        tenant = {**TENANT, "typeCredentials": {"JiraCloud": ["OAuth 1.1.1", "BasicAuthentication 1.1.1"]}}
        got = r.resolve(doc(step), tenant)["credentialsNeeded"][0]
        self.assertEqual((got["credentialType"], got["otherCredentialTypes"]), ("OAuth 1.1.1", ["BasicAuthentication 1.1.1"]))

    def test_a_type_with_one_credential_type_offers_no_alternative(self):
        step = {"id": "j", "type": "create_application", "name": "Jira new", "config": {"applicationType": "JiraCloud", "credentialType": "OAuth 1.1.1"}}
        got = r.resolve(doc(step), {**TENANT, "typeCredentials": {"JiraCloud": ["OAuth 1.1.1"]}})["credentialsNeeded"][0]
        self.assertNotIn("otherCredentialTypes", got)
