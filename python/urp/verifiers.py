from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class VerificationResult:
    accepted: bool
    verifier_id: str
    reason: str
    details: Dict[str, Any] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accepted": self.accepted,
            "verifier_id": self.verifier_id,
            "reason": self.reason,
            "details": self.details or {},
        }


def verify_sha256(data: bytes, expected_hex: str) -> VerificationResult:
    got = hashlib.sha256(data).hexdigest()
    return VerificationResult(got == expected_hex, "sha256_restore@0", "match" if got == expected_hex else "mismatch", {"expected": expected_hex, "actual": got})


def verify_non_empty_text(text: str) -> VerificationResult:
    return VerificationResult(bool(text.strip()), "non_empty_text@0", "non_empty" if text.strip() else "empty")


def verify_embedding_vector(value: Any) -> VerificationResult:
    vectors = value if isinstance(value, list) else []
    accepted = bool(vectors) and all(
        isinstance(vector, list)
        and bool(vector)
        and all(isinstance(item, (int, float)) for item in vector)
        for vector in vectors
    )
    return VerificationResult(
        accepted,
        "embedding_shape@0",
        "vector_shape_ok" if accepted else "invalid_embedding_shape",
        {"vectors": len(vectors)},
    )


def verify_source_fingerprints(expected: set[str], actual: set[str]) -> VerificationResult:
    accepted = expected == actual
    return VerificationResult(accepted, "source_fingerprint_match@0", "match" if accepted else "mismatch", {"expected": sorted(expected), "actual": sorted(actual)})


def verify_json_shape(value: Any, required_keys: set[str]) -> VerificationResult:
    keys = set(value) if isinstance(value, dict) else set()
    missing = required_keys - keys
    return VerificationResult(not missing, "json_shape@0", "shape_ok" if not missing else "missing_keys", {"missing": sorted(missing)})
