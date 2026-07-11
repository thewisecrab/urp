from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Optional

from .contracts import new_id, utc_now
from .auth import current_tenant
from .storage import append_json_line, ensure_private_file, file_lock


@dataclass(frozen=True)
class TraceSpan:
    name: str
    trace_id: str
    span_id: str = field(default_factory=lambda: new_id("sp"))
    parent_span_id: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    started_at: str = field(default_factory=utc_now)
    ended_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "attributes": self.attributes,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }


class JSONLTraceStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        ensure_private_file(self.path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    def append(self, span: TraceSpan) -> TraceSpan:
        tenant = current_tenant()
        span_tenant = span.attributes.get("tenant")
        if tenant and span_tenant not in {None, tenant}:
            from .errors import tenant_mismatch

            raise tenant_mismatch(tenant, str(span_tenant))
        if tenant and span_tenant is None:
            span = replace(span, attributes={**span.attributes, "tenant": tenant})
        append_json_line(self.path, span.to_dict(), lock_path=self.lock_path)
        return span

    def query(self, trace_id: str | None = None, name: str | None = None) -> List[TraceSpan]:
        rows: List[TraceSpan] = []
        tenant = current_tenant()
        with file_lock(self.lock_path, exclusive=False):
            with self.path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if trace_id and data.get("trace_id") != trace_id:
                        continue
                    if name and data.get("name") != name:
                        continue
                    if tenant and data.get("attributes", {}).get("tenant") != tenant:
                        continue
                    rows.append(TraceSpan(**data))
        return rows


def default_trace_store(state_dir: str | Path) -> JSONLTraceStore:
    return JSONLTraceStore(Path(state_dir) / "traces.jsonl")


def emit_span(state_dir: str | Path, name: str, trace_id: str, **attributes: Any) -> TraceSpan:
    return default_trace_store(state_dir).append(TraceSpan(name=name, trace_id=trace_id, attributes=attributes))
