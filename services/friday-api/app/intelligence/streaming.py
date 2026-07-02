import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, Set

from loguru import logger

from app.assembly.base import PromptSection, PromptFrame
from app.context.base import StrategyConfig
from app.budget.base import BudgetConfig
from app.extraction.base import ContextBlock, ExtractionResult
from app.cache.base import CacheKey, CacheLevel, compute_context_hash
from app.cache.cache import ContextCache
from app.events.bus import EventBus
from app.events.events import FridayEvent
from app.intent.analyzer import RuleBasedIntentAnalyzer, IntentResult
from app.context.manager import StrategyManager
from app.extraction.registry import ExtractorRegistry
from app.ranking.ranker import ContextRanker
from app.budget.allocator import AdaptiveTokenBudgetAllocator
from app.validation.validator import ContextValidator
from app.compression.compressor import ContextCompressor
from app.compression.base import CompressionPolicy, CompressedBlock
from app.assembly.assembler import PromptAssembler
from app.intelligence.pipeline import PipelineStatus, _CancellationToken, map_extractor_to_cache_level

from app.intelligence.events import (
    StreamingStarted,
    ExtractorCompleted,
    ContextUpdated,
    PromptUpdated,
    StreamingCompleted,
    PipelineStageStarted,
    PipelineStageCompleted,
    PipelineFailed,
    PipelineCancelled,
)


@dataclass
class StreamingMetrics:
    execution_id: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0
    time_to_first_context_ms: float = 0.0
    time_to_first_prompt_ms: float = 0.0
    time_to_final_prompt_ms: float = 0.0
    extractor_completion_timeline: Dict[str, float] = field(default_factory=dict)
    increment_count: int = 0
    average_update_latency_ms: float = 0.0
    total_update_time_ms: float = 0.0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    total_lookups: int = 0
    total_hits: int = 0
    total_misses: int = 0


@dataclass
class StreamingResult:
    status: PipelineStatus = PipelineStatus.PENDING
    execution_id: str = ""
    prompt_frame: PromptFrame = field(default_factory=PromptFrame)
    metrics: StreamingMetrics = field(default_factory=StreamingMetrics)
    error: Optional[str] = None
    failed_stage: str = ""


class PipelineBarrier:
    def __init__(self, extractor_names: List[str]) -> None:
        self.pending = set(extractor_names)
        self.completed = set()
        self.queue = asyncio.Queue()

    def complete(self, extractor_name: str, blocks: List[ContextBlock], latency_ms: float) -> None:
        if extractor_name in self.pending:
            self.pending.remove(extractor_name)
            self.completed.add(extractor_name)
        self.queue.put_nowait((extractor_name, blocks, latency_ms))

    def is_done(self) -> bool:
        return len(self.pending) == 0


class PipelineScheduler:
    def __init__(self, extractor_registry: ExtractorRegistry, barrier: PipelineBarrier, timeout: float) -> None:
        self.registry = extractor_registry
        self.barrier = barrier
        self.timeout = timeout
        self.tasks: List[asyncio.Task] = []

    def start_extraction(self, request: str, extractor_names: List[str]) -> None:
        for ext_name in extractor_names:
            task = asyncio.create_task(self._run_extractor(request, ext_name))
            self.tasks.append(task)

    async def _run_extractor(self, request: str, extractor_name: str) -> None:
        t0 = time.time()
        try:
            ext = self.registry.get(extractor_name)
            if ext is None:
                raise ValueError(f"Extractor '{extractor_name}' not registered")
            
            # Execute with configured timeout
            blocks = await asyncio.wait_for(ext.extract(request), timeout=self.timeout)
            latency = (time.time() - t0) * 1000
            self.barrier.complete(extractor_name, blocks, latency)
        except Exception as e:
            logger.warning(f"Extractor '{extractor_name}' failed or timed out: {e}")
            latency = (time.time() - t0) * 1000
            self.barrier.complete(extractor_name, [], latency)

    def cancel_all(self) -> None:
        for task in self.tasks:
            if not task.done():
                task.cancel()


class StreamingContextBuilder:
    def __init__(
        self,
        query: str,
        strategy_config: StrategyConfig,
        token_allocator: AdaptiveTokenBudgetAllocator,
        context_validator: ContextValidator,
        context_compressor: ContextCompressor,
        prompt_assembler: PromptAssembler,
        context_ranker: ContextRanker,
        metrics: StreamingMetrics,
        provider: str = "gemini",
        insertion_threshold: float = 0.5,
    ) -> None:
        self.query = query
        self.strategy_config = strategy_config
        self.token_allocator = token_allocator
        self.context_validator = context_validator
        self.context_compressor = context_compressor
        self.prompt_assembler = prompt_assembler
        self.context_ranker = context_ranker
        self.metrics = metrics
        self.provider = provider
        self.insertion_threshold = insertion_threshold

        self.accepted_blocks: List[Any] = []  # list of RankedContextBlock
        self.prompt_frame = PromptFrame()
        self.last_report = None
        self.budget_limit = strategy_config.token_budget.total if strategy_config and strategy_config.token_budget else 4096

    def current_estimated_tokens(self) -> int:
        return sum(rb.block.estimated_tokens for rb in self.accepted_blocks)

    def add_blocks(self, fresh_blocks: List[ContextBlock]) -> bool:
        if not fresh_blocks:
            return False

        t_start = time.time()

        # 1. Incremental Ranking
        ranking_res = self.context_ranker.rank(fresh_blocks, query=self.query)
        new_accepted = []

        for rb in ranking_res.ranked_blocks:
            current_tokens = self.current_estimated_tokens()
            remaining = self.budget_limit - current_tokens

            # Score condition: exceeds insertion_threshold
            # Budget condition: remaining budget is positive
            if remaining > 0 or rb.combined_score >= self.insertion_threshold:
                new_accepted.append(rb)

        if not new_accepted:
            return False

        # Never reorder already accepted blocks (Deterministic growth by appending)
        self.accepted_blocks.extend(new_accepted)

        # 2. Incremental Budget Allocation
        budget_config = BudgetConfig.for_model(self.provider)
        allocation_res = self.token_allocator.allocate(
            self.accepted_blocks,
            config=budget_config,
            strategy=self.strategy_config,
        )

        # 3. Incremental Validation
        validation_res = self.context_validator.validate(
            allocation_res.selected_blocks,
            strategy=self.strategy_config,
        )

        # 4. Incremental Compression
        compression_res = self.context_compressor.compress(
            validation_res.valid_blocks,
            policy=self.strategy_config.compression_policy if self.strategy_config else None,
            strategy=self.strategy_config,
        )

        # 5. Incremental Prompt Assembly
        assembly_res = self.prompt_assembler.assemble(
            compression_res.compressed_blocks,
            compression_report=compression_res.report,
            budget_report=allocation_res.report if allocation_res else None,
            strategy=self.strategy_config,
            provider=self.provider,
        )

        # Update prompt frame and compute latencies
        if assembly_res.frame:
            self.prompt_frame = assembly_res.frame
            self.last_report = assembly_res.report
            
            # Update metrics
            now_ms = (time.time() - self.metrics.started_at) * 1000
            if self.metrics.time_to_first_context_ms == 0.0:
                self.metrics.time_to_first_context_ms = now_ms
            if self.metrics.time_to_first_prompt_ms == 0.0 and self.prompt_frame.text_prompt:
                self.metrics.time_to_first_prompt_ms = now_ms

            self.metrics.increment_count += 1
            update_latency = (time.time() - t_start) * 1000
            self.metrics.total_update_time_ms += update_latency
            self.metrics.average_update_latency_ms = self.metrics.total_update_time_ms / self.metrics.increment_count
            return True
            
        return False


class StreamingPipeline:
    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self._event_bus = event_bus
        self._metrics_history: List[StreamingMetrics] = []
        self._cancellation_count: int = 0
        self._failure_count: int = 0
        self._execution_count: int = 0

    async def start(self) -> None:
        logger.info("Streaming Intelligence Pipeline started.")

    async def shutdown(self) -> None:
        logger.info("Streaming Intelligence Pipeline shut down.")

    def health(self) -> dict:
        total = self._execution_count or 1
        return {
            "status": "HEALTHY",
            "details": {
                "total_executions": self._execution_count,
                "total_failures": self._failure_count,
                "total_cancellations": self._cancellation_count,
                "average_first_context_latency_ms": (
                    sum(m.time_to_first_context_ms for m in self._metrics_history[-100:]) /
                    min(len(self._metrics_history[-100:]), 1)
                ) if self._metrics_history else 0.0,
                "average_first_prompt_latency_ms": (
                    sum(m.time_to_first_prompt_ms for m in self._metrics_history[-100:]) /
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
        insertion_threshold: float = 0.5,
        extractor_timeout: float = 10.0,
    ) -> StreamingResult:
        execution_id = str(uuid.uuid4())
        cancel_token = _CancellationToken()
        self._execution_count += 1

        metrics = StreamingMetrics(execution_id=execution_id, started_at=time.time())
        
        await self._publish(StreamingStarted(
            execution_id=execution_id,
            request=user_query,
            session_id=session_id,
        ))

        try:
            result = await asyncio.wait_for(
                self._run_streaming_pipeline(
                    execution_id, user_query, session_id, provider,
                    workflow_state, cancel_token, metrics,
                    insertion_threshold, extractor_timeout
                ),
                timeout=timeout
            )
            if cancel_token.cancelled:
                result = self._build_cancelled_result(execution_id, metrics, "")
            self._metrics_history.append(metrics)
            return result
        except asyncio.TimeoutError:
            cancel_token.cancel()
            logger.warning(f"Streaming Pipeline {execution_id} timed out after {timeout}s")
            self._cancellation_count += 1
            metrics.completed_at = time.time()
            metrics.time_to_final_prompt_ms = (metrics.completed_at - metrics.started_at) * 1000
            await self._publish(StreamingCompleted(
                execution_id=execution_id,
                total_latency_ms=metrics.time_to_final_prompt_ms,
                final_prompt_tokens=0,
            ))
            self._metrics_history.append(metrics)
            return StreamingResult(
                status=PipelineStatus.CANCELLED,
                execution_id=execution_id,
                metrics=metrics,
            )
        except Exception as e:
            logger.error(f"Streaming Pipeline {execution_id} failed: {e}")
            self._failure_count += 1
            metrics.completed_at = time.time()
            metrics.time_to_final_prompt_ms = (metrics.completed_at - metrics.started_at) * 1000
            result = StreamingResult(
                status=PipelineStatus.FAILED,
                execution_id=execution_id,
                metrics=metrics,
                error=str(e),
            )
            await self._publish(PipelineFailed(
                execution_id=execution_id, error=str(e),
                total_latency_ms=metrics.time_to_final_prompt_ms,
            ))
            self._metrics_history.append(metrics)
            return result

    async def _run_streaming_pipeline(
        self,
        execution_id: str,
        user_query: str,
        session_id: str,
        provider: str,
        workflow_state: Optional[Dict[str, Any]],
        cancel_token: _CancellationToken,
        metrics: StreamingMetrics,
        insertion_threshold: float,
        extractor_timeout: float,
    ) -> StreamingResult:
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
            return await self._abort_cancelled(metrics, "intent_analysis")
        await self._publish(PipelineStageStarted(execution_id, "intent_analysis"))
        t0 = time.time()
        try:
            if intent_analyzer is None:
                intent_analyzer = RuleBasedIntentAnalyzer()
            intent_result = await intent_analyzer.analyze(user_query)
        except Exception as e:
            return await self._abort_failed(metrics, "intent_analysis", str(e))
        intent_latency = (time.time() - t0) * 1000
        await self._publish(PipelineStageCompleted(execution_id, "intent_analysis", intent_latency))

        # ── Stage 2: Strategy Resolution ──────────────────────────────────────
        if cancel_token.cancelled:
            return await self._abort_cancelled(metrics, "strategy_resolution")
        await self._publish(PipelineStageStarted(execution_id, "strategy_resolution"))
        t0 = time.time()
        try:
            if strategy_manager is None:
                strategy_manager = StrategyManager()
            strategy = strategy_manager.get_strategy(intent_result.intent)
            strategy_config = strategy.get_config()
        except Exception as e:
            return await self._abort_failed(metrics, "strategy_resolution", str(e))
        strategy_latency = (time.time() - t0) * 1000
        await self._publish(PipelineStageCompleted(execution_id, "strategy_resolution", strategy_latency))

        # ── Setup Streaming Context Builder ──────────────────────────────────
        if context_ranker is None:
            context_ranker = ContextRanker()
        if token_allocator is None:
            token_allocator = AdaptiveTokenBudgetAllocator()
        if context_validator is None:
            context_validator = ContextValidator()
        if context_compressor is None:
            context_compressor = ContextCompressor()
        if prompt_assembler is None:
            prompt_assembler = PromptAssembler()

        builder = StreamingContextBuilder(
            query=user_query,
            strategy_config=strategy_config,
            token_allocator=token_allocator,
            context_validator=context_validator,
            context_compressor=context_compressor,
            prompt_assembler=prompt_assembler,
            context_ranker=context_ranker,
            metrics=metrics,
            provider=provider,
            insertion_threshold=insertion_threshold,
        )

        # ── Cache Lookup & Fresh Schedulers ──────────────────────────────────
        extractor_names = strategy_config.extractors if strategy_config else []
        fresh_extractors = []
        cached_blocks = []

        local_cache = None
        if context_cache is None:
            try:
                context_cache = ContextCache()
                await context_cache.start()
                local_cache = context_cache
            except Exception:
                pass

        # Check cache first
        for ext_name in extractor_names:
            cache_key = CacheKey(
                session_id=session_id,
                intent=intent_result.intent.value if intent_result else "",
                strategy=strategy.intent_type.value if strategy else "",
                provider=provider,
                extractor=ext_name,
                context_hash=compute_context_hash(user_query),
            )
            level = map_extractor_to_cache_level(ext_name)
            entry = None
            if context_cache:
                entry = await context_cache.get(cache_key, level)

            if entry is not None:
                cached_blocks.extend(entry.value)
                metrics.total_hits += 1
                await self._publish(ExtractorCompleted(execution_id, ext_name, len(entry.value), 0.0))
            else:
                fresh_extractors.append(ext_name)
                metrics.total_misses += 1

        # Feed cached blocks into builder immediately
        if cached_blocks:
            updated = builder.add_blocks(cached_blocks)
            if updated:
                await self._publish(ContextUpdated(
                    execution_id=execution_id,
                    total_blocks=len(builder.accepted_blocks),
                    estimated_tokens=builder.current_estimated_tokens(),
                ))
                await self._publish(PromptUpdated(
                    execution_id=execution_id,
                    prompt_tokens=builder.last_report.prompt_tokens if builder.last_report else 0,
                ))

        # ── Streaming Loop for Fresh Extractors ──────────────────────────────
        if fresh_extractors and extractor_registry is not None:
            barrier = PipelineBarrier(fresh_extractors)
            scheduler = PipelineScheduler(extractor_registry, barrier, extractor_timeout)

            # Start fresh extractors concurrently in the background
            scheduler.start_extraction(user_query, fresh_extractors)

            # Loop waiting for incoming blocks from barrier
            while not barrier.is_done() or not barrier.queue.empty():
                if cancel_token.cancelled:
                    scheduler.cancel_all()
                    if local_cache:
                        await local_cache.shutdown()
                    return await self._abort_cancelled(metrics, "context_extraction")

                # Check early exit when budget is filled
                if builder.current_estimated_tokens() >= builder.budget_limit:
                    logger.info("Token budget filled, ending stream early.")
                    scheduler.cancel_all()
                    break

                try:
                    ext_name, blocks, latency = await asyncio.wait_for(
                        barrier.queue.get(),
                        timeout=0.2
                    )
                    metrics.extractor_completion_timeline[ext_name] = (time.time() - metrics.started_at) * 1000

                    # Publish completed event
                    await self._publish(ExtractorCompleted(execution_id, ext_name, len(blocks), latency))

                    # Append to builder and cache results
                    if blocks:
                        updated = builder.add_blocks(blocks)
                        if updated:
                            # Cache the blocks
                            if context_cache:
                                cache_key = CacheKey(
                                    session_id=session_id,
                                    intent=intent_result.intent.value if intent_result else "",
                                    strategy=strategy.intent_type.value if strategy else "",
                                    provider=provider,
                                    extractor=ext_name,
                                    context_hash=compute_context_hash(user_query),
                                )
                                level = map_extractor_to_cache_level(ext_name)
                                await context_cache.set(cache_key, blocks, level)

                            # Publish updates
                            await self._publish(ContextUpdated(
                                execution_id=execution_id,
                                total_blocks=len(builder.accepted_blocks),
                                estimated_tokens=builder.current_estimated_tokens(),
                            ))
                            await self._publish(PromptUpdated(
                                execution_id=execution_id,
                                prompt_tokens=builder.last_report.prompt_tokens if builder.last_report else 0,
                            ))
                except asyncio.TimeoutError:
                    continue

        if local_cache:
            await local_cache.shutdown()

        # ── Finalize ──────────────────────────────────────────────────────────
        metrics.completed_at = time.time()
        metrics.time_to_final_prompt_ms = (metrics.completed_at - metrics.started_at) * 1000

        await self._publish(StreamingCompleted(
            execution_id=execution_id,
            total_latency_ms=metrics.time_to_final_prompt_ms,
            final_prompt_tokens=builder.last_report.prompt_tokens if builder.last_report else 0,
        ))

        return StreamingResult(
            status=PipelineStatus.COMPLETED,
            execution_id=execution_id,
            prompt_frame=builder.prompt_frame,
            metrics=metrics,
        )

    def cancel(self, execution_id: str) -> None:
        logger.info(f"Cancellation requested for streaming execution {execution_id}")

    async def _publish(self, event: Any) -> None:
        if self._event_bus is not None:
            try:
                await self._event_bus.publish(event)
            except Exception:
                pass

    async def _abort_failed(self, metrics: StreamingMetrics, stage: str, error: str) -> StreamingResult:
        metrics.completed_at = time.time()
        metrics.time_to_final_prompt_ms = (metrics.completed_at - metrics.started_at) * 1000
        metrics.errors.append(f"[{stage}] {error}")
        self._failure_count += 1
        await self._publish(PipelineFailed(
            execution_id=metrics.execution_id, stage=stage, error=error,
            total_latency_ms=metrics.time_to_final_prompt_ms,
        ))
        return StreamingResult(
            status=PipelineStatus.FAILED,
            execution_id=metrics.execution_id,
            metrics=metrics,
            error=error,
            failed_stage=stage,
        )

    async def _abort_cancelled(self, metrics: StreamingMetrics, stage: str) -> StreamingResult:
        metrics.completed_at = time.time()
        metrics.time_to_final_prompt_ms = (metrics.completed_at - metrics.started_at) * 1000
        self._cancellation_count += 1
        await self._publish(PipelineCancelled(
            execution_id=metrics.execution_id, stage=stage,
            total_latency_ms=metrics.time_to_final_prompt_ms,
        ))
        return StreamingResult(
            status=PipelineStatus.CANCELLED,
            execution_id=metrics.execution_id,
            metrics=metrics,
            failed_stage=stage,
        )

    def _build_cancelled_result(self, execution_id: str, metrics: StreamingMetrics, stage: str) -> StreamingResult:
        return StreamingResult(
            status=PipelineStatus.CANCELLED,
            execution_id=execution_id,
            metrics=metrics,
            failed_stage=stage,
        )
