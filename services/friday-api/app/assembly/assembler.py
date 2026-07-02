from typing import Dict, List, Optional
from loguru import logger

from app.compression.base import CompressedBlock, CompressionReport
from app.context.base import StrategyConfig
from app.budget.base import BudgetReport
from app.assembly.base import (
    IContextAssembler,
    PromptSection,
    PromptFrame,
    PromptReport,
    AssemblyResult,
    SECTION_ORDER,
    SOURCE_TO_SECTION,
    source_to_section,
    PROVIDER_FORMATS,
    GEMINI_FORMAT,
)
from app.assembly.templates import build_frame
from app.assembly.events import PromptAssembled
from app.events.bus import EventBus


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class PromptAssembler(IContextAssembler):

    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self._event_bus = event_bus
        self._running = False

    @property
    def assembler_name(self) -> str:
        return "prompt_assembler"

    async def start(self) -> None:
        self._running = True
        logger.info("PromptAssembler started.")

    async def shutdown(self) -> None:
        self._running = False
        logger.info("PromptAssembler shut down.")

    def health(self):
        return {
            "status": "HEALTHY",
            "details": {
                "assembler_name": self.assembler_name,
                "running": self._running,
            },
        }

    def assemble(
        self,
        compressed_blocks: List[CompressedBlock],
        compression_report: Optional[CompressionReport] = None,
        budget_report: Optional[BudgetReport] = None,
        strategy: Optional[StrategyConfig] = None,
        provider: str = "gemini",
    ) -> AssemblyResult:
        fmt = PROVIDER_FORMATS.get(provider, GEMINI_FORMAT)

        section_contents: Dict[str, List[str]] = {s: [] for s in SECTION_ORDER}
        truncation_flags: Dict[str, bool] = {s: False for s in SECTION_ORDER}

        for cb in compressed_blocks:
            block = cb.block.block.block
            source = block.source
            content = block.content
            if not content or not content.strip():
                continue

            section = source_to_section(source)
            if section not in section_contents:
                section = "retrieved_knowledge"

            section_contents[section].append(content)
            is_truncated = cb.block.is_truncated
            if is_truncated:
                truncation_flags[section] = True

        sections: List[PromptSection] = []
        section_sizes: Dict[str, int] = {}
        omitted: List[str] = []
        total_tokens = 0
        budget_ceiling = budget_report.allocated_tokens if budget_report else 0

        for section_name in SECTION_ORDER:
            contents = section_contents.get(section_name, [])
            if not contents:
                sections.append(PromptSection(
                    name=section_name, content="", is_omitted=True
                ))
                omitted.append(section_name)
                section_sizes[section_name] = 0
                continue

            combined = "\n\n".join(contents)
            tokens = _estimate_tokens(combined)

            if budget_ceiling > 0 and total_tokens + tokens > budget_ceiling:
                remaining = budget_ceiling - total_tokens
                if remaining <= 0:
                    sections.append(PromptSection(
                        name=section_name, content="", is_omitted=True
                    ))
                    omitted.append(section_name)
                    section_sizes[section_name] = 0
                    continue
                combined = combined[:remaining * 4]
                tokens = remaining
                truncation_flags[section_name] = True

            section = PromptSection(
                name=section_name,
                content=combined,
                tokens=tokens,
                is_truncated=truncation_flags.get(section_name, False),
            )
            sections.append(section)
            section_sizes[section_name] = tokens
            total_tokens += tokens

        frame = build_frame(sections, provider=provider)

        report = PromptReport(
            prompt_tokens=total_tokens,
            section_sizes=section_sizes,
            omitted_sections=omitted,
            truncation_flags=truncation_flags,
            provider=provider,
            template_name=fmt.template_name,
        )

        self._publish(report)

        return AssemblyResult(frame=frame, report=report)

    def _publish(self, report: PromptReport) -> None:
        if self._running and self._event_bus:
            try:
                self._event_bus.publish_background(
                    PromptAssembled(
                        prompt_tokens=report.prompt_tokens,
                        provider=report.provider,
                        template_name=report.template_name,
                        section_count=len(report.section_sizes),
                        omitted_sections=report.omitted_sections,
                    )
                )
            except Exception as e:
                logger.error(f"Failed to publish PromptAssembled: {e}")
