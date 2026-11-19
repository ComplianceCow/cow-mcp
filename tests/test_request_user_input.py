import asyncio
import unittest

from tools.playbook import request_user_input as r


class Calls:
    """A fake of the platform API that records every call."""

    def __init__(self, register=(201, None)):
        self.log = []
        self.register = register

    async def __call__(self, method, path, body):
        self.log.append((method, path, body))
        if path == r.ASKS_URL:
            status, answer = self.register
            return status, answer if answer is not None else {"ask_id": "ask-1", "status": "open", "escalation": "started", "expires_at": "2026-11-19T10:00:00Z", "chat_url": "https://app/c/x"}
        raise AssertionError(f"unexpected call to {path}")


def run(question="Which group?", calls=None, session="agent-1", **kw):
    calls = calls or Calls()
    out = asyncio.run(r.request(question, call=calls, session_id=session, **kw))
    return out, calls


class Asking(unittest.TestCase):
    def test_it_registers_the_ask_and_reports_that_a_workflow_started(self):
        out, calls = run(wait_minutes=7)
        self.assertEqual(out["success"], True)
        self.assertEqual((out["status"], out["ask_id"], out["escalation"]), ("waiting", "ask-1", "scheduled"))
        (method, path, body), = calls.log
        self.assertEqual((method, path), ("POST", r.ASKS_URL))
        self.assertEqual(body, {"agent_session_id": "agent-1", "kind": "question", "question": "Which group?", "wait_minutes": 7, "expires_in_hours": 24})

    def test_it_never_calls_the_workflow_service_itself(self):
        _, calls = run()
        self.assertEqual([path for _, path, _ in calls.log], [r.ASKS_URL])

    def test_options_are_sent_only_when_given(self):
        _, calls = run(kind="approval", options=["Approve", "Reject"])
        self.assertEqual(calls.log[0][2]["options"], ["Approve", "Reject"])
        _, calls = run()
        self.assertNotIn("options", calls.log[0][2])

    def test_a_repeat_at_the_same_chat_position_reports_the_first_escalation(self):
        out, calls = run(calls=Calls(register=(200, None)))
        self.assertEqual((out["success"], out["ask_id"], out["escalation"]), (True, "ask-1", "already_scheduled"))
        self.assertEqual(len(calls.log), 1)

    def test_the_model_is_told_to_end_its_turn(self):
        out, _ = run()
        self.assertIn("End your turn", out["message"])
        self.assertIn("minutes", out["message"])


class WhenItCannotRun(unittest.TestCase):
    def test_without_a_chat_session_nothing_is_called(self):
        out, calls = run(session="")
        self.assertEqual(out["success"], False)
        self.assertEqual(calls.log, [])

    def test_a_refused_registration_is_reported_with_the_service_message(self):
        for status, body in ((422, {"code": "INVALID_INPUT", "message": "question is required."}),
                             (404, {"code": "SESSION_NOT_FOUND", "message": "No chat belongs to this session."}),
                             (403, {"code": "NOT_OWNER", "message": "Only the chat owner can use this."}),
                             (500, {"code": "INTERNAL", "message": "The ask could not be registered."}),
                             (0, {"message": "the service did not answer"})):
            out, calls = run(calls=Calls(register=(status, body)))
            self.assertEqual(out["success"], False, status)
            self.assertEqual(out["error"], body["message"], status)
            self.assertEqual(len(calls.log), 1, status)

    def test_when_no_workflow_started_the_ask_still_waits_in_the_chat(self):
        for answer in ({"ask_id": "ask-1", "escalation": "none"}, {"ask_id": "ask-1"}):
            out, calls = run(calls=Calls(register=(201, answer)))
            self.assertEqual((out["success"], out["status"], out["escalation"]), (True, "waiting", "unavailable"), answer)
            self.assertEqual(len(calls.log), 1)
            self.assertIn("End your turn", out["message"])

    def test_nothing_the_model_reads_names_the_agent_host(self):
        for kwargs in ({}, {"calls": Calls(register=(201, {"ask_id": "a", "escalation": "none"}))}, {"session": ""}, {"calls": Calls(register=(404, {"message": "No chat belongs to this session."}))}):
            out, _ = run(**kwargs)
            self.assertNotIn("goose", str(out).lower())


class Credentials(unittest.TestCase):
    def test_a_credentials_ask_tells_the_model_the_user_gets_a_link_only(self):
        out, calls = run(kind="credentials", question="Enter the Okta API key in the web app")
        self.assertEqual(calls.log[0][2]["kind"], "credentials")
        self.assertIn("link", out["message"])


class SessionId(unittest.TestCase):
    class Req:
        def __init__(self, meta):
            self.meta = meta

    class Ctx:
        def __init__(self, req):
            self.request_context = req

    def test_it_is_read_from_the_request_meta(self):
        self.assertEqual(r.session_id_of(self.Ctx(self.Req({"agent-session-id": "a-1"}))), "a-1")

    def test_it_is_read_from_an_object_style_meta(self):
        class Meta:
            pass
        meta = Meta()
        setattr(meta, "agent-session-id", "a-2")
        self.assertEqual(r.session_id_of(self.Ctx(self.Req(meta))), "a-2")

    def test_it_is_empty_when_absent(self):
        self.assertEqual(r.session_id_of(None), "")
        self.assertEqual(r.session_id_of(self.Ctx(self.Req(None))), "")
        self.assertEqual(r.session_id_of(self.Ctx(self.Req({}))), "")
        self.assertEqual(r.session_id_of(self.Ctx(self.Req({"agent-session-id": 5}))), "")


if __name__ == "__main__":
    unittest.main()
