"""Metrics port; the exporter is an adapter detail."""

from typing import Protocol


class ExecutionMetrics(Protocol):
    def record(self, language: str, outcome: str, duration_ms: int) -> None: ...


class NullMetrics:
    def record(self, language: str, outcome: str, duration_ms: int) -> None:
        return None
