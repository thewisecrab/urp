from __future__ import annotations

import re
from typing import Any
from .contracts import Classification, WorkUnit, WorkUnitKind
from .entropy import byte_entropy, looks_random_or_encrypted


COMPRESSED_MAGIC = [
    b"\x1f\x8b",        # gzip
    b"\x28\xb5\x2f\xfd", # zstd
    b"PK\x03\x04",      # zip/jar/docx
    b"\x89PNG",          # png
    b"\xff\xd8\xff",    # jpeg
]


def _payload_bytes(payload: Any) -> bytes:
    if payload is None:
        return b""
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8", errors="replace")
    return repr(payload).encode("utf-8", errors="replace")


def classify(work_unit: WorkUnit) -> Classification:
    data = _payload_bytes(work_unit.payload)
    notes = []
    entropy = byte_entropy(data[: min(len(data), 65536)]) if data else None
    likely_compressed = any(data.startswith(m) for m in COMPRESSED_MAGIC)
    likely_encrypted = looks_random_or_encrypted(data) and not likely_compressed
    schema_hint = None
    ai_task_hint = None

    if work_unit.kind == WorkUnitKind.PROMPT_REQUEST:
        text = data.decode("utf-8", errors="ignore")
        if re.search(r"\bsummarize|summary\b", text, re.I):
            ai_task_hint = "summarization"
        elif re.search(r"\bclassify|label\b", text, re.I):
            ai_task_hint = "classification"
        elif re.search(r"\bsql|query|database\b", text, re.I):
            ai_task_hint = "tool_or_sql"
        else:
            ai_task_hint = "general"
        notes.append("prompt_request_classified_for_routing")

    if data.lstrip().startswith((b"{", b"[")):
        schema_hint = "json"
    elif b"," in data[:1024] and b"\n" in data[:4096]:
        schema_hint = "delimited_text"

    if likely_compressed:
        notes.append("payload_has_compressed_magic")
    if likely_encrypted:
        notes.append("payload_high_entropy")

    return Classification(
        detected_kind=work_unit.kind,
        entropy_bits_per_byte=entropy,
        likely_compressed=likely_compressed,
        likely_encrypted=likely_encrypted,
        schema_hint=schema_hint,
        ai_task_hint=ai_task_hint,
        confidence=0.7 if data else 0.4,
        notes=notes,
    )
