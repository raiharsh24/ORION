import os
import subprocess
from app.tools.base_tool import BaseTool

# Global in-memory storage for headless clipboard fallback
_MEM_CLIPBOARD = ""

class ClipboardTool(BaseTool):
    """
    Read or write to the system clipboard.
    Falls back gracefully to virtual memory in headless/CI servers.
    """
    @property
    def name(self) -> str:
        return "clipboard"

    @property
    def description(self) -> str:
        return "Read or write to the system clipboard. Args: op (copy/paste), text (str, optional)"

    def requires_confirmation(self, **kwargs) -> bool:
        return False

    def _has_display(self) -> bool:
        # Check if DISPLAY env var is set (for X11/Linux) or WAYLAND_DISPLAY (for Wayland)
        return "DISPLAY" in os.environ or "WAYLAND_DISPLAY" in os.environ

    async def execute(self, **kwargs) -> str:
        global _MEM_CLIPBOARD
        op = kwargs.get("op")
        text = kwargs.get("text", "")

        if not op:
            return "Error: Missing required parameter 'op'."

        if op not in ("copy", "paste"):
            return f"Error: Unsupported operation '{op}'."

        has_display = self._has_display()

        if op == "copy":
            if not text:
                return "Error: Missing parameter 'text' for copy operation."
            
            if has_display:
                # Try using xclip
                try:
                    proc = subprocess.Popen(
                        ["xclip", "-selection", "clipboard"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    proc.communicate(input=text.encode("utf-8"))
                    _MEM_CLIPBOARD = text
                    return "Copied text to clipboard."
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
                    _MEM_CLIPBOARD = text
                    return "Copied text to clipboard."
                except Exception:
                    pass

            # Headless or tool fallback
            _MEM_CLIPBOARD = text
            return "Copied text to clipboard (Headless/Virtual clipboard fallback)."

        elif op == "paste":
            if has_display:
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

            # Headless or tool fallback
            return _MEM_CLIPBOARD
