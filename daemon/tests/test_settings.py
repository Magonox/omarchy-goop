import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from goop import config, settings


class Settings(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "sub", "config.json")     # the directory does not exist yet

    def tearDown(self):
        self.tmp.cleanup()

    def read(self):
        with open(self.path) as f:
            return json.load(f)

    def test_set_creates_file_and_validates_choices(self):
        self.assertEqual(settings.set_value("animations", "off", self.path), "off")
        self.assertEqual(self.read(), {"animations": "off"})
        for bad in ("fast", "", "OFF"):
            with self.assertRaises(ValueError):
                settings.set_value("animations", bad, self.path)
        self.assertEqual(self.read(), {"animations": "off"})               # a rejected value changes nothing

    def test_dotted_keys_json_values_and_other_keys_kept(self):
        settings.set_value("animations", "reduced", self.path)
        settings.set_value("tts.speed", "0.9", self.path)
        settings.set_value("tts.enabled", "false", self.path)
        settings.set_value("model", "haiku", self.path)
        self.assertEqual(self.read(), {"animations": "reduced", "tts": {"speed": 0.9, "enabled": False}, "model": "haiku"})

    def test_get_falls_back_to_defaults(self):
        self.assertEqual(settings.get_value("animations", self.path), "full")        # no file yet
        settings.set_value("animations", "off", self.path)
        self.assertEqual(settings.get_value("animations", self.path), "off")
        self.assertEqual(settings.get_value("tts.pause_ms", self.path), config.DEFAULTS["tts"]["pause_ms"])
        self.assertIsNone(settings.get_value("no.such.key", self.path))

    def test_corrupt_file_is_replaced_not_crashed_on(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w") as f:
            f.write("{not json")
        settings.set_value("animations", "off", self.path)
        self.assertEqual(self.read(), {"animations": "off"})

    def test_default_is_full(self):
        self.assertEqual(config.DEFAULTS["animations"], "full")


if __name__ == "__main__":
    unittest.main()
