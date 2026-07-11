from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List

from .contracts import LedgerEvent, Plan, WorkUnit
from .ledger import default_ledger
from .storage import atomic_write_json, file_lock, validate_identifier
from .auth import current_tenant


class InMemoryPlanStore:
    def __init__(self) -> None:
        self._rows: Dict[str, Plan] = {}
        self._lock = threading.RLock()

    def put(self, plan: Plan) -> Plan:
        _enforce_plan_tenant(plan)
        with self._lock:
            self._rows[plan.plan_id] = plan
        return plan

    def get(self, plan_id: str) -> Plan:
        with self._lock:
            plan = self._rows[plan_id]
        _enforce_plan_tenant(plan)
        return plan

    def list(self, work_unit_id: str | None = None) -> List[Plan]:
        with self._lock:
            rows = list(self._rows.values())
        tenant = current_tenant()
        rows = [row for row in rows if not tenant or row.tenant == tenant]
        return [row for row in rows if row.work_unit_id == work_unit_id] if work_unit_id else rows


class FilePlanStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, plan: Plan) -> Plan:
        _enforce_plan_tenant(plan)
        with file_lock(self.root / ".plan.lock"):
            atomic_write_json(self._path(plan.plan_id), plan.to_dict())
        return plan

    def get(self, plan_id: str) -> Plan:
        with file_lock(self.root / ".plan.lock", exclusive=False):
            with self._path(plan_id).open("r", encoding="utf-8") as fh:
                plan = Plan.from_dict(json.load(fh))
        _enforce_plan_tenant(plan)
        return plan

    def list(self, work_unit_id: str | None = None) -> List[Plan]:
        rows: List[Plan] = []
        tenant = current_tenant()
        with file_lock(self.root / ".plan.lock", exclusive=False):
            for path in sorted(self.root.glob("pl_*.json")):
                with path.open("r", encoding="utf-8") as fh:
                    plan = Plan.from_dict(json.load(fh))
                if tenant and plan.tenant != tenant:
                    continue
                if work_unit_id is None or plan.work_unit_id == work_unit_id:
                    rows.append(plan)
        return rows

    def _path(self, plan_id: str) -> Path:
        validate_identifier(plan_id, label="plan id", prefix="pl_")
        return self.root / f"{plan_id}.json"


def default_plan_store(state_dir: str | Path = ".urp") -> FilePlanStore:
    return FilePlanStore(Path(state_dir) / "plans")


def store_plan_with_audit(
    state_dir: str | Path,
    plan: Plan,
    work_unit: WorkUnit,
    actor: str | None = None,
    details: Dict[str, Any] | None = None,
) -> Plan:
    stored = default_plan_store(state_dir).put(plan)
    event_details = {"plan": plan.to_dict()}
    if details:
        event_details.update(details)
    default_ledger(state_dir).append(
        LedgerEvent(
            "plan.created",
            work_unit.tenant,
            work_unit.id,
            policy_bundle_id=plan.policy_bundle_id,
            actor=actor,
            details=event_details,
            trace_id=plan.trace_id or work_unit.trace_id,
        )
    )
    return stored


def _enforce_plan_tenant(plan: Plan) -> None:
    tenant = current_tenant()
    if tenant and plan.tenant != tenant:
        from .errors import tenant_mismatch

        raise tenant_mismatch(tenant, str(plan.tenant))
