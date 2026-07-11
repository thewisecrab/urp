from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator

try:  # POSIX is the supported local runtime; the fallback still protects threads.
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None  # type: ignore[assignment]


IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_THREAD_LOCKS: Dict[str, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


def validate_identifier(value: str, *, label: str = "identifier", prefix: str | None = None) -> str:
    if not isinstance(value, str) or not IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"invalid {label}: expected 1-128 safe identifier characters")
    if value in {".", ".."}:
        raise ValueError(f"invalid {label}: path traversal is not allowed")
    if prefix and not value.startswith(prefix):
        raise ValueError(f"invalid {label}: expected prefix {prefix}")
    return value


def resolve_under(root: str | Path, relative: str | Path) -> Path:
    base = Path(root).resolve()
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError("path escapes configured storage root") from exc
    return candidate


def atomic_write_bytes(path: str | Path, data: bytes, *, mode: int | None = None) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    tmp = Path(temporary)
    try:
        if mode is not None:
            os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
        _fsync_directory(target.parent)
    finally:
        if tmp.exists():
            tmp.unlink()


def atomic_write_text(path: str | Path, text: str, *, mode: int | None = None) -> None:
    atomic_write_bytes(path, text.encode("utf-8"), mode=mode)


def atomic_write_json(path: str | Path, value: Any, *, mode: int | None = None) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", mode=mode)


def append_json_line(path: str | Path, value: Any, *, lock_path: str | Path | None = None, mode: int = 0o600) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, sort_keys=True, separators=(",", ":"), default=str) + "\n").encode("utf-8")
    with file_lock(lock_path or target.with_suffix(target.suffix + ".lock")):
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_APPEND, mode)
        try:
            os.write(fd, encoded)
            os.fsync(fd)
        finally:
            os.close(fd)


def ensure_private_file(path: str | Path, *, mode: int = 0o600) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    existed = target.exists()
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_APPEND, mode)
    os.close(fd)
    os.chmod(target, mode)
    if not existed:
        _fsync_directory(target.parent)
    return target


@contextmanager
def file_lock(path: str | Path, *, exclusive: bool = True) -> Iterator[None]:
    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    key = str(lock_path.resolve())
    with _THREAD_LOCKS_GUARD:
        thread_lock = _THREAD_LOCKS.setdefault(key, threading.RLock())
    with thread_lock:
        with lock_path.open("a+b") as fh:
            if fcntl is not None:
                operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
                fcntl.flock(fh.fileno(), operation)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:  # pragma: no cover - filesystem dependent
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
