import asyncio
from typing import Dict, List, Optional, Tuple
from loguru import logger

from app.extraction.base import IContextExtractor, ContextBlock, ExtractionResult
from app.extraction.events import (
    ContextExtractionStarted,
    ContextExtractionCompleted,
    ContextExtractionFailed,
)
from app.context.base import StrategyConfig
from app.events.bus import EventBus


class ExtractorRegistry:
    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self._event_bus = event_bus
        self._running = False
        self._extractors: Dict[str, IContextExtractor] = {}
        self._alias_map: Dict[str, str] = {}

    async def start(self) -> None:
        self._running = True
        logger.info(f"ExtractorRegistry started ({len(self._extractors)} extractors registered).")

    async def shutdown(self) -> None:
        self._running = False
        logger.info("ExtractorRegistry shut down.")

    def health(self):
        return {
            "status": "HEALTHY",
            "details": {
                "registered_extractors": len(self._extractors),
                "extractor_names": list(self._extractors.keys()),
            },
        }

    def register(self, extractor: IContextExtractor) -> None:
        primary = extractor.extractor_name
        self._extractors[primary] = extractor
        for alias in extractor.aliases:
            self._alias_map[alias] = primary
        logger.debug(f"Registered extractor '{primary}' under {len(extractor.aliases)} alias(es) (priority={extractor.priority}).")

    def unregister(self, name: str) -> None:
        primary = self._alias_map.get(name, name)
        self._extractors.pop(primary, None)
        aliases_to_remove = [k for k, v in self._alias_map.items() if v == primary]
        for a in aliases_to_remove:
            self._alias_map.pop(a, None)

    def get(self, name: str) -> Optional[IContextExtractor]:
        primary = self._alias_map.get(name, name)
        return self._extractors.get(primary)

    def list_extractors(self) -> Dict[str, int]:
        return {n: e.priority for n, e in self._extractors.items()}

    def resolve_by_strategy(self, config: StrategyConfig) -> List[IContextExtractor]:
        resolved: Dict[str, IContextExtractor] = {}
        for name in config.extractors:
            ext = self.get(name)
            if ext:
                resolved[ext.extractor_name] = ext
            else:
                logger.warning(f"Extractor '{name}' required by strategy but not registered.")
        resolved_list = list(resolved.values())
        resolved_list.sort(key=lambda e: e.priority)
        return resolved_list

    async def extract_all(self, request: str, timeout: float = 10.0) -> ExtractionResult:
        if not self._extractors:
            return ExtractionResult(failures=["No extractors registered"])

        sorted_extractors = sorted(self._extractors.values(), key=lambda e: e.priority)

        if self._running and self._event_bus:
            try:
                await self._event_bus.publish(ContextExtractionStarted(
                    request=request,
                    extractor_names=[e.extractor_name for e in sorted_extractors],
                    strategy_name="all",
                ))
            except Exception as pub_err:
                logger.error(f"Failed to publish ContextExtractionStarted: {pub_err}")

        blocks: List[ContextBlock] = []
        failures: List[str] = []

        async def _run_one(ext: IContextExtractor) -> Tuple[str, List[ContextBlock]]:
            try:
                result = await asyncio.wait_for(ext.extract(request), timeout=timeout)
                return (ext.extractor_name, result)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Extractor '{ext.extractor_name}' timed out after {timeout}s")
            except Exception as e:
                raise RuntimeError(f"Extractor '{ext.extractor_name}' failed: {e}")

        tasks = [_run_one(e) for e in sorted_extractors]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, BaseException):
                failures.append(str(r))
            else:
                _name, ext_blocks = r
                blocks.extend(ext_blocks)

        if failures:
            logger.warning(f"Extraction completed with {len(failures)} failure(s): {failures}")
        if self._running and self._event_bus:
            try:
                if len(failures) == len(sorted_extractors):
                    await self._event_bus.publish(ContextExtractionFailed(
                        request=request,
                        error="; ".join(failures),
                        extractor_name="all",
                    ))
                else:
                    await self._event_bus.publish(ContextExtractionCompleted(
                        request=request,
                        block_count=len(blocks),
                        total_tokens=sum(b.estimated_tokens for b in blocks),
                        partial_failures=failures if failures else None,
                    ))
            except Exception as pub_err:
                logger.error(f"Failed to publish extraction completion event: {pub_err}")

        return ExtractionResult(blocks=blocks, failures=failures)

    async def extract_for_strategy(self, request: str, config: StrategyConfig,
                                   timeout: float = 10.0) -> ExtractionResult:
        extractors = self.resolve_by_strategy(config)
        if not extractors:
            return ExtractionResult(failures=["No extractors resolved for strategy"])

        extractor_names = [e.extractor_name for e in extractors]

        if self._running and self._event_bus:
            try:
                await self._event_bus.publish(ContextExtractionStarted(
                    request=request,
                    extractor_names=extractor_names,
                    strategy_name="strategy_resolved",
                ))
            except Exception as pub_err:
                logger.error(f"Failed to publish ContextExtractionStarted: {pub_err}")

        blocks: List[ContextBlock] = []
        failures: List[str] = []

        async def _run_one(ext: IContextExtractor) -> Tuple[str, List[ContextBlock]]:
            try:
                result = await asyncio.wait_for(ext.extract(request), timeout=timeout)
                return (ext.extractor_name, result)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Extractor '{ext.extractor_name}' timed out after {timeout}s")
            except Exception as e:
                raise RuntimeError(f"Extractor '{ext.extractor_name}' failed: {e}")

        tasks = [_run_one(e) for e in extractors]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, BaseException):
                failures.append(str(r))
            else:
                _name, ext_blocks = r
                blocks.extend(ext_blocks)

        if failures:
            logger.warning(f"Strategy extraction completed with {len(failures)} failure(s): {failures}")
        if self._running and self._event_bus:
            try:
                if len(failures) == len(extractors):
                    await self._event_bus.publish(ContextExtractionFailed(
                        request=request,
                        error="; ".join(failures),
                        extractor_name=",".join(extractor_names),
                    ))
                else:
                    await self._event_bus.publish(ContextExtractionCompleted(
                        request=request,
                        block_count=len(blocks),
                        total_tokens=sum(b.estimated_tokens for b in blocks),
                        partial_failures=failures if failures else None,
                    ))
            except Exception as pub_err:
                logger.error(f"Failed to publish extraction completion event: {pub_err}")

        return ExtractionResult(blocks=blocks, failures=failures)
