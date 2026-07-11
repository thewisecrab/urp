from __future__ import annotations
import hashlib, time
from dataclasses import dataclass

@dataclass
class CacheEntry:
    key: str
    value: bytes
    tenant: str
    expires_at: float
    source_fingerprint: str

class ExactCache:
    def __init__(self) -> None:
        self._entries: dict[str, CacheEntry] = {}

    @staticmethod
    def key(tenant: str, payload: bytes) -> str:
        return tenant + ":" + hashlib.sha256(payload).hexdigest()

    def get(self, tenant: str, payload: bytes) -> bytes | None:
        key = self.key(tenant, payload)
        entry = self._entries.get(key)
        if not entry or entry.expires_at < time.time():
            return None
        return entry.value

    def put(self, tenant: str, payload: bytes, value: bytes, ttl_seconds: int, source_fingerprint: str) -> str:
        key = self.key(tenant, payload)
        self._entries[key] = CacheEntry(key, value, tenant, time.time() + ttl_seconds, source_fingerprint)
        return key
