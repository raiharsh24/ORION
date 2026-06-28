import os
import shutil
import subprocess
import tempfile
from typing import Optional

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
        pass

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

        # Try gnome-screenshot (Linux)
        if shutil.which("gnome-screenshot"):
            try:
                proc = subprocess.run(
                    ["gnome-screenshot", "-f", target_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                success = proc.returncode == 0
            except Exception:
                pass
        # Try screencapture (macOS)
        elif shutil.which("screencapture"):
            try:
                proc = subprocess.run(
                    ["screencapture", "-x", target_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                success = proc.returncode == 0
            except Exception:
                pass
        # Try maim (Linux fallback)
        elif shutil.which("maim"):
            try:
                proc = subprocess.run(
                    ["maim", target_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                success = proc.returncode == 0
            except Exception:
                pass

        if not success:
            # Fallback to writing transparent PNG stub
            try:
                with open(target_path, "wb") as f:
                    f.write(DUMMY_PNG)
                success = True
            except Exception:
                pass

        img_bytes = b""
        if success and os.path.exists(target_path):
            try:
                with open(target_path, "rb") as f:
                    img_bytes = f.read()
            except Exception:
                pass

        # Cleanup temporary files
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

        return img_bytes
