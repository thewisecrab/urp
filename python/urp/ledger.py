from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, List, Optional

from .contracts import LedgerEvent
from .schema_validation import validate_named_schema
from .storage import ensure_private_file, file_lock
from .auth import current_tenant


class JSONLLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        ensure_private_file(self.path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    def append(self, event: LedgerEvent) -> LedgerEvent:
        tenant = current_tenant()
        if tenant and event.tenant != tenant:
            from .errors import tenant_mismatch

            raise tenant_mismatch(tenant, event.tenant)
        with file_lock(self.lock_path):
            previous = self._last_event_unlocked()
            chained = event.with_chain_hash(previous.event_hash if previous else None)
            data = chained.to_dict()
            validate_named_schema("ledger_event", data)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(data, sort_keys=True) + "\n")
                fh.flush()
                import os

                os.fsync(fh.fileno())
        return chained

    def read(self) -> List[LedgerEvent]:
        with file_lock(self.lock_path, exclusive=False):
            rows = self._read_unlocked()
        tenant = current_tenant()
        return [event for event in rows if event.tenant == tenant] if tenant else rows

    def _read_unlocked(self) -> List[LedgerEvent]:
        events: List[LedgerEvent] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    events.append(LedgerEvent.from_dict(json.loads(line)))
        return events

    def _last_event_unlocked(self) -> LedgerEvent | None:
        with self.path.open("rb") as stream:
            stream.seek(0, 2)
            position = stream.tell()
            buffer = b""
            while position > 0:
                size = min(8192, position)
                position -= size
                stream.seek(position)
                buffer = stream.read(size) + buffer
                stripped = buffer.rstrip(b"\r\n")
                if position == 0 or b"\n" in stripped:
                    if not stripped:
                        return None
                    line = stripped.rsplit(b"\n", 1)[-1]
                    return LedgerEvent.from_dict(json.loads(line))
        return None

    def query(
        self,
        tenant: Optional[str] = None,
        work_unit_id: Optional[str] = None,
        manifest_id: Optional[str] = None,
        event_types: Optional[Iterable[str]] = None,
        limit: Optional[int] = None,
    ) -> List[LedgerEvent]:
        tenant = tenant or current_tenant()
        wanted = set(event_types or [])
        rows = []
        for event in self.read():
            if tenant and event.tenant != tenant:
                continue
            if work_unit_id and event.work_unit_id != work_unit_id:
                continue
            if manifest_id and event.manifest_id != manifest_id:
                continue
            if wanted and event.event_type not in wanted:
                continue
            rows.append(event)
        return rows[-limit:] if limit else rows

    def last_hash(self) -> Optional[str]:
        with file_lock(self.lock_path, exclusive=False):
            event = self._last_event_unlocked()
        return event.event_hash if event else None

    def verify_chain(self) -> bool:
        prev = None
        with file_lock(self.lock_path, exclusive=False):
            events = self._read_unlocked()
        for event in events:
            if event.prev_hash != prev:
                return False
            recalculated = event.with_chain_hash(event.prev_hash)
            if event.event_hash != recalculated.event_hash:
                return False
            prev = event.event_hash
        return True


def default_ledger(state_dir: str | Path) -> JSONLLedger:
    configured = os.environ.get("URP_LEDGER_STORE")
    if configured and configured.startswith(("postgres://", "postgresql://")):
        from .postgres import PostgresLedger

        return PostgresLedger(configured)  # type: ignore[return-value]
    return JSONLLedger(Path(state_dir) / "ledger.jsonl")
