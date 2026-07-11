from __future__ import annotations
import json

def classify_sample(data: bytes, content_type: str = "") -> str:
    head = data[:512].lstrip()
    ct = (content_type or "").lower()
    if "json" in ct:
        return "json"
    if "parquet" in ct or head.startswith(b"PAR1"):
        return "parquet"
    if "image" in ct or head.startswith((b"\xff\xd8", b"\x89PNG", b"GIF")):
        return "image"
    if "video" in ct or b"ftyp" in head[:32]:
        return "video"
    if "text" in ct:
        return "text"
    try:
        text = data[:4096].decode("utf-8")
        stripped = text.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            json.loads(stripped[: max(2, len(stripped))])
            return "json"
        if "," in text and "\n" in text:
            return "csv-or-log"
        return "text"
    except Exception:
        return "bytes"
