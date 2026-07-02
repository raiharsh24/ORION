from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.compression.base import CompressedBlock, CompressionReport
from app.context.base import StrategyConfig
from app.budget.base import BudgetReport


SECTION_ORDER = [
    "system_prompt",
    "conversation_history",
    "long_term_memory",
    "retrieved_knowledge",
    "workflow_state",
    "desktop_context",
    "tool_context",
    "user_query",
]

SECTION_NAMES = set(SECTION_ORDER)


@dataclass
class PromptSection:
    name: str
    content: str
    tokens: int = 0
    is_truncated: bool = False
    is_omitted: bool = False


@dataclass
class PromptFormat:
    provider: str = "gemini"
    role_system: str = "system"
    role_user: str = "user"
    role_assistant: str = "assistant"
    section_separator: str = "\n\n"
    use_xml_wrappers: bool = False
    use_json_messages: bool = True
    template_name: str = "default"


GEMINI_FORMAT = PromptFormat(
    provider="gemini",
    role_system="system",
    role_user="user",
    role_assistant="model",
    use_json_messages=True,
    template_name="gemini",
)

OPENAI_FORMAT = PromptFormat(
    provider="openai",
    role_system="system",
    role_user="user",
    role_assistant="assistant",
    use_json_messages=True,
    template_name="openai",
)

ANTHROPIC_FORMAT = PromptFormat(
    provider="anthropic",
    role_system="system",
    role_user="user",
    role_assistant="assistant",
    use_json_messages=True,
    template_name="anthropic",
)

LOCAL_FORMAT = PromptFormat(
    provider="local",
    role_system="system",
    role_user="user",
    role_assistant="assistant",
    use_json_messages=False,
    use_xml_wrappers=False,
    section_separator="\n",
    template_name="local",
)

PROVIDER_FORMATS: Dict[str, PromptFormat] = {
    "gemini": GEMINI_FORMAT,
    "openai": OPENAI_FORMAT,
    "anthropic": ANTHROPIC_FORMAT,
    "local": LOCAL_FORMAT,
}


@dataclass
class PromptFrame:
    system_instruction: str = ""
    messages: List[Dict[str, str]] = field(default_factory=list)
    text_prompt: str = ""
    sections: List[PromptSection] = field(default_factory=list)


@dataclass
class PromptReport:
    prompt_tokens: int = 0
    section_sizes: Dict[str, int] = field(default_factory=dict)
    omitted_sections: List[str] = field(default_factory=list)
    truncation_flags: Dict[str, bool] = field(default_factory=dict)
    provider: str = "gemini"
    template_name: str = "default"


@dataclass
class AssemblyResult:
    frame: Optional[PromptFrame] = None
    report: Optional[PromptReport] = None


SOURCE_TO_SECTION: Dict[str, str] = {
    "system": "system_prompt",
    "memory": "long_term_memory",
    "knowledge": "retrieved_knowledge",
    "workflow": "workflow_state",
    "desktop": "desktop_context",
    "browser": "desktop_context",
    "terminal": "desktop_context",
    "mission": "workflow_state",
    "voice": "conversation_history",
    "user": "user_query",
    "project": "retrieved_knowledge",
    "web": "retrieved_knowledge",
}


def source_to_section(source: str) -> str:
    prefix = source.split("/")[0] if "/" in source else source
    return SOURCE_TO_SECTION.get(prefix, "retrieved_knowledge")


class IContextAssembler(ABC):

    @property
    @abstractmethod
    def assembler_name(self) -> str:
        ...

    @abstractmethod
    def assemble(
        self,
        compressed_blocks: List[CompressedBlock],
        compression_report: Optional[CompressionReport] = None,
        budget_report: Optional[BudgetReport] = None,
        strategy: Optional[StrategyConfig] = None,
        provider: str = "gemini",
    ) -> AssemblyResult:
        ...
