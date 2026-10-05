import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import schedule

CEST = timezone(timedelta(hours=2))
EVENTS = Path(__file__).resolve().parent.parent / "events.json"


def utc(*parts):
    return datetime(*parts, tzinfo=timezone.utc)


def rule(anchor="00:00", every=60, duration=0):
    return schedule.parse_rule({"id": "t", "name": "T", "anchor_utc": anchor,
                                "every_minutes": every, "duration_minutes": duration})


class ParseRuleTests(unittest.TestCase):
    def test_valid_rule(self):
        r = rule("02:30", 180, 10)
        self.assertEqual((r.anchor_minutes, r.every_minutes, r.duration_minutes), (150, 180, 10))

    def test_rejects_period_not_dividing_day(self):
        with self.assertRaises(ValueError):
            rule(every=420)

    def test_rejects_bad_anchor(self):
        for anchor in ("25:00", "ab", "12"):
            with self.subTest(anchor), self.assertRaises(ValueError):
                rule(anchor=anchor)

    def test_rejects_duration_not_shorter_than_period(self):
        with self.assertRaises(ValueError):
            rule(every=60, duration=60)


class QuestlogFixtureTests(unittest.TestCase):
    """Values observed on questlog.gg at 2026-10-05 12:10 CEST."""

    def setUp(self):
        self.rules = {r.id: r for r in schedule.load_rules(EVENTS)}
        self.now = datetime(2026, 10, 5, 12, 10, 30, tzinfo=CEST)

    def upcoming_hours(self, rule_id, count):
        hours, t = [], self.now
        for _ in range(count):
            t = schedule.next_start(self.rules[rule_id], t)
            hours.append(t.astimezone(CEST).hour)
        return hours

    def test_next_starts_match_questlog(self):
        expected = {"shugo": 13, "rift": 14, "kaira": 13, "reset": 18}
        for rule_id, hour in expected.items():
            with self.subTest(rule_id):
                start = schedule.next_start(self.rules[rule_id], self.now)
                self.assertEqual(start.astimezone(CEST), datetime(2026, 10, 5, hour, 0, tzinfo=CEST))

    def test_rift_portals_match_questlog(self):
        self.assertEqual(self.upcoming_hours("rift", 5), [14, 17, 20, 23, 2])

    def test_kaira_spawns_match_questlog(self):
        self.assertEqual(self.upcoming_hours("kaira", 3), [13, 16, 19])


class StateTests(unittest.TestCase):
    def test_active_inside_window(self):
        st = schedule.state(rule(every=180, duration=10), utc(2026, 10, 5, 12, 5), 5)
        self.assertEqual((st.kind, st.seconds, st.next_start), ("active", 300, utc(2026, 10, 5, 15, 0)))

    def test_window_opens_at_exact_start(self):
        st = schedule.state(rule(duration=10), utc(2026, 10, 5, 11, 0), 5)
        self.assertEqual((st.kind, st.seconds), ("active", 600))

    def test_idle_after_window_closes(self):
        st = schedule.state(rule(duration=10), utc(2026, 10, 5, 11, 10), 5)
        self.assertEqual((st.kind, st.seconds, st.next_start), ("idle", 3000, utc(2026, 10, 5, 12, 0)))

    def test_zero_duration_is_never_active(self):
        st = schedule.state(rule("02:00", 180), utc(2026, 10, 5, 11, 0), 5)
        self.assertEqual((st.kind, st.seconds, st.next_start), ("idle", 10800, utc(2026, 10, 5, 14, 0)))

    def test_soon_within_lead(self):
        r = rule()
        self.assertEqual(schedule.state(r, utc(2026, 10, 5, 10, 55), 5).kind, "soon")
        self.assertEqual(schedule.state(r, utc(2026, 10, 5, 10, 54, 59), 5).kind, "idle")

    def test_midnight_wrap(self):
        self.assertEqual(schedule.next_start(rule(every=180), utc(2026, 10, 5, 23, 30)), utc(2026, 10, 6, 0, 0))
        kaira = rule("02:00", 180)
        self.assertEqual(schedule.next_start(kaira, utc(2026, 10, 5, 23, 30)), utc(2026, 10, 6, 2, 0))
        self.assertEqual(schedule.next_start(kaira, utc(2026, 10, 6, 0, 30)), utc(2026, 10, 6, 2, 0))

    def test_non_utc_now_gives_same_result(self):
        r = rule(every=180, duration=10)
        self.assertEqual(schedule.state(r, datetime(2026, 10, 5, 12, 10, tzinfo=CEST), 5),
                         schedule.state(r, utc(2026, 10, 5, 10, 10), 5))

    def test_reset_stays_at_16_utc_across_dst_change(self):
        reset = rule("16:00", 1440)
        self.assertEqual(schedule.next_start(reset, utc(2026, 10, 24, 12)), utc(2026, 10, 24, 16))
        self.assertEqual(schedule.next_start(reset, utc(2026, 10, 25, 12)), utc(2026, 10, 25, 16))


class FormatTests(unittest.TestCase):
    def test_format_seconds(self):
        cases = {0: "00:00", 59.2: "01:00", 3599: "59:59", 3600: "1:00:00", 20832: "5:47:12", -3: "00:00"}
        for seconds, text in cases.items():
            with self.subTest(seconds):
                self.assertEqual(schedule.format_seconds(seconds), text)


if __name__ == "__main__":
    unittest.main()
