from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List
from .contracts import Contract, WorkUnit, WorkUnitKind


@dataclass(frozen=True)
class PolicyDecision:
    contract: Contract
    allowed_actions: List[str]
    denied_actions: List[str]
    policy_bundle_id: str = "default"
    reasons: List[str] = field(default_factory=list)
    cache_domain: str = "tenant_namespace"
    dedupe_domain: str = "tenant"


def evaluate_policy(work_unit: WorkUnit) -> PolicyDecision:
    """Reference policy evaluator with safe defaults."""
    if work_unit.policy_context.get("legal_hold") is True:
        return PolicyDecision(
            contract=Contract.EXACT_BYTES,
            allowed_actions=["hash", "content_defined_chunk", "dedupe_same_tenant", "zstd"],
            denied_actions=["semantic_cache", "semantic_summary", "lossy_transcode", "delete"],
            reasons=["legal_hold_forces_exact_bytes"],
        )

    if work_unit.requested_contract is not None:
        requested = work_unit.requested_contract
    elif work_unit.kind in {WorkUnitKind.PROMPT_REQUEST, WorkUnitKind.COMPLETION_RESPONSE}:
        requested = Contract.SEMANTIC
    else:
        requested = Contract.EXACT_BYTES

    if requested == Contract.SEMANTIC and work_unit.kind == WorkUnitKind.PROMPT_REQUEST:
        return PolicyDecision(
            contract=Contract.SEMANTIC,
            allowed_actions=["normalize_prompt", "exact_cache_lookup", "context_compile", "model_route", "verify", "cache_store"],
            denied_actions=["cross_tenant_cache"],
            reasons=["prompt_semantic_contract_allowed_same_tenant"],
        )

    return PolicyDecision(
        contract=Contract.EXACT_BYTES if requested == Contract.EXACT_BYTES else requested,
        allowed_actions=["hash", "content_defined_chunk", "dedupe_same_tenant", "zstd", "manifest"],
        denied_actions=["semantic_cache", "semantic_summary", "lossy_transcode", "cross_tenant_dedupe"],
        reasons=["safe_default_exact_or_requested_contract"],
    )
