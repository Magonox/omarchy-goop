import os, sys, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from goop import doctor, settings


def by_id(items):
    return {c["id"]: c for c in items}


class Checks(unittest.TestCase):
    def test_everything_present(self):
        c = by_id(doctor.checks("claude", None, which=lambda t: "/usr/bin/" + t, exists=lambda p: True))
        self.assertTrue(all(x["ok"] for x in c.values()))

    def test_missing_pieces_come_with_hints(self):
        c = by_id(doctor.checks("claude", None, which=lambda t: None, exists=lambda p: False))
        self.assertFalse(c["agent"]["ok"])
        self.assertIn("Claude Code", c["agent"]["hint"])
        self.assertIn("setup.sh", c["voice"]["hint"])
        for k in ("hyprctl", "screenshots", "typing", "pdf", "audio"):
            self.assertFalse(c[k]["ok"])
            self.assertTrue(c[k]["hint"])

    def test_required_vs_optional(self):
        c = by_id(doctor.checks("claude", None, which=lambda t: "x", exists=lambda p: True))
        self.assertTrue(c["agent"]["required"] and c["screenshots"]["required"])
        self.assertFalse(c["voice"]["required"] or c["typing"]["required"] or c["pdf"]["required"])

    def test_other_provider_uses_its_own_problem(self):
        c = by_id(doctor.checks("grok", "no API key for 'grok'", which=lambda t: "x", exists=lambda p: True))
        self.assertFalse(c["agent"]["ok"])
        self.assertEqual(c["agent"]["hint"], "no API key for 'grok'")
        self.assertTrue(by_id(doctor.checks("grok", None, which=lambda t: None, exists=lambda p: True))["agent"]["ok"])  # claude CLI not needed


class Providers(unittest.TestCase):
    def test_listing_marks_active_and_problems(self):
        class P:
            def __init__(self, ok, problem=None):
                self._ok, self._problem = ok, problem
            def available(self):
                return self._ok
            def problem(self):
                return self._problem

        class Reg:
            @staticmethod
            def names():
                return ["claude", "grok"]
            @staticmethod
            def get(n):
                return P(True) if n == "claude" else P(False, "no key")

        out = doctor.providers(Reg, "grok")
        self.assertEqual([(p["name"], p["ready"], p["active"], p["problem"]) for p in out],
                         [("claude", True, False, ""), ("grok", False, True, "no key")])


class ProviderSetting(unittest.TestCase):
    def test_only_configured_agents_can_be_chosen(self):
        with mock.patch("goop.agent.registry.names", return_value=["claude", "grok"]):
            self.assertEqual(settings.parse("provider", "grok"), "grok")
            with self.assertRaises(ValueError):
                settings.parse("provider", "nope")


if __name__ == "__main__":
    unittest.main()
