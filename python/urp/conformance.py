from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict

from .ai_gateway import handle_chat_completion, handle_completion, handle_embeddings, list_models
from .cache import URPCache
from .ledger import default_ledger
from .manifest_store import default_manifest_store
from .plugins import ConformanceResult


def ai_gateway_conformance(state_dir: str | Path | None = None) -> ConformanceResult:
    if state_dir is None:
        with tempfile.TemporaryDirectory() as td:
            return _ai_gateway_conformance(td)
    return _ai_gateway_conformance(state_dir)


def _ai_gateway_conformance(state_dir: str | Path) -> ConformanceResult:
    cache = URPCache()
    tenant = "conformance-ai"
    namespace = "support"
    prompt_text = "Conformance prompt: summarize the VPN reset policy."
    chat_request = {
        "model": "auto",
        "messages": [
            {"role": "system", "content": "source:conformance-v1"},
            {"role": "user", "content": prompt_text},
        ],
        "urp": {"source_fingerprints": ["conformance-source-v1"]},
    }
    first_chat = handle_chat_completion(chat_request, tenant=tenant, namespace=namespace, state_dir=state_dir, cache=cache)
    second_chat = handle_chat_completion(chat_request, tenant=tenant, namespace=namespace, state_dir=state_dir, cache=cache)
    other_tenant_chat = handle_chat_completion(chat_request, tenant="conformance-other", namespace=namespace, state_dir=state_dir, cache=cache)
    completion = handle_completion(
        {"model": "auto", "prompt": "Conformance completion prompt", "urp": {"source_fingerprints": ["completion-source-v1"]}},
        tenant=tenant,
        namespace=namespace,
        state_dir=state_dir,
        cache=cache,
    )
    embedding = handle_embeddings(
        {"model": "mock-embedding", "input": "Conformance embedding input", "urp": {"source_fingerprints": ["embedding-source-v1"]}},
        tenant=tenant,
        namespace="vectors",
        state_dir=state_dir,
        cache=cache,
    )
    fallback_chat = handle_chat_completion(
        {"model": "auto", "messages": [{"role": "user", "content": "Conformance fallback prompt"}]},
        tenant=tenant,
        namespace=namespace,
        state_dir=state_dir,
        provider=_EmptyFirstProvider(),
        cache=cache,
    )
    models = list_models()
    manifests = default_manifest_store(state_dir).list()
    manifest_by_id = {manifest.manifest_id: manifest for manifest in manifests}
    response_manifest_ids = [
        first_chat["urp"]["manifest_id"],
        second_chat["urp"]["manifest_id"],
        other_tenant_chat["urp"]["manifest_id"],
        completion["urp"]["manifest_id"],
        embedding["urp"]["manifest_id"],
        fallback_chat["urp"]["manifest_id"],
    ]
    response_manifests = [manifest_by_id[mid] for mid in response_manifest_ids if mid in manifest_by_id]
    fallback_manifest = manifest_by_id.get(fallback_chat["urp"]["manifest_id"])
    event_types = {event.event_type for event in default_ledger(state_dir).read()}
    checks: Dict[str, bool] = {
        "chat_openai_shape": _chat_shape(first_chat),
        "chat_exact_cache_hit": first_chat.get("urp", {}).get("cache") == "miss" and second_chat.get("urp", {}).get("cache") == "exact_hit",
        "cross_tenant_cache_blocked": other_tenant_chat.get("urp", {}).get("cache") == "miss",
        "completion_openai_shape": completion.get("object") == "text_completion" and bool(completion.get("choices", [{}])[0].get("text")),
        "embeddings_shape": embedding.get("object") == "list" and bool(embedding.get("data", [{}])[0].get("embedding")),
        "models_shape": models.get("object") == "list" and any(row.get("id") == "frontier" for row in models.get("data", [])),
        "manifests_written": len(response_manifests) == len(response_manifest_ids),
        "prompt_redacted_from_manifests": all(not manifest.classification.get("raw_prompt_logged") and prompt_text not in json.dumps(manifest.to_dict(), sort_keys=True) for manifest in response_manifests),
        "ledger_lifecycle_events": {"work_unit.received", "policy.evaluated", "plan.created", "manifest.written", "cache.exact.hit", "cache.exact.miss"}.issubset(event_types),
        "fallback_invoked_and_recorded": bool(
            fallback_chat.get("urp", {}).get("fallback_used")
            and fallback_manifest
            and fallback_manifest.physical.get("compute_manifest", {}).get("result", {}).get("fallback_used")
            and "ai.fallback.invoked" in event_types
        ),
    }
    details: Dict[str, Any] = {
        "chat_cache_sequence": [first_chat["urp"]["cache"], second_chat["urp"]["cache"], other_tenant_chat["urp"]["cache"]],
        "manifest_ids": response_manifest_ids,
        "fallback_manifest_id": fallback_chat["urp"]["manifest_id"],
        "fallback_route": fallback_chat["urp"]["route"],
        "model_count": len(models.get("data", [])),
        "event_types": sorted(event_types),
        "tenant": tenant,
        "namespace": namespace,
    }
    return ConformanceResult("ai-gateway-openai-compatible-v1", all(checks.values()), checks, details)


def _chat_shape(response: Dict[str, Any]) -> bool:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return False
    message = choices[0].get("message", {})
    usage = response.get("usage", {})
    return (
        response.get("object") == "chat.completion"
        and isinstance(message.get("content"), str)
        and isinstance(usage.get("total_tokens"), int)
        and bool(response.get("urp", {}).get("manifest_id"))
    )


class _EmptyFirstProvider:
    def __init__(self) -> None:
        self.calls = 0

    def chat(self, request: Dict[str, Any], route: str) -> Dict[str, Any]:
        self.calls += 1
        content = "" if self.calls == 1 else f"[fallback:{route}] conformance answer"
        return {
            "id": "chatcmpl_conformance_fallback",
            "object": "chat.completion",
            "model": route,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1 if content else 0, "total_tokens": 2 if content else 1},
        }
