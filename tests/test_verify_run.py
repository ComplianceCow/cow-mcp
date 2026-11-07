import asyncio
import unittest

from tools.playbook import verify_run as v


def ev(name, status="Completed", rows=3):
    return {"name": name, "status": status, "rows": rows}


def dep(source, cross=False, name="In"):
    return {"input": name, "source": source, "crossAssessment": cross}


class ClassifyLogError(unittest.TestCase):
    def test_the_messages_seen_on_uat(self):
        self.assertEqual(v.classify_log_error("InputFile is missing in user inputs.")[0], "RULE_INPUT_MISSING")
        self.assertEqual(v.classify_log_error("Invalid URL")[0], "CONNECTION")

    def test_credentials_and_sql_errors(self):
        self.assertEqual(v.classify_log_error("HTTP 401 Unauthorized")[0], "CREDENTIALS")
        self.assertEqual(v.classify_log_error("no such column: UserStatus")[0], "SQL_ERROR")

    def test_anything_else_is_a_rule_error_with_the_message_kept_by_the_caller(self):
        self.assertEqual(v.classify_log_error("something odd")[0], "RULE_ERROR")


class ClassifyControl(unittest.TestCase):
    def test_a_control_with_rows_is_ok(self):
        self.assertEqual(v.classify_control("3.1", [ev("OktaUsers")], None, [], {})["verdict"], "OK")

    def test_a_completed_control_with_no_rows_is_empty(self):
        self.assertEqual(v.classify_control("3.1", [ev("OktaUsers", rows=0)], None, [], {})["verdict"], "EMPTY")

    def test_a_logged_error_gives_the_classified_verdict_and_keeps_the_message(self):
        got = v.classify_control("3.3", [ev("OktaSuspendedUsers", "Yet to start", None)], "InputFile is missing in user inputs.", [], {})
        self.assertEqual(got["verdict"], "RULE_INPUT_MISSING")
        self.assertIn("InputFile is missing", got["cause"])

    def test_an_error_while_an_upstream_control_failed_is_blamed_on_the_upstream(self):
        got = v.classify_control("2.1", [ev("Report", "Yet to start", None)], "Invalid URL", [dep("3.3")], {"3.3": "RULE_INPUT_MISSING"})
        self.assertEqual(got["verdict"], "UPSTREAM_FAILED")
        self.assertIn("3.3", got["cause"])

    def test_a_control_that_never_started_because_its_input_comes_from_another_assessment(self):
        got = v.classify_control("1.1", [ev("Report", "Yet to start", None)], None, [dep("3.1", cross=True, name="WorkdayWorkers")], {})
        self.assertEqual(got["verdict"], "CROSS_ASSESSMENT_DEPENDENCY")
        self.assertIn("WorkdayWorkers", got["cause"])
        self.assertIn("link_control", got["fix"])

    def test_a_control_that_never_started_with_nothing_failed_upstream(self):
        self.assertEqual(v.classify_control("1.1", [ev("R", "Yet to start", None)], None, [dep("3.1")], {"3.1": "OK"})["verdict"], "NOT_STARTED")

    def test_unreadable_evidence_is_not_a_failure(self):
        self.assertEqual(v.classify_control("3.1", [ev("R", "Completed", None)], None, [], {})["verdict"], "UNREADABLE")

    def test_a_failed_evidence_without_a_message(self):
        self.assertEqual(v.classify_control("3.1", [ev("R", "Failed", None)], None, [], {})["verdict"], "RULE_ERROR")


class Ordering(unittest.TestCase):
    def test_a_control_comes_after_the_controls_it_depends_on(self):
        order = v.order_by_dependency({"2.1": [dep("3.3"), dep("3.1")], "3.1": [], "3.3": []})
        self.assertLess(order.index("3.3"), order.index("2.1"))
        self.assertLess(order.index("3.1"), order.index("2.1"))

    def test_a_cycle_does_not_hang(self):
        self.assertEqual(sorted(v.order_by_dependency({"a": [dep("b")], "b": [dep("a")]})), ["a", "b"])


def adapters(controls, evidence_data, evidence_status, deps, status="Completed"):
    async def runs():
        return {"success": True, "data": [{"assessmentRunId": "run1", "status": status}]}

    async def details(rid):
        return {"success": True, "data": {"controls": controls}}

    async def evidence_rows(control_run_id):
        return {"items": [{"name": n, "status": s} for n, s in evidence_status.get(control_run_id, {}).items()]}

    async def data(evidence_id):
        return evidence_data.get(evidence_id, {"success": False, "error": "Facing internal error"})

    async def dependencies():
        return deps

    return {"runs": runs, "details": details, "evidence_rows": evidence_rows, "evidence_data": data, "dependencies": dependencies}


def rows(*items):
    return {"success": True, "data": {"items": list(items)}}


class VerifyEndToEnd(unittest.TestCase):
    """The shape of the uat run: two healthy controls, a new rule with broken wiring, the control starved by it, and one that depends on another assessment."""

    def run_verify(self, wait=60, **kw):
        controls = [
            {"id": "r31", "controlNo": "3.1", "name": "Okta Users Inventory", "evidence": [{"id": "e31", "name": "OktaUsers"}, {"id": "l31", "name": "LogFile"}]},
            {"id": "r33", "controlNo": "3.3", "name": "Suspended", "evidence": [{"id": "e33", "name": "OktaSuspendedUsers"}, {"id": "l33", "name": "LogFile"}]},
            {"id": "r21", "controlNo": "2.1", "name": "Residual groups", "evidence": [{"id": "e21", "name": "Report"}, {"id": "l21", "name": "LogFile"}]},
            {"id": "r11", "controlNo": "1.1", "name": "Reconciliation", "evidence": [{"id": "e11", "name": "Termination"}, {"id": "l11", "name": "LogFile"}]},
        ]
        data = {"e31": rows({"UserStatus": "ACTIVE"}), "l33": rows({"Error": "InputFile is missing in user inputs."}), "l21": rows({"Error": "Invalid URL"})}
        status = {"r33": {"OktaSuspendedUsers": "Yet to start"}, "r21": {"Report": "Yet to start"}, "r11": {"Termination": "Yet to start"}}
        deps = {"3.1": [], "3.3": [], "2.1": [dep("3.3"), dep("3.1")], "1.1": [dep("3.1"), dep("WorkdayWorkers-source", cross=True, name="WorkdayWorkers")]}
        return asyncio.run(v.verify("plan1", "run1", "x", wait, None, adapters(controls, data, status, deps, **kw)))

    def test_every_control_gets_the_right_verdict(self):
        got = self.run_verify()
        verdicts = {c["controlNo"]: c["verdict"] for c in got["controls"]}
        self.assertEqual(verdicts, {"1.1": "CROSS_ASSESSMENT_DEPENDENCY", "2.1": "UPSTREAM_FAILED", "3.1": "OK", "3.3": "RULE_INPUT_MISSING"})
        self.assertFalse(got["ok"])
        self.assertEqual(got["counts"]["OK"], 1)

    def test_controls_are_listed_in_number_order(self):
        self.assertEqual([c["controlNo"] for c in self.run_verify()["controls"]], ["1.1", "2.1", "3.1", "3.3"])

    def test_a_run_that_has_not_finished_says_so_instead_of_judging(self):
        got = self.run_verify(wait=0, status="Started")
        self.assertFalse(got["finished"])
        self.assertNotIn("controls", got)

    def test_an_all_healthy_run_is_ok(self):
        controls = [{"id": "r1", "controlNo": "1", "name": "n", "evidence": [{"id": "e1", "name": "R"}]}]
        got = asyncio.run(v.verify("p", "run1", "x", 60, None, adapters(controls, {"e1": rows({"a": 1})}, {}, {"1": []})))
        self.assertTrue(got["ok"])


if __name__ == "__main__":
    unittest.main()
