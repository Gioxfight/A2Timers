"""Load and save user preferences (window, language, updates, per-event show/alert/sound)."""
import json
import os

DEFAULTS = {"x": 50, "y": 50, "lead_minutes": 5, "language": "auto", "check_updates": True,
            "scale": 1.0, "opacity": 0.85}
LANGUAGE_CHOICES = ("auto", "it", "en")
SCALE_RANGE = (0.6, 2.0)
OPACITY_RANGE = (0.2, 1.0)
EVENT_FIELDS = {"show": bool, "alert": bool, "sound": str}


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def clamp_scale(value: float) -> float:
    return round(min(SCALE_RANGE[1], max(SCALE_RANGE[0], value)), 2)


def clamp_opacity(value: float) -> float:
    return round(min(OPACITY_RANGE[1], max(OPACITY_RANGE[0], value)), 2)


def _clean_event(raw) -> dict | None:
    if not isinstance(raw, dict):
        return None
    return {key: raw[key] for key, kind in EVENT_FIELDS.items() if isinstance(raw.get(key), kind)}


def load(path) -> dict:
    data = {**DEFAULTS, "events": {}}
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return data
    if not isinstance(raw, dict):
        return data
    for key in ("x", "y", "lead_minutes"):
        if _is_int(raw.get(key)):
            data[key] = raw[key]
    data["lead_minutes"] = min(60, max(1, data["lead_minutes"]))
    if raw.get("language") in LANGUAGE_CHOICES:
        data["language"] = raw["language"]
    if isinstance(raw.get("check_updates"), bool):
        data["check_updates"] = raw["check_updates"]
    if _is_number(raw.get("scale")):
        data["scale"] = clamp_scale(raw["scale"])
    if _is_number(raw.get("opacity")):
        data["opacity"] = clamp_opacity(raw["opacity"])
    if isinstance(raw.get("events"), dict):
        for rule_id, event in raw["events"].items():
            cleaned = _clean_event(event)
            if cleaned is not None:
                data["events"][str(rule_id)] = cleaned
    if isinstance(raw.get("alerts"), dict):  # v1 format: {"rule_id": bool}
        for rule_id, enabled in raw["alerts"].items():
            data["events"].setdefault(str(rule_id), {}).setdefault("alert", bool(enabled))
    return data


def save(path, data: dict):
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def event_pref(data: dict, rule_id: str, default_sound: str) -> dict:
    """Effective show/alert/sound for one event."""
    return {"show": True, "alert": True, "sound": default_sound, **data.get("events", {}).get(rule_id, {})}
