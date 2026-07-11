from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from .contracts import Contract, WorkUnit, WorkUnitKind
from .verifiers import VerificationResult


@dataclass(frozen=True)
class ReducerSpec:
    name: str
    required_contract: Contract
    policy_flag: str
    required_verifier: str
    action: str
    benchmark_suite: str
    rollback: str
    eligible_kinds: Sequence[WorkUnitKind]
    enabled_by_default: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "required_contract": self.required_contract.value,
            "policy_flag": self.policy_flag,
            "required_verifier": self.required_verifier,
            "action": self.action,
            "benchmark_suite": self.benchmark_suite,
            "rollback": self.rollback,
            "eligible_kinds": [kind.value for kind in self.eligible_kinds],
            "enabled_by_default": self.enabled_by_default,
        }


@dataclass(frozen=True)
class ReducerDecision:
    name: str
    enabled: bool
    reason: str
    details: Dict[str, Any]
    action: str = ""
    required_verifier: str = ""
    benchmark_suite: str = ""
    rollback: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "reason": self.reason,
            "details": self.details,
            "action": self.action,
            "required_verifier": self.required_verifier,
            "benchmark_suite": self.benchmark_suite,
            "rollback": self.rollback,
        }


def advanced_reducer_specs() -> Dict[str, ReducerSpec]:
    return {
        "semantic_cache": ReducerSpec(
            name="semantic_cache",
            required_contract=Contract.SEMANTIC,
            policy_flag="allow_semantic_cache",
            required_verifier="source_fingerprint_match",
            action="semantic_cache_lookup",
            benchmark_suite="prompt-cache-v1",
            rollback="disable allow_semantic_cache and fall back to exact cache/provider call",
            eligible_kinds=(WorkUnitKind.PROMPT_REQUEST, WorkUnitKind.RAG_CONTEXT_PACK),
        ),
        "bounded_approximation": ReducerSpec(
            name="bounded_approximation",
            required_contract=Contract.BOUNDED_APPROX,
            policy_flag="allow_bounded_approximation",
            required_verifier="error_bound",
            action="approximate_quantization",
            benchmark_suite="advanced-local-v1",
            rollback="restore exact source manifest and disable allow_bounded_approximation",
            eligible_kinds=(WorkUnitKind.MEDIA_ASSET, WorkUnitKind.METRIC_SERIES, WorkUnitKind.VECTOR_INDEX_SEGMENT),
        ),
        "lakehouse_optimizer": ReducerSpec(
            name="lakehouse_optimizer",
            required_contract=Contract.EXACT_LOGICAL,
            policy_flag="allow_lakehouse_optimization",
            required_verifier="snapshot_equivalence",
            action="lakehouse_compaction_plan",
            benchmark_suite="advanced-local-v1",
            rollback="restore previous table snapshot pointer and retain compacted files until audit expiry",
            eligible_kinds=(WorkUnitKind.TABLE_SNAPSHOT, WorkUnitKind.TABLE_ROW_GROUP, WorkUnitKind.STRUCTURED_FILE),
        ),
        "training_reducer": ReducerSpec(
            name="training_reducer",
            required_contract=Contract.SEMANTIC,
            policy_flag="allow_training_reducer",
            required_verifier="dataset_lineage",
            action="training_dataset_dedupe",
            benchmark_suite="advanced-local-v1",
            rollback="reconstruct original sample order from duplicate map",
            eligible_kinds=(WorkUnitKind.TRAINING_DATASET, WorkUnitKind.FINE_TUNE_JOB),
        ),
        "checkpoint_delta": ReducerSpec(
            name="checkpoint_delta",
            required_contract=Contract.EXACT_BYTES,
            policy_flag="allow_checkpoint_delta",
            required_verifier="sha256_restore",
            action="checkpoint_delta_store",
            benchmark_suite="advanced-local-v1",
            rollback="materialize full checkpoint bytes from base plus delta blocks",
            eligible_kinds=(WorkUnitKind.MODEL_CHECKPOINT, WorkUnitKind.BACKUP_SNAPSHOT),
        ),
        "distillation": ReducerSpec(
            name="distillation",
            required_contract=Contract.SEMANTIC,
            policy_flag="allow_distillation",
            required_verifier="eval_regression_gate",
            action="distillation_dataset_build",
            benchmark_suite="advanced-local-v1",
            rollback="route traffic to original model and discard distilled artifact",
            eligible_kinds=(WorkUnitKind.PROMPT_REQUEST, WorkUnitKind.EVALUATION_JOB, WorkUnitKind.SYNTHETIC_DATA_JOB),
        ),
    }


def evaluate_reducer(
    work_unit: WorkUnit,
    reducer_name: str,
    verification_results: Mapping[str, VerificationResult] | Iterable[VerificationResult] | None = None,
) -> ReducerDecision:
    spec = advanced_reducer_specs()[reducer_name]
    return _policy_gate(work_unit, spec, verification_results)


def evaluate_advanced_reducers(
    work_unit: WorkUnit,
    names: Iterable[str] | None = None,
    verification_results: Mapping[str, VerificationResult] | Iterable[VerificationResult] | None = None,
) -> List[ReducerDecision]:
    selected = list(names) if names is not None else sorted(advanced_reducer_specs())
    return [evaluate_reducer(work_unit, name, verification_results) for name in selected]


def reducer_conformance() -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}
    for name, spec in advanced_reducer_specs().items():
        missing = []
        if spec.enabled_by_default:
            missing.append("must_be_disabled_by_default")
        for attr in ("policy_flag", "required_verifier", "benchmark_suite", "rollback", "action"):
            if not getattr(spec, attr):
                missing.append(attr)
        results[name] = {"passed": not missing, "missing": missing, "spec": spec.to_dict()}
    return results


def semantic_cache_reducer(work_unit: WorkUnit, verification_results: Iterable[VerificationResult] | None = None) -> ReducerDecision:
    return evaluate_reducer(work_unit, "semantic_cache", verification_results)


def bounded_approximation_reducer(
    work_unit: WorkUnit,
    verification_results: Iterable[VerificationResult] | None = None,
) -> ReducerDecision:
    return evaluate_reducer(work_unit, "bounded_approximation", verification_results)


def lakehouse_optimizer_reducer(
    work_unit: WorkUnit,
    verification_results: Iterable[VerificationResult] | None = None,
) -> ReducerDecision:
    return evaluate_reducer(work_unit, "lakehouse_optimizer", verification_results)


def training_reducer(
    work_unit: WorkUnit,
    verification_results: Iterable[VerificationResult] | None = None,
) -> ReducerDecision:
    return evaluate_reducer(work_unit, "training_reducer", verification_results)


def checkpoint_delta_reducer(
    work_unit: WorkUnit,
    verification_results: Iterable[VerificationResult] | None = None,
) -> ReducerDecision:
    return evaluate_reducer(work_unit, "checkpoint_delta", verification_results)


def distillation_reducer(
    work_unit: WorkUnit,
    verification_results: Iterable[VerificationResult] | None = None,
) -> ReducerDecision:
    return evaluate_reducer(work_unit, "distillation", verification_results)


def semantic_cache_placeholder(
    work_unit: WorkUnit,
    verification_results: Iterable[VerificationResult] | None = None,
) -> ReducerDecision:
    return semantic_cache_reducer(work_unit, verification_results)


def bounded_approximation_placeholder(
    work_unit: WorkUnit,
    verification_results: Iterable[VerificationResult] | None = None,
) -> ReducerDecision:
    return bounded_approximation_reducer(work_unit, verification_results)


def lakehouse_optimizer_placeholder(
    work_unit: WorkUnit,
    verification_results: Iterable[VerificationResult] | None = None,
) -> ReducerDecision:
    return lakehouse_optimizer_reducer(work_unit, verification_results)


def training_reducer_placeholder(
    work_unit: WorkUnit,
    verification_results: Iterable[VerificationResult] | None = None,
) -> ReducerDecision:
    return training_reducer(work_unit, verification_results)


def checkpoint_delta_placeholder(
    work_unit: WorkUnit,
    verification_results: Iterable[VerificationResult] | None = None,
) -> ReducerDecision:
    return checkpoint_delta_reducer(work_unit, verification_results)


def distillation_placeholder(
    work_unit: WorkUnit,
    verification_results: Iterable[VerificationResult] | None = None,
) -> ReducerDecision:
    return distillation_reducer(work_unit, verification_results)


def _policy_gate(
    work_unit: WorkUnit,
    spec: ReducerSpec,
    verification_results: Mapping[str, VerificationResult] | Iterable[VerificationResult] | None,
) -> ReducerDecision:
    requested = _effective_contract(work_unit)
    base = {
        "policy_flag": spec.policy_flag,
        "eligible_kinds": [kind.value for kind in spec.eligible_kinds],
        "enabled_by_default": spec.enabled_by_default,
    }
    if work_unit.kind not in spec.eligible_kinds:
        return _decision(spec, False, "kind_not_eligible", {**base, "actual_kind": work_unit.kind.value})
    if requested != spec.required_contract:
        return _decision(
            spec,
            False,
            "contract_not_eligible",
            {**base, "required_contract": spec.required_contract.value, "actual_contract": requested.value},
        )
    if work_unit.policy_context.get(spec.policy_flag) is not True:
        return _decision(spec, False, "policy_flag_required", {**base, "required_flag": spec.policy_flag})
    results = _verification_map(verification_results)
    verification = results.get(spec.required_verifier)
    if verification is None:
        return _decision(spec, False, "accepted_verification_required", {**base, "required_verifier": spec.required_verifier})
    if not verification.accepted:
        return _decision(
            spec,
            False,
            "verifier_failed",
            {**base, "required_verifier": spec.required_verifier, "verification": verification.to_dict()},
        )
    return _decision(
        spec,
        True,
        "policy_and_verifier_accepted",
        {**base, "verification": verification.to_dict(), "rollback_required": True},
    )


def _verification_map(
    verification_results: Mapping[str, VerificationResult] | Iterable[VerificationResult] | None,
) -> Dict[str, VerificationResult]:
    if verification_results is None:
        return {}
    if isinstance(verification_results, Mapping):
        values = verification_results.values()
    else:
        values = verification_results
    result: Dict[str, VerificationResult] = {}
    for verification in values:
        base = verification.verifier_id.split("@", 1)[0]
        result[base] = verification
    return result


def _decision(spec: ReducerSpec, enabled: bool, reason: str, details: Dict[str, Any]) -> ReducerDecision:
    return ReducerDecision(
        name=spec.name,
        enabled=enabled,
        reason=reason,
        details=details,
        action=spec.action,
        required_verifier=spec.required_verifier,
        benchmark_suite=spec.benchmark_suite,
        rollback=spec.rollback,
    )


def _effective_contract(work_unit: WorkUnit) -> Contract:
    if work_unit.requested_contract:
        return work_unit.requested_contract
    if work_unit.kind in {WorkUnitKind.PROMPT_REQUEST, WorkUnitKind.COMPLETION_RESPONSE, WorkUnitKind.TRAINING_DATASET}:
        return Contract.SEMANTIC
    return Contract.EXACT_BYTES
