from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Set

from .contracts import Contract, PlanAction


@dataclass(frozen=True)
class ActionSpec:
    name: str
    supported_contracts: Set[Contract]
    risk: str = "low"
    required_verifiers: List[str] | None = None
    executor: str = "local"


class ActionRegistry:
    def __init__(self) -> None:
        self._actions: Dict[str, ActionSpec] = {}

    def register(self, spec: ActionSpec) -> None:
        self._actions[spec.name] = spec

    def get(self, name: str) -> ActionSpec:
        return self._actions[name]

    def names(self) -> List[str]:
        return sorted(self._actions)

    def allowed_for_contract(self, contract: Contract) -> List[str]:
        return [name for name, spec in self._actions.items() if contract in spec.supported_contracts]

    def validate_plan_actions(self, contract: Contract, actions: Iterable[PlanAction], denied: Iterable[str]) -> None:
        denied_set = set(denied)
        for action in actions:
            if action.type in denied_set:
                raise ValueError(f"action denied by policy: {action.type}")
            spec = self._actions.get(action.type)
            if spec is None:
                raise ValueError(f"unknown action: {action.type}")
            if contract not in spec.supported_contracts:
                raise ValueError(f"action {action.type} does not support contract {contract.value}")


def default_action_registry() -> ActionRegistry:
    exact = {Contract.EXACT_BYTES, Contract.EXACT_LOGICAL, Contract.BOUNDED_APPROX, Contract.SEMANTIC}
    semantic_only = {Contract.SEMANTIC}
    bounded = {Contract.BOUNDED_APPROX}
    registry = ActionRegistry()
    for name in [
        "hash",
        "content_defined_chunk",
        "fixed_chunk",
        "dedupe_same_tenant",
        "zstd",
        "dedupe_only_or_exact_store",
        "store_exact_ciphertext",
        "store_exact_bytes",
        "manifest",
        "verify_restore",
        "rehydrate",
    ]:
        registry.register(ActionSpec(name, exact))
    for name in [
        "normalize_prompt",
        "exact_cache_lookup",
        "context_compile",
        "tool_first_attempt",
        "model_route",
        "verify",
        "cache_store",
        "compute_manifest",
    ]:
        registry.register(ActionSpec(name, {Contract.SEMANTIC, Contract.EXACT_BYTES, Contract.EXACT_LOGICAL}, "medium"))
    registry.register(ActionSpec("semantic_cache_lookup", semantic_only, "high", ["source_consistency", "freshness_check"]))
    registry.register(ActionSpec("semantic_summary", semantic_only, "high", ["source_consistency"]))
    registry.register(ActionSpec("approximate_quantization", bounded, "high", ["error_bound"]))
    registry.register(ActionSpec("delete", {Contract.TOMBSTONE}, "high", ["retention_policy"]))
    return registry
