import re
from typing import Dict, List, Optional, Set, Tuple
from loguru import logger

from app.budget.base import AllocatedBlock
from app.context.base import StrategyConfig
from app.validation.base import ValidationReport
from app.budget.base import BudgetReport
from app.compression.base import (
    IContextCompressor,
    CompressionPolicy,
    CompressedBlock,
    CompressionReport,
    CompressionResult,
    DEFAULT_COMPRESSION_POLICY,
)
from app.compression.events import ContextCompressed
from app.events.bus import EventBus


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


_STRUCTURED_PATTERN = re.compile(
    r"^\s*(\{|\[|<(?!\|)|- )", re.MULTILINE
)
_UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)
_HASH_PATTERN = re.compile(r"\b[0-9a-fA-F]{32,64}\b")
_ID_PATTERN = re.compile(r"\b(id|_id|guid|uuid)\s*[=:]\s*\S+", re.IGNORECASE)
_STACK_TRACE_LINE = re.compile(r'^\s*(File\s+".*?",\s*line\s+\d+|at\s+[\w.]+\(|Traceback|Caused by)')
_LOG_TIMESTAMP = re.compile(r"^\d{4}[-/]\d{2}[-/]\d{2}[T ]\d{2}:\d{2}:\d{2}")
_CODE_COMMENT = re.compile(r"^\s*(#|//|--|/\*|\*| \*)")
_BLANK_LINE = re.compile(r"^\s*$")


class ContextCompressor(IContextCompressor):

    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self._event_bus = event_bus
        self._running = False

    @property
    def compressor_name(self) -> str:
        return "context_compressor"

    async def start(self) -> None:
        self._running = True
        logger.info("ContextCompressor started.")

    async def shutdown(self) -> None:
        self._running = False
        logger.info("ContextCompressor shut down.")

    def health(self):
        return {
            "status": "HEALTHY",
            "details": {
                "compressor_name": self.compressor_name,
                "running": self._running,
            },
        }

    def compress(
        self,
        blocks: List[AllocatedBlock],
        policy: CompressionPolicy = DEFAULT_COMPRESSION_POLICY,
        strategy: Optional[StrategyConfig] = None,
    ) -> CompressionResult:
        if policy == CompressionPolicy.NONE:
            return self._no_compression(blocks)

        compressed: List[CompressedBlock] = []
        skipped = 0
        per_block: List[Dict[str, object]] = []
        warnings: List[str] = []

        for ab in blocks:
            block = ab.block.block
            content = block.content
            source = block.source
            original_tokens = max(block.estimated_tokens, _estimate_tokens(content))

            if self._should_skip(source, content):
                compressed.append(CompressedBlock(
                    block=ab,
                    original_tokens=original_tokens,
                    compressed_tokens=original_tokens,
                    policy_applied="skipped",
                ))
                per_block.append({
                    "source": source,
                    "original_tokens": original_tokens,
                    "compressed_tokens": original_tokens,
                    "ratio": 0.0,
                    "policy": "skipped",
                })
                skipped += 1
                continue

            compressed_content = self._apply_policy(content, policy)

            compressed_tokens = _estimate_tokens(compressed_content)
            compressed_tokens = max(compressed_tokens, 1)

            # Update the block content with compressed version
            block.content = compressed_content

            cb = CompressedBlock(
                block=ab,
                original_tokens=original_tokens,
                compressed_tokens=compressed_tokens,
                policy_applied=policy.value,
            )

            if cb.compression_ratio < 0:
                warnings.append(f"Block '{source}' expanded after compression")

            compressed.append(cb)
            per_block.append({
                "source": source,
                "original_tokens": original_tokens,
                "compressed_tokens": compressed_tokens,
                "ratio": cb.compression_ratio,
                "policy": policy.value,
            })

        input_tokens = sum(cb.original_tokens for cb in compressed)
        output_tokens = sum(cb.compressed_tokens for cb in compressed)

        report = CompressionReport(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            saved_tokens=input_tokens - output_tokens,
            compression_ratio=round(
                1.0 - (output_tokens / input_tokens), 4
            ) if input_tokens > 0 else 0.0,
            per_block_statistics=per_block,
            skipped_blocks=skipped,
            warnings=warnings,
        )

        self._publish(report, policy)

        return CompressionResult(compressed_blocks=compressed, report=report)

    def _no_compression(self, blocks: List[AllocatedBlock]) -> CompressionResult:
        compressed: List[CompressedBlock] = []
        per_block: List[Dict[str, object]] = []
        for ab in blocks:
            content = ab.block.block.content
            original = max(ab.block.block.estimated_tokens, _estimate_tokens(content))
            cb = CompressedBlock(
                block=ab,
                original_tokens=original,
                compressed_tokens=original,
                policy_applied="none",
            )
            compressed.append(cb)
            per_block.append({
                "source": ab.block.block.source,
                "original_tokens": original,
                "compressed_tokens": original,
                "ratio": 0.0,
                "policy": "none",
            })

        total = sum(c.original_tokens for c in compressed)
        report = CompressionReport(
            input_tokens=total,
            output_tokens=total,
            saved_tokens=0,
            compression_ratio=0.0,
            per_block_statistics=per_block,
            skipped_blocks=0,
        )
        self._publish(report, CompressionPolicy.NONE)
        return CompressionResult(compressed_blocks=compressed, report=report)

    @staticmethod
    def _should_skip(source: str, content: str) -> bool:
        if source.startswith("system/"):
            return True
        if source.startswith("user/"):
            return True
        if source.startswith("memory/") and "identifier" in source:
            return True
        if not content.strip():
            return True
        if _STRUCTURED_PATTERN.match(content):
            return True
        if _UUID_PATTERN.search(content):
            return False
        if _HASH_PATTERN.search(content):
            return False
        return False

    @staticmethod
    def _apply_policy(content: str, policy: CompressionPolicy) -> str:
        result = content
        if policy == CompressionPolicy.LIGHT:
            result = ContextCompressor._whitespace_cleanup(result)
        elif policy == CompressionPolicy.STANDARD:
            result = ContextCompressor._whitespace_cleanup(result)
            result = ContextCompressor._markdown_cleanup(result)
            result = ContextCompressor._remove_redundant_lines(result)
            result = ContextCompressor._remove_repeated_sentences(result)
        elif policy == CompressionPolicy.AGGRESSIVE:
            result = ContextCompressor._whitespace_cleanup(result)
            result = ContextCompressor._markdown_cleanup(result)
            result = ContextCompressor._remove_redundant_lines(result)
            result = ContextCompressor._remove_repeated_sentences(result)
            result = ContextCompressor._shorten_stack_traces(result)
            result = ContextCompressor._collapse_logs(result)
            result = ContextCompressor._trim_code_blocks(result)
        return result

    @staticmethod
    def _whitespace_cleanup(text: str) -> str:
        lines = text.split("\n")
        cleaned = [line.rstrip() for line in lines]
        result: List[str] = []
        blank_count = 0
        for line in cleaned:
            if _BLANK_LINE.match(line):
                blank_count += 1
                if blank_count <= 2:
                    result.append("")
            else:
                blank_count = 0
                result.append(line)
        return "\n".join(result).strip()

    @staticmethod
    def _markdown_cleanup(text: str) -> str:
        lines = text.split("\n")
        result: List[str] = []
        hr_count = 0
        for line in lines:
            if re.match(r"^\s*[-*_]{3,}\s*$", line):
                hr_count += 1
                if hr_count <= 1:
                    result.append(line)
            else:
                hr_count = 0
                result.append(line)
        return "\n".join(result)

    @staticmethod
    def _remove_redundant_lines(text: str) -> str:
        lines = text.split("\n")
        result: List[str] = []
        prev = None
        for line in lines:
            stripped = line.strip()
            if stripped and stripped == prev:
                continue
            result.append(line)
            prev = stripped
        return "\n".join(result)

    @staticmethod
    def _remove_repeated_sentences(text: str) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        seen: Set[str] = set()
        result: List[str] = []
        for s in sentences:
            key = s.strip().lower()
            if key and key not in seen:
                result.append(s)
                seen.add(key)
        return " ".join(result)

    @staticmethod
    def _shorten_stack_traces(text: str) -> str:
        lines = text.split("\n")
        trace_indices: List[int] = []
        in_trace = False
        for i, line in enumerate(lines):
            if _STACK_TRACE_LINE.match(line) or in_trace:
                if _STACK_TRACE_LINE.match(line):
                    if not in_trace:
                        trace_indices.append(i)
                    in_trace = True
                elif _BLANK_LINE.match(line):
                    in_trace = False

        if not trace_indices:
            return text

        result = list(lines)
        offset = 0
        for start in trace_indices:
            end = start
            while end < len(lines) and (_STACK_TRACE_LINE.match(lines[end]) or
                                         (end > start and _BLANK_LINE.match(lines[end]))):
                end += 1
            while end < len(lines) and _STACK_TRACE_LINE.match(lines[end]):
                end += 1

            trace_lines = lines[start:end]
            if len(trace_lines) > 6:
                keep = trace_lines[:3] + ["  ..."] + trace_lines[-3:]
                result[start + offset:end + offset] = keep
                offset += len(keep) - len(trace_lines)

        return "\n".join(result)

    @staticmethod
    def _collapse_logs(text: str) -> str:
        lines = text.split("\n")
        result: List[str] = []
        group: List[str] = []
        group_key: Optional[str] = None

        def flush_group():
            if len(group) == 1:
                result.append(group[0])
            elif len(group) > 1:
                first = group[0]
                result.append(f"{first}  [repeated {len(group)}x]")
            group.clear()

        for line in lines:
            ts_match = _LOG_TIMESTAMP.match(line)
            if ts_match:
                key = line[ts_match.end():].strip()
                if group_key is not None and key == group_key:
                    group.append(line)
                else:
                    flush_group()
                    group_key = key
                    group = [line]
            else:
                flush_group()
                group_key = None
                result.append(line)

        flush_group()
        return "\n".join(result)

    @staticmethod
    def _trim_code_blocks(text: str) -> str:
        lines = text.split("\n")
        result: List[str] = []
        in_fence = False

        for line in lines:
            if line.strip().startswith("```"):
                in_fence = not in_fence
                result.append(line)
                continue

            if in_fence:
                if _CODE_COMMENT.match(line):
                    continue
                if _BLANK_LINE.match(line):
                    continue
                result.append(line)
                continue

            if _CODE_COMMENT.match(line):
                continue

            result.append(line)

        return "\n".join(result)

    def _publish(self, report: CompressionReport, policy: CompressionPolicy) -> None:
        if self._running and self._event_bus:
            try:
                self._event_bus.publish_background(
                    ContextCompressed(
                        input_tokens=report.input_tokens,
                        output_tokens=report.output_tokens,
                        saved_tokens=report.saved_tokens,
                        compression_ratio=report.compression_ratio,
                        skipped_blocks=report.skipped_blocks,
                        policy=policy.value,
                    )
                )
            except Exception as e:
                logger.error(f"Failed to publish ContextCompressed: {e}")
