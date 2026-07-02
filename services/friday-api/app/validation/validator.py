import hashlib
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timezone
from loguru import logger

from app.budget.base import AllocatedBlock
from app.context.base import StrategyConfig
from app.validation.base import (
    IContextValidator,
    ValidationConfig,
    ValidationReport,
    ValidationResult,
    DEFAULT_VALIDATION_CONFIG,
)
from app.validation.events import ContextValidated
from app.events.bus import EventBus


class ContextValidator(IContextValidator):

    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self._event_bus = event_bus
        self._running = False

    @property
    def validator_name(self) -> str:
        return "context_validator"

    async def start(self) -> None:
        self._running = True
        logger.info("ContextValidator started.")

    async def shutdown(self) -> None:
        self._running = False
        logger.info("ContextValidator shut down.")

    def health(self):
        return {
            "status": "HEALTHY",
            "details": {
                "validator_name": self.validator_name,
                "running": self._running,
            },
        }

    def validate(
        self,
        blocks: List[AllocatedBlock],
        config: Optional[ValidationConfig] = None,
        strategy: Optional[StrategyConfig] = None,
    ) -> ValidationResult:
        cfg = config or DEFAULT_VALIDATION_CONFIG
        input_count = len(blocks)
        warnings: List[str] = []
        errors: List[str] = []

        seen_content_hashes: Set[str] = set()
        seen_source_hashes: Set[str] = set()
        seen_metadata_keys: Dict[str, Dict[str, object]] = {}
        valid: List[AllocatedBlock] = []
        dup_count = 0
        invalid_count = 0

        for ab in blocks:
            block = ab.block.block
            block_warnings: List[str] = []
            is_duplicate = False
            is_invalid = False

            # --- Validation checks ---

            # 1. Empty content
            if cfg.enable_content_empty_check:
                if not block.content or not block.content.strip():
                    errors.append(f"Block '{block.source}' has empty/whitespace-only content")
                    is_invalid = True

            # 2. Invalid metadata type
            if not isinstance(block.metadata, dict):
                errors.append(f"Block '{block.source}' has non-dict metadata")
                is_invalid = True

            # 3. Invalid timestamp
            ts = block.timestamp
            now = datetime.now(timezone.utc)
            if ts.tzinfo is None:
                warnings.append(f"Block '{block.source}' has naive timestamp (no timezone)")
            elif ts > now:
                errors.append(f"Block '{block.source}' has future timestamp")
                is_invalid = True
            elif ts.year < 2000:
                warnings.append(f"Block '{block.source}' has timestamp before year 2000")

            # 4. Confidence out of range
            if block.confidence < 0.0 or block.confidence > 1.0:
                warnings.append(f"Block '{block.source}' confidence {block.confidence} outside [0,1]")

            # 5. Negative token estimate
            if block.estimated_tokens < 0:
                errors.append(f"Block '{block.source}' has negative token estimate")
                is_invalid = True

            # 6. Oversized metadata
            meta_str = str(block.metadata) if isinstance(block.metadata, dict) else ""
            if len(meta_str) > cfg.max_metadata_size:
                warnings.append(f"Block '{block.source}' metadata size ({len(meta_str)}) exceeds limit ({cfg.max_metadata_size})")

            # 7. Malformed source
            if not block.source or len(block.source) > cfg.max_source_length:
                errors.append(f"Block '{block.source}' has malformed source (empty or too long)")
                is_invalid = True
            else:
                prefix = block.source.split("/")[0] if "/" in block.source else block.source
                if prefix not in cfg.allowed_source_prefixes:
                    warnings.append(f"Block '{block.source}' has unrecognized source prefix '{prefix}'")

            # 8. Duplicate content (same content hash)
            if cfg.enable_duplicate_content_detection and not is_invalid:
                content_hash = hashlib.md5(block.content.encode("utf-8")).hexdigest()
                if content_hash in seen_content_hashes:
                    warnings.append(f"Block '{block.source}' has duplicate content")
                    is_duplicate = True
                else:
                    seen_content_hashes.add(content_hash)

            # 9. Duplicate source (same source string)
            source_hash = hashlib.md5(block.source.encode("utf-8")).hexdigest()
            if source_hash in seen_source_hashes and not is_invalid:
                warnings.append(f"Block '{block.source}' has duplicate source identifier")
                is_duplicate = True
            else:
                seen_source_hashes.add(source_hash)

            # 10. Conflicting metadata (same key, different value for same source prefix)
            if cfg.enable_conflict_detection and isinstance(block.metadata, dict) and not is_invalid:
                for key, value in block.metadata.items():
                    if value is None:
                        continue
                    prev = seen_metadata_keys.get(key)
                    if prev is not None and prev.get("value") != value:
                        warnings.append(
                            f"Conflicting metadata key '{key}' "
                            f"(was '{prev.get('value')}', now '{value}')"
                        )
                    seen_metadata_keys[key] = {"value": value, "source": block.source}

            # --- Apply normalization ---
            normalized = ab
            if not is_invalid:
                needs_normalize = False

                # Confidence clamp
                if block.confidence < 0.0:
                    block.confidence = 0.0
                    needs_normalize = True
                elif block.confidence > 1.0:
                    block.confidence = 1.0
                    needs_normalize = True

                # Metadata normalization
                if not isinstance(block.metadata, dict):
                    block.metadata = {}
                    needs_normalize = True

                if needs_normalize:
                    block_warnings.append(f"Block '{block.source}' was normalized")

            # --- Decision ---
            if is_invalid:
                invalid_count += 1
            elif is_duplicate:
                dup_count += 1
            else:
                valid.append(normalized)

            for w in block_warnings:
                warnings.append(w)

        report = ValidationReport(
            input_blocks=input_count,
            valid_blocks=len(valid),
            removed_duplicates=dup_count,
            removed_invalid=invalid_count,
            warnings=warnings,
            errors=errors,
        )

        self._publish(report)

        return ValidationResult(valid_blocks=valid, report=report)

    def _publish(self, report: ValidationReport) -> None:
        if self._running and self._event_bus:
            try:
                self._event_bus.publish_background(
                    ContextValidated(
                        input_blocks=report.input_blocks,
                        valid_blocks=report.valid_blocks,
                        removed_duplicates=report.removed_duplicates,
                        removed_invalid=report.removed_invalid,
                        warnings=report.warnings,
                    )
                )
            except Exception as e:
                logger.error(f"Failed to publish ContextValidated: {e}")
