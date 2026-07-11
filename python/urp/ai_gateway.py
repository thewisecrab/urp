from __future__ import annotations

import json
import os
import time
import base64
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Protocol, Set
from urllib import error as urlerror
from urllib import request as urlrequest

from .ai_router import RouteFeedbackStore, route_model
from .approval_store import ApprovalStore
from .cache import CacheEntry, URPCache
from .context import approximate_tokens, compile_openai_messages
from .contracts import Contract, LedgerEvent, Manifest, WorkUnit, WorkUnitKind, stable_json_hash
from .config import execution_mode, require_execution_enabled
from .errors import policy_denied, verifier_failed
from .executor import init_state
from .ledger import default_ledger
from .manifest_store import default_manifest_store
from .metrics import GLOBAL_METRICS
from .plan_store import store_plan_with_audit
from .planner import plan_work_unit
from .policy import evaluate_policy
from .policy_store import resolve_active_policy_bundle
from .schema_validation import validate_named_schema
from .semantic_cache import SemanticCache
from .structured_logs import emit_log
from .tracing import emit_span
from .verifiers import VerificationResult, verify_embedding_vector, verify_non_empty_text


class ChatProvider(Protocol):
    def chat(self, request: Dict[str, Any], route: str) -> Dict[str, Any]:
        ...


class MockProvider:
    def chat(self, request: Dict[str, Any], route: str) -> Dict[str, Any]:
        user_text = _last_user_text(request.get("messages", []))
        content = f"[mock:{route}] {user_text}".strip()
        return {
            "id": "chatcmpl_mock",
            "object": "chat.completion",
            "model": route,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": approximate_tokens(str(request.get("messages", ""))),
                "completion_tokens": approximate_tokens(content),
                "total_tokens": approximate_tokens(str(request.get("messages", ""))) + approximate_tokens(content),
            },
        }


class OpenAICompatibleProvider:
    """Opt-in OpenAI-compatible HTTP provider.

    The local mock provider remains the default. This adapter is only used when
    explicitly constructed by CLI/tests or by embedding applications.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        timeout_seconds: float = 30.0,
        model_map: Mapping[str, str] | None = None,
        organization: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.model_map = dict(model_map or {})
        self.organization = organization

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "OpenAICompatibleProvider":
        current = dict(os.environ if env is None else env)
        base_url = current.get("OPENAI_BASE_URL") or current.get("URP_OPENAI_BASE_URL") or "https://api.openai.com"
        api_key = current.get("OPENAI_API_KEY") or current.get("URP_OPENAI_API_KEY")
        if not api_key and current.get("URP_AI_PROVIDER_NO_AUTH") != "1":
            raise ValueError("OPENAI_API_KEY is required for live OpenAI-compatible provider use")
        model_map = {
            "tiny": current.get("URP_AI_MODEL_TINY", current.get("URP_OPENAI_MODEL", "gpt-4o-mini")),
            "small": current.get("URP_AI_MODEL_SMALL", current.get("URP_OPENAI_MODEL", "gpt-4o-mini")),
            "medium": current.get("URP_AI_MODEL_MEDIUM", current.get("URP_OPENAI_MODEL", "gpt-4o-mini")),
            "frontier": current.get("URP_AI_MODEL_FRONTIER", current.get("URP_OPENAI_FRONTIER_MODEL", current.get("URP_OPENAI_MODEL", "gpt-4o"))),
            "auto": current.get("URP_OPENAI_MODEL", "gpt-4o-mini"),
        }
        return cls(
            base_url,
            api_key,
            timeout_seconds=float(current.get("URP_OPENAI_TIMEOUT_SECONDS", "30")),
            model_map=model_map,
            organization=current.get("OPENAI_ORGANIZATION"),
        )

    def chat(self, request: Dict[str, Any], route: str) -> Dict[str, Any]:
        payload = {key: value for key, value in request.items() if key != "urp"}
        payload["model"] = self._model_for(str(payload.get("model", "auto")), route)
        raw = json.dumps(payload).encode("utf-8")
        req = urlrequest.Request(
            self._chat_url(),
            data=raw,
            method="POST",
            headers={
                "content-type": "application/json",
                "accept": "application/json",
                **({"authorization": f"Bearer {self.api_key}"} if self.api_key else {}),
                **({"openai-organization": self.organization} if self.organization else {}),
            },
        )
        try:
            with urlrequest.urlopen(req, timeout=self.timeout_seconds) as response:  # noqa: S310 - opt-in user configured endpoint
                body = response.read()
        except urlerror.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI-compatible provider returned HTTP {exc.code}: {detail}") from exc
        except urlerror.URLError as exc:
            raise RuntimeError(f"OpenAI-compatible provider unavailable: {exc.reason}") from exc
        decoded = json.loads(body.decode("utf-8"))
        if "choices" not in decoded:
            raise RuntimeError("OpenAI-compatible provider response missing choices")
        decoded.setdefault("object", "chat.completion")
        decoded.setdefault("model", payload["model"])
        return decoded

    def _chat_url(self) -> str:
        if self.base_url.endswith("/v1"):
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/v1/chat/completions"

    def _model_for(self, requested: str, route: str) -> str:
        if requested and requested not in {"auto", "tiny", "small", "medium", "frontier"}:
            return requested
        return self.model_map.get(route) or self.model_map.get(requested) or route


def normalize_openai_request(request: Dict[str, Any]) -> Dict[str, Any]:
    if request.get("stream") is True:
        raise ValueError("streaming chat completions are not supported by the local gateway")
    if not isinstance(request.get("messages"), list) or not request.get("messages"):
        raise ValueError("messages must be a non-empty array")
    if request.get("urp") is not None and not isinstance(request.get("urp"), dict):
        raise ValueError("urp options must be an object")
    normalized = {key: value for key, value in request.items() if key not in {"stream_options"}}
    normalized["model"] = request.get("model", "auto")
    normalized["messages"] = [_normalize_message(message) for message in request.get("messages", [])]
    normalized.setdefault("temperature", 0)
    normalized.setdefault("tools", [])
    normalized["urp"] = dict(request.get("urp") or {})
    return normalized


def handle_chat_completion(
    request: Dict[str, Any],
    tenant: str = "local",
    namespace: str = "default",
    state_dir: str | Path = ".urp",
    provider: ChatProvider | None = None,
    cache: URPCache | None = None,
    semantic_cache: SemanticCache | None = None,
    policy_bundle: Dict[str, Any] | None = None,
    mode: str | None = None,
) -> Dict[str, Any]:
    mode = execution_mode(mode)
    require_execution_enabled()
    state = init_state(state_dir)
    provider = provider or MockProvider()
    cache = cache or URPCache(state / "cache" / "cache.sqlite3")
    semantic_cache = semantic_cache or SemanticCache(path=state / "cache" / "cache.sqlite3")
    normalized = normalize_openai_request(request)
    urp_options = dict(normalized.get("urp") or {})
    source_fingerprints = _source_fingerprints(normalized)
    allow_semantic_cache = urp_options.get("allow_semantic_cache") is True
    requested_contract = Contract(str(urp_options.get("contract", Contract.SEMANTIC.value)))
    routing_text = _last_user_text(normalized["messages"])
    work_unit = WorkUnit(
        kind=WorkUnitKind.PROMPT_REQUEST,
        tenant=tenant,
        namespace=namespace,
        logical_ref="openai://chat/completions",
        payload={
            "request_hash": stable_json_hash(normalized),
            "messages_count": len(normalized.get("messages", [])),
            "routing_text": routing_text,
        },
        requested_contract=requested_contract,
        metadata={"source_fingerprints": sorted(source_fingerprints)},
        policy_context={
            "allow_semantic_cache": allow_semantic_cache,
            **({"approval_id": urp_options["approval_id"]} if urp_options.get("approval_id") else {}),
        },
    )
    if policy_bundle is None:
        policy_bundle = resolve_active_policy_bundle(state, urp_options.get("policy_bundle_id"))
    policy = evaluate_policy(work_unit, policy_bundle)
    plan = plan_work_unit(work_unit, mode=mode, policy_bundle=policy_bundle, policy_decision=policy)
    _require_ai_approval(state, work_unit, policy)
    action_names = {action.type for action in plan.actions}
    ledger = default_ledger(state)
    ledger.append(LedgerEvent("work_unit.received", tenant, work_unit.id, policy_bundle_id=policy.policy_bundle_id, trace_id=work_unit.trace_id))
    ledger.append(LedgerEvent("policy.evaluated", tenant, work_unit.id, policy_bundle_id=policy.policy_bundle_id, decision=policy.contract.value, details=policy.to_dict(), trace_id=work_unit.trace_id))
    store_plan_with_audit(state, plan, work_unit)
    emit_log(
        state,
        "ai.gateway.request",
        "AI gateway request received",
        tenant=tenant,
        work_unit_id=work_unit.id,
        policy_bundle_id=policy.policy_bundle_id,
        trace_id=work_unit.trace_id,
        details={"request_hash": stable_json_hash(normalized), "message_count": len(normalized.get("messages", [])), "source_fingerprint_count": len(source_fingerprints)},
    )
    emit_span(state, "urp.intake", work_unit.trace_id, work_unit_id=work_unit.id, tenant=tenant, kind="prompt_request")
    max_context_tokens = int(urp_options.get("max_context_tokens", 4000))
    compiled, compiled_messages = compile_openai_messages(normalized["messages"], max_tokens=max_context_tokens)
    provider_request = dict(normalized)
    context_applied = mode == "enforce" and "context_compile" in action_names
    if context_applied:
        provider_request["messages"] = compiled_messages
    cache_key = cache.exact_key(tenant, namespace, normalized, source_fingerprints)
    requested_cache_ttl = _cache_ttl_seconds(urp_options)
    exact_cache_enabled = mode == "enforce" and requested_cache_ttl > 0 and "exact_cache_lookup" in action_names
    cached = cache.get(cache_key, tenant, namespace, source_fingerprints) if exact_cache_enabled else None
    if cached is not None and not _verify_chat_response(cached).accepted:
        cache.delete(cache_key)
        cached = None
    cache_result = "miss"
    provider_called = False
    fallback_used = False
    fallback_reason = ""
    route = route_model(work_unit, policy.model_allowlist, prompt_text=routing_text)
    semantic_hit_score: float | None = None
    verification: VerificationResult
    if cached is not None:
        response = cached
        verification = _verify_chat_response(response)
        cache_result = "exact_hit"
        ledger.append(LedgerEvent("cache.exact.hit", tenant, work_unit.id, policy_bundle_id=policy.policy_bundle_id, details={"cache_key": cache_key}, trace_id=work_unit.trace_id))
        emit_log(
            state,
            "cache.exact.hit",
            "exact cache hit",
            tenant=tenant,
            work_unit_id=work_unit.id,
            policy_bundle_id=policy.policy_bundle_id,
            trace_id=work_unit.trace_id,
            details={"cache_key": cache_key, "cache_type": "exact"},
        )
        emit_span(state, "urp.cache.lookup", work_unit.trace_id, work_unit_id=work_unit.id, cache_result=cache_result, cache_type="exact")
        GLOBAL_METRICS.inc("urp_cache_hits_total")
        GLOBAL_METRICS.inc("urp_ai_large_model_calls_avoided_total")
    else:
        semantic_hit = None
        semantic_cache_enabled = (
            mode == "enforce"
            and allow_semantic_cache
            and requested_cache_ttl > 0
            and policy.contract == Contract.SEMANTIC
            and "semantic_cache_lookup" in action_names
        )
        if semantic_cache_enabled:
            semantic_hit = semantic_cache.lookup_hit(
                tenant,
                namespace,
                routing_text,
                source_fingerprints,
                threshold=float(urp_options.get("semantic_cache_threshold", semantic_cache.threshold)),
                verifier=_verify_chat_response,
            )
        if semantic_hit is not None:
            response = semantic_hit.value
            verification = semantic_hit.verification
            semantic_hit_score = semantic_hit.score
            cache_result = "semantic_hit"
            ledger.append(
                LedgerEvent(
                    "ai.semantic_cache.accepted",
                    tenant,
                    work_unit.id,
                    policy_bundle_id=policy.policy_bundle_id,
                    details={"source_fingerprints_match": True, "score": semantic_hit.score, "cache_key": semantic_hit.key},
                    trace_id=work_unit.trace_id,
                )
            )
            emit_log(
                state,
                "ai.semantic_cache.accepted",
                "semantic cache accepted",
                tenant=tenant,
                work_unit_id=work_unit.id,
                policy_bundle_id=policy.policy_bundle_id,
                trace_id=work_unit.trace_id,
                details={"source_fingerprints_match": True},
            )
            emit_span(state, "urp.cache.lookup", work_unit.trace_id, work_unit_id=work_unit.id, cache_result=cache_result, cache_type="semantic")
            GLOBAL_METRICS.inc("urp_cache_hits_total")
            GLOBAL_METRICS.inc("urp_ai_large_model_calls_avoided_total")
        else:
            emit_span(state, "urp.ai.route", work_unit.trace_id, work_unit_id=work_unit.id, route=route.model, reason=route.reason)
            emit_log(
                state,
                "ai.model.routed",
                "AI model routed",
                tenant=tenant,
                work_unit_id=work_unit.id,
                policy_bundle_id=policy.policy_bundle_id,
                trace_id=work_unit.trace_id,
                details={"route": route.model, "reason": route.reason},
            )
            selected_route = route.model if mode == "enforce" and "model_route" in action_names else _baseline_model(normalized, policy.model_allowlist)
            response = provider.chat(provider_request if mode == "enforce" else normalized, selected_route)
            provider_called = True
            verification = _verify_chat_response(response)
            if not verification.accepted:
                fallback_used = True
                fallback_reason = verification.reason
                ledger.append(LedgerEvent("ai.fallback.invoked", tenant, work_unit.id, policy_bundle_id=policy.policy_bundle_id, details=verification.to_dict(), trace_id=work_unit.trace_id))
                emit_log(
                    state,
                    "ai.fallback.invoked",
                    "AI fallback invoked",
                    severity="warning",
                    tenant=tenant,
                    work_unit_id=work_unit.id,
                    policy_bundle_id=policy.policy_bundle_id,
                    trace_id=work_unit.trace_id,
                    error_code="verifier_failed",
                    details=verification.to_dict(),
                )
                GLOBAL_METRICS.inc("urp_ai_fallbacks_total")
                response = provider.chat(normalized, _fallback_model(route.fallback_model, policy.model_allowlist))
                verification = _verify_chat_response(response)
            if verification.accepted:
                _verify_required_ai_verifiers(policy.required_verifiers, verification, response, source_fingerprints, cache_result, work_unit.id)
                ttl_seconds = requested_cache_ttl
                if mode == "enforce" and ttl_seconds > 0 and "cache_store" in action_names:
                    cache.put(CacheEntry(cache_key, tenant, namespace, response, source_fingerprints, True, _expiry(ttl_seconds)))
                if semantic_cache_enabled:
                    semantic_cache.store(
                        tenant,
                        namespace,
                        routing_text,
                        response,
                        source_fingerprints,
                        verification=verification,
                        ttl_seconds=ttl_seconds,
                    )
            else:
                ledger.append(LedgerEvent("verifier.failed", tenant, work_unit.id, policy_bundle_id=policy.policy_bundle_id, details=verification.to_dict(), trace_id=work_unit.trace_id))
                emit_log(
                    state,
                    "verifier.failed",
                    "AI verifier failed after fallback",
                    severity="error",
                    tenant=tenant,
                    work_unit_id=work_unit.id,
                    policy_bundle_id=policy.policy_bundle_id,
                    trace_id=work_unit.trace_id,
                    error_code="verifier_failed",
                    details=verification.to_dict(),
                )
                GLOBAL_METRICS.inc("urp_verifier_failures_total")
                raise verifier_failed("AI verifier failed after fallback", work_unit.id, verification.to_dict())
            ledger.append(LedgerEvent("cache.exact.miss", tenant, work_unit.id, policy_bundle_id=policy.policy_bundle_id, details={"cache_key": cache_key}, trace_id=work_unit.trace_id))
            ledger.append(LedgerEvent("ai.model.routed", tenant, work_unit.id, policy_bundle_id=policy.policy_bundle_id, details={"route": route.model, "final_model": response.get("model"), "fallback_used": fallback_used, "reason": route.reason}, trace_id=work_unit.trace_id))
            emit_log(
                state,
                "cache.exact.miss",
                "exact cache miss",
                tenant=tenant,
                work_unit_id=work_unit.id,
                policy_bundle_id=policy.policy_bundle_id,
                trace_id=work_unit.trace_id,
                details={"cache_key": cache_key, "cache_type": "exact"},
            )
            RouteFeedbackStore(state).record(work_unit, route, verification.accepted)
            GLOBAL_METRICS.inc("urp_cache_misses_total")
            if response.get("model") == "frontier":
                GLOBAL_METRICS.inc("urp_ai_large_model_calls_total")
    verification = _verify_chat_response(response)
    _verify_required_ai_verifiers(policy.required_verifiers, verification, response, source_fingerprints, cache_result, work_unit.id)
    compute_manifest = {
        "request": {
            "request_hash": stable_json_hash(normalized),
            "tenant": tenant,
            "task_type": "prompt_request",
            "input_tokens": approximate_tokens(str(normalized.get("messages", ""))),
        },
        "contract": {
            "quality_required": normalized.get("urp", {}).get("quality", "standard"),
            "latency_budget_ms": normalized.get("urp", {}).get("latency_budget_ms", 0),
            "freshness_required_seconds": normalized.get("urp", {}).get("freshness_required_seconds", 0),
            "privacy_scope": "tenant_namespace",
        },
        "plan": {
            "cache_checked": True,
            "tools_checked": [],
            "context_tokens_before": compiled.tokens_before,
            "context_tokens_after": compiled.tokens_after,
            "context_applied": context_applied,
            "selected_model": response.get("model", "mock"),
            "fallback_model": "frontier",
            "mode": mode,
        },
        "result": {
            "accepted_by_verifier": verification.accepted,
            "fallback_used": fallback_used,
            "fallback_reason": fallback_reason,
            "large_model_called": provider_called and response.get("model") == "frontier",
            "cacheable_until": _cacheable_until(urp_options) if mode == "enforce" else None,
            "estimated_joules_avoided": 0.0 if provider_called else 1.0,
        },
    }
    validate_named_schema("compute_manifest", compute_manifest)
    manifest = Manifest(
        work_unit_id=work_unit.id,
        tenant=tenant,
        kind=WorkUnitKind.PROMPT_REQUEST,
        contract=policy.contract,
        logical_ref=work_unit.logical_ref,
        namespace=namespace,
        trace_id=work_unit.trace_id,
        policy=policy.to_dict(),
        classification={"ai_task_hint": "general", "raw_prompt_logged": False},
        plan=plan.to_dict(),
        physical={
            "compute_manifest": compute_manifest,
            "request_hash": stable_json_hash(normalized),
            "cache_key": cache_key,
            "cache_result": cache_result,
            "semantic_hit_score": semantic_hit_score,
        },
        verification=verification.to_dict(),
        state="active" if mode == "enforce" else "planned" if mode == "observe" else "superseded",
        telemetry={
            "mode": mode,
            "tokens_removed": compiled.tokens_before - compiled.tokens_after if context_applied else 0,
            "tokens_removable": compiled.tokens_before - compiled.tokens_after,
            "provider_called": provider_called,
        },
    )
    default_manifest_store(state).put(manifest)
    ledger.append(LedgerEvent("manifest.written", tenant, work_unit.id, manifest.manifest_id, policy.policy_bundle_id, trace_id=work_unit.trace_id))
    emit_log(
        state,
        "manifest.written",
        "manifest written",
        tenant=tenant,
        work_unit_id=work_unit.id,
        manifest_id=manifest.manifest_id,
        policy_bundle_id=policy.policy_bundle_id,
        trace_id=work_unit.trace_id,
        details={"kind": "prompt_request", "cache_result": cache_result, "provider_called": provider_called},
    )
    emit_span(state, "urp.manifest.write", work_unit.trace_id, work_unit_id=work_unit.id, manifest_id=manifest.manifest_id)
    response = dict(response)
    response["urp"] = {
        "work_unit_id": work_unit.id,
        "manifest_id": manifest.manifest_id,
        "cache": cache_result,
        "route": response.get("model", "mock"),
        "fallback_used": fallback_used,
        "verifier": verification.verifier_id,
        "mode": mode,
        "context_applied": context_applied,
        "trace_id": work_unit.trace_id,
    }
    GLOBAL_METRICS.inc("urp_work_units_total")
    GLOBAL_METRICS.inc("urp_ai_input_tokens_total", compute_manifest["request"]["input_tokens"])
    GLOBAL_METRICS.inc("urp_ai_context_tokens_removed_total", max(0, compiled.tokens_before - compiled.tokens_after))
    return response


def handle_completion(
    request: Dict[str, Any],
    tenant: str = "local",
    namespace: str = "default",
    state_dir: str | Path = ".urp",
    provider: ChatProvider | None = None,
    cache: URPCache | None = None,
    semantic_cache: SemanticCache | None = None,
    policy_bundle: Dict[str, Any] | None = None,
    mode: str | None = None,
) -> Dict[str, Any]:
    prompt = request.get("prompt", "")
    if isinstance(prompt, list):
        prompt_text = "\n".join(str(item) for item in prompt)
    else:
        prompt_text = str(prompt)
    chat_request = {
        "model": request.get("model", "auto"),
        "messages": [{"role": "user", "content": prompt_text}],
        "temperature": request.get("temperature", 0),
        "tools": request.get("tools", []),
        "urp": request.get("urp", {}),
    }
    chat_response = handle_chat_completion(
        chat_request,
        tenant,
        namespace,
        state_dir,
        provider,
        cache,
        semantic_cache,
        policy_bundle,
        mode,
    )
    choice = chat_response["choices"][0]
    text = choice["message"]["content"]
    return {
        "id": str(chat_response.get("id", "chatcmpl_mock")).replace("chatcmpl", "cmpl", 1),
        "object": "text_completion",
        "model": chat_response.get("model", request.get("model", "auto")),
        "choices": [{"index": choice.get("index", 0), "text": text, "finish_reason": choice.get("finish_reason", "stop")}],
        "usage": chat_response.get("usage", {}),
        "urp": chat_response["urp"],
    }


def list_models() -> Dict[str, Any]:
    return {"object": "list", "data": [{"id": m, "object": "model", "owned_by": "urp-mock"} for m in ["tiny", "small", "medium", "frontier"]]}


def handle_embeddings(
    request: Dict[str, Any],
    tenant: str = "local",
    namespace: str = "default",
    state_dir: str | Path = ".urp",
    cache: URPCache | None = None,
    policy_bundle: Dict[str, Any] | None = None,
    mode: str | None = None,
) -> Dict[str, Any]:
    mode = execution_mode(mode)
    require_execution_enabled()
    state = init_state(state_dir)
    cache = cache or URPCache(state / "cache" / "cache.sqlite3")
    normalized = normalize_embedding_request(request)
    source_fingerprints = _embedding_source_fingerprints(normalized)
    input_items = _embedding_inputs(normalized.get("input", ""))
    input_hash = stable_json_hash({"input": normalized["input"], "model": normalized["model"]})
    work_unit = WorkUnit(
        kind=WorkUnitKind.EMBEDDING_REQUEST,
        tenant=tenant,
        namespace=namespace,
        logical_ref="openai://embeddings",
        payload={"request_hash": stable_json_hash(normalized), "input_hash": input_hash, "input_count": len(input_items), "routing_text": "\n".join(input_items)},
        requested_contract=Contract.SEMANTIC,
        metadata={"source_fingerprints": sorted(source_fingerprints), "model": normalized["model"]},
    )
    if policy_bundle is None:
        policy_bundle = resolve_active_policy_bundle(state, normalized.get("urp", {}).get("policy_bundle_id"))
    policy = evaluate_policy(work_unit, policy_bundle)
    plan = plan_work_unit(work_unit, mode=mode, policy_bundle=policy_bundle, policy_decision=policy)
    _require_ai_approval(state, work_unit, policy)
    action_names = {action.type for action in plan.actions}
    ledger = default_ledger(state)
    ledger.append(LedgerEvent("work_unit.received", tenant, work_unit.id, policy_bundle_id=policy.policy_bundle_id, trace_id=work_unit.trace_id))
    ledger.append(LedgerEvent("policy.evaluated", tenant, work_unit.id, policy_bundle_id=policy.policy_bundle_id, decision=policy.contract.value, details=policy.to_dict(), trace_id=work_unit.trace_id))
    store_plan_with_audit(state, plan, work_unit)
    emit_log(
        state,
        "ai.gateway.request",
        "AI gateway request received",
        tenant=tenant,
        work_unit_id=work_unit.id,
        policy_bundle_id=policy.policy_bundle_id,
        trace_id=work_unit.trace_id,
        details={"request_hash": stable_json_hash(normalized), "item_count": len(input_items), "source_fingerprint_count": len(source_fingerprints)},
    )
    emit_span(state, "urp.intake", work_unit.trace_id, work_unit_id=work_unit.id, tenant=tenant, kind="embedding_request")

    cache_key = cache.exact_key(tenant, namespace, normalized, source_fingerprints)
    embedding_cache_ttl = _cache_ttl_seconds(dict(normalized.get("urp") or {}))
    cached = cache.get(cache_key, tenant, namespace, source_fingerprints) if mode == "enforce" and embedding_cache_ttl > 0 and "exact_cache_lookup" in action_names else None
    cache_result = "miss"
    provider_called = False
    fallback_used = False
    fallback_reason = ""
    if cached is not None:
        response = cached
        cache_result = "exact_hit"
        provider_called = False
        ledger.append(LedgerEvent("cache.exact.hit", tenant, work_unit.id, policy_bundle_id=policy.policy_bundle_id, details={"cache_key": cache_key}, trace_id=work_unit.trace_id))
        emit_log(
            state,
            "cache.exact.hit",
            "exact cache hit",
            tenant=tenant,
            work_unit_id=work_unit.id,
            policy_bundle_id=policy.policy_bundle_id,
            trace_id=work_unit.trace_id,
            details={"cache_key": cache_key, "cache_type": "exact"},
        )
        GLOBAL_METRICS.inc("urp_cache_hits_total")
    else:
        route = route_model(work_unit, policy.model_allowlist, prompt_text="\n".join(input_items))
        emit_span(state, "urp.ai.route", work_unit.trace_id, work_unit_id=work_unit.id, route=route.model, reason=route.reason)
        emit_log(
            state,
            "ai.model.routed",
            "AI model routed",
            tenant=tenant,
            work_unit_id=work_unit.id,
            policy_bundle_id=policy.policy_bundle_id,
            trace_id=work_unit.trace_id,
            details={"route": route.model, "reason": route.reason},
        )
        vectors = [_embedding_vector(tenant, normalized["model"], item, normalized.get("dimensions")) for item in input_items]
        provider_called = True
        response = {
            "object": "list",
            "data": [
                {"object": "embedding", "embedding": _encode_embedding(vector, normalized["encoding_format"]), "index": index}
                for index, vector in enumerate(vectors)
            ],
            "model": normalized["model"],
            "usage": {
                "prompt_tokens": sum(approximate_tokens(item) for item in input_items),
                "total_tokens": sum(approximate_tokens(item) for item in input_items),
            },
        }
        verification = verify_embedding_vector(vectors)
        if not verification.accepted:
            fallback_used = True
            fallback_reason = verification.reason
            ledger.append(LedgerEvent("ai.fallback.invoked", tenant, work_unit.id, policy_bundle_id=policy.policy_bundle_id, details=verification.to_dict(), trace_id=work_unit.trace_id))
            emit_log(
                state,
                "ai.fallback.invoked",
                "AI fallback invoked",
                severity="warning",
                tenant=tenant,
                work_unit_id=work_unit.id,
                policy_bundle_id=policy.policy_bundle_id,
                trace_id=work_unit.trace_id,
                error_code="verifier_failed",
                details=verification.to_dict(),
            )
            GLOBAL_METRICS.inc("urp_ai_fallbacks_total")
            vectors = [_embedding_vector(tenant, "frontier", item, normalized.get("dimensions")) for item in input_items]
            response["data"] = [
                {"object": "embedding", "embedding": _encode_embedding(vector, normalized["encoding_format"]), "index": index}
                for index, vector in enumerate(vectors)
            ]
            response["model"] = "frontier"
            verification = verify_embedding_vector(vectors)
        if verification.accepted:
            _verify_required_embedding_verifiers(policy.required_verifiers, verification, work_unit.id)
            if mode == "enforce" and "cache_store" in action_names:
                ttl_seconds = embedding_cache_ttl
                if ttl_seconds > 0:
                    cache.put(CacheEntry(cache_key, tenant, namespace, response, source_fingerprints, True, _expiry(ttl_seconds)))
        else:
            ledger.append(LedgerEvent("verifier.failed", tenant, work_unit.id, policy_bundle_id=policy.policy_bundle_id, details=verification.to_dict(), trace_id=work_unit.trace_id))
            emit_log(
                state,
                "verifier.failed",
                "AI verifier failed after fallback",
                severity="error",
                tenant=tenant,
                work_unit_id=work_unit.id,
                policy_bundle_id=policy.policy_bundle_id,
                trace_id=work_unit.trace_id,
                error_code="verifier_failed",
                details=verification.to_dict(),
            )
            GLOBAL_METRICS.inc("urp_verifier_failures_total")
            raise verifier_failed("embedding verifier failed after fallback", work_unit.id, verification.to_dict())
        ledger.append(LedgerEvent("cache.exact.miss", tenant, work_unit.id, policy_bundle_id=policy.policy_bundle_id, details={"cache_key": cache_key}, trace_id=work_unit.trace_id))
        ledger.append(LedgerEvent("ai.model.routed", tenant, work_unit.id, policy_bundle_id=policy.policy_bundle_id, details={"route": route.model, "final_model": response["model"], "fallback_used": fallback_used, "reason": route.reason}, trace_id=work_unit.trace_id))
        emit_log(
            state,
            "cache.exact.miss",
            "exact cache miss",
            tenant=tenant,
            work_unit_id=work_unit.id,
            policy_bundle_id=policy.policy_bundle_id,
            trace_id=work_unit.trace_id,
            details={"cache_key": cache_key, "cache_type": "exact"},
        )
        RouteFeedbackStore(state).record(work_unit, route, verification.accepted)
        GLOBAL_METRICS.inc("urp_cache_misses_total")
        if provider_called and response.get("model") == "frontier":
            GLOBAL_METRICS.inc("urp_ai_large_model_calls_total")
    vectors_for_verification = [_decode_embedding(row["embedding"], normalized["encoding_format"]) for row in response.get("data", [])]
    verification = verify_embedding_vector(vectors_for_verification)
    _verify_required_embedding_verifiers(policy.required_verifiers, verification, work_unit.id)
    compute_manifest = {
        "request": {
            "request_hash": stable_json_hash(normalized),
            "input_hash": input_hash,
            "tenant": tenant,
            "task_type": "embedding_request",
            "input_count": len(input_items),
            "input_tokens": sum(approximate_tokens(item) for item in input_items),
        },
        "contract": {
            "quality_required": normalized.get("urp", {}).get("quality", "standard"),
            "privacy_scope": "tenant_namespace",
        },
        "plan": {
            "cache_checked": True,
            "selected_model": response.get("model", normalized["model"]),
            "vector_dimensions": len(vectors_for_verification[0]) if vectors_for_verification else 0,
        },
        "result": {
            "accepted_by_verifier": verification.accepted,
            "fallback_used": fallback_used,
            "fallback_reason": fallback_reason,
            "large_model_called": provider_called and response.get("model") == "frontier",
            "cacheable_until": _cacheable_until(dict(normalized.get("urp") or {})) if mode == "enforce" else None,
            "estimated_joules_avoided": 0.0 if provider_called else 0.25,
        },
    }
    validate_named_schema("compute_manifest", compute_manifest)
    manifest = Manifest(
        work_unit_id=work_unit.id,
        tenant=tenant,
        kind=WorkUnitKind.EMBEDDING_REQUEST,
        contract=policy.contract,
        logical_ref=work_unit.logical_ref,
        namespace=namespace,
        trace_id=work_unit.trace_id,
        policy=policy.to_dict(),
        classification={"ai_task_hint": "embedding", "raw_prompt_logged": False},
        plan=plan.to_dict(),
        physical={"compute_manifest": compute_manifest, "request_hash": stable_json_hash(normalized), "cache_key": cache_key, "cache_result": cache_result},
        verification=verification.to_dict(),
        state="active" if mode == "enforce" else "planned" if mode == "observe" else "superseded",
        telemetry={"mode": mode, "provider_called": provider_called, "vector_count": len(vectors_for_verification), "vector_dimensions": compute_manifest["plan"]["vector_dimensions"]},
    )
    default_manifest_store(state).put(manifest)
    ledger.append(LedgerEvent("manifest.written", tenant, work_unit.id, manifest.manifest_id, policy.policy_bundle_id, trace_id=work_unit.trace_id))
    emit_log(
        state,
        "manifest.written",
        "manifest written",
        tenant=tenant,
        work_unit_id=work_unit.id,
        manifest_id=manifest.manifest_id,
        policy_bundle_id=policy.policy_bundle_id,
        trace_id=work_unit.trace_id,
        details={"kind": "embedding_request", "cache_result": cache_result, "provider_called": provider_called},
    )
    emit_span(state, "urp.manifest.write", work_unit.trace_id, work_unit_id=work_unit.id, manifest_id=manifest.manifest_id)
    response = dict(response)
    response["urp"] = {
        "work_unit_id": work_unit.id,
        "manifest_id": manifest.manifest_id,
        "cache": cache_result,
        "route": response.get("model", normalized["model"]),
        "fallback_used": fallback_used,
        "verifier": verification.verifier_id,
        "mode": mode,
        "trace_id": work_unit.trace_id,
    }
    GLOBAL_METRICS.inc("urp_work_units_total")
    GLOBAL_METRICS.inc("urp_ai_input_tokens_total", compute_manifest["request"]["input_tokens"])
    return response


def normalize_embedding_request(request: Dict[str, Any]) -> Dict[str, Any]:
    encoding_format = str(request.get("encoding_format", "float"))
    if encoding_format not in {"float", "base64"}:
        raise ValueError("encoding_format must be float or base64")
    dimensions = request.get("dimensions")
    if dimensions is not None:
        dimensions = int(dimensions)
        if dimensions < 1 or dimensions > 4096:
            raise ValueError("dimensions must be between 1 and 4096")
    return {
        "model": request.get("model", "mock-embedding"),
        "input": request.get("input", ""),
        "encoding_format": encoding_format,
        "dimensions": dimensions,
        "urp": request.get("urp", {}),
    }


def lookup_semantic_cache(
    tenant: str,
    namespace: str,
    text: str,
    source_fingerprints: Set[str],
    task_type: str = "general",
    state_dir: str | Path = ".urp",
) -> Any | None:
    state = init_state(state_dir)
    return SemanticCache(path=state / "cache" / "cache.sqlite3").lookup(tenant, namespace, text, source_fingerprints, task_type)


def _source_fingerprints(normalized: Dict[str, Any]) -> Set[str]:
    explicit = normalized.get("urp", {}).get("source_fingerprints")
    if explicit:
        return set(map(str, explicit))
    return {stable_json_hash(msg) for msg in normalized.get("messages", []) if msg.get("role") in {"system", "developer", "tool"}}


def _embedding_source_fingerprints(normalized: Dict[str, Any]) -> Set[str]:
    explicit = normalized.get("urp", {}).get("source_fingerprints")
    return set(map(str, explicit or []))


def _embedding_inputs(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _embedding_vector(tenant: str, model: str, text: str, dimensions: Any = None) -> List[float]:
    try:
        size = int(dimensions) if dimensions else 8
    except (TypeError, ValueError):
        size = 8
    size = max(1, min(size, 4096))
    digest = stable_json_hash({"tenant": tenant, "input": text, "model": model})
    while len(digest) < size * 2:
        digest += stable_json_hash({"seed": digest})
    return [int(digest[i : i + 2], 16) / 255 for i in range(0, size * 2, 2)]


def _encode_embedding(vector: List[float], encoding_format: str) -> List[float] | str:
    if encoding_format == "float":
        return vector
    return base64.b64encode(struct.pack(f"<{len(vector)}f", *vector)).decode("ascii")


def _decode_embedding(value: Any, encoding_format: str) -> List[float]:
    if encoding_format == "float":
        return list(value) if isinstance(value, list) else []
    if not isinstance(value, str):
        return []
    try:
        raw = base64.b64decode(value, validate=True)
    except ValueError:
        return []
    if len(raw) % 4:
        return []
    return list(struct.unpack(f"<{len(raw) // 4}f", raw))


def _last_user_text(messages: List[Dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                return "\n".join(str(part.get("text", "")) for part in content if isinstance(part, dict) and part.get("type") == "text")
            return str(content)
    return ""


def _normalize_message(message: Any) -> Dict[str, Any]:
    if not isinstance(message, dict):
        raise ValueError("each chat message must be an object")
    normalized = dict(message)
    normalized["role"] = str(message.get("role", "user"))
    content = message.get("content", "")
    if isinstance(content, str):
        normalized["content"] = content.strip()
    elif isinstance(content, list):
        parts: list[Any] = []
        for part in content:
            if isinstance(part, dict):
                item = dict(part)
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    item["text"] = item["text"].strip()
                parts.append(item)
            else:
                parts.append(part)
        normalized["content"] = parts
    else:
        normalized["content"] = str(content)
    return normalized


def _verify_chat_response(response: Any) -> VerificationResult:
    try:
        text = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return VerificationResult(False, "chat_completion_shape@1", "missing_assistant_content")
    return verify_non_empty_text(str(text))


def _verify_required_ai_verifiers(
    required: List[str],
    primary: VerificationResult,
    response: Dict[str, Any],
    source_fingerprints: Set[str],
    cache_result: str,
    work_unit_id: str,
) -> None:
    supported = {
        "non_empty_text",
        "fallback_available",
        "source_fingerprint_match",
        "source_consistency",
        "freshness_check",
        "answer_citation_check",
    }
    names = {name.split("@", 1)[0] for name in required}
    unsupported = sorted(names - supported)
    if unsupported:
        raise verifier_failed("required AI verifier is not implemented", work_unit_id, {"unsupported": unsupported})
    if "non_empty_text" in names and not primary.accepted:
        raise verifier_failed("required non-empty text verifier failed", work_unit_id, primary.to_dict())
    if names & {"source_fingerprint_match", "source_consistency"} and cache_result in {"exact_hit", "semantic_hit"} and source_fingerprints is None:
        raise verifier_failed("source fingerprint verification could not run", work_unit_id)
    if "answer_citation_check" in names and source_fingerprints:
        text = str(response.get("choices", [{}])[0].get("message", {}).get("content", "")).casefold()
        if not any(marker in text for marker in ("[source", "[1]", "citation", "http://", "https://")):
            raise verifier_failed("required answer citation verifier failed", work_unit_id, {"required": "answer_citation_check"})


def _verify_required_embedding_verifiers(required: List[str], primary: VerificationResult, work_unit_id: str) -> None:
    names = {name.split("@", 1)[0] for name in required}
    supported = {"embedding_shape", "fallback_available", "freshness_check", "source_fingerprint_match", "source_consistency"}
    unsupported = sorted(names - supported)
    if unsupported:
        raise verifier_failed("required embedding verifier is not implemented", work_unit_id, {"unsupported": unsupported})
    if "embedding_shape" in names and not primary.accepted:
        raise verifier_failed("required embedding shape verifier failed", work_unit_id, primary.to_dict())


def _require_ai_approval(state: Path, work_unit: WorkUnit, policy: Any) -> None:
    if not policy.require_approval:
        return
    approval_id = work_unit.policy_context.get("approval_id")
    if not approval_id:
        raise policy_denied("policy requires an approved approval_id", work_unit.id, policy.policy_bundle_id)
    try:
        ApprovalStore(state).verify(str(approval_id), work_unit, policy.contract, policy.policy_bundle_id)
    except (KeyError, ValueError, FileNotFoundError) as exc:
        raise policy_denied(f"approval verification failed: {exc}", work_unit.id, policy.policy_bundle_id) from exc


def _baseline_model(request: Dict[str, Any], allowed_models: List[str]) -> str:
    requested = str(request.get("model", "auto"))
    if requested not in {"", "auto"}:
        return requested
    return "frontier" if "frontier" in allowed_models else allowed_models[-1]


def _fallback_model(requested: str, allowed_models: List[str]) -> str:
    if requested in allowed_models:
        return requested
    return "frontier" if "frontier" in allowed_models else allowed_models[-1]


def _cache_ttl_seconds(options: Dict[str, Any]) -> float:
    value = options.get("cache_ttl_seconds", options.get("freshness_required_seconds", 3600))
    try:
        ttl = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("cache_ttl_seconds must be numeric") from exc
    if ttl < 0 or ttl > 86400:
        raise ValueError("cache_ttl_seconds must be between 0 and 86400")
    return ttl


def _expiry(ttl_seconds: float) -> float:
    return time.time() + ttl_seconds


def _cacheable_until(options: Dict[str, Any]) -> str | None:
    ttl = _cache_ttl_seconds(options)
    return datetime.fromtimestamp(_expiry(ttl), timezone.utc).isoformat() if ttl > 0 else None
