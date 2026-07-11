from __future__ import annotations

import base64
from typing import Any, Dict

from .contracts import WorkUnit


ENCODING_KEY = "_urp_encoding"


def encode_json_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return {ENCODING_KEY: "base64", "data": base64.b64encode(value).decode("ascii")}
    if isinstance(value, dict):
        return {str(key): encode_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [encode_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [encode_json_value(item) for item in value]
    return value


def decode_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value) == {ENCODING_KEY, "data"} and value.get(ENCODING_KEY) == "base64":
            try:
                return base64.b64decode(str(value["data"]), validate=True)
            except Exception as exc:
                raise ValueError("invalid URP base64 payload envelope") from exc
        return {str(key): decode_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [decode_json_value(item) for item in value]
    return value


def json_safe_work_unit(work_unit: WorkUnit) -> Dict[str, Any]:
    data = work_unit.to_dict()
    data["payload"] = encode_json_value(data.get("payload"))
    return data


def work_unit_from_json_safe(data: Dict[str, Any]) -> WorkUnit:
    row = dict(data)
    row["payload"] = decode_json_value(row.get("payload"))
    return WorkUnit.from_dict(row)
