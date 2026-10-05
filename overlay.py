"""Always-on-top Tk overlay showing AION 2 event countdowns."""
import math
import threading
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from datetime import datetime, timezone
from tkinter import filedialog, messagebox, ttk

import i18n
import notifier
import paths
import schedule
import settings
import sounds
import updater
from version import GITHUB_REPO, __version__

BG = "#14161c"
FG = "#d8dce6"
MUTED = "#7a8194"
GREEN = "#4ade80"
ORANGE = "#fb923c"
# Base fonts at 100% size; the overlay scales them with prefs["scale"].
FONT_SPECS = {
    "name": ("Segoe UI", 10, "normal"),
    "time": ("Consolas", 11, "bold"),
    "small": ("Segoe UI", 8, "normal"),
    "symbol": ("Segoe UI Symbol", 10, "normal"),
}
TOPMOST_EVERY_TICKS = 5
MUTEX_NAME = "A2Timers.Overlay.Mutex"  # also used by the installer's AppMutex
ERROR_ALREADY_EXISTS = 183


class Overlay:
    def __init__(self, root, rules, prefs):
        self.root = root
        self.rules = rules
        self.prefs = prefs
        self.tracker = notifier.AlertTracker()
        self.detected_language = i18n.detect_language()
        self.ticks = 0
        self._drag = (0, 0)
        self._dialog = None
        self._container = None
        # Set by the update thread, displayed by tick(): Release, then the verified installer path.
        self.update_release = None
        self.update_installer = None
        self._update_state = None

        root.title("A2Timers")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg=BG)
        self.fonts = {key: tkfont.Font(root, family=family, size=size, weight=weight)
                      for key, (family, size, weight) in FONT_SPECS.items()}
        self._grip_start = None
        self.apply_scale(prefs["scale"])
        self.apply_opacity(prefs["opacity"])
        self._place_window()
        self.build()

        root.bind("<ButtonPress-1>", self._start_drag)
        root.bind("<B1-Motion>", self._on_drag)
        root.bind("<ButtonRelease-1>", lambda _e: self._save_prefs())
        if prefs["check_updates"]:
            threading.Thread(target=self._check_updates, daemon=True).start()
        self.tick()

    @property
    def lang(self):
        return i18n.resolve_language(self.prefs["language"], self.detected_language)

    def pref(self, rule):
        return settings.event_pref(self.prefs, rule.id, rule.sound)

    def build(self):
        """(Re)create all widgets; called on start and after settings change."""
        if self._container is not None:
            self._container.destroy()
        self._container = tk.Frame(self.root, bg=BG)
        self._container.pack(fill="both")

        header = tk.Frame(self._container, bg=BG)
        header.pack(fill="x", padx=8, pady=(6, 2))
        title = "AION 2 Timers" + ("" if self.prefs["region"] == "global" else f" · {self.prefs['region'].upper()}")
        tk.Label(header, text=title, bg=BG, fg=MUTED, font=self.fonts["small"]).pack(side="left")
        self._button(header, "✕", self.close)
        self._button(header, "⚙", self.open_settings)
        self.update_label = tk.Label(header, text="", bg=BG, fg=GREEN, font=self.fonts["small"], cursor="hand2")
        self._update_state = None

        body = tk.Frame(self._container, bg=BG)
        body.pack(fill="both", padx=8)
        self.time_labels = {}
        visible = [rule for rule in self.rules if self.pref(rule)["show"]]
        for row, rule in enumerate(visible):
            tk.Label(body, text=f"{rule.icon} {i18n.rule_name(rule, self.lang)}", bg=BG, fg=FG,
                     font=self.fonts["name"], anchor="w").grid(row=row, column=0, sticky="w", padx=(0, 16))
            label = tk.Label(body, text="--:--", bg=BG, fg=FG, font=self.fonts["time"], anchor="e", width=14)
            label.grid(row=row, column=1, sticky="e")
            self.time_labels[rule.id] = label

        footer = tk.Frame(self._container, bg=BG)
        footer.pack(fill="x", padx=(8, 2), pady=(0, 2))
        grip = tk.Label(footer, text="◢", bg=BG, fg=MUTED, font=self.fonts["small"], cursor="size_nw_se")
        grip.pack(side="right")
        # "break" keeps grip drags from also moving the window.
        grip.bind("<ButtonPress-1>", lambda e: (self._grip_press(e), "break")[1])
        grip.bind("<B1-Motion>", lambda e: (self._grip_drag(e), "break")[1])
        grip.bind("<ButtonRelease-1>", lambda _e: (self._save_prefs(), "break")[1])

    def apply_scale(self, scale):
        self.prefs["scale"] = settings.clamp_scale(scale)
        for key, (_family, size, _weight) in FONT_SPECS.items():
            self.fonts[key].configure(size=max(6, round(size * self.prefs["scale"])))

    def apply_opacity(self, opacity):
        self.prefs["opacity"] = settings.clamp_opacity(opacity)
        self.root.attributes("-alpha", self.prefs["opacity"])

    def _grip_press(self, event):
        self._grip_start = (event.x_root, self.root.winfo_width(), self.prefs["scale"])

    def _grip_drag(self, event):
        x0, width, scale = self._grip_start
        new_scale = settings.clamp_scale(scale * max(1, width + event.x_root - x0) / width)
        if new_scale != self.prefs["scale"]:
            self.apply_scale(new_scale)

    def _button(self, parent, text, command):
        button = tk.Label(parent, text=text, bg=BG, fg=MUTED, font=self.fonts["symbol"], cursor="hand2")
        button.pack(side="right", padx=(6, 0))
        # Returning "break" keeps the click from also starting a window drag.
        button.bind("<Button-1>", lambda _e: (command(), "break")[1])
        button.bind("<Enter>", lambda _e: button.configure(fg=FG))
        button.bind("<Leave>", lambda _e: button.configure(fg=MUTED))

    def _place_window(self):
        x, y = self.prefs["x"], self.prefs["y"]
        if not (0 <= x < self.root.winfo_screenwidth() - 40 and 0 <= y < self.root.winfo_screenheight() - 40):
            x, y = 50, 50
        self.root.geometry(f"+{x}+{y}")

    def _start_drag(self, event):
        self._drag = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _on_drag(self, event):
        self.root.geometry(f"+{event.x_root - self._drag[0]}+{event.y_root - self._drag[1]}")

    def _save_prefs(self):
        self.prefs["x"], self.prefs["y"] = self.root.winfo_x(), self.root.winfo_y()
        try:
            settings.save(paths.settings_path(), self.prefs)
        except OSError:
            pass

    def _check_updates(self):
        # Runs in a worker thread: only stores results, the Tk tick displays them.
        updater.clean_downloads(paths.updates_dir(), __version__)
        release = updater.check_for_update(GITHUB_REPO, __version__)
        self.update_release = release
        if release is not None:
            self.update_installer = updater.download_update(release, paths.updates_dir())

    def _show_update(self):
        release = self.update_release
        if self.update_installer is not None:
            state, text, action = "ready", "update_ready", self.install_update
        else:
            state, text, action = "available", "update_available", lambda: webbrowser.open(release.page_url)
        if state == self._update_state:
            return
        self.update_label.configure(text=i18n.t(self.lang, text, version=release.tag))
        self.update_label.pack(side="left", padx=(8, 0))
        self.update_label.bind("<Button-1>", lambda _e: (action(), "break")[1])
        self._update_state = state

    def install_update(self):
        """Close and let the verified installer update and relaunch the app."""
        self._save_prefs()
        _release_instance_lock()
        try:
            updater.launch_installer(self.update_installer)
        except OSError:
            webbrowser.open(self.update_release.page_url)
            return
        self.root.destroy()

    def tick(self):
        now = datetime.now(timezone.utc)
        lead = self.prefs["lead_minutes"]
        for rule in self.rules:
            st = schedule.state(rule, now, lead)
            label = self.time_labels.get(rule.id)
            if label is not None:
                if st.kind == "active":
                    label.configure(text=i18n.t(self.lang, "active", time=self.countdown(st.seconds)), fg=GREEN)
                else:
                    label.configure(text=self.countdown(st.seconds), fg=ORANGE if st.kind == "soon" else FG)
            if self.pref(rule)["alert"] and self.tracker.should_alert(rule.id, st.next_start, now, lead):
                self.alert(rule, st.next_start, now)
        if self.update_release is not None:
            self._show_update()
        self.ticks += 1
        if self.ticks % TOPMOST_EVERY_TICKS == 0:
            self.root.attributes("-topmost", True)
        self.root.after(1000 - now.microsecond // 1000, self.tick)

    def countdown(self, seconds):
        return schedule.format_seconds(seconds, i18n.t(self.lang, "day_unit"))

    def alert(self, rule, start, now):
        minutes = max(1, math.ceil((start - now).total_seconds() / 60))
        sounds.play(self.pref(rule)["sound"], paths.sounds_dir())
        notifier.toast(i18n.t(self.lang, "toast_title", name=i18n.rule_name(rule, self.lang), minutes=minutes),
                       i18n.t(self.lang, "toast_body", time=f"{start.astimezone():%H:%M}"))

    def open_settings(self):
        if self._dialog is not None and self._dialog.winfo_exists():
            self._dialog.lift()
            return
        SettingsDialog(self)

    def apply_settings(self, values):
        region_changed = values.get("region", self.prefs["region"]) != self.prefs["region"]
        self.prefs.update(values)
        if region_changed:
            try:
                self.rules = schedule.load_rules(paths.events_path(), self.prefs["region"])
            except (OSError, ValueError, KeyError, TypeError):
                pass  # keep the current schedule; the file was valid at startup
            self.tracker = notifier.AlertTracker()
        self.apply_scale(self.prefs["scale"])
        self.apply_opacity(self.prefs["opacity"])
        self._save_prefs()
        self.build()

    def close(self):
        self._save_prefs()
        self.root.destroy()


class SettingsDialog:
    LANGUAGE_LABELS = {"it": "Italiano", "en": "English"}

    def __init__(self, overlay):
        self.overlay = overlay
        self.lang = lang = overlay.lang
        prefs = overlay.prefs
        win = self.win = overlay._dialog = tk.Toplevel(overlay.root)
        win.title(i18n.t(lang, "settings_title"))
        win.attributes("-topmost", True)
        win.resizable(False, False)
        frame = ttk.Frame(win, padding=12)
        frame.pack(fill="both")

        head = ttk.Frame(frame)
        head.grid(row=0, column=0, sticky="w", pady=(0, 10))
        top = ttk.Frame(head)
        top.pack(anchor="w")
        ttk.Label(top, text=i18n.t(lang, "language")).pack(side="left")
        self.language_ids = list(settings.LANGUAGE_CHOICES)
        language_labels = [i18n.t(lang, "lang_auto")] + [self.LANGUAGE_LABELS[c] for c in self.language_ids[1:]]
        self.language = ttk.Combobox(top, values=language_labels, state="readonly", width=12)
        self.language.current(self.language_ids.index(prefs["language"]))
        self.language.pack(side="left", padx=(6, 18))
        ttk.Label(top, text=i18n.t(lang, "lead")).pack(side="left")
        self.lead = tk.IntVar(value=prefs["lead_minutes"])
        ttk.Spinbox(top, from_=1, to=60, textvariable=self.lead, width=4).pack(side="left", padx=(6, 0))

        where = ttk.Frame(head)
        where.pack(anchor="w", pady=(8, 0))
        ttk.Label(where, text=i18n.t(lang, "region")).pack(side="left")
        self.region_ids = list(settings.REGION_CHOICES)
        self.region = ttk.Combobox(where, values=[i18n.REGION_LABELS[r] for r in self.region_ids],
                                   state="readonly", width=26)
        self.region.current(self.region_ids.index(prefs["region"]))
        self.region.pack(side="left", padx=(6, 12))
        ttk.Label(where, text=i18n.local_time_label(lang), foreground="#6b7280").pack(side="left")

        look = ttk.Frame(frame)
        look.grid(row=1, column=0, sticky="w", pady=(0, 10))
        self.original_look = (prefs["scale"], prefs["opacity"])
        self.scale = self._slider(look, 0, i18n.t(lang, "size"), settings.SCALE_RANGE, prefs["scale"],
                                  overlay.apply_scale)
        self.opacity = self._slider(look, 1, i18n.t(lang, "opacity"), settings.OPACITY_RANGE, prefs["opacity"],
                                    overlay.apply_opacity)

        table = ttk.Frame(frame)
        table.grid(row=2, column=0, sticky="w")
        for col, key in enumerate(("col_event", "col_show", "col_alert", "col_sound")):
            ttk.Label(table, text=i18n.t(lang, key), font=("Segoe UI Semibold", 9)).grid(
                row=0, column=col, sticky="w", padx=(0, 12), pady=(0, 4))
        self.rows = {}
        for row, rule in enumerate(overlay.rules, start=1):
            pref = overlay.pref(rule)
            ttk.Label(table, text=f"{rule.icon} {i18n.rule_name(rule, lang)}").grid(
                row=row, column=0, sticky="w", padx=(0, 12), pady=1)
            show, alert = tk.BooleanVar(value=pref["show"]), tk.BooleanVar(value=pref["alert"])
            ttk.Checkbutton(table, variable=show).grid(row=row, column=1)
            ttk.Checkbutton(table, variable=alert).grid(row=row, column=2)
            sound = SoundPicker(table, win, lang, pref["sound"])
            sound.grid(row=row, column=3, sticky="w")
            self.rows[rule.id] = (show, alert, sound)

        self.check_updates = tk.BooleanVar(value=prefs["check_updates"])
        ttk.Checkbutton(frame, text=i18n.t(lang, "check_updates"), variable=self.check_updates).grid(
            row=3, column=0, sticky="w", pady=(10, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(buttons, text=i18n.t(lang, "test_alert"), command=self.test_notification).pack(side="left")
        ttk.Button(buttons, text=i18n.t(lang, "save"), command=self.save).pack(side="right")
        ttk.Button(buttons, text=i18n.t(lang, "cancel"), command=self.cancel).pack(side="right", padx=(0, 6))
        win.protocol("WM_DELETE_WINDOW", self.cancel)

    @staticmethod
    def _slider(parent, row, text, bounds, value, on_change):
        """Percent slider that previews live on the overlay."""
        var = tk.DoubleVar(value=value)
        percent = ttk.Label(parent, width=5)

        def changed(_value=None):
            percent.configure(text=f"{round(var.get() * 100)}%")
            on_change(var.get())

        ttk.Label(parent, text=text).grid(row=row, column=0, sticky="w", padx=(0, 8))
        ttk.Scale(parent, from_=bounds[0], to=bounds[1], variable=var, length=220, command=changed).grid(
            row=row, column=1, sticky="w")
        percent.grid(row=row, column=2, sticky="w", padx=(8, 0))
        changed()
        return var

    def cancel(self):
        self.overlay.apply_scale(self.original_look[0])
        self.overlay.apply_opacity(self.original_look[1])
        self.win.destroy()

    def test_notification(self):
        notifier.toast("A2Timers", i18n.t(self.lang, "test_toast_body"))

    def save(self):
        try:
            lead = int(self.lead.get())
        except (tk.TclError, ValueError):
            lead = self.overlay.prefs["lead_minutes"]
        values = {
            "language": self.language_ids[self.language.current()],
            "region": self.region_ids[self.region.current()],
            "lead_minutes": min(60, max(1, lead)),
            "check_updates": self.check_updates.get(),
            "scale": settings.clamp_scale(self.scale.get()),
            "opacity": settings.clamp_opacity(self.opacity.get()),
            "events": {},
        }
        for rule in self.overlay.rules:
            show, alert, sound = self.rows[rule.id]
            chosen = {"show": show.get(), "alert": alert.get(), "sound": sound.value}
            values["events"][rule.id] = settings.event_overrides(chosen, rule.sound)
        self.win.destroy()
        self.overlay.apply_settings(values)


class SoundPicker(ttk.Frame):
    """Sound combobox (catalog + user WAV + "Choose file…") with a ▶ preview button."""

    def __init__(self, parent, dialog, lang, sound_id):
        super().__init__(parent)
        self.dialog = dialog
        self.lang = lang
        self.value = sound_id
        self.combo = ttk.Combobox(self, state="readonly", width=24)
        self.combo.pack(side="left")
        self.combo.bind("<<ComboboxSelected>>", self._on_select)
        ttk.Button(self, text="▶", width=3, command=self.preview).pack(side="left", padx=(4, 0))
        self._refresh()

    def _refresh(self):
        self.ids = sounds.catalog()
        if self.value.startswith("file:"):
            self.ids.append(self.value)
        if self.value not in self.ids:
            self.value = self.ids[0]
        self.combo.configure(values=[i18n.sound_label(s, self.lang) for s in self.ids]
                             + [i18n.t(self.lang, "choose_file")])
        self.combo.current(self.ids.index(self.value))

    def _on_select(self, _event):
        index = self.combo.current()
        if index < len(self.ids):
            self.value = self.ids[index]
        else:
            path = filedialog.askopenfilename(parent=self.dialog,
                                              filetypes=[(i18n.t(self.lang, "wav_files"), "*.wav")])
            if path:
                self.value = f"file:{path}"
        self._refresh()

    def preview(self):
        sounds.play(self.value, paths.sounds_dir())


def _already_running() -> bool:
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # Keep the handle referenced for the whole process lifetime.
        _already_running.handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        return kernel32.GetLastError() == ERROR_ALREADY_EXISTS
    except (ImportError, AttributeError, OSError):
        return False


def _release_instance_lock():
    """Let the installer see that the app is no longer running."""
    handle = getattr(_already_running, "handle", None)
    if handle:
        try:
            import ctypes
            ctypes.windll.kernel32.CloseHandle(handle)
        except (ImportError, AttributeError, OSError):
            pass
        _already_running.handle = None


def main():
    if _already_running():
        return 0
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (ImportError, AttributeError, OSError):
        pass
    notifier.set_process_app_id()
    root = tk.Tk()
    icon = paths.app_dir() / "assets" / "icon.ico"
    if icon.exists():
        root.iconbitmap(default=str(icon))
    prefs = settings.load(paths.settings_path())
    try:
        rules = schedule.load_rules(paths.events_path(), prefs["region"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        root.withdraw()
        lang = i18n.resolve_language(prefs["language"])
        messagebox.showerror("A2Timers", i18n.t(lang, "events_error", error=exc))
        root.destroy()
        return 1
    Overlay(root, rules, prefs)
    root.mainloop()
    return 0
