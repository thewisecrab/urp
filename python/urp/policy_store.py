from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from .contracts import LedgerEvent, stable_json_hash, utc_now
from .ledger import default_ledger
from .policy import load_policy_bundle, validate_policy_bundle
from .storage import atomic_write_json, file_lock, validate_identifier


class PolicyBundleStore:
    def __init__(self, state_dir: str | Path = ".urp") -> None:
        self.state_dir = Path(state_dir)
        self.root = self.state_dir / "policies"
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.root / ".policy.lock"

    def publish(self, bundle_or_path: Dict[str, Any] | str | Path, actor: str = "system") -> Dict[str, Any]:
        bundle = load_policy_bundle(bundle_or_path) if isinstance(bundle_or_path, (str, Path)) else bundle_or_path
        validate_policy_bundle(bundle)
        name = validate_identifier(str(bundle.get("metadata", {}).get("name", "default")), label="policy name")
        version = validate_identifier(str(bundle.get("metadata", {}).get("version") or stable_json_hash(bundle)[:16]), label="policy version")
        record = {"name": name, "version": version, "published_at": utc_now(), "bundle": bundle, "bundle_hash": stable_json_hash(bundle)}
        policy_dir = self.root / name
        policy_dir.mkdir(parents=True, exist_ok=True)
        with file_lock(self.lock_path):
            atomic_write_json(policy_dir / f"{version}.json", record)
        self._write_active(name, version)
        default_ledger(self.state_dir).append(
            LedgerEvent("policy.bundle.published", bundle.get("metadata", {}).get("tenant", "system"), policy_bundle_id=name, actor=actor, decision=version, details={"bundle_hash": record["bundle_hash"]})
        )
        return record

    def active(self, name: str = "default-safe") -> Dict[str, Any]:
        validate_identifier(name, label="policy name")
        active = self._read_active()
        version = active[name]
        return self.get(name, version)

    def active_for_work_unit(self, policy_name: str | None = None) -> Dict[str, Any] | None:
        active = self._read_active()
        selected = policy_name or os.environ.get("URP_ACTIVE_POLICY")
        if selected:
            return self.active(validate_identifier(selected, label="policy name")) if selected in active else None
        if "default-safe" in active:
            return self.active("default-safe")
        if len(active) == 1:
            name = next(iter(active))
            return self.active(name)
        return None

    def get(self, name: str, version: str) -> Dict[str, Any]:
        validate_identifier(name, label="policy name")
        validate_identifier(version, label="policy version")
        with (self.root / name / f"{version}.json").open("r", encoding="utf-8") as fh:
            record = json.load(fh)
        bundle_hash = stable_json_hash(record.get("bundle", {}))
        if bundle_hash != record.get("bundle_hash"):
            raise ValueError(f"policy bundle integrity check failed: {name}@{version}")
        return record

    def list(self) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        for path in sorted(self.root.glob("*/*.json")):
            if path.name == "active.json":
                continue
            with path.open("r", encoding="utf-8") as fh:
                record = json.load(fh)
            if stable_json_hash(record.get("bundle", {})) != record.get("bundle_hash"):
                raise ValueError(f"policy bundle integrity check failed: {path}")
            records.append(record)
        return records

    def rollback(self, name: str, version: str, actor: str = "system") -> Dict[str, Any]:
        record = self.get(name, version)
        previous = self._read_active().get(name)
        self._write_active(name, version)
        default_ledger(self.state_dir).append(
            LedgerEvent("policy.bundle.rolled_back", record["bundle"].get("metadata", {}).get("tenant", "system"), policy_bundle_id=name, actor=actor, decision=version, details={"previous_version": previous})
        )
        return record

    def reload(self, name: str = "default-safe", actor: str = "system") -> Dict[str, Any]:
        record = self.active(name)
        bundle = record["bundle"]
        validate_policy_bundle(bundle)
        bundle_hash = stable_json_hash(bundle)
        default_ledger(self.state_dir).append(
            LedgerEvent(
                "policy.bundle.reloaded",
                bundle.get("metadata", {}).get("tenant", "system"),
                policy_bundle_id=name,
                actor=actor,
                decision=record["version"],
                details={
                    "version": record["version"],
                    "bundle_hash": bundle_hash,
                    "record_hash_matches": bundle_hash == record.get("bundle_hash"),
                },
            )
        )
        return {**record, "reloaded_at": utc_now(), "record_hash_matches": bundle_hash == record.get("bundle_hash")}

    def _read_active(self) -> Dict[str, str]:
        path = self.root / "active.json"
        if not path.exists():
            return {}
        with file_lock(self.lock_path, exclusive=False):
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)

    def _write_active(self, name: str, version: str) -> None:
        validate_identifier(name, label="policy name")
        validate_identifier(version, label="policy version")
        with file_lock(self.lock_path):
            path = self.root / "active.json"
            if path.exists():
                with path.open("r", encoding="utf-8") as fh:
                    active = json.load(fh)
            else:
                active = {}
            active[name] = version
            atomic_write_json(self.root / "active.json", active)


def resolve_active_policy_bundle(state_dir: str | Path, policy_name: str | None = None) -> Dict[str, Any] | None:
    record = PolicyBundleStore(state_dir).active_for_work_unit(policy_name)
    return dict(record["bundle"]) if record else None
