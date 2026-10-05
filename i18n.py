"""Italian / English UI strings."""
from pathlib import PureWindowsPath

LANGUAGES = ("it", "en")

STRINGS = {
    "it": {
        "active": "ATTIVO {time}",
        "day_unit": "g",
        "toast_title": "{name} tra {minutes} min",
        "toast_body": "Inizia alle {time}",
        "test_toast_body": "Avviso di prova: suono e notifica funzionano",
        "update_available": "⬆ {version} disponibile",
        "settings_title": "A2Timers - Impostazioni",
        "language": "Lingua:",
        "lang_auto": "Automatica",
        "lead": "Avviso minuti prima:",
        "size": "Grandezza:",
        "opacity": "Opacità:",
        "col_event": "Evento",
        "col_show": "Mostra",
        "col_alert": "Avviso",
        "col_sound": "Suono",
        "check_updates": "Controlla aggiornamenti all'avvio",
        "test_alert": "Prova notifica",
        "save": "Salva",
        "cancel": "Annulla",
        "choose_file": "Scegli file…",
        "wav_files": "File audio WAV",
        "events_error": "events.json non valido:\n{error}",
        "sound.builtin:harp": "Arpa celeste",
        "sound.builtin:crystal": "Cristallo",
        "sound.builtin:choir": "Coro etereo",
        "sound.builtin:temple": "Campana del tempio",
        "sound.builtin:warhorn": "Corno di guerra",
        "sound.builtin:fanfare": "Fanfara",
        "sound.builtin:bell": "Campanello",
        "sound.builtin:gong": "Gong",
        "sound.builtin:double": "Doppio beep",
        "sound.builtin:horn": "Corno",
        "sound.system:SystemNotification": "Windows: Notifica",
        "sound.system:SystemAsterisk": "Windows: Asterisco",
        "sound.system:SystemExclamation": "Windows: Esclamazione",
        "sound.system:SystemHand": "Windows: Errore",
        "sound.none": "Nessun suono",
        "sound.file": "File: {name}",
    },
    "en": {
        "active": "ACTIVE {time}",
        "day_unit": "d",
        "toast_title": "{name} in {minutes} min",
        "toast_body": "Starts at {time}",
        "test_toast_body": "Test alert: sound and notification work",
        "update_available": "⬆ {version} available",
        "settings_title": "A2Timers - Settings",
        "language": "Language:",
        "lang_auto": "Automatic",
        "lead": "Alert minutes before:",
        "size": "Size:",
        "opacity": "Opacity:",
        "col_event": "Event",
        "col_show": "Show",
        "col_alert": "Alert",
        "col_sound": "Sound",
        "check_updates": "Check for updates on start",
        "test_alert": "Test notification",
        "save": "Save",
        "cancel": "Cancel",
        "choose_file": "Choose file…",
        "wav_files": "WAV audio files",
        "events_error": "Invalid events.json:\n{error}",
        "sound.builtin:harp": "Celestial harp",
        "sound.builtin:crystal": "Crystal",
        "sound.builtin:choir": "Ethereal choir",
        "sound.builtin:temple": "Temple bell",
        "sound.builtin:warhorn": "War horn",
        "sound.builtin:fanfare": "Fanfare",
        "sound.builtin:bell": "Bell",
        "sound.builtin:gong": "Gong",
        "sound.builtin:double": "Double beep",
        "sound.builtin:horn": "Horn",
        "sound.system:SystemNotification": "Windows: Notification",
        "sound.system:SystemAsterisk": "Windows: Asterisk",
        "sound.system:SystemExclamation": "Windows: Exclamation",
        "sound.system:SystemHand": "Windows: Critical stop",
        "sound.none": "No sound",
        "sound.file": "File: {name}",
    },
}


def t(lang: str, key: str, **fmt) -> str:
    table = STRINGS.get(lang, STRINGS["en"])
    text = table.get(key, STRINGS["en"].get(key, key))
    return text.format(**fmt) if fmt else text


def detect_language() -> str:
    """Italian if the Windows UI language is Italian, else English."""
    try:
        import ctypes
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return "it" if lang_id & 0x3FF == 0x10 else "en"
    except (ImportError, AttributeError, OSError):
        return "en"


def resolve_language(setting: str, detected: str | None = None) -> str:
    if setting in LANGUAGES:
        return setting
    return detected if detected is not None else detect_language()


def rule_name(rule, lang: str) -> str:
    names = rule.names
    return names.get(lang) or names.get("en") or next(iter(names.values()))


def sound_label(sound_id: str, lang: str) -> str:
    if sound_id.startswith("file:"):
        return t(lang, "sound.file", name=PureWindowsPath(sound_id[5:]).name)
    return t(lang, f"sound.{sound_id}")
