"""Alert sound catalog, id resolution and playback (WAV only, via winsound)."""
from pathlib import Path

# Fantasy set first, then the simple originals.
BUILTIN = ("harp", "crystal", "choir", "temple", "warhorn", "fanfare", "bell", "gong", "double", "horn")
SYSTEM = ("SystemNotification", "SystemAsterisk", "SystemExclamation", "SystemHand")
FALLBACK = ("alias", "SystemNotification")


def catalog() -> list[str]:
    """Selectable sound ids, in menu order (user files are added separately)."""
    return [f"builtin:{name}" for name in BUILTIN] + [f"system:{name}" for name in SYSTEM] + ["none"]


def resolve(sound_id: str, assets_dir: Path):
    """Map a sound id to ("file", path) / ("alias", name), or None for silence."""
    if sound_id == "none":
        return None
    kind, _, value = sound_id.partition(":")
    if kind == "builtin" and value in BUILTIN:
        path = Path(assets_dir) / f"{value}.wav"
        return ("file", path) if path.is_file() else FALLBACK
    if kind == "system" and value in SYSTEM:
        return ("alias", value)
    if kind == "file" and value:
        path = Path(value)
        return ("file", path) if path.suffix.lower() == ".wav" and path.is_file() else FALLBACK
    return FALLBACK


def play(sound_id: str, assets_dir: Path):
    target = resolve(sound_id, assets_dir)
    if target is None:
        return
    try:
        import winsound
        kind, value = target
        flag = winsound.SND_FILENAME if kind == "file" else winsound.SND_ALIAS
        winsound.PlaySound(str(value), flag | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except (ImportError, RuntimeError):
        pass
