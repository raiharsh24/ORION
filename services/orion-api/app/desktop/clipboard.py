import os
import subprocess

# Global virtual clipboard buffer for fallback
_MEM_CLIPBOARD = ""

class DesktopClipboard:
    """
    Handles OS clipboard copy and paste operations.
    Integrates with 'xclip'/'xsel' on X11 and falls back to in-memory buffers in headless spaces.
    """
    def __init__(self) -> None:
        """Initialize the DesktopClipboard."""
        pass

    def _has_display(self) -> bool:
        return "DISPLAY" in os.environ or "WAYLAND_DISPLAY" in os.environ

    async def get_text(self) -> str:
        """
        Retrieves text from system clipboard.

        Returns:
            str: Clipboard string content.
        """
        global _MEM_CLIPBOARD
        if self._has_display():
            # Try using xclip
            try:
                proc = subprocess.Popen(
                    ["xclip", "-selection", "clipboard", "-o"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL
                )
                stdout, _ = proc.communicate()
                if proc.returncode == 0:
                    return stdout.decode("utf-8")
            except Exception:
                pass
            
            # Try using xsel
            try:
                proc = subprocess.Popen(
                    ["xsel", "-b", "-o"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL
                )
                stdout, _ = proc.communicate()
                if proc.returncode == 0:
                    return stdout.decode("utf-8")
            except Exception:
                pass

        return _MEM_CLIPBOARD

    async def set_text(self, text: str) -> bool:
        """
        Writes text to system clipboard.

        Args:
            text (str): String content to copy.

        Returns:
            bool: True if write succeeded.
        """
        global _MEM_CLIPBOARD
        _MEM_CLIPBOARD = text

        if self._has_display():
            # Try using xclip
            try:
                proc = subprocess.Popen(
                    ["xclip", "-selection", "clipboard"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                proc.communicate(input=text.encode("utf-8"))
                if proc.returncode == 0:
                    return True
            except Exception:
                pass
            
            # Try using xsel
            try:
                proc = subprocess.Popen(
                    ["xsel", "-b", "-i"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                proc.communicate(input=text.encode("utf-8"))
                if proc.returncode == 0:
                    return True
            except Exception:
                pass

        # Returns True because the in-memory fallback successfully captured the state
        return True
