from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List

from .ai_gateway import handle_chat_completion
from .cache import CacheEntry, URPCache
from .contracts import Contract, Manifest, WorkUnit, WorkUnitKind
from .executor import execute_work_unit, rehydrate_manifest
from .lakehouse import LakehouseFile, recommend_compaction
from .manifest_store import FileManifestStore
from .scheduler import FlexibleJob, schedule_job
from .training import TrainingSample, dedupe_training_samples


def run_benchmark_suite(name: str, state_dir: str | Path = ".urp") -> Dict[str, Any]:
    if name == "object-exact-v1":
        return _object_exact(state_dir)
    if name == "prompt-cache-v1":
        return _prompt_cache(state_dir)
    if name == "advanced-local-v1":
        return _advanced_local(state_dir)
    if name == "load-local-v1":
        return _load_local(state_dir)
    if name == "local-all-v1":
        return {"suite": name, "results": [_object_exact(state_dir), _prompt_cache(state_dir), _advanced_local(state_dir), _load_local(state_dir)]}
    raise ValueError(f"unknown benchmark suite: {name}")


def _object_exact(state_dir: str | Path) -> Dict[str, Any]:
    data = (b"alpha beta gamma\n" * 2048) + b"tail"
    wu = WorkUnit(WorkUnitKind.BYTE_OBJECT, "benchmark", "bench://object-exact-v1", data, namespace="benchmarks")
    baseline_started = time.perf_counter()
    baseline = bytes(data)
    baseline_elapsed = time.perf_counter() - baseline_started
    started = time.perf_counter()
    result = execute_work_unit(wu, state_dir, mode="enforce")
    restored = rehydrate_manifest(result.manifest_id, state_dir)
    elapsed = time.perf_counter() - started
    return {
        "suite": "object-exact-v1",
        "accepted": restored == data,
        "work_unit_id": result.work_unit_id,
        "manifest_id": result.manifest_id,
        "elapsed_seconds": elapsed,
        "baseline_elapsed_seconds": baseline_elapsed,
        "bytes_in": len(data),
        "baseline_bytes": len(baseline),
        "bytes_restored": len(restored),
        "baseline_equal": baseline == data,
    }


def _prompt_cache(state_dir: str | Path) -> Dict[str, Any]:
    request = {
        "model": "auto",
        "messages": [{"role": "system", "content": "Use policy v1"}, {"role": "user", "content": "Summarize reset policy"}],
    }
    started = time.perf_counter()
    first = handle_chat_completion(request, tenant="benchmark", namespace="ai", state_dir=state_dir)
    second = handle_chat_completion(request, tenant="benchmark", namespace="ai", state_dir=state_dir)
    elapsed = time.perf_counter() - started
    return {
        "suite": "prompt-cache-v1",
        "accepted": first["choices"][0]["message"]["content"] == second["choices"][0]["message"]["content"],
        "first_cache": first["urp"]["cache"],
        "second_cache": second["urp"]["cache"],
        "model_calls_avoided": 1 if second["urp"]["cache"] in {"exact_hit", "semantic_hit"} else 0,
        "elapsed_seconds": elapsed,
        "first_manifest_id": first["urp"]["manifest_id"],
        "second_manifest_id": second["urp"]["manifest_id"],
    }


def _advanced_local(state_dir: str | Path) -> Dict[str, Any]:
    lakehouse = recommend_compaction(
        [
            LakehouseFile("s3://table/dt=2026-07-08/part-1.parquet", "dt=2026-07-08", 1024, 10),
            LakehouseFile("s3://table/dt=2026-07-08/part-2.parquet", "dt=2026-07-08", 2048, 20),
            LakehouseFile("s3://table/dt=2026-07-09/large.parquet", "dt=2026-07-09", 512 * 1024 * 1024, 1000),
        ],
        target_file_size=128 * 1024,
    )
    training = dedupe_training_samples(
        [
            TrainingSample("a", "reset the VPN token", {"source": "kb"}),
            TrainingSample("b", "reset the VPN token", {"source": "kb"}),
            TrainingSample("c", "rotate the SSH key", {"source": "kb"}),
        ]
    )
    schedule = schedule_job(FlexibleJob("benchmark", "batch_compute_job", deadline_seconds=3600, carbon_signal=0.95))
    return {
        "suite": "advanced-local-v1",
        "accepted": lakehouse.accepted and training.accepted and not schedule.run_now,
        "lakehouse_groups": len(lakehouse.groups),
        "training_duplicates": len(training.duplicate_map),
        "training_bytes_avoided": training.bytes_avoided,
        "scheduler_shifted_seconds": schedule.shifted_seconds,
    }


def _load_local(state_dir: str | Path) -> Dict[str, Any]:
    state = Path(state_dir)
    object_count = 6
    payload = (b"load line alpha beta gamma\n" * 256) + b"tail"

    ingest_started = time.perf_counter()
    manifests = []
    for index in range(object_count):
        wu = WorkUnit(WorkUnitKind.BYTE_OBJECT, "load", f"bench://load/object/{index}", payload + str(index).encode("ascii"), namespace="load")
        manifests.append(execute_work_unit(wu, state, mode="enforce").manifest_id)
    ingest_elapsed = max(time.perf_counter() - ingest_started, 1e-9)
    bytes_ingested = sum(len(payload) + len(str(index)) for index in range(object_count))

    rehydrate_latencies: List[float] = []
    for manifest_id in manifests:
        started = time.perf_counter()
        restored = rehydrate_manifest(manifest_id, state)
        rehydrate_latencies.append(time.perf_counter() - started)
        if not restored.startswith(b"load line"):
            raise AssertionError("load benchmark rehydration returned unexpected bytes")

    ai_latencies: List[float] = []
    for index in range(12):
        request = {"model": "auto", "messages": [{"role": "user", "content": f"Classify load request {index % 3}"}]}
        started = time.perf_counter()
        handle_chat_completion(request, tenant="load", namespace="ai", state_dir=state)
        ai_latencies.append(time.perf_counter() - started)

    cache = URPCache()
    cache_entries = 256
    cache_payload = {"query": "load-cache"}
    cache_started = time.perf_counter()
    for index in range(cache_entries):
        sources = {f"src-{index}"}
        key = cache.exact_key("load", "cache", {**cache_payload, "index": index}, sources)
        cache.put(CacheEntry(key, "load", "cache", index, sources, True))
    cache_write_elapsed = max(time.perf_counter() - cache_started, 1e-9)
    lookup_started = time.perf_counter()
    cache_hits = 0
    for index in range(cache_entries):
        sources = {f"src-{index}"}
        key = cache.exact_key("load", "cache", {**cache_payload, "index": index}, sources)
        cache_hits += 1 if cache.get(key, "load", "cache", sources) == index else 0
    cache_lookup_elapsed = max(time.perf_counter() - lookup_started, 1e-9)

    manifest_store = FileManifestStore(state / "load-manifests")
    manifest_count = 24
    manifest_started = time.perf_counter()
    for index in range(manifest_count):
        manifest_store.put(
            Manifest(
                work_unit_id=f"wu_load_{index}",
                tenant="load",
                kind=WorkUnitKind.BYTE_OBJECT,
                contract=Contract.EXACT_BYTES,
                logical_ref=f"bench://load/manifest/{index}",
                namespace="load",
                physical={"whole_sha256": "0" * 64, "logical_size": index},
                verification={"accepted": True, "verifier_id": "load_smoke@0"},
            )
        )
    manifest_elapsed = max(time.perf_counter() - manifest_started, 1e-9)

    result = {
        "suite": "load-local-v1",
        "accepted": True,
        "object_ingest": {
            "objects": object_count,
            "bytes": bytes_ingested,
            "elapsed_seconds": ingest_elapsed,
            "objects_per_second": object_count / ingest_elapsed,
            "bytes_per_second": bytes_ingested / ingest_elapsed,
        },
        "rehydration_latency": {
            "operations": len(rehydrate_latencies),
            "p95_seconds": _percentile(rehydrate_latencies, 0.95),
            "max_seconds": max(rehydrate_latencies),
        },
        "ai_gateway_latency": {
            "operations": len(ai_latencies),
            "p95_seconds": _percentile(ai_latencies, 0.95),
            "max_seconds": max(ai_latencies),
        },
        "cache_index_scalability": {
            "entries": cache_entries,
            "hits": cache_hits,
            "write_entries_per_second": cache_entries / cache_write_elapsed,
            "lookup_entries_per_second": cache_entries / cache_lookup_elapsed,
        },
        "manifest_store_write_rate": {
            "manifests": manifest_count,
            "elapsed_seconds": manifest_elapsed,
            "manifests_per_second": manifest_count / manifest_elapsed,
        },
    }
    result["accepted"] = (
        result["object_ingest"]["objects"] == object_count
        and result["rehydration_latency"]["operations"] == object_count
        and result["ai_gateway_latency"]["operations"] == 12
        and result["cache_index_scalability"]["hits"] == cache_entries
        and result["manifest_store_write_rate"]["manifests"] == manifest_count
    )
    return result


def _percentile(values: List[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]
