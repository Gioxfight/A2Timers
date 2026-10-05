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

    def test_missing_file_gives_defaults(self):
        self.assertEqual(settings.load(self.path), {"x": 50, "y": 50, "lead_minutes": 5, "alerts": {}})

    def test_corrupt_file_gives_defaults(self):
        Path(self.path).write_text("{not json", encoding="utf-8")
        self.assertEqual(settings.load(self.path)["lead_minutes"], 5)

    def test_round_trip(self):
        data = {"x": 300, "y": 120, "lead_minutes": 10, "alerts": {"rift": False}}
        settings.save(self.path, data)
        self.assertEqual(settings.load(self.path), data)

    def test_lead_is_clamped(self):
        for raw, expected in ((0, 1), (999, 60)):
            with self.subTest(raw):
                settings.save(self.path, {"lead_minutes": raw})
                self.assertEqual(settings.load(self.path)["lead_minutes"], expected)

    def test_alert_enabled_defaults_to_true(self):
        data = {"alerts": {"rift": False}}
        self.assertTrue(settings.alert_enabled(data, "shugo"))
        self.assertFalse(settings.alert_enabled(data, "rift"))


if __name__ == "__main__":
    unittest.main()
