from __future__ import annotations

import base64
import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .contracts import new_id, utc_now
from .storage import atomic_write_bytes, atomic_write_json, file_lock, validate_identifier


@dataclass(frozen=True)
class LocalKey:
    key_id: str
    material: bytes
    created_at: str
    purpose: str = "local-dev"

    def to_dict(self) -> Dict[str, str]:
        return {"key_id": self.key_id, "created_at": self.created_at, "purpose": self.purpose, "algorithm": "AES-256-GCM"}


class LocalKMS:
    """Authenticated local envelope encryption for development and tests.

    Data keys are wrapped by a local master key with AES-256-GCM. Key material
    is never returned by the public representation or API.
    """

    def __init__(self, state_dir: str | Path = ".urp") -> None:
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.state_dir / "kms_keys.json"
        self.master_path = self.state_dir / "kms_master.key"
        self.lock_path = self.state_dir / ".kms.lock"
        with file_lock(self.lock_path):
            if not self.path.exists():
                atomic_write_json(self.path, {}, mode=0o600)

    def create_key(self, purpose: str = "local-dev") -> LocalKey:
        key = LocalKey(new_id("key"), secrets.token_bytes(32), utc_now(), purpose)
        with file_lock(self.lock_path):
            master = self._master_key_unlocked()
            nonce = secrets.token_bytes(12)
            wrapped = AESGCM(master).encrypt(nonce, key.material, key.key_id.encode("utf-8"))
            keys = self._read_unlocked()
            keys[key.key_id] = {
                **key.to_dict(),
                "wrap_algorithm": "AES-256-GCM",
                "wrap_nonce": base64.b64encode(nonce).decode("ascii"),
                "wrapped_material": base64.b64encode(wrapped).decode("ascii"),
            }
            self._write(keys)
        return key

    def get_key(self, key_id: str) -> LocalKey:
        validate_identifier(key_id, label="key id", prefix="key_")
        with file_lock(self.lock_path, exclusive=False):
            data = self._read_unlocked()[key_id]
            if "wrapped_material" in data:
                nonce = base64.b64decode(data["wrap_nonce"], validate=True)
                wrapped = base64.b64decode(data["wrapped_material"], validate=True)
                material = AESGCM(self._master_key_unlocked()).decrypt(nonce, wrapped, key_id.encode("utf-8"))
            else:  # Backward-compatible migration for earlier local state.
                material = base64.b64decode(data["material"], validate=True)
        return LocalKey(data["key_id"], material, data["created_at"], data.get("purpose", "local-dev"))

    def encrypt(self, key_id: str, plaintext: bytes, aad: bytes = b"") -> Dict[str, str]:
        key = self.get_key(key_id)
        nonce = secrets.token_bytes(12)
        ciphertext = AESGCM(key.material).encrypt(nonce, plaintext, aad)
        return {
            "key_id": key_id,
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
            "algorithm": "AES-256-GCM",
        }

    def decrypt(self, envelope: Dict[str, str], aad: bytes = b"") -> bytes:
        if envelope.get("algorithm") != "AES-256-GCM":
            raise ValueError("unsupported or unauthenticated encryption envelope")
        key = self.get_key(envelope["key_id"])
        nonce = base64.b64decode(envelope["nonce"], validate=True)
        ciphertext = base64.b64decode(envelope["ciphertext"], validate=True)
        if len(nonce) != 12:
            raise ValueError("AES-GCM nonce must be 12 bytes")
        return AESGCM(key.material).decrypt(nonce, ciphertext, aad)

    def _master_key_unlocked(self) -> bytes:
        configured = os.environ.get("URP_LOCAL_KMS_MASTER_KEY")
        if configured:
            material = base64.b64decode(configured, validate=True)
            if len(material) != 32:
                raise ValueError("URP_LOCAL_KMS_MASTER_KEY must decode to 32 bytes")
            return material
        if not self.master_path.exists():
            atomic_write_bytes(self.master_path, base64.b64encode(secrets.token_bytes(32)) + b"\n", mode=0o600)
        material = base64.b64decode(self.master_path.read_bytes().strip(), validate=True)
        if len(material) != 32:
            raise ValueError("local KMS master key is invalid")
        return material

    def _read_unlocked(self) -> Dict[str, Dict[str, str]]:
        with self.path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _write(self, data: Dict[str, Dict[str, str]]) -> None:
        atomic_write_json(self.path, data, mode=0o600)
