from typing import List
import httpx
from app.tools.base import ToolParameter, ToolExample
from app.tools.base_tool import BaseTool

class BrowserTool(BaseTool):
    """
    Crawls web URL paths using HTTP client crawls to fetch text elements.
    """
    @property
    def name(self) -> str:
        return "browser"

    @property
    def description(self) -> str:
        return "Fetch the text content of a web page or URL."

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="url", type="string", description="The full URL to fetch (including https://)", required=True),
        ]

    @property
    def examples(self) -> List[ToolExample]:
        return [
            ToolExample(prompt="Fetch example.com", args={"url": "https://example.com"}, description="Fetch the homepage of example.com"),
            ToolExample(prompt="Read API docs", args={"url": "https://api.github.com"}, description="Fetch GitHub API root endpoint"),
        ]

    def requires_confirmation(self, **kwargs) -> bool:
        return False

    async def execute(self, **kwargs) -> str:
        url = kwargs.get("url")
        if not url:
            return "Error: Missing required parameter 'url'."

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.text[:2000]
                else:
                    return f"Error: Request failed with status code {response.status_code}"
        except Exception as e:
            return f"Error: Failed to fetch URL '{url}': {str(e)}"
