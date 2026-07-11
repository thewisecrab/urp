from __future__ import annotations

import json
import hashlib
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, List

from .adapters import Adapter, validate_plugin_descriptor
from .contracts import LedgerEvent
from .ledger import default_ledger
from .storage import atomic_write_json, file_lock, validate_identifier


REQUIRED_PLUGIN_FILES = ["plugin.yaml", "plugin.json", "README.md", "security.md"]
REQUIRED_PLUGIN_DIRS = ["src", "tests", "conformance", "examples"]


@dataclass(frozen=True)
class ConformanceResult:
    name: str
    passed: bool
    checks: Dict[str, bool]
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "checks": self.checks, "details": self.details}


@dataclass(frozen=True)
class LoadedPlugin:
    descriptor: Dict[str, Any]
    operations: Dict[str, Callable[..., Any]]
    module: ModuleType

    def invoke(self, operation: str, *args: Any, **kwargs: Any) -> Any:
        if operation not in self.descriptor["operations"] or operation not in self.operations:
            raise ValueError(f"plugin operation is not declared: {operation}")
        return self.operations[operation](*args, **kwargs)


class PluginRegistry:
    def __init__(self, state_dir: str | Path = ".urp") -> None:
        self.state_dir = Path(state_dir)
        self.root = self.state_dir / "plugins"
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.root / ".plugin.lock"

    def register(self, descriptor: Dict[str, Any], actor: str = "system") -> Dict[str, Any]:
        validation = validate_plugin_descriptor(descriptor)
        if not validation.accepted:
            raise ValueError(validation.details)
        name = validate_identifier(str(descriptor["name"]), label="plugin name")
        path = self.root / f"{name}.json"
        with file_lock(self.lock_path):
            atomic_write_json(path, descriptor)
        default_ledger(self.state_dir).append(LedgerEvent("plugin.registered", descriptor.get("tenant", "system"), actor=actor, details={"name": name, "trust_level": descriptor["trust_level"]}))
        return descriptor

    def list(self) -> List[Dict[str, Any]]:
        plugins = []
        with file_lock(self.lock_path, exclusive=False):
            for path in sorted(self.root.glob("*.json")):
                with path.open("r", encoding="utf-8") as fh:
                    plugins.append(json.load(fh))
        return plugins


def adapter_conformance(name: str, adapter: Adapter) -> ConformanceResult:
    caps = adapter.capabilities()
    callable_operations = [key for key, enabled in caps.items() if enabled is True and callable(getattr(adapter, key, None))]
    checks = {
        "has_name": bool(name),
        "capabilities_non_empty": bool(caps),
        "declares_mock_or_operations": bool(caps.get("mock") or any(caps.get(k) for k in ("put_object", "get_object", "execute_file"))),
    }
    if not caps.get("mock"):
        checks["advertised_operations_callable"] = bool(callable_operations)
    else:
        required = ["plan_work_unit", "execute_work_unit", "submit_work_unit", "rehydrate"]
        checks["mock_contract_methods"] = all(caps.get(key) is True and callable(getattr(adapter, key, None)) for key in required)
        checks["mock_external_free"] = caps.get("external_integrations_required") is False
    if name == "posix":
        required = ["plan_file", "execute_file", "read_file", "write_file", "rehydrate_file", "stat_file", "list_dir"]
        checks["posix_file_methods"] = all(caps.get(key) is True and callable(getattr(adapter, key, None)) for key in required)
    return ConformanceResult(name, all(checks.values()), checks, {"capabilities": caps})


def plugin_package_conformance(path: str | Path) -> ConformanceResult:
    root = Path(path)
    checks = {f"has_{name}": (root / name).exists() for name in REQUIRED_PLUGIN_FILES}
    checks.update({f"has_{name}/": (root / name).is_dir() for name in REQUIRED_PLUGIN_DIRS})
    descriptor: Dict[str, Any] = {}
    descriptor_path = root / "plugin.json"
    if descriptor_path.exists():
        with descriptor_path.open("r", encoding="utf-8") as fh:
            descriptor = json.load(fh)
        checks["descriptor_valid"] = validate_plugin_descriptor(descriptor).accepted
    else:
        checks["descriptor_valid"] = False
    checks["entrypoint_contained"] = _entrypoint_contained(root, descriptor)
    checks["entrypoint_digest_matches"] = _entrypoint_digest_matches(root, descriptor)
    runtime_operations: List[str] = []
    if checks["descriptor_valid"] and checks["entrypoint_contained"] and checks["entrypoint_digest_matches"]:
        try:
            loaded = load_plugin_package(root, allow_local=True)
        except Exception:
            checks["runtime_loads"] = False
        else:
            runtime_operations = sorted(loaded.operations)
            checks["runtime_loads"] = True
            checks["declared_operations_callable"] = set(descriptor["operations"]) <= set(runtime_operations)
    else:
        checks["runtime_loads"] = False
        checks["declared_operations_callable"] = False
    checks["package_digest_present"] = bool(_package_digest(root))
    return ConformanceResult(
        root.name,
        all(checks.values()),
        checks,
        {"descriptor": descriptor, "package_sha256": _package_digest(root), "runtime_operations": runtime_operations},
    )


def load_plugin_package(path: str | Path, *, allow_local: bool = False) -> LoadedPlugin:
    root = Path(path).resolve()
    descriptor_path = root / "plugin.json"
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    validation = validate_plugin_descriptor(descriptor)
    if not validation.accepted:
        raise ValueError(f"invalid plugin descriptor: {validation.details}")
    trust_level = descriptor["trust_level"]
    if trust_level == "community":
        raise ValueError("community plugins require an out-of-process sandbox and cannot be loaded in-process")
    if trust_level == "local" and not allow_local:
        raise ValueError("loading a local plugin requires allow_local=True")
    if not _entrypoint_contained(root, descriptor) or not _entrypoint_digest_matches(root, descriptor):
        raise ValueError("plugin entrypoint containment or integrity check failed")
    entrypoint = (root / descriptor["entrypoint"]).resolve()
    module_name = f"urp_plugin_{hashlib.sha256(str(root).encode('utf-8')).hexdigest()[:16]}"
    spec = importlib.util.spec_from_file_location(module_name, entrypoint)
    if spec is None or spec.loader is None:
        raise ValueError("plugin entrypoint could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    factory = getattr(module, "urp_plugin_v1", None)
    if not callable(factory):
        raise ValueError("plugin entrypoint must export urp_plugin_v1()")
    runtime = factory()
    if not isinstance(runtime, dict) or not isinstance(runtime.get("descriptor"), dict) or not isinstance(runtime.get("operations"), dict):
        raise ValueError("urp_plugin_v1() must return descriptor and operations objects")
    runtime_descriptor = runtime["descriptor"]
    for key in ("api_version", "name", "version", "category"):
        if runtime_descriptor.get(key) != descriptor.get(key):
            raise ValueError(f"runtime descriptor mismatch: {key}")
    operations = runtime["operations"]
    if not all(isinstance(name, str) and callable(operation) for name, operation in operations.items()):
        raise ValueError("plugin runtime operations must be callable")
    missing = set(descriptor["operations"]) - set(operations)
    if missing:
        raise ValueError(f"plugin runtime is missing declared operations: {sorted(missing)}")
    return LoadedPlugin(descriptor, operations, module)


def discover_plugin_packages(root: str | Path = "plugins") -> List[Path]:
    base = Path(root)
    if not base.exists():
        return []
    return sorted(path for path in base.glob("*/*") if path.is_dir() and (path / "plugin.json").exists())


def _entrypoint_contained(root: Path, descriptor: Dict[str, Any]) -> bool:
    entrypoint = descriptor.get("entrypoint")
    if not isinstance(entrypoint, str) or not entrypoint:
        return False
    try:
        path = (root / entrypoint).resolve()
        path.relative_to(root.resolve())
    except (ValueError, OSError):
        return False
    return path.is_file()


def _entrypoint_digest_matches(root: Path, descriptor: Dict[str, Any]) -> bool:
    if not _entrypoint_contained(root, descriptor):
        return False
    entrypoint = (root / str(descriptor["entrypoint"])).resolve()
    return hashlib.sha256(entrypoint.read_bytes()).hexdigest() == descriptor.get("entrypoint_sha256")


def _package_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = str(path.relative_to(root)).encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(path.read_bytes())
    return digest.hexdigest()
