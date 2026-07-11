from __future__ import annotations

from typing import Any, Dict, List
from .action_registry import default_action_registry
from .contracts import Contract, Plan, PlanAction, WorkUnit, WorkUnitKind, stable_json_hash
from .classifier import Classification, classify
from .policy import PolicyDecision, evaluate_policy


def plan_work_unit(
    work_unit: WorkUnit,
    mode: str = "observe",
    policy_bundle: dict | None = None,
    policy_decision: PolicyDecision | None = None,
) -> Plan:
    if mode not in {"observe", "shadow", "enforce"}:
        raise ValueError("mode must be observe, shadow, or enforce")
    classification = classify(work_unit)
    decision = policy_decision or evaluate_policy(work_unit, policy_bundle)
    actions: List[PlanAction] = []

    if work_unit.kind == WorkUnitKind.EMBEDDING_REQUEST:
        actions.extend([
            PlanAction("normalize_prompt", True, "low", reason="stable embedding cache key"),
            PlanAction("exact_cache_lookup", False, "low", reason="avoid repeated identical embedding computation"),
            PlanAction("model_route", True, "medium", reason="choose embedding model path"),
            PlanAction("verify", True, "medium", reason="embedding vector shape before acceptance"),
            PlanAction("cache_store", False, "low", reason="reuse verified embedding vector"),
            PlanAction("compute_manifest", True, "low", reason="record AI compute path"),
        ])
        filtered = _filter_actions(actions, decision, mode)
        default_action_registry().validate_plan_actions(decision.contract, filtered, [d for d in decision.denied_actions if d in [a.type for a in filtered]])
        score = _score_plan(work_unit, filtered, classification, decision)
        return Plan(
            work_unit_id=work_unit.id,
            contract=decision.contract,
            actions=filtered,
            tenant=work_unit.tenant,
            plan_id=_plan_id(work_unit, filtered, mode),
            trace_id=work_unit.trace_id,
            mode=mode,
            policy_bundle_id=decision.policy_bundle_id,
            risk="medium",
            expected={
                "embedding_recompute_avoided_possible": True,
                "denied_actions": decision.denied_actions,
                "matched_rules": decision.matched_rules,
                "required_verifiers": decision.required_verifiers,
                **score,
            },
            fallback="call_baseline_embedding_provider",
        )

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
            PlanAction("compute_manifest", True, "low", reason="record AI compute path"),
        ])
        filtered = _filter_actions(actions, decision, mode)
        default_action_registry().validate_plan_actions(decision.contract, filtered, [d for d in decision.denied_actions if d in [a.type for a in filtered]])
        score = _score_plan(work_unit, filtered, classification, decision)
        return Plan(
            work_unit_id=work_unit.id,
            contract=decision.contract,
            actions=filtered,
            tenant=work_unit.tenant,
            plan_id=_plan_id(work_unit, filtered, mode),
            trace_id=work_unit.trace_id,
            mode=mode,
            policy_bundle_id=decision.policy_bundle_id,
            risk="medium",
            expected={
                "tokens_avoided_possible": True,
                "large_model_calls_avoided_possible": True,
                "denied_actions": decision.denied_actions,
                "matched_rules": decision.matched_rules,
                "required_verifiers": decision.required_verifiers,
                **score,
            },
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
    actions = _filter_actions(actions, decision, mode)
    if not any(action.type in {"content_defined_chunk", "fixed_chunk", "store_exact_ciphertext", "store_exact_bytes"} for action in actions):
        actions.insert(1, PlanAction("store_exact_bytes", True, "low", reason="policy-safe exact fallback"))
    default_action_registry().validate_plan_actions(decision.contract, actions, [])
    score = _score_plan(work_unit, actions, classification, decision)

    return Plan(
        work_unit_id=work_unit.id,
        contract=decision.contract,
        actions=actions,
        tenant=work_unit.tenant,
        plan_id=_plan_id(work_unit, actions, mode),
        trace_id=work_unit.trace_id,
        mode=mode,
        policy_bundle_id=decision.policy_bundle_id,
        risk="low",
        expected={
            "stored_bytes_reduction_possible": not classification.likely_encrypted,
            "denied_actions": decision.denied_actions,
            "matched_rules": decision.matched_rules,
            "required_verifiers": decision.required_verifiers,
            **score,
        },
        fallback="store_exact_bytes",
    )


def _plan_id(work_unit: WorkUnit, actions: List[PlanAction], mode: str) -> str:
    digest = stable_json_hash({
        "work_unit_id": work_unit.id,
        "kind": work_unit.kind.value,
        "actions": [a.type for a in actions],
        "mode": mode,
    })[:24]
    return f"pl_{digest}"


def _score_plan(
    work_unit: WorkUnit,
    actions: List[PlanAction],
    classification: Classification,
    decision: PolicyDecision,
) -> Dict[str, Any]:
    action_names = {action.type for action in actions}
    savings_value = _savings_value(work_unit, action_names, classification)
    risk_penalty = sum({"low": 0.01, "medium": 0.04, "high": 0.12}.get(action.risk, 0.04) for action in actions)
    latency_penalty = 0.03 if any(action.required and action.risk == "medium" for action in actions) else 0.01
    cpu_overhead = 0.0
    if "content_defined_chunk" in action_names:
        cpu_overhead += 0.03
    if "zstd" in action_names:
        cpu_overhead += 0.04
    if "context_compile" in action_names:
        cpu_overhead += 0.02
    if "model_route" in action_names:
        cpu_overhead += 0.01
    rehydration_penalty = 0.05 if {"content_defined_chunk", "zstd"} & action_names else 0.01
    metadata_overhead = min(0.08, len(actions) * 0.008)
    verifier_cost = min(0.08, max(1, len(decision.required_verifiers)) * 0.02)
    policy_bonus = _policy_bonus(decision)
    raw_score = savings_value - latency_penalty - risk_penalty - cpu_overhead - rehydration_penalty - metadata_overhead - verifier_cost + policy_bonus
    score = max(0.0, min(1.0, raw_score))
    components = {
        "savings_value": savings_value,
        "latency_penalty": latency_penalty,
        "risk_penalty": risk_penalty,
        "cpu_overhead": cpu_overhead,
        "rehydration_penalty": rehydration_penalty,
        "metadata_overhead": metadata_overhead,
        "verifier_cost": verifier_cost,
        "policy_bonus": policy_bonus,
    }
    return {
        "score": round(score, 4),
        "score_components": {key: round(value, 4) for key, value in components.items()},
        "score_formula": "savings_value - latency_penalty - risk_penalty - cpu_overhead - rehydration_penalty - metadata_overhead - verifier_cost + policy_bonus",
    }


def _savings_value(work_unit: WorkUnit, action_names: set[str], classification: Classification) -> float:
    if work_unit.kind == WorkUnitKind.EMBEDDING_REQUEST:
        return 0.52 if "exact_cache_lookup" in action_names else 0.25
    if work_unit.kind == WorkUnitKind.PROMPT_REQUEST:
        value = 0.45 if "exact_cache_lookup" in action_names else 0.2
        if "context_compile" in action_names:
            value += 0.12
        if "semantic_cache_lookup" in action_names:
            value += 0.08
        return min(value, 0.75)
    if classification.likely_encrypted:
        return 0.18
    if "zstd" in action_names:
        return 0.78
    if "content_defined_chunk" in action_names:
        return 0.55
    return 0.25


def _policy_bonus(decision: PolicyDecision) -> float:
    bonus = 0.04 if decision.required_verifiers else 0.0
    if decision.contract in {Contract.EXACT_BYTES, Contract.EXACT_LOGICAL}:
        bonus += 0.04
    if decision.denied_actions:
        bonus += 0.02
    return min(bonus, 0.12)


def _filter_actions(actions: List[PlanAction], decision: PolicyDecision, mode: str) -> List[PlanAction]:
    framework = {"hash", "manifest", "verify", "verify_restore", "compute_manifest"}
    denied = set(decision.denied_actions)
    allowed = set(decision.allowed_actions)
    filtered: List[PlanAction] = []
    for action in actions:
        if action.type in denied:
            if action.type in framework:
                raise ValueError(f"policy cannot deny mandatory safety action: {action.type}")
            continue
        shadow_allowed = mode == "shadow" and f"{action.type}_shadow" in allowed
        if action.type in framework or action.type in allowed or shadow_allowed:
            filtered.append(action)
    return filtered
