# A2Timers — AION 2 event timer overlay

Date: 2026-10-05

## Goal
A lightweight always-on-top overlay for AION 2 (borderless window mode) showing live
countdowns for recurring events, plus a sound + Windows notification N minutes before
each event starts. No network access, no interaction with the game client.

## Events (v1)
All rules are defined in UTC and converted to the PC's local time zone (DST-aware).

| id      | Name               | Rule (UTC)                         | Active window |
|---------|--------------------|------------------------------------|---------------|
| shugo   | Shugo Festival     | every 1 h, anchor 00:00            | 10 min        |
| rift    | Spacetime Rift     | every 3 h, anchor 00:00            | 10 min (portal open) |
| kaira   | Watcher Kaira      | every 3 h, anchor 02:00            | 0 (spawn)     |
| reset   | Daily reset        | every 24 h, anchor 16:00           | 0             |

Source: questlog.gg (Shugo, Spacetime Rift, Boss Schedule, Server Resets pages), verified
2026-10-05 12:10 CEST: next Shugo 13:00, Rift 14:00, Kaira 13:00, Reset 18:00 local.

v1.1 (2026-10-05) adds weekday rules (`"weekdays": ["mon", "thu", "sat"]`, implies
`every_minutes` = 1440; weekday evaluated in UTC):

| id           | Name                | Rule (UTC)              | Active window |
|--------------|---------------------|-------------------------|---------------|
| siege        | Artifact Siege      | Mon/Thu/Sat 21:00       | 30 min        |
| siege_bosses | Siege Bosses        | Mon/Thu/Sat 21:30       | 30 min        |
| nahma        | Guardian Lord Nahma | Fri/Sun 19:00           | 30 min        |
| weekly_reset | Weekly reset        | Wed 16:00               | 0             |

Countdowns of a day or more display as `Ng HH:MM:SS`.

Out of scope: online sync.

## Rule format (`events.json`)
```json
{"id": "rift", "name": "Spacetime Rift", "icon": "🌀",
 "anchor_utc": "00:00", "every_minutes": 180, "duration_minutes": 10}
```
An event occurs at every `anchor + k * every_minutes` (k integer) measured from
midnight UTC. Constraint: `every_minutes` divides 1440.

## Behaviour
- Row state per event, computed from `now`:
  - **active**: `start <= now < start + duration` → green, "ATTIVO mm:ss" (time left).
  - **soon**: time to next start `<= lead_minutes` → orange.
  - **idle**: countdown `h:mm:ss` (or `mm:ss` under one hour).
- Alert: once per occurrence, when time to start crosses `lead_minutes` (default 5):
  `winsound` beep + Windows toast. Alert dedup key = `(event id, start timestamp)`.
  If the app starts inside the lead window, it alerts immediately once.
- Per-event alert on/off and `lead_minutes` editable from the ⚙ settings dialog.

## Window
- Tkinter, `overrideredirect`, `-topmost`, alpha 0.85, dark theme.
- Drag anywhere to move; position saved to `settings.json` on move/close.
- Header buttons: ⚙ settings, ✕ close. Refresh every 1 s.

## Modules
- `schedule.py` — pure: load rules, `next_start(rule, now)`, `current_start(rule, now)`,
  `state(rule, now, lead)`. No Tk imports. Fully unit-tested.
- `notifier.py` — `beep()`, `toast(title, msg)` (PowerShell + WinRT ToastNotificationManager,
  launched detached, failures swallowed and logged), `AlertTracker` (dedup logic, pure).
- `settings.py` — load/save `settings.json` with defaults; corrupt file → defaults.
- `overlay.py` — Tk UI, wires everything; entry point `main()`.
- `A2Timers.pyw` + `A2Timers.bat` — launch with `pythonw` (no console).

## Error handling
- Missing/invalid `events.json` → message box with the error, exit.
- Missing/corrupt `settings.json` → defaults, rewritten on next save.
- Toast failure → ignored (beep still plays).
- Window position off-screen (monitor removed) → reset to (50, 50).

## Testing
pytest-free `unittest` suite: rule arithmetic (boundaries, active windows, midnight wrap,
DST change in Europe/Rome), alert dedup, and a fixture check against the questlog
values observed on 2026-10-05.
