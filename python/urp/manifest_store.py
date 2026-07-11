from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from typing import Dict, List

from .contracts import Manifest
from .schema_validation import validate_named_schema
from .storage import atomic_write_json, ensure_private_file, file_lock, validate_identifier
from .structured_logs import redact_details
from .auth import current_tenant


class InMemoryManifestStore:
    def __init__(self) -> None:
        self._by_id: Dict[str, Manifest] = {}
        self._by_work_unit: Dict[str, str] = {}
        self._lock = threading.RLock()

    def put(self, manifest: Manifest) -> None:
        _enforce_request_tenant(manifest)
        _validate_manifest(manifest)
        with self._lock:
            self._by_id[manifest.manifest_id] = manifest
            self._by_work_unit[manifest.work_unit_id] = manifest.manifest_id

    def get(self, manifest_id: str) -> Manifest:
        with self._lock:
            manifest = self._by_id[manifest_id]
        _enforce_request_tenant(manifest)
        return manifest

    def get_for_tenant(self, manifest_id: str, tenant: str) -> Manifest:
        manifest = self.get(manifest_id)
        _require_manifest_tenant(manifest, tenant)
        return manifest

    def get_by_work_unit(self, work_unit_id: str) -> Manifest:
        with self._lock:
            manifest = self._by_id[self._by_work_unit[work_unit_id]]
        _enforce_request_tenant(manifest)
        return manifest

    def list(self, tenant: str | None = None) -> List[Manifest]:
        tenant = tenant or current_tenant()
        with self._lock:
            rows = list(self._by_id.values())
        return [row for row in rows if row.tenant == tenant] if tenant else rows

    def find_by_logical_ref(self, logical_ref: str) -> List[Manifest]:
        return [m for m in self.list() if m.logical_ref == logical_ref]


class FileManifestStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, manifest_id: str) -> Path:
        validate_identifier(manifest_id, label="manifest id", prefix="mf_")
        return self.root / f"{manifest_id}.json"

    def put(self, manifest: Manifest) -> None:
        _enforce_request_tenant(manifest)
        data = _validate_manifest(manifest)
        path = self._path(manifest.manifest_id)
        with file_lock(self.root / ".manifest.lock"):
            atomic_write_json(path, data)

    def get(self, manifest_id: str) -> Manifest:
        with file_lock(self.root / ".manifest.lock", exclusive=False):
            with self._path(manifest_id).open("r", encoding="utf-8") as fh:
                manifest = Manifest.from_dict(json.load(fh))
        _enforce_request_tenant(manifest)
        return manifest

    def get_for_tenant(self, manifest_id: str, tenant: str) -> Manifest:
        manifest = self.get(manifest_id)
        _require_manifest_tenant(manifest, tenant)
        return manifest

    def get_by_work_unit(self, work_unit_id: str) -> Manifest:
        for manifest in self.list():
            if manifest.work_unit_id == work_unit_id:
                return manifest
        raise KeyError(work_unit_id)

    def list(self, tenant: str | None = None) -> List[Manifest]:
        tenant = tenant or current_tenant()
        manifests: List[Manifest] = []
        with file_lock(self.root / ".manifest.lock", exclusive=False):
            for path in sorted(self.root.glob("mf_*.json")):
                with path.open("r", encoding="utf-8") as fh:
                    manifest = Manifest.from_dict(json.load(fh))
                if tenant is None or manifest.tenant == tenant:
                    manifests.append(manifest)
        return manifests

    def find_by_logical_ref(self, logical_ref: str) -> List[Manifest]:
        return [m for m in self.list() if m.logical_ref == logical_ref]

    def redacted(self, manifest_id: str) -> Dict[str, object]:
        return redact_manifest(self.get(manifest_id))


class SQLiteManifestStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        ensure_private_file(self.path)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=30)
        db.execute("pragma journal_mode=wal")
        db.execute("pragma busy_timeout=30000")
        return db

    def _init(self) -> None:
        with closing(self._connect()) as db:
            db.execute(
                "create table if not exists manifests (manifest_id text primary key, work_unit_id text, logical_ref text, tenant text, created_at text, payload text not null)"
            )
            columns = {row[1] for row in db.execute("pragma table_info(manifests)").fetchall()}
            if "created_at" not in columns:
                db.execute("alter table manifests add column created_at text")
            db.execute("create index if not exists idx_manifests_work_unit_created on manifests(work_unit_id, created_at desc)")
            db.execute("create index if not exists idx_manifests_tenant_logical on manifests(tenant, logical_ref)")
            db.commit()

    def put(self, manifest: Manifest) -> None:
        _enforce_request_tenant(manifest)
        validate_identifier(manifest.manifest_id, label="manifest id", prefix="mf_")
        data = _validate_manifest(manifest)
        with closing(self._connect()) as db:
            db.execute(
                "insert or replace into manifests (manifest_id, work_unit_id, logical_ref, tenant, created_at, payload) values (?, ?, ?, ?, ?, ?)",
                (manifest.manifest_id, manifest.work_unit_id, manifest.logical_ref, manifest.tenant, manifest.created_at, json.dumps(data, sort_keys=True)),
            )
            db.commit()

    def get(self, manifest_id: str) -> Manifest:
        validate_identifier(manifest_id, label="manifest id", prefix="mf_")
        with closing(self._connect()) as db:
            row = db.execute("select payload from manifests where manifest_id = ?", (manifest_id,)).fetchone()
        if row is None:
            raise KeyError(manifest_id)
        manifest = Manifest.from_dict(json.loads(row[0]))
        _enforce_request_tenant(manifest)
        return manifest

    def get_for_tenant(self, manifest_id: str, tenant: str) -> Manifest:
        manifest = self.get(manifest_id)
        _require_manifest_tenant(manifest, tenant)
        return manifest

    def get_by_work_unit(self, work_unit_id: str) -> Manifest:
        tenant = current_tenant()
        with closing(self._connect()) as db:
            if tenant:
                row = db.execute(
                    "select payload from manifests where work_unit_id = ? and tenant = ? order by created_at desc, rowid desc limit 1",
                    (work_unit_id, tenant),
                ).fetchone()
            else:
                row = db.execute("select payload from manifests where work_unit_id = ? order by created_at desc, rowid desc limit 1", (work_unit_id,)).fetchone()
        if row is None:
            raise KeyError(work_unit_id)
        return Manifest.from_dict(json.loads(row[0]))

    def list(self, tenant: str | None = None) -> List[Manifest]:
        tenant = tenant or current_tenant()
        with closing(self._connect()) as db:
            if tenant:
                rows = db.execute("select payload from manifests where tenant = ? order by created_at, rowid", (tenant,)).fetchall()
            else:
                rows = db.execute("select payload from manifests order by created_at, rowid").fetchall()
        return [Manifest.from_dict(json.loads(row[0])) for row in rows]

    def find_by_logical_ref(self, logical_ref: str) -> List[Manifest]:
        tenant = current_tenant()
        with closing(self._connect()) as db:
            if tenant:
                rows = db.execute(
                    "select payload from manifests where logical_ref = ? and tenant = ? order by manifest_id",
                    (logical_ref, tenant),
                ).fetchall()
            else:
                rows = db.execute("select payload from manifests where logical_ref = ? order by manifest_id", (logical_ref,)).fetchall()
        return [Manifest.from_dict(json.loads(row[0])) for row in rows]


def default_manifest_store(state_dir: str | Path, backend: str = "file"):
    state = Path(state_dir)
    configured = os.environ.get("URP_MANIFEST_STORE")
    if configured and backend == "file":
        if configured in {"sqlite", "sqlite3"}:
            backend = "sqlite"
        elif configured.startswith("sqlite:///"):
            return SQLiteManifestStore(configured.removeprefix("sqlite:///"))
        elif configured.startswith(("postgres://", "postgresql://")):
            from .postgres import PostgresManifestStore

            return PostgresManifestStore(configured)
    if backend == "sqlite":
        return SQLiteManifestStore(state / "manifests.sqlite3")
    return FileManifestStore(state / "manifests")


def _validate_manifest(manifest: Manifest) -> Dict[str, object]:
    data = manifest.to_dict()
    validate_named_schema("manifest", data)
    compute_manifest = manifest.physical.get("compute_manifest")
    if compute_manifest is not None:
        validate_named_schema("compute_manifest", compute_manifest)
    return data


def _require_manifest_tenant(manifest: Manifest, tenant: str) -> None:
    if manifest.tenant != tenant:
        from .errors import tenant_mismatch

        raise tenant_mismatch(tenant, manifest.tenant)


def _enforce_request_tenant(manifest: Manifest) -> None:
    tenant = current_tenant()
    if tenant and manifest.tenant != tenant:
        from .errors import tenant_mismatch

        raise tenant_mismatch(tenant, manifest.tenant)


def redact_manifest(manifest: Manifest) -> Dict[str, object]:
    data = redact_details(manifest.to_dict())
    data["logical_ref"] = "[redacted]"
    physical = data.get("physical")
    if isinstance(physical, dict):
        physical.pop("cache_key", None)
        segments = physical.get("segments")
        if isinstance(segments, list):
            for segment in segments:
                if isinstance(segment, dict):
                    segment.pop("ref", None)
    return data
