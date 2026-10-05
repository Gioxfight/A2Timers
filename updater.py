"""Find, download and verify new releases on GitHub. Network failures never raise."""
import hashlib
import json
import os
import re
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from version import __version__

API_URL = "https://api.github.com/repos/{repo}/releases/latest"
DOWNLOAD_PREFIX = "https://github.com/{repo}/releases/download/"
SETUP_PATTERN = re.compile(r"^A2Timers-Setup-[\w.]+\.exe$")
SUMS_NAME = "SHA256SUMS.txt"
TIMEOUT = 5
DOWNLOAD_TIMEOUT = 120


@dataclass(frozen=True)
class Release:
    tag: str
    page_url: str
    setup_url: str | None  # None when the release has no installer we trust
    sums_url: str | None


def parse_version(tag: str):
    try:
        return tuple(int(part) for part in tag.strip().lstrip("vV").split("."))
    except ValueError:
        return None


def is_newer(tag: str, current: str) -> bool:
    latest, installed = parse_version(tag), parse_version(current)
    return latest is not None and installed is not None and latest > installed


def _request(url: str, timeout: float):
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                                   "User-Agent": f"A2Timers/{__version__}"})
    return urllib.request.urlopen(request, timeout=timeout)


def _get_json(url: str, timeout: float):
    with _request(url, timeout) as response:
        return json.load(response)


def _get_bytes(url: str, timeout: float) -> bytes:
    with _request(url, timeout) as response:
        return response.read()


def check_for_update(repo: str, current: str, fetch=_get_json) -> Release | None:
    """The latest GitHub release if it is newer than `current`, else None."""
    if not repo:
        return None
    try:
        data = fetch(API_URL.format(repo=repo), TIMEOUT)
        tag, page_url = data["tag_name"], data["html_url"]
        assets = {a["name"]: a["browser_download_url"] for a in data.get("assets", [])}
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not is_newer(tag, current):
        return None
    prefix = DOWNLOAD_PREFIX.format(repo=repo)

    def trusted(name):
        url = assets.get(name)
        return url if isinstance(url, str) and url.startswith(prefix) else None

    setup_name = next((name for name in assets if SETUP_PATTERN.match(name)), None)
    return Release(tag, page_url, trusted(setup_name) if setup_name else None, trusted(SUMS_NAME))


def parse_sums(text: str, filename: str) -> str | None:
    """SHA-256 for `filename` from a `sha256sum`-style file."""
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == filename and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            return parts[0].lower()
    return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_update(release: Release, dest_dir: Path, fetch=_get_bytes) -> Path | None:
    """Download the installer into dest_dir and return it only if its SHA-256 matches."""
    if not release.setup_url or not release.sums_url:
        return None
    filename = release.setup_url.rsplit("/", 1)[-1]
    target = Path(dest_dir) / filename
    try:
        expected = parse_sums(fetch(release.sums_url, TIMEOUT * 6).decode("utf-8"), filename)
        if expected is None:
            return None
        if target.is_file() and _sha256(target) == expected:
            return target
        data = fetch(release.setup_url, DOWNLOAD_TIMEOUT)
        if hashlib.sha256(data).hexdigest() != expected:
            return None
        Path(dest_dir).mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".part")
        tmp.write_bytes(data)
        os.replace(tmp, target)
        return target
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def clean_downloads(dest_dir: Path, current: str):
    """Remove installers for versions that are not newer than the running one."""
    for path in Path(dest_dir).glob("A2Timers-Setup-*"):
        version = path.stem.removeprefix("A2Timers-Setup-")
        if not is_newer(version, current):
            try:
                path.unlink()
            except OSError:
                pass


def launch_installer(setup: Path):
    """Run the installer silently a moment after we exit; /AUTOUPDATE=1 makes it relaunch the app."""
    script = ("Start-Sleep -Seconds 2; Start-Process -FilePath $env:A2T_SETUP "
              "-ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/AUTOUPDATE=1'")
    subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
        env=dict(os.environ, A2T_SETUP=str(setup)),
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        # Not DETACHED_PROCESS: powershell.exe then exits without running the command.
        # A CREATE_NO_WINDOW child still outlives the app.
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
