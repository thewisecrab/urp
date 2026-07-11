from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import parse_qs, urlparse

from .adapters import LocalS3Adapter, built_in_adapters
from .ai_gateway import handle_chat_completion, handle_completion, handle_embeddings, list_models, lookup_semantic_cache
from .ai_router import RouteFeedbackStore
from .approval_store import ApprovalStore
from .auth import (
    APIKeyAuthenticator,
    LocalAuthorizer,
    Principal,
    action_for_request,
    bearer_token,
    bind_principal,
    current_principal,
    current_tenant,
    reset_principal,
)
from .benchmarks import run_benchmark_suite
from .cache import CacheEntry, URPCache
from .cache_verification import verify_cache_value
from .conformance import ai_gateway_conformance
from .contracts import Contract, LedgerEvent, WorkUnit, WorkUnitKind
from .disaster_recovery import export_state, import_state
from .errors import URPError
from .encoding import decode_json_value, json_safe_work_unit
from .executor import execute_work_unit, init_state, rehydrate_manifest, rehydrate_manifest_range
from .health import dependency_readiness
from .kms import LocalKMS
from .ledger import default_ledger
from .manifest_explorer import manifest_explorer_report
from .manifest_store import default_manifest_store, redact_manifest
from .metrics import GLOBAL_METRICS
from .plan_store import default_plan_store, store_plan_with_audit
from .platforms import built_in_platform_profiles, platform_matrix, platform_readiness
from .planner import plan_work_unit
from .plugins import PluginRegistry, adapter_conformance
from .policy import evaluate_policy, validate_policy_bundle
from .policy_store import PolicyBundleStore, resolve_active_policy_bundle
from .production import production_readiness_check
from .reports import dashboard_report, savings_report
from .scheduler import FlexibleJob, SchedulerStore
from .schema_validation import SchemaValidationError, validate_named_schema
from .structured_logs import default_log_store
from .tracing import default_trace_store
from .work_unit_store import default_work_unit_store


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    role: str
    command: List[str]
    health_path: str
    endpoints: List[str]
    external_dependencies: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "role": self.role,
            "command": self.command,
            "health_path": self.health_path,
            "endpoints": self.endpoints,
            "external_dependencies": self.external_dependencies,
        }


def service_specs() -> Dict[str, ServiceSpec]:
    base = ["python3", "-m", "urp.cli", "service", "run", "--name"]
    return {
        "control-plane": ServiceSpec(
            "control-plane",
            "URP-native control API",
            [*base, "control-plane", "--listen", "127.0.0.1:8080"],
            "/healthz",
            [
                "/metrics",
                "/v1/work-units",
                "/v1/work-units/{id}",
                "/v1/work-units/plan",
                "/v1/work-units/execute",
                "/v1/work-units/{id}/plan",
                "/v1/work-units/{id}/execute",
                "/v1/plans",
                "/v1/plans/{id}",
                "/v1/manifests",
                "/v1/manifests/explore",
                "/v1/manifests/{id}",
                "/v1/manifests/export",
                "/v1/manifests/{id}/rehydrate",
                "/v1/ledger/query",
                "/v1/ledger/stream",
                "/v1/policies/evaluate",
                "/v1/policies/validate",
                "/v1/policies/bundles",
                "/v1/policies/bundles/{name}/rollback",
                "/v1/policies/bundles/{name}/reload",
                "/v1/approvals",
                "/v1/approvals/{id}",
                "/v1/plugins",
                "/v1/plugins/register",
                "/v1/kms/keys",
                "/v1/admin/backup",
                "/v1/admin/restore",
                "/v1/admin/readiness",
                "/v1/platforms",
                "/v1/platforms/readiness",
                "/v1/platforms/matrix",
                "/v1/cache/exact/lookup",
                "/v1/cache/semantic/lookup",
                "/v1/cache/store",
                "/v1/reports/savings",
                "/v1/reports/dashboard",
                "/v1/routes/feedback",
                "/v1/traces/query",
                "/v1/logs/query",
                "/v1/auth/check",
                "/v1/adapters/conformance",
                "/v1/conformance/ai",
                "/v1/benchmarks/run",
            ],
            [],
        ),
        "gateway-ai": ServiceSpec(
            "gateway-ai",
            "OpenAI-compatible mock AI gateway",
            [*base, "gateway-ai", "--listen", "127.0.0.1:8081"],
            "/healthz",
            ["/v1/chat/completions", "/v1/completions", "/v1/embeddings", "/v1/models"],
            [],
        ),
        "gateway-s3": ServiceSpec(
            "gateway-s3",
            "Local S3-compatible object facade",
            [*base, "gateway-s3", "--listen", "127.0.0.1:9000"],
            "/healthz",
            [
                "/v1/s3/objects",
                "/v1/s3/objects/head",
                "/v1/s3/objects/get",
                "/v1/s3/objects/range",
                "/v1/s3/objects/list",
                "/v1/s3/objects/delete",
                "/v1/s3/multipart/create",
                "/v1/s3/multipart/part",
                "/v1/s3/multipart/complete",
                "/v1/s3/multipart/abort",
            ],
            [],
        ),
        "worker": ServiceSpec(
            "worker",
            "Local work-unit executor",
            [*base, "worker", "--listen", "127.0.0.1:8082"],
            "/healthz",
            ["/v1/work-units/plan", "/v1/work-units/execute", "/v1/benchmarks/run"],
            [],
        ),
        "scheduler": ServiceSpec(
            "scheduler",
            "Local energy-aware scheduler",
            [*base, "scheduler", "--listen", "127.0.0.1:8083"],
            "/healthz",
            ["/v1/scheduler/submit", "/v1/scheduler/jobs"],
            [],
        ),
    }


def service_health(name: str, state_dir: str | Path = ".urp") -> Dict[str, object]:
    specs = service_specs()
    if name not in specs:
        raise KeyError(name)
    state = init_state(state_dir)
    return {
        "ok": True,
        "service": specs[name].to_dict(),
        "state_dir": str(state),
        "external_dependencies_required": False,
    }


def create_service_server(
    name: str,
    host: str,
    port: int,
    state_dir: str | Path = ".urp",
    authenticator: APIKeyAuthenticator | None = None,
    ai_provider: Any | None = None,
) -> HTTPServer:
    if name not in service_specs():
        raise KeyError(name)
    authenticator = authenticator or APIKeyAuthenticator.from_env()
    if not authenticator.configured:
        raise RuntimeError("configure URP_LOCAL_API_KEY or URP_API_KEYS_JSON, or explicitly set URP_AUTH_MODE=disabled")
    state = init_state(state_dir)
    cache = URPCache(state / "cache" / "cache.sqlite3")
    authorizer = LocalAuthorizer()

    class Handler(BaseHTTPRequestHandler):
        server_version = f"URPService/{name}"

        def log_message(self, fmt: str, *args: object) -> None:  # noqa: A003
            return

        def do_GET(self) -> None:  # noqa: N802
            context_token = None
            try:
                path, query = _path_and_query(self.path)
                principal = self._authenticate(path, "GET", query=query)
                context_token = bind_principal(principal)
                if path == "/healthz":
                    self._json(200, service_health(name, state))
                elif path == "/readyz":
                    readiness = dependency_readiness(state)
                    self._json(200 if readiness["ok"] else 503, {**readiness, "service": name})
                elif path == "/metrics":
                    self._plain(200, GLOBAL_METRICS.prometheus())
                elif name == "gateway-ai" and path == "/v1/models":
                    self._json(200, list_models())
                elif name == "scheduler" and path == "/v1/scheduler/jobs":
                    self._json(200, SchedulerStore(state).read())
                elif name == "control-plane" and path == "/v1/work-units":
                    tenant = _first(query, "tenant")
                    self._json(200, [json_safe_work_unit(row) for row in default_work_unit_store(state).list(tenant)])
                elif name == "control-plane" and path.startswith("/v1/work-units/"):
                    work_unit_id = path.rsplit("/", 1)[-1]
                    self._json(200, json_safe_work_unit(default_work_unit_store(state).get(work_unit_id)))
                elif name == "control-plane" and path == "/v1/plans":
                    self._json(200, [row.to_dict() for row in default_plan_store(state).list(_first(query, "work_unit_id"))])
                elif name == "control-plane" and path.startswith("/v1/plans/"):
                    plan_id = path.rsplit("/", 1)[-1]
                    self._json(200, default_plan_store(state).get(plan_id).to_dict())
                elif name == "control-plane" and path == "/v1/manifests":
                    store = default_manifest_store(state)
                    logical_ref = _first(query, "logical_ref")
                    tenant = _first(query, "tenant")
                    requested_redaction = _first(query, "redacted") == "true"
                    rows = store.find_by_logical_ref(logical_ref) if logical_ref else store.list()
                    if tenant:
                        rows = [row for row in rows if row.tenant == tenant]
                    self._json(
                        200,
                        [
                            redact_manifest(row)
                            if requested_redaction or not authorizer.allowed(principal, "manifest:sensitive", row.tenant)
                            else row.to_dict()
                            for row in rows
                        ],
                    )
                elif name == "control-plane" and path == "/v1/manifests/explore":
                    self._json(
                        200,
                        manifest_explorer_report(
                            state,
                            tenant=_first(query, "tenant"),
                            kind=_first(query, "kind"),
                            contract=_first(query, "contract"),
                            state=_first(query, "state"),
                            limit=_int_or_none(_first(query, "limit")),
                            redacted=(
                                _first(query, "redacted") != "false"
                                or not authorizer.allowed(principal, "manifest:sensitive", _first(query, "tenant"))
                            ),
                        ),
                    )
                elif name == "control-plane" and path.startswith("/v1/manifests/"):
                    manifest_id = path.rsplit("/", 1)[-1]
                    manifest = default_manifest_store(state).get(manifest_id)
                    payload = (
                        manifest.to_dict()
                        if authorizer.allowed(principal, "manifest:sensitive", manifest.tenant)
                        else redact_manifest(manifest)
                    )
                    self._json(200, payload)
                elif name == "control-plane" and path == "/v1/ledger/stream":
                    rows = default_ledger(state).query(
                        tenant=_first(query, "tenant"),
                        work_unit_id=_first(query, "work_unit_id"),
                        manifest_id=_first(query, "manifest_id"),
                        event_types=_event_types_from_query(_first(query, "event_types")),
                        limit=_int_or_none(_first(query, "limit")),
                    )
                    self._event_stream(rows)
                elif name == "control-plane" and path == "/v1/reports/savings":
                    self._json(200, savings_report(state, _first(query, "tenant")))
                elif name == "control-plane" and path == "/v1/reports/dashboard":
                    self._json(200, dashboard_report(state, _first(query, "tenant")))
                elif name == "control-plane" and path == "/v1/routes/feedback":
                    self._json(200, RouteFeedbackStore(state).summary())
                elif name == "control-plane" and path == "/v1/policies/bundles":
                    self._json(200, PolicyBundleStore(state).list())
                elif name == "control-plane" and path == "/v1/approvals":
                    self._json(200, [record.to_dict() for record in ApprovalStore(state).list(_first(query, "tenant") or current_tenant())])
                elif name == "control-plane" and path.startswith("/v1/approvals/"):
                    record = ApprovalStore(state).get(path.rsplit("/", 1)[-1])
                    principal_tenant = current_tenant()
                    if principal_tenant and record.tenant != principal_tenant:
                        from .errors import tenant_mismatch

                        raise tenant_mismatch(principal_tenant, record.tenant)
                    self._json(200, record.to_dict())
                elif name == "control-plane" and path == "/v1/plugins":
                    self._json(200, PluginRegistry(state).list())
                elif name == "control-plane" and path == "/v1/adapters/conformance":
                    rows = [adapter_conformance(adapter_name, adapter).to_dict() for adapter_name, adapter in built_in_adapters().items()]
                    self._json(200, rows)
                elif name == "control-plane" and path == "/v1/conformance/ai":
                    self._json(200, ai_gateway_conformance(state).to_dict())
                elif name == "control-plane" and path == "/v1/admin/readiness":
                    self._json(200, production_readiness_check(state).to_dict())
                elif name == "control-plane" and path == "/v1/platforms":
                    self._json(200, [profile.to_dict() for profile in built_in_platform_profiles().values()])
                elif name == "control-plane" and path == "/v1/platforms/readiness":
                    result = platform_readiness(_first(query, "target") or "all", require_live=_first(query, "require_live") == "true")
                    self._json(200, [row.to_dict() for row in result] if isinstance(result, list) else result.to_dict())
                elif name == "control-plane" and path == "/v1/platforms/matrix":
                    self._json(200, platform_matrix())
                else:
                    self._json(404, {"error": {"code": "not_found", "path": path}})
            except Exception as exc:  # pragma: no cover - defensive server boundary
                self._error(exc)
            finally:
                if context_token is not None:
                    reset_principal(context_token)

        def do_POST(self) -> None:  # noqa: N802
            context_token = None
            try:
                path, _ = _path_and_query(self.path)
                payload = self._payload()
                principal = self._authenticate(path, "POST", payload=payload)
                context_token = bind_principal(principal)
                if name == "control-plane" and path == "/v1/work-units":
                    wu = _work_unit_from_payload(payload)
                    default_work_unit_store(state).put(wu)
                    default_ledger(state).append(LedgerEvent("work_unit.created", wu.tenant, wu.id, trace_id=wu.trace_id))
                    self._json(200, {"work_unit_id": wu.id, "trace_id": wu.trace_id, "state": "received"})
                elif name in {"control-plane", "worker"} and path == "/v1/work-units/plan":
                    wu = _work_unit_from_payload(payload)
                    plan = plan_work_unit(wu, mode=payload.get("mode", "observe"), policy_bundle=_active_policy_for_work_unit(state, wu))
                    store_plan_with_audit(state, plan, wu, actor=_actor(name))
                    self._json(200, plan.to_dict())
                elif name == "control-plane" and path.startswith("/v1/work-units/") and path.endswith("/plan"):
                    work_unit_id = path.split("/")[-2]
                    wu = default_work_unit_store(state).get(work_unit_id)
                    plan = plan_work_unit(wu, mode=payload.get("mode", "observe"), policy_bundle=_active_policy_for_work_unit(state, wu))
                    store_plan_with_audit(state, plan, wu, actor=_actor(name))
                    self._json(200, plan.to_dict())
                elif name == "control-plane" and path == "/v1/plans":
                    wu = _work_unit_from_payload(payload)
                    plan = plan_work_unit(wu, mode=payload.get("mode", "observe"), policy_bundle=_active_policy_for_work_unit(state, wu))
                    store_plan_with_audit(state, plan, wu, actor=_actor(name))
                    self._json(200, plan.to_dict())
                elif name in {"control-plane", "worker"} and path == "/v1/work-units/execute":
                    wu = _work_unit_from_payload(payload)
                    self._json(200, execute_work_unit(wu, state, mode=payload.get("mode")).to_dict())
                elif name == "control-plane" and path.startswith("/v1/work-units/") and path.endswith("/execute"):
                    work_unit_id = path.split("/")[-2]
                    wu = default_work_unit_store(state).get(work_unit_id)
                    self._json(200, execute_work_unit(wu, state, mode=payload.get("mode")).to_dict())
                elif name == "control-plane" and path == "/v1/manifests/export":
                    store = default_manifest_store(state)
                    rows = store.find_by_logical_ref(payload["logical_ref"]) if payload.get("logical_ref") else store.list()
                    if payload.get("tenant"):
                        rows = [row for row in rows if row.tenant == payload["tenant"]]
                    requested_redaction = payload.get("redacted", True) is not False
                    redacted = requested_redaction or any(
                        not authorizer.allowed(principal, "manifest:sensitive", row.tenant) for row in rows
                    )
                    self._json(
                        200,
                        {
                            "manifest_count": len(rows),
                            "redacted": redacted,
                            "manifests": [
                                redact_manifest(row)
                                if requested_redaction or not authorizer.allowed(principal, "manifest:sensitive", row.tenant)
                                else row.to_dict()
                                for row in rows
                            ],
                        },
                    )
                elif name == "control-plane" and path.startswith("/v1/manifests/") and path.endswith("/rehydrate"):
                    manifest_id = path.split("/")[-2]
                    range_request = payload.get("range") or {}
                    if range_request:
                        data = rehydrate_manifest_range(manifest_id, int(range_request["start"]), int(range_request["end"]), state)
                    else:
                        data = rehydrate_manifest(manifest_id, state)
                    self._bytes(200, data)
                elif name == "control-plane" and path == "/v1/ledger/query":
                    rows = default_ledger(state).query(
                        tenant=payload.get("tenant"),
                        work_unit_id=payload.get("work_unit_id"),
                        manifest_id=payload.get("manifest_id"),
                        event_types=payload.get("event_types"),
                        limit=payload.get("limit"),
                    )
                    self._json(200, [row.to_dict() for row in rows])
                elif name == "control-plane" and path == "/v1/policies/evaluate":
                    wu = _work_unit_from_payload(payload)
                    self._json(200, evaluate_policy(wu, _active_policy_for_work_unit(state, wu)).to_dict())
                elif name == "control-plane" and path == "/v1/policies/validate":
                    validate_policy_bundle(payload)
                    self._json(200, {"valid": True, "policy_bundle_id": payload.get("metadata", {}).get("name", "policy_bundle")})
                elif name == "control-plane" and path == "/v1/policies/bundles":
                    bundle = payload.get("bundle", payload)
                    self._json(200, PolicyBundleStore(state).publish(bundle, _actor(name)))
                elif name == "control-plane" and path.startswith("/v1/policies/bundles/") and path.endswith("/rollback"):
                    bundle_name = path.split("/")[-2]
                    self._json(200, PolicyBundleStore(state).rollback(bundle_name, payload["version"], _actor(name)))
                elif name == "control-plane" and path.startswith("/v1/policies/bundles/") and path.endswith("/reload"):
                    bundle_name = path.split("/")[-2]
                    self._json(200, PolicyBundleStore(state).reload(bundle_name, _actor(name)))
                elif name == "control-plane" and path == "/v1/approvals":
                    tenant = str(payload.get("tenant") or current_tenant() or "")
                    if not tenant:
                        raise ValueError("tenant is required for an approval")
                    record = ApprovalStore(state).issue(
                        tenant=tenant,
                        actor=_actor(name),
                        contract=payload["contract"],
                        policy_bundle_id=str(payload["policy_bundle_id"]),
                        reason=str(payload.get("reason") or ""),
                        work_unit_id=payload.get("work_unit_id"),
                        ttl_seconds=int(payload.get("ttl_seconds", 900)),
                    )
                    default_ledger(state).append(
                        LedgerEvent(
                            "approval.issued",
                            tenant,
                            work_unit_id=record.work_unit_id,
                            policy_bundle_id=record.policy_bundle_id,
                            actor=record.actor,
                            decision=record.contract,
                            details={"approval_id": record.approval_id, "expires_at": record.expires_at, "reason": record.reason},
                        )
                    )
                    self._json(200, record.to_dict())
                elif name == "control-plane" and path == "/v1/plugins/register":
                    descriptor = payload.get("descriptor", payload)
                    self._json(200, PluginRegistry(state).register(descriptor, _actor(name)))
                elif name == "control-plane" and path == "/v1/kms/keys":
                    self._json(200, LocalKMS(state).create_key(payload.get("purpose", "local-dev")).to_dict())
                elif name == "control-plane" and path == "/v1/admin/backup":
                    self._json(200, export_state(state, payload["output"]))
                elif name == "control-plane" and path == "/v1/admin/restore":
                    self._json(200, import_state(payload["archive"], state, payload.get("replace", False)))
                elif name == "control-plane" and path == "/v1/cache/exact/lookup":
                    value = cache.get(payload["key"], payload["tenant"], payload.get("namespace", "default"), set(payload.get("source_fingerprints", [])))
                    self._json(200, {"hit": value is not None, "value": value})
                elif name == "control-plane" and path == "/v1/cache/store":
                    verification = verify_cache_value(payload.get("value"), payload.get("verification"))
                    if not verification.accepted:
                        from .errors import verifier_failed

                        raise verifier_failed("cache value verification failed", details=verification.to_dict())
                    ttl = float(payload.get("ttl_seconds", 3600))
                    if ttl <= 0 or ttl > 86400:
                        raise ValueError("ttl_seconds must be between 1 and 86400")
                    cache.put(
                        CacheEntry(
                            payload["key"],
                            payload["tenant"],
                            payload.get("namespace", "default"),
                            payload.get("value"),
                            set(payload.get("source_fingerprints", [])),
                            True,
                            time.time() + ttl,
                        )
                    )
                    self._json(200, {"stored": True, "verification": verification.to_dict()})
                elif name == "control-plane" and path == "/v1/cache/semantic/lookup":
                    policy_context = {
                        "allow_semantic_cache": payload.get("allow_semantic_cache") is True,
                        **({"policy_bundle_id": payload["policy_bundle_id"]} if payload.get("policy_bundle_id") else {}),
                    }
                    wu = WorkUnit(
                        WorkUnitKind.PROMPT_REQUEST,
                        payload["tenant"],
                        payload.get("logical_ref", "cache://semantic/lookup"),
                        requested_contract=Contract.SEMANTIC,
                        namespace=payload.get("namespace", "default"),
                        policy_context=policy_context,
                    )
                    decision = evaluate_policy(wu, _active_policy_for_work_unit(state, wu))
                    if "semantic_cache_lookup" not in decision.allowed_actions:
                        self._json(200, {"hit": False, "allowed": False, "decision": decision.to_dict()})
                    else:
                        value = lookup_semantic_cache(
                            payload["tenant"],
                            payload.get("namespace", "default"),
                            payload.get("text", ""),
                            set(payload.get("source_fingerprints", [])),
                            payload.get("task_type", "general"),
                            state,
                        )
                        self._json(200, {"hit": value is not None, "allowed": True, "value": value})
                elif name == "control-plane" and path == "/v1/traces/query":
                    rows = default_trace_store(state).query(trace_id=payload.get("trace_id"), name=payload.get("name"))
                    self._json(200, [row.to_dict() for row in rows])
                elif name == "control-plane" and path == "/v1/logs/query":
                    rows = default_log_store(state).query(
                        tenant=payload.get("tenant"),
                        work_unit_id=payload.get("work_unit_id"),
                        manifest_id=payload.get("manifest_id"),
                        event_types=payload.get("event_types"),
                        trace_id=payload.get("trace_id"),
                        severity=payload.get("severity"),
                        error_code=payload.get("error_code"),
                        limit=payload.get("limit"),
                    )
                    self._json(200, [row.to_dict() for row in rows])
                elif name == "control-plane" and path == "/v1/auth/check":
                    principal = current_principal()
                    if principal is None:
                        raise URPError("authentication_required", "authentication is required")
                    tenant = payload.get("tenant") or (None if principal.tenant == "*" else principal.tenant)
                    allowed = authorizer.allowed(principal, payload.get("action", "auth:self"), tenant)
                    self._json(200 if allowed else 403, {"allowed": allowed, "actor": principal.actor, "roles": sorted(principal.roles)})
                elif name in {"control-plane", "worker"} and path == "/v1/benchmarks/run":
                    self._json(200, run_benchmark_suite(payload["suite"], state))
                elif name == "gateway-ai" and path == "/v1/chat/completions":
                    urp = payload.get("urp", {})
                    self._json(200, handle_chat_completion(payload, tenant=urp.get("tenant") or current_tenant() or "local", namespace=urp.get("namespace", "default"), state_dir=state, provider=ai_provider, mode=urp.get("mode")))
                elif name == "gateway-ai" and path == "/v1/completions":
                    urp = payload.get("urp", {})
                    self._json(200, handle_completion(payload, tenant=urp.get("tenant") or current_tenant() or "local", namespace=urp.get("namespace", "default"), state_dir=state, provider=ai_provider, mode=urp.get("mode")))
                elif name == "gateway-ai" and path == "/v1/embeddings":
                    urp = payload.get("urp", {})
                    self._json(200, handle_embeddings(payload, tenant=urp.get("tenant") or current_tenant() or "local", namespace=urp.get("namespace", "default"), state_dir=state, mode=urp.get("mode")))
                elif name == "gateway-s3":
                    self._handle_s3(path, payload)
                elif name == "scheduler" and path == "/v1/scheduler/submit":
                    job = FlexibleJob(
                        tenant=payload.get("tenant", "local"),
                        kind=payload.get("kind", "batch_compute_job"),
                        deadline_seconds=payload.get("deadline_seconds"),
                        estimated_runtime_seconds=int(payload.get("estimated_runtime_seconds", 0)),
                        carbon_signal=payload.get("carbon_signal"),
                        preferred_region=payload.get("preferred_region", "local"),
                        policy_context=payload.get("policy_context", {}),
                    )
                    self._json(200, SchedulerStore(state).submit(job).to_dict())
                else:
                    self._json(404, {"error": {"code": "not_found", "path": path}})
            except Exception as exc:  # pragma: no cover - defensive server boundary
                self._error(exc)
            finally:
                if context_token is not None:
                    reset_principal(context_token)

        def _handle_s3(self, path: str, payload: Dict[str, Any]) -> None:
            adapter = LocalS3Adapter(state, tenant=_payload_tenant(payload))
            if path == "/v1/s3/objects":
                body = _body_from_payload(payload)
                self._json(
                    200,
                    adapter.put_object(
                        payload["bucket"],
                        payload["key"],
                        body,
                        payload.get("namespace", "s3"),
                        payload.get("metadata"),
                        payload.get("tags"),
                    ),
                )
            elif path == "/v1/s3/objects/head":
                self._json(200, adapter.head_object(payload["manifest_id"]))
            elif path == "/v1/s3/objects/range":
                data = adapter.range_read(payload["manifest_id"], int(payload["start"]), int(payload["end"]))
                self._bytes(200, data)
            elif path == "/v1/s3/objects/get":
                self._bytes(200, adapter.get_object(payload["manifest_id"]))
            elif path == "/v1/s3/objects/list":
                self._json(200, adapter.list_objects(payload.get("bucket"), payload.get("prefix", ""), payload.get("include_tombstoned") is True))
            elif path == "/v1/s3/objects/delete":
                self._json(200, adapter.delete_object(payload["manifest_id"], _actor(name), payload.get("allow_delete") is True))
            elif path == "/v1/s3/multipart/create":
                self._json(
                    200,
                    adapter.create_multipart_upload(
                        payload["bucket"],
                        payload["key"],
                        payload.get("namespace", "s3"),
                        payload.get("metadata"),
                        payload.get("tags"),
                    ),
                )
            elif path == "/v1/s3/multipart/part":
                self._json(200, adapter.upload_part(payload["upload_id"], int(payload["part_number"]), _body_from_payload(payload)))
            elif path == "/v1/s3/multipart/complete":
                self._json(200, adapter.complete_multipart_upload(payload["upload_id"]))
            elif path == "/v1/s3/multipart/abort":
                self._json(200, adapter.abort_multipart_upload(payload["upload_id"]))
            else:
                self._json(404, {"error": {"code": "not_found", "path": path}})

        def _payload(self) -> Dict[str, Any]:
            length = int(self.headers.get("content-length", "0"))
            maximum = int(os.environ.get("URP_MAX_REQUEST_BYTES", str(16 * 1024 * 1024)))
            if length < 0 or length > maximum:
                raise URPError("request_too_large", f"request exceeds {maximum} bytes", retryable=False)
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw or b"{}")

        def _authenticate(
            self,
            path: str,
            method: str,
            *,
            payload: Dict[str, Any] | None = None,
            query: Dict[str, List[str]] | None = None,
        ) -> Principal:
            if path in {"/healthz", "/readyz"}:
                return Principal("health-check", "*", set())
            token = bearer_token(self.headers.get("authorization"), self.headers.get("x-api-key"))
            principal = authenticator.authenticate(token)
            tenant: str | None = self.headers.get("x-urp-tenant")
            if query:
                tenant = _first(query, "tenant") or tenant
            if payload:
                urp = payload.get("urp") if isinstance(payload.get("urp"), dict) else {}
                tenant = payload.get("tenant") or urp.get("tenant") or tenant
            authorizer.require(principal, action_for_request(method, path), str(tenant) if tenant else None)
            return principal

        def _json(self, status: int, payload: Any) -> None:
            body = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.send_header("cache-control", "no-store")
            self.send_header("x-content-type-options", "nosniff")
            if status == 401:
                self.send_header("www-authenticate", "Bearer")
            self.end_headers()
            self.wfile.write(body)

        def _error(self, exc: Exception) -> None:
            status, payload = _error_response(exc)
            self._json(status, payload)

        def _plain(self, status: int, body: str) -> None:
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "text/plain; charset=utf-8")
            self.send_header("content-length", str(len(encoded)))
            self.send_header("cache-control", "no-store")
            self.send_header("x-content-type-options", "nosniff")
            self.end_headers()
            self.wfile.write(encoded)

        def _bytes(self, status: int, body: bytes) -> None:
            self.send_response(status)
            self.send_header("content-type", "application/octet-stream")
            self.send_header("content-length", str(len(body)))
            self.send_header("cache-control", "no-store")
            self.send_header("x-content-type-options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _event_stream(self, events: List[LedgerEvent]) -> None:
            body = "".join(f"data: {json.dumps(event.to_dict(), sort_keys=True)}\n\n" for event in events).encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "text/event-stream")
            self.send_header("cache-control", "no-cache")
            self.send_header("x-content-type-options", "nosniff")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server


def serve_service(name: str, listen: str = "127.0.0.1:8080", state_dir: str | Path = ".urp") -> None:
    host, port = parse_listen(listen)
    server = create_service_server(name, host, port, state_dir)
    print(f"URP {name} listening on http://{host}:{port}")
    server.serve_forever()


def parse_listen(listen: str) -> Tuple[str, int]:
    host, port_s = listen.rsplit(":", 1)
    return host, int(port_s)


def _error_response(exc: Exception) -> Tuple[int, Dict[str, Any]]:
    if isinstance(exc, URPError):
        status = 403 if exc.code in {"authorization_denied", "policy_denied", "tenant_mismatch"} else 400
        if exc.code == "authentication_required":
            status = 401
        if exc.code == "request_too_large":
            status = 413
        if exc.code in {"manifest_not_found", "work_unit_not_found", "plan_not_found"}:
            status = 404
        return status, exc.to_dict()
    if isinstance(exc, SchemaValidationError):
        return 400, {"error": {"code": "schema_validation_failed", "message": str(exc), "retryable": False, "details": {}}}
    if isinstance(exc, ValueError):
        return 400, {"error": {"code": "invalid_request", "message": str(exc), "retryable": False, "details": {}}}
    if isinstance(exc, KeyError):
        missing = str(exc).strip("'")
        return 404, {"error": {"code": "not_found", "message": f"resource not found: {missing}", "retryable": False, "details": {"id": missing}}}
    if isinstance(exc, FileNotFoundError):
        missing = str(exc.filename or exc)
        return 404, {"error": {"code": "not_found", "message": f"resource not found: {missing}", "retryable": False, "details": {"path": missing}}}
    return 500, {"error": {"code": "internal_error", "message": "internal service error", "retryable": False, "details": {}}}


def _work_unit_from_payload(payload: Dict[str, Any]) -> WorkUnit:
    work_unit = WorkUnit(
        kind=WorkUnitKind(payload["kind"]),
        tenant=payload["tenant"],
        logical_ref=payload["logical_ref"],
        payload=decode_json_value(payload.get("payload")),
        requested_contract=Contract(payload["requested_contract"]) if payload.get("requested_contract") else None,
        namespace=payload.get("namespace", "default"),
        metadata=payload.get("metadata", {}),
        policy_context=payload.get("policy_context", {}),
        payload_ref=payload.get("payload_ref"),
        effective_contract=Contract(payload["effective_contract"]) if payload.get("effective_contract") else None,
        deadline=payload.get("deadline"),
        latency_budget_ms=int(payload["latency_budget_ms"]) if payload.get("latency_budget_ms") is not None else None,
        quality_target=payload.get("quality_target", {}),
    )
    validate_named_schema("work_unit", json_safe_work_unit(work_unit))
    return work_unit


def _body_from_payload(payload: Dict[str, Any]) -> bytes:
    if "body_base64" in payload:
        return base64.b64decode(payload["body_base64"], validate=True)
    if "body_text" in payload:
        return str(payload["body_text"]).encode("utf-8")
    if "body" in payload:
        value = payload["body"]
        return value if isinstance(value, bytes) else str(value).encode("utf-8")
    return b""


def _bytes_payload(data: bytes) -> Dict[str, object]:
    row: Dict[str, object] = {"bytes": len(data), "body_base64": base64.b64encode(data).decode("ascii")}
    try:
        row["body_text"] = data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    return row


def _payload_tenant(payload: Dict[str, Any]) -> str:
    return str(payload.get("tenant") or current_tenant() or "local")


def _path_and_query(raw_path: str) -> Tuple[str, Dict[str, List[str]]]:
    parsed = urlparse(raw_path)
    return parsed.path, parse_qs(parsed.query)


def _first(query: Dict[str, List[str]], key: str) -> str | None:
    values = query.get(key)
    return values[0] if values else None


def _event_types_from_query(event_types: str | None) -> List[str] | None:
    if not event_types:
        return None
    return [part.strip() for part in event_types.split(",") if part.strip()]


def _int_or_none(value: str | None) -> int | None:
    return int(value) if value is not None else None


def _actor(default: str) -> str:
    principal = current_principal()
    return principal.actor if principal else default


def _active_policy_for_work_unit(state_dir: str | Path, work_unit: WorkUnit) -> Dict[str, Any] | None:
    policy_name = work_unit.policy_context.get("policy_bundle_id") or work_unit.policy_context.get("policy_bundle")
    return resolve_active_policy_bundle(state_dir, str(policy_name) if policy_name else None)
