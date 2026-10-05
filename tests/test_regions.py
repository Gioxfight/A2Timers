import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import schedule

CEST = timezone(timedelta(hours=2))
EVENTS = Path(__file__).resolve().parent.parent / "events.json"
# questlog.gg region schedules observed on Monday 2026-10-05 at 14:49 CEST.
NOW = datetime(2026, 10, 5, 14, 49, tzinfo=CEST)


def local(month, day, hour, minute=0):
    return datetime(2026, month, day, hour, minute, tzinfo=CEST)


class RegionMergeTests(unittest.TestCase):
    def test_global_is_the_default(self):
        self.assertEqual(schedule.load_rules(EVENTS), schedule.load_rules(EVENTS, "global"))

    def test_unknown_region_is_rejected(self):
        with self.assertRaises(ValueError):
            schedule.load_rules(EVENTS, "mars")

    def test_override_replaces_repeat_kind(self):
        base = {"id": "x", "name": "X", "anchor_utc": "02:00", "every_minutes": 180,
                "regions": {"kr": {"anchor_utc": "12:20", "weekdays": ["wed", "sat"]}}}
        rule = schedule.parse_rule(schedule.merge_region(base, "kr"))
        self.assertEqual((rule.anchor_minutes, rule.weekdays, rule.every_minutes), (740, (2, 5), 1440))
        back = {"id": "y", "name": "Y", "anchor_utc": "21:00", "weekdays": ["mon"],
                "regions": {"kr": {"every_minutes": 240, "anchor_utc": "16:00"}}}
        rule = schedule.parse_rule(schedule.merge_region(back, "kr"))
        self.assertEqual((rule.weekdays, rule.every_minutes), (None, 240))


class RegionScheduleTests(unittest.TestCase):
    def next_starts(self, region, rule_id, count=1):
        rule = {r.id: r for r in schedule.load_rules(EVENTS, region)}[rule_id]
        starts, t = [], NOW
        for _ in range(count):
            t = schedule.next_start(rule, t)
            starts.append(t.astimezone(CEST))
        return starts

    def test_korea(self):
        expected = {
            "shugo": [local(10, 5, 15)],
            "rift": [local(10, 5, 16), local(10, 5, 19), local(10, 5, 22), local(10, 6, 1)],
            "kaira": [local(10, 5, 18), local(10, 5, 22), local(10, 6, 2)],
            "siege": [local(10, 7, 14, 20), local(10, 10, 14, 20), local(10, 14, 14, 20)],
            "siege_bosses": [local(10, 7, 14, 45), local(10, 10, 14, 45)],
            "nahma": [local(10, 9, 15), local(10, 11, 15), local(10, 16, 15)],
            "reset": [local(10, 5, 22), local(10, 6, 22)],
            "weekly_reset": [local(10, 6, 22), local(10, 13, 22)],
        }
        for rule_id, starts in expected.items():
            with self.subTest(rule_id):
                self.assertEqual(self.next_starts("kr", rule_id, len(starts)), starts)

    def test_taiwan(self):
        expected = {
            "shugo": [local(10, 5, 15)],
            "rift": [local(10, 5, 17), local(10, 5, 20), local(10, 5, 23), local(10, 6, 2)],
            "kaira": [local(10, 5, 15), local(10, 5, 19), local(10, 5, 23)],
            "siege": [local(10, 7, 15, 20), local(10, 10, 15, 20)],
            "siege_bosses": [local(10, 7, 15, 45), local(10, 10, 15, 45)],
            "nahma": [local(10, 9, 16), local(10, 11, 16)],
            "reset": [local(10, 5, 23), local(10, 6, 23)],
            "weekly_reset": [local(10, 6, 23), local(10, 13, 23)],
        }
        for rule_id, starts in expected.items():
            with self.subTest(rule_id):
                self.assertEqual(self.next_starts("tw", rule_id, len(starts)), starts)

    def test_global_unchanged(self):
        self.assertEqual(self.next_starts("global", "kaira", 2), [local(10, 5, 16), local(10, 5, 19)])
        self.assertEqual(self.next_starts("global", "reset"), [local(10, 5, 18)])


if __name__ == "__main__":
    unittest.main()
