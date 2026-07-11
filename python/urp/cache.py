from __future__ import annotations

import json
import copy
import sqlite3
import threading
import time
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Set

from .contracts import stable_json_hash
from .encoding import decode_json_value, encode_json_value
from .storage import ensure_private_file


@dataclass(frozen=True)
class CacheEntry:
    key: str
    tenant: str
    namespace: str
    value: Any
    source_fingerprints: Set[str] = field(default_factory=set)
    verifier_passed: bool = False
    expires_at: float | None = None


class URPCache:
    """Tenant-isolated exact cache with an optional durable SQLite backend."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self._entries: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        if self.path is not None:
            ensure_private_file(self.path)
            self._initialize()

    def exact_key(self, tenant: str, namespace: str, payload: Any, source_fingerprints: Optional[Set[str]] = None) -> str:
        return stable_json_hash(
            {
                "tenant": tenant,
                "namespace": namespace,
                "payload": encode_json_value(payload),
                "source_fingerprints": sorted(source_fingerprints or set()),
            }
        )

    def put(self, entry: CacheEntry) -> None:
        if not entry.verifier_passed:
            raise ValueError("cache entries must have verifier_passed=True")
        if not entry.tenant or not entry.namespace:
            raise ValueError("cache entries require tenant and namespace")
        if entry.expires_at is not None and entry.expires_at <= time.time():
            raise ValueError("cache entry is already expired")
        with self._lock:
            if self.path is None:
                self._entries[entry.key] = CacheEntry(
                    entry.key,
                    entry.tenant,
                    entry.namespace,
                    copy.deepcopy(entry.value),
                    set(entry.source_fingerprints),
                    entry.verifier_passed,
                    entry.expires_at,
                )
                return
            with closing(self._connect()) as conn, conn:
                conn.execute(
                    """
                    INSERT INTO exact_cache(
                        cache_key, tenant, namespace, value_json, source_fingerprints_json,
                        verifier_passed, expires_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    ON CONFLICT(cache_key) DO UPDATE SET
                        tenant=excluded.tenant,
                        namespace=excluded.namespace,
                        value_json=excluded.value_json,
                        source_fingerprints_json=excluded.source_fingerprints_json,
                        verifier_passed=excluded.verifier_passed,
                        expires_at=excluded.expires_at,
                        created_at=excluded.created_at
                    """,
                    (
                        entry.key,
                        entry.tenant,
                        entry.namespace,
                        json.dumps(encode_json_value(entry.value), sort_keys=True, separators=(",", ":")),
                        json.dumps(sorted(entry.source_fingerprints), separators=(",", ":")),
                        entry.expires_at,
                        time.time(),
                    ),
                )

    def get(self, key: str, tenant: str, namespace: str, source_fingerprints: Optional[Set[str]] = None) -> Optional[Any]:
        with self._lock:
            entry = self._get_entry(key)
            if entry is None:
                return None
            if entry.tenant != tenant or entry.namespace != namespace:
                return None
            if source_fingerprints is not None and entry.source_fingerprints != source_fingerprints:
                return None
            if not entry.verifier_passed:
                return None
            if entry.expires_at is not None and entry.expires_at <= time.time():
                self.delete(key)
                return None
            return copy.deepcopy(entry.value)

    def delete(self, key: str) -> None:
        with self._lock:
            if self.path is None:
                self._entries.pop(key, None)
                return
            with closing(self._connect()) as conn, conn:
                conn.execute("DELETE FROM exact_cache WHERE cache_key = ?", (key,))

    def purge_expired(self) -> int:
        now = time.time()
        with self._lock:
            if self.path is None:
                expired = [key for key, entry in self._entries.items() if entry.expires_at is not None and entry.expires_at <= now]
                for key in expired:
                    del self._entries[key]
                return len(expired)
            with closing(self._connect()) as conn, conn:
                cursor = conn.execute("DELETE FROM exact_cache WHERE expires_at IS NOT NULL AND expires_at <= ?", (now,))
                return max(0, cursor.rowcount)

    def _get_entry(self, key: str) -> CacheEntry | None:
        if self.path is None:
            return self._entries.get(key)
        with closing(self._connect()) as conn, conn:
            row = conn.execute(
                """
                SELECT cache_key, tenant, namespace, value_json, source_fingerprints_json,
                       verifier_passed, expires_at
                FROM exact_cache WHERE cache_key = ?
                """,
                (key,),
            ).fetchone()
        if row is None:
            return None
        return CacheEntry(
            key=str(row[0]),
            tenant=str(row[1]),
            namespace=str(row[2]),
            value=decode_json_value(json.loads(str(row[3]))),
            source_fingerprints=set(json.loads(str(row[4]))),
            verifier_passed=bool(row[5]),
            expires_at=float(row[6]) if row[6] is not None else None,
        )

    def _initialize(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS exact_cache(
                    cache_key TEXT PRIMARY KEY,
                    tenant TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    source_fingerprints_json TEXT NOT NULL,
                    verifier_passed INTEGER NOT NULL CHECK(verifier_passed = 1),
                    expires_at REAL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_exact_cache_scope ON exact_cache(tenant, namespace)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_exact_cache_expiry ON exact_cache(expires_at)")

    def _connect(self) -> sqlite3.Connection:
        if self.path is None:
            raise RuntimeError("SQLite connection requested for an in-memory cache")
        return sqlite3.connect(self.path, timeout=30.0)
