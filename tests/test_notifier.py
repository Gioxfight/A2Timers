import unittest
from datetime import datetime, timedelta, timezone

from notifier import AlertTracker

START = datetime(2026, 10, 5, 11, 0, tzinfo=timezone.utc)
MIN = timedelta(minutes=1)


class AlertTrackerTests(unittest.TestCase):
    def setUp(self):
        self.tracker = AlertTracker()

    def test_fires_once_inside_lead(self):
        self.assertTrue(self.tracker.should_alert("k", START, START - 5 * MIN, 5))
        self.assertFalse(self.tracker.should_alert("k", START, START - 4 * MIN, 5))

    def test_not_before_lead(self):
        self.assertFalse(self.tracker.should_alert("k", START, START - 5 * MIN - timedelta(seconds=1), 5))

    def test_not_at_start(self):
        self.assertFalse(self.tracker.should_alert("k", START, START, 5))

    def test_startup_inside_lead_fires(self):
        self.assertTrue(self.tracker.should_alert("k", START, START - 2 * MIN, 5))

    def test_next_occurrence_fires_again(self):
        self.tracker.should_alert("k", START, START - 5 * MIN, 5)
        later = START + timedelta(hours=3)
        self.assertTrue(self.tracker.should_alert("k", later, later - 5 * MIN, 5))

    def test_events_are_independent(self):
        self.assertTrue(self.tracker.should_alert("a", START, START - 3 * MIN, 5))
        self.assertTrue(self.tracker.should_alert("b", START, START - 3 * MIN, 5))


if __name__ == "__main__":
    unittest.main()
