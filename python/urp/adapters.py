from __future__ import annotations

import json
from dataclasses import replace
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Protocol

from .contracts import Contract, LedgerEvent, WorkUnit, WorkUnitKind, new_id
from .executor import execute_work_unit, rehydrate_manifest, rehydrate_manifest_range
from .ledger import default_ledger
from .manifest_store import default_manifest_store
from .planner import plan_work_unit
from .storage import atomic_write_bytes, atomic_write_json, file_lock, validate_identifier
from .chunking import sha256_bytes


class Adapter(Protocol):
    name: str

    def capabilities(self) -> Dict[str, Any]:
        ...


@dataclass(frozen=True)
class AdapterResult:
    accepted: bool
    details: Dict[str, Any]


class LocalS3Adapter:
    name = "local_s3"

    def __init__(self, state_dir: str | Path = ".urp", tenant: str = "local") -> None:
        self.state_dir = Path(state_dir)
        self.tenant = tenant

    def capabilities(self) -> Dict[str, Any]:
        return {
            "put_object": True,
            "get_object": True,
            "head_object": True,
            "range_read": True,
            "list_objects_v2": True,
            "delete_object": True,
            "multipart": True,
            "metadata_headers": True,
            "object_tags": True,
        }

    def put_object(
        self,
        bucket: str,
        key: str,
        body: bytes,
        namespace: str = "s3",
        metadata: Dict[str, Any] | None = None,
        tags: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        object_metadata = dict(metadata or {})
        object_tags = dict(tags or {})
        policy_context = {"tags": object_tags}
        if _truthy_tag(object_tags.get("legal_hold")):
            policy_context["legal_hold"] = True
        wu = WorkUnit(
            WorkUnitKind.BYTE_OBJECT,
            self.tenant,
            f"s3://{bucket}/{key}",
            body,
            namespace=namespace,
            metadata={"bucket": bucket, "key": key, "object_metadata": object_metadata, "tags": object_tags},
            policy_context=policy_context,
        )
        result = execute_work_unit(wu, self.state_dir, mode="enforce")
        return {"bucket": bucket, "key": key, "work_unit_id": result.work_unit_id, "manifest_id": result.manifest_id, "etag": result.output["sha256"]}

    def get_object(self, manifest_id: str) -> bytes:
        default_manifest_store(self.state_dir).get_for_tenant(manifest_id, self.tenant)
        return rehydrate_manifest(manifest_id, self.state_dir)

    def range_read(self, manifest_id: str, start: int, end: int) -> bytes:
        default_manifest_store(self.state_dir).get_for_tenant(manifest_id, self.tenant)
        return rehydrate_manifest_range(manifest_id, start, end, self.state_dir)

    def create_multipart_upload(
        self,
        bucket: str,
        key: str,
        namespace: str = "s3",
        metadata: Dict[str, Any] | None = None,
        tags: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        if not bucket.strip() or not key:
            raise ValueError("bucket and key are required")
        upload_id = new_id("mpu")
        root = self._multipart_dir(upload_id)
        root.mkdir(parents=True, exist_ok=True)
        atomic_write_json(
            root / "meta.json",
            {
                "tenant": self.tenant,
                "bucket": bucket,
                "key": key,
                "namespace": namespace,
                "metadata": metadata or {},
                "tags": tags or {},
                "parts": {},
                "status": "open",
            },
        )
        return {"upload_id": upload_id, "bucket": bucket, "key": key}

    def upload_part(self, upload_id: str, part_number: int, body: bytes) -> Dict[str, Any]:
        if part_number <= 0 or part_number > 10_000:
            raise ValueError("part_number must be between 1 and 10000")
        root = self._multipart_dir(upload_id)
        if not root.exists():
            raise KeyError(upload_id)
        digest = sha256_bytes(body)
        with file_lock(root / ".multipart.lock"):
            meta = json.loads((root / "meta.json").read_text(encoding="utf-8"))
            self._require_multipart_tenant(root, meta)
            if meta.get("status", "open") != "open":
                raise ValueError("multipart upload is not open")
            path = root / f"part-{part_number:08d}.bin"
            atomic_write_bytes(path, body)
            meta.setdefault("parts", {})[str(part_number)] = {"sha256": digest, "size": len(body), "file": path.name}
            atomic_write_json(root / "meta.json", meta)
        return {"upload_id": upload_id, "part_number": part_number, "size": len(body), "etag": digest}

    def complete_multipart_upload(self, upload_id: str) -> Dict[str, Any]:
        root = self._multipart_dir(upload_id)
        if not root.exists():
            raise KeyError(upload_id)
        with file_lock(root / ".multipart.lock"):
            meta = json.loads((root / "meta.json").read_text(encoding="utf-8"))
            self._require_multipart_tenant(root, meta)
            if meta.get("status", "open") != "open":
                raise ValueError("multipart upload is already completing")
            part_records = meta.get("parts", {})
            if not part_records:
                raise ValueError("multipart upload has no parts")
            bodies: List[bytes] = []
            for part_number in sorted((int(number) for number in part_records)):
                record = part_records[str(part_number)]
                path = root / str(record["file"])
                data = path.read_bytes()
                if len(data) != int(record["size"]) or sha256_bytes(data) != record["sha256"]:
                    raise ValueError(f"multipart part verification failed: {part_number}")
                bodies.append(data)
            body = b"".join(bodies)
            meta["status"] = "completing"
            atomic_write_json(root / "meta.json", meta)
        try:
            result = self.put_object(
                meta["bucket"],
                meta["key"],
                body,
                meta.get("namespace", "s3"),
                meta.get("metadata"),
                meta.get("tags"),
            )
        except Exception:
            with file_lock(root / ".multipart.lock"):
                if root.exists():
                    current = json.loads((root / "meta.json").read_text(encoding="utf-8"))
                    current["status"] = "open"
                    atomic_write_json(root / "meta.json", current)
            raise
        result["upload_id"] = upload_id
        result["parts"] = len(part_records)
        self._remove_multipart(root, expected_status="completing")
        return result

    def abort_multipart_upload(self, upload_id: str) -> Dict[str, Any]:
        root = self._multipart_dir(upload_id)
        if root.exists():
            self._remove_multipart(root, expected_status="open")
        return {"upload_id": upload_id, "aborted": True}

    def head_object(self, manifest_id: str) -> Dict[str, Any]:
        manifest = default_manifest_store(self.state_dir).get_for_tenant(manifest_id, self.tenant)
        source = manifest.lineage.get("work_unit_metadata", {})
        return {
            "manifest_id": manifest.manifest_id,
            "work_unit_id": manifest.work_unit_id,
            "content_length": manifest.physical.get("logical_size", 0),
            "sha256": manifest.physical.get("whole_sha256"),
            "metadata": source.get("object_metadata", {}),
            "tags": source.get("tags", {}),
        }

    def list_objects(self, bucket: str | None = None, prefix: str = "", include_tombstoned: bool = False) -> Dict[str, Any]:
        rows = []
        for manifest in default_manifest_store(self.state_dir).list(self.tenant):
            if manifest.state == "tombstoned" and not include_tombstoned:
                continue
            source = manifest.lineage.get("work_unit_metadata", {})
            if "bucket" not in source or "key" not in source:
                continue
            key = source.get("key", "")
            if bucket and source.get("bucket") != bucket:
                continue
            if prefix and not str(key).startswith(prefix):
                continue
            rows.append(
                {
                    "bucket": source.get("bucket"),
                    "key": key,
                    "manifest_id": manifest.manifest_id,
                    "state": manifest.state,
                    "size": manifest.physical.get("logical_size", 0),
                    "metadata": source.get("object_metadata", {}),
                    "tags": source.get("tags", {}),
                }
            )
        return {"objects": rows, "count": len(rows)}

    def delete_object(self, manifest_id: str, actor: str = "local", allow_delete: bool = False) -> Dict[str, Any]:
        store = default_manifest_store(self.state_dir)
        manifest = store.get_for_tenant(manifest_id, self.tenant)
        legal_hold = manifest.lineage.get("policy_context", {}).get("legal_hold") is True
        ledger = default_ledger(self.state_dir)
        if legal_hold or not allow_delete:
            reason = "legal_hold" if legal_hold else "delete_disabled_by_default"
            ledger.append(
                LedgerEvent(
                    "s3.delete.denied",
                    manifest.tenant,
                    manifest.work_unit_id,
                    manifest.manifest_id,
                    actor=actor,
                    decision="denied",
                    details={"reason": reason},
                    trace_id=manifest.trace_id,
                )
            )
            return {"deleted": False, "manifest_id": manifest_id, "reason": reason}
        tombstone = replace(manifest, state="tombstoned")
        store.put(tombstone)
        ledger.append(
            LedgerEvent(
                "s3.delete.tombstoned",
                manifest.tenant,
                manifest.work_unit_id,
                manifest.manifest_id,
                actor=actor,
                decision="tombstoned",
                details={"raw_chunks_retained": True},
                trace_id=manifest.trace_id,
            )
        )
        return {"deleted": True, "manifest_id": manifest_id, "state": "tombstoned", "raw_chunks_retained": True}

    def _multipart_dir(self, upload_id: str) -> Path:
        validate_identifier(upload_id, label="multipart upload id", prefix="mpu_")
        return Path(self.state_dir) / "tmp" / "multipart" / upload_id

    def _require_multipart_tenant(self, root: Path, meta: Dict[str, Any] | None = None) -> None:
        record = meta or json.loads((root / "meta.json").read_text(encoding="utf-8"))
        if record.get("tenant") != self.tenant:
            from .errors import tenant_mismatch

            raise tenant_mismatch(self.tenant, str(record.get("tenant")))

    def _remove_multipart(self, root: Path, *, expected_status: str) -> None:
        with file_lock(root / ".multipart.lock"):
            meta = json.loads((root / "meta.json").read_text(encoding="utf-8"))
            self._require_multipart_tenant(root, meta)
            if meta.get("status", "open") != expected_status:
                raise ValueError(f"multipart upload must be {expected_status} for cleanup")
            for path in root.iterdir():
                if not path.is_file():
                    raise ValueError("multipart upload directory contains an unexpected entry")
                if path.name != ".multipart.lock":
                    path.unlink()
        (root / ".multipart.lock").unlink(missing_ok=True)
        root.rmdir()


class POSIXAdapter:
    name = "posix"

    def __init__(self, state_dir: str | Path = ".urp", tenant: str = "local") -> None:
        self.state_dir = Path(state_dir)
        self.tenant = tenant

    def capabilities(self) -> Dict[str, Any]:
        return {
            "plan_file": True,
            "execute_file": True,
            "read_file": True,
            "write_file": True,
            "rehydrate_file": True,
            "stat_file": True,
            "list_dir": True,
        }

    def plan_file(self, path: str | Path, namespace: str = "posix") -> Dict[str, Any]:
        return plan_work_unit(self._work_unit_for_path(path, namespace), mode="observe").to_dict()

    def execute_file(self, path: str | Path, namespace: str = "posix") -> Dict[str, Any]:
        return execute_work_unit(self._work_unit_for_path(path, namespace), self.state_dir).to_dict()

    def put_file(self, path: str | Path, data: bytes, namespace: str = "posix", overwrite: bool = False) -> Dict[str, Any]:
        p = Path(path)
        if p.exists() and not overwrite:
            raise FileExistsError(str(p))
        atomic_write_bytes(p, data)
        return self.execute_file(p, namespace=namespace)

    def write_file(self, path: str | Path, data: bytes, namespace: str = "posix", overwrite: bool = False) -> Dict[str, Any]:
        return self.put_file(path, data, namespace=namespace, overwrite=overwrite)

    def read_file(self, manifest_id: str) -> bytes:
        default_manifest_store(self.state_dir).get_for_tenant(manifest_id, self.tenant)
        return rehydrate_manifest(manifest_id, self.state_dir)

    def rehydrate_file(self, manifest_id: str, output_path: str | Path, overwrite: bool = False) -> Dict[str, Any]:
        data = self.read_file(manifest_id)
        out = Path(output_path)
        if out.exists() and not overwrite:
            raise FileExistsError(str(out))
        atomic_write_bytes(out, data)
        return {"manifest_id": manifest_id, "path": str(out), "bytes": len(data)}

    def stat_file(self, manifest_id: str) -> Dict[str, Any]:
        manifest = default_manifest_store(self.state_dir).get_for_tenant(manifest_id, self.tenant)
        source = manifest.lineage.get("work_unit_metadata", {})
        return {
            "manifest_id": manifest.manifest_id,
            "work_unit_id": manifest.work_unit_id,
            "logical_ref": manifest.logical_ref,
            "path": source.get("path"),
            "content_length": manifest.physical.get("logical_size", 0),
            "sha256": manifest.physical.get("whole_sha256"),
            "mode": source.get("mode"),
            "mtime_ns": source.get("mtime_ns"),
        }

    def list_dir(self, path: str | Path) -> Dict[str, Any]:
        root = Path(path)
        rows = []
        for child in sorted(root.iterdir()):
            stat = child.stat()
            rows.append(
                {
                    "name": child.name,
                    "path": str(child),
                    "type": "dir" if child.is_dir() else "file",
                    "size": stat.st_size,
                    "mode": stat.st_mode,
                    "mtime_ns": stat.st_mtime_ns,
                }
            )
        return {"path": str(root), "entries": rows, "count": len(rows)}

    def _work_unit_for_path(self, path: str | Path, namespace: str) -> WorkUnit:
        p = Path(path)
        stat = p.stat()
        return WorkUnit(
            WorkUnitKind.FILE,
            self.tenant,
            str(p),
            p.read_bytes(),
            namespace=namespace,
            metadata={
                "path": str(p),
                "name": p.name,
                "mode": stat.st_mode,
                "mtime_ns": stat.st_mtime_ns,
                "size": stat.st_size,
            },
        )


class MockContractAdapter:
    def __init__(self, name: str, kinds: List[WorkUnitKind], state_dir: str | Path = ".urp", tenant: str = "local") -> None:
        self.name = name
        self.kinds = kinds
        self.state_dir = Path(state_dir)
        self.tenant = tenant

    def capabilities(self) -> Dict[str, Any]:
        return {
            "mock": True,
            "plan_work_unit": True,
            "execute_work_unit": True,
            "submit_work_unit": True,
            "rehydrate": True,
            "kinds": [kind.value for kind in self.kinds],
            "external_integrations_required": False,
        }

    def plan(self, work_unit: WorkUnit, mode: str = "observe") -> Dict[str, Any]:
        self._ensure_supported(work_unit.kind)
        return plan_work_unit(work_unit, mode=mode).to_dict()

    def plan_work_unit(self, work_unit: WorkUnit, mode: str = "observe") -> Dict[str, Any]:
        return self.plan(work_unit, mode=mode)

    def execute(self, work_unit: WorkUnit, state_dir: str | Path | None = None, mode: str = "enforce") -> Dict[str, Any]:
        self._ensure_supported(work_unit.kind)
        return execute_work_unit(work_unit, state_dir or self.state_dir, mode=mode).to_dict()

    def execute_work_unit(self, work_unit: WorkUnit, state_dir: str | Path | None = None, mode: str = "enforce") -> Dict[str, Any]:
        return self.execute(work_unit, state_dir=state_dir, mode=mode)

    def submit_work_unit(
        self,
        kind: WorkUnitKind | str,
        logical_ref: str,
        payload: Any = None,
        *,
        state_dir: str | Path | None = None,
        tenant: str | None = None,
        namespace: str | None = None,
        requested_contract: Contract | str | None = None,
        metadata: Dict[str, Any] | None = None,
        policy_context: Dict[str, Any] | None = None,
        mode: str = "enforce",
    ) -> Dict[str, Any]:
        resolved_kind = WorkUnitKind(kind)
        self._ensure_supported(resolved_kind)
        contract = Contract(requested_contract) if requested_contract else None
        work_unit = WorkUnit(
            resolved_kind,
            tenant or self.tenant,
            logical_ref,
            payload,
            requested_contract=contract,
            namespace=namespace or self.name,
            metadata={**(metadata or {}), "adapter": self.name},
            policy_context=dict(policy_context or {}),
        )
        result = execute_work_unit(work_unit, state_dir or self.state_dir, mode=mode).to_dict()
        result["adapter"] = self.name
        result["kind"] = resolved_kind.value
        return result

    def execute_kind(
        self,
        kind: WorkUnitKind | str,
        logical_ref: str,
        payload: Any = None,
        *,
        state_dir: str | Path | None = None,
        tenant: str | None = None,
        namespace: str | None = None,
        requested_contract: Contract | str | None = None,
        metadata: Dict[str, Any] | None = None,
        policy_context: Dict[str, Any] | None = None,
        mode: str = "enforce",
    ) -> Dict[str, Any]:
        return self.submit_work_unit(
            kind,
            logical_ref,
            payload,
            state_dir=state_dir,
            tenant=tenant,
            namespace=namespace,
            requested_contract=requested_contract,
            metadata=metadata,
            policy_context=policy_context,
            mode=mode,
        )

    def rehydrate(self, manifest_id: str, state_dir: str | Path | None = None) -> bytes:
        return rehydrate_manifest(manifest_id, state_dir or self.state_dir)

    def _ensure_supported(self, kind: WorkUnitKind) -> None:
        if kind not in self.kinds:
            supported = ", ".join(item.value for item in self.kinds)
            raise ValueError(f"{self.name} adapter does not support {kind.value}; supported kinds: {supported}")


def built_in_adapters() -> Dict[str, Adapter]:
    return {
        "s3": LocalS3Adapter(),
        "posix": POSIXAdapter(),
        "sql": MockContractAdapter("sql", [WorkUnitKind.TABLE_SNAPSHOT, WorkUnitKind.TABLE_ROW_GROUP]),
        "lakehouse": MockContractAdapter("lakehouse", [WorkUnitKind.TABLE_SNAPSHOT, WorkUnitKind.STRUCTURED_FILE]),
        "stream": MockContractAdapter("stream", [WorkUnitKind.STREAM_SEGMENT, WorkUnitKind.EVENT_BATCH]),
        "otlp": MockContractAdapter("otlp", [WorkUnitKind.TRACE_BATCH, WorkUnitKind.METRIC_SERIES, WorkUnitKind.LOG_BATCH]),
        "training": MockContractAdapter("training", [WorkUnitKind.FINE_TUNE_JOB, WorkUnitKind.TRAINING_DATASET, WorkUnitKind.MODEL_CHECKPOINT]),
        "vector": MockContractAdapter("vector", [WorkUnitKind.EMBEDDING_BATCH, WorkUnitKind.VECTOR_INDEX_SEGMENT]),
        "edge": MockContractAdapter("edge", [WorkUnitKind.BATCH_COMPUTE_JOB]),
        "cicd": MockContractAdapter("cicd", [WorkUnitKind.PLUGIN_ACTION]),
    }


def _truthy_tag(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def validate_plugin_descriptor(descriptor: Dict[str, Any]) -> AdapterResult:
    required = {
        "api_version",
        "name",
        "version",
        "category",
        "capabilities",
        "contracts",
        "trust_level",
        "entrypoint",
        "entrypoint_sha256",
        "network_access",
        "operations",
        "default_enabled",
    }
    missing = sorted(required - set(descriptor))
    if missing:
        return AdapterResult(False, {"missing": missing})
    if descriptor["trust_level"] not in {"core", "certified", "community", "local"}:
        return AdapterResult(False, {"error": "invalid_trust_level"})
    if descriptor.get("api_version") != "urp.plugin.v1":
        return AdapterResult(False, {"error": "unsupported_api_version"})
    if descriptor.get("category") not in {"adapters", "classifiers", "transforms", "verifiers"}:
        return AdapterResult(False, {"error": "invalid_category"})
    try:
        validate_identifier(str(descriptor["name"]), label="plugin name")
        validate_identifier(str(descriptor["version"]), label="plugin version")
    except ValueError as exc:
        return AdapterResult(False, {"error": str(exc)})
    capabilities = descriptor.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities or not all(isinstance(item, str) and item for item in capabilities):
        return AdapterResult(False, {"error": "capabilities_must_be_non_empty_strings"})
    operations = descriptor.get("operations")
    if not isinstance(operations, list) or not operations or not all(isinstance(item, str) and item for item in operations):
        return AdapterResult(False, {"error": "operations_must_be_non_empty_strings"})
    if not isinstance(descriptor.get("entrypoint"), str) or not descriptor.get("entrypoint"):
        return AdapterResult(False, {"error": "entrypoint_must_be_a_string"})
    digest = descriptor.get("entrypoint_sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        return AdapterResult(False, {"error": "entrypoint_sha256_must_be_lowercase_hex"})
    contracts = descriptor.get("contracts")
    if not isinstance(contracts, list) or not contracts or not all(item in {contract.value for contract in Contract} for item in contracts):
        return AdapterResult(False, {"error": "invalid_contracts"})
    if not isinstance(descriptor.get("network_access"), bool) or not isinstance(descriptor.get("default_enabled"), bool):
        return AdapterResult(False, {"error": "network_access_and_default_enabled_must_be_boolean"})
    return AdapterResult(True, {"descriptor": descriptor["name"]})
