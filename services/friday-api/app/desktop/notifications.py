import shutil
import subprocess
from typing import Optional

class DesktopNotifier:
    """
    Manages user-facing desktop system toast notifications.
    Uses 'notify-send' on Linux, falling back gracefully to system loggers.
    """
    def __init__(self) -> None:
        """Initialize the DesktopNotifier."""
        pass

    async def notify(self, message: str, title: Optional[str] = None) -> bool:
        """
        Sends a desktop notification.

        Args:
            message (str): Body text of the notification.
            title (Optional[str]): Header title.

        Returns:
            bool: True if trigger succeeded.
        """
        executable = shutil.which("notify-send")
        if executable:
            try:
                cmd = [executable]
                if title:
                    cmd.append(title)
                cmd.append(message)
                proc = subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return proc.returncode == 0
            except Exception:
                pass
        return False
