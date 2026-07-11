from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from .encoding import decode_json_value
from .verifiers import VerificationResult, verify_embedding_vector, verify_json_shape, verify_non_empty_text


def verify_cache_value(value: Any, specification: Dict[str, Any] | None) -> VerificationResult:
    spec = dict(specification or {})
    verifier_type = str(spec.get("type") or "")
    if verifier_type == "non_empty_text":
        return verify_non_empty_text(_text_value(value))
    if verifier_type == "chat_completion":
        try:
            text = value["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return VerificationResult(False, "chat_completion_shape@1", "missing_assistant_content")
        return verify_non_empty_text(str(text))
    if verifier_type == "embedding_shape":
        vectors = value
        if isinstance(value, dict):
            vectors = [row.get("embedding") for row in value.get("data", []) if isinstance(row, dict)]
        return verify_embedding_vector(vectors)
    if verifier_type == "json_shape":
        required = {str(key) for key in spec.get("required_keys", [])}
        if not required:
            return VerificationResult(False, "json_shape@1", "required_keys_missing")
        return verify_json_shape(value, required)
    if verifier_type == "sha256":
        expected = str(spec.get("expected") or "")
        decoded = decode_json_value(value)
        if isinstance(decoded, str):
            decoded = decoded.encode("utf-8")
        if not isinstance(decoded, bytes) or len(expected) != 64:
            return VerificationResult(False, "sha256_cache_value@1", "bytes_and_expected_digest_required")
        actual = hashlib.sha256(decoded).hexdigest()
        return VerificationResult(actual == expected, "sha256_cache_value@1", "match" if actual == expected else "mismatch", {"expected": expected, "actual": actual})
    return VerificationResult(False, "cache_value_verifier@1", "supported_verifier_type_required", {"supported": ["chat_completion", "embedding_shape", "json_shape", "non_empty_text", "sha256"]})


def ensure_json_serializable(value: Any) -> None:
    json.dumps(value, sort_keys=True)


def _text_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        try:
            return str(value["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError):
            return ""
    return ""
