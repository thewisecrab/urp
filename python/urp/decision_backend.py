"""Local interfaces for a future calibrated router and semantic verifier.

The default backend is the keyword router plus the lexical Jaccard scorer.
It does not call a vendor API, read credentials, or open a network connection.
"""

from __future__ import annotations

from typing import Any, List, Protocol

from .ai_router import KeywordModelRouter, ModelRoute
from .contracts import WorkUnit
from .semantic_cache import semantic_similarity
from .verifiers import VerificationResult, verify_non_empty_text


class DecisionBackend(Protocol):
    def route(
        self,
        work_unit: WorkUnit,
        allowed_models: List[str] | None = None,
        prompt_text: str | None = None,
    ) -> ModelRoute:
        ...

    def semantic_score(self, left: str, right: str) -> float:
        ...

    def verify(self, value: Any) -> VerificationResult:
        ...


class KeywordDecisionBackend:
    """Adapter around the fixed keyword router and lexical cache score.

    ``verify`` checks non-empty text. It is not a calibrated task verifier.
    """

    def __init__(self) -> None:
        self._router = KeywordModelRouter()

    def route(
        self,
        work_unit: WorkUnit,
        allowed_models: List[str] | None = None,
        prompt_text: str | None = None,
    ) -> ModelRoute:
        return self._router.route(work_unit, allowed_models, prompt_text)

    def semantic_score(self, left: str, right: str) -> float:
        return semantic_similarity(left, right)

    def verify(self, value: Any) -> VerificationResult:
        if isinstance(value, dict):
            try:
                value = value["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                return VerificationResult(False, "decision_backend@1", "missing_chat_completion_content")
        return verify_non_empty_text(str(value))


class BackendSimilarityScorer:
    def __init__(self, backend: DecisionBackend) -> None:
        self._backend = backend

    def score(self, left: str, right: str) -> float:
        return self._backend.semantic_score(left, right)
