from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class URPError(Exception):
    code: str
    message: str
    work_unit_id: str | None = None
    policy_bundle_id: str | None = None
    retryable: bool = False
    details: Dict[str, Any] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "work_unit_id": self.work_unit_id,
                "policy_bundle_id": self.policy_bundle_id,
                "retryable": self.retryable,
                "details": self.details or {},
            }
        }


def invalid_work_unit(message: str, details: Dict[str, Any] | None = None) -> URPError:
    return URPError("invalid_work_unit", message, details=details)


def policy_denied(message: str, work_unit_id: str | None = None, policy_bundle_id: str | None = None) -> URPError:
    return URPError("policy_denied", message, work_unit_id=work_unit_id, policy_bundle_id=policy_bundle_id)


def authentication_required(message: str = "authentication is required") -> URPError:
    return URPError("authentication_required", message, retryable=False)


def tenant_mismatch(expected: str, actual: str) -> URPError:
    return URPError(
        "tenant_mismatch",
        "the authenticated principal cannot access the requested tenant",
        retryable=False,
        details={"principal_tenant": expected, "requested_tenant": actual},
    )


def verifier_failed(message: str, work_unit_id: str | None = None, details: Dict[str, Any] | None = None) -> URPError:
    return URPError("verifier_failed", message, work_unit_id=work_unit_id, details=details)


def manifest_not_found(manifest_id: str) -> URPError:
    return URPError("manifest_not_found", f"manifest not found: {manifest_id}", details={"manifest_id": manifest_id})


def work_unit_not_found(work_unit_id: str) -> URPError:
    return URPError("work_unit_not_found", f"work unit not found: {work_unit_id}", work_unit_id=work_unit_id)


def rehydration_failed(message: str, work_unit_id: str | None = None, details: Dict[str, Any] | None = None) -> URPError:
    return URPError("rehydration_failed", message, work_unit_id=work_unit_id, details=details)
