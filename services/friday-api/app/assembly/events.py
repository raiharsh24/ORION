from typing import Dict, Any, List, Optional
from app.events.events import FridayEvent


class PromptAssembled(FridayEvent):
    def __init__(self, prompt_tokens: int, provider: str = "",
                 template_name: str = "",
                 section_count: int = 0,
                 omitted_sections: Optional[List[str]] = None) -> None:
        super().__init__(topic="PromptAssembled", data={
            "prompt_tokens": prompt_tokens,
            "provider": provider,
            "template_name": template_name,
            "section_count": section_count,
            "omitted_sections": omitted_sections or [],
        })
