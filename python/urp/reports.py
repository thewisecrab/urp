from __future__ import annotations

from collections import Counter
from datetime import datetime
from math import ceil
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .contracts import Manifest
from .ai_router import RouteFeedbackStore
from .ledger import default_ledger
from .manifest_store import default_manifest_store
from .tracing import TraceSpan, default_trace_store


AI_KINDS = {"prompt_request", "embedding_request", "completion_response", "chat_session", "agent_step", "tool_call"}


def savings_report(state_dir: str | Path = ".urp", tenant: str | None = None) -> Dict[str, Any]:
    manifests = default_manifest_store(state_dir).list()
    if tenant:
        manifests = [m for m in manifests if m.tenant == tenant]
    ledger = default_ledger(state_dir)
    events = ledger.query(tenant=tenant)
    trace_ids = {m.trace_id for m in manifests if m.trace_id} | {e.trace_id for e in events if e.trace_id}
    spans = [span for span in default_trace_store(state_dir).query() if not trace_ids or span.trace_id in trace_ids]
    bytes_in = sum(int(m.telemetry.get("bytes_in", m.physical.get("logical_size", 0)) or 0) for m in manifests)
    bytes_stored = sum(int(m.telemetry.get("bytes_stored", m.physical.get("stored_size", 0)) or 0) for m in manifests)
    bytes_avoided = sum(int(m.telemetry.get("bytes_avoided", max(0, int(m.physical.get("logical_size", 0) or 0) - int(m.physical.get("stored_size", 0) or 0))) or 0) for m in manifests)
    exact_cache_hits = sum(1 for e in events if e.event_type == "cache.exact.hit")
    semantic_cache_hits = sum(1 for e in events if e.event_type == "ai.semantic_cache.accepted")
    cache_hits = exact_cache_hits + semantic_cache_hits
    cache_misses = sum(1 for e in events if e.event_type == "cache.exact.miss")
    cache_lookups = cache_hits + cache_misses
    ai_manifests = [m for m in manifests if m.kind.value in AI_KINDS]
    input_tokens = sum(_compute_manifest_int(m, "request", "input_tokens") for m in ai_manifests)
    context_tokens_removed = sum(int(m.telemetry.get("tokens_removed", 0) or 0) for m in ai_manifests)
    cache_token_avoidance = sum(_compute_manifest_int(m, "request", "input_tokens") for m in ai_manifests if m.physical.get("cache_result") in {"exact_hit", "semantic_hit"})
    provider_avoided = sum(1 for m in ai_manifests if m.physical.get("cache_result") in {"exact_hit", "semantic_hit"})
    verifier_failures = sum(1 for e in events if e.event_type in {"verifier.failed", "ai.fallback.invoked"})
    policy_denials = sum(1 for e in events if e.event_type == "policy.denied")
    fallback_events = sum(1 for e in events if e.event_type == "ai.fallback.invoked")
    overhead_spans = [span for span in spans if span.name in {"urp.cache.lookup", "urp.ai.route", "urp.manifest.write", "urp.ledger.append", "urp.policy.evaluate"}]
    overhead_seconds = _p95(_span_durations(overhead_spans))
    return {
        "tenant": tenant,
        "manifest_count": len(manifests),
        "bytes_in": bytes_in,
        "bytes_stored": bytes_stored,
        "bytes_avoided": bytes_avoided,
        "storage_reduction_ratio": (bytes_avoided / bytes_in) if bytes_in else 0.0,
        "exact_cache_hits": exact_cache_hits,
        "semantic_cache_hits": semantic_cache_hits,
        "exact_cache_misses": cache_misses,
        "cache_hit_rate": (cache_hits / cache_lookups) if cache_lookups else 0.0,
        "model_calls_avoided": provider_avoided,
        "ai_request_count": len(ai_manifests),
        "ai_input_tokens": input_tokens,
        "ai_context_tokens_removed": context_tokens_removed,
        "ai_tokens_avoided_by_cache": cache_token_avoidance,
        "verifier_failures": verifier_failures,
        "policy_denials": policy_denials,
        "fallback_events": fallback_events,
        "trace_span_count": len(spans),
        "latency_overhead_seconds_p95": overhead_seconds,
        "latency_overhead_note": "Computed from recorded local URP overhead spans; zero means no matching spans were recorded.",
    }


def dashboard_report(state_dir: str | Path = ".urp", tenant: str | None = None) -> Dict[str, Any]:
    manifests = default_manifest_store(state_dir).list()
    if tenant:
        manifests = [m for m in manifests if m.tenant == tenant]
    events = default_ledger(state_dir).query(tenant=tenant)
    savings = savings_report(state_dir, tenant)
    by_contract = Counter(m.contract.value for m in manifests)
    by_kind = Counter(m.kind.value for m in manifests)
    legal_holds = sum(1 for m in manifests if m.lineage.get("policy_context", {}).get("legal_hold") is True)
    tombstones = sum(1 for m in manifests if m.state == "tombstoned")
    semantic_reductions = sum(1 for m in manifests if m.contract.value == "semantic")
    plugin_changes = sum(1 for e in events if e.event_type in {"plugin.registered", "plugin.updated", "plugin.disabled"})
    policy_overrides = sum(1 for e in events if e.event_type.startswith("policy.override."))
    cross_tenant_blocked = sum(1 for e in events if e.event_type == "cache.cross_tenant.blocked")
    work_units = max(1, sum(1 for e in events if e.event_type == "work_unit.received"))
    route_feedback = RouteFeedbackStore(state_dir).summary()
    return {
        "tenant": tenant,
        "generated_from": "local_state",
        "summary": savings,
        "executive": {
            "total_bytes_avoided": savings["bytes_avoided"],
            "total_ai_calls_avoided": savings["model_calls_avoided"],
            "total_ai_tokens_avoided": savings["ai_tokens_avoided_by_cache"],
            "risk_events": savings["verifier_failures"] + savings["policy_denials"] + policy_overrides,
            "savings_by_business_unit": {tenant or "all": savings["bytes_avoided"]},
        },
        "platform": {
            "manifest_store_health": "ok",
            "manifest_count": savings["manifest_count"],
            "ledger_event_count": len(events),
            "trace_span_count": savings["trace_span_count"],
            "fallback_rate": savings["fallback_events"] / work_units,
            "latency_overhead_seconds_p95": savings["latency_overhead_seconds_p95"],
        },
        "ai": {
            "request_count": savings["ai_request_count"],
            "requests_by_route": route_feedback,
            "cache_hit_rate": savings["cache_hit_rate"],
            "context_tokens_removed": savings["ai_context_tokens_removed"],
            "input_tokens": savings["ai_input_tokens"],
            "tokens_avoided_by_cache": savings["ai_tokens_avoided_by_cache"],
            "verifier_failures": savings["verifier_failures"],
            "model_escalation_rate": _route_rate(route_feedback, "frontier"),
        },
        "data": {
            "storage_by_contract": dict(by_contract),
            "work_units_by_kind": dict(by_kind),
            "compression_ratio": (savings["bytes_stored"] / savings["bytes_in"]) if savings["bytes_in"] else 0.0,
            "rehydration_test_status": "local_exact_rehydration_tested",
            "tombstoned_manifest_count": tombstones,
        },
        "security": {
            "policy_denials": savings["policy_denials"],
            "semantic_reductions": semantic_reductions,
            "legal_holds": legal_holds,
            "cross_tenant_attempts_blocked": cross_tenant_blocked,
            "plugin_changes": plugin_changes,
            "policy_overrides": policy_overrides,
        },
    }


def _compute_manifest_int(manifest: Manifest, section: str, key: str) -> int:
    compute_manifest = manifest.physical.get("compute_manifest", {})
    if not isinstance(compute_manifest, dict):
        return 0
    row = compute_manifest.get(section, {})
    if not isinstance(row, dict):
        return 0
    try:
        return int(row.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _span_durations(spans: Iterable[TraceSpan]) -> List[float]:
    durations: List[float] = []
    for span in spans:
        started = _parse_datetime(span.started_at)
        ended = _parse_datetime(span.ended_at)
        if started and ended:
            durations.append(max(0.0, (ended - started).total_seconds()))
    return durations


def _parse_datetime(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _p95(values: List[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, ceil(len(ordered) * 0.95) - 1)]


def _route_rate(route_feedback: Dict[str, Any], route: str) -> float:
    total = 0
    selected = 0
    for name, row in route_feedback.items():
        if isinstance(row, dict):
            count = int(row.get("count", 0) or 0)
        else:
            count = 0
        total += count
        if name == route:
            selected += count
    return (selected / total) if total else 0.0
