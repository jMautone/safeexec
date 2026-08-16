"""Prometheus exporter for execution metrics."""

from functools import lru_cache

from prometheus_client import REGISTRY as DEFAULT_REGISTRY
from prometheus_client import CollectorRegistry, Counter, Histogram


class PrometheusExecutionMetrics:
    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        registry = registry or DEFAULT_REGISTRY
        self._executions = Counter(
            "safeexec_executions_total",
            "Executions by language and outcome",
            ["language", "outcome"],
            registry=registry,
        )
        self._duration = Histogram(
            "safeexec_execution_duration_seconds",
            "Sandbox execution wall-clock duration",
            ["language"],
            registry=registry,
        )

    def record(self, language: str, outcome: str, duration_ms: int) -> None:
        self._executions.labels(language=language, outcome=outcome).inc()
        self._duration.labels(language=language).observe(duration_ms / 1000)


@lru_cache
def get_metrics() -> PrometheusExecutionMetrics:
    """Singleton against the default registry (re-registration would raise)."""
    return PrometheusExecutionMetrics()
