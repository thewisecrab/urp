from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal

ContractMode = Literal[
    "exact-byte", "exact-logical", "bounded-approximate", "semantic-equivalent",
    "summary", "sketch", "sample", "tombstone", "legal-hold", "do-not-transform"
]

@dataclass(frozen=True)
class ResourceContract:
    mode: ContractMode = "exact-byte"
    reversibility: str = "byte-identical"
    freshness_slo_seconds: int = 0
    latency_slo_ms: int = 0
    audit_required: bool = True
    quality_bounds: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ResourceRef:
    logical_id: str
    resource_type: str
    tenant: str = "default"
    content_type: str = "application/octet-stream"

@dataclass
class ReductionPlan:
    plan_id: str
    resource: ResourceRef
    contract: ResourceContract
    transforms: list[str]
    fallback: str
    policy_allowed: bool = True
    reasons: list[str] = field(default_factory=list)

@dataclass
class ManifestSegment:
    logical_start: int
    logical_end: int
    physical_ref: str
    checksum: str
    transform_stack: list[str]

@dataclass
class URPManifest:
    manifest_version: str
    resource: ResourceRef
    contract: ResourceContract
    segments: list[ManifestSegment]
    policy_id: str
    provenance: dict[str, Any]
