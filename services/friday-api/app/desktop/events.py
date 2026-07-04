from app.events.events import FridayEvent


class DesktopActionStarted(FridayEvent):
    def __init__(self, action: str, params: dict) -> None:
        super().__init__(topic="desktop.action.started", data={"action": action, "params": params})


class DesktopActionCompleted(FridayEvent):
    def __init__(self, action: str, success: bool, duration_ms: float) -> None:
        super().__init__(topic="desktop.action.completed", data={"action": action, "success": success, "duration_ms": duration_ms})


class DesktopActionFailed(FridayEvent):
    def __init__(self, action: str, error: str) -> None:
        super().__init__(topic="desktop.action.failed", data={"action": action, "error": error})


class DesktopScreenshotCaptured(FridayEvent):
    def __init__(self, source: str, size_bytes: int) -> None:
        super().__init__(topic="desktop.screenshot.captured", data={"source": source, "size_bytes": size_bytes})


class DesktopUIDetected(FridayEvent):
    def __init__(self, element_count: int) -> None:
        super().__init__(topic="desktop.ui.detected", data={"element_count": element_count})


class DesktopOCRExtracted(FridayEvent):
    def __init__(self, char_count: int) -> None:
        super().__init__(topic="desktop.ocr.completed", data={"char_count": char_count})


class DesktopOverlayUpdated(FridayEvent):
    def __init__(self, overlay_data: dict) -> None:
        super().__init__(topic="desktop.overlay.updated", data=overlay_data)
