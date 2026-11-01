import json, os, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from goop import config, migrate, settings


class Migrating(unittest.TestCase):
    def test_an_unversioned_config_gets_stamped_and_keeps_every_setting(self):
        new, notes = migrate.migrate({"access": "look", "tts": {"speed": 0.9}})
        self.assertEqual(new["config_version"], migrate.CURRENT)
        self.assertEqual((new["access"], new["tts"]), ("look", {"speed": 0.9}))

    def test_a_current_config_comes_back_unchanged(self):
        cfg = {"config_version": migrate.CURRENT, "access": "ask"}
        self.assertEqual(migrate.migrate(cfg), (cfg, []))

    def test_a_newer_config_is_never_touched(self):
        cfg = {"config_version": migrate.CURRENT + 5, "future_setting": [1, 2]}
        self.assertEqual(migrate.migrate(cfg)[0], cfg)

    def test_junk_versions_count_as_unversioned(self):
        for junk in ("two", -3, None, True, 1.5):
            self.assertEqual(migrate.version_of({"config_version": junk}), 0)

    def test_steps_run_in_order_and_report_what_they_did(self):
        steps = {0: lambda c: c.update(a=1) or ["step zero"], 1: lambda c: c.update(b=c["a"] + 1) or ["step one"]}
        with mock.patch.object(migrate, "CURRENT", 2), mock.patch.object(migrate, "STEPS", steps):
            new, notes = migrate.migrate({})
        self.assertEqual((new["a"], new["b"], new["config_version"], notes), (1, 2, 2, ["step zero", "step one"]))

    def test_the_input_is_not_modified(self):
        old = {"access": "ask"}
        migrate.migrate(old)
        self.assertNotIn("config_version", old)

    def test_every_step_up_to_current_exists(self):
        self.assertTrue(all(v in migrate.STEPS for v in range(migrate.CURRENT)))


class OnDisk(unittest.TestCase):
    def test_load_migrates_in_memory_without_writing(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "config.json")
        open(path, "w").write(json.dumps({"access": "look"}))
        with mock.patch.object(config, "PATH", path):
            self.assertEqual(config.load()["config_version"], migrate.CURRENT)
        self.assertNotIn("config_version", json.load(open(path)))

    def test_migrate_file_backs_up_then_writes_and_is_then_a_no_op(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "config.json")
        open(path, "w").write(json.dumps({"access": "look"}))
        settings.migrate_file(path)
        self.assertEqual(json.load(open(path))["config_version"], migrate.CURRENT)
        self.assertEqual(json.load(open(path))["access"], "look")
        self.assertTrue(any(n.startswith("config.json.bak.") for n in os.listdir(d)))
        before = sorted(os.listdir(d))
        settings.migrate_file(path)
        self.assertEqual(sorted(os.listdir(d)), before)               # nothing more to do, so no new backup

    def test_no_config_file_means_nothing_is_created(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "config.json")
        self.assertEqual(settings.migrate_file(path), [])
        self.assertFalse(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
