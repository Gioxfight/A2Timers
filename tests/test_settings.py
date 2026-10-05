import json
import tempfile
import unittest
from pathlib import Path

import settings


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = str(Path(self.dir.name) / "settings.json")

    def tearDown(self):
        self.dir.cleanup()

    def write(self, raw):
        Path(self.path).write_text(json.dumps(raw), encoding="utf-8")

    def test_missing_file_gives_defaults(self):
        self.assertEqual(settings.load(self.path), {"x": 50, "y": 50, "lead_minutes": 5, "language": "auto",
                                                    "check_updates": True, "scale": 1.0, "opacity": 0.85,
                                                    "events": {}})

    def test_corrupt_file_gives_defaults(self):
        Path(self.path).write_text("{not json", encoding="utf-8")
        self.assertEqual(settings.load(self.path)["lead_minutes"], 5)

    def test_round_trip(self):
        data = {"x": 300, "y": 120, "lead_minutes": 10, "language": "en", "check_updates": False,
                "scale": 1.5, "opacity": 0.6, "events": {"rift": {"show": False, "alert": True, "sound": "builtin:gong"}}}
        settings.save(self.path, data)
        self.assertEqual(settings.load(self.path), data)

    def test_lead_is_clamped(self):
        for raw, expected in ((0, 1), (999, 60)):
            with self.subTest(raw):
                self.write({"lead_minutes": raw})
                self.assertEqual(settings.load(self.path)["lead_minutes"], expected)

    def test_scale_and_opacity_are_clamped(self):
        for raw, expected in (({"scale": 0.1, "opacity": 0.0}, (0.6, 0.2)),
                              ({"scale": 9, "opacity": 3}, (2.0, 1.0)),
                              ({"scale": "big", "opacity": True}, (1.0, 0.85))):
            with self.subTest(raw):
                self.write(raw)
                data = settings.load(self.path)
                self.assertEqual((data["scale"], data["opacity"]), expected)

    def test_clamp_helpers(self):
        self.assertEqual(settings.clamp_scale(1.234), 1.23)
        self.assertEqual(settings.clamp_opacity(0.05), 0.2)

    def test_invalid_values_are_ignored(self):
        self.write({"language": "fr", "check_updates": "yes", "x": True,
                    "events": {"rift": {"show": "no", "sound": 5}, "kaira": "bad"}})
        data = settings.load(self.path)
        self.assertEqual((data["language"], data["check_updates"], data["x"]), ("auto", True, 50))
        self.assertEqual(data["events"], {"rift": {}})

    def test_legacy_alerts_are_migrated(self):
        self.write({"alerts": {"rift": False}, "events": {"kaira": {"alert": True}}})
        self.assertEqual(settings.load(self.path)["events"], {"rift": {"alert": False}, "kaira": {"alert": True}})

    def test_event_pref_defaults(self):
        data = {"events": {"rift": {"show": False}}}
        self.assertEqual(settings.event_pref(data, "rift", "builtin:gong"),
                         {"show": False, "alert": True, "sound": "builtin:gong"})
        self.assertEqual(settings.event_pref(data, "kaira", "builtin:horn"),
                         {"show": True, "alert": True, "sound": "builtin:horn"})


if __name__ == "__main__":
    unittest.main()
