from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from .contracts import Contract, WorkUnit, new_id, stable_json_hash
from .storage import atomic_write_bytes, atomic_write_json, file_lock, validate_identifier
from .auth import current_tenant


@dataclass(frozen=True)
class ApprovalRecord:
    approval_id: str
    tenant: str
    actor: str
    contract: str
    policy_bundle_id: str
    created_at: str
    expires_at: str
    work_unit_id: str | None = None
    reason: str = ""
    signature: str = ""

    def payload(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("signature", None)
        return data

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ApprovalStore:
    def __init__(self, state_dir: str | Path = ".urp") -> None:
        self.state_dir = Path(state_dir)
        self.root = self.state_dir / "approvals"
        self.root.mkdir(parents=True, exist_ok=True)
        self.key_path = self.state_dir / "approval_signing.key"
        self.lock_path = self.root / ".approval.lock"
        self.key_lock_path = self.state_dir / ".approval-key.lock"

    def issue(
        self,
        *,
        tenant: str,
        actor: str,
        contract: Contract | str,
        policy_bundle_id: str,
        reason: str,
        work_unit_id: str | None = None,
        ttl_seconds: int = 900,
    ) -> ApprovalRecord:
        if ttl_seconds <= 0 or ttl_seconds > 86400:
            raise ValueError("approval ttl_seconds must be between 1 and 86400")
        if not tenant.strip() or not actor.strip() or not reason.strip():
            raise ValueError("approval tenant, actor, and reason are required")
        if len(reason) > 2048:
            raise ValueError("approval reason must be at most 2048 characters")
        validate_identifier(policy_bundle_id, label="policy bundle id")
        if work_unit_id:
            validate_identifier(work_unit_id, label="work unit id", prefix="wu_")
        principal_tenant = current_tenant()
        if principal_tenant and principal_tenant != tenant:
            from .errors import tenant_mismatch

            raise tenant_mismatch(principal_tenant, tenant)
        created = datetime.now(timezone.utc)
        unsigned = ApprovalRecord(
            approval_id=new_id("appr"),
            tenant=tenant,
            actor=actor,
            contract=Contract(contract).value,
            policy_bundle_id=policy_bundle_id,
            created_at=created.isoformat(),
            expires_at=(created + timedelta(seconds=ttl_seconds)).isoformat(),
            work_unit_id=work_unit_id,
            reason=reason,
        )
        record = ApprovalRecord(**unsigned.payload(), signature=self._sign(unsigned.payload()))
        with file_lock(self.lock_path):
            atomic_write_json(self._path(record.approval_id), record.to_dict(), mode=0o600)
        return record

    def get(self, approval_id: str) -> ApprovalRecord:
        with file_lock(self.lock_path, exclusive=False):
            data = json.loads(self._path(approval_id).read_text(encoding="utf-8"))
        record = ApprovalRecord(**data)
        if not hmac.compare_digest(record.signature, self._sign(record.payload())):
            raise ValueError("approval signature verification failed")
        return record

    def list(self, tenant: str | None = None) -> List[ApprovalRecord]:
        tenant = tenant or current_tenant()
        rows = []
        with file_lock(self.lock_path, exclusive=False):
            for path in sorted(self.root.glob("appr_*.json")):
                record = ApprovalRecord(**json.loads(path.read_text(encoding="utf-8")))
                if not hmac.compare_digest(record.signature, self._sign(record.payload())):
                    raise ValueError(f"approval signature verification failed: {record.approval_id}")
                if tenant is None or record.tenant == tenant:
                    rows.append(record)
        return rows

    def verify(self, approval_id: str, work_unit: WorkUnit, contract: Contract, policy_bundle_id: str) -> ApprovalRecord:
        record = self.get(approval_id)
        now = datetime.now(timezone.utc)
        if datetime.fromisoformat(record.expires_at) <= now:
            raise ValueError("approval has expired")
        if record.tenant != work_unit.tenant:
            raise ValueError("approval tenant does not match work unit")
        if record.work_unit_id and record.work_unit_id != work_unit.id:
            raise ValueError("approval is bound to another work unit")
        if record.contract != contract.value:
            raise ValueError("approval contract does not match policy decision")
        if record.policy_bundle_id != policy_bundle_id:
            raise ValueError("approval policy bundle does not match policy decision")
        return record

    def _path(self, approval_id: str) -> Path:
        validate_identifier(approval_id, label="approval id", prefix="appr_")
        return self.root / f"{approval_id}.json"

    def _key(self) -> bytes:
        configured = os.environ.get("URP_APPROVAL_SIGNING_KEY")
        if configured:
            key = base64.b64decode(configured, validate=True)
            if len(key) < 32:
                raise ValueError("URP_APPROVAL_SIGNING_KEY must decode to at least 32 bytes")
            return key
        with file_lock(self.key_lock_path):
            if not self.key_path.exists():
                atomic_write_bytes(self.key_path, base64.b64encode(secrets.token_bytes(32)) + b"\n", mode=0o600)
            key = base64.b64decode(self.key_path.read_bytes().strip(), validate=True)
        if len(key) != 32:
            raise ValueError("local approval signing key is invalid")
        return key

    def _sign(self, payload: Dict[str, Any]) -> str:
        digest = stable_json_hash(payload).encode("ascii")
        return hmac.new(self._key(), digest, hashlib.sha256).hexdigest()
