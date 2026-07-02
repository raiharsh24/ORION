from typing import Dict, Any, List, Set

class PlanningRules:
    @staticmethod
    def evaluate(
        user_query: str,
        intent_type: str,
        strategy_config: Any,
        cache_state: Dict[str, Any],
        snapshot_available: bool,
        recommendations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        stages = {"intent", "strategy", "budget", "assembly"}
        enabled_extractors = []
        skipped_stages = []
        optimization_actions = []
        cache_probability = 0.0

        query_lower = user_query.lower()
        intent_lower = intent_type.lower() if intent_type else ""

        # 1. Math query heuristic
        is_math = "math" in intent_lower or "calculate" in intent_lower or any(op in query_lower for op in ["+", "-", "*", "/", "=", "solve"])
        
        # 2. Desktop request heuristic
        is_desktop = "desktop" in intent_lower or any(word in query_lower for word in ["click", "open window", "screenshot", "type"])
        
        # 3. Mission request heuristic
        is_mission = "mission" in intent_lower or any(word in query_lower for word in ["goal", "execute mission", "objective"])

        if is_math:
            skipped_stages.extend(["extraction", "ranking", "validation", "compression"])
            cache_probability = 1.0
        elif is_desktop:
            stages.update({"extraction", "ranking", "validation", "assembly"})
            enabled_extractors = ["desktop_extractor"]
        elif is_mission:
            stages.update({"extraction", "ranking", "validation", "compression", "assembly"})
            enabled_extractors = ["mission_extractor", "workflow_extractor", "memory_extractor", "knowledge_extractor"]
        else:
            stages.update({"extraction", "ranking", "validation", "compression", "assembly"})
            if strategy_config:
                enabled_extractors = list(strategy_config.extractors)
            else:
                enabled_extractors = ["memory_extractor", "knowledge_extractor"]

        # Parse Optimizer Recommendations
        skip_expensive = False
        reuse_ranking = False
        disable_compression = False
        
        for rec in recommendations:
            action = rec.get("action")
            if action == "skip_expensive_extractors":
                skip_expensive = True
                optimization_actions.append("skip_expensive_extractors")
            elif action == "reuse_ranking":
                reuse_ranking = True
                optimization_actions.append("reuse_ranking")
            elif action == "disable_compression_passes":
                disable_compression = True
                optimization_actions.append("disable_compression")

        if skip_expensive:
            if "knowledge_extractor" in enabled_extractors:
                enabled_extractors.remove("knowledge_extractor")
                optimization_actions.append("skipped knowledge_extractor")

        if disable_compression:
            stages.discard("compression")
            skipped_stages.append("compression")

        if reuse_ranking:
            stages.discard("ranking")
            skipped_stages.append("ranking")

        # Snapshot / Incremental Update rule
        early_exit = False
        if snapshot_available:
            stages.add("incremental_update")
            
            all_cached = True
            for ext in enabled_extractors:
                if not cache_state.get(ext, False):
                    all_cached = False
            
            if all_cached and enabled_extractors:
                for stg in ["extraction", "ranking", "validation"]:
                    if stg in stages:
                        stages.discard(stg)
                        skipped_stages.append(stg)
                early_exit = True
                cache_probability = 1.0
                optimization_actions.append("early_exit_on_cache_hit")

        return {
            "stages": stages,
            "enabled_extractors": enabled_extractors,
            "skipped_stages": skipped_stages,
            "optimization_actions": optimization_actions,
            "early_exit": early_exit,
            "cache_probability": cache_probability,
        }
