from __future__ import annotations

import json
import hashlib
import concurrent.futures
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from .approval_store import ApprovalStore
from .auth import APIKeyAuthenticator, LocalAuthorizer, Principal, principal_context
from .contracts import Contract, LedgerEvent, WorkUnit, WorkUnitKind, stable_json_hash
from .deployment_validation import validate_deployment_artifacts
from .disaster_recovery import export_state, import_state
from .executor import execute_work_unit, rehydrate_manifest
from .kms import LocalKMS
from .ledger import default_ledger
from .manifest_store import default_manifest_store
from .platforms import platform_matrix
from .policy_store import PolicyBundleStore
from .storage import atomic_write_bytes
from .structured_logs import redact_details
from .spec_validation import validate_api_specs


@dataclass(frozen=True)
class ProductionReadinessResult:
    name: str
    passed: bool
    checks: Dict[str, bool]
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "checks": self.checks, "details": self.details}


def production_readiness_check(state_dir: str | Path | None = None, repo_root: str | Path | None = None) -> ProductionReadinessResult:
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[2]
    if state_dir is None:
        with tempfile.TemporaryDirectory() as td:
            return _run_readiness(Path(td), root, temporary_state=True)
    return _run_readiness(Path(state_dir), root, temporary_state=False)


def _run_readiness(state: Path, root: Path, temporary_state: bool) -> ProductionReadinessResult:
    state.mkdir(parents=True, exist_ok=True)
    payload = b"urp production readiness exact payload\n" * 64
    work_unit = WorkUnit(WorkUnitKind.BYTE_OBJECT, "readiness", "readiness://restart-persistence", payload)
    execution = execute_work_unit(work_unit, state)
    manifest_id = execution.manifest_id
    restarted_manifest = default_manifest_store(state).get(manifest_id)
    restarted_payload = rehydrate_manifest(manifest_id, state)

    policy_record = PolicyBundleStore(state).publish(root / "examples/policies/default_policy.yaml", actor="readiness-admin")
    policy_audit_events = default_ledger(state).query(event_types=["policy.bundle.published"])

    kms = LocalKMS(state)
    key = kms.create_key("production-readiness")
    envelope = kms.encrypt(key.key_id, b"readiness-secret", aad=b"readiness")
    kms_roundtrip = kms.decrypt(envelope, aad=b"readiness") == b"readiness-secret"

    authorizer = LocalAuthorizer()
    viewer = Principal("readiness-viewer", "readiness", {"viewer"})
    authz_enforced = authorizer.allowed(viewer, "manifest:read", "readiness") and not authorizer.allowed(viewer, "work_unit:write", "readiness")
    authenticator = APIKeyAuthenticator({"readiness-secret": Principal("readiness-operator", "readiness", {"operator"})})
    authentication_enforced = authenticator.authenticate("readiness-secret").actor == "readiness-operator"
    try:
        authenticator.authenticate("invalid-secret")
    except Exception:
        authentication_enforced = authentication_enforced and True
    else:
        authentication_enforced = False

    tenant_isolation_enforced = False
    with principal_context(Principal("other-tenant", "other", {"viewer"})):
        try:
            default_manifest_store(state).get(manifest_id)
        except Exception:
            tenant_isolation_enforced = True

    approval_bundle = {
        "apiVersion": "urp.dev/v1",
        "kind": "ReductionPolicy",
        "metadata": {"name": "readiness-approval"},
        "spec": {
            "defaults": {"contract": "exact_bytes", "semanticReduction": "deny"},
            "rules": [
                {
                    "name": "approval-gate",
                    "match": {"kind": "byte_object"},
                    "contract": "exact_bytes",
                    "requires_approval": True,
                    "require": {"verifiers": ["sha256_restore"]},
                }
            ],
        },
    }
    PolicyBundleStore(state).publish(approval_bundle, actor="readiness-admin")
    gated = WorkUnit(
        WorkUnitKind.BYTE_OBJECT,
        "readiness",
        "readiness://approval",
        b"approval-gated",
        policy_context={"policy_bundle_id": "readiness-approval"},
    )
    approval_denial_enforced = False
    try:
        execute_work_unit(gated, state)
    except Exception:
        approval_denial_enforced = True
    approval = ApprovalStore(state).issue(
        tenant="readiness",
        actor="readiness-admin",
        contract=Contract.EXACT_BYTES,
        policy_bundle_id="readiness-approval",
        reason="production readiness gate",
        work_unit_id=gated.id,
    )
    approved = WorkUnit(
        kind=gated.kind,
        tenant=gated.tenant,
        logical_ref=gated.logical_ref,
        payload=gated.payload,
        policy_context={"policy_bundle_id": "readiness-approval", "approval_id": approval.approval_id},
        id=gated.id,
        trace_id=gated.trace_id,
        created_at=gated.created_at,
    )
    signed_approval_enforced = execute_work_unit(approved, state).accepted

    redacted = redact_details({"outer": {"authorization": "Bearer secret", "rows": [{"prompt": "private"}]}, "safe": "visible"})
    recursive_redaction = redacted["outer"]["authorization"] == "[redacted]" and redacted["outer"]["rows"][0]["prompt"] == "[redacted]" and redacted["safe"] == "visible"

    tamper_result = execute_work_unit(WorkUnit(WorkUnitKind.BYTE_OBJECT, "readiness", "readiness://tamper", b"0123456789"), state)
    tamper_manifest = default_manifest_store(state).get(tamper_result.manifest_id)
    segment_path = state / "chunks" / str(tamper_manifest.physical["segments"][0]["ref"])
    original_segment = segment_path.read_bytes()
    tamper_detected = False
    try:
        atomic_write_bytes(segment_path, bytes([original_segment[0] ^ 0xFF]) + original_segment[1:])
        from .executor import rehydrate_manifest_range

        rehydrate_manifest_range(tamper_result.manifest_id, 0, 4, state)
    except Exception:
        tamper_detected = True
    finally:
        atomic_write_bytes(segment_path, original_segment)

    def append_concurrent(index: int) -> None:
        default_ledger(state).append(LedgerEvent("readiness.concurrent", "readiness", details={"index": index}))

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(append_concurrent, range(32)))
    concurrent_ledger_chain_valid = default_ledger(state).verify_chain()
    kms_material_redacted = "material" not in key.to_dict() and "wrapped_material" not in key.to_dict()

    with tempfile.TemporaryDirectory() as restore_tmp:
        archive = Path(restore_tmp) / "urp-backup.zip"
        restored_state = Path(restore_tmp) / "restored"
        backup_manifest = export_state(state, archive)
        restore = import_state(archive, restored_state)
        restored_payload = rehydrate_manifest(manifest_id, restored_state)
        tampered = Path(restore_tmp) / "urp-backup-tampered.zip"
        tampered_entry = _write_tampered_archive(archive, tampered)
        backup_integrity_detected = False
        try:
            import_state(tampered, Path(restore_tmp) / "tampered")
        except ValueError:
            backup_integrity_detected = True
        zip_slip_rejected = _zip_slip_rejected(Path(restore_tmp))

    deployment = _deployment_checks(root)
    static_deployment = validate_deployment_artifacts(root)
    spec_validation = validate_api_specs(root)
    checks = {
        "manifest_persists_after_restart": restarted_manifest.manifest_id == manifest_id,
        "exact_rehydration_after_restart": restarted_payload == payload,
        "policy_change_audited": any(event.actor == "readiness-admin" and event.decision == policy_record["version"] for event in policy_audit_events),
        "kms_roundtrip": kms_roundtrip,
        "authz_enforced": authz_enforced,
        "authentication_enforced": authentication_enforced,
        "tenant_isolation_enforced": tenant_isolation_enforced,
        "approval_denial_enforced": approval_denial_enforced,
        "signed_approval_enforced": signed_approval_enforced,
        "recursive_redaction": recursive_redaction,
        "range_tamper_detected": tamper_detected,
        "concurrent_ledger_chain_valid": concurrent_ledger_chain_valid,
        "kms_material_redacted": kms_material_redacted,
        "backup_restore_rehydrates": restore.get("imported") is True and restored_payload == payload,
        "backup_integrity_detected": backup_integrity_detected and bool(tampered_entry),
        "backup_zip_slip_rejected": zip_slip_rejected,
        **deployment["checks"],
        **static_deployment.checks,
        **spec_validation.checks,
    }
    details = {
        "state_dir": str(state),
        "temporary_state": temporary_state,
        "manifest_id": manifest_id,
        "work_unit_id": execution.work_unit_id,
        "policy_bundle": {"name": policy_record["name"], "version": policy_record["version"]},
        "backup_file_count": len(backup_manifest.get("files", {})),
        "tampered_backup_entry": tampered_entry,
        "deployment_files": deployment["files"],
        "deployment_static_validation": static_deployment.to_dict(),
        "api_spec_validation": spec_validation.to_dict(),
    }
    return ProductionReadinessResult("production-readiness-local-v1", all(checks.values()), checks, details)


def _deployment_checks(root: Path) -> Dict[str, Any]:
    kubernetes = root / "deployments/kubernetes/urp-control-plane.yaml"
    compose = root / "deployments/docker-compose/docker-compose.yaml"
    terraform = root / "deployments/terraform/aws/main.tf"
    azure_terraform = root / "deployments/terraform/azure/main.tf"
    gcp_terraform = root / "deployments/terraform/gcp/main.tf"
    on_prem_compose = root / "deployments/on-prem/docker-compose.airgap.yaml"
    on_prem_systemd = root / "deployments/on-prem/systemd/urp-control-plane.service"
    edge_sidecar = root / "deployments/edge/urp-edge-sidecar.yaml"
    operator = root / "deployments/operator/urp-operator.yaml"
    multi_region = root / "deployments/kubernetes/urp-multi-region.yaml"
    paths = [kubernetes, compose, terraform, azure_terraform, gcp_terraform, on_prem_compose, on_prem_systemd, edge_sidecar, operator, multi_region]
    texts = {path: path.read_text(encoding="utf-8") if path.exists() else "" for path in paths}
    platforms = platform_matrix(root)
    checks = {
        "ha_deployment_declared": "replicas: 2" in texts[kubernetes] or "replicas: 3" in texts[kubernetes],
        "postgres_backend_declared": "postgres" in texts[compose] and "URP_MANIFEST_STORE" in texts[compose],
        "versioned_object_backend_declared": "aws_s3_bucket_versioning" in texts[terraform],
        "azure_backend_declared": "azurerm_storage_account" in texts[azure_terraform] and "azurerm_key_vault" in texts[azure_terraform],
        "gcp_backend_declared": "google_storage_bucket" in texts[gcp_terraform] and "google_kms_crypto_key" in texts[gcp_terraform],
        "on_prem_airgap_declared": "URP_AIRGAP_MODE" in texts[on_prem_compose] and "control-plane" in texts[on_prem_systemd],
        "edge_sidecar_declared": "kind: DaemonSet" in texts[edge_sidecar] and "URP_EDGE_MODE" in texts[edge_sidecar],
        "operator_manifest_declared": "kind: CustomResourceDefinition" in texts[operator] and "kind: URPControlPlane" in texts[operator],
        "multi_region_topology_declared": "topology.kubernetes.io/region" in texts[multi_region] and "URP_MULTI_REGION" in texts[multi_region],
        "all_platform_profiles_contract_ready": platforms["contract_ready_count"] == platforms["platform_count"],
    }
    return {"checks": checks, "files": {str(path.relative_to(root)): str(path) for path in texts}, "platform_matrix": platforms}


def _write_tampered_archive(source: Path, target: Path) -> str | None:
    tampered_entry: str | None = None
    with zipfile.ZipFile(source, "r") as src, zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if tampered_entry is None and info.filename != "backup_manifest.json" and not info.is_dir():
                tampered_entry = info.filename
                data = b"tampered"
            dst.writestr(info, data)
    return tampered_entry


def _zip_slip_rejected(root: Path) -> bool:
    archive = root / "zip-slip.zip"
    malicious_name = "../outside-state"
    content = b"escape"
    files = {malicious_name: {"sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}}
    manifest = {
        "backup_version": "urp.backup.v2",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "state_format": "local-durable-v1",
        "files": files,
        "content_hash": stable_json_hash(files),
    }
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(malicious_name, content)
        output.writestr("backup_manifest.json", json.dumps(manifest))
    try:
        import_state(archive, root / "zip-slip-state")
    except ValueError:
        return not (root / "outside-state").exists()
    return False
