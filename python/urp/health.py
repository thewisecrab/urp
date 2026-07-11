from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict

from .ledger import default_ledger
from .manifest_store import default_manifest_store


def dependency_readiness(state_dir: str | Path = ".urp") -> Dict[str, Any]:
    state = Path(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    checks: Dict[str, bool] = {}
    errors: Dict[str, str] = {}
    try:
        fd, path = tempfile.mkstemp(prefix=".ready-", dir=state)
        os.write(fd, b"ready")
        os.fsync(fd)
        os.close(fd)
        Path(path).unlink()
        checks["state_writable"] = True
    except Exception as exc:  # pragma: no cover - environment dependent
        checks["state_writable"] = False
        errors["state_writable"] = str(exc)
    try:
        default_manifest_store(state).list()
        checks["manifest_store_available"] = True
    except Exception as exc:
        checks["manifest_store_available"] = False
        errors["manifest_store_available"] = str(exc)
    try:
        default_ledger(state).last_hash()
        checks["ledger_store_available"] = True
    except Exception as exc:
        checks["ledger_store_available"] = False
        errors["ledger_store_available"] = str(exc)
    return {"ok": all(checks.values()), "checks": checks, "errors": errors}
