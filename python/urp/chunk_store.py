from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

from .chunking import Chunk
from .transforms import ZstdLikePlugin
from .chunking import sha256_bytes
from .storage import atomic_write_bytes, atomic_write_json, file_lock, resolve_under


@dataclass(frozen=True)
class StoredChunk:
    digest: str
    tenant: str
    namespace: str
    ref: str
    transform_stack: List[str]
    codec: str | None
    logical_size: int
    stored_size: int
    dedupe_hit: bool

    def to_dict(self) -> Dict[str, object]:
        return {
            "digest": self.digest,
            "tenant": self.tenant,
            "namespace": self.namespace,
            "ref": self.ref,
            "transform_stack": self.transform_stack,
            "codec": self.codec,
            "logical_size": self.logical_size,
            "stored_size": self.stored_size,
            "dedupe_hit": self.dedupe_hit,
        }


class LocalChunkStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"
        self.lock_path = self.root / ".chunk-store.lock"
        if not self.index_path.exists():
            with file_lock(self.lock_path):
                if not self.index_path.exists():
                    self._write_index({})

    def _domain_dir(self, tenant: str, namespace: str) -> Path:
        domain = hashlib.sha256(f"{tenant}\0{namespace}".encode("utf-8")).hexdigest()[:32]
        path = self.root / f"domain-{domain}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _read_index(self) -> Dict[str, Dict[str, object]]:
        with self.index_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _write_index(self, data: Dict[str, Dict[str, object]]) -> None:
        atomic_write_json(self.index_path, data)

    def put_chunk(self, tenant: str, namespace: str, chunk: Chunk, compress: bool = True) -> StoredChunk:
        with file_lock(self.lock_path):
            domain_dir = self._domain_dir(tenant, namespace)
            path = domain_dir / chunk.sha256
            index = self._read_index()
            key = hashlib.sha256(f"{tenant}\0{namespace}\0{chunk.sha256}".encode("utf-8")).hexdigest()
            if path.exists() and key in index:
                existing = index[key]
                candidate = StoredChunk(
                    digest=str(existing["digest"]),
                    tenant=tenant,
                    namespace=namespace,
                    ref=str(existing["ref"]),
                    transform_stack=list(existing.get("transform_stack") or []),
                    codec=existing.get("codec") if existing.get("codec") else None,
                    logical_size=int(existing["logical_size"]),
                    stored_size=int(existing["stored_size"]),
                    dedupe_hit=True,
                )
                self._verify_stored(candidate.to_dict())
                return candidate
            codec = None
            transform_stack: List[str] = []
            payload = chunk.data
            if compress:
                plugin = ZstdLikePlugin()
                result = plugin.try_compress(chunk.data)
                if result.useful:
                    payload = result.data
                    codec = result.codec
                    transform_stack.append(result.transform)
            atomic_write_bytes(path, payload)
            stored = StoredChunk(
                digest=chunk.sha256,
                tenant=tenant,
                namespace=namespace,
                ref=str(path.relative_to(self.root)),
                transform_stack=transform_stack,
                codec=codec,
                logical_size=len(chunk.data),
                stored_size=len(payload),
                dedupe_hit=False,
            )
            index[key] = stored.to_dict()
            self._write_index(index)
            return stored

    def put_chunks(self, tenant: str, namespace: str, chunks: Iterable[Chunk], compress: bool = True) -> List[StoredChunk]:
        return [self.put_chunk(tenant, namespace, chunk, compress) for chunk in chunks]

    def read_stored(self, stored: Dict[str, object]) -> bytes:
        path = resolve_under(self.root, str(stored["ref"]))
        payload = path.read_bytes()
        stack = list(stored.get("transform_stack") or [])
        if "zstd" in stack:
            codec = str(stored.get("codec") or "")
            if codec not in {"zstd", "zlib"}:
                raise ValueError("compressed chunk manifest is missing a supported codec")
            payload = ZstdLikePlugin(codec=codec).decompress(payload)
        expected = str(stored.get("digest") or stored.get("sha256") or "")
        if expected and sha256_bytes(payload) != expected:
            raise ValueError("chunk checksum verification failed")
        return payload

    def rehydrate(self, segments: Iterable[Dict[str, object]]) -> bytes:
        return b"".join(self.read_stored(segment) for segment in segments)

    def _verify_stored(self, stored: Dict[str, object]) -> None:
        self.read_stored(stored)
