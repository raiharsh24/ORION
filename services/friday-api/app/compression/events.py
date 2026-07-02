from typing import Dict, Any, List, Optional
from app.events.events import FridayEvent


class ContextCompressed(FridayEvent):
    def __init__(self, input_tokens: int, output_tokens: int,
                 saved_tokens: int, compression_ratio: float,
                 skipped_blocks: int = 0,
                 policy: str = "standard") -> None:
        super().__init__(topic="ContextCompressed", data={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "saved_tokens": saved_tokens,
            "compression_ratio": compression_ratio,
            "skipped_blocks": skipped_blocks,
            "policy": policy,
        })
