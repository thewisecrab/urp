from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .contracts import stable_json_hash, utc_now
from .storage import atomic_write_json


DEFAULT_EXCLUDES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".urp",
    ".venv",
    ".DS_Store",
    ".coverage",
    "__pycache__",
    "archive",
    "build",
    "coverage",
    "dist",
    "htmlcov",
    "node_modules",
    "site",
    "target",
    "tmp",
    "PACKAGE_SHA256.json",
}


def iter_release_files(
    root: str | Path = ".",
    excludes: Iterable[str] = DEFAULT_EXCLUDES,
    excluded_paths: Iterable[str] = (),
) -> list[Path]:
    base = Path(root).resolve()
    excluded = set(excludes)
    excluded_relative_paths = set(excluded_paths)
    files: list[Path] = []
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(base).parts
        relative = path.relative_to(base).as_posix()
        if relative in excluded_relative_paths:
            continue
        if any(part in excluded or part.startswith(".urp") or part.endswith(".egg-info") for part in rel_parts):
            continue
        if path.name.endswith((".pyc", ".pyo")):
            continue
        files.append(path)
    return sorted(files)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_release_manifest(
    root: str | Path = ".",
    signing_key: str | bytes | None = None,
    *,
    excluded_paths: Iterable[str] = (),
) -> Dict[str, object]:
    base = Path(root).resolve()
    files = {
        str(path.relative_to(base)): {"sha256": sha256_file(path), "size": path.stat().st_size}
        for path in iter_release_files(base, excluded_paths=excluded_paths)
    }
    generated_at = _generated_at()
    content_digest = stable_json_hash(files)
    manifest: Dict[str, object] = {
        "manifest_version": "urp.release.v2",
        "scope": "active_distribution",
        "excluded_roots": sorted(DEFAULT_EXCLUDES),
        "generated_at": generated_at,
        "file_count": len(files),
        "files": files,
        "content_digest": content_digest,
        "content_digest_algorithm": "sha256(stable-json(files))",
        "provenance": {
            "builder": "urp.release.write_release_manifest",
            "python": platform.python_version(),
            "platform": platform.platform(),
            "source_date_epoch": os.environ.get("SOURCE_DATE_EPOCH"),
            "git": _git_provenance(base),
            "archive_policy": "archive/source_packages is preserved in the repository but excluded from the active release manifest",
        },
    }
    configured_key = signing_key or os.environ.get("URP_RELEASE_SIGNING_KEY")
    if configured_key:
        private_key = _private_key(configured_key)
        signed_payload = _signature_payload(manifest)
        signature = private_key.sign(signed_payload)
        public_key = private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        manifest["attestation"] = {
            "algorithm": "ed25519",
            "public_key": base64.b64encode(public_key).decode("ascii"),
            "signature": base64.b64encode(signature).decode("ascii"),
            "payload": "manifest_version,generated_at,content_digest,git.commit",
        }
    return manifest


def verify_release_manifest(
    manifest: Dict[str, Any],
    root: str | Path | None = None,
    *,
    require_signature: bool = False,
) -> Dict[str, Any]:
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise ValueError("release manifest files must be an object")
    content_valid = stable_json_hash(files) == manifest.get("content_digest")
    file_results: Dict[str, bool] = {}
    if root is not None:
        base = Path(root).resolve()
        for relative, metadata in files.items():
            path = _release_path(base, str(relative))
            if not isinstance(metadata, dict) or not isinstance(metadata.get("sha256"), str):
                raise ValueError(f"invalid release metadata: {relative}")
            file_results[relative] = (
                path.is_file()
                and path.stat().st_size == int(metadata["size"])
                and sha256_file(path) == metadata["sha256"]
            )
    attestation = manifest.get("attestation")
    signature_valid: bool | None = None
    if attestation:
        try:
            public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(attestation["public_key"], validate=True))
            public_key.verify(base64.b64decode(attestation["signature"], validate=True), _signature_payload(manifest))
        except Exception:
            signature_valid = False
        else:
            signature_valid = True
    passed = (
        content_valid
        and all(file_results.values())
        and signature_valid is not False
        and (not require_signature or signature_valid is True)
    )
    return {
        "passed": passed,
        "content_digest_valid": content_valid,
        "files_valid": all(file_results.values()) if file_results else None,
        "invalid_files": sorted(path for path, valid in file_results.items() if not valid),
        "signature_present": bool(attestation),
        "signature_valid": signature_valid,
    }


def write_release_manifest(root: str | Path = ".", output: str | Path = "PACKAGE_SHA256.json") -> Dict[str, object]:
    base = Path(root).resolve()
    out = (base / output).resolve()
    try:
        relative_output = out.relative_to(base).as_posix()
    except ValueError:
        relative_output = ""
    manifest = build_release_manifest(base, excluded_paths=[relative_output] if relative_output else [])
    atomic_write_json(out, manifest)
    return manifest


def _private_key(value: str | bytes) -> Ed25519PrivateKey:
    if isinstance(value, str):
        try:
            raw = base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("URP_RELEASE_SIGNING_KEY must be base64-encoded Ed25519 private key bytes") from exc
    else:
        raw = value
    if len(raw) != 32:
        raise ValueError("URP_RELEASE_SIGNING_KEY must decode to exactly 32 bytes")
    return Ed25519PrivateKey.from_private_bytes(raw)


def _signature_payload(manifest: Dict[str, Any]) -> bytes:
    git = manifest.get("provenance", {}).get("git", {})
    payload = {
        "manifest_version": manifest.get("manifest_version"),
        "generated_at": manifest.get("generated_at"),
        "content_digest": manifest.get("content_digest"),
        "git_commit": git.get("commit"),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _generated_at() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        return datetime.fromtimestamp(int(epoch), timezone.utc).isoformat()
    return utc_now()


def _git_provenance(root: Path) -> Dict[str, Any]:
    def run(*args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None
        return result.stdout.strip()

    commit = run("rev-parse", "HEAD")
    branch = run("branch", "--show-current")
    status = run("status", "--porcelain=v1", "--untracked-files=normal")
    return {
        "commit": commit,
        "branch": branch,
        "dirty": bool(status) if status is not None else None,
        "available": commit is not None,
    }


def _release_path(root: Path, relative: str) -> Path:
    candidate = PurePosixPath(relative)
    if (
        candidate.is_absolute()
        or not candidate.parts
        or "\\" in relative
        or any(part in {"", ".", ".."} for part in candidate.parts)
    ):
        raise ValueError(f"unsafe release manifest path: {relative}")
    path = (root / Path(*candidate.parts)).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"release manifest path escapes root: {relative}") from exc
    return path
