import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set

from loguru import logger

from app.cache.base import CacheKey, CacheLevel, compute_context_hash, DEFAULT_CACHE_TTL
from app.context.base import StrategyConfig
from app.budget.base import BudgetConfig
from app.extraction.base import ContextBlock
from app.ranking.base import RankingResult, RankedContextBlock
from app.compression.base import CompressionResult, CompressedBlock
from app.assembly.base import PromptSection, PromptFrame
from app.events.bus import EventBus
from app.events.events import FridayEvent
from app.intent.analyzer import RuleBasedIntentAnalyzer, IntentResult
from app.context.manager import StrategyManager
from app.extraction.registry import ExtractorRegistry
from app.ranking.ranker import ContextRanker
from app.budget.allocator import AdaptiveTokenBudgetAllocator
from app.validation.validator import ContextValidator
from app.compression.compressor import ContextCompressor
from app.assembly.assembler import PromptAssembler
from app.intelligence.pipeline import PipelineStatus, PipelineResult, map_extractor_to_cache_level

from app.intelligence.events import (
    SnapshotLoaded,
    ContextDeltaCalculated,
    SnapshotUpdated,
    IncrementalUpdateCompleted,
    PipelineFailed,
)


@dataclass
class ContextSnapshot:
    session_id: str
    query_hash: str
    strategy_signature: str
    timestamp: float
    ranked_blocks: List[RankedContextBlock] = field(default_factory=list)
    allocated_blocks: List[Any] = field(default_factory=list)
    valid_blocks: List[ContextBlock] = field(default_factory=list)
    compressed_blocks: List[CompressedBlock] = field(default_factory=list)
    prompt_sections: List[PromptSection] = field(default_factory=list)
    prompt_frame: Optional[PromptFrame] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextDelta:
    new_blocks: List[ContextBlock] = field(default_factory=list)
    removed_blocks: List[ContextBlock] = field(default_factory=list)
    updated_blocks: List[ContextBlock] = field(default_factory=list)
    reused_blocks: List[ContextBlock] = field(default_factory=list)
    has_changes: bool = False


class DeltaCalculator:
    @staticmethod
    def calculate(
        prev_snapshot: Optional[ContextSnapshot],
        fresh_blocks: List[ContextBlock],
        strategy_config: StrategyConfig,
        extractors_run: Optional[List[str]] = None,
    ) -> ContextDelta:
        if not prev_snapshot:
            return ContextDelta(new_blocks=fresh_blocks, has_changes=True)

        snap_by_source = {b.source: b for b in prev_snapshot.valid_blocks}

        new_blocks = []
        updated_blocks = []
        reused_blocks = []
        fresh_sources = set()

        for b in fresh_blocks:
            fresh_sources.add(b.source)
            if b.source in snap_by_source:
                old_b = snap_by_source[b.source]
                # Compare content and basic properties
                if old_b.content != b.content or old_b.estimated_tokens != b.estimated_tokens:
                    updated_blocks.append(b)
                else:
                    reused_blocks.append(old_b)
            else:
                new_blocks.append(b)

        # Detect removed blocks for extractors that actually ran (or all strategy extractors if not specified)
        removed_blocks = []
        target_extractors = extractors_run if extractors_run is not None else strategy_config.extractors
        run_prefixes = {ext.split("_")[0] for ext in target_extractors}
        for src, old_b in snap_by_source.items():
            prefix = src.split("/")[0] if "/" in src else src
            if prefix in run_prefixes and src not in fresh_sources:
                removed_blocks.append(old_b)

        has_changes = len(new_blocks) > 0 or len(removed_blocks) > 0 or len(updated_blocks) > 0

        return ContextDelta(
            new_blocks=new_blocks,
            removed_blocks=removed_blocks,
            updated_blocks=updated_blocks,
            reused_blocks=reused_blocks,
            has_changes=has_changes,
        )


class SnapshotStore:
    def __init__(self) -> None:
        self._snapshots: Dict[str, ContextSnapshot] = {}

    def get(self, session_id: str) -> Optional[ContextSnapshot]:
        return self._snapshots.get(session_id)

    def save(self, session_id: str, snapshot: ContextSnapshot) -> None:
        self._snapshots[session_id] = snapshot

    def invalidate(self, session_id: str) -> None:
        self._snapshots.pop(session_id, None)

    def clear(self) -> None:
        self._snapshots.clear()


class IncrementalContextManager:
    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self._event_bus = event_bus
        self._store = SnapshotStore()
        self._invalidated_levels: Dict[str, Set[CacheLevel]] = {}
        self._running = False
        self._metrics_history: List[Dict[str, Any]] = []

    async def start(self) -> None:
        self._running = True
        self._subscribe_to_events()
        logger.info("IncrementalContextManager started.")

    async def shutdown(self) -> None:
        self._running = False
        self._unsubscribe_from_events()
        logger.info("IncrementalContextManager shut down.")

    def health(self) -> dict:
        return {
            "status": "HEALTHY",
            "details": {
                "active_snapshots": len(self._store._snapshots),
                "running": self._running,
                "total_metrics_recorded": len(self._metrics_history),
            },
        }

    def _invalidate_level(self, session_id: str, level: CacheLevel) -> None:
        if session_id not in self._invalidated_levels:
            self._invalidated_levels[session_id] = set()
        self._invalidated_levels[session_id].add(level)

    def _on_memory_changed(self, event: FridayEvent) -> None:
        session_id = event.data.get("session_id", "")
        if session_id:
            self._invalidate_level(session_id, CacheLevel.MEMORY)
        else:
            for s in list(self._invalidated_levels.keys()):
                self._invalidate_level(s, CacheLevel.MEMORY)

    def _on_knowledge_changed(self, event: FridayEvent) -> None:
        for s in list(self._invalidated_levels.keys()):
            self._invalidate_level(s, CacheLevel.KNOWLEDGE)

    def _on_workflow_changed(self, event: FridayEvent) -> None:
        session_id = event.data.get("session_id", "")
        if session_id:
            self._invalidate_level(session_id, CacheLevel.WORKFLOW)
        else:
            for s in list(self._invalidated_levels.keys()):
                self._invalidate_level(s, CacheLevel.WORKFLOW)

    def _on_desktop_changed(self, event: FridayEvent) -> None:
        session_id = event.data.get("session_id", "")
        if session_id:
            self._invalidate_level(session_id, CacheLevel.DESKTOP)
        else:
            for s in list(self._invalidated_levels.keys()):
                self._invalidate_level(s, CacheLevel.DESKTOP)

    def _on_tool_changed(self, event: FridayEvent) -> None:
        session_id = event.data.get("session_id", "")
        if session_id:
            self._invalidate_level(session_id, CacheLevel.TOOL_RESULTS)
        else:
            for s in list(self._invalidated_levels.keys()):
                self._invalidate_level(s, CacheLevel.TOOL_RESULTS)

    def _subscribe_to_events(self) -> None:
        if not self._event_bus:
            return
        self._event_bus.subscribe("MemoryCreated", self._on_memory_changed)
        self._event_bus.subscribe("MemoryUpdated", self._on_memory_changed)
        self._event_bus.subscribe("MemoryExpired", self._on_memory_changed)
        self._event_bus.subscribe("DocumentIndexed", self._on_knowledge_changed)
        self._event_bus.subscribe("DocumentUpdated", self._on_knowledge_changed)
        self._event_bus.subscribe("DocumentDeleted", self._on_knowledge_changed)
        self._event_bus.subscribe("WorkflowStarted", self._on_workflow_changed)
        self._event_bus.subscribe("WorkflowCompleted", self._on_workflow_changed)
        self._event_bus.subscribe("DesktopChanged", self._on_desktop_changed)
        self._event_bus.subscribe("WindowOpened", self._on_desktop_changed)
        self._event_bus.subscribe("WindowClosed", self._on_desktop_changed)
        self._event_bus.subscribe("ToolExecuted", self._on_tool_changed)
        self._event_bus.subscribe("ToolCompleted", self._on_tool_changed)

    def _unsubscribe_from_events(self) -> None:
        if not self._event_bus:
            return
        self._event_bus.unsubscribe("MemoryCreated", self._on_memory_changed)
        self._event_bus.unsubscribe("MemoryUpdated", self._on_memory_changed)
        self._event_bus.unsubscribe("MemoryExpired", self._on_memory_changed)
        self._event_bus.unsubscribe("DocumentIndexed", self._on_knowledge_changed)
        self._event_bus.unsubscribe("DocumentUpdated", self._on_knowledge_changed)
        self._event_bus.unsubscribe("DocumentDeleted", self._on_knowledge_changed)
        self._event_bus.unsubscribe("WorkflowStarted", self._on_workflow_changed)
        self._event_bus.unsubscribe("WorkflowCompleted", self._on_workflow_changed)
        self._event_bus.unsubscribe("DesktopChanged", self._on_desktop_changed)
        self._event_bus.unsubscribe("WindowOpened", self._on_desktop_changed)
        self._event_bus.unsubscribe("WindowClosed", self._on_desktop_changed)
        self._event_bus.unsubscribe("ToolExecuted", self._on_tool_changed)
        self._event_bus.unsubscribe("ToolCompleted", self._on_tool_changed)

    async def execute_incremental(
        self,
        user_query: str,
        session_id: str = "",
        provider: str = "gemini",
        timeout: float = 60.0,
    ) -> PipelineResult:
        execution_id = str(uuid.uuid4())
        t_start = time.time()

        # 1. Load Snapshot
        t0 = time.time()
        snapshot = self._store.get(session_id)
        snapshot_load_time = (time.time() - t0) * 1000

        if snapshot:
            await self._publish(SnapshotLoaded(execution_id, session_id, snapshot.timestamp))

        # Retrieve DI Core Components
        kernel = None
        try:
            from app.kernel.kernel import FridayKernel
            kernel = FridayKernel.get_instance()
        except Exception:
            pass

        def get_svc(name: str):
            if kernel is not None:
                return kernel.get_service(name)
            return None

        intent_analyzer = get_svc("intent_analyzer") or RuleBasedIntentAnalyzer()
        strategy_manager = get_svc("strategy_manager") or StrategyManager()
        extractor_registry = get_svc("extractor_registry") or ExtractorRegistry()
        context_ranker = get_svc("context_ranker") or ContextRanker()
        token_allocator = get_svc("token_allocator") or AdaptiveTokenBudgetAllocator()
        context_validator = get_svc("context_validator") or ContextValidator()
        context_compressor = get_svc("context_compressor") or ContextCompressor()
        prompt_assembler = get_svc("prompt_assembler") or PromptAssembler()
        context_cache = get_svc("context_cache")

        try:
            intent_res = await intent_analyzer.analyze(user_query)
            strategy = strategy_manager.get_strategy(intent_res.intent)
            strategy_config = strategy.get_config()

            if not snapshot:
                # Cold run
                fresh_res = await extractor_registry.extract_for_strategy(user_query, strategy_config)
                fresh_blocks = fresh_res.blocks

                ranking_res = context_ranker.rank(fresh_blocks, query=user_query)

                budget_config = BudgetConfig.for_model(provider)
                allocation_res = token_allocator.allocate(
                    ranking_res.ranked_blocks,
                    config=budget_config,
                    strategy=strategy_config,
                )

                validation_res = context_validator.validate(
                    allocation_res.selected_blocks,
                    strategy=strategy_config,
                )

                compression_res = context_compressor.compress(
                    validation_res.valid_blocks,
                    policy=strategy_config.compression_policy if strategy_config else None,
                    strategy=strategy_config,
                )

                assembly_res = prompt_assembler.assemble(
                    compression_res.compressed_blocks,
                    compression_report=compression_res.report,
                    budget_report=allocation_res.report if allocation_res else None,
                    strategy=strategy_config,
                    provider=provider,
                )

                # Save snapshot
                t0 = time.time()
                new_snapshot = ContextSnapshot(
                    session_id=session_id,
                    query_hash=compute_context_hash(user_query),
                    strategy_signature=str(strategy_config),
                    timestamp=time.time(),
                    ranked_blocks=ranking_res.ranked_blocks,
                    allocated_blocks=allocation_res.selected_blocks,
                    valid_blocks=validation_res.valid_blocks,
                    compressed_blocks=compression_res.compressed_blocks,
                    prompt_sections=assembly_res.frame.sections if assembly_res.frame else [],
                    prompt_frame=assembly_res.frame,
                    metadata={"reused_count": 0, "recomputed_count": len(fresh_blocks)}
                )
                self._store.save(session_id, new_snapshot)
                snapshot_save_time = (time.time() - t0) * 1000

                await self._publish(SnapshotUpdated(execution_id, session_id, len(new_snapshot.valid_blocks)))

                # Record metrics
                self._metrics_history.append({
                    "execution_id": execution_id,
                    "delta_size": len(fresh_blocks),
                    "reused_blocks": 0,
                    "recomputed_blocks": len(fresh_blocks),
                    "snapshot_load_time": snapshot_load_time,
                    "snapshot_save_time": snapshot_save_time,
                    "pipeline_speedup": 1.0,
                })

                return PipelineResult(
                    status=PipelineStatus.COMPLETED,
                    execution_id=execution_id,
                    assembly_result=assembly_res,
                )

            # Warm run
            invalidated = self._invalidated_levels.get(session_id, set())

            # Cache expiration checks
            now = time.time()
            for lvl in list(CacheLevel):
                ttl = DEFAULT_CACHE_TTL.get(lvl, 300.0)
                if now - snapshot.timestamp > ttl:
                    invalidated.add(lvl)

            extractor_names = strategy_config.extractors if strategy_config else []
            extractors_to_run = []
            reused_blocks = []

            for ext_name in extractor_names:
                level = map_extractor_to_cache_level(ext_name)
                if level in invalidated:
                    extractors_to_run.append(ext_name)
                else:
                    ext_prefix = ext_name.split("_")[0]
                    snap_blocks = [b for b in snapshot.valid_blocks if b.source.startswith(ext_prefix) or (("/" in b.source) and b.source.split("/")[0] == ext_prefix)]
                    if snap_blocks:
                        reused_blocks.extend(snap_blocks)
                    else:
                        extractors_to_run.append(ext_name)

            # Execute changed sources
            fresh_blocks = []
            if extractors_to_run:
                config = StrategyConfig(
                    extractors=extractors_to_run,
                    token_budget=strategy_config.token_budget if strategy_config else None,
                    retrieval_priority=strategy_config.retrieval_priority if strategy_config else None,
                    compression_policy=strategy_config.compression_policy if strategy_config else None,
                    cache_policy=strategy_config.cache_policy if strategy_config else None,
                )
                fresh_res = await extractor_registry.extract_for_strategy(user_query, config)
                fresh_blocks = fresh_res.blocks

            # Invalidate/refresh the cache if needed
            if context_cache and fresh_blocks:
                for ext_name in extractors_to_run:
                    ext_prefix = ext_name.split("_")[0]
                    ext_fresh = [b for b in fresh_blocks if b.source.startswith(ext_prefix) or (("/" in b.source) and b.source.split("/")[0] == ext_prefix)]
                    if ext_fresh:
                        cache_key = CacheKey(
                            session_id=session_id,
                            intent=intent_res.intent.value if intent_res else "",
                            strategy=strategy.intent_type.value if strategy else "",
                            provider=provider,
                            extractor=ext_name,
                            context_hash=compute_context_hash(user_query),
                        )
                        await context_cache.set(cache_key, ext_fresh, map_extractor_to_cache_level(ext_name))

            # Compute Delta
            delta = DeltaCalculator.calculate(snapshot, fresh_blocks, strategy_config, extractors_to_run)
            await self._publish(ContextDeltaCalculated(
                execution_id,
                len(delta.new_blocks),
                len(delta.removed_blocks),
                len(delta.updated_blocks),
            ))

            # Merge Delta
            removed_sources = {b.source for b in delta.removed_blocks}
            updated_sources = {b.source for b in delta.updated_blocks}
            
            merged_blocks = []
            for b in reused_blocks:
                if b.source not in removed_sources and b.source not in updated_sources:
                    merged_blocks.append(b)

            merged_blocks.extend(delta.updated_blocks)
            merged_blocks.extend(delta.new_blocks)

            # Re-run pipeline elements only if changes were detected
            if delta.has_changes or len(extractors_to_run) > 0:
                ranking_res = context_ranker.rank(merged_blocks, query=user_query)

                budget_config = BudgetConfig.for_model(provider)
                allocation_res = token_allocator.allocate(
                    ranking_res.ranked_blocks,
                    config=budget_config,
                    strategy=strategy_config,
                )

                validation_res = context_validator.validate(
                    allocation_res.selected_blocks,
                    strategy=strategy_config,
                )

                compression_res = context_compressor.compress(
                    validation_res.valid_blocks,
                    policy=strategy_config.compression_policy if strategy_config else None,
                    strategy=strategy_config,
                )

                assembly_res = prompt_assembler.assemble(
                    compression_res.compressed_blocks,
                    compression_report=compression_res.report,
                    budget_report=allocation_res.report if allocation_res else None,
                    strategy=strategy_config,
                    provider=provider,
                )
            else:
                # If nothing changed, mock the outputs using current snapshot state
                ranking_res = type("RankRes", (), {"ranked_blocks": snapshot.ranked_blocks})()
                allocation_res = type("AllocRes", (), {"selected_blocks": snapshot.allocated_blocks, "report": None})()
                validation_res = type("ValRes", (), {"valid_blocks": snapshot.valid_blocks, "report": None})()
                compression_res = type("CompRes", (), {"compressed_blocks": snapshot.compressed_blocks, "report": None})()
                assembly_res = type("AsmRes", (), {"frame": snapshot.prompt_frame, "report": None})()

            # Save snapshot
            t0 = time.time()
            new_snapshot = ContextSnapshot(
                session_id=session_id,
                query_hash=compute_context_hash(user_query),
                strategy_signature=str(strategy_config),
                timestamp=time.time(),
                ranked_blocks=ranking_res.ranked_blocks,
                allocated_blocks=allocation_res.selected_blocks,
                valid_blocks=validation_res.valid_blocks,
                compressed_blocks=compression_res.compressed_blocks,
                prompt_sections=assembly_res.frame.sections if assembly_res.frame else [],
                prompt_frame=assembly_res.frame,
                metadata={"reused_count": len(reused_blocks), "recomputed_count": len(fresh_blocks)}
            )
            self._store.save(session_id, new_snapshot)
            snapshot_save_time = (time.time() - t0) * 1000

            await self._publish(SnapshotUpdated(execution_id, session_id, len(new_snapshot.valid_blocks)))

            if session_id in self._invalidated_levels:
                self._invalidated_levels[session_id].clear()

            total_blocks = len(reused_blocks) + len(fresh_blocks)
            recomputed_count = len(fresh_blocks)
            speedup = float(total_blocks) / float(recomputed_count or 1)

            await self._publish(IncrementalUpdateCompleted(
                execution_id,
                reused_count=len(reused_blocks),
                recomputed_count=recomputed_count,
                speedup_ratio=speedup,
            ))

            self._metrics_history.append({
                "execution_id": execution_id,
                "delta_size": len(delta.new_blocks) + len(delta.removed_blocks) + len(delta.updated_blocks),
                "reused_blocks": len(reused_blocks),
                "recomputed_blocks": recomputed_count,
                "snapshot_load_time": snapshot_load_time,
                "snapshot_save_time": snapshot_save_time,
                "pipeline_speedup": speedup,
            })

            return PipelineResult(
                status=PipelineStatus.COMPLETED,
                execution_id=execution_id,
                assembly_result=assembly_res,
            )

        except Exception as e:
            logger.error(f"Incremental Context Update {execution_id} failed: {e}")
            latency = (time.time() - t_start) * 1000
            await self._publish(PipelineFailed(execution_id, "incremental_update", str(e), latency))
            return PipelineResult(
                status=PipelineStatus.FAILED,
                execution_id=execution_id,
                error=str(e),
                failed_stage="incremental_update",
            )

    async def _publish(self, event: Any) -> None:
        if self._event_bus is not None:
            try:
                await self._event_bus.publish(event)
            except Exception:
                pass
