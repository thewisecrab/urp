from __future__ import annotations

from dataclasses import dataclass, field
import re
import threading
from typing import Dict


@dataclass
class Metrics:
    counters: Dict[str, float] = field(default_factory=dict)
    gauges: Dict[str, float] = field(default_factory=dict)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)

    def inc(self, name: str, value: float = 1.0) -> None:
        _validate_metric(name, value)
        with self._lock:
            self.counters[name] = self.counters.get(name, 0.0) + value

    def set(self, name: str, value: float) -> None:
        _validate_metric(name, value)
        with self._lock:
            self.gauges[name] = value

    def snapshot(self) -> Dict[str, Dict[str, float]]:
        with self._lock:
            return {"counters": dict(self.counters), "gauges": dict(self.gauges)}

    def prometheus(self) -> str:
        snapshot = self.snapshot()
        lines = []
        for name, value in sorted(snapshot["counters"].items()):
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value:g}")
        for name, value in sorted(snapshot["gauges"].items()):
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value:g}")
        return "\n".join(lines) + ("\n" if lines else "")


GLOBAL_METRICS = Metrics()


def _validate_metric(name: str, value: float) -> None:
    if re.fullmatch(r"[a-zA-Z_:][a-zA-Z0-9_:]*", name) is None:
        raise ValueError(f"invalid Prometheus metric name: {name}")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError("metric values must be numeric")


def default_metric_names() -> list[str]:
    return [
        "urp_work_units_total",
        "urp_work_unit_bytes_in_total",
        "urp_work_unit_bytes_stored_total",
        "urp_bytes_avoided_total",
        "urp_chunks_total",
        "urp_chunk_dedupe_hits_total",
        "urp_policy_denials_total",
        "urp_verifier_failures_total",
        "urp_cache_hits_total",
        "urp_cache_misses_total",
        "urp_ai_input_tokens_total",
        "urp_ai_context_tokens_removed_total",
        "urp_ai_large_model_calls_total",
        "urp_ai_large_model_calls_avoided_total",
        "urp_ai_fallbacks_total",
        "urp_scheduler_jobs_shifted_total",
        "urp_lakehouse_files_compacted_total",
        "urp_training_samples_deduped_total",
        "urp_checkpoint_bytes_avoided_total",
        "urp_manifest_write_seconds",
        "urp_ledger_events_total",
    ]
