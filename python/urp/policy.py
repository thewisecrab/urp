from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from .contracts import Contract, LedgerEvent, WorkUnit, WorkUnitKind
from .ledger import JSONLLedger
from .schema_validation import validate_named_schema


@dataclass(frozen=True)
class PolicyDecision:
    contract: Contract
    allowed_actions: List[str]
    denied_actions: List[str]
    policy_bundle_id: str = "default"
    reasons: List[str] = field(default_factory=list)
    cache_domain: str = "tenant_namespace"
    dedupe_domain: str = "tenant"
    matched_rules: List[str] = field(default_factory=list)
    required_verifiers: List[str] = field(default_factory=list)
    model_allowlist: List[str] = field(default_factory=lambda: ["tiny", "small", "medium", "frontier"])
    require_approval: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract.value,
            "allowed_actions": self.allowed_actions,
            "denied_actions": self.denied_actions,
            "policy_bundle_id": self.policy_bundle_id,
            "reasons": self.reasons,
            "cache_domain": self.cache_domain,
            "dedupe_domain": self.dedupe_domain,
            "matched_rules": self.matched_rules,
            "required_verifiers": self.required_verifiers,
            "model_allowlist": self.model_allowlist,
            "require_approval": self.require_approval,
        }


def load_policy_bundle(path: str | Path) -> Dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except Exception:
        # The bundled example policies are simple enough for JSON-compatible
        # callers. YAML validation remains dependency-free by accepting text and
        # returning a structured error when PyYAML is unavailable.
        try:
            bundle = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("YAML policy validation requires PyYAML; JSON policies are supported without dependencies") from exc
    else:
        bundle = yaml.safe_load(text)
    validate_policy_bundle(bundle)
    return bundle


def validate_policy_bundle(bundle: Dict[str, Any]) -> None:
    validate_named_schema("policy", bundle)


def evaluate_policy(work_unit: WorkUnit, bundle: Dict[str, Any] | None = None) -> PolicyDecision:
    """Reference policy evaluator with safe defaults."""
    if work_unit.policy_context.get("legal_hold") is True:
        return PolicyDecision(
            contract=Contract.EXACT_BYTES,
            allowed_actions=["hash", "content_defined_chunk", "dedupe_same_tenant", "zstd", "manifest", "verify_restore"],
            denied_actions=["semantic_cache", "semantic_cache_lookup", "semantic_summary", "lossy_transcode", "delete", "tombstone"],
            reasons=["legal_hold_forces_exact_bytes"],
            matched_rules=["legal_hold"],
            required_verifiers=["sha256_restore"],
        )

    if work_unit.requested_contract is not None:
        requested = work_unit.requested_contract
    elif work_unit.kind in {WorkUnitKind.PROMPT_REQUEST, WorkUnitKind.COMPLETION_RESPONSE, WorkUnitKind.EMBEDDING_REQUEST}:
        requested = Contract.SEMANTIC
    else:
        requested = Contract.EXACT_BYTES

    bundle_decision = _evaluate_bundle(work_unit, requested, bundle) if bundle else None
    if bundle_decision:
        return bundle_decision

    if requested == Contract.SEMANTIC and work_unit.kind in {WorkUnitKind.PROMPT_REQUEST, WorkUnitKind.COMPLETION_RESPONSE, WorkUnitKind.EMBEDDING_REQUEST}:
        allow_semantic_cache = work_unit.policy_context.get("allow_semantic_cache") is True
        allowed = ["normalize_prompt", "exact_cache_lookup", "model_route", "verify", "cache_store", "compute_manifest"]
        denied = ["cross_tenant_cache", "semantic_summary", "lossy_transcode", "delete"]
        if work_unit.kind in {WorkUnitKind.PROMPT_REQUEST, WorkUnitKind.COMPLETION_RESPONSE}:
            allowed.append("context_compile")
        if allow_semantic_cache and work_unit.kind in {WorkUnitKind.PROMPT_REQUEST, WorkUnitKind.COMPLETION_RESPONSE}:
            allowed.append("semantic_cache_lookup")
        else:
            denied.append("semantic_cache_lookup")
        return PolicyDecision(
            contract=Contract.SEMANTIC,
            allowed_actions=allowed,
            denied_actions=denied,
            reasons=["ai_contract_with_semantic_reducers_disabled_by_default"],
            matched_rules=["ai_request_default"],
            required_verifiers=["embedding_shape" if work_unit.kind == WorkUnitKind.EMBEDDING_REQUEST else "non_empty_text"],
        )

    return PolicyDecision(
        contract=Contract.EXACT_BYTES if requested == Contract.EXACT_BYTES else requested,
        allowed_actions=["hash", "content_defined_chunk", "fixed_chunk", "dedupe_same_tenant", "zstd", "manifest", "verify_restore"],
        denied_actions=["semantic_cache", "semantic_cache_lookup", "semantic_summary", "lossy_transcode", "cross_tenant_dedupe", "delete"],
        reasons=["safe_default_exact_or_requested_contract"],
        matched_rules=["global_default"],
        required_verifiers=["sha256_restore"],
    )


def _evaluate_bundle(work_unit: WorkUnit, requested: Contract, bundle: Dict[str, Any] | None) -> PolicyDecision | None:
    if not bundle:
        return None
    spec = bundle.get("spec", {})
    defaults = spec.get("defaults", {})
    rules = spec.get("rules", [])
    matched: List[Dict[str, Any]] = []
    for rule in rules:
        match = rule.get("match", {})
        if _matches(work_unit, match):
            matched.append(rule)
    if not matched and not defaults:
        return None
    matched_contracts = [Contract(rule["contract"]) for rule in matched if rule.get("contract")]
    strict = matched_contracts[0] if matched_contracts else Contract(defaults.get("contract", requested.value))
    for contract in matched_contracts[1:]:
        strict = _stricter(strict, contract)
    allowed, denied, required_verifiers = _baseline_policy_controls(work_unit, strict)
    require_approval = False
    matched_names = ["defaults"] if defaults else []
    explicitly_allowed: set[str] = set()
    for rule in matched:
        matched_names.append(rule.get("name", "unnamed"))
        allow = rule.get("allow", {})
        deny = rule.get("deny", {})
        required = rule.get("require", {})
        for transform in allow.get("transforms", []):
            canonical = _canonical_actions(str(transform))
            explicitly_allowed.update(canonical)
            allowed.extend(canonical)
        for transform in deny.get("transforms", []):
            denied.extend(_canonical_actions(str(transform)))
        required_verifiers.extend(required.get("verifiers", []))
        require_approval = require_approval or bool(rule.get("requires_approval"))
    if defaults.get("semanticReduction") == "deny" and strict != Contract.SEMANTIC:
        denied.extend(["semantic_cache_lookup", "semantic_summary"])
    elif defaults.get("semanticReduction") == "deny" and "semantic_cache_lookup" not in explicitly_allowed:
        denied.extend(["semantic_cache_lookup", "semantic_summary"])
    if defaults.get("approximateReduction") == "deny" and strict != Contract.BOUNDED_APPROX:
        denied.append("approximate_quantization")
    if defaults.get("crossTenantDedupe") == "deny":
        denied.append("cross_tenant_dedupe")
    if defaults.get("crossTenantCache") == "deny":
        denied.append("cross_tenant_cache")
    model_allowlist = list(defaults.get("modelAllowlist") or ["tiny", "small", "medium", "frontier"])
    for rule in matched:
        if rule.get("modelAllowlist"):
            model_allowlist = [str(item) for item in rule["modelAllowlist"]]
    if not model_allowlist:
        raise ValueError("policy modelAllowlist cannot be empty")
    return PolicyDecision(
        contract=strict,
        allowed_actions=sorted(set(allowed) - set(denied)),
        denied_actions=sorted(set(denied)),
        policy_bundle_id=bundle.get("metadata", {}).get("name", "policy_bundle"),
        reasons=["policy_bundle_evaluated"],
        matched_rules=matched_names,
        required_verifiers=sorted(set(required_verifiers)),
        cache_domain=str(defaults.get("cacheDomain", "tenant_namespace")),
        dedupe_domain=str(defaults.get("dedupeDomain", "tenant")),
        model_allowlist=model_allowlist,
        require_approval=require_approval,
    )


def _baseline_policy_controls(work_unit: WorkUnit, contract: Contract) -> tuple[List[str], List[str], List[str]]:
    denied = ["cross_tenant_cache", "cross_tenant_dedupe", "semantic_summary", "lossy_transcode", "delete"]
    if work_unit.kind == WorkUnitKind.EMBEDDING_REQUEST:
        return (
            ["normalize_prompt", "verify", "compute_manifest"],
            denied + ["semantic_cache_lookup"],
            ["embedding_shape"],
        )
    if work_unit.kind in {WorkUnitKind.PROMPT_REQUEST, WorkUnitKind.COMPLETION_RESPONSE}:
        return (
            ["normalize_prompt", "verify", "compute_manifest"],
            denied,
            ["non_empty_text"],
        )
    return (
        ["hash", "content_defined_chunk", "fixed_chunk", "dedupe_same_tenant", "zstd", "manifest", "verify_restore"],
        denied + ["semantic_cache_lookup"],
        ["sha256_restore"],
    )


def _canonical_actions(name: str) -> List[str]:
    aliases = {
        "exact_cache": ["exact_cache_lookup", "cache_store"],
        "context_dedupe": ["context_compile"],
        "model_route_shadow": ["model_route_shadow"],
        "semantic_cache_shadow": ["semantic_cache_shadow"],
        "semantic_cache_enforce": ["semantic_cache_lookup"],
        "distillation_enforce": ["distillation"],
    }
    return aliases.get(name, [name])


def _matches(work_unit: WorkUnit, match: Dict[str, Any]) -> bool:
    for key, value in match.items():
        if key == "kind" and work_unit.kind.value != value:
            return False
        if key == "namespace" and work_unit.namespace != value:
            return False
        if key == "tenant" and work_unit.tenant != value:
            return False
        if key == "tags":
            tags = work_unit.metadata.get("tags", work_unit.metadata)
            if any(tags.get(k) != v for k, v in value.items()):
                return False
    return True


def _stricter(left: Contract, right: Contract) -> Contract:
    order = {
        Contract.EXACT_BYTES: 0,
        Contract.EXACT_LOGICAL: 1,
        Contract.BOUNDED_APPROX: 2,
        Contract.SEMANTIC: 3,
        Contract.DERIVED: 4,
        Contract.TOMBSTONE: 5,
    }
    return left if order[left] <= order[right] else right


def audit_policy_override(
    work_unit: WorkUnit,
    requested_contract: Contract,
    actor: str,
    reason: str,
    ledger: JSONLLedger,
    approved: bool = False,
) -> LedgerEvent:
    event = LedgerEvent(
        "policy.override.approved" if approved else "policy.override.requested",
        work_unit.tenant,
        work_unit.id,
        policy_bundle_id="override",
        actor=actor,
        decision=requested_contract.value,
        details={"reason": reason, "approved": approved, "requested_contract": requested_contract.value},
        trace_id=work_unit.trace_id,
    )
    return ledger.append(event)
