from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class VerificationResult:
    accepted: bool
    verifier_id: str
    reason: str


def verify_sha256(data: bytes, expected_hex: str) -> VerificationResult:
    got = hashlib.sha256(data).hexdigest()
    return VerificationResult(got == expected_hex, "sha256_restore@0", "match" if got == expected_hex else "mismatch")


def verify_non_empty_text(text: str) -> VerificationResult:
    return VerificationResult(bool(text.strip()), "non_empty_text@0", "non_empty" if text.strip() else "empty")
