from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import List


@dataclass(frozen=True)
class Chunk:
    offset: int
    data: bytes
    sha256: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_defined_chunks(
    data: bytes,
    min_size: int = 2048,
    avg_bits: int = 12,
    max_size: int = 8192,
) -> List[Chunk]:
    """Small deterministic content-defined chunker for reference tests.

    This is not a production chunker. Production should use a vetted Rabin or
    buzhash implementation with careful performance and security review.
    """
    if not data:
        return []
    if min_size <= 0 or max_size < min_size:
        raise ValueError("invalid chunk sizes")
    mask = (1 << avg_bits) - 1
    chunks: List[Chunk] = []
    start = 0
    rolling = 0
    for i, b in enumerate(data):
        rolling = ((rolling << 1) + b + 0x9E3779B1) & 0xFFFFFFFF
        size = i - start + 1
        should_cut = size >= min_size and ((rolling & mask) == 0 or size >= max_size)
        if should_cut:
            part = data[start : i + 1]
            chunks.append(Chunk(start, part, sha256_bytes(part)))
            start = i + 1
            rolling = 0
    if start < len(data):
        part = data[start:]
        chunks.append(Chunk(start, part, sha256_bytes(part)))
    return chunks
