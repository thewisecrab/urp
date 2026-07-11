# Universal Reduction Plane (URP)

**Status:** complete product and engineering handoff, curated rebuild, no line-count padding  
**Date:** 2026-07-08  
**License target:** Apache-2.0 for the open-source core  
**Audience:** Codex, founding engineers, maintainers, enterprise architects, platform teams, AI infrastructure teams, data engineers, security reviewers, and open-source contributors

URP is one product: a compatibility-first reduction layer for data and AI workloads.

URP does not pretend to be a magical universal compressor. It acknowledges the hard information-theory boundary for exact lossless compression and then builds a practical universal product around that boundary. The product reduces unnecessary bytes, duplicate data, duplicate computation, bloated prompts, wasteful AI routing, redundant training, cold-data over-retention, and peak energy demand while preserving existing application interfaces.

The single sentence:

> URP intercepts every data or AI work unit, assigns a contract, plans the cheapest safe reduction path, executes through pluggable adapters and transforms, verifies the result, records a manifest, and writes an immutable ledger event.

## What this package contains

```text
README.md
URP_COMPLETE_HANDOFF.md
docs/
  00_START_HERE.md
  01_PRODUCT_EXPLAINER.md
  02_IDEAL_STATE_ARCHITECTURE.md
  03_UNIFIED_WORK_UNIT_AND_MANIFEST_MODEL.md
  04_REDUCTION_AND_AI_ALGORITHMS.md
  05_ADAPTER_CATALOG_AND_COMPATIBILITY.md
  06_POLICY_SECURITY_COMPLIANCE.md
  07_APIS_SCHEMAS_PROTOCOLS.md
  08_IMPLEMENTATION_BLUEPRINT_CODEX.md
  09_OBSERVABILITY_BENCHMARKS_OPS.md
  10_RESEARCH_LANDSCAPE.md
  11_OPEN_SOURCE_GOVERNANCE_ADOPTION.md
  12_DEPLOYMENT_PLAYBOOKS.md
codex/
  CODEX_BUILD_PROMPT.md
  ACCEPTANCE_CHECKLIST.md
  ROADMAP_AND_TICKETS.md
specs/
  urp_work_unit.schema.json
  urp_manifest.schema.json
  urp_policy.schema.json
  urp_ledger_event.schema.json
  openapi.yaml
  urp.proto
examples/
  policies/
  docker-compose.yaml
  kubernetes/
  terraform/aws/
src/
  python/urp/        # runnable reference skeleton
  typescript/        # SDK shape
  go/                # SDK shape
tests/
  test_urp_core.py
research/
  research_sources.yaml
```

## The shape of the product

URP has one public product surface:

```text
Application or platform call
  -> URP Gateway
  -> Work Unit classifier
  -> Contract and policy resolver
  -> Universal planner
  -> Reduction executors
  -> Verifiers
  -> Manifest store
  -> Ledger
  -> Existing storage, compute, model, table, stream, or cache backend
```

The same product handles:

- S3 objects and object-compatible storage.
- Filesystems, volumes, backup snapshots, and container images.
- SQL exports, lakehouse row groups, Parquet, Arrow, Iceberg, Delta, Hudi.
- Kafka/Pulsar segments, OpenTelemetry traces, logs, metrics, and time series.
- Media assets, thumbnails, raw captures, derived renditions.
- Embeddings, vector indexes, semantic caches, RAG context packs.
- Chat/completion requests, tool calls, agent steps, batch inference jobs.
- Fine-tuning jobs, LoRA/QLoRA adapters, model checkpoints, evaluation runs.
- Edge devices and local developer workflows.

## What URP is not

URP is not:

- a replacement for databases, object stores, vector databases, or model servers;
- a new universal file format that every application must adopt;
- a data-loss product disguised as compression;
- a model provider;
- a closed control plane;
- a single proprietary appliance;
- a mandate that enterprises rewrite applications.

URP is an overlay and gateway system with adapters.

## Product promises

1. Existing interfaces keep working.
2. Unknown data is stored safely by default.
3. Exact-byte restoration is always available for exact-byte contracts.
4. Semantic or lossy reduction is policy-gated, auditable, reversible when possible, and never silent.
5. Cross-tenant dedupe and cache reuse are disabled by default.
6. Every action produces a manifest and ledger event.
7. Open-source core must be useful without paid SaaS dependencies.
8. Plugins are first-class but constrained by stable contracts and conformance tests.

## Quick local prototype

```bash
cd urp_quality_product_package
PYTHONPATH=src/python python -m unittest discover -s tests -v
python -m urp.cli plan --kind byte_object --input "hello hello hello"
python -m urp.cli plan --kind prompt_request --input "Summarize the VPN reset policy"
```

The prototype is intentionally small. It is a contract and behavior skeleton, not a production engine.

## First enterprise deployment path

1. Run URP in observe-only mode in front of object storage and AI APIs.
2. Collect manifests and ledger events without modifying outputs.
3. Enable exact-byte object dedupe for low-risk buckets.
4. Enable prompt/context telemetry and exact cache for low-risk AI traffic.
5. Enable contract-based reduction policies by team, tenant, bucket, topic, model, and dataset.
6. Turn on semantic caching only after verifier and permission tests pass.
7. Add lakehouse compaction and training-job reduction once governance is stable.
8. Add energy-aware scheduling for flexible batch workloads.

## Maintainer principle

URP should be boring to adopt and aggressive only where policy makes it safe. The winning implementation is transparent, debuggable, reversible, and measurable.
