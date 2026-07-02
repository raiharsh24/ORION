from app.context.base import (
    ContextStrategy,
    StrategyConfig,
    TokenBudget,
    RetrievalPriority,
    CompressionPolicy,
    CachePolicy,
)
from app.intent.types import IntentType


class ConversationStrategy(ContextStrategy):
    intent_type = IntentType.CONVERSATION

    def get_config(self) -> StrategyConfig:
        return StrategyConfig(
            extractors=["conversation_history_extractor", "user_preference_extractor"],
            token_budget=TokenBudget(
                total=4096,
                system=256,
                conversation_history=2048,
                working_memory=256,
                retrieved_context=512,
                instructions=256,
                reserved=768,
            ),
            retrieval_priority=RetrievalPriority(sources=[
                "session_history",
                "user_preferences",
                "working_memory",
            ]),
            compression_policy=CompressionPolicy(strategy="summarize", max_tokens=2048, threshold=0.8),
            cache_policy=CachePolicy(ttl_seconds=60, max_entries=100, invalidation="lru"),
        )


class CodingStrategy(ContextStrategy):
    intent_type = IntentType.CODING

    def get_config(self) -> StrategyConfig:
        return StrategyConfig(
            extractors=[
                "code_context_extractor",
                "file_tree_extractor",
                "recent_changes_extractor",
                "terminal_output_extractor",
            ],
            token_budget=TokenBudget(
                total=8192,
                system=1024,
                conversation_history=512,
                working_memory=1024,
                retrieved_context=3072,
                instructions=1024,
                reserved=1536,
            ),
            retrieval_priority=RetrievalPriority(sources=[
                "working_memory",
                "project_memory",
                "knowledge_base",
                "session_history",
            ]),
            compression_policy=CompressionPolicy(strategy="key_point_extraction", max_tokens=4096, threshold=0.75),
            cache_policy=CachePolicy(ttl_seconds=120, max_entries=200, invalidation="lru"),
        )


class TerminalStrategy(ContextStrategy):
    intent_type = IntentType.TERMINAL

    def get_config(self) -> StrategyConfig:
        return StrategyConfig(
            extractors=["terminal_output_extractor", "shell_history_extractor", "process_list_extractor"],
            token_budget=TokenBudget(
                total=4096,
                system=512,
                conversation_history=256,
                working_memory=1024,
                retrieved_context=1024,
                instructions=512,
                reserved=768,
            ),
            retrieval_priority=RetrievalPriority(sources=[
                "working_memory",
                "session_history",
                "project_memory",
            ]),
            compression_policy=CompressionPolicy(strategy="truncate", max_tokens=2048, threshold=0.8),
            cache_policy=CachePolicy(ttl_seconds=30, max_entries=50, invalidation="lru"),
        )


class DesktopStrategy(ContextStrategy):
    intent_type = IntentType.DESKTOP

    def get_config(self) -> StrategyConfig:
        return StrategyConfig(
            extractors=["desktop_state_extractor", "active_window_extractor", "notification_extractor"],
            token_budget=TokenBudget(
                total=4096,
                system=512,
                conversation_history=256,
                working_memory=1024,
                retrieved_context=1024,
                instructions=512,
                reserved=768,
            ),
            retrieval_priority=RetrievalPriority(sources=[
                "working_memory",
                "user_preferences",
                "session_history",
            ]),
            compression_policy=CompressionPolicy(strategy="truncate", max_tokens=2048, threshold=0.85),
            cache_policy=CachePolicy(ttl_seconds=30, max_entries=50, invalidation="lru"),
        )


class BrowserStrategy(ContextStrategy):
    intent_type = IntentType.BROWSER

    def get_config(self) -> StrategyConfig:
        return StrategyConfig(
            extractors=["web_page_extractor", "browser_state_extractor", "bookmark_extractor"],
            token_budget=TokenBudget(
                total=4096,
                system=512,
                conversation_history=256,
                working_memory=512,
                retrieved_context=1536,
                instructions=512,
                reserved=768,
            ),
            retrieval_priority=RetrievalPriority(sources=[
                "session_history",
                "user_preferences",
                "working_memory",
            ]),
            compression_policy=CompressionPolicy(strategy="summarize", max_tokens=2048, threshold=0.8),
            cache_policy=CachePolicy(ttl_seconds=60, max_entries=100, invalidation="ttl_only"),
        )


class WorkflowStrategy(ContextStrategy):
    intent_type = IntentType.WORKFLOW

    def get_config(self) -> StrategyConfig:
        return StrategyConfig(
            extractors=["workflow_state_extractor", "step_progress_extractor", "mission_context_extractor"],
            token_budget=TokenBudget(
                total=8192,
                system=1024,
                conversation_history=512,
                working_memory=1024,
                retrieved_context=3072,
                instructions=1024,
                reserved=1536,
            ),
            retrieval_priority=RetrievalPriority(sources=[
                "working_memory",
                "project_memory",
                "mission_context",
                "knowledge_base",
            ]),
            compression_policy=CompressionPolicy(strategy="key_point_extraction", max_tokens=4096, threshold=0.75),
            cache_policy=CachePolicy(ttl_seconds=120, max_entries=100, invalidation="lru"),
        )


class PlanningStrategy(ContextStrategy):
    intent_type = IntentType.PLANNING

    def get_config(self) -> StrategyConfig:
        return StrategyConfig(
            extractors=["project_state_extractor", "milestone_extractor", "resource_extractor"],
            token_budget=TokenBudget(
                total=8192,
                system=1024,
                conversation_history=1024,
                working_memory=1024,
                retrieved_context=2048,
                instructions=1024,
                reserved=2048,
            ),
            retrieval_priority=RetrievalPriority(sources=[
                "project_memory",
                "working_memory",
                "mission_context",
                "session_history",
            ]),
            compression_policy=CompressionPolicy(strategy="key_point_extraction", max_tokens=4096, threshold=0.7),
            cache_policy=CachePolicy(ttl_seconds=300, max_entries=100, invalidation="lru"),
        )


class MemoryStrategy(ContextStrategy):
    intent_type = IntentType.MEMORY

    def get_config(self) -> StrategyConfig:
        return StrategyConfig(
            extractors=["long_term_memory_extractor", "session_history_extractor", "user_preference_extractor"],
            token_budget=TokenBudget(
                total=8192,
                system=512,
                conversation_history=1024,
                working_memory=512,
                retrieved_context=4096,
                instructions=512,
                reserved=1536,
            ),
            retrieval_priority=RetrievalPriority(sources=[
                "session_history",
                "user_preferences",
                "project_memory",
                "knowledge_base",
            ]),
            compression_policy=CompressionPolicy(strategy="summarize", max_tokens=4096, threshold=0.8),
            cache_policy=CachePolicy(ttl_seconds=300, max_entries=200, invalidation="ttl_only"),
        )


class SearchStrategy(ContextStrategy):
    intent_type = IntentType.SEARCH

    def get_config(self) -> StrategyConfig:
        return StrategyConfig(
            extractors=["web_search_extractor", "knowledge_base_extractor", "documentation_extractor"],
            token_budget=TokenBudget(
                total=4096,
                system=512,
                conversation_history=256,
                working_memory=256,
                retrieved_context=2048,
                instructions=512,
                reserved=512,
            ),
            retrieval_priority=RetrievalPriority(sources=[
                "knowledge_base",
                "web_search",
                "project_memory",
                "session_history",
            ]),
            compression_policy=CompressionPolicy(strategy="summarize", max_tokens=2048, threshold=0.8),
            cache_policy=CachePolicy(ttl_seconds=120, max_entries=200, invalidation="lru"),
        )


class VisionStrategy(ContextStrategy):
    intent_type = IntentType.VISION

    def get_config(self) -> StrategyConfig:
        return StrategyConfig(
            extractors=["image_analysis_extractor", "screen_capture_extractor", "object_detection_extractor"],
            token_budget=TokenBudget(
                total=8192,
                system=1024,
                conversation_history=512,
                working_memory=1024,
                retrieved_context=3072,
                instructions=1024,
                reserved=1536,
            ),
            retrieval_priority=RetrievalPriority(sources=[
                "working_memory",
                "session_history",
                "user_preferences",
            ]),
            compression_policy=CompressionPolicy(strategy="key_point_extraction", max_tokens=4096, threshold=0.7),
            cache_policy=CachePolicy(ttl_seconds=60, max_entries=50, invalidation="lru"),
        )


class UnknownStrategy(ContextStrategy):
    intent_type = IntentType.UNKNOWN

    def get_config(self) -> StrategyConfig:
        return StrategyConfig(
            extractors=["general_context_extractor"],
            token_budget=TokenBudget(
                total=2048,
                system=256,
                conversation_history=512,
                working_memory=256,
                retrieved_context=512,
                instructions=256,
                reserved=256,
            ),
            retrieval_priority=RetrievalPriority(sources=[
                "session_history",
                "working_memory",
            ]),
            compression_policy=CompressionPolicy(strategy="truncate", max_tokens=1024, threshold=0.9),
            cache_policy=CachePolicy(ttl_seconds=30, max_entries=50, invalidation="lru"),
        )
