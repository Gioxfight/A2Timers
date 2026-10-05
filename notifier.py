"""Alert de-duplication (pure) plus Windows sound and toast output."""
import os
import subprocess
from datetime import datetime
from xml.sax.saxutils import escape

# AppUserModelID of Windows PowerShell: lets an unregistered script show toasts.
POWERSHELL_APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
TOAST_SCRIPT = (
    "$null = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime];"
    "$null = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime];"
    "$xml = New-Object Windows.Data.Xml.Dom.XmlDocument;"
    "$xml.LoadXml($env:A2T_TOAST_XML);"
    "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('" + POWERSHELL_APP_ID + "')"
    ".Show([Windows.UI.Notifications.ToastNotification]::new($xml))"
)


class AlertTracker:
    """Decides when to alert: once per (event, occurrence), inside the lead window."""

    def __init__(self):
        self._fired: set[tuple[str, datetime]] = set()

    def should_alert(self, rule_id: str, next_start: datetime, now: datetime, lead_minutes: int) -> bool:
        self._fired = {key for key in self._fired if key[1] > now}
        to_start = (next_start - now).total_seconds()
        key = (rule_id, next_start)
        if 0 < to_start <= lead_minutes * 60 and key not in self._fired:
            self._fired.add(key)
            return True
        return False


def beep():
    try:
        import winsound
        winsound.PlaySound("SystemNotification", winsound.SND_ALIAS | winsound.SND_ASYNC)
    except (ImportError, RuntimeError):
        pass


def toast(title: str, message: str):
    # Silent toast: the sound comes from beep(), which still plays when Windows
    # suppresses notifications during full-screen games.
    xml = ("<toast><visual><binding template='ToastGeneric'>"
           f"<text>{escape(title)}</text><text>{escape(message)}</text>"
           "</binding></visual><audio silent='true'/></toast>")
    try:
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", TOAST_SCRIPT],
            env=dict(os.environ, A2T_TOAST_XML=xml),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except OSError:
        pass
