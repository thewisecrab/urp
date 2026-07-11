from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set
from .contracts import stable_json_hash


@dataclass
class CacheEntry:
    key: str
    tenant: str
    namespace: str
    value: Any
    source_fingerprints: Set[str] = field(default_factory=set)
    verifier_passed: bool = False


class URPCache:
    def __init__(self) -> None:
        self._entries: Dict[str, CacheEntry] = {}

    def exact_key(self, tenant: str, namespace: str, payload: Any, source_fingerprints: Optional[Set[str]] = None) -> str:
        return stable_json_hash({
            "tenant": tenant,
            "namespace": namespace,
            "payload": payload,
            "source_fingerprints": sorted(source_fingerprints or set()),
        })

    def put(self, entry: CacheEntry) -> None:
        if not entry.verifier_passed:
            raise ValueError("cache entries must have verifier_passed=True")
        self._entries[entry.key] = entry

    def get(self, key: str, tenant: str, namespace: str, source_fingerprints: Optional[Set[str]] = None) -> Optional[Any]:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.tenant != tenant or entry.namespace != namespace:
            return None
        if source_fingerprints is not None and entry.source_fingerprints != source_fingerprints:
            return None
        if not entry.verifier_passed:
            return None
        return entry.value
