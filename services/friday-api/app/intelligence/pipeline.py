import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Awaitable

from loguru import logger

from app.intent.analyzer import RuleBasedIntentAnalyzer, IntentResult
from app.context.manager import StrategyManager
from app.context.base import StrategyConfig
from app.extraction.registry import ExtractorRegistry
from app.ranking.ranker import ContextRanker
from app.budget.allocator import AdaptiveTokenBudgetAllocator
from app.budget.base import BudgetConfig
from app.validation.validator import ContextValidator
from app.compression.compressor import ContextCompressor
from app.compression.base import CompressionPolicy, CompressedBlock
from app.assembly.assembler import PromptAssembler
from app.cache.cache import ContextCache
from app.cache.base import CacheKey, CacheLevel, DEFAULT_CACHE_TTL, compute_context_hash

from app.intelligence.events import (
    STAGE_NAMES,
    PipelineStarted,
    PipelineStageStarted,
    PipelineStageCompleted,
    PipelineCompleted,
    PipelineFailed,
    PipelineCancelled,
)
from app.events.bus import EventBus


class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PipelineMetrics:
    execution_id: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0
    intent_latency_ms: float = 0.0
    strategy_latency_ms: float = 0.0
    extraction_latency_ms: float = 0.0
    ranking_latency_ms: float = 0.0
    budget_latency_ms: float = 0.0
    validation_latency_ms: float = 0.0
    compression_latency_ms: float = 0.0
    assembly_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    raw_tokens: int = 0
    ranked_tokens: int = 0
    validated_tokens: int = 0
    compressed_tokens: int = 0
    assembled_tokens: int = 0
    memory_usage_estimate: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def stage_latency_ms(self) -> Dict[str, float]:
        return {
            "intent_analysis": self.intent_latency_ms,
            "strategy_resolution": self.strategy_latency_ms,
            "context_extraction": self.extraction_latency_ms,
            "context_ranking": self.ranking_latency_ms,
            "token_budget_allocation": self.budget_latency_ms,
            "context_validation": self.validation_latency_ms,
            "context_compression": self.compression_latency_ms,
            "prompt_assembly": self.assembly_latency_ms,
        }


@dataclass
class PipelineResult:
    status: PipelineStatus = PipelineStatus.PENDING
    execution_id: str = ""
    assembly_result: Any = None
    metrics: Optional[PipelineMetrics] = None
    error: Optional[str] = None
    failed_stage: str = ""


@dataclass
class PipelineExecutionContext:
    execution_id: str = ""
    user_query: str = ""
    session_id: str = ""
    provider: str = "gemini"
    workflow_state: Optional[Dict[str, Any]] = None
    cancellation_token: Any = None
    timeout: float = 120.0

    intent_result: Any = None
    strategy_config: Any = None
    strategy_policy: Any = None
    extraction_result: Any = None
    ranking_result: Any = None
    allocation_result: Any = None
    validation_result: Any = None
    compression_result: Any = None


class _CancellationToken:
    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled


def map_extractor_to_cache_level(extractor_name: str) -> CacheLevel:
    name = extractor_name.lower()
    if "memory" in name:
        return CacheLevel.MEMORY
    elif "knowledge" in name:
        return CacheLevel.KNOWLEDGE
    elif "workflow" in name:
        return CacheLevel.WORKFLOW
    elif "desktop" in name or "browser" in name or "terminal" in name:
        return CacheLevel.DESKTOP
    elif "mission" in name:
        return CacheLevel.MISSION
    elif "voice" in name or "conversation" in name:
        return CacheLevel.CONVERSATION
    else:
        return CacheLevel.MEMORY


class IntelligencePipeline:
    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self._event_bus = event_bus
        self._metrics_history: List[PipelineMetrics] = []
        self._cancellation_count: int = 0
        self._failure_count: int = 0
        self._execution_count: int = 0

    async def start(self) -> None:
        logger.info("Intelligence Pipeline started.")

    async def shutdown(self) -> None:
        logger.info("Intelligence Pipeline shut down.")

    def health(self) -> dict:
        total = self._execution_count or 1
        return {
            "status": "HEALTHY",
            "details": {
                "total_executions": self._execution_count,
                "total_failures": self._failure_count,
                "total_cancellations": self._cancellation_count,
                "average_latency_ms": (
                    sum(m.total_latency_ms for m in self._metrics_history[-100:]) /
                    min(len(self._metrics_history[-100:]), 1)
                ) if self._metrics_history else 0.0,
                "failure_rate": round(self._failure_count / total, 4),
            },
        }

    async def execute(
        self,
        user_query: str,
        session_id: str = "",
        provider: str = "gemini",
        workflow_state: Optional[Dict[str, Any]] = None,
        timeout: float = 120.0,
    ) -> PipelineResult:
        execution_id = str(uuid.uuid4())
        cancel_token = _CancellationToken()
        ctx = PipelineExecutionContext(
            execution_id=execution_id,
            user_query=user_query,
            session_id=session_id,
            provider=provider,
            workflow_state=workflow_state,
            cancellation_token=cancel_token,
            timeout=timeout,
        )
        metrics = PipelineMetrics(execution_id=execution_id, started_at=time.time())
        self._execution_count += 1

        await self._publish(PipelineStarted(
            execution_id=execution_id,
            request=user_query,
            session_id=session_id,
            provider=provider,
        ))

        try:
            result = await asyncio.wait_for(
                self._run_pipeline(ctx, metrics, cancel_token),
                timeout=timeout,
            )
            if cancel_token.cancelled:
                result = self._build_cancelled_result(execution_id, metrics, "")
            self._metrics_history.append(metrics)
            return result
        except asyncio.TimeoutError:
            cancel_token.cancel()
            logger.warning(f"Pipeline {execution_id} timed out after {timeout}s")
            self._cancellation_count += 1
            metrics.completed_at = time.time()
            metrics.total_latency_ms = (metrics.completed_at - metrics.started_at) * 1000
            await self._publish(PipelineCancelled(
                execution_id=execution_id, stage="",
                total_latency_ms=metrics.total_latency_ms,
            ))
            self._metrics_history.append(metrics)
            return PipelineResult(
                status=PipelineStatus.CANCELLED,
                execution_id=execution_id,
                metrics=metrics,
            )
        except Exception as e:
            logger.error(f"Pipeline {execution_id} failed: {e}")
            self._failure_count += 1
            result = PipelineResult(
                status=PipelineStatus.FAILED,
                execution_id=execution_id,
                metrics=metrics,
                error=str(e),
            )
            await self._publish(PipelineFailed(
                execution_id=execution_id, error=str(e),
                total_latency_ms=metrics.total_latency_ms,
            ))
            self._metrics_history.append(metrics)
            return result

    async def _run_pipeline(
        self,
        ctx: PipelineExecutionContext,
        metrics: PipelineMetrics,
        cancel_token: _CancellationToken,
    ) -> PipelineResult:
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

        intent_analyzer = get_svc("intent_analyzer")
        strategy_manager = get_svc("strategy_manager")
        extractor_registry = get_svc("extractor_registry")
        context_ranker = get_svc("context_ranker")
        token_allocator = get_svc("token_allocator")
        context_validator = get_svc("context_validator")
        context_compressor = get_svc("context_compressor")
        prompt_assembler = get_svc("prompt_assembler")
        context_cache = get_svc("context_cache")

        # ── Stage 1: Intent Analysis ──────────────────────────────────────────
        if cancel_token.cancelled:
            return await self._abort_cancelled(ctx, metrics, "intent_analysis")
        await self._publish(PipelineStageStarted(ctx.execution_id, "intent_analysis"))
        t0 = time.time()
        try:
            if intent_analyzer is None:
                intent_analyzer = RuleBasedIntentAnalyzer()
            intent_result = await intent_analyzer.analyze(ctx.user_query)
            ctx.intent_result = intent_result
            metrics.raw_tokens = len(ctx.user_query) // 4
        except Exception as e:
            return await self._abort_failed(ctx, metrics, "intent_analysis", str(e))
        metrics.intent_latency_ms = (time.time() - t0) * 1000
        await self._publish(PipelineStageCompleted(ctx.execution_id, "intent_analysis", metrics.intent_latency_ms))

        # ── Stage 2: Strategy Resolution ──────────────────────────────────────
        if cancel_token.cancelled:
            return await self._abort_cancelled(ctx, metrics, "strategy_resolution")
        await self._publish(PipelineStageStarted(ctx.execution_id, "strategy_resolution"))
        t0 = time.time()
        try:
            if strategy_manager is None:
                strategy_manager = StrategyManager()
            strategy = strategy_manager.get_strategy(intent_result.intent)
            ctx.strategy_config = strategy.get_config()
            ctx.strategy_policy = strategy
        except Exception as e:
            return await self._abort_failed(ctx, metrics, "strategy_resolution", str(e))
        metrics.strategy_latency_ms = (time.time() - t0) * 1000
        await self._publish(PipelineStageCompleted(ctx.execution_id, "strategy_resolution", metrics.strategy_latency_ms))

        # ── Stage 3: Context Extraction (with cache) ─────────────────────────
        if cancel_token.cancelled:
            return await self._abort_cancelled(ctx, metrics, "context_extraction")
        await self._publish(PipelineStageStarted(ctx.execution_id, "context_extraction"))
        t0 = time.time()
        try:
            if extractor_registry is None:
                extractor_registry = ExtractorRegistry()
            if context_cache is None:
                context_cache = ContextCache()
                await context_cache.start()
                ctx._local_cache = context_cache

            extractor_names = ctx.strategy_config.extractors if ctx.strategy_config else []
            cached_blocks = []
            extractors_to_run = []

            for ext_name in extractor_names:
                cache_key = CacheKey(
                    session_id=ctx.session_id,
                    intent=ctx.intent_result.intent.value if ctx.intent_result else "",
                    strategy=ctx.strategy_policy.intent_type.value if ctx.strategy_policy else "",
                    provider=ctx.provider,
                    extractor=ext_name,
                    context_hash=compute_context_hash(ctx.user_query),
                )
                level = map_extractor_to_cache_level(ext_name)
                entry = await context_cache.get(cache_key, level)
                if entry is not None:
                    cached_blocks.extend(entry.value)
                    metrics.warnings.append(f"Cache hit for extractor: {ext_name}")
                else:
                    extractors_to_run.append(ext_name)

            if extractors_to_run:
                config = StrategyConfig(
                    extractors=extractors_to_run,
                    token_budget=ctx.strategy_config.token_budget if ctx.strategy_config else None,
                    retrieval_priority=ctx.strategy_config.retrieval_priority if ctx.strategy_config else None,
                    compression_policy=ctx.strategy_config.compression_policy if ctx.strategy_config else None,
                    cache_policy=ctx.strategy_config.cache_policy if ctx.strategy_config else None,
                )
                fresh_result = await extractor_registry.extract_for_strategy(
                    ctx.user_query, config,
                )
                fresh_blocks = fresh_result.blocks
                failures = fresh_result.failures

                for ext_name in extractors_to_run:
                    prefix = ext_name.split("_")[0]
                    ext_blocks = [b for b in fresh_blocks if b.source.startswith(prefix) or (("/" in b.source) and b.source.split("/")[0] == prefix)]
                    if ext_blocks:
                        cache_key = CacheKey(
                            session_id=ctx.session_id,
                            intent=ctx.intent_result.intent.value if ctx.intent_result else "",
                            strategy=ctx.strategy_policy.intent_type.value if ctx.strategy_policy else "",
                            provider=ctx.provider,
                            extractor=ext_name,
                            context_hash=compute_context_hash(ctx.user_query),
                        )
                        level = map_extractor_to_cache_level(ext_name)
                        await context_cache.set(cache_key, ext_blocks, level)
            else:
                fresh_blocks = []
                failures = []

            all_blocks = cached_blocks + fresh_blocks
            from app.extraction.base import ExtractionResult
            extraction_result = ExtractionResult(blocks=all_blocks, failures=failures)
            ctx.extraction_result = extraction_result
            metrics.raw_tokens = sum(
                b.estimated_tokens for b in extraction_result.blocks
            )
        except Exception as e:
            return await self._abort_failed(ctx, metrics, "context_extraction", str(e))
        metrics.extraction_latency_ms = (time.time() - t0) * 1000
        await self._publish(PipelineStageCompleted(ctx.execution_id, "context_extraction", metrics.extraction_latency_ms))

        # ── Stage 4: Context Ranking (with cache) ────────────────────────────
        if cancel_token.cancelled:
            return await self._abort_cancelled(ctx, metrics, "context_ranking")
        await self._publish(PipelineStageStarted(ctx.execution_id, "context_ranking"))
        t0 = time.time()
        try:
            if context_ranker is None:
                context_ranker = ContextRanker()
            ranking_cache_key = CacheKey(
                session_id=ctx.session_id,
                intent=ctx.intent_result.intent.value if ctx.intent_result else "",
                strategy=ctx.strategy_policy.intent_type.value if ctx.strategy_policy else "",
                provider=ctx.provider,
                extractor="ranker",
                context_hash=compute_context_hash(extraction_result.blocks),
            )
            ranking_entry = await context_cache.get(ranking_cache_key, CacheLevel.RANKING_RESULTS) if context_cache else None
            if ranking_entry is not None:
                ranking_result = ranking_entry.value
                metrics.warnings.append("Cache hit for ranking result")
            else:
                ranking_result = context_ranker.rank(
                    extraction_result.blocks,
                    query=ctx.user_query,
                )
                if context_cache:
                    await context_cache.set(ranking_cache_key, ranking_result, CacheLevel.RANKING_RESULTS)
            ctx.ranking_result = ranking_result
            metrics.ranked_tokens = sum(
                rb.block.estimated_tokens for rb in ranking_result.ranked_blocks
            )
        except Exception as e:
            return await self._abort_failed(ctx, metrics, "context_ranking", str(e))
        metrics.ranking_latency_ms = (time.time() - t0) * 1000
        await self._publish(PipelineStageCompleted(ctx.execution_id, "context_ranking", metrics.ranking_latency_ms))

        # ── Stage 5: Token Budget Allocation ──────────────────────────────────
        if cancel_token.cancelled:
            return await self._abort_cancelled(ctx, metrics, "token_budget_allocation")
        await self._publish(PipelineStageStarted(ctx.execution_id, "token_budget_allocation"))
        t0 = time.time()
        try:
            if token_allocator is None:
                token_allocator = AdaptiveTokenBudgetAllocator()
            budget_config = BudgetConfig.for_model(ctx.provider)
            allocation_result = token_allocator.allocate(
                ranking_result.ranked_blocks,
                config=budget_config,
                strategy=ctx.strategy_config,
            )
            ctx.allocation_result = allocation_result
        except Exception as e:
            return await self._abort_failed(ctx, metrics, "token_budget_allocation", str(e))
        metrics.budget_latency_ms = (time.time() - t0) * 1000
        await self._publish(PipelineStageCompleted(ctx.execution_id, "token_budget_allocation", metrics.budget_latency_ms))

        # ── Stage 6: Context Validation ───────────────────────────────────────
        if cancel_token.cancelled:
            return await self._abort_cancelled(ctx, metrics, "context_validation")
        await self._publish(PipelineStageStarted(ctx.execution_id, "context_validation"))
        t0 = time.time()
        try:
            if context_validator is None:
                context_validator = ContextValidator()
            validation_result = context_validator.validate(
                allocation_result.selected_blocks,
                strategy=ctx.strategy_config,
            )
            ctx.validation_result = validation_result
            metrics.validated_tokens = sum(
                ab.allocated_tokens for ab in validation_result.valid_blocks
            )
            if validation_result.report and validation_result.report.warnings:
                metrics.warnings.extend(validation_result.report.warnings)
        except Exception as e:
            return await self._abort_failed(ctx, metrics, "context_validation", str(e))
        metrics.validation_latency_ms = (time.time() - t0) * 1000
        await self._publish(PipelineStageCompleted(ctx.execution_id, "context_validation", metrics.validation_latency_ms))

        # ── Stage 7: Context Compression (with cache) ────────────────────────
        if cancel_token.cancelled:
            return await self._abort_cancelled(ctx, metrics, "context_compression")
        await self._publish(PipelineStageStarted(ctx.execution_id, "context_compression"))
        t0 = time.time()
        try:
            if context_compressor is None:
                context_compressor = ContextCompressor()
            compression_cache_key = CacheKey(
                session_id=ctx.session_id,
                intent=ctx.intent_result.intent.value if ctx.intent_result else "",
                strategy=ctx.strategy_policy.intent_type.value if ctx.strategy_policy else "",
                provider=ctx.provider,
                extractor="compressor",
                context_hash=compute_context_hash(validation_result.valid_blocks),
            )
            compression_entry = await context_cache.get(compression_cache_key, CacheLevel.COMPRESSED_CONTEXT) if context_cache else None
            if compression_entry is not None:
                compression_result = compression_entry.value
                metrics.warnings.append("Cache hit for compression result")
            else:
                compression_result = context_compressor.compress(
                    validation_result.valid_blocks,
                    policy=ctx.strategy_config.compression_policy if ctx.strategy_config else CompressionPolicy.STANDARD,
                    strategy=ctx.strategy_config,
                )
                if context_cache:
                    await context_cache.set(compression_cache_key, compression_result, CacheLevel.COMPRESSED_CONTEXT)
            ctx.compression_result = compression_result
            metrics.compressed_tokens = compression_result.total_compressed_tokens
            if compression_result.report and compression_result.report.warnings:
                metrics.warnings.extend(compression_result.report.warnings)
        except Exception as e:
            logger.warning(f"Compression failed, falling back to validated blocks: {e}")
            fallback_blocks = []
            for ab in validation_result.valid_blocks:
                cb = CompressedBlock(
                    block=ab,
                    original_tokens=ab.allocated_tokens,
                    compressed_tokens=ab.allocated_tokens,
                    policy_applied="none",
                )
                fallback_blocks.append(cb)
            ctx.compression_result = type("FallbackCompressionResult", (), {
                "compressed_blocks": fallback_blocks,
                "report": None,
                "total_original_tokens": sum(ab.allocated_tokens for ab in validation_result.valid_blocks),
                "total_compressed_tokens": sum(ab.allocated_tokens for ab in validation_result.valid_blocks),
            })()
            metrics.warnings.append(f"Compression failed, used validated blocks: {e}")
        metrics.compression_latency_ms = (time.time() - t0) * 1000
        await self._publish(PipelineStageCompleted(ctx.execution_id, "context_compression", metrics.compression_latency_ms))

        # ── Stage 8: Prompt Assembly ──────────────────────────────────────────
        if cancel_token.cancelled:
            return await self._abort_cancelled(ctx, metrics, "prompt_assembly")
        await self._publish(PipelineStageStarted(ctx.execution_id, "prompt_assembly"))
        t0 = time.time()
        try:
            if prompt_assembler is None:
                prompt_assembler = PromptAssembler()
            assembly_result = prompt_assembler.assemble(
                ctx.compression_result.compressed_blocks,
                compression_report=ctx.compression_result.report,
                budget_report=ctx.allocation_result.report if ctx.allocation_result else None,
                strategy=ctx.strategy_config,
                provider=ctx.provider,
            )
            metrics.assembled_tokens = assembly_result.report.prompt_tokens if assembly_result.report else 0
        except Exception as e:
            return await self._abort_failed(ctx, metrics, "prompt_assembly", str(e))
        metrics.assembly_latency_ms = (time.time() - t0) * 1000
        await self._publish(PipelineStageCompleted(ctx.execution_id, "prompt_assembly", metrics.assembly_latency_ms))

        # ── Complete ──────────────────────────────────────────────────────────
        metrics.completed_at = time.time()
        metrics.total_latency_ms = (metrics.completed_at - metrics.started_at) * 1000
        await self._cleanup_local_cache(ctx)

        result = PipelineResult(
            status=PipelineStatus.COMPLETED,
            execution_id=ctx.execution_id,
            assembly_result=assembly_result,
            metrics=metrics,
        )
        await self._publish(PipelineCompleted(
            execution_id=ctx.execution_id,
            total_latency_ms=metrics.total_latency_ms,
            prompt_tokens=metrics.assembled_tokens,
            status="completed",
        ))
        return result

    async def _cleanup_local_cache(self, ctx: PipelineExecutionContext) -> None:
        local_cache = getattr(ctx, "_local_cache", None)
        if local_cache is not None:
            try:
                await local_cache.shutdown()
            except Exception:
                pass

    async def _abort_failed(
        self, ctx: PipelineExecutionContext, metrics: PipelineMetrics, stage: str, error: str
    ) -> PipelineResult:
        metrics.completed_at = time.time()
        metrics.total_latency_ms = (metrics.completed_at - metrics.started_at) * 1000
        await self._cleanup_local_cache(ctx)
        metrics.errors.append(f"[{stage}] {error}")
        self._failure_count += 1
        await self._publish(PipelineFailed(
            execution_id=ctx.execution_id, stage=stage, error=error,
            total_latency_ms=metrics.total_latency_ms,
        ))
        return PipelineResult(
            status=PipelineStatus.FAILED,
            execution_id=ctx.execution_id,
            metrics=metrics,
            error=error,
            failed_stage=stage,
        )

    async def _abort_cancelled(
        self, ctx: PipelineExecutionContext, metrics: PipelineMetrics, stage: str
    ) -> PipelineResult:
        metrics.completed_at = time.time()
        metrics.total_latency_ms = (metrics.completed_at - metrics.started_at) * 1000
        await self._cleanup_local_cache(ctx)
        self._cancellation_count += 1
        await self._publish(PipelineCancelled(
            execution_id=ctx.execution_id, stage=stage,
            total_latency_ms=metrics.total_latency_ms,
        ))
        return PipelineResult(
            status=PipelineStatus.CANCELLED,
            execution_id=ctx.execution_id,
            metrics=metrics,
            failed_stage=stage,
        )

    def cancel(self, execution_id: str) -> None:
        logger.info(f"Cancellation requested for execution {execution_id}")

    async def _publish(self, event: Any) -> None:
        if self._event_bus is not None:
            try:
                await self._event_bus.publish(event)
            except Exception:
                pass
