from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Dict, List
from .contracts import WorkUnit, utc_now
from .auth import current_tenant
from .storage import append_json_line, ensure_private_file, file_lock


@dataclass(frozen=True)
class ModelRoute:
    model: str
    reason: str
    fallback_model: str
    score: float = 0.5


def route_model(work_unit: WorkUnit, allowed_models: List[str] | None = None, prompt_text: str | None = None) -> ModelRoute:
    allowed_models = allowed_models or ["tiny", "small", "medium", "frontier"]
    if not allowed_models:
        raise ValueError("policy model allowlist cannot be empty")
    text = (prompt_text if prompt_text is not None else str(work_unit.payload or "")).casefold()
    if any(
        phrase in text
        for phrase in [
            "legal",
            "medical",
            "diagnosis",
            "medication",
            "financial advice",
            "investment advice",
            "safety critical",
            "self-harm",
            "emergency",
        ]
    ):
        chosen = "frontier" if "frontier" in allowed_models else allowed_models[-1]
        return ModelRoute(chosen, "high_risk_task_uses_strongest_allowed", "frontier", 0.95)
    if any(word in text for word in ["classify", "label", "extract"]):
        chosen = "small" if "small" in allowed_models else allowed_models[0]
        return ModelRoute(chosen, "structured_easy_task", "frontier", 0.75)
    chosen = "medium" if "medium" in allowed_models else allowed_models[-1]
    return ModelRoute(chosen, "general_task_default", "frontier", 0.6)


class RouteFeedbackStore:
    def __init__(self, state_dir: str | Path = ".urp") -> None:
        self.path = Path(state_dir) / "route_feedback.jsonl"
        ensure_private_file(self.path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    def record(self, work_unit: WorkUnit, route: ModelRoute, verifier_passed: bool, latency_ms: float = 0.0) -> Dict[str, object]:
        row: Dict[str, object] = {
            "created_at": utc_now(),
            "work_unit_id": work_unit.id,
            "tenant": work_unit.tenant,
            "namespace": work_unit.namespace,
            "model": route.model,
            "reason": route.reason,
            "score": route.score,
            "verifier_passed": verifier_passed,
            "latency_ms": latency_ms,
        }
        append_json_line(self.path, row, lock_path=self.lock_path)
        return row

    def summary(self, tenant: str | None = None) -> Dict[str, Dict[str, float]]:
        tenant = tenant or current_tenant()
        rows = []
        with file_lock(self.lock_path, exclusive=False):
            with self.path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        rows.append(json.loads(line))
        by_model: Dict[str, Dict[str, float]] = {}
        for row in rows:
            if tenant and row.get("tenant") != tenant:
                continue
            model = str(row["model"])
            stats = by_model.setdefault(model, {"count": 0.0, "verifier_passed": 0.0, "avg_latency_ms": 0.0})
            stats["count"] += 1
            stats["verifier_passed"] += 1 if row.get("verifier_passed") else 0
            stats["avg_latency_ms"] += float(row.get("latency_ms") or 0)
        for stats in by_model.values():
            if stats["count"]:
                stats["pass_rate"] = stats["verifier_passed"] / stats["count"]
                stats["avg_latency_ms"] = stats["avg_latency_ms"] / stats["count"]
        return by_model
