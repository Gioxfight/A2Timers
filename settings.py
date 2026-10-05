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
