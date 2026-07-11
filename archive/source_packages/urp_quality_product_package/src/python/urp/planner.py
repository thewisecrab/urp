from __future__ import annotations

from typing import List
from .contracts import Contract, Plan, PlanAction, WorkUnit, WorkUnitKind
from .classifier import classify
from .policy import evaluate_policy


def plan_work_unit(work_unit: WorkUnit, mode: str = "observe") -> Plan:
    classification = classify(work_unit)
    decision = evaluate_policy(work_unit)
    actions: List[PlanAction] = []

    if work_unit.kind == WorkUnitKind.PROMPT_REQUEST:
        actions.extend([
            PlanAction("normalize_prompt", True, "low", reason="stable cache key and context separation"),
            PlanAction("exact_cache_lookup", False, "low", reason="avoid repeated identical model calls"),
            PlanAction("semantic_cache_lookup", False, "medium", reason="policy-gated meaning reuse"),
            PlanAction("context_compile", False, "medium", reason="remove duplicate or irrelevant context"),
            PlanAction("tool_first_attempt", False, "low", reason="deterministic tools are cheaper and verifiable"),
            PlanAction("model_route", True, "medium", reason="choose smallest verified model path"),
            PlanAction("verify", True, "medium", reason="contract satisfaction before acceptance"),
            PlanAction("cache_store", False, "low", reason="reuse verified answer"),
        ])
        return Plan(
            work_unit_id=work_unit.id,
            contract=decision.contract,
            actions=[a for a in actions if a.type in decision.allowed_actions or a.required],
            mode=mode,
            policy_bundle_id=decision.policy_bundle_id,
            risk="medium",
            expected={"tokens_avoided_possible": True, "large_model_calls_avoided_possible": True},
            fallback="call_baseline_model_provider",
        )

    actions.append(PlanAction("hash", True, "low", reason="identity and exact duplicate detection"))
    if not classification.likely_encrypted:
        actions.append(PlanAction("content_defined_chunk", True, "low", reason="partial duplicate detection"))
    else:
        actions.append(PlanAction("store_exact_ciphertext", True, "low", reason="payload high entropy; exact fallback"))

    if classification.entropy_bits_per_byte is not None and classification.entropy_bits_per_byte < 7.85 and not classification.likely_compressed:
        actions.append(PlanAction("zstd", False, "low", reason="sample entropy suggests compressibility"))
    else:
        actions.append(PlanAction("dedupe_only_or_exact_store", True, "low", reason="compression unlikely or unsafe"))

    actions.append(PlanAction("manifest", True, "low", reason="record restoration and audit path"))
    actions.append(PlanAction("verify_restore", True, "low", reason="exact contract requires restore proof"))

    return Plan(
        work_unit_id=work_unit.id,
        contract=decision.contract,
        actions=actions,
        mode=mode,
        policy_bundle_id=decision.policy_bundle_id,
        risk="low",
        expected={"stored_bytes_reduction_possible": not classification.likely_encrypted},
        fallback="store_exact_bytes",
    )
