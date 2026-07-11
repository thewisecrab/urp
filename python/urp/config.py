from __future__ import annotations

import os

from .errors import policy_denied


VALID_MODES = {"observe", "shadow", "enforce"}


def execution_mode(requested: str | None = None) -> str:
    mode = str(requested or os.environ.get("URP_MODE", "enforce")).strip().lower()
    if mode not in VALID_MODES:
        raise ValueError("mode must be observe, shadow, or enforce")
    return mode


def require_execution_enabled(work_unit_id: str | None = None) -> None:
    if os.environ.get("URP_EXECUTION_DISABLED", "").strip().lower() in {"1", "true", "yes", "on"}:
        raise policy_denied("execution is disabled for this control-plane deployment", work_unit_id)
