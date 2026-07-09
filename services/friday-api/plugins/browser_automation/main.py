from app.plugin_sdk.base_plugin import BasePlugin


class BrowserAutomationPlugin(BasePlugin):
    id = "browser_automation"
    name = "Browser Automation"
    version = "1.0.0"

    async def on_load(self) -> None:
        self.log_info("Browser Automation loaded")

    def get_manifest(self):
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
        }

    def get_requested_permissions(self):
        return ["network", "browser.control"]

    async def navigate(self, url: str) -> dict:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return {"error": "playwright not installed", "url": url}

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(url, timeout=30000)
                title = await page.title()
                content = await page.content()
                result = {
                    "url": url,
                    "title": title,
                    "content_length": len(content),
                }
                self.log_info(f"Navigated to {url}: {title}")
                return result
            except Exception as e:
                self.log_error(f"Navigation failed: {e}")
                return {"error": str(e), "url": url}
            finally:
                await browser.close()

    async def extract_text(self, url: str) -> dict:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return {"error": "playwright not installed", "url": url}

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(url, timeout=30000)
                text = await page.inner_text("body")
                result = {
                    "url": url,
                    "text": text[:5000],
                    "text_length": len(text),
                }
                self.log_info(f"Extracted {len(text)} chars from {url}")
                return result
            except Exception as e:
                return {"error": str(e), "url": url}
            finally:
                await browser.close()
