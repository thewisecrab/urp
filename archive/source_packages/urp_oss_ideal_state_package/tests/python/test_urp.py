from urp.contracts import ResourceRef, ResourceContract
from urp.planner import build_plan
from urp.chunking import content_defined_chunks, fixed_chunks
from urp.entropy import shannon_entropy_bits_per_byte, likely_incompressible
from urp.ai_router import route_ai_request
from urp.cache import ExactCache


def test_low_entropy_plans_lossless_reduction():
    plan = build_plan(ResourceRef("s3://b/repeated", "object"), ResourceContract(), b"a" * 10000)
    assert "zstd" in plan.transforms
    assert "content-defined-chunking" in plan.transforms


def test_high_entropy_uses_safe_fallback():
    data = bytes(range(256)) * 128
    plan = build_plan(ResourceRef("s3://b/noisy", "object"), ResourceContract(), data)
    assert "whole-object-dedupe" in plan.transforms
    assert plan.fallback == "store-original-and-audit"


def test_content_defined_chunks_cover_data():
    data = (b"abc123" * 5000) + (b"xyz" * 1000)
    chunks = content_defined_chunks(data, min_size=512, avg_size=1024, max_size=4096)
    assert chunks[0].start == 0
    assert chunks[-1].end == len(data)
    assert b"".join(c.data for c in chunks) == data


def test_fixed_chunks_cover_data():
    data = b"0123456789"
    chunks = fixed_chunks(data, size=3)
    assert [c.data for c in chunks] == [b"012", b"345", b"678", b"9"]


def test_entropy_empty():
    assert shannon_entropy_bits_per_byte(b"") == 0.0


def test_ai_tool_route():
    decision = route_ai_request("calculate revenue growth from this SQL table")
    assert decision.route == "tool-first"


def test_ai_small_model_route():
    decision = route_ai_request("summarize this policy")
    assert decision.route == "small-model-first"


def test_exact_cache_roundtrip():
    cache = ExactCache()
    cache.put("tenant-a", b"prompt", b"answer", ttl_seconds=60, source_fingerprint="src")
    assert cache.get("tenant-a", b"prompt") == b"answer"
    assert cache.get("tenant-b", b"prompt") is None


def test_legal_hold_no_transform():
    plan = build_plan(ResourceRef("ledger", "financial_ledger"), ResourceContract(mode="legal-hold"), b"ledger")
    assert plan.transforms == []
