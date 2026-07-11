from __future__ import annotations

from math import log2
from collections import Counter


def byte_entropy(data: bytes) -> float:
    """Return Shannon entropy in bits per byte for a byte string."""
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    return -sum((count / total) * log2(count / total) for count in counts.values())


def looks_random_or_encrypted(data: bytes, threshold: float = 7.85) -> bool:
    """Heuristic only. High entropy suggests little lossless compression opportunity."""
    if len(data) < 256:
        return False
    return byte_entropy(data[: min(len(data), 65536)]) >= threshold
