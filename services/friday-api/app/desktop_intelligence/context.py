from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


@dataclass
class WindowInfo:
    id: str = ""
    title: str = ""
    is_focused: bool = False
    is_minimized: bool = False
    geometry: Optional[Dict[str, int]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "is_focused": self.is_focused,
            "is_minimized": self.is_minimized,
            "geometry": self.geometry or {},
        }


@dataclass
class ClipboardState:
    text: str = ""
    has_image: bool = False
    last_updated: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text[:200] if self.text else "",
            "text_truncated": len(self.text) > 200,
            "has_image": self.has_image,
            "last_updated": self.last_updated or "",
        }


@dataclass
class ProcessInfo:
    pid: int = 0
    name: str = ""
    status: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {"pid": self.pid, "name": self.name, "status": self.status}


@dataclass
class ScreenInfo:
    width: int = 0
    height: int = 0
    active_screen: int = 0
    screen_count: int = 1
    screenshot_available: bool = False
    ocr_text: str = ""
    ui_element_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "active_screen": self.active_screen,
            "screen_count": self.screen_count,
            "screenshot_available": self.screenshot_available,
            "ocr_text": self.ocr_text[:500] if self.ocr_text else "",
            "ocr_text_truncated": len(self.ocr_text) > 500,
            "ui_element_count": self.ui_element_count,
        }


@dataclass
class DesktopContext:
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    windows: List[WindowInfo] = field(default_factory=list)
    clipboard: ClipboardState = field(default_factory=ClipboardState)
    processes: List[ProcessInfo] = field(default_factory=list)
    screen: ScreenInfo = field(default_factory=ScreenInfo)
    active_window_title: str = ""
    active_window_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "active_window_title": self.active_window_title,
            "active_window_id": self.active_window_id,
            "windows": [w.to_dict() for w in self.windows],
            "clipboard": self.clipboard.to_dict(),
            "processes": [p.to_dict() for p in self.processes[:50]],
            "process_count": len(self.processes),
            "screen": self.screen.to_dict(),
        }

    def to_text_summary(self) -> str:
        parts = [
            f"Desktop State ({self.timestamp}):",
            f"  Active Window: {self.active_window_title or 'unknown'}",
            f"  Open Windows: {len(self.windows)}",
            f"  Running Processes: {len(self.processes)}",
        ]
        if self.clipboard.text:
            parts.append(f"  Clipboard: {self.clipboard.text[:100]}")
        if self.screen.ocr_text:
            parts.append(f"  Screen OCR: {self.screen.ocr_text[:200]}")
            if self.screen.ui_element_count:
                parts.append(f"  UI Elements: {self.screen.ui_element_count}")
        return "\n".join(parts)
