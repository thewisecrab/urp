from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .contracts import Contract, WorkUnitKind
from .manifest_store import default_manifest_store


def manifest_explorer_report(
    state_dir: str | Path = ".urp",
    *,
    tenant: Optional[str] = None,
    kind: Optional[str] = None,
    contract: Optional[str] = None,
    state: Optional[str] = None,
    limit: Optional[int] = None,
    redacted: bool = True,
) -> Dict[str, Any]:
    manifests = default_manifest_store(state_dir).list()
    if tenant:
        manifests = [manifest for manifest in manifests if manifest.tenant == tenant]
    if kind:
        selected_kind = WorkUnitKind(kind)
        manifests = [manifest for manifest in manifests if manifest.kind == selected_kind]
    if contract:
        selected_contract = Contract(contract)
        manifests = [manifest for manifest in manifests if manifest.contract == selected_contract]
    if state:
        manifests = [manifest for manifest in manifests if manifest.state == state]

    manifests = sorted(manifests, key=lambda manifest: manifest.created_at)
    selected = manifests[-limit:] if limit else manifests
    rows = [_manifest_row(manifest, redacted) for manifest in selected]
    return {
        "manifest_count": len(manifests),
        "returned": len(rows),
        "filters": {
            "tenant": tenant,
            "kind": kind,
            "contract": contract,
            "state": state,
            "limit": limit,
            "redacted": redacted,
        },
        "by_kind": _count(rows, "kind"),
        "by_contract": _count(rows, "contract"),
        "by_state": _count(rows, "state"),
        "totals": {
            "logical_bytes": sum(int(row.get("logical_size") or 0) for row in rows),
            "stored_bytes": sum(int(row.get("stored_size") or 0) for row in rows),
            "bytes_avoided": sum(int(row.get("bytes_avoided") or 0) for row in rows),
            "dedupe_hits": sum(int(row.get("dedupe_hits") or 0) for row in rows),
        },
        "rows": rows,
    }


def _manifest_row(manifest, redacted: bool) -> Dict[str, Any]:
    physical = manifest.physical or {}
    telemetry = manifest.telemetry or {}
    verification = manifest.verification or {}
    logical_size = _first_int(physical, telemetry, "logical_size", "bytes_in")
    stored_size = _first_int(physical, telemetry, "stored_size", "bytes_stored")
    bytes_avoided = _first_int(telemetry, physical, "bytes_avoided")
    return {
        "manifest_id": manifest.manifest_id,
        "work_unit_id": manifest.work_unit_id,
        "tenant": manifest.tenant,
        "namespace": manifest.namespace,
        "kind": manifest.kind.value,
        "contract": manifest.contract.value,
        "state": manifest.state,
        "logical_ref": "[redacted]" if redacted else manifest.logical_ref,
        "trace_id": manifest.trace_id,
        "created_at": manifest.created_at,
        "logical_size": logical_size,
        "stored_size": stored_size,
        "bytes_avoided": bytes_avoided,
        "dedupe_hits": int(telemetry.get("dedupe_hits", 0) or 0),
        "cache_result": physical.get("cache_result"),
        "verifier_accepted": bool(verification.get("accepted", False)),
    }


def _first_int(primary: Dict[str, Any], secondary: Dict[str, Any], *keys: str) -> int:
    for key in keys:
        if key in primary:
            return int(primary.get(key) or 0)
        if key in secondary:
            return int(secondary.get(key) or 0)
    return 0


def _count(rows: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts
