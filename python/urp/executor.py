from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from .chunk_store import LocalChunkStore
from .chunking import content_defined_chunks, fixed_chunks, sha256_bytes
from .classifier import classify
from .config import execution_mode, require_execution_enabled
from .contracts import LedgerEvent, Manifest, WorkUnit, WorkUnitKind
from .errors import policy_denied, rehydration_failed, verifier_failed
from .approval_store import ApprovalStore
from .encoding import decode_json_value, json_safe_work_unit
from .ledger import default_ledger
from .manifest_store import default_manifest_store
from .metrics import GLOBAL_METRICS
from .plan_store import store_plan_with_audit
from .planner import plan_work_unit
from .policy import evaluate_policy
from .policy_store import resolve_active_policy_bundle
from .schema_validation import validate_named_schema
from .structured_logs import emit_log
from .tracing import emit_span
from .verifiers import verify_sha256


@dataclass(frozen=True)
class ExecutionResult:
    work_unit_id: str
    manifest_id: str
    accepted: bool
    mode: str
    output: Any = None
    details: Dict[str, Any] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "work_unit_id": self.work_unit_id,
            "manifest_id": self.manifest_id,
            "accepted": self.accepted,
            "mode": self.mode,
            "output": self.output,
            "details": self.details or {},
        }


def init_state(state_dir: str | Path) -> Path:
    state = Path(state_dir)
    for child in ("chunks", "manifests", "plans", "cache", "tmp"):
        (state / child).mkdir(parents=True, exist_ok=True)
    (state / "ledger.jsonl").touch(exist_ok=True)
    return state


def payload_to_bytes(payload: Any) -> bytes:
    payload = decode_json_value(payload)
    if payload is None:
        return b""
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8")
    return json.dumps(payload, sort_keys=True, default=str).encode("utf-8")


def execute_work_unit(work_unit: WorkUnit, state_dir: str | Path = ".urp", mode: str | None = None) -> ExecutionResult:
    mode = execution_mode(mode)
    require_execution_enabled(work_unit.id)
    validate_named_schema("work_unit", json_safe_work_unit(work_unit))
    policy_name = work_unit.policy_context.get("policy_bundle_id") or work_unit.policy_context.get("policy_bundle")
    policy_bundle = resolve_active_policy_bundle(state_dir, str(policy_name) if policy_name else None)
    if work_unit.kind == WorkUnitKind.PROMPT_REQUEST:
        from .ai_gateway import handle_chat_completion

        request = work_unit.payload if isinstance(work_unit.payload, dict) else {"messages": [{"role": "user", "content": str(work_unit.payload or "")}], "model": "auto"}
        response = handle_chat_completion(
            request,
            tenant=work_unit.tenant,
            namespace=work_unit.namespace,
            state_dir=state_dir,
            policy_bundle=policy_bundle,
            mode=mode,
        )
        return ExecutionResult(work_unit.id, response["urp"]["manifest_id"], True, mode, response)
    if work_unit.kind not in {WorkUnitKind.BYTE_OBJECT, WorkUnitKind.FILE, WorkUnitKind.STRUCTURED_FILE, WorkUnitKind.LOG_BATCH}:
        return execute_mock_adapter(work_unit, state_dir, mode, policy_bundle=policy_bundle)
    return execute_exact_object(work_unit, state_dir, mode, policy_bundle=policy_bundle)


def execute_exact_object(
    work_unit: WorkUnit,
    state_dir: str | Path = ".urp",
    mode: str | None = None,
    *,
    policy_bundle: Dict[str, Any] | None = None,
    adapter_name: str | None = None,
) -> ExecutionResult:
    mode = execution_mode(mode)
    state = init_state(state_dir)
    ledger = default_ledger(state)
    manifest_store = default_manifest_store(state)
    chunk_store = LocalChunkStore(state / "chunks")
    payload = payload_to_bytes(work_unit.payload)
    whole_hash = sha256_bytes(payload)
    classification = classify(work_unit)
    policy = evaluate_policy(work_unit, policy_bundle)
    plan = plan_work_unit(work_unit, mode=mode, policy_bundle=policy_bundle, policy_decision=policy)
    _require_policy_approval(state, work_unit, policy)
    ledger.append(LedgerEvent("work_unit.received", work_unit.tenant, work_unit.id, policy_bundle_id=policy.policy_bundle_id, trace_id=work_unit.trace_id))
    emit_log(
        state,
        "work_unit.received",
        "work unit received",
        tenant=work_unit.tenant,
        work_unit_id=work_unit.id,
        policy_bundle_id=policy.policy_bundle_id,
        trace_id=work_unit.trace_id,
        details={"kind": work_unit.kind.value, "namespace": work_unit.namespace, "logical_bytes": len(payload)},
    )
    emit_span(state, "urp.intake", work_unit.trace_id, work_unit_id=work_unit.id, tenant=work_unit.tenant, kind=work_unit.kind.value)
    ledger.append(LedgerEvent("policy.evaluated", work_unit.tenant, work_unit.id, policy_bundle_id=policy.policy_bundle_id, decision=policy.contract.value, details=policy.to_dict(), trace_id=work_unit.trace_id))
    emit_log(
        state,
        "policy.evaluated",
        "policy evaluated",
        tenant=work_unit.tenant,
        work_unit_id=work_unit.id,
        policy_bundle_id=policy.policy_bundle_id,
        trace_id=work_unit.trace_id,
        details={"contract": policy.contract.value, "denied_actions": policy.denied_actions},
    )
    emit_span(state, "urp.policy.evaluate", work_unit.trace_id, work_unit_id=work_unit.id, policy_bundle_id=policy.policy_bundle_id, contract=policy.contract.value)
    store_plan_with_audit(state, plan, work_unit)
    emit_log(
        state,
        "plan.created",
        "plan created",
        tenant=work_unit.tenant,
        work_unit_id=work_unit.id,
        policy_bundle_id=policy.policy_bundle_id,
        trace_id=work_unit.trace_id,
        details={"plan_id": plan.plan_id, "action_count": len(plan.actions), "mode": plan.mode},
    )
    emit_span(state, "urp.plan", work_unit.trace_id, work_unit_id=work_unit.id, plan_id=plan.plan_id, action_count=len(plan.actions))
    if mode == "observe":
        return _record_observation(work_unit, state, policy, plan, classification, payload, whole_hash, adapter_name)
    action_names = {action.type for action in plan.actions}
    if "content_defined_chunk" in action_names:
        chunks = content_defined_chunks(payload)
    elif "fixed_chunk" in action_names:
        chunks = fixed_chunks(payload)
    else:
        chunks = fixed_chunks(payload, max(1, len(payload)))
    storage_namespace = work_unit.namespace if mode == "enforce" else f"shadow-{work_unit.namespace}"
    stored = chunk_store.put_chunks(work_unit.tenant, storage_namespace, chunks, compress="zstd" in action_names)
    segments = []
    for chunk, stored_chunk in zip(chunks, stored):
        row = stored_chunk.to_dict()
        row.update({"logical_start": chunk.start, "logical_end": chunk.end, "sha256": chunk.sha256})
        segments.append(row)
        ledger.append(LedgerEvent("action.executed", work_unit.tenant, work_unit.id, policy_bundle_id=policy.policy_bundle_id, details={"action": "store_chunk", "digest": chunk.sha256, "dedupe_hit": stored_chunk.dedupe_hit}, trace_id=work_unit.trace_id))
    restored = chunk_store.rehydrate(segments)
    emit_span(state, "urp.rehydrate", work_unit.trace_id, work_unit_id=work_unit.id, bytes=len(restored))
    verification = verify_sha256(restored, whole_hash)
    if not verification.accepted:
        ledger.append(LedgerEvent("verifier.failed", work_unit.tenant, work_unit.id, policy_bundle_id=policy.policy_bundle_id, details=verification.to_dict(), trace_id=work_unit.trace_id))
        emit_log(
            state,
            "verifier.failed",
            "verifier failed",
            severity="error",
            tenant=work_unit.tenant,
            work_unit_id=work_unit.id,
            policy_bundle_id=policy.policy_bundle_id,
            trace_id=work_unit.trace_id,
            error_code="verifier_failed",
            details=verification.to_dict(),
        )
        GLOBAL_METRICS.inc("urp_verifier_failures_total")
        raise verifier_failed("exact rehydration verifier failed", work_unit.id, verification.to_dict())
    _require_exact_verifiers(policy.required_verifiers, verification.accepted, work_unit.id)
    physical_bytes = sum(int(s["stored_size"]) for s in segments)
    manifest = Manifest(
        work_unit_id=work_unit.id,
        tenant=work_unit.tenant,
        kind=work_unit.kind,
        contract=policy.contract,
        logical_ref=work_unit.logical_ref,
        namespace=work_unit.namespace,
        trace_id=work_unit.trace_id,
        policy=policy.to_dict(),
        classification={
            "entropy_bits_per_byte": classification.entropy_bits_per_byte,
            "likely_compressed": classification.likely_compressed,
            "likely_encrypted": classification.likely_encrypted,
            "schema_hint": classification.schema_hint,
            "notes": classification.notes,
        },
        physical={
            **({"adapter": adapter_name, "external_integrations_required": False} if adapter_name else {}),
            "whole_sha256": whole_hash,
            "logical_size": len(payload),
            "stored_size": physical_bytes,
            "segments": segments,
        },
        plan=plan.to_dict(),
        verification=verification.to_dict(),
        lineage={
            "work_unit_metadata": work_unit.metadata,
            "policy_context": work_unit.policy_context,
        },
        state="active" if mode == "enforce" else "superseded",
        telemetry={
            "mode": mode,
            "bytes_in": len(payload),
            "bytes_stored": physical_bytes,
            "bytes_avoided": max(0, len(payload) - physical_bytes),
            "chunk_count": len(segments),
            "dedupe_hits": sum(1 for s in segments if s.get("dedupe_hit")),
        },
    )
    manifest_store.put(manifest)
    ledger.append(LedgerEvent("manifest.written", work_unit.tenant, work_unit.id, manifest.manifest_id, policy.policy_bundle_id, details={"logical_ref": work_unit.logical_ref}, trace_id=work_unit.trace_id))
    if adapter_name:
        ledger.append(
            LedgerEvent(
                "adapter.mock.executed",
                work_unit.tenant,
                work_unit.id,
                manifest.manifest_id,
                policy.policy_bundle_id,
                details={"kind": work_unit.kind.value, "adapter": adapter_name},
                trace_id=work_unit.trace_id,
            )
        )
    emit_log(
        state,
        "manifest.written",
        "manifest written",
        tenant=work_unit.tenant,
        work_unit_id=work_unit.id,
        manifest_id=manifest.manifest_id,
        policy_bundle_id=policy.policy_bundle_id,
        trace_id=work_unit.trace_id,
        details={"kind": work_unit.kind.value, "logical_size": len(payload), "stored_size": physical_bytes, "chunk_count": len(segments)},
    )
    emit_span(state, "urp.manifest.write", work_unit.trace_id, work_unit_id=work_unit.id, manifest_id=manifest.manifest_id)
    GLOBAL_METRICS.inc("urp_work_units_total")
    GLOBAL_METRICS.inc("urp_work_unit_bytes_in_total", len(payload))
    GLOBAL_METRICS.inc("urp_work_unit_bytes_stored_total", physical_bytes)
    GLOBAL_METRICS.inc("urp_bytes_avoided_total", max(0, len(payload) - physical_bytes))
    GLOBAL_METRICS.inc("urp_chunks_total", len(segments))
    GLOBAL_METRICS.inc("urp_chunk_dedupe_hits_total", sum(1 for s in segments if s.get("dedupe_hit")))
    GLOBAL_METRICS.inc("urp_ledger_events_total", len(segments) + 4)
    return ExecutionResult(work_unit.id, manifest.manifest_id, True, mode, {"sha256": whole_hash}, {"bytes_in": len(payload), "bytes_stored": physical_bytes})


def rehydrate_manifest(manifest_id: str, state_dir: str | Path = ".urp") -> bytes:
    state = init_state(state_dir)
    manifest = default_manifest_store(state).get(manifest_id)
    segments = manifest.physical.get("segments", [])
    try:
        data = LocalChunkStore(state / "chunks").rehydrate(segments)
    except (OSError, ValueError, KeyError) as exc:
        raise rehydration_failed("rehydration failed segment verification", manifest.work_unit_id, {"reason": str(exc)}) from exc
    expected = str(manifest.physical.get("whole_sha256", ""))
    verification = verify_sha256(data, expected)
    if not verification.accepted:
        raise rehydration_failed("rehydration failed checksum verification", manifest.work_unit_id, verification.to_dict())
    return data


def rehydrate_manifest_range(manifest_id: str, start: int, end: int, state_dir: str | Path = ".urp") -> bytes:
    if start < 0 or end < start:
        raise ValueError("invalid range")
    state = init_state(state_dir)
    manifest = default_manifest_store(state).get(manifest_id)
    logical_size = int(manifest.physical.get("logical_size", 0))
    effective_end = min(end, logical_size)
    if start >= effective_end:
        return b""
    pieces: list[bytes] = []
    store = LocalChunkStore(state / "chunks")
    try:
        for segment in sorted(manifest.physical.get("segments", []), key=lambda row: int(row["logical_start"])):
            seg_start = int(segment["logical_start"])
            seg_end = int(segment["logical_end"])
            if seg_end <= start or seg_start >= effective_end:
                continue
            data = store.read_stored(segment)
            if len(data) != seg_end - seg_start:
                raise ValueError("segment logical size does not match restored bytes")
            local_start = max(start, seg_start) - seg_start
            local_end = min(effective_end, seg_end) - seg_start
            pieces.append(data[local_start:local_end])
    except (OSError, ValueError, KeyError) as exc:
        raise rehydration_failed("range rehydration failed segment verification", manifest.work_unit_id, {"reason": str(exc)}) from exc
    result = b"".join(pieces)
    expected_size = effective_end - start
    if len(result) != expected_size:
        raise rehydration_failed(
            "range rehydration encountered a segment gap",
            manifest.work_unit_id,
            {"expected_bytes": expected_size, "actual_bytes": len(result), "start": start, "end": effective_end},
        )
    emit_span(state, "urp.rehydrate.range", manifest.trace_id or "tr_unknown", work_unit_id=manifest.work_unit_id, manifest_id=manifest_id, start=start, end=end, bytes=len(result))
    return result


def execute_mock_adapter(
    work_unit: WorkUnit,
    state_dir: str | Path = ".urp",
    mode: str = "enforce",
    *,
    policy_bundle: Dict[str, Any] | None = None,
) -> ExecutionResult:
    adapter_name = str(work_unit.metadata.get("adapter") or "local_mock")
    return execute_exact_object(
        work_unit,
        state_dir,
        mode,
        policy_bundle=policy_bundle,
        adapter_name=adapter_name,
    )


def _require_policy_approval(state: Path, work_unit: WorkUnit, policy: Any) -> None:
    if not policy.require_approval:
        return
    approval_id = work_unit.policy_context.get("approval_id")
    if not approval_id:
        default_ledger(state).append(
            LedgerEvent(
                "policy.denied",
                work_unit.tenant,
                work_unit.id,
                policy_bundle_id=policy.policy_bundle_id,
                decision="approval_required",
                trace_id=work_unit.trace_id,
            )
        )
        raise policy_denied("policy requires an approved approval_id", work_unit.id, policy.policy_bundle_id)
    try:
        ApprovalStore(state).verify(str(approval_id), work_unit, policy.contract, policy.policy_bundle_id)
    except (KeyError, ValueError, FileNotFoundError) as exc:
        raise policy_denied(f"approval verification failed: {exc}", work_unit.id, policy.policy_bundle_id) from exc


def _require_exact_verifiers(required: list[str], accepted: bool, work_unit_id: str) -> None:
    aliases = {"sha256_restore", "sha256_restore@0"}
    unsupported = [name for name in required if name not in aliases]
    if unsupported:
        raise verifier_failed("required verifier is not implemented for exact execution", work_unit_id, {"unsupported": unsupported})
    if required and not accepted:
        raise verifier_failed("required exact verifier failed", work_unit_id)


def _record_observation(
    work_unit: WorkUnit,
    state: Path,
    policy: Any,
    plan: Any,
    classification: Any,
    payload: bytes,
    whole_hash: str,
    adapter_name: str | None,
) -> ExecutionResult:
    manifest = Manifest(
        work_unit_id=work_unit.id,
        tenant=work_unit.tenant,
        kind=work_unit.kind,
        contract=policy.contract,
        logical_ref=work_unit.logical_ref,
        namespace=work_unit.namespace,
        trace_id=work_unit.trace_id,
        state="planned",
        policy=policy.to_dict(),
        classification={
            "entropy_bits_per_byte": classification.entropy_bits_per_byte,
            "likely_compressed": classification.likely_compressed,
            "likely_encrypted": classification.likely_encrypted,
            "schema_hint": classification.schema_hint,
            "notes": classification.notes,
        },
        plan=plan.to_dict(),
        physical={
            "mode": "observe",
            "whole_sha256": whole_hash,
            "logical_size": len(payload),
            "stored_size": 0,
            "segments": [],
            "rehydratable": False,
            **({"adapter": adapter_name} if adapter_name else {}),
        },
        verification={"accepted": True, "verifier_id": "observe_only@1", "reason": "no_transform_executed", "details": {}},
        telemetry={"mode": "observe", "bytes_in": len(payload), "bytes_stored": 0, "bytes_avoided": 0, "chunk_count": 0, "dedupe_hits": 0},
    )
    default_manifest_store(state).put(manifest)
    default_ledger(state).append(
        LedgerEvent(
            "manifest.written",
            work_unit.tenant,
            work_unit.id,
            manifest.manifest_id,
            policy.policy_bundle_id,
            details={"logical_ref": work_unit.logical_ref, "mode": "observe"},
            trace_id=work_unit.trace_id,
        )
    )
    return ExecutionResult(
        work_unit.id,
        manifest.manifest_id,
        True,
        "observe",
        {"sha256": whole_hash, "passthrough": True, "rehydratable": False},
        {"bytes_in": len(payload), "bytes_stored": 0},
    )
