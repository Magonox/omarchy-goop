import json, os, shutil, subprocess, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from goop.explainer import build
from test_blueprint import truck

LESSON_JS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "shell", "explainer3d", "lesson.js")
HARNESS = r"""
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8").replace(".pragma library", "") + "\nmodule.exports = {prepare, state};";
const m = { exports: {} }; new Function("module", src)(m);
const scene = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const C = m.exports.prepare(scene);
const out = JSON.parse(process.argv[4]).map(t => { const st = m.exports.state(C, t);
  return { t, spin: st.parts.map(p => p.spin), root: st.root, vis: st.parts.map(p => p.vis) }; });
console.log(JSON.stringify(out));
"""


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class FinaleInTheRenderer(unittest.TestCase):
    """Runs the renderer's own state() (shell/explainer3d/lesson.js) in node against a built scene."""
    @classmethod
    def setUpClass(cls):
        story = truck()
        story["steps"][2]["do"].append({"spin": ["tires"]})
        cls.scene = build.build(story, parts_dir="/tmp/js.parts")
        cls.dir = tempfile.mkdtemp()
        cls.path = os.path.join(cls.dir, "scene.json")
        with open(cls.path, "w") as f:
            json.dump(cls.scene, f)
        with open(os.path.join(cls.dir, "h.js"), "w") as f:
            f.write(HARNESS)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def states(self, times):
        r = subprocess.run(["node", os.path.join(self.dir, "h.js"), LESSON_JS, self.path, json.dumps(times)], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def ids(self):
        return [p["id"] for p in self.scene["parts"]]

    def test_a_demonstration_spin_turns_the_wheel_and_stops_when_the_finale_begins(self):
        spin = next(e for e in self.scene["events"] if e["type"] == "spin")
        fin = self.scene["finale"]
        tire = self.ids().index("tires")
        a, b, c, d = self.states([spin.get("t0") + 0.5, spin["t0"] + 2.0, fin["t0"] + 0.1, fin["t0"] + 3.0])
        self.assertGreater(b["spin"][tire], a["spin"][tire] + 50)                          # it is turning during the explanation
        self.assertAlmostEqual(c["spin"][tire], d["spin"][tire], delta=0.5)               # frozen once the finale begins (nothing drives it yet)
        self.assertEqual(self.scene["parts"][tire]["spin_axis"], [0, 0, 1])

    def test_wheels_roll_in_step_with_the_distance_driven(self):
        fin = self.scene["finale"]
        ids = self.ids()
        tires = [i for i, p in enumerate(ids) if p.startswith("tires")]
        t1, t2 = fin["t_go"] + 3.0, fin["t_go"] + 5.0
        a, b = self.states([t1, t2])
        moved = b["root"]["pos"][0] - a["root"]["pos"][0]
        want = -(moved / fin["roll_radius"]) * 57.2958                                     # one wheel circumference per circumference travelled, forwards is clockwise
        for i in tires:
            self.assertAlmostEqual(b["spin"][i] - a["spin"][i], want, delta=0.5)
        body = ids.index("body")
        self.assertEqual(b["spin"][body], a["spin"][body])                                 # nothing else turns

    def test_the_whole_machine_is_gone_when_the_motion_ends(self):
        fin = self.scene["finale"]
        before, after = self.states([fin["t_go"] + fin["dur"] - 1.0, fin["t_go"] + fin["dur"] + 0.6])
        self.assertTrue(any(before["vis"]))
        self.assertFalse(any(after["vis"]))


if __name__ == "__main__":
    unittest.main()
