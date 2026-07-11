from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import hashlib
import json
import uuid


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class Contract(str, Enum):
    EXACT_BYTES = "exact_bytes"
    EXACT_LOGICAL = "exact_logical"
    BOUNDED_APPROX = "bounded_approx"
    SEMANTIC = "semantic"
    DERIVED = "derived"
    TOMBSTONE = "tombstone"


class WorkUnitKind(str, Enum):
    BYTE_OBJECT = "byte_object"
    STRUCTURED_FILE = "structured_file"
    TABLE_ROW_GROUP = "table_row_group"
    STREAM_SEGMENT = "stream_segment"
    LOG_BATCH = "log_batch"
    MEDIA_ASSET = "media_asset"
    EMBEDDING_BATCH = "embedding_batch"
    PROMPT_REQUEST = "prompt_request"
    COMPLETION_RESPONSE = "completion_response"
    TRAINING_DATASET = "training_dataset"
    MODEL_CHECKPOINT = "model_checkpoint"
    FINE_TUNE_JOB = "fine_tune_job"
    BATCH_COMPUTE_JOB = "batch_compute_job"


@dataclass(frozen=True)
class WorkUnit:
    kind: WorkUnitKind
    tenant: str
    logical_ref: str
    payload: Any = None
    requested_contract: Optional[Contract] = None
    namespace: str = "default"
    metadata: Dict[str, Any] = field(default_factory=dict)
    policy_context: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: new_id("wu"))
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.kind.value
        data["requested_contract"] = self.requested_contract.value if self.requested_contract else None
        return data


@dataclass(frozen=True)
class Classification:
    detected_kind: WorkUnitKind
    entropy_bits_per_byte: Optional[float] = None
    likely_compressed: bool = False
    likely_encrypted: bool = False
    schema_hint: Optional[str] = None
    ai_task_hint: Optional[str] = None
    confidence: float = 0.5
    notes: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class PlanAction:
    type: str
    required: bool = True
    risk: str = "low"
    params: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass(frozen=True)
class Plan:
    work_unit_id: str
    contract: Contract
    actions: List[PlanAction]
    mode: str = "observe"
    policy_bundle_id: str = "default"
    risk: str = "low"
    expected: Dict[str, Any] = field(default_factory=dict)
    fallback: str = "store_exact_or_call_baseline"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "work_unit_id": self.work_unit_id,
            "contract": self.contract.value,
            "actions": [asdict(a) for a in self.actions],
            "mode": self.mode,
            "policy_bundle_id": self.policy_bundle_id,
            "risk": self.risk,
            "expected": self.expected,
            "fallback": self.fallback,
        }


@dataclass(frozen=True)
class Manifest:
    work_unit_id: str
    tenant: str
    kind: WorkUnitKind
    contract: Contract
    logical_ref: str
    state: str = "active"
    physical: Dict[str, Any] = field(default_factory=dict)
    plan: Dict[str, Any] = field(default_factory=dict)
    verification: Dict[str, Any] = field(default_factory=dict)
    lineage: Dict[str, Any] = field(default_factory=dict)
    telemetry: Dict[str, Any] = field(default_factory=dict)
    manifest_version: str = "urp.manifest.v1"
    manifest_id: str = field(default_factory=lambda: new_id("mf"))
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest_version": self.manifest_version,
            "manifest_id": self.manifest_id,
            "work_unit_id": self.work_unit_id,
            "tenant": self.tenant,
            "kind": self.kind.value,
            "contract": self.contract.value,
            "logical_ref": self.logical_ref,
            "state": self.state,
            "created_at": self.created_at,
            "physical": self.physical,
            "plan": self.plan,
            "verification": self.verification,
            "lineage": self.lineage,
            "telemetry": self.telemetry,
        }


def stable_json_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
