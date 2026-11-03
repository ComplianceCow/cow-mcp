import asyncio
import base64
import json
import os
import unittest
from unittest import mock

import httpx

from constants import constants
from tools.playbook import usecase_push as u
from tools.playbook import usecase_tools as tools

VALID = """\
apiVersion: playbook.compliancecow.io/v1
kind: UseCase
metadata:
  id: uc-servicenow-eol
  version: 1.0.0
spec:
  name: Software end of life
  lifecycle: draft
  domainArea: Vulnerability management
  steps:
    - {id: a, type: create_application}
    - {id: b, type: create_application_scope}
    - {id: c, type: create_control}
    - {id: d, type: create_control}
"""

PUSHED = {"status": "success", "action": "pushed", "key": "uc-servicenow-eol@1.0.0", "content_hash": "abc", "stats": {"steps": 4}}
VALID_ANSWER = {"status": "success", "valid": True, "id": "uc-servicenow-eol", "version": "1.0.0", "message": "Playbook specification is valid."}
INVALID_ANSWER = {"status": "error", "valid": False, "error_count": 2, "errors": ["step 'c' has an unknown type", "steps[2].refs.assessment is required"]}


def run(coro):
    return asyncio.run(coro)


class Recorder:
    """A backend that remembers what it was sent and answers as told."""

    def __init__(self, status=200, body=None, problem=None):
        self.sent, self.status, self.body, self.problem = [], status, body, problem

    async def __call__(self, payload):
        self.sent.append(payload)
        return self.status, self.body, self.problem


class Prepare(unittest.TestCase):
    def test_reads_a_use_case_and_names_the_file_after_it(self):
        p = u.prepare(VALID)
        self.assertEqual((p.source_name, p.replace), ("uc-servicenow-eol.yaml", False))
        self.assertEqual(p.data, VALID.encode())

    def test_keeps_the_file_name_it_is_given(self):
        self.assertEqual(u.prepare(VALID, "servicenow.yaml").source_name, "servicenow.yaml")
        self.assertEqual(u.prepare(VALID, "servicenow.yml").source_name, "servicenow.yml")

    def test_refuses_what_is_not_a_plain_yaml_file_name(self):
        for bad in ("../x.yaml", "a/b.yaml", "x.json", "x", ".yaml", "x y.yaml", "x.yaml\n", "a" * 101 + ".yaml", 5):
            with self.assertRaises(ValueError, msg=repr(bad)):
                u.prepare(VALID, bad)

    def test_refuses_what_is_not_a_use_case(self):
        cases = {
            "nothing": "", "spaces": "   \n", "not text": 5, "unreadable": "a: [1, 2", "a list": "- a\n- b\n", "a value": "just text",
            "two documents": VALID + "---\n" + VALID,
            "wrong kind": VALID.replace("kind: UseCase", "kind: Rule"),
            "no kind": VALID.replace("kind: UseCase\n", ""),
            "wrong apiVersion": VALID.replace("playbook.compliancecow.io/v1", "other.io/v1"),
            "no apiVersion": VALID.replace("apiVersion: playbook.compliancecow.io/v1\n", ""),
            "no id": VALID.replace("  id: uc-servicenow-eol\n", ""),
            "blank id": VALID.replace("id: uc-servicenow-eol", "id: '  '"),
            "no version": VALID.replace("  version: 1.0.0\n", ""),
            "no spec": "apiVersion: playbook.compliancecow.io/v1\nkind: UseCase\nmetadata: {id: x, version: 1}\n",
            "no steps": VALID.split("  steps:")[0],
            "empty steps": VALID.split("  steps:")[0] + "  steps: []\n",
            "steps not a list": VALID.split("  steps:")[0] + "  steps: a\n",
        }
        for label, text in cases.items():
            with self.assertRaises(ValueError, msg=label):
                u.prepare(text)

    def test_a_number_for_a_version_is_accepted_and_left_to_the_backend(self):
        self.assertEqual(u.prepare(VALID.replace("version: 1.0.0", "version: 2")).doc["metadata"]["version"], 2)

    def test_refuses_a_document_too_large_to_push(self):
        with self.assertRaises(ValueError) as caught:
            u.prepare(VALID + "# " + "x" * u.MAX_BYTES)
        self.assertIn("bytes", str(caught.exception))

    def test_replace_has_to_be_a_real_boolean(self):
        for bad in ("true", 1, None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                u.prepare(VALID, None, bad)

    def test_does_not_judge_what_the_backend_judges(self):
        odd = VALID.replace("type: create_application}", "type: nothing_known}")
        self.assertEqual(u.prepare(odd).doc["spec"]["steps"][0]["type"], "nothing_known")


class Summary(unittest.TestCase):
    def test_says_what_would_be_pushed(self):
        out = u.summary(u.prepare(VALID, "servicenow.yaml"))
        self.assertEqual((out["id"], out["version"], out["name"], out["lifecycle"], out["steps"]), ("uc-servicenow-eol", "1.0.0", "Software end of life", "draft", 4))
        self.assertEqual(out["step_types"], {"create_application": 1, "create_application_scope": 1, "create_control": 2})
        self.assertEqual((out["source_name"], out["replace"], out["bytes"]), ("servicenow.yaml", False, len(VALID.encode())))

    def test_a_step_that_is_not_a_mapping_is_counted_not_crashed_on(self):
        out = u.summary(u.prepare(VALID.replace("    - {id: d, type: create_control}\n", "    - just text\n")))
        self.assertEqual(out["steps"], 4)
        self.assertEqual(out["step_types"]["None"], 1)

    def test_the_approval_covers_the_document_the_name_and_replace(self):
        base = u.approval_of(u.prepare(VALID, "a.yaml"))
        self.assertEqual(base, u.approval_of(u.prepare(VALID, "a.yaml")))
        self.assertNotEqual(base, u.approval_of(u.prepare(VALID + "# changed\n", "a.yaml")))
        self.assertNotEqual(base, u.approval_of(u.prepare(VALID, "b.yaml")))
        self.assertNotEqual(base, u.approval_of(u.prepare(VALID, "a.yaml", True)))


class WhatIsSent(unittest.TestCase):
    def test_the_document_goes_as_base64_of_exactly_the_bytes(self):
        text = VALID.replace("Software end of life", "Revisión de logiciels périmés – 終了")
        payload = u.payload_of(u.prepare(text, "a.yaml"), True)
        self.assertEqual(set(payload), {"source_name", "doc"})
        self.assertEqual(base64.b64decode(payload["doc"]).decode("utf-8"), text)

    def test_replace_goes_only_with_a_push_that_asks_for_it(self):
        replacing, keeping = u.prepare(VALID, "a.yaml", True), u.prepare(VALID, "a.yaml")
        self.assertIs(u.payload_of(replacing, True)["replace"], True)
        self.assertNotIn("replace", u.payload_of(keeping, True))
        self.assertNotIn("replace", u.payload_of(replacing, False), "the validate route takes no replace")


class WhatValidationSays(unittest.TestCase):
    def test_a_document_the_backend_accepts_is_valid(self):
        self.assertEqual(u.validation_of(200, VALID_ANSWER), {"valid": True})

    def test_a_document_the_backend_refuses_comes_back_with_every_error(self):
        out = u.validation_of(200, INVALID_ANSWER)
        self.assertIs(out["valid"], False)
        self.assertEqual(out["validation_errors"], INVALID_ANSWER["errors"])
        self.assertEqual(out["error_count"], 2)
        self.assertIn("2 problem", out["problem"])

    def test_a_document_the_backend_could_not_read_is_not_valid_and_says_why(self):
        out = u.validation_of(200, {"status": "error", "error": "Failed to parse 'doc' file content into a valid UseCase object."})
        self.assertIs(out["valid"], False)
        self.assertIn("Failed to parse", out["problem"])

    def test_nothing_that_is_not_a_clear_yes_is_taken_for_valid(self):
        for body in ({"status": "success"}, {"status": "success", "valid": "true"}, {"status": "success", "valid": False}, {"status": "ok", "valid": True},
                     {"valid": True}, "OK", [], None, 200, {"status": "conflict"}):
            self.assertIsNot(u.validation_of(200, body).get("valid"), True, repr(body))

    def test_a_backend_that_could_not_be_asked_is_unknown_not_invalid(self):
        self.assertEqual(u.validation_of(None, None, "the backend could not be reached"), {"valid": None, "problem": "the backend could not be reached"})


class Review(unittest.TestCase):
    def go(self, post, **over):
        return run(u.review(u.prepare(VALID, "servicenow.yaml", over.get("replace", False)), post))

    def test_a_valid_document_gets_a_preview_and_an_approval_code(self):
        post = Recorder(body=VALID_ANSWER)
        out = self.go(post)
        self.assertTrue(out["valid"])
        self.assertTrue(out["needs_approval"])
        self.assertFalse(out["pushed"])
        self.assertEqual(out["approval"], u.approval_of(u.prepare(VALID, "servicenow.yaml")))
        self.assertEqual((out["id"], out["steps"]), ("uc-servicenow-eol", 4))
        self.assertNotIn("warning", out)

    def test_it_asks_the_validate_route_only_and_never_replaces(self):
        post = Recorder(body=VALID_ANSWER)
        self.go(post, replace=True)
        self.assertEqual(len(post.sent), 1)
        self.assertEqual(set(post.sent[0]), {"source_name", "doc"})

    def test_a_document_that_is_not_valid_gets_its_errors_and_no_approval_code(self):
        out = self.go(Recorder(body=INVALID_ANSWER))
        self.assertIs(out["valid"], False)
        self.assertFalse(out["needs_approval"])
        self.assertNotIn("approval", out)
        self.assertEqual(out["validation_errors"], INVALID_ANSWER["errors"])
        self.assertIn("Fix every listed error", out["next"])

    def test_a_backend_that_could_not_be_asked_gives_no_approval_code(self):
        for post in (Recorder(status=None, body=None, problem="the backend could not be reached"), Recorder(body={"unexpected": 1}), Recorder(body="OK")):
            out = self.go(post)
            self.assertIsNone(out["valid"])
            self.assertNotIn("approval", out)
            self.assertFalse(out["needs_approval"])
            self.assertIn("Try again later", out["next"])

    def test_warns_when_it_would_overwrite(self):
        out = self.go(Recorder(body=VALID_ANSWER), replace=True)
        self.assertTrue(out["replace"])
        self.assertIn("overwritten", out["warning"])


class Pushing(unittest.TestCase):
    def go(self, post, approval="right", replace=False):
        p = u.prepare(VALID, "servicenow.yaml", replace)
        return run(u.push(p, u.approval_of(p) if approval == "right" else approval, post))

    def test_without_the_right_approval_nothing_is_sent(self):
        for approval in (None, "", "right-looking", "x" * 64):
            post = Recorder(body=PUSHED)
            out = self.go(post, approval)
            self.assertFalse(out["pushed"], repr(approval))
            self.assertIn("approval", out["problem"])
            self.assertEqual(post.sent, [], repr(approval))

    def test_an_approval_for_another_document_does_not_push_this_one(self):
        post = Recorder(body=PUSHED)
        out = self.go(post, u.approval_of(u.prepare(VALID + "# something else\n", "servicenow.yaml")))
        self.assertFalse(out["pushed"])
        self.assertEqual(post.sent, [])

    def test_sends_the_name_and_the_exact_document_and_reports_what_was_loaded(self):
        post = Recorder(body=PUSHED)
        out = self.go(post)
        self.assertEqual(len(post.sent), 1)
        self.assertEqual(post.sent[0], u.payload_of(u.prepare(VALID, "servicenow.yaml"), True))
        self.assertTrue(out["pushed"])
        self.assertEqual(out["loaded"], {"key": "uc-servicenow-eol@1.0.0", "content_hash": "abc", "stats": {"steps": 4}})
        self.assertEqual(out["backend"], PUSHED)

    def test_sends_replace_only_when_asked(self):
        post = Recorder(body=PUSHED)
        self.go(post, replace=True)
        self.assertIs(post.sent[0]["replace"], True)

    def test_success_without_a_write_is_not_a_push(self):
        for body in ({"status": "success"}, VALID_ANSWER, {**PUSHED, "action": "unchanged"}, {**PUSHED, "action": None}, {"status": "success", "action": "Pushed"}):
            out = self.go(Recorder(body=body))
            self.assertFalse(out["pushed"], repr(body))
            self.assertIn("not that it pushed", out["problem"])

    def test_a_validation_failure_comes_back_with_every_error(self):
        out = self.go(Recorder(body={**INVALID_ANSWER, "error_type": "ValidationError"}))
        self.assertFalse(out["pushed"])
        self.assertEqual(out["validation_errors"], INVALID_ANSWER["errors"])
        self.assertIn("Fix every listed error", out["next"])

    def test_a_conflict_says_so_and_does_not_suggest_overwriting_without_asking(self):
        out = self.go(Recorder(body={"status": "conflict", "error": "uc-servicenow-eol 1.0.0 already exists", "hint": "Pass 'replace': true in payload to overwrite this version."}))
        self.assertFalse(out["pushed"])
        self.assertTrue(out["conflict"])
        self.assertIn("already exists", out["problem"])
        self.assertIn("ask the person", out["hint"])
        self.assertNotIn("Pass 'replace'", out["hint"])

    def test_a_database_error_is_not_a_push(self):
        out = self.go(Recorder(body={"status": "error", "error_type": "DatabaseError", "error": "constraint failed"}))
        self.assertFalse(out["pushed"])
        self.assertEqual(out["problem"], "constraint failed")

    def test_only_the_backends_answer_decides_not_the_http_code(self):
        self.assertFalse(self.go(Recorder(status=200, body={"status": "error", "error": "no"}))["pushed"])
        self.assertTrue(self.go(Recorder(status=500, body=PUSHED))["pushed"], "the backend said it, and the code is only the transport")

    def test_an_answer_in_a_form_not_known_is_never_taken_for_a_success(self):
        for body in ({"loaded": 4}, {"data": []}, {"status": "ok"}, {"status": "partial"}, "OK", [], None, 200):
            out = self.go(Recorder(status=200, body=body))
            self.assertFalse(out["pushed"], repr(body))
            self.assertIn("problem", out, repr(body))

    def test_a_backend_that_could_not_be_reached_is_not_a_push(self):
        out = self.go(Recorder(status=None, body=None, problem="the backend could not be reached"))
        self.assertEqual(out, {"pushed": False, "problem": "the backend could not be reached"})

    def test_a_very_long_answer_is_cut_not_dropped(self):
        out = self.go(Recorder(body="x" * 50000))
        self.assertLess(len(out["backend"]), 7000)
        self.assertTrue(out["backend"].endswith("…"))


class TheRealRequest(unittest.TestCase):
    def post(self, handler, route=None, payload=None):
        transport = httpx.MockTransport(handler)
        return run(tools._poster(None, route or constants.URL_PLAYBOOK_LOAD, transport)(payload or {"source_name": "a.yaml", "doc": "e30="}))

    def test_the_two_routes_are_the_backends(self):
        self.assertEqual(constants.URL_PLAYBOOK_LOAD, "/v1/graphloader/playbook/load")
        self.assertEqual(constants.URL_PLAYBOOK_VALIDATE, "/v1/graphloader/playbook/validate")

    def test_posts_to_the_route_it_is_given_with_the_json_body(self):
        for route in (constants.URL_PLAYBOOK_LOAD, constants.URL_PLAYBOOK_VALIDATE):
            seen = {}

            def handler(request):
                seen.update(url=str(request.url), method=request.method, body=json.loads(request.content))
                return httpx.Response(200, json={"status": "success"})

            status, body, problem = self.post(handler, route)
            self.assertEqual((status, body, problem), (200, {"status": "success"}, None))
            self.assertTrue(seen["url"].endswith(route), seen["url"])
            self.assertEqual((seen["method"], seen["body"]), ("POST", {"source_name": "a.yaml", "doc": "e30="}))

    def test_sends_the_callers_credentials(self):
        seen = {}

        def handler(request):
            seen["headers"] = dict(request.headers)
            return httpx.Response(200, json={"status": "success"})

        with mock.patch.object(tools.utils, "get_cc_headers", return_value={"Authorization": "caller-token", "X-Cow-Security-Context": "{}"}):
            self.post(handler)
        self.assertEqual(seen["headers"]["authorization"], "caller-token")
        self.assertEqual(seen["headers"]["x-cow-security-context"], "{}")

    def test_keeps_the_whole_body_of_an_error(self):
        body = {"status": "error", "errors": ["a", "b"]}
        self.assertEqual(self.post(lambda r: httpx.Response(400, json=body)), (400, body, None))

    def test_a_body_that_is_not_json_is_kept_as_text(self):
        self.assertEqual(self.post(lambda r: httpx.Response(502, text="Bad gateway")), (502, "Bad gateway", None))

    def test_a_timeout_says_it_is_not_known_what_the_backend_concluded(self):
        def handler(request):
            raise httpx.ReadTimeout("slow", request=request)

        status, body, problem = self.post(handler)
        self.assertIsNone(status)
        self.assertIn("not known", problem)

    def test_a_connection_failure_says_nothing_was_sent_through_and_hides_the_detail(self):
        def handler(request):
            raise httpx.ConnectError("refused by 10.0.0.7", request=request)

        status, body, problem = self.post(handler)
        self.assertIsNone(status)
        self.assertIn("nothing was sent through", problem)
        self.assertNotIn("10.0.0.7", problem)


class TheTools(unittest.IsolatedAsyncioTestCase):
    """The tool functions themselves, with a backend that answers each route as told and remembers which routes were hit."""

    def backend(self, validate=None, load=None):
        self.hits = []
        posts = {constants.URL_PLAYBOOK_VALIDATE: Recorder(body=validate if validate is not None else VALID_ANSWER),
                 constants.URL_PLAYBOOK_LOAD: Recorder(body=load if load is not None else PUSHED)}

        def poster(ctx, route, transport=None):
            async def post(payload):
                self.hits.append(route)
                return await posts[route](payload)
            return post
        return mock.patch.object(tools, "_poster", poster), posts

    async def test_validate_writes_nothing_and_says_what_the_backend_said(self):
        patch, posts = self.backend(validate=INVALID_ANSWER)
        with patch:
            out = await tools.validate_use_case_yaml(VALID, "servicenow.yaml")
        self.assertEqual(self.hits, [constants.URL_PLAYBOOK_VALIDATE])
        self.assertIs(out["valid"], False)
        self.assertEqual(out["validation_errors"], INVALID_ANSWER["errors"])
        self.assertEqual(out["id"], "uc-servicenow-eol")

    async def test_the_first_step_only_validates(self):
        patch, posts = self.backend()
        with patch:
            out = await tools.push_use_case(VALID, "servicenow.yaml")
        self.assertEqual(self.hits, [constants.URL_PLAYBOOK_VALIDATE])
        self.assertTrue(out["needs_approval"])
        self.assertEqual(posts[constants.URL_PLAYBOOK_LOAD].sent, [])

    async def test_the_second_step_pushes_with_the_approval_and_only_then(self):
        patch, posts = self.backend()
        with patch:
            first = await tools.push_use_case(VALID, "servicenow.yaml")
            self.hits.clear()
            refused = await tools.push_use_case(VALID, "servicenow.yaml", approval="not-the-code")
            self.assertEqual((self.hits, refused["pushed"]), ([], False))
            done = await tools.push_use_case(VALID, "servicenow.yaml", approval=first["approval"])
        self.assertEqual(self.hits, [constants.URL_PLAYBOOK_LOAD])
        self.assertTrue(done["pushed"])

    async def test_a_document_that_is_not_valid_never_reaches_the_load_route(self):
        patch, posts = self.backend(validate=INVALID_ANSWER)
        with patch:
            out = await tools.push_use_case(VALID, "servicenow.yaml")
        self.assertNotIn("approval", out)
        self.assertEqual(posts[constants.URL_PLAYBOOK_LOAD].sent, [])

    async def test_a_file_that_is_not_a_use_case_is_refused_before_anything_is_sent(self):
        patch, posts = self.backend()
        with patch:
            with self.assertRaises(Exception):
                await tools.push_use_case("kind: Rule\n")
            with self.assertRaises(Exception):
                await tools.validate_use_case_yaml("kind: Rule\n")
        self.assertEqual(self.hits, [])


class Switch(unittest.TestCase):
    def test_it_is_off_unless_asked_for(self):
        for value, want in (("", False), ("0", False), ("no", False), ("1", True), ("true", True), ("YES", True), (" on ", True)):
            with mock.patch.dict(os.environ, {"PLAYBOOK_PUSH_ENABLED": value}):
                self.assertIs(tools.enabled(), want, repr(value))
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(tools.enabled())


if __name__ == "__main__":
    unittest.main()
