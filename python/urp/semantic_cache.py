from __future__ import annotations

import json
import copy
import sqlite3
import threading
import time
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional, Set

from .contracts import stable_json_hash
from .encoding import decode_json_value, encode_json_value
from .storage import ensure_private_file
from .verifiers import VerificationResult, verify_non_empty_text, verify_source_fingerprints


@dataclass(frozen=True)
class SemanticCacheEntry:
    key: str
    tenant: str
    namespace: str
    normalized_text: str
    value: Any
    source_fingerprints: Set[str] = field(default_factory=set)
    verification: VerificationResult = field(default_factory=lambda: VerificationResult(False, "missing@1", "missing_verification"))
    task_type: str = "general"
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None


@dataclass(frozen=True)
class SemanticCacheHit:
    value: Any
    key: str
    score: float
    verification: VerificationResult
    created_at: float


class SemanticCache:
    """Policy-facing semantic cache.

    Every stored entry carries an accepted verifier result, and every lookup
    re-checks tenant, namespace, sources, freshness, and output shape.
    """

    def __init__(self, threshold: float = 0.82, path: str | Path | None = None) -> None:
        if not 0 <= threshold <= 1:
            raise ValueError("semantic cache threshold must be between 0 and 1")
        self.threshold = threshold
        self.path = Path(path) if path is not None else None
        self._entries: Dict[str, SemanticCacheEntry] = {}
        self._lock = threading.RLock()
        if self.path is not None:
            ensure_private_file(self.path)
            self._initialize()

    def put(self, entry: SemanticCacheEntry) -> None:
        if not entry.verification.accepted:
            raise ValueError("semantic cache entries require an accepted verification result")
        if entry.expires_at is not None and entry.expires_at <= time.time():
            raise ValueError("semantic cache entry is already expired")
        with self._lock:
            if self.path is None:
                self._entries[entry.key] = SemanticCacheEntry(
                    entry.key,
                    entry.tenant,
                    entry.namespace,
                    entry.normalized_text,
                    copy.deepcopy(entry.value),
                    set(entry.source_fingerprints),
                    entry.verification,
                    entry.task_type,
                    entry.created_at,
                    entry.expires_at,
                )
                return
            with closing(self._connect()) as conn, conn:
                conn.execute(
                    """
                    INSERT INTO semantic_cache(
                        cache_key, tenant, namespace, normalized_text, value_json,
                        source_fingerprints_json, verification_json, task_type,
                        created_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(cache_key) DO UPDATE SET
                        tenant=excluded.tenant,
                        namespace=excluded.namespace,
                        normalized_text=excluded.normalized_text,
                        value_json=excluded.value_json,
                        source_fingerprints_json=excluded.source_fingerprints_json,
                        verification_json=excluded.verification_json,
                        task_type=excluded.task_type,
                        created_at=excluded.created_at,
                        expires_at=excluded.expires_at
                    """,
                    (
                        entry.key,
                        entry.tenant,
                        entry.namespace,
                        entry.normalized_text,
                        json.dumps(encode_json_value(entry.value), sort_keys=True, separators=(",", ":")),
                        json.dumps(sorted(entry.source_fingerprints), separators=(",", ":")),
                        json.dumps(entry.verification.to_dict(), sort_keys=True, separators=(",", ":")),
                        entry.task_type,
                        entry.created_at,
                        entry.expires_at,
                    ),
                )

    def store(
        self,
        tenant: str,
        namespace: str,
        normalized_text: str,
        value: Any,
        source_fingerprints: Set[str],
        *,
        verification: VerificationResult,
        task_type: str = "general",
        ttl_seconds: float | None = None,
    ) -> str:
        if ttl_seconds is not None and ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        normalized = normalize_semantic_text(normalized_text)
        key = stable_json_hash(
            {
                "tenant": tenant,
                "namespace": namespace,
                "text": normalized,
                "sources": sorted(source_fingerprints),
                "task_type": task_type,
            }
        )
        now = time.time()
        self.put(
            SemanticCacheEntry(
                key=key,
                tenant=tenant,
                namespace=namespace,
                normalized_text=normalized,
                value=value,
                source_fingerprints=set(source_fingerprints),
                verification=verification,
                task_type=task_type,
                created_at=now,
                expires_at=now + ttl_seconds if ttl_seconds is not None else None,
            )
        )
        return key

    def lookup(
        self,
        tenant: str,
        namespace: str,
        normalized_text: str,
        source_fingerprints: Set[str],
        task_type: str = "general",
        threshold: Optional[float] = None,
        verifier: Callable[[Any], VerificationResult] | None = None,
    ) -> Optional[Any]:
        hit = self.lookup_hit(tenant, namespace, normalized_text, source_fingerprints, task_type, threshold, verifier)
        return hit.value if hit else None

    def lookup_hit(
        self,
        tenant: str,
        namespace: str,
        normalized_text: str,
        source_fingerprints: Set[str],
        task_type: str = "general",
        threshold: Optional[float] = None,
        verifier: Callable[[Any], VerificationResult] | None = None,
    ) -> SemanticCacheHit | None:
        resolved_threshold = self.threshold if threshold is None else threshold
        if not 0 <= resolved_threshold <= 1:
            raise ValueError("semantic cache threshold must be between 0 and 1")
        query = normalize_semantic_text(normalized_text)
        now = time.time()
        best: tuple[float, SemanticCacheEntry] | None = None
        with self._lock:
            for entry in self._iter_entries(tenant, namespace, task_type):
                if entry.expires_at is not None and entry.expires_at <= now:
                    self.delete(entry.key)
                    continue
                source_check = verify_source_fingerprints(source_fingerprints, entry.source_fingerprints)
                if not source_check.accepted or not entry.verification.accepted:
                    continue
                score = semantic_similarity(query, entry.normalized_text)
                if score >= resolved_threshold and (best is None or score > best[0]):
                    best = (score, entry)
            if best is None:
                return None
            output_check = (verifier or _default_value_verifier)(best[1].value)
            if not output_check.accepted:
                self.delete(best[1].key)
                return None
            return SemanticCacheHit(copy.deepcopy(best[1].value), best[1].key, best[0], output_check, best[1].created_at)

    def delete(self, key: str) -> None:
        if self.path is None:
            self._entries.pop(key, None)
            return
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM semantic_cache WHERE cache_key = ?", (key,))

    def _iter_entries(self, tenant: str, namespace: str, task_type: str) -> Iterable[SemanticCacheEntry]:
        if self.path is None:
            return [
                entry
                for entry in self._entries.values()
                if entry.tenant == tenant and entry.namespace == namespace and entry.task_type == task_type
            ]
        with closing(self._connect()) as conn, conn:
            rows = conn.execute(
                """
                SELECT cache_key, tenant, namespace, normalized_text, value_json,
                       source_fingerprints_json, verification_json, task_type,
                       created_at, expires_at
                FROM semantic_cache
                WHERE tenant = ? AND namespace = ? AND task_type = ?
                """,
                (tenant, namespace, task_type),
            ).fetchall()
        return [_entry_from_row(row) for row in rows]

    def _initialize(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS semantic_cache(
                    cache_key TEXT PRIMARY KEY,
                    tenant TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    normalized_text TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    source_fingerprints_json TEXT NOT NULL,
                    verification_json TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_scope ON semantic_cache(tenant, namespace, task_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_expiry ON semantic_cache(expires_at)")

    def _connect(self) -> sqlite3.Connection:
        if self.path is None:
            raise RuntimeError("SQLite connection requested for an in-memory semantic cache")
        return sqlite3.connect(self.path, timeout=30.0)


def normalize_semantic_text(text: str) -> str:
    return " ".join(text.casefold().strip().split())


def semantic_similarity(left: str, right: str) -> float:
    word_score = jaccard_similarity(left, right)
    left_trigrams = _character_ngrams(left, 3)
    right_trigrams = _character_ngrams(right, 3)
    trigram_score = _set_jaccard(left_trigrams, right_trigrams)
    return 0.7 * word_score + 0.3 * trigram_score


def jaccard_similarity(left: str, right: str) -> float:
    return _set_jaccard(set(left.split()), set(right.split()))


def _set_jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _character_ngrams(value: str, size: int) -> set[str]:
    compact = " ".join(value.split())
    if len(compact) <= size:
        return {compact} if compact else set()
    return {compact[index : index + size] for index in range(len(compact) - size + 1)}


def _default_value_verifier(value: Any) -> VerificationResult:
    if isinstance(value, dict):
        try:
            value = value["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return VerificationResult(False, "semantic_cache_shape@1", "missing_chat_completion_content")
    return verify_non_empty_text(str(value))


def _entry_from_row(row: tuple[Any, ...]) -> SemanticCacheEntry:
    verification = json.loads(str(row[6]))
    return SemanticCacheEntry(
        key=str(row[0]),
        tenant=str(row[1]),
        namespace=str(row[2]),
        normalized_text=str(row[3]),
        value=decode_json_value(json.loads(str(row[4]))),
        source_fingerprints=set(json.loads(str(row[5]))),
        verification=VerificationResult(
            bool(verification.get("accepted")),
            str(verification.get("verifier_id", "unknown@1")),
            str(verification.get("reason", "unknown")),
            dict(verification.get("details") or {}),
        ),
        task_type=str(row[7]),
        created_at=float(row[8]),
        expires_at=float(row[9]) if row[9] is not None else None,
    )
