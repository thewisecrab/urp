from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Dict, List

from .contracts import WorkUnit
from .schema_validation import validate_named_schema
from .storage import atomic_write_json, file_lock, validate_identifier
from .auth import current_tenant
from .encoding import json_safe_work_unit, work_unit_from_json_safe


class InMemoryWorkUnitStore:
    def __init__(self) -> None:
        self._rows: Dict[str, WorkUnit] = {}
        self._lock = threading.RLock()

    def put(self, work_unit: WorkUnit) -> WorkUnit:
        _enforce_tenant(work_unit)
        validate_named_schema("work_unit", json_safe_work_unit(work_unit))
        with self._lock:
            self._rows[work_unit.id] = work_unit
        return work_unit

    def get(self, work_unit_id: str) -> WorkUnit:
        with self._lock:
            row = self._rows[work_unit_id]
        _enforce_tenant(row)
        return row

    def list(self, tenant: str | None = None) -> List[WorkUnit]:
        tenant = tenant or current_tenant()
        with self._lock:
            rows = list(self._rows.values())
        return [row for row in rows if row.tenant == tenant] if tenant else rows


class FileWorkUnitStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, work_unit: WorkUnit) -> WorkUnit:
        _enforce_tenant(work_unit)
        data = json_safe_work_unit(work_unit)
        validate_named_schema("work_unit", data)
        with file_lock(self.root / ".work-unit.lock"):
            atomic_write_json(self._path(work_unit.id), data)
        return work_unit

    def get(self, work_unit_id: str) -> WorkUnit:
        with file_lock(self.root / ".work-unit.lock", exclusive=False):
            with self._path(work_unit_id).open("r", encoding="utf-8") as fh:
                row = work_unit_from_json_safe(json.load(fh))
        _enforce_tenant(row)
        return row

    def list(self, tenant: str | None = None) -> List[WorkUnit]:
        tenant = tenant or current_tenant()
        rows: List[WorkUnit] = []
        with file_lock(self.root / ".work-unit.lock", exclusive=False):
            for path in sorted(self.root.glob("wu_*.json")):
                with path.open("r", encoding="utf-8") as fh:
                    row = work_unit_from_json_safe(json.load(fh))
                if tenant is None or row.tenant == tenant:
                    rows.append(row)
        return rows

    def _path(self, work_unit_id: str) -> Path:
        validate_identifier(work_unit_id, label="work unit id", prefix="wu_")
        return self.root / f"{work_unit_id}.json"


def default_work_unit_store(state_dir: str | Path = ".urp") -> FileWorkUnitStore:
    return FileWorkUnitStore(Path(state_dir) / "work_units")


def _enforce_tenant(work_unit: WorkUnit) -> None:
    tenant = current_tenant()
    if tenant and work_unit.tenant != tenant:
        from .errors import tenant_mismatch

        raise tenant_mismatch(tenant, work_unit.tenant)
