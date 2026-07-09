from typing import Any, List, Optional
from loguru import logger

from app.extraction.base import IContextExtractor, ContextBlock


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class DesktopIntelligenceExtractor(IContextExtractor):
    extractor_name = "desktop_intelligence_extractor"
    supported_sources = [
        "desktop_state", "active_window", "clipboard", "screen",
        "process_list", "desktop_intelligence",
    ]
    priority = 35

    def __init__(self, desktop_intelligence: Any = None) -> None:
        self._di = desktop_intelligence

    def set_desktop_intelligence(self, di: Any) -> None:
        self._di = di

    @property
    def aliases(self):
        return [
            "desktop_intelligence_extractor",
            "desktop_context_extractor",
            "desktop_state_extractor_v2",
            "active_window_extractor_v2",
            "clipboard_extractor",
            "screen_context_extractor",
        ]

    async def extract(self, request: str) -> List[ContextBlock]:
        if not self._di:
            return [self._fallback_block()]

        try:
            ctx = await self._di.get_full_context()
            blocks = []

            window_text = (
                f"Active window: {ctx.active_window_title or 'unknown'}. "
                f"Open windows ({len(ctx.windows)}): "
            )
            for w in ctx.windows[:5]:
                window_text += f"{w.title}, "
            window_text = window_text.rstrip(", ") + "."

            blocks.append(
                ContextBlock(
                    source="desktop_intelligence/windows",
                    title="Desktop Intelligence — Windows",
                    content=window_text,
                    metadata={
                        "window_count": len(ctx.windows),
                        "active_window": ctx.active_window_title,
                    },
                    confidence=0.9,
                    importance=0.6,
                    estimated_tokens=_estimate_tokens(window_text),
                )
            )

            if ctx.clipboard.text:
                clip_text = f"Clipboard content: {ctx.clipboard.text[:200]}"
                blocks.append(
                    ContextBlock(
                        source="desktop_intelligence/clipboard",
                        title="Desktop Intelligence — Clipboard",
                        content=clip_text,
                        metadata={"has_text": True, "truncated": len(ctx.clipboard.text) > 200},
                        confidence=0.95,
                        importance=0.4,
                        estimated_tokens=_estimate_tokens(clip_text),
                    )
                )

            if ctx.processes:
                proc_text = f"Running processes ({len(ctx.processes)}): "
                by_status: dict = {}
                for p in ctx.processes:
                    by_status.setdefault(p.status, 0)
                    by_status[p.status] += 1
                proc_text += ", ".join(f"{k}: {v}" for k, v in sorted(by_status.items()))
                top = sorted(ctx.processes, key=lambda p: p.pid)[:5]
                proc_text += f". Top processes: {', '.join(p.name for p in top)}."

                blocks.append(
                    ContextBlock(
                        source="desktop_intelligence/processes",
                        title="Desktop Intelligence — Processes",
                        content=proc_text,
                        metadata={"process_count": len(ctx.processes)},
                        confidence=0.9,
                        importance=0.5,
                        estimated_tokens=_estimate_tokens(proc_text),
                    )
                )

            if ctx.screen.ocr_text:
                screen_text = f"Screen OCR: {ctx.screen.ocr_text[:300]}"
                if ctx.screen.ui_element_count:
                    screen_text += f" UI elements detected: {ctx.screen.ui_element_count}."
                blocks.append(
                    ContextBlock(
                        source="desktop_intelligence/screen",
                        title="Desktop Intelligence — Screen",
                        content=screen_text,
                        metadata={
                            "ocr_available": True,
                            "ui_element_count": ctx.screen.ui_element_count,
                        },
                        confidence=0.8,
                        importance=0.7,
                        estimated_tokens=_estimate_tokens(screen_text),
                    )
                )

            return blocks

        except Exception as e:
            logger.debug(f"DesktopIntelligenceExtractor failed: {e}")
            return [self._fallback_block()]

    def _fallback_block(self) -> ContextBlock:
        content = (
            "Desktop intelligence unavailable at this time. "
            "The DesktopIntelligence service may not be initialized."
        )
        return ContextBlock(
            source="desktop_intelligence/fallback",
            title="Desktop Intelligence — Unavailable",
            content=content,
            metadata={"available": False},
            confidence=0.3,
            importance=0.2,
            estimated_tokens=_estimate_tokens(content),
        )
