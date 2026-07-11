from __future__ import annotations

from dataclasses import dataclass
from typing import List
from .contracts import WorkUnit


@dataclass(frozen=True)
class ModelRoute:
    model: str
    reason: str
    fallback_model: str


def route_model(work_unit: WorkUnit, allowed_models: List[str] | None = None) -> ModelRoute:
    allowed_models = allowed_models or ["tiny", "small", "medium", "frontier"]
    text = str(work_unit.payload or "").lower()
    if any(word in text for word in ["legal", "medical", "financial advice", "safety critical"]):
        chosen = "frontier" if "frontier" in allowed_models else allowed_models[-1]
        return ModelRoute(chosen, "high_risk_task_uses_strongest_allowed", "frontier")
    if any(word in text for word in ["classify", "label", "extract"]):
        chosen = "small" if "small" in allowed_models else allowed_models[0]
        return ModelRoute(chosen, "structured_easy_task", "frontier")
    chosen = "medium" if "medium" in allowed_models else allowed_models[-1]
    return ModelRoute(chosen, "general_task_default", "frontier")
