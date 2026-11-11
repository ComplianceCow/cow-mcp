import copy
import unittest

from tools.playbook import compliance_logic as c

MFA = {
    "id": "mfa", "title": "MFA enrolment", "about": "Every active user has enrolled in MFA, unless they joined recently.",
    "level": "L2", "step": "MFA Reconciliation Rule", "control": "MFA Check",
    "fields": [{"id": "status", "label": "User status", "kind": "text", "options": ["ACTIVE", "SUSPENDED"], "from": "Okta users", "column": "UserStatus"},
               {"id": "mfa", "label": "Enrolled in MFA", "kind": "flag"}, {"id": "created", "label": "Account created", "kind": "time"}],
    "settings": [{"id": "grace", "label": "Days a new user has to enrol", "kind": "number", "default": 7, "unit": "day"}],
    "applies_to": {"field": "status", "is": "present"},
    "cases": [{"when": {"field": "status", "is": "not_equals", "value": "ACTIVE"}, "verdict": "NOT_APPLICABLE", "reason": "Only active users need MFA"},
              {"when": {"field": "mfa", "is": "is_true"}, "verdict": "COMPLIANT", "code": "MFA_ENROLLED", "reason": "The user has enrolled"},
              {"when": {"field": "created", "is": "greater_than", "than": {"now": True, "minus": {"amount": {"setting": "grace"}, "unit": "day"}}}, "verdict": "COMPLIANT", "reason": "New user"},
              {"verdict": "NON_COMPLIANT", "reason": "An active user past the enrolment period has not enrolled"}],
    "samples": [{"label": "Active, no MFA, old account", "values": {"status": "ACTIVE", "mfa": False, "created": "2025-01-01T00:00:00Z"}}],
}


def with_(**changes):
    d = copy.deepcopy(MFA)
    d.update(changes)
    return d


def messages(check):
    return [i["message"] for i in c.validate_checks([check])]


class Valid(unittest.TestCase):
    def test_the_documented_example_and_a_full_check_are_valid(self):
        self.assertEqual(c.validate_checks([MFA]), [])

    def test_a_group_of_conditions_and_a_list_of_values_are_valid(self):
        check = with_(cases=[{"when": {"all": [{"field": "status", "is": "in", "values": ["ACTIVE", "SUSPENDED"]}, {"not": {"field": "mfa", "is": "is_true"}}]}, "verdict": "NON_COMPLIANT"}, {"verdict": "COMPLIANT"}])
        self.assertEqual(c.validate_checks([check]), [])

    def test_two_times_compared_with_a_duration_from_a_setting(self):
        check = with_(fields=[{"id": "changed", "label": "Changed", "kind": "time"}, {"id": "term", "label": "Terminated", "kind": "time"}],
                      cases=[{"when": {"field": "changed", "is": "at_most", "than": {"field": "term", "plus": {"amount": {"setting": "grace"}, "unit": "hour"}}}, "verdict": "COMPLIANT"}, {"verdict": "NON_COMPLIANT"}], samples=[], applies_to=None)
        check.pop("applies_to")
        self.assertEqual(c.validate_checks([check]), [])


class Refused(unittest.TestCase):
    def test_a_condition_on_a_field_the_check_did_not_declare(self):
        bad = with_(cases=[{"when": {"field": "nope", "is": "present"}, "verdict": "COMPLIANT"}, {"verdict": "NON_COMPLIANT"}])
        self.assertTrue(any("not a field of this check" in m for m in messages(bad)))

    def test_only_the_last_case_may_be_the_otherwise_case(self):
        bad = with_(cases=[{"verdict": "COMPLIANT"}, {"when": {"field": "mfa", "is": "is_true"}, "verdict": "NON_COMPLIANT"}])
        self.assertTrue(any("only the last case" in m for m in messages(bad)))

    def test_a_verdict_must_be_one_of_the_three(self):
        bad = with_(cases=[{"verdict": "FAILED"}])
        self.assertTrue(any("verdict is one of" in m for m in messages(bad)))

    def test_an_operator_must_suit_the_kind_of_field(self):
        self.assertTrue(any("flag" in m for m in messages(with_(cases=[{"when": {"field": "mfa", "is": "greater_than", "value": 1}, "verdict": "COMPLIANT"}]))))
        self.assertTrue(any("text field" in m for m in messages(with_(cases=[{"when": {"field": "status", "is": "at_most", "value": "A"}, "verdict": "COMPLIANT"}]))))
        self.assertTrue(any("is_true" in m for m in messages(with_(cases=[{"when": {"field": "status", "is": "is_true"}, "verdict": "COMPLIANT"}]))))

    def test_a_value_must_fit_its_field(self):
        self.assertTrue(any("number field" in m for m in messages(with_(fields=[{"id": "n", "label": "N", "kind": "number"}], cases=[{"when": {"field": "n", "is": "equals", "value": "x"}, "verdict": "COMPLIANT"}], samples=[], applies_to=None))))

    def test_a_time_must_be_written_as_a_time_and_a_flag_compared_with_a_boolean(self):
        for when in ({"field": "created", "is": "greater_than", "value": "last week"},
                     {"field": "created", "is": "in", "values": ["2026-01-31", "soon"]},
                     {"field": "created", "is": "less_than", "than": {"value": "yesterday"}},
                     {"field": "mfa", "is": "equals", "value": "yes"}):
            self.assertTrue(messages(with_(cases=[{"when": when, "verdict": "COMPLIANT"}, {"verdict": "NON_COMPLIANT"}])), when)
        self.assertEqual(messages(with_(samples=[{"label": "s", "values": {"created": "2026-01-31"}}])), [])
        self.assertTrue(messages(with_(samples=[{"label": "s", "values": {"created": "a while ago"}}])))
        self.assertEqual(messages(with_(cases=[{"when": {"field": "created", "is": "greater_than", "value": "2026-01-31"}, "verdict": "COMPLIANT"}, {"verdict": "NON_COMPLIANT"}])), [])

    def test_columns_are_a_list_of_named_typed_columns_without_repeats(self):
        good = with_(columns=[{"name": "UserEmail", "kind": "text", "from": "Okta users", "about": "The user's email"}, {"name": "LastLogin", "kind": "time"}])
        self.assertEqual(messages(good), [])
        for bad in ([{"name": "A"}], [{"name": "A", "kind": "date"}], [{"name": "A", "kind": "text"}, {"name": "A", "kind": "text"}], [{"name": "", "kind": "text"}],
                    [{"name": "A", "kind": "text", "x": 1}], "UserEmail", [{"name": f"c{i}", "kind": "text"} for i in range(41)]):
            self.assertTrue(messages(with_(columns=bad)), bad)

    def test_a_setting_that_does_not_exist_or_is_not_a_number_cannot_be_used_as_an_amount(self):
        gone = with_(cases=[{"when": {"field": "created", "is": "less_than", "than": {"now": True, "minus": {"amount": {"setting": "missing"}, "unit": "day"}}}, "verdict": "COMPLIANT"}, {"verdict": "NON_COMPLIANT"}])
        self.assertTrue(any("number setting" in m for m in messages(gone)))

    def test_now_is_only_for_time_fields(self):
        bad = with_(cases=[{"when": {"field": "mfa", "is": "equals", "than": {"now": True}}, "verdict": "COMPLIANT"}, {"verdict": "NON_COMPLIANT"}])
        self.assertTrue(messages(bad))

    def test_a_duration_needs_a_known_unit_and_an_amount(self):
        bad = with_(cases=[{"when": {"field": "created", "is": "less_than", "than": {"now": True, "minus": {"amount": 3, "unit": "fortnight"}}}, "verdict": "COMPLIANT"}, {"verdict": "NON_COMPLIANT"}])
        self.assertTrue(any("unit is one of" in m for m in messages(bad)))

    def test_ids_are_unique_and_well_formed(self):
        self.assertTrue(any("used twice" in i["message"] for i in c.validate_checks([MFA, MFA])))
        self.assertTrue(any("lower case" in m for m in messages(with_(id="Bad Id"))))
        dup = with_(fields=[{"id": "a", "label": "A", "kind": "flag"}, {"id": "a", "label": "B", "kind": "flag"}], cases=[{"verdict": "COMPLIANT"}], samples=[], applies_to=None)
        self.assertTrue(any("used twice" in m for m in messages(dup)))

    def test_a_sample_must_use_declared_fields_and_fitting_values(self):
        self.assertTrue(any("not a field" in m for m in messages(with_(samples=[{"label": "x", "values": {"ghost": 1}}]))))
        self.assertTrue(any("does not fit" in m for m in messages(with_(samples=[{"label": "x", "values": {"mfa": "yes"}}]))))

    def test_a_check_must_say_what_it_establishes_and_have_a_case(self):
        self.assertTrue(any("about" in m for m in messages(with_(about=""))))
        self.assertTrue(any("cases" in m for m in messages(with_(cases=[]))))

    def test_a_condition_with_unknown_keys_or_a_mixed_group_is_refused(self):
        self.assertTrue(messages(with_(cases=[{"when": {"all": [{"field": "mfa", "is": "is_true"}], "any": []}, "verdict": "COMPLIANT"}])))
        self.assertTrue(messages(with_(cases=[{"when": {"field": "mfa", "is": "is_true", "colour": "red"}, "verdict": "COMPLIANT"}])))

    def test_too_many_checks_or_too_deep_a_condition(self):
        self.assertTrue(c.validate_checks([MFA] * 13))
        deep = {"field": "mfa", "is": "is_true"}
        for _ in range(8):
            deep = {"not": deep}
        self.assertTrue(any("deep" in m for m in messages(with_(cases=[{"when": deep, "verdict": "COMPLIANT"}, {"verdict": "NON_COMPLIANT"}]))))

    def test_nothing_that_is_not_a_list_of_checks(self):
        for bad in (None, {}, [], "x", [1]):
            self.assertTrue(c.validate_checks(bad), bad)


class Tool(unittest.IsolatedAsyncioTestCase):
    async def test_it_says_success_for_a_drawable_structure_and_names_the_issues_otherwise(self):
        ok = await c.compliance_logic.fn([MFA]) if hasattr(c.compliance_logic, "fn") else await c.compliance_logic([MFA])
        self.assertEqual(ok, {"success": True, "checks": 1})
        bad = await c.compliance_logic.fn([with_(cases=[])]) if hasattr(c.compliance_logic, "fn") else await c.compliance_logic([with_(cases=[])])
        self.assertFalse(bad["success"])
        self.assertTrue(bad["issues"])


if __name__ == "__main__":
    unittest.main()
