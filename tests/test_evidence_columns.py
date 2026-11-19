import asyncio
import unittest

from tools.playbook import evidence_columns as e

SUMMARY = {
    "assessmentName": "Okta Identity Inventory", "controlId": "c12", "controlName": "Okta User Inactivity Compliance",
    "lineage": [{"originType": "link", "recursionLevel": 1, "linkedFrom": [
        {"controlId": "c31", "controlName": "Okta User Inventory", "evidences": [
            {"id": "ev1", "name": "OktaUsers", "columnsInfo": [
                {"name": "UserEmail", "type": "STRING"}, {"name": "LoginCount", "type": "INTEGER"},
                {"name": "UserLastLogin", "type": "TIMESTAMP"}, {"name": "MFAEnabled", "type": "BOOLEAN"}, {"name": "", "type": "STRING"}]},
            {"id": "ev2", "name": "LogFile", "columnsInfo": [{"name": "Error", "type": "STRING"}]},
            {"id": "ev3", "name": "Empty", "columnsInfo": []}],
         "lineage": [{"linkedFrom": [{"controlId": "c11", "controlName": "Okta Apps", "evidences": [
             {"id": "ev4", "name": "OktaApps", "columnsInfo": [{"name": "AppName", "fieldDataType": "string"}]},
             {"id": "ev1", "name": "OktaUsers", "columnsInfo": [{"name": "UserEmail", "type": "STRING"}]}]}]}]}]}],
}


class Kinds(unittest.TestCase):
    def test_the_platforms_type_names_become_one_of_four_kinds(self):
        for types, kind in ((("STRING",), "text"), (("INTEGER",), "number"), (("FLOAT64",), "number"), (("BOOLEAN",), "flag"), (("TIMESTAMP",), "time"),
                            (("DATE",), "time"), (("DATETIME",), "time"), (("",), "text"), ((None, "number"), "number"), (("JSON",), "text")):
            self.assertEqual(e.kind_of(*types), kind, types)


class Reading(unittest.TestCase):
    def test_the_evidence_of_every_linked_control_is_listed_with_its_columns(self):
        ev = e.evidences_of(SUMMARY)
        self.assertEqual([x["name"] for x in ev], ["OktaUsers", "OktaApps"])
        self.assertEqual(ev[0]["control"], "Okta User Inventory")
        self.assertEqual(ev[0]["columns"], [{"name": "UserEmail", "kind": "text", "type": "STRING"}, {"name": "LoginCount", "kind": "number", "type": "INTEGER"},
                                            {"name": "UserLastLogin", "kind": "time", "type": "TIMESTAMP"}, {"name": "MFAEnabled", "kind": "flag", "type": "BOOLEAN"}])
        self.assertEqual(ev[1]["columns"], [{"name": "AppName", "kind": "text", "type": "string"}])

    def test_log_and_empty_evidence_and_a_repeat_are_left_out(self):
        names = [x["name"] for x in e.evidences_of(SUMMARY)]
        self.assertNotIn("LogFile", names)
        self.assertNotIn("Empty", names)
        self.assertEqual(names.count("OktaUsers"), 1)

    def test_nothing_linked_gives_nothing(self):
        self.assertEqual(e.evidences_of({}), [])
        self.assertEqual(e.evidences_of({"lineage": [{"linkedFrom": None}]}), [])

    def test_the_lists_are_capped(self):
        many = {"lineage": [{"linkedFrom": [{"controlId": f"c{i}", "controlName": f"C{i}", "evidences": [{"name": f"E{i}", "columnsInfo": [{"name": f"col{j}", "type": "STRING"} for j in range(200)]}]} for i in range(30)]}]}
        ev = e.evidences_of(many)
        self.assertEqual(len(ev), e.MAX_EVIDENCES)
        self.assertEqual(len(ev[0]["columns"]), e.MAX_COLUMNS)


class Tool(unittest.IsolatedAsyncioTestCase):
    async def test_a_summary_becomes_the_answer(self):
        async def fetch(control_id, ctx):
            return {"success": True, "data": SUMMARY}
        r = await e.read("c12", None, fetch)
        self.assertTrue(r["success"])
        self.assertEqual((r["control"], r["assessment"], r["control_id"]), ("Okta User Inactivity Compliance", "Okta Identity Inventory", "c12"))
        self.assertEqual(len(r["evidences"]), 2)
        self.assertNotIn("note", r)

    async def test_a_control_with_no_known_schema_says_so(self):
        async def fetch(control_id, ctx):
            return {"success": True, "data": {"controlName": "X", "lineage": []}}
        r = await e.read("c1", None, fetch)
        self.assertEqual(r["evidences"], [])
        self.assertIn("no evidence with a known schema", r["note"])

    async def test_an_evidence_that_a_run_produced_is_read_by_its_id_and_comes_first(self):
        async def fetch(control_id, ctx):
            return {"success": True, "data": SUMMARY}
        async def schema(evidence_id, ctx):
            return [{"name": "Dept", "kind": "text", "type": "STRING"}]
        r = await e.read("c12", None, fetch, evidence_id=" evX ", evidence_name="OktaUserDetails", fetch_schema=schema)
        self.assertEqual([x["name"] for x in r["evidences"]], ["OktaUserDetails", "OktaUsers", "OktaApps"])
        self.assertEqual((r["evidences"][0]["id"], r["evidences"][0]["control"]), ("evX", "Okta User Inactivity Compliance"))

    async def test_an_evidence_already_listed_is_not_listed_twice(self):
        async def fetch(control_id, ctx):
            return {"success": True, "data": SUMMARY}
        async def schema(evidence_id, ctx):
            return [{"name": "Dept", "kind": "text", "type": "STRING"}]
        r = await e.read("c12", None, fetch, evidence_id="ev1", fetch_schema=schema)
        self.assertEqual([x["name"] for x in r["evidences"]], ["OktaUsers", "OktaApps"])

    async def test_an_evidence_that_cannot_be_read_is_a_failure_that_says_why(self):
        async def fetch(control_id, ctx):
            return {"success": True, "data": SUMMARY}
        async def schema(evidence_id, ctx):
            return None
        r = await e.read("c12", None, fetch, evidence_id="evX", fetch_schema=schema)
        self.assertFalse(r["success"])
        self.assertIn("no run has produced it", r["error"])

    def test_a_platform_schema_becomes_columns_and_skips_entries_without_a_name_or_type(self):
        self.assertEqual(e.columns_of_schema([{"name": "A", "type": "TIMESTAMP"}, {"name": "B"}, {"type": "STRING"}, "x", {"name": "C", "type": "BOOLEAN"}]),
                         [{"name": "A", "kind": "time", "type": "TIMESTAMP"}, {"name": "C", "kind": "flag", "type": "BOOLEAN"}])

    async def test_a_failed_read_is_a_failure_with_the_reason(self):
        async def fetch(control_id, ctx):
            return {"success": False, "error": "controlId is mandatory"}
        r = await e.read("", None, fetch)
        self.assertEqual(r, {"success": False, "error": "controlId is mandatory", "control_id": ""})

    async def test_no_control_id_is_refused_without_asking_the_platform(self):
        self.assertEqual(await e._summary("  ", None), {"success": False, "error": "control_id is mandatory"})

    async def test_a_model_object_is_read_like_a_dict(self):
        class Answer:
            def model_dump(self):
                return {"success": True, "data": SUMMARY}
        async def fetch(control_id, ctx):
            return Answer()
        self.assertEqual(len((await e.read("c12", None, fetch))["evidences"]), 2)


if __name__ == "__main__":
    unittest.main()
