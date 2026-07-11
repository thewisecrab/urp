from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .contracts import new_id, utc_now
from .auth import current_tenant
from .storage import append_json_line, ensure_private_file, file_lock


SENSITIVE_KEY_PARTS = (
    "authorization",
    "api_key",
    "api-key",
    "body",
    "content",
    "input",
    "message",
    "messages",
    "payload",
    "prompt",
    "secret",
    "token",
)
SENSITIVE_MESSAGE_MARKERS = (
    "api_key",
    "authorization:",
    "body:",
    "content:",
    "messages:",
    "payload:",
    "prompt:",
    "secret",
    "token:",
)


@dataclass(frozen=True)
class StructuredLogEntry:
    severity: str
    event_type: str
    message: str
    tenant: Optional[str] = None
    work_unit_id: Optional[str] = None
    manifest_id: Optional[str] = None
    policy_bundle_id: Optional[str] = None
    trace_id: Optional[str] = None
    error_code: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    log_id: str = field(default_factory=lambda: new_id("log"))
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "log_id": self.log_id,
            "created_at": self.created_at,
            "severity": self.severity,
            "event_type": self.event_type,
            "tenant": self.tenant,
            "work_unit_id": self.work_unit_id,
            "manifest_id": self.manifest_id,
            "policy_bundle_id": self.policy_bundle_id,
            "trace_id": self.trace_id,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StructuredLogEntry":
        return cls(
            severity=data["severity"],
            event_type=data["event_type"],
            message=data.get("message", ""),
            tenant=data.get("tenant"),
            work_unit_id=data.get("work_unit_id"),
            manifest_id=data.get("manifest_id"),
            policy_bundle_id=data.get("policy_bundle_id"),
            trace_id=data.get("trace_id"),
            error_code=data.get("error_code"),
            details=dict(data.get("details") or {}),
            log_id=data.get("log_id") or new_id("log"),
            created_at=data.get("created_at") or utc_now(),
        )


class JSONLLogStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        ensure_private_file(self.path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    def append(self, entry: StructuredLogEntry) -> StructuredLogEntry:
        tenant = current_tenant()
        if tenant and entry.tenant not in {None, tenant}:
            from .errors import tenant_mismatch

            raise tenant_mismatch(tenant, str(entry.tenant))
        redacted = StructuredLogEntry(
            severity=entry.severity.lower(),
            event_type=entry.event_type,
            message=redact_message(entry.message),
            tenant=entry.tenant,
            work_unit_id=entry.work_unit_id,
            manifest_id=entry.manifest_id,
            policy_bundle_id=entry.policy_bundle_id,
            trace_id=entry.trace_id,
            error_code=entry.error_code,
            details=redact_details(entry.details),
            log_id=entry.log_id,
            created_at=entry.created_at,
        )
        append_json_line(self.path, redacted.to_dict(), lock_path=self.lock_path)
        return redacted

    def read(self) -> List[StructuredLogEntry]:
        rows: List[StructuredLogEntry] = []
        tenant = current_tenant()
        with file_lock(self.lock_path, exclusive=False):
            with self.path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        entry = StructuredLogEntry.from_dict(json.loads(line))
                        if not tenant or entry.tenant == tenant:
                            rows.append(entry)
        return rows

    def query(
        self,
        tenant: Optional[str] = None,
        work_unit_id: Optional[str] = None,
        manifest_id: Optional[str] = None,
        event_types: Optional[Iterable[str]] = None,
        trace_id: Optional[str] = None,
        severity: Optional[str] = None,
        error_code: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[StructuredLogEntry]:
        tenant = tenant or current_tenant()
        wanted = set(event_types or [])
        rows: List[StructuredLogEntry] = []
        for entry in self.read():
            if tenant and entry.tenant != tenant:
                continue
            if work_unit_id and entry.work_unit_id != work_unit_id:
                continue
            if manifest_id and entry.manifest_id != manifest_id:
                continue
            if wanted and entry.event_type not in wanted:
                continue
            if trace_id and entry.trace_id != trace_id:
                continue
            if severity and entry.severity != severity.lower():
                continue
            if error_code and entry.error_code != error_code:
                continue
            rows.append(entry)
        return rows[-limit:] if limit else rows


def default_log_store(state_dir: str | Path) -> JSONLLogStore:
    return JSONLLogStore(Path(state_dir) / "logs.jsonl")


def emit_log(
    state_dir: str | Path,
    event_type: str,
    message: str,
    *,
    severity: str = "info",
    tenant: Optional[str] = None,
    work_unit_id: Optional[str] = None,
    manifest_id: Optional[str] = None,
    policy_bundle_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> StructuredLogEntry:
    return default_log_store(state_dir).append(
        StructuredLogEntry(
            severity=severity,
            event_type=event_type,
            message=message,
            tenant=tenant,
            work_unit_id=work_unit_id,
            manifest_id=manifest_id,
            policy_bundle_id=policy_bundle_id,
            trace_id=trace_id,
            error_code=error_code,
            details=details or {},
        )
    )


def redact_message(message: str) -> str:
    cleaned = " ".join(str(message).split())
    lowered = cleaned.lower()
    if any(marker in lowered for marker in SENSITIVE_MESSAGE_MARKERS):
        return "[redacted]"
    return cleaned[:512]


def redact_details(value: Any) -> Any:
    return _redact_value(value, key_hint=None)


def _redact_value(value: Any, key_hint: Optional[str]) -> Any:
    if key_hint and any(part in key_hint.lower() for part in SENSITIVE_KEY_PARTS):
        return "[redacted]"
    if isinstance(value, dict):
        return {str(k): _redact_value(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(item, key_hint=None) for item in value]
    if isinstance(value, tuple):
        return [_redact_value(item, key_hint=None) for item in value]
    return value
