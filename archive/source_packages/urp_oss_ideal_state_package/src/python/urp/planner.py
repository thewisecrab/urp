from __future__ import annotations
import hashlib
from .contracts import ResourceRef, ResourceContract, ReductionPlan
from .classifier import classify_sample
from .entropy import likely_incompressible
from .policy import ReductionPolicy

def build_plan(resource: ResourceRef, contract: ResourceContract, sample: bytes, policy: ReductionPolicy | None = None) -> ReductionPlan:
    policy = policy or ReductionPolicy()
    rule = policy.match_rule(resource.resource_type, {"content_type": resource.content_type})
    transforms: list[str] = []
    reasons: list[str] = []
    kind = classify_sample(sample, resource.content_type)
    if contract.mode in {"legal-hold", "do-not-transform"}:
        transforms = []
        reasons.append("contract forbids transformation")
    else:
        transforms.append("whole-object-dedupe")
        if not likely_incompressible(sample):
            transforms.append("content-defined-chunking")
            transforms.append("zstd")
            reasons.append("sample entropy indicates lossless reduction may help")
        else:
            transforms.append("dedupe-only")
            reasons.append("sample appears high entropy, encrypted, or already compressed")
        if kind in {"json", "csv-or-log", "text"} and contract.mode in {"exact-byte", "exact-logical"}:
            transforms.append("dictionary-training-candidate")
        if kind == "parquet" and contract.mode in {"exact-logical", "bounded-approximate"}:
            transforms.append("row-group-compaction-candidate")
        if resource.resource_type == "ai_request":
            transforms.extend(["exact-cache", "semantic-cache", "context-pruning", "model-routing", "verifier-fallback"])
    forbidden = set(rule.forbidden_transforms)
    transforms = [t for t in transforms if t not in forbidden]
    plan_id = hashlib.sha256((resource.logical_id + contract.mode + "|".join(transforms)).encode()).hexdigest()[:16]
    return ReductionPlan(plan_id=plan_id, resource=resource, contract=contract, transforms=transforms, fallback="store-original-and-audit", policy_allowed=not rule.requires_approval, reasons=reasons)
