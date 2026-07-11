from __future__ import annotations
import math
from collections import Counter

def shannon_entropy_bits_per_byte(data: bytes) -> float:
    if not data:
        return 0.0
    n = len(data)
    counts = Counter(data)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())

def likely_incompressible(data: bytes, threshold: float = 7.7) -> bool:
    return shannon_entropy_bits_per_byte(data[: min(len(data), 65536)]) >= threshold
