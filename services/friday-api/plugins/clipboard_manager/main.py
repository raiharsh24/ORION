from app.plugin_sdk.base_plugin import BasePlugin


class ClipboardPlugin(BasePlugin):
    id = "clipboard_manager"
    name = "Clipboard Manager"
    version = "1.0.0"

    async def on_load(self) -> None:
        self.log_info("Clipboard Manager loaded")

    def get_manifest(self):
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
        }

    def get_requested_permissions(self):
        return ["desktop.access"]

    def copy(self, text: str) -> bool:
        try:
            import pyperclip
            pyperclip.copy(text)
            self.log_info(f"Copied {len(text)} chars to clipboard")
            return True
        except ImportError:
            self.log_warning("pyperclip not installed, using fallback")
            return False
        except Exception as e:
            self.log_error(f"Clipboard copy failed: {e}")
            return False

    def paste(self) -> str:
        try:
            import pyperclip
            text = pyperclip.paste()
            self.log_info(f"Pasted {len(text)} chars from clipboard")
            return text
        except ImportError:
            self.log_warning("pyperclip not installed")
            return ""
        except Exception as e:
            self.log_error(f"Clipboard paste failed: {e}")
            return ""
