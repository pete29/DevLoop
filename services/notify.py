"""A desktop notification, when a background run ends.

A plan runs in a worker now, so nobody has to watch the page
-- and nothing said when it was done. On Windows this shows a
toast through PowerShell and the system's own notification
API: no package to install. Elsewhere it does nothing.

The title and the message reach the script as environment
variables, never as part of its text, so a plan named with
quotes or a semicolon cannot become a command.
"""

import os
import subprocess

from config.settings import Settings

# PowerShell's own application id: a toast needs one that is
# registered, and this one always is.
APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"

SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml('<toast><visual><binding template="ToastGeneric"><text></text><text></text></binding></visual></toast>')
$texts = $xml.GetElementsByTagName('text')
$texts.Item(0).AppendChild($xml.CreateTextNode($env:DEVLOOP_TITLE)) | Out-Null
$texts.Item(1).AppendChild($xml.CreateTextNode($env:DEVLOOP_MESSAGE)) | Out-Null
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:DEVLOOP_APP_ID).Show($toast)
"""


def command(title: str, message: str) -> tuple[list[str], dict]:
    """The PowerShell call and its environment, for a toast."""

    return (
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            SCRIPT,
        ],
        {
            **os.environ,
            "DEVLOOP_TITLE": title[:120],
            "DEVLOOP_MESSAGE": message[:400],
            "DEVLOOP_APP_ID": APP_ID,
        },
    )


def notify(title: str, message: str) -> bool:
    """Shows a notification; True when one was sent.

    Never raises: a notification that cannot be shown must
    not turn a finished run into a failed one.
    """

    if not Settings.NOTIFY_ON_RUN_END or os.name != "nt":
        return False

    arguments, environment = command(title, message)

    try:
        subprocess.Popen(
            arguments,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    except OSError as error:
        print(f"no notification: {error}")
        return False

    return True
