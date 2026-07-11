"""FastAPI control-plane and gateway application.

This module avoids importing FastAPI at package import time so the reference
tests can run with only the Python standard library.
"""

from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

from .ai_router import RouteFeedbackStore
from .ai_gateway import handle_chat_completion, handle_completion, handle_embeddings, list_models, lookup_semantic_cache
from .approval_store import ApprovalStore
from .auth import (
    APIKeyAuthenticator,
    LocalAuthorizer,
    action_for_request,
    bearer_token,
    current_principal,
    current_tenant,
    principal_context,
)
from .cache import CacheEntry, URPCache
from .cache_verification import verify_cache_value
from .conformance import ai_gateway_conformance
from .contracts import Contract, LedgerEvent, WorkUnit, WorkUnitKind
from .disaster_recovery import export_state, import_state
from .errors import URPError, manifest_not_found, verifier_failed, work_unit_not_found
from .encoding import decode_json_value, json_safe_work_unit
from .executor import execute_work_unit, rehydrate_manifest, rehydrate_manifest_range
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
from .adapters import LocalS3Adapter, built_in_adapters
from .benchmarks import run_benchmark_suite
from .policy import evaluate_policy, validate_policy_bundle
from .policy_store import PolicyBundleStore, resolve_active_policy_bundle
from .production import production_readiness_check
from .reports import dashboard_report, savings_report
from .scheduler import FlexibleJob, SchedulerStore
from .schema_validation import SchemaValidationError, validate_named_schema
from .structured_logs import default_log_store
from .tracing import default_trace_store
from .work_unit_store import default_work_unit_store


def create_app(state_dir: str = ".urp", authenticator: APIKeyAuthenticator | None = None):
    try:
        from fastapi import FastAPI
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Install urp[api] to run the FastAPI application") from exc

    app = FastAPI(title="Universal Reduction Plane")
    authorizer = LocalAuthorizer()
    authenticator = authenticator or APIKeyAuthenticator.from_env()
    if not authenticator.configured:
        raise RuntimeError("configure URP_LOCAL_API_KEY or URP_API_KEYS_JSON, or explicitly set URP_AUTH_MODE=disabled")
    app.state.authenticator = authenticator

    @app.middleware("http")
    async def authentication_middleware(request, call_next):
        from fastapi.responses import JSONResponse

        if request.url.path in {"/healthz", "/readyz"}:
            return await call_next(request)
        if request.url.path == "/metrics" or request.url.path.startswith("/v1/"):
            try:
                maximum = int(os.environ.get("URP_MAX_REQUEST_BYTES", str(16 * 1024 * 1024)))
                length = int(request.headers.get("content-length", "0") or "0")
                if length > maximum:
                    raise URPError("request_too_large", f"request exceeds {maximum} bytes", retryable=False)
                token = bearer_token(request.headers.get("authorization"), request.headers.get("x-api-key"))
                principal = authenticator.authenticate(token)
                tenant = request.query_params.get("tenant") or request.headers.get("x-urp-tenant")
                if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
                    raw = await request.body()
                    if len(raw) > maximum:
                        raise URPError("request_too_large", f"request exceeds {maximum} bytes", retryable=False)
                    if raw:
                        try:
                            body = json.loads(raw)
                        except (TypeError, json.JSONDecodeError):
                            body = {}
                        if isinstance(body, dict):
                            urp = body.get("urp") if isinstance(body.get("urp"), dict) else {}
                            tenant = body.get("tenant") or urp.get("tenant") or tenant
                authorizer.require(principal, action_for_request(request.method, request.url.path), str(tenant) if tenant else None)
                request.state.principal = principal
                with principal_context(principal):
                    return await call_next(request)
            except URPError as exc:
                status = 401 if exc.code == "authentication_required" else 403
                if exc.code == "request_too_large":
                    status = 413
                headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
                return JSONResponse(exc.to_dict(), status_code=status, headers=headers)
        return await call_next(request)

    @app.middleware("http")
    async def security_headers_middleware(request, call_next):
        response = await call_next(request)
        response.headers.setdefault("x-content-type-options", "nosniff")
        response.headers.setdefault("cache-control", "no-store")
        return response

    @app.exception_handler(URPError)
    def urp_error_handler(request, exc: URPError):  # pragma: no cover - requires FastAPI runtime
        from fastapi.responses import JSONResponse

        status = 403 if exc.code in {"authorization_denied", "policy_denied", "tenant_mismatch"} else 400
        if exc.code == "authentication_required":
            status = 401
        if exc.code in {"manifest_not_found", "work_unit_not_found", "plan_not_found"}:
            status = 404
        headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
        return JSONResponse(exc.to_dict(), status_code=status, headers=headers)

    @app.exception_handler(SchemaValidationError)
    def schema_validation_error_handler(request, exc: SchemaValidationError):  # pragma: no cover - requires FastAPI runtime
        from fastapi.responses import JSONResponse

        return JSONResponse(
            {"error": {"code": "schema_validation_failed", "message": str(exc), "retryable": False, "details": {}}},
            status_code=400,
        )

    @app.exception_handler(FileNotFoundError)
    def file_not_found_error_handler(request, exc: FileNotFoundError):  # pragma: no cover - requires FastAPI runtime
        from fastapi.responses import JSONResponse

        missing = str(exc.filename or exc)
        return JSONResponse(
            {"error": {"code": "not_found", "message": f"resource not found: {missing}", "retryable": False, "details": {"path": missing}}},
            status_code=404,
        )

    @app.exception_handler(ValueError)
    def value_error_handler(request, exc: ValueError):  # pragma: no cover - requires FastAPI runtime
        from fastapi.responses import JSONResponse

        return JSONResponse(
            {"error": {"code": "invalid_request", "message": str(exc), "retryable": False, "details": {}}},
            status_code=400,
        )

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/readyz")
    def readyz():
        from fastapi.responses import JSONResponse

        result = dependency_readiness(state_dir)
        return JSONResponse(result, status_code=200 if result["ok"] else 503)

    @app.get("/metrics")
    def metrics():
        from fastapi.responses import PlainTextResponse

        return PlainTextResponse(GLOBAL_METRICS.prometheus())

    @app.post("/v1/work-units")
    def create_work_unit(payload: dict):
        wu = _work_unit_from_payload(payload)
        default_work_unit_store(state_dir).put(wu)
        default_ledger(state_dir).append(LedgerEvent("work_unit.created", wu.tenant, wu.id, trace_id=wu.trace_id))
        return {"work_unit_id": wu.id, "trace_id": wu.trace_id, "state": "received"}

    @app.get("/v1/work-units")
    def list_work_units(tenant: str | None = None):
        return [json_safe_work_unit(wu) for wu in default_work_unit_store(state_dir).list(tenant)]

    @app.get("/v1/work-units/{work_unit_id}")
    def get_work_unit(work_unit_id: str):
        try:
            return json_safe_work_unit(default_work_unit_store(state_dir).get(work_unit_id))
        except KeyError:
            raise work_unit_not_found(work_unit_id)

    @app.post("/v1/work-units/{work_unit_id}/plan")
    def plan_stored(work_unit_id: str):
        try:
            wu = default_work_unit_store(state_dir).get(work_unit_id)
        except KeyError:
            raise work_unit_not_found(work_unit_id)
        bundle = _active_policy_for_work_unit(state_dir, wu)
        plan = plan_work_unit(wu, policy_bundle=bundle)
        store_plan_with_audit(state_dir, plan, wu, actor="api")
        return plan.to_dict()

    @app.post("/v1/work-units/{work_unit_id}/execute")
    def execute_stored(work_unit_id: str, payload: dict | None = None):
        try:
            wu = default_work_unit_store(state_dir).get(work_unit_id)
        except KeyError:
            raise work_unit_not_found(work_unit_id)
        return execute_work_unit(wu, state_dir, mode=(payload or {}).get("mode")).to_dict()

    @app.post("/v1/work-units/plan")
    def plan(payload: dict):
        wu = _work_unit_from_payload(payload)
        bundle = _active_policy_for_work_unit(state_dir, wu)
        row = plan_work_unit(wu, mode=payload.get("mode", "observe"), policy_bundle=bundle)
        store_plan_with_audit(state_dir, row, wu, actor="api")
        return row.to_dict()

    @app.post("/v1/plans")
    def create_plan(payload: dict):
        wu = _work_unit_from_payload(payload)
        bundle = _active_policy_for_work_unit(state_dir, wu)
        row = plan_work_unit(wu, mode=payload.get("mode", "observe"), policy_bundle=bundle)
        store_plan_with_audit(state_dir, row, wu, actor="api")
        return row.to_dict()

    @app.get("/v1/plans")
    def list_plans(work_unit_id: str | None = None):
        return [row.to_dict() for row in default_plan_store(state_dir).list(work_unit_id)]

    @app.get("/v1/plans/{plan_id}")
    def get_plan(plan_id: str):
        try:
            return default_plan_store(state_dir).get(plan_id).to_dict()
        except KeyError:
            raise URPError("plan_not_found", f"plan not found: {plan_id}", details={"plan_id": plan_id})

    @app.post("/v1/work-units/execute")
    def execute(payload: dict):
        wu = _work_unit_from_payload(payload)
        return execute_work_unit(wu, state_dir, mode=payload.get("mode")).to_dict()

    @app.get("/v1/manifests")
    def list_manifests(logical_ref: str | None = None, tenant: str | None = None, redacted: bool = False):
        store = default_manifest_store(state_dir)
        rows = store.find_by_logical_ref(logical_ref) if logical_ref else store.list()
        if tenant:
            rows = [row for row in rows if row.tenant == tenant]
        return [redact_manifest(row) if _manifest_redaction_required(authorizer, row.tenant, redacted) else row.to_dict() for row in rows]

    @app.get("/v1/manifests/explore")
    def explore_manifests(tenant: str | None = None, kind: str | None = None, contract: str | None = None, state: str | None = None, limit: int | None = None, redacted: bool = True):
        effective_redaction = _manifest_redaction_required(authorizer, tenant, redacted)
        return manifest_explorer_report(state_dir, tenant=tenant, kind=kind, contract=contract, state=state, limit=limit, redacted=effective_redaction)

    @app.get("/v1/manifests/{manifest_id}")
    def get_manifest(manifest_id: str):
        try:
            manifest = default_manifest_store(state_dir).get(manifest_id)
            return redact_manifest(manifest) if _manifest_redaction_required(authorizer, manifest.tenant, False) else manifest.to_dict()
        except KeyError:
            raise manifest_not_found(manifest_id)

    @app.post("/v1/manifests/export")
    def export_manifests(payload: dict):
        store = default_manifest_store(state_dir)
        rows = store.find_by_logical_ref(payload["logical_ref"]) if payload.get("logical_ref") else store.list()
        if payload.get("tenant"):
            rows = [row for row in rows if row.tenant == payload["tenant"]]
        requested_redaction = payload.get("redacted", True) is not False
        manifests = [
            redact_manifest(row) if _manifest_redaction_required(authorizer, row.tenant, requested_redaction) else row.to_dict()
            for row in rows
        ]
        effective_redaction = requested_redaction or any(
            _manifest_redaction_required(authorizer, row.tenant, False) for row in rows
        )
        return {"manifest_count": len(manifests), "redacted": effective_redaction, "manifests": manifests}

    @app.post("/v1/manifests/{manifest_id}/rehydrate")
    def rehydrate(manifest_id: str, payload: dict | None = None):
        from fastapi.responses import Response

        range_request = (payload or {}).get("range") or {}
        if range_request:
            data = rehydrate_manifest_range(manifest_id, int(range_request["start"]), int(range_request["end"]), state_dir)
        else:
            data = rehydrate_manifest(manifest_id, state_dir)
        return Response(content=data, media_type="application/octet-stream")

    @app.post("/v1/ledger/query")
    def ledger_query(payload: dict):
        return [e.to_dict() for e in default_ledger(state_dir).query(tenant=payload.get("tenant"), work_unit_id=payload.get("work_unit_id"), manifest_id=payload.get("manifest_id"), event_types=payload.get("event_types"), limit=payload.get("limit"))]

    @app.get("/v1/ledger/stream")
    def ledger_stream(tenant: str | None = None, work_unit_id: str | None = None, manifest_id: str | None = None, event_types: str | None = None, limit: int | None = None):
        from fastapi.responses import StreamingResponse

        events = _event_types_from_query(event_types)

        def rows():
            for event in default_ledger(state_dir).query(tenant=tenant, work_unit_id=work_unit_id, manifest_id=manifest_id, event_types=events, limit=limit):
                yield f"data: {json.dumps(event.to_dict(), sort_keys=True)}\n\n"

        return StreamingResponse(rows(), media_type="text/event-stream")

    @app.get("/v1/reports/savings")
    def report_savings(tenant: str | None = None):
        return savings_report(state_dir, tenant)

    @app.get("/v1/reports/dashboard")
    def report_dashboard(tenant: str | None = None):
        return dashboard_report(state_dir, tenant)

    @app.get("/v1/routes/feedback")
    def route_feedback():
        return RouteFeedbackStore(state_dir).summary()

    @app.post("/v1/benchmarks/run")
    def benchmark_run(payload: dict):
        return run_benchmark_suite(payload["suite"], state_dir)

    @app.post("/v1/scheduler/submit")
    def scheduler_submit(payload: dict):
        job = FlexibleJob(
            tenant=payload.get("tenant", "local"),
            kind=payload.get("kind", "batch_compute_job"),
            deadline_seconds=payload.get("deadline_seconds"),
            estimated_runtime_seconds=int(payload.get("estimated_runtime_seconds", 0)),
            carbon_signal=payload.get("carbon_signal"),
            preferred_region=payload.get("preferred_region", "local"),
            policy_context=payload.get("policy_context", {}),
        )
        return SchedulerStore(state_dir).submit(job).to_dict()

    @app.get("/v1/scheduler/jobs")
    def scheduler_jobs():
        return SchedulerStore(state_dir).read()

    @app.post("/v1/traces/query")
    def traces_query(payload: dict):
        return [span.to_dict() for span in default_trace_store(state_dir).query(trace_id=payload.get("trace_id"), name=payload.get("name"))]

    @app.post("/v1/logs/query")
    def logs_query(payload: dict):
        return [
            row.to_dict()
            for row in default_log_store(state_dir).query(
                tenant=payload.get("tenant"),
                work_unit_id=payload.get("work_unit_id"),
                manifest_id=payload.get("manifest_id"),
                event_types=payload.get("event_types"),
                trace_id=payload.get("trace_id"),
                severity=payload.get("severity"),
                error_code=payload.get("error_code"),
                limit=payload.get("limit"),
            )
        ]

    @app.post("/v1/auth/check")
    def auth_check(payload: dict):
        principal = current_principal()
        if principal is None:
            raise URPError("authentication_required", "authentication is required")
        tenant = payload.get("tenant") or (None if principal.tenant == "*" else principal.tenant)
        authorizer.require(principal, payload.get("action", "auth:self"), tenant)
        return {"allowed": True, "actor": principal.actor, "tenant": principal.tenant, "roles": sorted(principal.roles)}

    @app.post("/v1/policies/evaluate")
    def policy_evaluate(payload: dict):
        wu = _work_unit_from_payload(payload)
        return evaluate_policy(wu, _active_policy_for_work_unit(state_dir, wu)).to_dict()

    @app.post("/v1/policies/validate")
    def policy_validate(payload: dict):
        validate_policy_bundle(payload)
        return {"valid": True}

    @app.post("/v1/policies/bundles")
    def policy_publish(payload: dict):
        return PolicyBundleStore(state_dir).publish(payload["bundle"], _actor())

    @app.get("/v1/policies/bundles")
    def policy_list():
        return PolicyBundleStore(state_dir).list()

    @app.post("/v1/policies/bundles/{name}/rollback")
    def policy_rollback(name: str, payload: dict):
        return PolicyBundleStore(state_dir).rollback(name, payload["version"], _actor())

    @app.post("/v1/policies/bundles/{name}/reload")
    def policy_reload(name: str, payload: dict | None = None):
        return PolicyBundleStore(state_dir).reload(name, _actor())

    @app.post("/v1/approvals")
    def issue_approval(payload: dict):
        tenant = str(payload.get("tenant") or current_tenant() or "")
        if not tenant:
            raise ValueError("tenant is required for an approval")
        record = ApprovalStore(state_dir).issue(
            tenant=tenant,
            actor=_actor(),
            contract=payload["contract"],
            policy_bundle_id=str(payload["policy_bundle_id"]),
            reason=str(payload.get("reason") or ""),
            work_unit_id=payload.get("work_unit_id"),
            ttl_seconds=int(payload.get("ttl_seconds", 900)),
        )
        default_ledger(state_dir).append(
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
        return record.to_dict()

    @app.get("/v1/approvals")
    def list_approvals(tenant: str | None = None):
        return [record.to_dict() for record in ApprovalStore(state_dir).list(tenant or current_tenant())]

    @app.get("/v1/approvals/{approval_id}")
    def get_approval(approval_id: str):
        record = ApprovalStore(state_dir).get(approval_id)
        principal_tenant = current_tenant()
        if principal_tenant and record.tenant != principal_tenant:
            from .errors import tenant_mismatch

            raise tenant_mismatch(principal_tenant, record.tenant)
        return record.to_dict()

    @app.post("/v1/plugins/register")
    def plugin_register(payload: dict):
        return PluginRegistry(state_dir).register(payload["descriptor"], _actor())

    @app.get("/v1/plugins")
    def plugin_list():
        return PluginRegistry(state_dir).list()

    @app.get("/v1/adapters/conformance")
    def adapters_conformance():
        return [adapter_conformance(name, adapter).to_dict() for name, adapter in built_in_adapters().items()]

    @app.get("/v1/conformance/ai")
    def ai_conformance():
        return ai_gateway_conformance(state_dir).to_dict()

    @app.post("/v1/kms/keys")
    def kms_create(payload: dict):
        return LocalKMS(state_dir).create_key(payload.get("purpose", "local-dev")).to_dict()

    @app.post("/v1/admin/backup")
    def backup(payload: dict):
        return export_state(state_dir, payload["output"])

    @app.post("/v1/admin/restore")
    def restore(payload: dict):
        return import_state(payload["archive"], state_dir, payload.get("replace", False))

    @app.get("/v1/admin/readiness")
    def readiness():
        return production_readiness_check(state_dir).to_dict()

    @app.get("/v1/platforms")
    def platforms():
        return [profile.to_dict() for profile in built_in_platform_profiles().values()]

    @app.get("/v1/platforms/readiness")
    def platforms_readiness(target: str = "all", require_live: bool = False):
        result = platform_readiness(target, require_live=require_live)
        if isinstance(result, list):
            return [row.to_dict() for row in result]
        return result.to_dict()

    @app.get("/v1/platforms/matrix")
    def platforms_matrix():
        return platform_matrix()

    cache = URPCache(Path(state_dir) / "cache" / "cache.sqlite3")

    @app.post("/v1/cache/exact/lookup")
    def cache_lookup(payload: dict):
        value = cache.get(payload["key"], payload["tenant"], payload.get("namespace", "default"), set(payload.get("source_fingerprints", [])))
        return {"hit": value is not None, "value": value}

    @app.post("/v1/cache/semantic/lookup")
    def semantic_cache_lookup(payload: dict):
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
        decision = evaluate_policy(wu, _active_policy_for_work_unit(state_dir, wu))
        if "semantic_cache_lookup" not in decision.allowed_actions:
            return {"hit": False, "allowed": False, "decision": decision.to_dict()}
        value = lookup_semantic_cache(
            payload["tenant"],
            payload.get("namespace", "default"),
            payload.get("text", ""),
            set(payload.get("source_fingerprints", [])),
            payload.get("task_type", "general"),
            state_dir,
        )
        return {"hit": value is not None, "allowed": True, "value": value}

    @app.post("/v1/cache/store")
    def cache_store(payload: dict):
        verification = verify_cache_value(payload.get("value"), payload.get("verification"))
        if not verification.accepted:
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
        return {"stored": True, "verification": verification.to_dict()}

    @app.post("/v1/s3/objects")
    def s3_put(payload: dict):
        adapter = LocalS3Adapter(state_dir, tenant=_payload_tenant(payload))
        return adapter.put_object(
            payload["bucket"],
            payload["key"],
            _body_from_payload(payload),
            payload.get("namespace", "s3"),
            payload.get("metadata"),
            payload.get("tags"),
        )

    @app.post("/v1/s3/objects/head")
    def s3_head(payload: dict):
        return LocalS3Adapter(state_dir, tenant=_payload_tenant(payload)).head_object(payload["manifest_id"])

    @app.post("/v1/s3/objects/get")
    def s3_get(payload: dict):
        from fastapi.responses import Response

        data = LocalS3Adapter(state_dir, tenant=_payload_tenant(payload)).get_object(payload["manifest_id"])
        return Response(content=data, media_type="application/octet-stream", headers={"x-urp-bytes": str(len(data))})

    @app.post("/v1/s3/objects/range")
    def s3_range(payload: dict):
        from fastapi.responses import Response

        data = LocalS3Adapter(state_dir, tenant=_payload_tenant(payload)).range_read(payload["manifest_id"], int(payload["start"]), int(payload["end"]))
        return Response(content=data, media_type="application/octet-stream", headers={"x-urp-bytes": str(len(data))})

    @app.post("/v1/s3/objects/list")
    def s3_list(payload: dict):
        return LocalS3Adapter(state_dir, tenant=_payload_tenant(payload)).list_objects(
            payload.get("bucket"),
            payload.get("prefix", ""),
            payload.get("include_tombstoned") is True,
        )

    @app.post("/v1/s3/objects/delete")
    def s3_delete(payload: dict):
        return LocalS3Adapter(state_dir, tenant=_payload_tenant(payload)).delete_object(
            payload["manifest_id"],
            _actor(),
            payload.get("allow_delete") is True,
        )

    @app.post("/v1/s3/multipart/create")
    def s3_multipart_create(payload: dict):
        adapter = LocalS3Adapter(state_dir, tenant=_payload_tenant(payload))
        return adapter.create_multipart_upload(
            payload["bucket"],
            payload["key"],
            payload.get("namespace", "s3"),
            payload.get("metadata"),
            payload.get("tags"),
        )

    @app.post("/v1/s3/multipart/part")
    def s3_multipart_part(payload: dict):
        adapter = LocalS3Adapter(state_dir, tenant=_payload_tenant(payload))
        return adapter.upload_part(payload["upload_id"], int(payload["part_number"]), _body_from_payload(payload))

    @app.post("/v1/s3/multipart/complete")
    def s3_multipart_complete(payload: dict):
        return LocalS3Adapter(state_dir, tenant=_payload_tenant(payload)).complete_multipart_upload(payload["upload_id"])

    @app.post("/v1/s3/multipart/abort")
    def s3_multipart_abort(payload: dict):
        return LocalS3Adapter(state_dir, tenant=_payload_tenant(payload)).abort_multipart_upload(payload["upload_id"])

    @app.post("/v1/chat/completions")
    def chat(payload: dict):
        urp = payload.get("urp", {})
        return handle_chat_completion(
            payload,
            tenant=urp.get("tenant") or current_tenant() or "local",
            namespace=urp.get("namespace", "default"),
            state_dir=state_dir,
            mode=urp.get("mode"),
        )

    @app.post("/v1/completions")
    def completions(payload: dict):
        urp = payload.get("urp", {})
        return handle_completion(
            payload,
            tenant=urp.get("tenant") or current_tenant() or "local",
            namespace=urp.get("namespace", "default"),
            state_dir=state_dir,
            mode=urp.get("mode"),
        )

    @app.post("/v1/embeddings")
    def embeddings(payload: dict):
        urp = payload.get("urp", {})
        return handle_embeddings(
            payload,
            tenant=urp.get("tenant") or current_tenant() or "local",
            namespace=urp.get("namespace", "default"),
            state_dir=state_dir,
            mode=urp.get("mode"),
        )

    @app.get("/v1/models")
    def models():
        return list_models()

    return app


def _work_unit_from_payload(payload: dict) -> WorkUnit:
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


def _body_from_payload(payload: dict) -> bytes:
    if "body_base64" in payload:
        return base64.b64decode(payload["body_base64"], validate=True)
    if "body_text" in payload:
        return str(payload["body_text"]).encode("utf-8")
    if "body" in payload:
        value = payload["body"]
        return value if isinstance(value, bytes) else str(value).encode("utf-8")
    return b""


def _bytes_payload(data: bytes) -> dict:
    row: dict = {"bytes": len(data), "body_base64": base64.b64encode(data).decode("ascii")}
    try:
        row["body_text"] = data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    return row


def _payload_tenant(payload: dict) -> str:
    return str(payload.get("tenant") or current_tenant() or "local")


def _manifest_redaction_required(
    authorizer: LocalAuthorizer,
    tenant: str | None,
    requested_redaction: bool,
) -> bool:
    if requested_redaction:
        return True
    principal = current_principal()
    return principal is None or not authorizer.allowed(principal, "manifest:sensitive", tenant)


def _event_types_from_query(event_types: str | None) -> list[str] | None:
    if not event_types:
        return None
    return [part.strip() for part in event_types.split(",") if part.strip()]


def _actor() -> str:
    principal = current_principal()
    return principal.actor if principal else "local-cli"


def _active_policy_for_work_unit(state_dir: str, work_unit: WorkUnit) -> dict | None:
    policy_name = work_unit.policy_context.get("policy_bundle_id") or work_unit.policy_context.get("policy_bundle")
    return resolve_active_policy_bundle(state_dir, str(policy_name) if policy_name else None)
