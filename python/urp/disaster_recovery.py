from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable

from .contracts import stable_json_hash, utc_now
from .storage import atomic_write_bytes, file_lock, resolve_under


INCLUDED_STATE_PATHS = [
    "approval_signing.key",
    "approvals",
    "cache",
    "checkpoints",
    "chunks",
    "kms_keys.json",
    "kms_master.key",
    "ledger.jsonl",
    "logs.jsonl",
    "manifests",
    "manifests.sqlite3",
    "plans",
    "plugins",
    "policies",
    "route_feedback.jsonl",
    "scheduler_jobs.jsonl",
    "traces.jsonl",
    "work_units",
]
BACKUP_VERSION = "urp.backup.v2"
MAX_ARCHIVE_FILES = 1_000_000
MAX_ARCHIVE_BYTES = 1024 * 1024 * 1024 * 1024


def export_state(state_dir: str | Path = ".urp", output: str | Path = "urp-backup.zip") -> Dict[str, Any]:
    state = Path(state_dir).resolve()
    out = Path(output).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest: Dict[str, Any] = {
        "backup_version": BACKUP_VERSION,
        "generated_at": utc_now(),
        "state_format": "local-durable-v1",
        "files": {},
    }
    with file_lock(state / ".backup.lock"):
        _checkpoint_sqlite_files(state)
        files = list(_state_files(state, out))
        temporary = out.with_name(f".{out.name}.{os.getpid()}.tmp")
        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                for path in files:
                    relative = path.relative_to(state).as_posix()
                    digest = _sha256(path)
                    size = path.stat().st_size
                    archive.write(path, relative)
                    manifest["files"][relative] = {"sha256": digest, "size": size}
                manifest["content_hash"] = stable_json_hash(manifest["files"])
                _sign_manifest(manifest)
                archive.writestr("backup_manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            os.replace(temporary, out)
        finally:
            if temporary.exists():
                temporary.unlink()
    return {**manifest, "archive": str(out), "file_count": len(manifest["files"])}


def import_state(archive: str | Path, state_dir: str | Path = ".urp", replace: bool = False) -> Dict[str, Any]:
    archive_path = Path(archive).resolve()
    state = Path(state_dir).resolve()
    state.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".urp-restore-", dir=state.parent) as temporary:
        staging = Path(temporary) / "state"
        staging.mkdir()
        manifest = _extract_verified(archive_path, staging)
        if replace:
            _replace_state(staging, state)
        else:
            _merge_state(staging, state)
    return {
        "imported": True,
        "backup_version": manifest["backup_version"],
        "file_count": len(manifest.get("files", {})),
        "mismatches": [],
        "replace": replace,
    }


def _extract_verified(archive_path: Path, staging: Path) -> Dict[str, Any]:
    with zipfile.ZipFile(archive_path, "r") as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ARCHIVE_FILES:
            raise ValueError("backup archive contains too many entries")
        total_size = sum(info.file_size for info in infos)
        if total_size > MAX_ARCHIVE_BYTES:
            raise ValueError("backup archive exceeds the configured extraction limit")
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise ValueError("backup archive contains duplicate entries")
        if "backup_manifest.json" not in names:
            raise ValueError("backup archive is missing backup_manifest.json")
        manifest = json.loads(archive.read("backup_manifest.json"))
        _validate_manifest(manifest)
        declared = set(manifest.get("files", {}))
        actual = {name for name in names if name != "backup_manifest.json" and not name.endswith("/")}
        if declared != actual:
            raise ValueError("backup archive entries do not match the signed manifest")
        for info in infos:
            if info.filename == "backup_manifest.json" or info.is_dir():
                continue
            _validate_archive_name(info.filename)
            if _is_symlink(info):
                raise ValueError(f"backup archive contains a symbolic link: {info.filename}")
            target = resolve_under(staging, PurePosixPath(info.filename))
            data = archive.read(info)
            expected = manifest["files"][info.filename]
            if len(data) != int(expected["size"]) or hashlib.sha256(data).hexdigest() != expected["sha256"]:
                raise ValueError(f"backup checksum mismatch: {info.filename}")
            atomic_write_bytes(target, data, mode=0o600 if _is_secret_path(info.filename) else None)
    return manifest


def _replace_state(staging: Path, state: Path) -> None:
    previous = state.with_name(f".{state.name}.pre-restore-{os.getpid()}")
    if previous.exists():
        shutil.rmtree(previous)
    try:
        if state.exists():
            os.replace(state, previous)
        os.replace(staging, state)
    except Exception:
        if not state.exists() and previous.exists():
            os.replace(previous, state)
        raise
    else:
        if previous.exists():
            shutil.rmtree(previous)


def _merge_state(staging: Path, state: Path) -> None:
    state.mkdir(parents=True, exist_ok=True)
    for source in sorted(path for path in staging.rglob("*") if path.is_file()):
        relative = source.relative_to(staging)
        target = resolve_under(state, relative)
        if target.exists():
            if _sha256(target) != _sha256(source):
                raise FileExistsError(f"restore would overwrite existing state: {relative}")
            continue
        atomic_write_bytes(target, source.read_bytes(), mode=0o600 if _is_secret_path(relative.as_posix()) else None)


def _state_files(state: Path, output: Path) -> Iterable[Path]:
    for item in INCLUDED_STATE_PATHS:
        path = state / item
        if not path.exists():
            continue
        candidates = path.rglob("*") if path.is_dir() else [path]
        for child in sorted(candidates):
            if not child.is_file() or child.resolve() == output:
                continue
            if child.name.endswith((".lock", "-wal", "-shm")) or child.name.startswith(".backup"):
                continue
            yield child


def _checkpoint_sqlite_files(state: Path) -> None:
    for path in state.rglob("*.sqlite3"):
        try:
            with closing(sqlite3.connect(path, timeout=30.0)) as connection, connection:
                connection.execute("PRAGMA wal_checkpoint(FULL)")
        except sqlite3.DatabaseError as exc:
            raise ValueError(f"could not checkpoint SQLite state before backup: {path}") from exc


def _validate_manifest(manifest: Dict[str, Any]) -> None:
    if manifest.get("backup_version") != BACKUP_VERSION:
        raise ValueError(f"unsupported backup version: {manifest.get('backup_version')}")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise ValueError("backup manifest files must be an object")
    if stable_json_hash(files) != manifest.get("content_hash"):
        raise ValueError("backup manifest content hash mismatch")
    key = os.environ.get("URP_BACKUP_SIGNING_KEY")
    signature = manifest.get("signature")
    if key:
        if not signature:
            raise ValueError("signed backup is required by URP_BACKUP_SIGNING_KEY")
        expected = hmac.new(key.encode("utf-8"), str(manifest["content_hash"]).encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(str(signature), expected):
            raise ValueError("backup manifest signature mismatch")


def _sign_manifest(manifest: Dict[str, Any]) -> None:
    key = os.environ.get("URP_BACKUP_SIGNING_KEY")
    if key:
        manifest["signature_algorithm"] = "hmac-sha256"
        manifest["signature"] = hmac.new(key.encode("utf-8"), str(manifest["content_hash"]).encode("ascii"), hashlib.sha256).hexdigest()


def _validate_archive_name(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe backup archive path: {name}")


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return ((info.external_attr >> 16) & 0o170000) == 0o120000


def _is_secret_path(relative: str) -> bool:
    name = PurePosixPath(relative).name
    return name in {"approval_signing.key", "kms_master.key", "kms_keys.json"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
