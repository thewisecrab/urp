from __future__ import annotations
import hashlib
from dataclasses import dataclass

@dataclass(frozen=True)
class Chunk:
    start: int
    end: int
    digest: str
    data: bytes

def fixed_chunks(data: bytes, size: int = 1024 * 1024) -> list[Chunk]:
    chunks: list[Chunk] = []
    for start in range(0, len(data), size):
        part = data[start:start + size]
        chunks.append(Chunk(start, start + len(part), hashlib.sha256(part).hexdigest(), part))
    return chunks

def content_defined_chunks(data: bytes, min_size: int = 2048, avg_size: int = 8192, max_size: int = 65536) -> list[Chunk]:
    if not data:
        return []
    mask = avg_size - 1
    chunks: list[Chunk] = []
    start = 0
    rolling = 0
    for i, b in enumerate(data):
        rolling = ((rolling << 1) + b) & 0xFFFFFFFF
        length = i + 1 - start
        if length >= min_size and ((rolling & mask) == 0 or length >= max_size):
            part = data[start:i + 1]
            chunks.append(Chunk(start, i + 1, hashlib.sha256(part).hexdigest(), part))
            start = i + 1
            rolling = 0
    if start < len(data):
        part = data[start:]
        chunks.append(Chunk(start, len(data), hashlib.sha256(part).hexdigest(), part))
    return chunks
