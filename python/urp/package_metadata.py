from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .contracts import utc_now
from .release import iter_release_files
from .storage import atomic_write_json


GENERATED_METADATA = {"PACKAGE_SHA256.json", "line_count_manifest.json", "package_manifest.json"}
TEXT_SUFFIXES = {
    ".go",
    ".json",
    ".md",
    ".proto",
    ".py",
    ".rs",
    ".tf",
    ".toml",
    ".ts",
    ".yaml",
    ".yml",
}


def build_package_manifest(root: str | Path = ".") -> Dict[str, Any]:
    base = Path(root).resolve()
    files = iter_release_files(base, excluded_paths=GENERATED_METADATA)
    return {
        "schema_version": "urp.package.v2",
        "package": "urp",
        "status": "local-ideal implementation",
        "generated_at": utc_now(),
        "active_file_count": len(files),
        "canonical_layout": {
            "python": "python/urp",
            "rust": ["crates/urp-core", "crates/urp-chunker", "crates/urp-gateway-s3"],
            "go": "go",
            "typescript": "typescript",
            "services": "services",
            "plugins": "plugins",
            "specs": "specs",
            "deployments": "deployments",
            "tests": "tests",
            "archived_sources": "archive/source_packages",
        },
        "core_model": [
            "WorkUnit",
            "Contract",
            "Plan",
            "PlanAction",
            "Manifest",
            "LedgerEvent",
            "PolicyDecision",
            "VerificationResult",
        ],
        "default_safety": {
            "unknown_data": "exact_bytes",
            "cross_tenant_cache": "disabled",
            "cross_tenant_dedupe": "disabled",
            "semantic_and_lossy_reducers": "policy_and_verifier_gated",
            "deletion": "denied",
            "authentication": "required",
        },
        "public_surfaces": ["CLI", "REST/OpenAPI", "protobuf", "Python", "TypeScript", "Go", "Rust"],
        "platform_targets": [
            "local",
            "kubernetes",
            "aws",
            "azure",
            "gcp",
            "on_prem",
            "edge",
            "openai_compatible",
            "cicd",
        ],
        "verification_commands": {
            "python": "python3 -m pytest -q && python3 -m ruff check python tests",
            "typescript": "npm test --prefix typescript && npm pack --dry-run --prefix typescript",
            "go": "cd go && go test -race ./...",
            "rust": "cargo fmt --all -- --check && cargo clippy --workspace --all-targets -- -D warnings && cargo test --workspace",
            "readiness": "python3 -m urp.cli admin readiness",
            "platforms": "python3 -m urp.cli platform validate --target all",
            "release": "python3 -m urp.cli release verify --manifest PACKAGE_SHA256.json",
        },
        "evidence": ["TEST_RESULTS.md", "QUALITY_REPORT.md", "docs/WHITE_PAPER.md", "examples/live/run_live_examples.py"],
    }


def build_line_count_manifest(root: str | Path = ".") -> Dict[str, Any]:
    base = Path(root).resolve()
    counts: Dict[str, int] = {}
    for path in iter_release_files(base, excluded_paths=GENERATED_METADATA):
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        counts[path.relative_to(base).as_posix()] = len(text.splitlines())
    return {
        "schema_version": "urp.line-count.v2",
        "arbitrary_line_count_target": False,
        "generated_at": utc_now(),
        "file_count": len(counts),
        "total_lines": sum(counts.values()),
        "line_counts": dict(sorted(counts.items())),
    }


def write_package_metadata(root: str | Path = ".") -> Dict[str, Any]:
    base = Path(root).resolve()
    package = build_package_manifest(base)
    lines = build_line_count_manifest(base)
    atomic_write_json(base / "package_manifest.json", package)
    atomic_write_json(base / "line_count_manifest.json", lines)
    return {
        "package_manifest": str(base / "package_manifest.json"),
        "line_count_manifest": str(base / "line_count_manifest.json"),
        "active_file_count": package["active_file_count"],
        "text_file_count": lines["file_count"],
        "total_lines": lines["total_lines"],
    }
