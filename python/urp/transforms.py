from __future__ import annotations

import zlib
from dataclasses import dataclass
from typing import Protocol


class CompressionPlugin(Protocol):
    name: str

    def compress(self, data: bytes) -> bytes:
        ...

    def decompress(self, data: bytes) -> bytes:
        ...


@dataclass(frozen=True)
class CompressionResult:
    transform: str
    codec: str
    original_size: int
    stored_size: int
    data: bytes

    @property
    def useful(self) -> bool:
        return self.stored_size < self.original_size


class ZstdLikePlugin:
    """A zstd-compatible interface with a stdlib fallback.

    If python-zstandard is unavailable, local-ideal mode uses zlib while keeping
    the transform interface stable. The manifest records the actual codec.
    """

    name = "zstd"

    def __init__(self, level: int = 3, codec: str | None = None) -> None:
        self.level = level
        if codec not in {None, "zstd", "zlib"}:
            raise ValueError(f"unsupported compression codec: {codec}")
        self.requested_codec = codec
        try:
            import zstandard as zstd  # type: ignore
        except Exception:
            self._zstd = None
        else:
            self._zstd = zstd
        if codec == "zstd" and self._zstd is None:
            raise RuntimeError("zstd-compressed data requires the optional zstandard dependency")

    @property
    def codec(self) -> str:
        if self.requested_codec:
            return self.requested_codec
        return "zstd" if self._zstd else "zlib"

    def compress(self, data: bytes) -> bytes:
        if self.codec == "zstd":
            return self._zstd.ZstdCompressor(level=self.level).compress(data)
        return zlib.compress(data, self.level)

    def decompress(self, data: bytes) -> bytes:
        if self.codec == "zstd":
            return self._zstd.ZstdDecompressor().decompress(data)
        return zlib.decompress(data)

    def try_compress(self, data: bytes) -> CompressionResult:
        encoded = self.compress(data)
        return CompressionResult(self.name, self.codec, len(data), len(encoded), encoded)
