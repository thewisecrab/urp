from __future__ import annotations

import json
from typing import Iterable, List, Optional

from .auth import current_tenant
from .contracts import LedgerEvent, Manifest
from .schema_validation import validate_named_schema
from .storage import validate_identifier


class PostgresManifestStore:
    """Opt-in PostgreSQL manifest store with tenant-scoped queries."""

    def __init__(self, dsn: str) -> None:
        try:
            import psycopg  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional production dependency
            raise RuntimeError("install urp[production] to use PostgreSQL persistence") from exc
        self._psycopg = psycopg
        self.dsn = dsn
        self._initialize()

    def put(self, manifest: Manifest) -> None:
        tenant = current_tenant()
        if tenant and manifest.tenant != tenant:
            from .errors import tenant_mismatch

            raise tenant_mismatch(tenant, manifest.tenant)
        validate_identifier(manifest.manifest_id, label="manifest id", prefix="mf_")
        data = manifest.to_dict()
        validate_named_schema("manifest", data)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO urp_manifests(manifest_id, work_unit_id, tenant, logical_ref, created_at, payload)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT(manifest_id) DO UPDATE SET
                    work_unit_id=excluded.work_unit_id,
                    tenant=excluded.tenant,
                    logical_ref=excluded.logical_ref,
                    created_at=excluded.created_at,
                    payload=excluded.payload
                """,
                (manifest.manifest_id, manifest.work_unit_id, manifest.tenant, manifest.logical_ref, manifest.created_at, json.dumps(data)),
            )

    def get(self, manifest_id: str) -> Manifest:
        validate_identifier(manifest_id, label="manifest id", prefix="mf_")
        tenant = current_tenant()
        with self._connect() as conn:
            if tenant:
                row = conn.execute("SELECT payload FROM urp_manifests WHERE manifest_id=%s AND tenant=%s", (manifest_id, tenant)).fetchone()
            else:
                row = conn.execute("SELECT payload FROM urp_manifests WHERE manifest_id=%s", (manifest_id,)).fetchone()
        if row is None:
            raise KeyError(manifest_id)
        return Manifest.from_dict(_json_value(row[0]))

    def get_for_tenant(self, manifest_id: str, tenant: str) -> Manifest:
        manifest = self.get(manifest_id)
        if manifest.tenant != tenant:
            from .errors import tenant_mismatch

            raise tenant_mismatch(tenant, manifest.tenant)
        return manifest

    def get_by_work_unit(self, work_unit_id: str) -> Manifest:
        validate_identifier(work_unit_id, label="work unit id", prefix="wu_")
        tenant = current_tenant()
        with self._connect() as conn:
            if tenant:
                row = conn.execute(
                    "SELECT payload FROM urp_manifests WHERE work_unit_id=%s AND tenant=%s ORDER BY created_at DESC LIMIT 1",
                    (work_unit_id, tenant),
                ).fetchone()
            else:
                row = conn.execute("SELECT payload FROM urp_manifests WHERE work_unit_id=%s ORDER BY created_at DESC LIMIT 1", (work_unit_id,)).fetchone()
        if row is None:
            raise KeyError(work_unit_id)
        return Manifest.from_dict(_json_value(row[0]))

    def list(self, tenant: str | None = None) -> List[Manifest]:
        tenant = tenant or current_tenant()
        with self._connect() as conn:
            if tenant:
                rows = conn.execute("SELECT payload FROM urp_manifests WHERE tenant=%s ORDER BY created_at", (tenant,)).fetchall()
            else:
                rows = conn.execute("SELECT payload FROM urp_manifests ORDER BY created_at").fetchall()
        return [Manifest.from_dict(_json_value(row[0])) for row in rows]

    def find_by_logical_ref(self, logical_ref: str) -> List[Manifest]:
        tenant = current_tenant()
        with self._connect() as conn:
            if tenant:
                rows = conn.execute(
                    "SELECT payload FROM urp_manifests WHERE logical_ref=%s AND tenant=%s ORDER BY created_at",
                    (logical_ref, tenant),
                ).fetchall()
            else:
                rows = conn.execute("SELECT payload FROM urp_manifests WHERE logical_ref=%s ORDER BY created_at", (logical_ref,)).fetchall()
        return [Manifest.from_dict(_json_value(row[0])) for row in rows]

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS urp_manifests(
                    manifest_id text PRIMARY KEY,
                    work_unit_id text NOT NULL,
                    tenant text NOT NULL,
                    logical_ref text NOT NULL,
                    created_at timestamptz NOT NULL,
                    payload jsonb NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS urp_manifests_work_unit_idx ON urp_manifests(work_unit_id, created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS urp_manifests_tenant_ref_idx ON urp_manifests(tenant, logical_ref)")

    def _connect(self):
        return self._psycopg.connect(self.dsn, autocommit=False)


def _json_value(value):
    return json.loads(value) if isinstance(value, str) else dict(value)


class PostgresLedger:
    """Append-only PostgreSQL ledger with a transaction-serialized hash chain."""

    def __init__(self, dsn: str) -> None:
        try:
            import psycopg  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional production dependency
            raise RuntimeError("install urp[production] to use PostgreSQL persistence") from exc
        self._psycopg = psycopg
        self.dsn = dsn
        self._initialize()

    def append(self, event: LedgerEvent) -> LedgerEvent:
        tenant = current_tenant()
        if tenant and event.tenant != tenant:
            from .errors import tenant_mismatch

            raise tenant_mismatch(tenant, event.tenant)
        with self._connect() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtext('urp-ledger-v1'))")
            row = conn.execute("SELECT event_hash FROM urp_ledger ORDER BY sequence DESC LIMIT 1").fetchone()
            chained = event.with_chain_hash(str(row[0]) if row else None)
            data = chained.to_dict()
            validate_named_schema("ledger_event", data)
            conn.execute(
                """
                INSERT INTO urp_ledger(event_id, tenant, work_unit_id, manifest_id, event_type, created_at, event_hash, payload)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    chained.event_id,
                    chained.tenant,
                    chained.work_unit_id,
                    chained.manifest_id,
                    chained.event_type,
                    chained.created_at,
                    chained.event_hash,
                    json.dumps(data),
                ),
            )
        return chained

    def read(self) -> List[LedgerEvent]:
        tenant = current_tenant()
        with self._connect() as conn:
            if tenant:
                rows = conn.execute("SELECT payload FROM urp_ledger WHERE tenant=%s ORDER BY sequence", (tenant,)).fetchall()
            else:
                rows = conn.execute("SELECT payload FROM urp_ledger ORDER BY sequence").fetchall()
        return [LedgerEvent.from_dict(_json_value(row[0])) for row in rows]

    def query(
        self,
        tenant: Optional[str] = None,
        work_unit_id: Optional[str] = None,
        manifest_id: Optional[str] = None,
        event_types: Optional[Iterable[str]] = None,
        limit: Optional[int] = None,
    ) -> List[LedgerEvent]:
        tenant = tenant or current_tenant()
        clauses: list[str] = []
        params: list[object] = []
        if tenant:
            clauses.append("tenant=%s")
            params.append(tenant)
        if work_unit_id:
            clauses.append("work_unit_id=%s")
            params.append(work_unit_id)
        if manifest_id:
            clauses.append("manifest_id=%s")
            params.append(manifest_id)
        wanted = list(event_types or [])
        if wanted:
            clauses.append("event_type=ANY(%s)")
            params.append(wanted)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        order = " ORDER BY sequence DESC" if limit else " ORDER BY sequence"
        if limit:
            params.append(int(limit))
            query = f"SELECT payload FROM urp_ledger{where}{order} LIMIT %s"
        else:
            query = f"SELECT payload FROM urp_ledger{where}{order}"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        events = [LedgerEvent.from_dict(_json_value(row[0])) for row in rows]
        return list(reversed(events)) if limit else events

    def last_hash(self) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute("SELECT event_hash FROM urp_ledger ORDER BY sequence DESC LIMIT 1").fetchone()
        return str(row[0]) if row else None

    def verify_chain(self) -> bool:
        previous = None
        with self._connect() as conn:
            rows = conn.execute("SELECT payload FROM urp_ledger ORDER BY sequence").fetchall()
        for event in (LedgerEvent.from_dict(_json_value(row[0])) for row in rows):
            if event.prev_hash != previous or event.with_chain_hash(event.prev_hash).event_hash != event.event_hash:
                return False
            previous = event.event_hash
        return True

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS urp_ledger(
                    sequence bigserial PRIMARY KEY,
                    event_id text UNIQUE NOT NULL,
                    tenant text NOT NULL,
                    work_unit_id text,
                    manifest_id text,
                    event_type text NOT NULL,
                    created_at timestamptz NOT NULL,
                    event_hash text UNIQUE NOT NULL,
                    payload jsonb NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS urp_ledger_tenant_sequence_idx ON urp_ledger(tenant, sequence)")
            conn.execute("CREATE INDEX IF NOT EXISTS urp_ledger_work_unit_idx ON urp_ledger(work_unit_id, sequence)")
            conn.execute("CREATE INDEX IF NOT EXISTS urp_ledger_manifest_idx ON urp_ledger(manifest_id, sequence)")

    def _connect(self):
        return self._psycopg.connect(self.dsn, autocommit=False)
