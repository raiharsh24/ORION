import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone

from app.desktop_intelligence.context import (
    DesktopContext, WindowInfo, ClipboardState, ProcessInfo, ScreenInfo,
)
from app.desktop_intelligence.service import DesktopIntelligence
from app.desktop_intelligence.middleware import DesktopContextMiddleware
from app.desktop_intelligence.extractor import DesktopIntelligenceExtractor


class TestDesktopContextDataClasses:
    def test_window_info_to_dict(self):
        w = WindowInfo(id="123", title="Terminal", is_focused=True)
        d = w.to_dict()
        assert d["id"] == "123"
        assert d["title"] == "Terminal"
        assert d["is_focused"] is True

    def test_clipboard_state_to_dict(self):
        c = ClipboardState(text="hello world", has_image=False)
        d = c.to_dict()
        assert d["text"] == "hello world"
        assert d["text_truncated"] is False

    def test_clipboard_state_truncates_long_text(self):
        long_text = "x" * 500
        c = ClipboardState(text=long_text)
        d = c.to_dict()
        assert d["text_truncated"] is True
        assert len(d["text"]) == 200

    def test_screen_info_to_dict(self):
        s = ScreenInfo(width=1920, height=1080, ocr_text="Hello", ui_element_count=3)
        d = s.to_dict()
        assert d["width"] == 1920
        assert d["ocr_text"] == "Hello"
        assert d["ui_element_count"] == 3

    def test_desktop_context_to_dict(self):
        ctx = DesktopContext(
            windows=[WindowInfo(id="1", title="Code"), WindowInfo(id="2", title="Browser")],
            clipboard=ClipboardState(text="clip"),
            processes=[ProcessInfo(pid=100, name="python3", status="running")],
            screen=ScreenInfo(width=1920, height=1080),
            active_window_title="Code",
            active_window_id="1",
        )
        d = ctx.to_dict()
        assert d["active_window_title"] == "Code"
        assert len(d["windows"]) == 2
        assert len(d["processes"]) == 1
        assert d["process_count"] == 1
        assert d["clipboard"]["text"] == "clip"

    def test_desktop_context_to_text_summary(self):
        ctx = DesktopContext(
            windows=[WindowInfo(id="1", title="Terminal", is_focused=True)],
            clipboard=ClipboardState(text="copied text"),
            screen=ScreenInfo(ocr_text="Button: Submit", ui_element_count=5),
            active_window_title="Terminal",
            active_window_id="1",
        )
        summary = ctx.to_text_summary()
        assert "Terminal" in summary
        assert "1" in summary  # open windows count
        assert "copied text" in summary
        assert "Submit" in summary
        assert "5" in summary  # ui element count

    def test_empty_context_to_text_summary(self):
        ctx = DesktopContext()
        summary = ctx.to_text_summary()
        assert "unknown" in summary
        assert "0" in summary  # zero windows


@pytest.mark.anyio
class TestDesktopIntelligenceService:
    @pytest.fixture
    def mock_desktop(self):
        d = MagicMock()
        d.window_manager = MagicMock()
        d.window_manager.list_windows = AsyncMock(return_value={
            "success": True,
            "windows": [
                {"id": "1", "name": "Terminal", "focused": True},
                {"id": "2", "name": "Browser", "focused": False},
            ]
        })
        d.list_running_processes = AsyncMock(return_value=[
            {"pid": 100, "name": "python3", "status": "running"},
            {"pid": 200, "name": "node", "status": "sleeping"},
        ])
        d.read_clipboard = AsyncMock(return_value="clipboard text")
        d.take_screenshot = AsyncMock(return_value=b"x" * 500)
        return d

    @pytest.fixture
    def mock_vision(self):
        v = MagicMock()
        v.get_screen_context = AsyncMock(return_value={
            "ocr_text": "Button: Submit\nLabel: Name",
            "element_count": 3,
            "has_screenshot": True,
        })
        return v

    @pytest.fixture
    def service(self, mock_desktop, mock_vision):
        return DesktopIntelligence(
            desktop_controller=mock_desktop,
            vision_engine=mock_vision,
            event_bus=None,
        )

    async def test_get_window_context(self, service, mock_desktop):
        windows = await service.get_window_context()
        assert len(windows) == 2
        assert windows[0].id == "1"
        assert windows[0].title == "Terminal"
        assert windows[0].is_focused is True

    async def test_get_clipboard_context(self, service, mock_desktop):
        clip = await service.get_clipboard_context()
        assert clip.text == "clipboard text"
        assert clip.last_updated is not None

    async def test_get_process_context(self, service, mock_desktop):
        procs = await service.get_process_context()
        assert len(procs) == 2
        assert procs[0].pid == 100
        assert procs[0].name == "python3"

    async def test_get_screen_context_with_vision(self, service, mock_desktop, mock_vision):
        screen = await service.get_screen_context()
        assert screen.ocr_text == "Button: Submit\nLabel: Name"
        assert screen.ui_element_count == 3
        assert screen.screenshot_available is True

    async def test_get_screen_context_without_vision(self, mock_desktop):
        service = DesktopIntelligence(desktop_controller=mock_desktop, vision_engine=None)
        screen = await service.get_screen_context()
        assert screen.ocr_text == ""
        assert screen.screenshot_available is True

    async def test_get_full_context(self, service):
        ctx = await service.get_full_context()
        assert len(ctx.windows) == 2
        assert ctx.clipboard.text == "clipboard text"
        assert len(ctx.processes) == 2
        assert ctx.screen.ocr_text == "Button: Submit\nLabel: Name"
        assert ctx.active_window_title == "Terminal"
        assert ctx.active_window_id == "1"
        assert ctx.timestamp is not None

    async def test_get_text_summary(self, service):
        summary = await service.get_text_summary()
        assert "Terminal" in summary
        assert "clipboard text" in summary
        assert "Submit" in summary

    async def test_get_last_context(self, service):
        assert service.get_last_context() is None
        ctx = await service.get_full_context()
        assert service.get_last_context() is ctx

    async def test_health(self, service):
        h = service.health()
        assert h["status"] == "healthy"
        assert h["vision_available"] is True

    async def test_health_without_vision(self, mock_desktop):
        service = DesktopIntelligence(desktop_controller=mock_desktop, vision_engine=None)
        h = service.health()
        assert h["vision_available"] is False

    async def test_graceful_fallback_on_desktop_failure(self, mock_desktop):
        mock_desktop.window_manager.list_windows = AsyncMock(side_effect=RuntimeError("display error"))
        mock_desktop.list_running_processes = AsyncMock(side_effect=RuntimeError("proc error"))
        mock_desktop.read_clipboard = AsyncMock(side_effect=RuntimeError("clip error"))
        service = DesktopIntelligence(desktop_controller=mock_desktop, vision_engine=None)
        ctx = await service.get_full_context()
        assert len(ctx.windows) == 0
        assert ctx.clipboard.text == ""
        assert len(ctx.processes) == 0
        assert ctx.active_window_title == ""


@pytest.mark.anyio
class TestDesktopContextMiddleware:
    @pytest.fixture
    def mock_di(self):
        m = AsyncMock()
        ctx = DesktopContext(
            windows=[WindowInfo(id="1", title="Terminal", is_focused=True)],
            processes=[ProcessInfo(pid=100, name="python3")],
        )
        m.get_full_context = AsyncMock(return_value=ctx)
        return m

    async def test_before_planning_injects_context(self, mock_di):
        from app.execution.context import ExecutionContext
        mw = DesktopContextMiddleware(desktop_intelligence=mock_di)
        ctx = ExecutionContext(prompt="test")
        await mw.before_planning(ctx)
        assert "desktop_context" in ctx.metadata
        assert ctx.metadata["desktop_context_windows"] == 1
        assert ctx.metadata["desktop_context_processes"] == 1

    async def test_before_planning_skips_when_no_di(self):
        from app.execution.context import ExecutionContext
        mw = DesktopContextMiddleware(desktop_intelligence=None)
        ctx = ExecutionContext(prompt="test")
        await mw.before_planning(ctx)
        assert "desktop_context" not in ctx.metadata

    async def test_set_desktop_intelligence(self, mock_di):
        mw = DesktopContextMiddleware()
        assert mw._di is None
        mw.set_desktop_intelligence(mock_di)
        assert mw._di is mock_di


@pytest.mark.anyio
class TestDesktopIntelligenceExtractor:
    @pytest.fixture
    def mock_di(self):
        m = AsyncMock()
        ctx = DesktopContext(
            timestamp="2026-07-10T12:00:00",
            windows=[
                WindowInfo(id="1", title="Code Editor", is_focused=True),
                WindowInfo(id="2", title="Browser", is_focused=False),
            ],
            clipboard=ClipboardState(text="copied snippet"),
            processes=[
                ProcessInfo(pid=100, name="python3", status="running"),
                ProcessInfo(pid=200, name="node", status="sleeping"),
            ],
            screen=ScreenInfo(ocr_text="Hello World", ui_element_count=2),
            active_window_title="Code Editor",
            active_window_id="1",
        )
        m.get_full_context = AsyncMock(return_value=ctx)
        return m

    async def test_extract_returns_blocks(self, mock_di):
        extractor = DesktopIntelligenceExtractor(desktop_intelligence=mock_di)
        blocks = await extractor.extract("test request")
        assert len(blocks) >= 3
        sources = [b.source for b in blocks]
        assert "desktop_intelligence/windows" in sources
        assert "desktop_intelligence/clipboard" in sources
        assert "desktop_intelligence/processes" in sources

    async def test_extract_with_screen_context(self, mock_di):
        extractor = DesktopIntelligenceExtractor(desktop_intelligence=mock_di)
        blocks = await extractor.extract("test")
        sources = [b.source for b in blocks]
        assert "desktop_intelligence/screen" in sources

    async def test_extract_without_di_returns_fallback(self):
        extractor = DesktopIntelligenceExtractor(desktop_intelligence=None)
        blocks = await extractor.extract("test")
        assert len(blocks) == 1
        assert blocks[0].source == "desktop_intelligence/fallback"
        assert blocks[0].confidence == 0.3

    async def test_extract_without_clipboard(self, mock_di):
        mock_di.get_full_context.return_value.clipboard = ClipboardState(text="")
        extractor = DesktopIntelligenceExtractor(desktop_intelligence=mock_di)
        blocks = await extractor.extract("test")
        sources = [b.source for b in blocks]
        assert "desktop_intelligence/clipboard" not in sources

    async def test_extractor_aliases(self):
        extractor = DesktopIntelligenceExtractor()
        aliases = extractor.aliases
        assert "desktop_intelligence_extractor" in aliases
        assert "desktop_context_extractor" in aliases

    async def test_extractor_properties(self):
        extractor = DesktopIntelligenceExtractor()
        assert extractor.extractor_name == "desktop_intelligence_extractor"
        assert extractor.priority == 35
        assert "desktop_state" in extractor.supported_sources

    async def test_set_desktop_intelligence(self, mock_di):
        extractor = DesktopIntelligenceExtractor()
        assert extractor._di is None
        extractor.set_desktop_intelligence(mock_di)
        assert extractor._di is mock_di
