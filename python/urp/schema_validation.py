from __future__ import annotations

import json
import sysconfig
from pathlib import Path
from typing import Any, Dict, Iterable, List

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError


class SchemaValidationError(ValueError):
    pass


SCHEMA_FILES = {
    "work_unit": "urp_work_unit.schema.json",
    "manifest": "urp_manifest.schema.json",
    "policy": "urp_policy.schema.json",
    "ledger_event": "urp_ledger_event.schema.json",
    "compute_manifest": "compute_manifest.schema.json",
}


def default_schema_dir() -> Path:
    checkout = Path(__file__).resolve().parents[2] / "specs"
    if checkout.is_dir():
        return checkout
    installed = Path(sysconfig.get_path("data")) / "share" / "urp" / "specs"
    if installed.is_dir():
        return installed
    raise FileNotFoundError("URP schema directory was not installed; reinstall the package from a complete distribution")


def load_schema(name: str, schema_dir: str | Path | None = None) -> Dict[str, Any]:
    filename = SCHEMA_FILES.get(name, name)
    root = Path(schema_dir) if schema_dir else default_schema_dir()
    with (root / filename).open("r", encoding="utf-8") as stream:
        schema = json.load(stream)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise SchemaValidationError(f"invalid schema {filename}: {exc.message}") from exc
    return schema


def validate_named_schema(name: str, value: Dict[str, Any], schema_dir: str | Path | None = None) -> None:
    validate_schema(value, load_schema(name, schema_dir))


def validate_schema(value: Any, schema: Dict[str, Any], path: str = "$") -> None:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(value), key=lambda error: list(error.absolute_path))
    if not errors:
        return
    first = errors[0]
    location = path + "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in first.absolute_path)
    raise SchemaValidationError(f"{location}: {first.message}") from first


def validate_many(items: Iterable[tuple[str, Dict[str, Any]]], schema_dir: str | Path | None = None) -> List[str]:
    errors: List[str] = []
    for name, value in items:
        try:
            validate_named_schema(name, value, schema_dir)
        except SchemaValidationError as exc:
            errors.append(str(exc))
    return errors
