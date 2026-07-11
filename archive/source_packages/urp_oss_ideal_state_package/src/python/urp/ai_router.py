from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class AIRouteDecision:
    route: str
    selected_model: str | None
    fallback_model: str | None
    reasons: list[str]
    verifier_required: bool

EASY_KEYWORDS = {"summarize", "classify", "extract", "rewrite", "format", "translate"}
TOOL_KEYWORDS = {"calculate", "weather", "stock", "database", "sql", "search", "lookup"}

def route_ai_request(prompt: str, quality_required: str = "standard", latency_budget_ms: int = 2000) -> AIRouteDecision:
    lower = prompt.lower()
    reasons: list[str] = []
    if any(k in lower for k in TOOL_KEYWORDS):
        return AIRouteDecision("tool-first", None, "large-general", ["deterministic or retrieval tool may solve request"], True)
    if quality_required == "low" or any(k in lower for k in EASY_KEYWORDS):
        reasons.append("task appears routine and eligible for small-model attempt")
        return AIRouteDecision("small-model-first", "small-general", "large-general", reasons, True)
    if latency_budget_ms < 500:
        return AIRouteDecision("cache-or-small-model", "small-fast", "medium-general", ["latency budget favors small model and cache"], True)
    return AIRouteDecision("medium-with-large-fallback", "medium-general", "large-general", ["standard quality path"], True)
