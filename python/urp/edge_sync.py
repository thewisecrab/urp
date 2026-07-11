from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Protocol
from urllib import request

from .contracts import LedgerEvent
from .ledger import JSONLLedger, default_ledger
from .storage import atomic_write_json, file_lock


@dataclass(frozen=True)
class LedgerSyncBatch:
    site_id: str
    events: List[LedgerEvent]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "site_id": self.site_id,
            "first_prev_hash": self.events[0].prev_hash if self.events else None,
            "last_event_hash": self.events[-1].event_hash if self.events else None,
            "events": [event.to_dict() for event in self.events],
        }


class LedgerSink(Protocol):
    def accept(self, batch: LedgerSyncBatch) -> Dict[str, Any]:
        ...


class DelayedLedgerSync:
    def __init__(self, state_dir: str | Path, site_id: str) -> None:
        if not site_id.strip():
            raise ValueError("site_id is required")
        self.state_dir = Path(state_dir)
        self.site_id = site_id
        self.cursor_path = self.state_dir / "edge_sync_cursor.json"
        self.lock_path = self.state_dir / ".edge-sync.lock"

    def pending(self, limit: int = 500) -> LedgerSyncBatch:
        if limit <= 0 or limit > 10_000:
            raise ValueError("sync limit must be between 1 and 10000")
        ledger = default_ledger(self.state_dir)
        if not ledger.verify_chain():
            raise ValueError("local ledger chain verification failed")
        events = ledger.read()
        cursor = self._cursor()
        if cursor:
            indexes = [index for index, event in enumerate(events) if event.event_id == cursor]
            if not indexes:
                raise ValueError("edge sync cursor does not exist in the local ledger")
            events = events[indexes[-1] + 1 :]
        return LedgerSyncBatch(self.site_id, events[:limit])

    def sync(self, sink: LedgerSink, limit: int = 500) -> Dict[str, Any]:
        with file_lock(self.lock_path):
            batch = self.pending(limit)
            if not batch.events:
                return {"accepted": True, "events": 0, "cursor": self._cursor()}
            receipt = sink.accept(batch)
            if receipt.get("accepted") is not True or receipt.get("last_event_hash") != batch.events[-1].event_hash:
                raise ValueError("ledger sink did not acknowledge the complete verified batch")
            atomic_write_json(
                self.cursor_path,
                {"site_id": self.site_id, "event_id": batch.events[-1].event_id, "event_hash": batch.events[-1].event_hash},
            )
            return {"accepted": True, "events": len(batch.events), "cursor": batch.events[-1].event_id}

    def _cursor(self) -> str | None:
        if not self.cursor_path.exists():
            return None
        data = json.loads(self.cursor_path.read_text(encoding="utf-8"))
        if data.get("site_id") != self.site_id:
            raise ValueError("edge sync cursor belongs to another site")
        return str(data["event_id"])


class LocalLedgerSink:
    """Conformance sink that verifies a site chain and writes an isolated ledger."""

    def __init__(self, path: str | Path) -> None:
        self.ledger = JSONLLedger(path)

    def accept(self, batch: LedgerSyncBatch) -> Dict[str, Any]:
        previous = batch.events[0].prev_hash if batch.events else None
        for event in batch.events:
            if event.prev_hash != previous or event.with_chain_hash(event.prev_hash).event_hash != event.event_hash:
                raise ValueError("edge ledger batch chain verification failed")
            self.ledger.append(
                LedgerEvent(
                    event_type=f"edge.sync.{event.event_type}",
                    tenant=event.tenant,
                    work_unit_id=event.work_unit_id,
                    manifest_id=event.manifest_id,
                    policy_bundle_id=event.policy_bundle_id,
                    actor=f"edge:{batch.site_id}",
                    decision=event.decision,
                    details={"source_event_id": event.event_id, "source_event_hash": event.event_hash, "source_details": event.details},
                    trace_id=event.trace_id,
                )
            )
            previous = event.event_hash
        return {"accepted": True, "events": len(batch.events), "last_event_hash": batch.events[-1].event_hash if batch.events else None}


class HTTPLedgerSink:
    def __init__(self, endpoint: str, api_key: str, timeout_seconds: float = 30.0) -> None:
        if not endpoint.startswith("https://"):
            raise ValueError("edge ledger sync endpoint must use HTTPS")
        self.endpoint = endpoint
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def accept(self, batch: LedgerSyncBatch) -> Dict[str, Any]:
        payload = json.dumps(batch.to_dict(), sort_keys=True).encode("utf-8")
        req = request.Request(
            self.endpoint,
            data=payload,
            method="POST",
            headers={"authorization": f"Bearer {self.api_key}", "content-type": "application/json"},
        )
        with request.urlopen(req, timeout=self.timeout_seconds) as response:  # noqa: S310 - explicit HTTPS endpoint
            return json.loads(response.read())
