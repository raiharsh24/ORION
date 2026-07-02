import time
from typing import List, Dict, Any
from app.optimizer.base import PipelineRunMetadata, OptimizationRecommendation, PerformanceAnomaly

class RecommendationEngine:
    @staticmethod
    def evaluate(summary: Dict[str, Any]) -> List[OptimizationRecommendation]:
        recommendations = []
        now = time.time()
        
        # 1. Slow Extractor Rule
        extractors_data = summary.get("extractors", {})
        for ext_name, stats in extractors_data.items():
            last_100_stats = stats.get("last_100", {})
            mean_lat = last_100_stats.get("mean", 0.0)
            p95_lat = last_100_stats.get("p95", 0.0)
            
            if mean_lat > 500.0 or p95_lat > 800.0:
                recommendations.append(OptimizationRecommendation(
                    rule_name="Slow Extractor Detected",
                    target=ext_name,
                    action="demote_priority",
                    description=f"Extractor '{ext_name}' repeatedly exceeds latency threshold (mean={mean_lat:.1f}ms, p95={p95_lat:.1f}ms). Recommend reducing priority or executing later.",
                    priority="HIGH",
                    timestamp=now,
                ))

        # 2. High Cache Hit Ratio Rule
        cache_stats = summary.get("cache_hit_ratio", {}).get("last_100", {})
        mean_cache_hit = cache_stats.get("mean", 0.0)
        if mean_cache_hit > 0.8:
            expensive = []
            for ext_name, stats in extractors_data.items():
                ext_mean = stats.get("last_100", {}).get("mean", 0.0)
                if ext_mean > 200.0:
                    expensive.append(ext_name)
            
            if expensive:
                recommendations.append(OptimizationRecommendation(
                    rule_name="High Cache Efficiency",
                    target="pipeline_orchestrator",
                    action="skip_expensive_extractors",
                    description=f"Cache hit ratio is high ({mean_cache_hit * 100:.1f}%). Recommend skipping expensive extractors: {', '.join(expensive)}.",
                    priority="MEDIUM",
                    timestamp=now,
                ))

        # 3. Compression Underrun
        token_stats = summary.get("token_utilization", {}).get("last_100", {})
        mean_token_util = token_stats.get("mean", 0.0)
        if mean_token_util < 0.5:
            recommendations.append(OptimizationRecommendation(
                rule_name="Low Token Utilization",
                target="context_compressor",
                action="disable_compression_passes",
                description=f"Token budget is consistently underutilized (mean={mean_token_util * 100:.1f}%). Recommend disabling expensive compression passes to save CPU/latency.",
                priority="LOW",
                timestamp=now,
            ))

        # 4. Lightweight Validation
        exclusion_ratio = summary.get("validation_exclusion_ratio", 0.0)
        if exclusion_ratio == 0.0 and summary.get("total_runs", 0) > 10:
            recommendations.append(OptimizationRecommendation(
                rule_name="Redundant Validation",
                target="context_validator",
                action="lightweight_validation",
                description="Context validator never filters or removes block items. Recommend switching to lightweight validation mode.",
                priority="LOW",
                timestamp=now,
            ))

        # 5. Stable Ranking
        ranking_stable_ratio = summary.get("ranking_stable_ratio", 1.0)
        if ranking_stable_ratio > 0.9 and summary.get("total_runs", 0) > 10:
            recommendations.append(OptimizationRecommendation(
                rule_name="Stable Ranking Orders",
                target="context_ranker",
                action="reuse_ranking",
                description="Ranker consistently produces identical relative orderings. Recommend reusing ranking outcomes to bypass sorting.",
                priority="MEDIUM",
                timestamp=now,
            ))

        # 6. Underused Budget
        if mean_token_util < 0.6:
            recommendations.append(OptimizationRecommendation(
                rule_name="Underutilized Token Budget",
                target="token_allocator",
                action="increase_retrieval_budget",
                description=f"Token budget is consistently underused (mean={mean_token_util * 100:.1f}%). Recommend increasing retrieval extraction depth budget limits.",
                priority="MEDIUM",
                timestamp=now,
            ))

        # 7. Budget Overflow
        if mean_token_util >= 0.95 or summary.get("timeouts", 0) > 0:
            recommendations.append(OptimizationRecommendation(
                rule_name="High Budget Pressure",
                target="token_allocator",
                action="reduce_extraction_depth",
                description=f"High token budget pressure (mean={mean_token_util * 100:.1f}%) or timeouts detected. Recommend reducing extraction depth.",
                priority="HIGH",
                timestamp=now,
            ))

        return recommendations


class AnomalyDetector:
    @staticmethod
    def detect(run: PipelineRunMetadata, summary: Dict[str, Any]) -> List[PerformanceAnomaly]:
        anomalies = []
        now = time.time()
        
        overall_latency_stats = summary.get("total_latency", {}).get("overall", {})
        mean_lat = overall_latency_stats.get("mean", 0.0)
        std_dev_lat = overall_latency_stats.get("std_dev", 0.0)
        
        if mean_lat > 0:
            threshold = max(2.0 * mean_lat, mean_lat + 3 * std_dev_lat)
            if run.total_latency_ms > threshold:
                anomalies.append(PerformanceAnomaly(
                    anomaly_type="Latency Spike",
                    metric_name="total_latency_ms",
                    value=run.total_latency_ms,
                    threshold=threshold,
                    description=f"Pipeline run total latency spiked to {run.total_latency_ms:.1f}ms (threshold={threshold:.1f}ms, mean={mean_lat:.1f}ms).",
                    timestamp=now,
                ))

        if run.is_timeout:
            anomalies.append(PerformanceAnomaly(
                anomaly_type="Extractor Timeout",
                metric_name="is_timeout",
                value=1.0,
                threshold=0.5,
                description="An active extractor failed to respond within the configured deadline limit.",
                timestamp=now,
            ))

        if run.status == "failed":
            anomalies.append(PerformanceAnomaly(
                anomaly_type="Pipeline Execution Failure",
                metric_name="status",
                value=0.0,
                threshold=1.0,
                description=f"Pipeline aborted due to unexpected runtime error: {run.error_message}",
                timestamp=now,
            ))

        return anomalies
