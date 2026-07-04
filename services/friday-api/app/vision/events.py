from app.events.events import FridayEvent


class VisionCaptureStarted(FridayEvent):
    def __init__(self, source: str) -> None:
        super().__init__(topic="VisionCaptureStarted", data={"source": source})


class VisionCaptureCompleted(FridayEvent):
    def __init__(self, source: str, image_size: int, format: str) -> None:
        super().__init__(topic="VisionCaptureCompleted", data={
            "source": source, "image_size": image_size, "format": format,
        })


class VisionAnalysisStarted(FridayEvent):
    def __init__(self, source: str) -> None:
        super().__init__(topic="VisionAnalysisStarted", data={"source": source})


class VisionAnalysisCompleted(FridayEvent):
    def __init__(self, source: str, description: str, confidence: float) -> None:
        super().__init__(topic="VisionAnalysisCompleted", data={
            "source": source, "description": description, "confidence": confidence,
        })


class VisionOCRExtracted(FridayEvent):
    def __init__(self, source: str, text_length: int) -> None:
        super().__init__(topic="VisionOCRExtracted", data={
            "source": source, "text_length": text_length,
        })


class VisionUIElementsDetected(FridayEvent):
    def __init__(self, source: str, element_count: int) -> None:
        super().__init__(topic="VisionUIElementsDetected", data={
            "source": source, "element_count": element_count,
        })


class VisionContextBuilt(FridayEvent):
    def __init__(self, source: str, has_text: bool, element_count: int) -> None:
        super().__init__(topic="VisionContextBuilt", data={
            "source": source, "has_text": has_text, "element_count": element_count,
        })


class VisionMemoryStored(FridayEvent):
    def __init__(self, session_id: str, source: str) -> None:
        super().__init__(topic="VisionMemoryStored", data={
            "session_id": session_id, "source": source,
        })


class VisionProviderError(FridayEvent):
    def __init__(self, provider: str, error: str) -> None:
        super().__init__(topic="VisionProviderError", data={
            "provider": provider, "error": error,
        })
