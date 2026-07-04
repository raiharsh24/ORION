import os
import shutil
import subprocess
import tempfile
from typing import Optional, Tuple

# Valid 1x1 transparent PNG byte stream for headless spaces
DUMMY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00"
    b"\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
)

class ScreenshotHandler:
    """
    Handles screen capture operations.
    Integrates with 'gnome-screenshot' / 'screencapture' and falls back to dummy files.
    """
    def __init__(self) -> None:
        """Initialize the ScreenshotHandler."""
        self._has_maim = shutil.which("maim") is not None
        self._has_xdotool = shutil.which("xdotool") is not None
        self._has_gnome_screenshot = shutil.which("gnome-screenshot") is not None
        self._has_screencapture = shutil.which("screencapture") is not None
        self._has_import_cmd = shutil.which("import") is not None

    def _capture_to_file(self, target_path: str, cmd: list) -> bool:
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return proc.returncode == 0
        except Exception:
            return False

    def _read_file_bytes(self, path: str) -> bytes:
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    return f.read()
            except Exception:
                pass
        return b""

    async def capture_screen(self, save_path: Optional[str] = None) -> bytes:
        """
        Captures the current desktop screen.

        Args:
            save_path (Optional[str]): Target file path to write image.

        Returns:
            bytes: Raw image byte buffer.
        """
        target_path = save_path
        temp_path = None
        if not target_path:
            fd, temp_path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            target_path = temp_path

        success = False

        if self._has_gnome_screenshot:
            success = self._capture_to_file(target_path, ["gnome-screenshot", "-f", target_path])
        elif self._has_screencapture:
            success = self._capture_to_file(target_path, ["screencapture", "-x", target_path])
        elif self._has_maim:
            success = self._capture_to_file(target_path, ["maim", target_path])
        elif self._has_import_cmd:
            success = self._capture_to_file(target_path, ["import", "-window", "root", target_path])

        if not success:
            try:
                with open(target_path, "wb") as f:
                    f.write(DUMMY_PNG)
                success = True
            except Exception:
                pass

        img_bytes = self._read_file_bytes(target_path)

        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

        return img_bytes

    async def capture_active_window(self, save_path: Optional[str] = None) -> bytes:
        target_path = save_path
        temp_path = None
        if not target_path:
            fd, temp_path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            target_path = temp_path

        success = False

        if self._has_import_cmd:
            success = self._capture_to_file(target_path, ["import", "-window", "active", target_path])
        elif self._has_xdotool and self._has_maim:
            try:
                proc = subprocess.run(
                    ["xdotool", "getactivewindow"],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                )
                if proc.returncode == 0:
                    wid = proc.stdout.strip()
                    success = self._capture_to_file(target_path, ["maim", "-i", wid, target_path])
            except Exception:
                pass
        elif self._has_screencapture:
            success = self._capture_to_file(target_path, ["screencapture", "-w", target_path])

        if not success:
            return await self.capture_screen(save_path)

        img_bytes = self._read_file_bytes(target_path)

        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

        return img_bytes

    async def capture_region(self, x: int, y: int, width: int, height: int, save_path: Optional[str] = None) -> bytes:
        target_path = save_path
        temp_path = None
        if not target_path:
            fd, temp_path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            target_path = temp_path

        success = False

        if self._has_maim:
            geom = f"{width}x{height}+{x}+{y}"
            success = self._capture_to_file(target_path, ["maim", "-g", geom, target_path])
        elif self._has_import_cmd:
            geom = f"{width}x{height}+{x}+{y}"
            success = self._capture_to_file(target_path, ["import", "-window", "root", "-crop", geom, target_path])

        if not success:
            return await self.capture_screen(save_path)

        img_bytes = self._read_file_bytes(target_path)

        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

        return img_bytes
