"""Always-on-top Tk overlay showing AION 2 event countdowns."""
import math
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import messagebox

import notifier
import schedule
import settings

APP_DIR = Path(__file__).resolve().parent
EVENTS_PATH = APP_DIR / "events.json"
SETTINGS_PATH = APP_DIR / "settings.json"

BG = "#14161c"
FG = "#d8dce6"
MUTED = "#7a8194"
GREEN = "#4ade80"
ORANGE = "#fb923c"
FONT = ("Segoe UI", 10)
MONO = ("Consolas", 11, "bold")
TOPMOST_EVERY_TICKS = 5


class Overlay:
    def __init__(self, root, rules, prefs):
        self.root = root
        self.rules = rules
        self.prefs = prefs
        self.tracker = notifier.AlertTracker()
        self.ticks = 0
        self._drag = (0, 0)
        self._dialog = None

        root.title("A2Timers")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.85)
        root.configure(bg=BG)
        self._place_window()

        header = tk.Frame(root, bg=BG)
        header.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(header, text="AION 2 Timers", bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(side="left")
        self._button(header, "✕", self.close)
        self._button(header, "⚙", self.open_settings)

        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", padx=8, pady=(0, 8))
        self.time_labels = {}
        for row, rule in enumerate(rules):
            tk.Label(body, text=f"{rule.icon} {rule.name}", bg=BG, fg=FG, font=FONT, anchor="w").grid(
                row=row, column=0, sticky="w", padx=(0, 16))
            label = tk.Label(body, text="--:--", bg=BG, fg=FG, font=MONO, anchor="e", width=14)
            label.grid(row=row, column=1, sticky="e")
            self.time_labels[rule.id] = label

        root.bind("<ButtonPress-1>", self._start_drag)
        root.bind("<B1-Motion>", self._on_drag)
        root.bind("<ButtonRelease-1>", lambda _e: self._save_prefs())
        self.tick()

    def _button(self, parent, text, command):
        button = tk.Label(parent, text=text, bg=BG, fg=MUTED, font=("Segoe UI Symbol", 10), cursor="hand2")
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
            settings.save(str(SETTINGS_PATH), self.prefs)
        except OSError:
            pass

    def tick(self):
        now = datetime.now(timezone.utc)
        lead = self.prefs["lead_minutes"]
        for rule in self.rules:
            st = schedule.state(rule, now, lead)
            label = self.time_labels[rule.id]
            if st.kind == "active":
                label.configure(text=f"ATTIVO {schedule.format_seconds(st.seconds)}", fg=GREEN)
            else:
                label.configure(text=schedule.format_seconds(st.seconds), fg=ORANGE if st.kind == "soon" else FG)
            if settings.alert_enabled(self.prefs, rule.id) and self.tracker.should_alert(
                    rule.id, st.next_start, now, lead):
                self.alert(rule, st.next_start, now)
        self.ticks += 1
        if self.ticks % TOPMOST_EVERY_TICKS == 0:
            self.root.attributes("-topmost", True)
        self.root.after(1000 - now.microsecond // 1000, self.tick)

    def alert(self, rule, start, now):
        minutes = max(1, math.ceil((start - now).total_seconds() / 60))
        notifier.beep()
        notifier.toast(f"{rule.name} tra {minutes} min", f"Inizia alle {start.astimezone():%H:%M}")

    def test_alert(self):
        notifier.beep()
        notifier.toast("A2Timers", "Avviso di prova: suono e notifica funzionano")

    def open_settings(self):
        if self._dialog is not None and self._dialog.winfo_exists():
            self._dialog.lift()
            return
        win = self._dialog = tk.Toplevel(self.root)
        win.title("A2Timers - Impostazioni")
        win.configure(bg=BG, padx=12, pady=12)
        win.attributes("-topmost", True)
        win.resizable(False, False)

        tk.Label(win, text="Avviso minuti prima:", bg=BG, fg=FG, font=FONT).grid(row=0, column=0, sticky="w")
        lead = tk.IntVar(value=self.prefs["lead_minutes"])
        tk.Spinbox(win, from_=1, to=60, textvariable=lead, width=4).grid(row=0, column=1, sticky="w", padx=(8, 0))

        checks = {}
        for row, rule in enumerate(self.rules, start=1):
            var = tk.BooleanVar(value=settings.alert_enabled(self.prefs, rule.id))
            tk.Checkbutton(win, text=f"Avviso {rule.name}", variable=var, bg=BG, fg=FG, selectcolor="#2a2e38",
                           activebackground=BG, activeforeground=FG, font=FONT).grid(
                row=row, column=0, columnspan=2, sticky="w")
            checks[rule.id] = var

        def save():
            try:
                value = int(lead.get())
            except (tk.TclError, ValueError):
                value = self.prefs["lead_minutes"]
            self.prefs["lead_minutes"] = min(60, max(1, value))
            self.prefs["alerts"] = {rule_id: var.get() for rule_id, var in checks.items()}
            self._save_prefs()
            win.destroy()

        buttons = tk.Frame(win, bg=BG)
        buttons.grid(row=len(self.rules) + 1, column=0, columnspan=2, pady=(10, 0), sticky="e")
        tk.Button(buttons, text="Prova avviso", command=self.test_alert).pack(side="left", padx=(0, 6))
        tk.Button(buttons, text="Salva", command=save).pack(side="left")

    def close(self):
        self._save_prefs()
        self.root.destroy()


def main():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (ImportError, AttributeError, OSError):
        pass
    root = tk.Tk()
    try:
        rules = schedule.load_rules(EVENTS_PATH)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        root.withdraw()
        messagebox.showerror("A2Timers", f"events.json non valido:\n{exc}")
        root.destroy()
        return 1
    Overlay(root, rules, settings.load(str(SETTINGS_PATH)))
    root.mainloop()
    return 0
