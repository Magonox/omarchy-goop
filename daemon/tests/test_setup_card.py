import os, re, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from goop import config, doctor, settings

SHELL = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "shell")


def source(name):
    with open(os.path.join(SHELL, name)) as f:
        return f.read()


class SetupState(unittest.TestCase):
    def test_setup_starts_undone_and_is_a_plain_number_setting(self):
        self.assertEqual(config.DEFAULTS["setup_version"], 0)
        self.assertEqual(settings.parse("setup_version", "1"), 1)
        self.assertEqual(settings.parse("setup_version", "0"), 0)


class WizardSource(unittest.TestCase):
    """The setup card is QML, so these read its source for the things that must stay true."""

    def test_every_check_it_asks_about_exists_in_the_doctor(self):
        ids = {c["id"] for c in doctor.checks(which=lambda x: x, exists=lambda p: True, has_module=lambda n: True, browser_up=True)}
        used = set(re.findall(r'wz\.ok\("(\w+)"\)|[^.\w]ok\("(\w+)"\)', source("Wizard.qml")))
        names = {a or b for a, b in used}
        self.assertTrue({"voice", "listen", "pagereader", "quick3d", "sandbox"} <= names, names)
        self.assertEqual(names - ids, set(), "the wizard asks about a check the doctor does not have")

    def test_every_setting_it_writes_is_a_real_setting(self):
        keys = set(re.findall(r'wz\.set\("([\w.]+)"', source("Wizard.qml"))) | set(re.findall(r'\bset\("([\w.]+)"', source("Wizard.qml")))
        self.assertTrue({"setup_version", "access", "explainers", "tts.muted", "stt.enabled"} <= keys, keys)
        for key in keys:
            top = key.split(".")[0]
            self.assertIn(top, config.DEFAULTS, key)

    def test_the_choices_it_offers_are_the_ones_the_daemon_accepts(self):
        src = source("Wizard.qml")
        for k in settings.CHOICES["access"] + settings.CHOICES["explainers"]:
            self.assertIn(f'k: "{k}"', src, k)

    def test_it_is_wired_in_and_can_be_run_again_from_the_panel(self):
        self.assertIn("Wizard {", source("Goop.qml"))
        self.assertIn("wantWizard", source("Goop.qml"))
        panel = source("GoopPanel.qml")
        self.assertIn("Run setup again", panel)
        self.assertIn('change("setup_version", 0)', panel)

    def test_the_card_can_always_be_skipped(self):
        self.assertIn("Skip setup", source("Wizard.qml"))


if __name__ == "__main__":
    unittest.main()
