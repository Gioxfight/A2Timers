"""Pure schedule math for AION 2 recurring events. All rules are defined in UTC."""
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

DAY_MINUTES = 1440
DEFAULT_SOUND = "builtin:bell"
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@dataclass(frozen=True)
class Rule:
    id: str
    names: dict  # language code -> display name
    icon: str
    anchor_minutes: int
    every_minutes: int
    duration_minutes: int
    weekdays: tuple[int, ...] | None = None  # Monday=0; None means every day
    sound: str = DEFAULT_SOUND


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
    weekdays = _parse_weekdays(rule_id, data["weekdays"]) if "weekdays" in data else None
    every = int(data.get("every_minutes", DAY_MINUTES)) if weekdays else int(data["every_minutes"])
    duration = int(data.get("duration_minutes", 0))
    if every <= 0 or DAY_MINUTES % every:
        raise ValueError(f"{rule_id}: every_minutes must divide 1440")
    if weekdays and every != DAY_MINUTES:
        raise ValueError(f"{rule_id}: weekdays requires every_minutes = 1440")
    if not 0 <= duration < every:
        raise ValueError(f"{rule_id}: duration_minutes must be in [0, every_minutes)")
    return Rule(id=str(data["id"]), names=_parse_names(rule_id, data.get("name")), icon=str(data.get("icon", "")),
                anchor_minutes=hours * 60 + minutes, every_minutes=every, duration_minutes=duration,
                weekdays=weekdays, sound=str(data.get("sound", DEFAULT_SOUND)))


def _parse_names(rule_id, name) -> dict:
    if isinstance(name, str) and name:
        return {"en": name}
    if isinstance(name, dict) and name and all(isinstance(v, str) and v for v in name.values()):
        return {str(k): v for k, v in name.items()}
    raise ValueError(f"{rule_id}: name must be a string or {{\"it\": ..., \"en\": ...}}")


def _parse_weekdays(rule_id, days) -> tuple[int, ...]:
    if not isinstance(days, list) or not days:
        raise ValueError(f"{rule_id}: weekdays must be a non-empty list like [\"mon\", \"thu\"]")
    try:
        return tuple(sorted({WEEKDAYS.index(str(day).lower()) for day in days}))
    except ValueError as exc:
        raise ValueError(f"{rule_id}: weekdays must use {', '.join(WEEKDAYS)}") from exc


def load_rules(path) -> list[Rule]:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, list) or not raw:
        raise ValueError("events.json must be a non-empty list")
    return [parse_rule(item) for item in raw]


def _today_anchor(rule: Rule, now: datetime) -> tuple[datetime, datetime]:
    now_utc = now.astimezone(timezone.utc)
    midnight = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    return now_utc, midnight + timedelta(minutes=rule.anchor_minutes)


def current_start(rule: Rule, now: datetime) -> datetime:
    """Latest occurrence start that is <= now (UTC)."""
    now_utc, anchor = _today_anchor(rule, now)
    if rule.weekdays:
        for back in range(8):
            candidate = anchor - timedelta(days=back)
            if candidate <= now_utc and candidate.weekday() in rule.weekdays:
                return candidate
    period = timedelta(minutes=rule.every_minutes)
    return anchor + math.floor((now_utc - anchor) / period) * period


def next_start(rule: Rule, now: datetime) -> datetime:
    """First occurrence start strictly after now (UTC)."""
    if rule.weekdays:
        now_utc, anchor = _today_anchor(rule, now)
        for ahead in range(8):
            candidate = anchor + timedelta(days=ahead)
            if candidate > now_utc and candidate.weekday() in rule.weekdays:
                return candidate
    return current_start(rule, now) + timedelta(minutes=rule.every_minutes)


def state(rule: Rule, now: datetime, lead_minutes: int) -> EventState:
    start = current_start(rule, now)
    upcoming = next_start(rule, now)
    end = start + timedelta(minutes=rule.duration_minutes)
    if now < end:
        return EventState("active", (end - now).total_seconds(), upcoming)
    to_next = (upcoming - now).total_seconds()
    return EventState("soon" if to_next <= lead_minutes * 60 else "idle", to_next, upcoming)


def format_seconds(seconds: float) -> str:
    total = max(0, math.ceil(seconds))
    days, total = divmod(total, 86400)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if days:
        return f"{days}g {hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"
