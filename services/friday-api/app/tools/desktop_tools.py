import time
from typing import Any, List, Optional
from loguru import logger
from app.tools.base_tool import BaseTool
from app.desktop.controller import DesktopController

class OpenApplicationTool(BaseTool):
    """
    Tool to open desktop applications.
    """
    def __init__(self, controller: DesktopController) -> None:
        self.controller = controller

    @property
    def name(self) -> str:
        return "desktop.open_application"

    @property
    def description(self) -> str:
        return "Launch an application by name or path with optional arguments. Args: app_name (str), args (List[str], optional)"

    async def execute(self, **kwargs) -> Any:
        start_time = time.perf_counter()
        app_name = kwargs.get("app_name")
        args = kwargs.get("args")
        
        logger.info(f"Executing tool {self.name} with app_name={app_name}, args={args}")
        
        if not app_name:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(f"Tool {self.name} failed: missing app_name | duration={duration:.2f}ms | scope=desktop_control")
            return {"success": False, "error": "Missing parameter 'app_name'"}

        result = await self.controller.open_application(app_name, args)
        duration = (time.perf_counter() - start_time) * 1000
        
        success = result.get("success", False)
        if success:
            logger.info(f"Tool {self.name} succeeded | duration={duration:.2f}ms | scope=desktop_control")
        else:
            logger.error(f"Tool {self.name} failed: {result.get('error')} | duration={duration:.2f}ms | scope=desktop_control")
            
        return result


class CloseApplicationTool(BaseTool):
    """
    Tool to close desktop applications.
    """
    def __init__(self, controller: DesktopController) -> None:
        self.controller = controller

    @property
    def name(self) -> str:
        return "desktop.close_application"

    @property
    def description(self) -> str:
        return "Terminate running applications matching a process name. Args: app_name (str)"

    async def execute(self, **kwargs) -> Any:
        start_time = time.perf_counter()
        app_name = kwargs.get("app_name")
        
        logger.info(f"Executing tool {self.name} with app_name={app_name}")
        
        if not app_name:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(f"Tool {self.name} failed: missing app_name | duration={duration:.2f}ms | scope=desktop_control")
            return {"success": False, "error": "Missing parameter 'app_name'"}

        result = await self.controller.close_application(app_name)
        duration = (time.perf_counter() - start_time) * 1000
        
        success = result.get("success", False)
        if success:
            logger.info(f"Tool {self.name} succeeded | duration={duration:.2f}ms | scope=desktop_control")
        else:
            logger.error(f"Tool {self.name} failed: {result.get('error')} | duration={duration:.2f}ms | scope=desktop_control")
            
        return result


class ScreenshotTool(BaseTool):
    """
    Tool to capture screenshots.
    """
    def __init__(self, controller: DesktopController) -> None:
        self.controller = controller

    @property
    def name(self) -> str:
        return "desktop.screenshot"

    @property
    def description(self) -> str:
        return "Capture a full screenshot and save to an optional path. Args: save_path (str, optional)"

    async def execute(self, **kwargs) -> Any:
        start_time = time.perf_counter()
        save_path = kwargs.get("save_path")
        
        logger.info(f"Executing tool {self.name} with save_path={save_path}")
        
        result_bytes = await self.controller.take_screenshot(save_path)
        duration = (time.perf_counter() - start_time) * 1000
        
        success = len(result_bytes) > 0
        if success:
            logger.info(f"Tool {self.name} succeeded | duration={duration:.2f}ms | scope=desktop_control")
            return {"success": True, "message": "Screenshot captured successfully.", "size_bytes": len(result_bytes)}
        else:
            logger.error(f"Tool {self.name} failed: empty result | duration={duration:.2f}ms | scope=desktop_control")
            return {"success": False, "error": "Failed to capture screenshot or permission denied."}


class ClipboardCopyTool(BaseTool):
    """
    Tool to copy text to system clipboard.
    """
    def __init__(self, controller: DesktopController) -> None:
        self.controller = controller

    @property
    def name(self) -> str:
        return "desktop.clipboard.copy"

    @property
    def description(self) -> str:
        return "Copy text to the system clipboard. Args: text (str)"

    async def execute(self, **kwargs) -> Any:
        start_time = time.perf_counter()
        text = kwargs.get("text")
        
        logger.info(f"Executing tool {self.name} with text length {len(text) if text else 0}")
        
        if text is None:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(f"Tool {self.name} failed: missing text | duration={duration:.2f}ms | scope=desktop_control")
            return {"success": False, "error": "Missing parameter 'text'"}

        result = await self.controller.copy_to_clipboard(text)
        duration = (time.perf_counter() - start_time) * 1000
        
        if result:
            logger.info(f"Tool {self.name} succeeded | duration={duration:.2f}ms | scope=desktop_control")
            return {"success": True, "message": "Successfully copied text to clipboard."}
        else:
            logger.error(f"Tool {self.name} failed: operation failed | duration={duration:.2f}ms | scope=desktop_control")
            return {"success": False, "error": "Failed to copy text or permission denied."}


class ClipboardReadTool(BaseTool):
    """
    Tool to read text from system clipboard.
    """
    def __init__(self, controller: DesktopController) -> None:
        self.controller = controller

    @property
    def name(self) -> str:
        return "desktop.clipboard.read"

    @property
    def description(self) -> str:
        return "Read text content from the system clipboard."

    async def execute(self, **kwargs) -> Any:
        start_time = time.perf_counter()
        
        logger.info(f"Executing tool {self.name}")
        
        result_text = await self.controller.read_clipboard()
        duration = (time.perf_counter() - start_time) * 1000
        
        logger.info(f"Tool {self.name} succeeded | duration={duration:.2f}ms | scope=desktop_control")
        return {"success": True, "text": result_text}


class NotificationsTool(BaseTool):
    """
    Tool to show desktop toast notifications.
    """
    def __init__(self, controller: DesktopController) -> None:
        self.controller = controller

    @property
    def name(self) -> str:
        return "desktop.notifications"

    @property
    def description(self) -> str:
        return "Show a desktop toast notification. Args: message (str), title (str, optional)"

    async def execute(self, **kwargs) -> Any:
        start_time = time.perf_counter()
        message = kwargs.get("message")
        title = kwargs.get("title")
        
        logger.info(f"Executing tool {self.name} with message={message}, title={title}")
        
        if not message:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(f"Tool {self.name} failed: missing message | duration={duration:.2f}ms | scope=desktop_control")
            return {"success": False, "error": "Missing parameter 'message'"}

        result = await self.controller.show_notification(message, title)
        duration = (time.perf_counter() - start_time) * 1000
        
        if result:
            logger.info(f"Tool {self.name} succeeded | duration={duration:.2f}ms | scope=desktop_control")
            return {"success": True, "message": "Notification triggered successfully."}
        else:
            logger.warning(f"Tool {self.name} returned False | duration={duration:.2f}ms | scope=desktop_control")
            return {"success": False, "error": "Failed to trigger notification (notify-send not available or display missing)."}
