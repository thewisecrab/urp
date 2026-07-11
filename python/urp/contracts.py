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
    FILE = "file"
    DIRECTORY_SNAPSHOT = "directory_snapshot"
    BLOCK_EXTENT = "block_extent"
    BACKUP_SNAPSHOT = "backup_snapshot"
    CONTAINER_LAYER = "container_layer"
    STRUCTURED_FILE = "structured_file"
    TABLE_SNAPSHOT = "table_snapshot"
    TABLE_ROW_GROUP = "table_row_group"
    STREAM_SEGMENT = "stream_segment"
    EVENT_BATCH = "event_batch"
    METRIC_SERIES = "metric_series"
    TRACE_BATCH = "trace_batch"
    LOG_BATCH = "log_batch"
    MEDIA_ASSET = "media_asset"
    IMAGE_ASSET = "image_asset"
    VIDEO_ASSET = "video_asset"
    AUDIO_ASSET = "audio_asset"
    DOCUMENT_ASSET = "document_asset"
    VECTOR_INDEX_SEGMENT = "vector_index_segment"
    EMBEDDING_REQUEST = "embedding_request"
    EMBEDDING_BATCH = "embedding_batch"
    PROMPT_REQUEST = "prompt_request"
    COMPLETION_RESPONSE = "completion_response"
    CHAT_SESSION = "chat_session"
    AGENT_STEP = "agent_step"
    TOOL_CALL = "tool_call"
    RAG_CONTEXT_PACK = "rag_context_pack"
    TRAINING_DATASET = "training_dataset"
    EVALUATION_JOB = "evaluation_job"
    MODEL_CHECKPOINT = "model_checkpoint"
    ADAPTER_ARTIFACT = "adapter_artifact"
    FINE_TUNE_JOB = "fine_tune_job"
    INFERENCE_BATCH = "inference_batch"
    KV_CACHE_SEGMENT = "kv_cache_segment"
    SYNTHETIC_DATA_JOB = "synthetic_data_job"
    BATCH_COMPUTE_JOB = "batch_compute_job"
    LIFECYCLE_TRANSITION = "lifecycle_transition"
    DELETION_CANDIDATE = "deletion_candidate"
    REHYDRATION_REQUEST = "rehydration_request"
    POLICY_OVERRIDE = "policy_override"
    PLUGIN_ACTION = "plugin_action"


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
    trace_id: str = field(default_factory=lambda: new_id("tr"))
    id: str = field(default_factory=lambda: new_id("wu"))
    created_at: str = field(default_factory=utc_now)
    payload_ref: Any = None
    effective_contract: Optional[Contract] = None
    deadline: Optional[str] = None
    latency_budget_ms: Optional[int] = None
    quality_target: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.kind.value
        data["requested_contract"] = self.requested_contract.value if self.requested_contract else None
        data["effective_contract"] = self.effective_contract.value if self.effective_contract else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkUnit":
        return cls(
            kind=WorkUnitKind(data["kind"]),
            tenant=data["tenant"],
            logical_ref=data["logical_ref"],
            payload=data.get("payload"),
            requested_contract=Contract(data["requested_contract"]) if data.get("requested_contract") else None,
            namespace=data.get("namespace", "default"),
            metadata=dict(data.get("metadata") or {}),
            policy_context=dict(data.get("policy_context") or {}),
            trace_id=data.get("trace_id") or new_id("tr"),
            id=data.get("id") or new_id("wu"),
            created_at=data.get("created_at") or utc_now(),
            payload_ref=data.get("payload_ref"),
            effective_contract=Contract(data["effective_contract"]) if data.get("effective_contract") else None,
            deadline=data.get("deadline"),
            latency_budget_ms=int(data["latency_budget_ms"]) if data.get("latency_budget_ms") is not None else None,
            quality_target=dict(data.get("quality_target") or {}),
        )


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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanAction":
        return cls(
            type=data["type"],
            required=bool(data.get("required", True)),
            risk=data.get("risk", "low"),
            params=dict(data.get("params") or {}),
            reason=data.get("reason", ""),
        )


@dataclass(frozen=True)
class Plan:
    work_unit_id: str
    contract: Contract
    actions: List[PlanAction]
    tenant: Optional[str] = None
    plan_id: str = field(default_factory=lambda: new_id("pl"))
    trace_id: Optional[str] = None
    mode: str = "observe"
    policy_bundle_id: str = "default"
    risk: str = "low"
    expected: Dict[str, Any] = field(default_factory=dict)
    fallback: str = "store_exact_or_call_baseline"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "work_unit_id": self.work_unit_id,
            "tenant": self.tenant,
            "trace_id": self.trace_id,
            "contract": self.contract.value,
            "actions": [asdict(a) for a in self.actions],
            "mode": self.mode,
            "policy_bundle_id": self.policy_bundle_id,
            "risk": self.risk,
            "expected": self.expected,
            "fallback": self.fallback,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Plan":
        return cls(
            work_unit_id=data["work_unit_id"],
            contract=Contract(data["contract"]),
            actions=[PlanAction.from_dict(row) for row in data.get("actions", [])],
            tenant=data.get("tenant"),
            plan_id=data.get("plan_id") or new_id("pl"),
            trace_id=data.get("trace_id"),
            mode=data.get("mode", "observe"),
            policy_bundle_id=data.get("policy_bundle_id", "default"),
            risk=data.get("risk", "low"),
            expected=dict(data.get("expected") or {}),
            fallback=data.get("fallback", "store_exact_or_call_baseline"),
        )


@dataclass(frozen=True)
class Manifest:
    work_unit_id: str
    tenant: str
    kind: WorkUnitKind
    contract: Contract
    logical_ref: str
    state: str = "active"
    namespace: str = "default"
    trace_id: Optional[str] = None
    policy: Dict[str, Any] = field(default_factory=dict)
    classification: Dict[str, Any] = field(default_factory=dict)
    physical: Dict[str, Any] = field(default_factory=dict)
    plan: Dict[str, Any] = field(default_factory=dict)
    verification: Dict[str, Any] = field(default_factory=dict)
    lineage: Dict[str, Any] = field(default_factory=dict)
    telemetry: Dict[str, Any] = field(default_factory=dict)
    signatures: List[Dict[str, Any]] = field(default_factory=list)
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
            "namespace": self.namespace,
            "trace_id": self.trace_id,
            "state": self.state,
            "created_at": self.created_at,
            "policy": self.policy,
            "classification": self.classification,
            "physical": self.physical,
            "plan": self.plan,
            "verification": self.verification,
            "lineage": self.lineage,
            "telemetry": self.telemetry,
            "signatures": self.signatures,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Manifest":
        return cls(
            work_unit_id=data["work_unit_id"],
            tenant=data["tenant"],
            kind=WorkUnitKind(data["kind"]),
            contract=Contract(data["contract"]),
            logical_ref=data.get("logical_ref", ""),
            state=data.get("state", "active"),
            namespace=data.get("namespace") or "default",
            trace_id=data.get("trace_id"),
            policy=dict(data.get("policy") or {}),
            classification=dict(data.get("classification") or {}),
            physical=dict(data.get("physical") or {}),
            plan=dict(data.get("plan") or {}),
            verification=dict(data.get("verification") or {}),
            lineage=dict(data.get("lineage") or {}),
            telemetry=dict(data.get("telemetry") or {}),
            signatures=list(data.get("signatures") or []),
            manifest_version=data.get("manifest_version", "urp.manifest.v1"),
            manifest_id=data.get("manifest_id") or new_id("mf"),
            created_at=data.get("created_at") or utc_now(),
        )


@dataclass(frozen=True)
class LedgerEvent:
    event_type: str
    tenant: str
    work_unit_id: Optional[str] = None
    manifest_id: Optional[str] = None
    policy_bundle_id: Optional[str] = None
    actor: Optional[str] = None
    decision: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    trace_id: Optional[str] = None
    prev_hash: Optional[str] = None
    event_id: str = field(default_factory=lambda: new_id("evt"))
    created_at: str = field(default_factory=utc_now)
    event_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "tenant": self.tenant,
            "work_unit_id": self.work_unit_id,
            "manifest_id": self.manifest_id,
            "policy_bundle_id": self.policy_bundle_id,
            "actor": self.actor,
            "decision": self.decision,
            "details": self.details,
            "trace_id": self.trace_id,
            "created_at": self.created_at,
            "prev_hash": self.prev_hash,
            "event_hash": self.event_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LedgerEvent":
        return cls(
            event_type=data["event_type"],
            tenant=data["tenant"],
            work_unit_id=data.get("work_unit_id"),
            manifest_id=data.get("manifest_id"),
            policy_bundle_id=data.get("policy_bundle_id"),
            actor=data.get("actor"),
            decision=data.get("decision"),
            details=dict(data.get("details") or {}),
            trace_id=data.get("trace_id"),
            prev_hash=data.get("prev_hash"),
            event_id=data.get("event_id") or new_id("evt"),
            created_at=data.get("created_at") or utc_now(),
            event_hash=data.get("event_hash"),
        )

    def with_chain_hash(self, prev_hash: Optional[str]) -> "LedgerEvent":
        payload = self.to_dict()
        payload["prev_hash"] = prev_hash
        payload["event_hash"] = None
        digest = stable_json_hash(payload)
        return LedgerEvent(
            event_type=self.event_type,
            tenant=self.tenant,
            work_unit_id=self.work_unit_id,
            manifest_id=self.manifest_id,
            policy_bundle_id=self.policy_bundle_id,
            actor=self.actor,
            decision=self.decision,
            details=self.details,
            trace_id=self.trace_id,
            prev_hash=prev_hash,
            event_id=self.event_id,
            created_at=self.created_at,
            event_hash=digest,
        )


def stable_json_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
