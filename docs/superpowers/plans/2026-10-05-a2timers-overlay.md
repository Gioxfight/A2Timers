# A2Timers Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Always-on-top Tkinter overlay showing AION 2 event countdowns (Shugo, Rift, Kaira, daily reset) with sound + Windows toast 5 minutes before each event.

**Architecture:** Pure UTC schedule math in `schedule.py` (rules from `events.json`), alert dedup + OS output in `notifier.py`, JSON prefs in `settings.py`, Tk UI in `overlay.py`. Only `overlay.py` touches Tk; everything else is unit-tested with `unittest`.

**Tech Stack:** Python 3.14 stdlib only (tkinter, winsound, subprocess→PowerShell WinRT toast). No `tzdata` on this machine → app uses `datetime.astimezone()` (OS tz), tests use fixed offsets.

Spec: `docs/superpowers/specs/2026-10-05-a2timers-overlay-design.md`

Run all tests from repo root: `python -m unittest discover -s tests -t . -v`

---

### Task 1: Scaffolding + event rules

**Files:**
- Create: `events.json`, `.gitignore`, `tests/__init__.py` (empty)

- [ ] **Step 1: Create `events.json`**

```json
[
  {"id": "shugo", "name": "Shugo Festival", "icon": "🎉", "anchor_utc": "00:00", "every_minutes": 60, "duration_minutes": 10},
  {"id": "rift", "name": "Spacetime Rift", "icon": "🌀", "anchor_utc": "00:00", "every_minutes": 180, "duration_minutes": 10},
  {"id": "kaira", "name": "Watcher Kaira", "icon": "💀", "anchor_utc": "02:00", "every_minutes": 180, "duration_minutes": 0},
  {"id": "reset", "name": "Reset giornaliero", "icon": "🕕", "anchor_utc": "16:00", "every_minutes": 1440, "duration_minutes": 0}
]
```

- [ ] **Step 2: Create `.gitignore`**

```
__pycache__/
settings.json
*.tmp
```

- [ ] **Step 3: Commit** — `git add -A && git commit -m "chore: scaffold events and gitignore"`

### Task 2: `schedule.py` (TDD)

**Files:** Create `tests/test_schedule.py`, `schedule.py`

- [ ] **Step 1: Write failing tests** — `tests/test_schedule.py`:

```python
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
```

- [ ] **Step 2: Run, expect FAIL** — `ModuleNotFoundError: No module named 'schedule'`

- [ ] **Step 3: Implement `schedule.py`**

```python
"""Pure schedule math for AION 2 recurring events. All rules are defined in UTC."""
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

DAY_MINUTES = 1440


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    icon: str
    anchor_minutes: int
    every_minutes: int
    duration_minutes: int


@dataclass(frozen=True)
class EventState:
    kind: str  # "active" | "soon" | "idle"
    seconds: float  # active: time left in the window; otherwise: time to next start
    next_start: datetime


def parse_rule(data: dict) -> Rule:
    rule_id = data.get("id", "?")
    try:
        hours, minutes = (int(part) for part in data["anchor_utc"].split(":"))
    except (KeyError, ValueError, AttributeError) as exc:
        raise ValueError(f"{rule_id}: anchor_utc must be 'HH:MM'") from exc
    if not (0 <= hours < 24 and 0 <= minutes < 60):
        raise ValueError(f"{rule_id}: anchor_utc out of range")
    every = int(data["every_minutes"])
    duration = int(data.get("duration_minutes", 0))
    if every <= 0 or DAY_MINUTES % every:
        raise ValueError(f"{rule_id}: every_minutes must divide 1440")
    if not 0 <= duration < every:
        raise ValueError(f"{rule_id}: duration_minutes must be in [0, every_minutes)")
    return Rule(id=str(data["id"]), name=str(data["name"]), icon=str(data.get("icon", "")),
                anchor_minutes=hours * 60 + minutes, every_minutes=every, duration_minutes=duration)


def load_rules(path) -> list[Rule]:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, list) or not raw:
        raise ValueError("events.json must be a non-empty list")
    return [parse_rule(item) for item in raw]


def current_start(rule: Rule, now: datetime) -> datetime:
    """Latest occurrence start that is <= now (UTC)."""
    now_utc = now.astimezone(timezone.utc)
    midnight = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    anchor = midnight + timedelta(minutes=rule.anchor_minutes)
    period = timedelta(minutes=rule.every_minutes)
    return anchor + math.floor((now_utc - anchor) / period) * period


def next_start(rule: Rule, now: datetime) -> datetime:
    """First occurrence start strictly after now (UTC)."""
    return current_start(rule, now) + timedelta(minutes=rule.every_minutes)


def state(rule: Rule, now: datetime, lead_minutes: int) -> EventState:
    start = current_start(rule, now)
    upcoming = start + timedelta(minutes=rule.every_minutes)
    end = start + timedelta(minutes=rule.duration_minutes)
    if now < end:
        return EventState("active", (end - now).total_seconds(), upcoming)
    to_next = (upcoming - now).total_seconds()
    return EventState("soon" if to_next <= lead_minutes * 60 else "idle", to_next, upcoming)


def format_seconds(seconds: float) -> str:
    total = max(0, math.ceil(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"
```

- [ ] **Step 4: Run, expect PASS** — `python -m unittest tests.test_schedule -v`
- [ ] **Step 5: Commit** — `feat: schedule math for recurring events`

### Task 3: `notifier.py` (TDD for `AlertTracker`)

**Files:** Create `tests/test_notifier.py`, `notifier.py`

- [ ] **Step 1: Failing tests** — `tests/test_notifier.py`:

```python
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
```

- [ ] **Step 2: Run, expect FAIL** (module missing)
- [ ] **Step 3: Implement `notifier.py`**

```python
"""Alert de-duplication (pure) plus Windows sound and toast output."""
import os
import subprocess
from datetime import datetime
from xml.sax.saxutils import escape

# AppUserModelID of Windows PowerShell: lets an unregistered script show toasts.
POWERSHELL_APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
TOAST_SCRIPT = (
    "$null = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime];"
    "$null = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime];"
    "$xml = New-Object Windows.Data.Xml.Dom.XmlDocument;"
    "$xml.LoadXml($env:A2T_TOAST_XML);"
    "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('" + POWERSHELL_APP_ID + "')"
    ".Show([Windows.UI.Notifications.ToastNotification]::new($xml))"
)


class AlertTracker:
    """Decides when to alert: once per (event, occurrence), inside the lead window."""

    def __init__(self):
        self._fired: set[tuple[str, datetime]] = set()

    def should_alert(self, rule_id: str, next_start: datetime, now: datetime, lead_minutes: int) -> bool:
        self._fired = {key for key in self._fired if key[1] > now}
        to_start = (next_start - now).total_seconds()
        key = (rule_id, next_start)
        if 0 < to_start <= lead_minutes * 60 and key not in self._fired:
            self._fired.add(key)
            return True
        return False


def beep():
    try:
        import winsound
        winsound.PlaySound("SystemNotification", winsound.SND_ALIAS | winsound.SND_ASYNC)
    except (ImportError, RuntimeError):
        pass


def toast(title: str, message: str):
    # Silent toast: the sound comes from beep(), which still plays when Windows
    # suppresses notifications during full-screen games.
    xml = ("<toast><visual><binding template='ToastGeneric'>"
           f"<text>{escape(title)}</text><text>{escape(message)}</text>"
           "</binding></visual><audio silent='true'/></toast>")
    try:
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", TOAST_SCRIPT],
            env=dict(os.environ, A2T_TOAST_XML=xml),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except OSError:
        pass
```

- [ ] **Step 4: Run, expect PASS** — `python -m unittest tests.test_notifier -v`
- [ ] **Step 5: Manual toast check** — `python -c "import notifier; notifier.beep(); notifier.toast('A2Timers', 'Prova')"` → sound + toast visible.
- [ ] **Step 6: Commit** — `feat: alert tracker, beep and toast`

### Task 4: `settings.py` (TDD)

**Files:** Create `tests/test_settings.py`, `settings.py`

- [ ] **Step 1: Failing tests** — `tests/test_settings.py`:

```python
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
```

- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement `settings.py`**

```python
"""Load and save user preferences (window position, alert lead time, per-event alerts)."""
import json
import os

DEFAULTS = {"x": 50, "y": 50, "lead_minutes": 5}


def load(path: str) -> dict:
    data = {**DEFAULTS, "alerts": {}}
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return data
    if not isinstance(raw, dict):
        return data
    for key in DEFAULTS:
        if isinstance(raw.get(key), int) and not isinstance(raw[key], bool):
            data[key] = raw[key]
    if isinstance(raw.get("alerts"), dict):
        data["alerts"] = {str(k): bool(v) for k, v in raw["alerts"].items()}
    data["lead_minutes"] = min(60, max(1, data["lead_minutes"]))
    return data


def save(path: str, data: dict):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def alert_enabled(data: dict, rule_id: str) -> bool:
    return data.get("alerts", {}).get(rule_id, True)
```

- [ ] **Step 4: Run, expect PASS** — `python -m unittest tests.test_settings -v`
- [ ] **Step 5: Commit** — `feat: persistent settings`

### Task 5: `overlay.py` + launchers

**Files:** Create `overlay.py`, `A2Timers.pyw`, `A2Timers.bat`

- [ ] **Step 1: Implement `overlay.py`** (full code in repo; responsibilities):
  - `Overlay(root, rules, prefs)`: borderless (`overrideredirect`), `-topmost`, `-alpha 0.85`, dark theme; header "AION 2 Timers" + ⚙ / ✕ label-buttons (their click handlers return `"break"` so they don't start a drag); one grid row per rule (icon+name left, monospace time right).
  - Drag: `<ButtonPress-1>`/`<B1-Motion>` on root; `<ButtonRelease-1>` saves prefs.
  - `_place_window()`: position from prefs, reset to (50, 50) if outside the primary screen.
  - `tick()` every second aligned to the wall clock: `schedule.state()` per rule → text/colour (active green "ATTIVO mm:ss", soon orange, idle default); if `settings.alert_enabled` and `tracker.should_alert(...)` → `alert()`. Re-assert `-topmost` every 5 ticks.
  - `alert(rule, start)`: `notifier.beep()` + `notifier.toast(f"{name} tra {n} min", f"Inizia alle {HH:MM local}")`.
  - `open_settings()`: single Toplevel with Spinbox (1–60) for lead, Checkbutton per rule, "Prova avviso" and "Salva" buttons.
  - `main()`: DPI awareness, load rules (error → messagebox + exit 1), load prefs, mainloop.
- [ ] **Step 2: `A2Timers.pyw`**: `import sys; from overlay import main; sys.exit(main())`
- [ ] **Step 3: `A2Timers.bat`**: `@echo off` / `start "" pythonw "%~dp0A2Timers.pyw"`
- [ ] **Step 4: Run full suite** — all PASS.
- [ ] **Step 5: Launch and screenshot** — overlay visible top-left, 4 rows, countdowns ticking, values match questlog; drag works; ⚙ dialog opens; "Prova avviso" plays sound + toast; restart keeps position.
- [ ] **Step 6: Commit** — `feat: Tk overlay and launchers`
