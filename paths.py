"""Where bundled assets and per-user data live (source checkout or PyInstaller build)."""
import os
import sys
from pathlib import Path


def app_dir() -> Path:
    """Read-only bundle: default events.json and assets/."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def data_dir() -> Path:
    """Per-user writable data: %APPDATA%\\A2Timers."""
    path = Path(os.environ.get("APPDATA") or Path.home()) / "A2Timers"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sounds_dir() -> Path:
    return app_dir() / "assets" / "sounds"


def updates_dir() -> Path:
    return data_dir() / "updates"


def settings_path() -> Path:
    return data_dir() / "settings.json"


def events_path() -> Path:
    """A user's own events.json overrides the bundled one."""
    user = data_dir() / "events.json"
    return user if user.exists() else app_dir() / "events.json"
