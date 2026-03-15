"""
Observability Layer - Tracing, metrics, and logging for all agents.
Provides structured telemetry without external dependencies.
"""

import time
import logging
import functools
from contextlib import contextmanager
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class Span:
    """A single trace span representing a unit of work."""

    def __init__(self, name: str, service: str):
        self.name = name
        self.service = service
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.attributes: Dict[str, Any] = {}
        self.status = "ok"
        self.error: Optional[str] = None

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def set_error(self, error: str) -> None:
        self.status = "error"
        self.error = error

    def finish(self) -> None:
        self.end_time = time.time()

    @property
    def duration_ms(self) -> float:
        end = self.end_time or time.time()
        return round((end - self.start_time) * 1000, 2)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "service": self.service,
            "start_time": self.start_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "attributes": self.attributes,
            "error": self.error,
        }


class ObservabilityLayer:
    """
    Lightweight observability for CodeDebt Guardian agents.

    Provides:
    - Span-based tracing (OpenTelemetry-inspired)
    - Operation metrics (count, avg duration, errors)
    - Structured logging
    """

    def __init__(self, service_name: str):
        self.service_name = service_name
        self._spans: List[Span] = []
        self._metrics: Dict[str, List[float]] = {}
        self._error_count: int = 0

    @contextmanager
    def trace(self, operation_name: str):
        """Context manager for tracing a code block."""
        span = Span(name=operation_name, service=self.service_name)
        try:
            logger.debug(f"[{self.service_name}] Starting: {operation_name}")
            yield span
        except Exception as e:
            span.set_error(str(e))
            self._error_count += 1
            logger.error(f"[{self.service_name}] Error in {operation_name}: {e}")
            raise
        finally:
            span.finish()
            self._spans.append(span)
            self._record_metric(operation_name, span.duration_ms)
            logger.debug(
                f"[{self.service_name}] Finished: {operation_name} "
                f"({span.duration_ms}ms, status={span.status})"
            )

    def _record_metric(self, operation: str, duration_ms: float) -> None:
        if operation not in self._metrics:
            self._metrics[operation] = []
        self._metrics[operation].append(duration_ms)

    def get_metrics(self) -> Dict[str, Any]:
        """Return aggregated metrics for all observed operations."""
        summary = {}
        for op, durations in self._metrics.items():
            summary[op] = {
                "count": len(durations),
                "avg_ms": round(sum(durations) / len(durations), 2),
                "min_ms": round(min(durations), 2),
                "max_ms": round(max(durations), 2),
                "total_ms": round(sum(durations), 2),
            }
        return {
            "service": self.service_name,
            "operations": summary,
            "total_spans": len(self._spans),
            "error_count": self._error_count,
        }

    def get_recent_spans(self, limit: int = 10) -> List[Dict]:
        """Return the most recent spans as dicts."""
        return [s.to_dict() for s in self._spans[-limit:]]
