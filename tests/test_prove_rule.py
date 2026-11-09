import asyncio
import json
import unittest

from tools.playbook import prove_rule as p


def structure(tags=("oktaconnector",), inputs=1):
    tasks = [{"name": f"t{i}", "appTags": {"appType": [t]}} for i, t in enumerate(tags)]
    meta = [{"name": f"In{i}", "dataType": "FILE", "defaultValue": "<<MINIO_FILE_PATH>>"} for i in range(inputs)]
    return {"meta": {"name": "R"}, "spec": {"tasks": tasks, "inputsMeta__": meta}}


OKTA = {"id": "a1", "credentialName": "Okta app", "appType": "OktaConnector::", "isValidated": True}
UNVALIDATED = {"id": "a2", "credentialName": "Other", "appType": "OktaConnector::", "isValidated": False}


def log(*errors):
    return {"display_content": json.dumps([{"Error": e} for e in errors])}


def rows(n):
    return {"file_format": "json", "display_content": json.dumps([{"UserStatus": "ACTIVE"}] * n)}


def line(name, status="COMPLETED", **outputs):
    return {"task_name": name, "status": status, "outputs": outputs}


def run(progress_lines, files, apps=(OKTA,), struct=None, status="COMPLETED", wait=5):
    async def apps_():
        return list(apps)

    async def structure_():
        return struct if struct is not None else structure()

    async def execute(payload):
        run.payload = payload
        return {"id": "exec1"}

    async def progress(_):
        return {"continue_polling": False, "status": status, "display_lines": progress_lines}

    async def file(url):
        return files.get(url, {"display_content": "[]"})

    return asyncio.run(p.prove("R", None, wait, None, {"structure": structure_, "apps": apps_, "execute": execute, "progress": progress, "file": file}))


class Helpers(unittest.TestCase):
    def test_a_no_credential_task_needs_no_application(self):
        self.assertEqual(list(p.application_needs(structure(("nocredapp", "oktaconnector", "oktaconnector")))), ["oktaconnector"])

    def test_inputs_carry_every_field_and_the_default_as_value(self):
        got = p.input_payload(structure(inputs=1))[0]
        self.assertEqual((got["value"], got["defaultValue"], got["dataType"]), ("<<MINIO_FILE_PATH>>", "<<MINIO_FILE_PATH>>", "FILE"))

    def test_only_a_validated_application_of_the_right_type_is_picked(self):
        picked, missing, ambiguous = p.pick_applications({"oktaconnector": {"appType": ["oktaconnector"]}}, [UNVALIDATED, OKTA])
        self.assertEqual((picked[0]["applicationId"], missing, ambiguous), ("a1", [], {}))
        _, missing, _ = p.pick_applications({"oktaconnector": {}}, [UNVALIDATED])
        self.assertEqual(missing, ["oktaconnector"])

    def test_several_validated_applications_of_a_type_are_never_guessed_between(self):
        second = {**OKTA, "id": "a3", "credentialName": "Second Okta"}
        picked, missing, ambiguous = p.pick_applications({"oktaconnector": {}}, [OKTA, second])
        self.assertEqual((picked, ambiguous), ([], {"oktaconnector": ["Okta app", "Second Okta"]}))

    def test_naming_the_application_by_name_or_id_settles_it_whatever_the_key(self):
        second = {**OKTA, "id": "a3", "credentialName": "Second Okta"}
        for chosen in (["Second Okta"], ["a3"], {"any key": "a3"}, {"httprequest": "Second Okta"}):
            picked, _, ambiguous = p.pick_applications({"oktaconnector": {}}, [OKTA, second], chosen)
            self.assertEqual((picked[0]["applicationId"], ambiguous), ("a3", {}), chosen)

    def test_naming_an_application_of_another_type_does_not_settle_it(self):
        other = {"id": "w1", "credentialName": "Workday", "appType": "HttpRequest::", "isValidated": True}
        second = {**OKTA, "id": "a3"}
        _, _, ambiguous = p.pick_applications({"oktaconnector": {}}, [OKTA, second, other], ["Workday"])
        self.assertIn("oktaconnector", ambiguous)

    def test_log_records_come_from_the_text_of_the_file(self):
        self.assertEqual(p.log_records('[{"Error": "x"}]'), [{"Error": "x"}])
        self.assertEqual(p.log_records("not json"), [])


class Prove(unittest.TestCase):
    def test_a_rule_whose_tasks_log_no_error_passes_with_its_output_rows(self):
        got = run([line("t1-GetOktaUsers", LogFile="log", OktaUsers="out")], {"log": {"display_content": "[]"}, "out": rows(3)})
        self.assertEqual(got["verdict"], "PASS")
        self.assertEqual(got["tasks"][0]["outputs"], [{"name": "OktaUsers", "format": "json", "sizeKb": None, "rows": 3, "sample": [{"UserStatus": "ACTIVE"}] * 3, "emptyShare": 0.0}])
        self.assertEqual(run.payload["applications"][0]["applicationId"], "a1")

    def test_the_first_error_is_the_cause_and_the_later_ones_are_consequences(self):
        lines = [line("fetch_suspended", LogFile="l1"), line("fetch_groups", LogFile="l2"), line("join", LogFile="l3"), line("transform", LogFile="l4")]
        files = {"l1": log("Forbidden - You do not have the necessary permissions to access this resource."), "l2": log("Forbidden - You do not have the necessary permissions to access this resource."),
                 "l3": log("Mandatory input files are missing or invalid. InputFile1 is/are empty."), "l4": log("InputFile is missing in user inputs.")}
        got = run(lines, files)
        self.assertEqual(got["verdict"], "FAIL")
        self.assertEqual(got["status"], "COMPLETED")
        self.assertEqual((got["firstError"]["task"], got["firstError"]["kind"]), ("fetch_suspended", "CREDENTIALS"))
        self.assertEqual([c["task"] for c in got["consequences"]], ["fetch_groups", "join", "transform"])

    def test_a_task_marked_error_without_a_log_message_still_fails(self):
        got = run([{**line("t1"), "status": "ERROR", "error": "boom"}], {})
        self.assertEqual((got["verdict"], got["firstError"]["task"], got["firstError"]["message"]), ("FAIL", "t1", "boom"))

    def test_a_pass_with_an_empty_output_carries_a_warning(self):
        got = run([line("t1", LogFile="log", Report="out")], {"log": {"display_content": "[]"}, "out": rows(0)})
        self.assertEqual(got["verdict"], "PASS")
        self.assertIn("Report", got["warning"])

    def test_a_parquet_output_has_an_unknown_row_count_and_no_empty_warning(self):
        parquet = {"file_format": "parquet", "file_size_kb": 13.9, "display_content": "Error processing Parquet: no engine"}
        got = run([line("t1", LogFile="log", Users="out")], {"log": {"file_format": "json", "display_content": "[]"}, "out": parquet})
        self.assertEqual(got["verdict"], "PASS")
        self.assertNotIn("warning", got)
        self.assertEqual((got["tasks"][0]["outputs"][0]["rows"], got["tasks"][0]["outputs"][0]["sizeKb"]), (None, 13.9))

    def test_an_output_file_of_size_zero_is_an_empty_output(self):
        got = run([line("t1", LogFile="log", Users="out")], {"log": {"file_format": "json", "display_content": "[]"}, "out": {"file_format": "parquet", "file_size_kb": 0, "display_content": ""}})
        self.assertIn("Users", got["warning"])

    def test_a_pass_whose_rows_are_mostly_empty_carries_a_warning(self):
        placeholder = {"file_format": "json", "display_content": json.dumps([{"RuleName": "", "RuleStatus": "", "RuleConditions": None, "System": "okta"}])}
        got = run([line("t1", LogFile="log", Report="out")], {"log": {"file_format": "json", "display_content": "[]"}, "out": placeholder})
        self.assertEqual(got["verdict"], "PASS")
        self.assertIn("placeholder", got["warning"])

    def test_no_validated_application_means_the_rule_is_not_run(self):
        got = run([], {}, apps=(UNVALIDATED,))
        self.assertEqual(got["verdict"], "NEEDS_APPLICATION")
        self.assertEqual(got["missingApplicationTypes"], ["oktaconnector"])

    def test_two_validated_applications_of_the_type_ask_for_a_choice_and_run_nothing(self):
        got = run([], {}, apps=(OKTA, {**OKTA, "id": "a3", "credentialName": "Second Okta"}))
        self.assertEqual(got["verdict"], "NEEDS_CHOICE")
        self.assertEqual(got["candidates"], {"oktaconnector": ["Okta app", "Second Okta"]})

    def test_a_rule_that_cannot_be_read_is_not_found(self):
        async def none():
            return None
        got = asyncio.run(p.prove("R", None, 5, None, {"structure": none}))
        self.assertEqual(got["verdict"], "NOT_FOUND")

    def test_an_execution_that_never_finishes_times_out(self):
        async def structure_():
            return structure()

        async def apps_():
            return [OKTA]

        async def execute(_):
            return {"id": "e"}

        async def progress(_):
            return {"continue_polling": True, "status": "INPROGRESS"}

        got = asyncio.run(p.prove("R", None, 0, None, {"structure": structure_, "apps": apps_, "execute": execute, "progress": progress, "file": None}))
        self.assertEqual(got["verdict"], "TIMEOUT")

    def test_an_execution_that_does_not_start_is_a_failure(self):
        async def structure_():
            return structure()

        async def apps_():
            return [OKTA]

        async def execute(_):
            return {"error": "bad"}

        got = asyncio.run(p.prove("R", None, 5, None, {"structure": structure_, "apps": apps_, "execute": execute}))
        self.assertEqual(got["verdict"], "FAIL")


if __name__ == "__main__":
    unittest.main()
