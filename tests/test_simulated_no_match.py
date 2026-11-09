import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from tools.playbook import simulated_no_match as hook

REQUIREMENT = "Validate Workday terminations, plus device assignment and application assignment checks for deprovisioned users"


class Lease(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "lease.json"
        os.environ["COW_MCP_NO_MATCH_LEASE"] = str(self.path)
        self.force = hook.FORCE_NO_MATCH
        hook.FORCE_NO_MATCH = False

    def tearDown(self):
        hook.FORCE_NO_MATCH = self.force
        os.environ.pop("COW_MCP_NO_MATCH_LEASE", None)
        self.dir.cleanup()

    def lease(self, until, keywords):
        self.path.write_text(json.dumps({"until": until, "keywords": keywords}))

    def test_no_lease_file_means_the_matcher_is_untouched(self):
        self.assertFalse(hook.active(REQUIREMENT))

    def test_valid_lease_applies_to_a_matching_requirement(self):
        self.lease(time.time() + 600, ["device", "application assign"])
        self.assertTrue(hook.active(REQUIREMENT))

    def test_other_requirements_are_not_affected(self):
        self.lease(time.time() + 600, ["device", "application assign"])
        self.assertFalse(hook.active("Terminated Workday workers must have Okta accounts deactivated; group membership check only"))

    def test_expired_lease_does_nothing(self):
        self.lease(time.time() - 1, ["device"])
        self.assertFalse(hook.active(REQUIREMENT))

    def test_a_lease_without_keywords_never_applies(self):
        self.lease(time.time() + 600, [])
        self.assertFalse(hook.active(REQUIREMENT))

    def test_a_broken_lease_file_does_nothing(self):
        self.path.write_text("not json")
        self.assertFalse(hook.active(REQUIREMENT))


if __name__ == "__main__":
    unittest.main()


class Hidden(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "lease.json"
        os.environ["COW_MCP_NO_MATCH_LEASE"] = str(self.path)
        self.force = hook.FORCE_NO_MATCH
        hook.FORCE_NO_MATCH = False

    def tearDown(self):
        hook.FORCE_NO_MATCH = self.force
        os.environ.pop("COW_MCP_NO_MATCH_LEASE", None)
        self.dir.cleanup()

    def test_only_the_named_use_case_is_hidden_while_the_lease_is_valid(self):
        self.path.write_text(json.dumps({"until": time.time() + 600, "keywords": ["x"], "hide": ["uc-a"]}))
        self.assertTrue(hook.hidden("uc-a"))
        self.assertFalse(hook.hidden("uc-b"))

    def test_nothing_is_hidden_after_the_lease_expires_or_without_one(self):
        self.assertFalse(hook.hidden("uc-a"))
        self.path.write_text(json.dumps({"until": time.time() - 1, "keywords": ["x"], "hide": ["uc-a"]}))
        self.assertFalse(hook.hidden("uc-a"))


class Forced(unittest.TestCase):
    def test_the_switch_hides_everything_for_every_requirement(self):
        was = hook.FORCE_NO_MATCH
        hook.FORCE_NO_MATCH = True
        try:
            self.assertTrue(hook.active("anything at all"))
            self.assertTrue(hook.hidden("any-use-case"))
        finally:
            hook.FORCE_NO_MATCH = was
