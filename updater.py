"""Check GitHub Releases for a newer version. Never raises."""
import json
import urllib.request

from version import __version__

API_URL = "https://api.github.com/repos/{repo}/releases/latest"
TIMEOUT = 5


def parse_version(tag: str):
    try:
        return tuple(int(part) for part in tag.strip().lstrip("vV").split("."))
    except ValueError:
        return None


def is_newer(tag: str, current: str) -> bool:
    latest, installed = parse_version(tag), parse_version(current)
    return latest is not None and installed is not None and latest > installed


def _get_json(url: str, timeout: float):
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                                   "User-Agent": f"A2Timers/{__version__}"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def check_for_update(repo: str, current: str, fetch=_get_json):
    """(tag, release page url) if GitHub has a newer release, else None."""
    if not repo:
        return None
    try:
        release = fetch(API_URL.format(repo=repo), TIMEOUT)
        tag, url = release["tag_name"], release["html_url"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return (tag, url) if is_newer(tag, current) else None
