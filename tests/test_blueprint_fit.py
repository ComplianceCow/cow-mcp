import unittest

from tools.playbook import blueprint_fit as b

SPECIFIC = "Triggered when a NIST 800-53 v5 (L2) assessment run completes. Fetches run details and the Jira config, then triggers the second workflow once per evidence."
GENERIC = "Triggered when an assessment run completes. Fetches run details and the Jira config, then triggers the second workflow once per evidence."
LISTING = [
    {"folder": "TicketsFlow", "description": SPECIFIC, "hasDefinition": True},
    {"folder": "TicketsFlowAny", "description": GENERIC, "hasDefinition": True},
    {"folder": "Unrelated", "description": "Assessment Run Completed", "hasDefinition": False},
]


def design(blueprint, assessment):
    return {"spec": {"steps": [{"id": "w", "type": "create_workflow", "refs": {"workflow": blueprint}, "config": {"assessmentName": assessment}}]}}


class TriggerScope(unittest.TestCase):
    def test_a_named_assessment_is_returned_without_its_level_tag_kept_in_the_text(self):
        self.assertEqual(b.trigger_scope(SPECIFIC), "NIST 800-53 v5 (L2)")

    def test_a_generic_trigger_has_no_scope(self):
        self.assertIsNone(b.trigger_scope(GENERIC))

    def test_any_and_every_are_generic(self):
        self.assertIsNone(b.trigger_scope("Triggered when any assessment run completes."))
        self.assertIsNone(b.trigger_scope("Runs when every assessment run is completed."))

    def test_a_description_that_says_nothing_has_no_scope(self):
        self.assertIsNone(b.trigger_scope("Assessment Run Completed"))
        self.assertIsNone(b.trigger_scope(None))


class Fits(unittest.TestCase):
    def test_a_generic_trigger_fits_everything(self):
        self.assertTrue(b.fits(None, "Any Assessment"))

    def test_a_named_trigger_fits_only_that_assessment(self):
        self.assertTrue(b.fits("NIST 800-53 v5 (L2)", "NIST 800-53 v5"))
        self.assertFalse(b.fits("NIST 800-53 v5 (L2)", "User Deprovisioning Policy"))
        self.assertFalse(b.fits("NIST 800-53 v5 (L2)", None))


class Issues(unittest.TestCase):
    def test_a_named_trigger_on_another_assessment_is_an_error_that_names_the_generic_alternative(self):
        got = b.issues(design("TicketsFlow", "User Deprovisioning Policy"), LISTING)
        self.assertEqual(len(got), 1)
        self.assertEqual((got[0]["check"], got[0]["severity"], got[0]["step"]), ("workflow-blueprint", "error", "w"))
        self.assertIn("TicketsFlowAny", got[0]["message"])

    def test_the_named_trigger_on_the_assessment_it_names_is_fine(self):
        self.assertEqual(b.issues(design("TicketsFlow", "NIST 800-53 v5"), LISTING), [])

    def test_a_generic_trigger_is_fine_anywhere(self):
        self.assertEqual(b.issues(design("TicketsFlowAny", "User Deprovisioning Policy"), LISTING), [])

    def test_an_unknown_blueprint_or_no_listing_is_not_judged(self):
        self.assertEqual(b.issues(design("Ghost", "x"), LISTING), [])
        self.assertEqual(b.issues(design("TicketsFlow", "x"), None), [])

    def test_the_alternative_must_be_deployable_and_similar(self):
        self.assertEqual(b.alternatives(LISTING[0], LISTING), ["TicketsFlowAny"])
