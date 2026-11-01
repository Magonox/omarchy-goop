import os, re, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from goop import hypr

SHELL = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "shell")


def source(name):
    with open(os.path.join(SHELL, name)) as f:
        return f.read()


class Summary(unittest.TestCase):
    def test_a_scaled_panel_is_reported_in_layout_pixels(self):
        m = hypr.monitor_summary({"id": 0, "name": "eDP-1", "x": 0, "y": 0, "width": 2560, "height": 1600, "scale": 2, "transform": 0, "focused": True})
        self.assertEqual((m["w"], m["h"], m["focused"]), (1280, 800, True))

    def test_a_rotated_monitor_swaps_its_sides(self):
        m = hypr.monitor_summary({"id": 1, "name": "DP-2", "x": 1280, "y": 0, "width": 1920, "height": 1080, "scale": 1, "transform": 1})
        self.assertEqual((m["w"], m["h"], m["x"]), (1080, 1920, 1280))

    def test_a_fractional_scale_rounds_and_missing_fields_do_not_break_it(self):
        m = hypr.monitor_summary({"id": 2, "name": "HDMI-A-1", "x": -1920, "y": 0, "width": 1920, "height": 1080, "scale": 1.5})
        self.assertEqual((m["w"], m["h"], m["x"], m["focused"]), (1280, 720, -1920, False))
        self.assertEqual(hypr.monitor_summary({"id": 3, "name": "x", "x": 0, "y": 0, "width": 800, "height": 600})["w"], 800)


class OverlaySource(unittest.TestCase):
    """The overlay is QML, so these read its source for the multi-monitor rules."""

    def test_the_overlay_follows_the_focused_monitor_and_every_window_of_it_does_too(self):
        src = source("Goop.qml")
        self.assertIn("screen: root.screenFor(win.monName)", src)
        self.assertIn("screen: win.screen", src)                      # the ask box
        self.assertIn("w.monitor === cur.id", src)                    # only windows on this monitor show a goop
        self.assertIn("w.x -= win.monX", src)                         # positions are shifted by the monitor's origin
        self.assertIn("parseFloat(p[0]) - win.monX", src)             # and so is the cursor the eyes follow
        self.assertIn("screen: app.screen", source("Wizard.qml"))

    def test_the_state_feed_reports_monitors_and_each_windows_monitor(self):
        text = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state.py")).read()
        self.assertIn('"monitor": c.get("monitor", 0)', text)
        self.assertIn('"monitors": monitors', text)


class Mascot(unittest.TestCase):
    def test_the_gloss_and_the_drip_hang_on_the_live_outline_not_on_fixed_spots(self):
        src = source("GoopMark.qml")
        self.assertIn("Goo.points(13, 13, 13", src)
        self.assertIn("x: g.glossX", src)
        self.assertIn("g.rim[3].y", src)
        self.assertIsNone(re.search(r"Drip \{[^}]*\by: 25", src), "the drip must not be pinned to a fixed spot")


if __name__ == "__main__":
    unittest.main()
