from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml


@dataclass(frozen=True)
class SpecValidationResult:
    passed: bool
    checks: Dict[str, bool]
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {"passed": self.passed, "checks": self.checks, "details": self.details}


def validate_api_specs(repo_root: str | Path) -> SpecValidationResult:
    root = Path(repo_root)
    openapi_path = root / "specs/openapi.yaml"
    proto_path = root / "specs/urp.proto"
    openapi = yaml.safe_load(openapi_path.read_text(encoding="utf-8"))
    proto = proto_path.read_text(encoding="utf-8")
    refs = sorted(_openapi_refs(openapi))
    paths = openapi.get("paths", {}) if isinstance(openapi, dict) else {}
    operations = [
        operation
        for path_item in paths.values()
        if isinstance(path_item, dict)
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "patch", "delete"} and isinstance(operation, dict)
    ]
    services = re.findall(r"^service\s+(\w+)\s*\{", proto, flags=re.MULTILINE)
    rpcs = re.findall(r"^\s*rpc\s+(\w+)\s*\(([^)]+)\)\s+returns\s+\(([^)]+)\)", proto, flags=re.MULTILINE)
    serialized_openapi = openapi_path.read_text(encoding="utf-8")
    binary_paths = [
        "/v1/manifests/{id}/rehydrate",
        "/v1/s3/objects/get",
        "/v1/s3/objects/range",
    ]
    checks = {
        "openapi_version_declared": str(openapi.get("openapi", "")).startswith("3."),
        "openapi_paths_declared": bool(paths),
        "openapi_operations_have_responses": bool(operations) and all("responses" in operation for operation in operations),
        "openapi_schema_refs_exist": all((openapi_path.parent / ref.removeprefix("./")).exists() for ref in refs if ref.startswith("./")),
        "openapi_authentication_declared": _authentication_declared(openapi),
        "openapi_health_endpoints_are_public": all(
            paths.get(path, {}).get("get", {}).get("security") == [] for path in ("/healthz", "/readyz")
        ),
        "openapi_binary_responses_declared": all(_has_binary_response(paths.get(path, {})) for path in binary_paths),
        "openapi_cache_verification_is_server_side": (
            "verifier_passed" not in serialized_openapi
            and "verification" in openapi.get("components", {}).get("schemas", {}).get("CacheStoreRequest", {}).get("required", [])
        ),
        "openapi_approval_schema_is_closed_and_complete": _approval_schema_valid(openapi),
        "proto_syntax_declared": 'syntax = "proto3";' in proto,
        "proto_services_declared": len(services) >= 5,
        "proto_rpcs_are_typed": bool(rpcs) and all(request.strip() and response.strip() for _, request, response in rpcs),
        "proto_workunit_and_platform_services_exist": {"WorkUnitService", "PlatformService"}.issubset(set(services)),
        "proto_approval_service_exists": "ApprovalService" in services,
        "proto_workunit_extended_fields_exist": all(
            field in proto
            for field in ("payload_ref = 12", "effective_contract = 13", "deadline = 14", "latency_budget_ms = 15", "quality_target = 16")
        ),
        "proto_cache_verification_is_server_side": "verifier_passed" not in proto and "CacheVerification verification" in proto,
    }
    details = {
        "openapi_path_count": len(paths),
        "openapi_operation_count": len(operations),
        "openapi_refs": refs,
        "proto_services": services,
        "proto_rpc_count": len(rpcs),
    }
    return SpecValidationResult(all(checks.values()), checks, details)


def _openapi_refs(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str):
            refs.add(ref)
        for child in value.values():
            refs.update(_openapi_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.update(_openapi_refs(child))
    return refs


def _authentication_declared(openapi: Dict[str, Any]) -> bool:
    schemes = openapi.get("components", {}).get("securitySchemes", {})
    security = openapi.get("security", [])
    return (
        schemes.get("bearerAuth", {}).get("type") == "http"
        and schemes.get("apiKeyAuth", {}).get("type") == "apiKey"
        and {next(iter(item), "") for item in security if isinstance(item, dict)} >= {"bearerAuth", "apiKeyAuth"}
    )


def _has_binary_response(path_item: Dict[str, Any]) -> bool:
    operation = path_item.get("post", {})
    responses = operation.get("responses", {})
    success = responses.get("200", {})
    return "application/octet-stream" in success.get("content", {})


def _approval_schema_valid(openapi: Dict[str, Any]) -> bool:
    schema = openapi.get("components", {}).get("schemas", {}).get("Approval", {})
    required = set(schema.get("required", []))
    properties = set(schema.get("properties", {}))
    expected = {"approval_id", "tenant", "actor", "contract", "policy_bundle_id", "reason", "created_at", "expires_at", "signature"}
    return schema.get("additionalProperties") is False and expected <= required <= properties and "allOf" not in schema
