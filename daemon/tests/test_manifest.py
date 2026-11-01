import json, os, re, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Manifest(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "manifest.json")) as f:
            self.m = json.load(f)

    def test_the_id_is_the_permanent_marketplace_id(self):
        self.assertEqual(self.m["id"], "io.github.magonox.goop")
        self.assertRegex(self.m["id"], r"^io\.github\.[a-z0-9-]+\.[a-z0-9-]+$")      # lowercase, namespaced, outside omarchy.*

    def test_the_bar_panel_uses_the_same_id(self):
        with open(os.path.join(ROOT, "shell", "GoopPanel.qml")) as f:
            panel = f.read()
        self.assertIn(f'moduleName: "{self.m["id"]}"', panel)
        self.assertIn(f'ipcTarget: "{self.m["id"]}"', panel)

    def test_no_file_still_uses_the_old_id(self):
        for folder in ("shell", "daemon", "bin", "browser", "docs"):
            for dirpath, _, files in os.walk(os.path.join(ROOT, folder)):
                for name in files:
                    if name.endswith((".pyc", ".png", ".onnx")) or "tests" in dirpath or name == "BACKLOG.md":
                        continue
                    with open(os.path.join(dirpath, name), errors="ignore") as f:
                        self.assertNotIn("shawn.goop", f.read(), os.path.join(dirpath, name))
        with open(os.path.join(ROOT, "README.md")) as f:
            self.assertNotIn("shawn.goop", f.read())

    def test_the_marketplace_basics_are_present(self):
        for key in ("name", "version", "author", "description", "kinds", "entryPoints"):
            self.assertTrue(self.m.get(key), key)
        self.assertRegex(self.m["version"], r"^\d+\.\d+\.\d+$")
        for entry in self.m["entryPoints"].values():
            self.assertTrue(os.path.exists(os.path.join(ROOT, entry)), entry)
        for needed in ("LICENSE", "README.md"):
            self.assertTrue(os.path.exists(os.path.join(ROOT, needed)), needed)

    def test_the_license_is_mit_for_the_named_author(self):
        with open(os.path.join(ROOT, "LICENSE")) as f:
            text = f.read()
        self.assertTrue(text.startswith("MIT License"))
        self.assertIn("Shawn Boehm", text)

    def test_the_readme_covers_what_a_marketplace_listing_needs(self):
        with open(os.path.join(ROOT, "README.md")) as f:
            readme = f.read()
        for heading in ("## Install", "## Uninstall", "## Privacy and permissions", "## Third-party software", "## License"):
            self.assertIn(heading, readme)
        self.assertIn("omarchy plugin remove io.github.magonox.goop", readme)


if __name__ == "__main__":
    unittest.main()
