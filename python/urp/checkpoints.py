from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .chunking import fixed_chunks, sha256_bytes
from .contracts import utc_now
from .storage import atomic_write_bytes, atomic_write_json, file_lock, resolve_under, validate_identifier


class CheckpointDeltaStore:
    def __init__(self, state_dir: str | Path = ".urp", block_size: int = 1024 * 1024) -> None:
        self.root = Path(state_dir) / "checkpoints"
        self.root.mkdir(parents=True, exist_ok=True)
        self.block_size = block_size
        if block_size <= 0:
            raise ValueError("block_size must be positive")
        self.lock_path = self.root / ".checkpoint.lock"

    def put_base(self, checkpoint_id: str, data: bytes) -> Dict[str, object]:
        validate_identifier(checkpoint_id, label="checkpoint id")
        path = self.root / f"{checkpoint_id}.base"
        with file_lock(self.lock_path):
            atomic_write_bytes(path, data)
        manifest = {"checkpoint_id": checkpoint_id, "kind": "base", "sha256": sha256_bytes(data), "size": len(data), "created_at": utc_now()}
        self._write_manifest(checkpoint_id, manifest)
        return manifest

    def put_delta(self, base_id: str, checkpoint_id: str, data: bytes) -> Dict[str, object]:
        validate_identifier(base_id, label="base checkpoint id")
        validate_identifier(checkpoint_id, label="checkpoint id")
        base = self.read(base_id)
        base_chunks = fixed_chunks(base, self.block_size)
        target_chunks = fixed_chunks(data, self.block_size)
        changed: List[Dict[str, object]] = []
        for idx, chunk in enumerate(target_chunks):
            if idx >= len(base_chunks) or base_chunks[idx].data != chunk.data:
                ref = f"{checkpoint_id}.block.{idx}"
                with file_lock(self.lock_path):
                    atomic_write_bytes(self.root / ref, chunk.data)
                changed.append({"index": idx, "ref": ref, "size": len(chunk.data), "sha256": chunk.sha256})
        manifest = {
            "checkpoint_id": checkpoint_id,
            "kind": "delta",
            "base_id": base_id,
            "sha256": sha256_bytes(data),
            "size": len(data),
            "block_size": self.block_size,
            "changed_blocks": changed,
            "base_block_count": len(base_chunks),
            "target_block_count": len(target_chunks),
            "created_at": utc_now(),
            "bytes_avoided": max(0, len(data) - sum(int(b["size"]) for b in changed)),
        }
        self._write_manifest(checkpoint_id, manifest)
        return manifest

    def read(self, checkpoint_id: str) -> bytes:
        validate_identifier(checkpoint_id, label="checkpoint id")
        manifest = self.get_manifest(checkpoint_id)
        if manifest["kind"] == "base":
            data = (self.root / f"{checkpoint_id}.base").read_bytes()
            if sha256_bytes(data) != manifest["sha256"]:
                raise ValueError("checkpoint base checksum mismatch")
            return data
        base = self.read(str(manifest["base_id"]))
        blocks = [chunk.data for chunk in fixed_chunks(base, int(manifest["block_size"]))]
        while len(blocks) < int(manifest["target_block_count"]):
            blocks.append(b"")
        for changed in manifest["changed_blocks"]:
            block = resolve_under(self.root, str(changed["ref"])).read_bytes()
            if sha256_bytes(block) != changed["sha256"]:
                raise ValueError("checkpoint delta block checksum mismatch")
            blocks[int(changed["index"])] = block
        data = b"".join(blocks)[: int(manifest["size"])]
        if sha256_bytes(data) != manifest["sha256"]:
            raise ValueError("checkpoint delta reconstruction checksum mismatch")
        return data

    def get_manifest(self, checkpoint_id: str) -> Dict[str, object]:
        validate_identifier(checkpoint_id, label="checkpoint id")
        with file_lock(self.lock_path, exclusive=False):
            with (self.root / f"{checkpoint_id}.json").open("r", encoding="utf-8") as fh:
                return json.load(fh)

    def _write_manifest(self, checkpoint_id: str, manifest: Dict[str, object]) -> None:
        validate_identifier(checkpoint_id, label="checkpoint id")
        with file_lock(self.lock_path):
            atomic_write_json(self.root / f"{checkpoint_id}.json", manifest)
