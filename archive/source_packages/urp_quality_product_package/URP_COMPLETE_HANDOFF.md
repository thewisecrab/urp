# URP Complete Handoff

Generated: 2026-07-08

This combined handoff is assembled from curated package documents. The ZIP is the source of truth for machine-readable schemas, code, tests, and examples.


---

<!-- BEGIN README.md -->

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

<!-- END README.md -->


---

<!-- BEGIN docs/00_START_HERE.md -->

# 00 — Start Here

This document tells a new engineer, contributor, investor, enterprise buyer, or Codex agent how to read the package.

## The correction this package makes

A prior draft used artificial length targets. This package removes arbitrary line-count requirements. The goal is now usefulness, precision, and buildability. Every document has a specific job. Repetition is kept only where it improves standalone readability.

## URP in one paragraph

Universal Reduction Plane is a single open-source product that sits between existing applications and existing infrastructure. It observes or intercepts data and AI work units, determines what must be preserved, applies safe reduction methods, verifies the outcome, records a manifest, and emits audit events. It reduces storage pressure, data movement, AI inference waste, redundant training, cache misses, and peak compute demand while preserving compatibility with S3, POSIX, SQL, lakehouse formats, streams, OpenAI-compatible APIs, model servers, Kubernetes, and developer SDKs.

## The order to read

1. Product explainer for market, user, and value.
2. Ideal-state architecture for the final system.
3. Work unit and manifest model for the universal abstraction.
4. Reduction and AI algorithms for the core technical engine.
5. Adapter catalog for platform compatibility.
6. Policy/security/compliance for safe enterprise adoption.
7. APIs/schemas/protocols for implementation.
8. Codex blueprint for build tasks.
9. Observability and benchmarks for proving value.
10. Research landscape for grounding decisions.
11. Open-source governance and adoption.
12. Deployment playbooks.

## The central design decision

Do not split URP into a "data plane" and an "AI plane" product. There is only one URP. The internal modules can be separated for code organization, but the product abstraction is singular:

```text
Work Unit + Contract + Policy -> Plan -> Execute -> Verify -> Manifest + Ledger
```

The same lifecycle applies to a 16 MiB object chunk, a Parquet row group, a stream segment, a prompt request, an embedding batch, an adapter training run, and a model checkpoint.

## What to build first

Build the thin vertical slice that proves the universal model:

- Accept a work unit.
- Classify it.
- Resolve a policy.
- Produce a plan.
- Execute simple exact-safe transforms.
- Verify restoration.
- Store a manifest.
- Emit ledger events.
- Expose metrics.
- Provide SDK and CLI usage.

The first production-capable target should be:

```text
S3-compatible object gateway + OpenAI-compatible AI gateway + shared manifest/ledger/policy system
```

That is enough to prove URP as one product, not a collection of isolated optimizers.

## Repository quality bar

A contributor should be able to:

- run tests locally;
- inspect a manifest;
- understand why URP made a decision;
- disable any reducer;
- run in observe-only mode;
- write a plugin without changing core code;
- see reduction ratios, cache hit rates, and verifier results;
- compare URP outputs against baseline infrastructure;
- perform a clean rollback.


## Core glossary

| Term | Meaning |
|---|---|
| URP | Universal Reduction Plane, one product that reduces storage, data movement, AI compute, training waste, inference waste, and peak energy demand without forcing application rewrites. |
| Work Unit | The universal input abstraction. A work unit may be a file, object, row group, stream segment, media asset, prompt, embedding request, batch inference job, model checkpoint, fine-tuning job, cache entry, or agent step. |
| Contract | The compatibility and quality promise for a work unit. It tells URP what must be preserved and what may be changed. |
| Manifest | The durable record that maps a logical work unit to physical chunks, transforms, cache entries, model routes, summaries, lineage, checksums, and policy decisions. |
| Ledger | Append-only audit trail of every classification, policy decision, transform, cache hit, AI route, verification result, restore, deletion, and override. |
| Exact Bytes | Readback must return byte-for-byte identical content. This is the default for unknown or regulated data. |
| Exact Logical | Readback must return equivalent rows, records, messages, frames, or values, but physical layout can change. |
| Bounded Approximation | URP may reduce fidelity within explicitly measured error bounds. |
| Semantic | URP may preserve meaning instead of raw bytes, only when policy allows it. |
| Tombstone | Raw content was intentionally deleted or expired; lineage, deletion proof, and minimal metadata remain. |
| Rehydration | Reconstructing the logical view from manifest, chunks, transforms, cache records, or derived artifacts. |
| Reduction Proof | Metadata proving why a reduction is safe: checksums, sample entropy, transform identity, verifier output, policy id, and lineage. |

<!-- END docs/00_START_HERE.md -->


---

<!-- BEGIN docs/01_PRODUCT_EXPLAINER.md -->

# 01 — Product Explainer

## Product name

**Universal Reduction Plane (URP)**

URP is one product that reduces unnecessary data and AI infrastructure demand without requiring application rewrites.

The product is deliberately named a plane, not a codec, database, or AI model. The word "plane" means URP is a cross-cutting layer that can be inserted into existing architecture through gateways, adapters, SDKs, sidecars, proxies, storage engines, and batch integrations.

## Product thesis

Organizations are running into two related scaling problems:

1. They store and move too much data because systems treat all bytes as equally valuable.
2. They spend too much AI compute because systems treat all model calls as equally difficult.

URP solves both through one abstraction. Everything becomes a **work unit** with a **contract** and **policy**. URP then decides the least expensive safe way to satisfy the contract.

## The problem in human terms

An enterprise may have:

- duplicate backups across teams;
- object stores full of raw logs never read after seven days;
- Parquet datasets with redundant columns and poor file layout;
- event streams that preserve every normal heartbeat forever;
- media files stored in too many resolutions without lineage;
- vector databases with duplicate or stale embeddings;
- AI prompts that send entire documents when three paragraphs are relevant;
- repeated AI questions answered again and again by expensive models;
- fine-tunes that could have been adapters;
- model checkpoints stored as full copies instead of deltas;
- batch AI jobs running during expensive grid peaks.

Each issue is usually handled by a different tool. URP unifies the operating model.

## Buyer promise

URP gives platform teams a single control surface for reducing:

- storage footprint;
- network egress;
- read/write I/O;
- AI prompt tokens;
- AI completion tokens;
- KV-cache memory;
- redundant model calls;
- redundant training steps;
- model artifact duplication;
- peak GPU demand;
- peak power demand;
- audit uncertainty.

## User promise

A developer should not have to become a compression expert, storage engineer, ML systems engineer, and compliance officer to reduce waste.

URP gives developers:

- a simple API;
- safe defaults;
- local tooling;
- observable decisions;
- policy-defined guardrails;
- compatibility with existing tools;
- a way to mark intent without changing storage or AI providers.

## Product personas

### Platform engineer

Wants fewer infrastructure surprises, consistent telemetry, safe rollout, and a way to enforce policies across object storage, AI APIs, and data pipelines.

URP value:

- observe-only rollout;
- policy-as-code;
- conformance tests;
- SLO dashboards;
- resource savings by team and service.

### Data engineer

Wants lakehouse, stream, and object datasets to be smaller and faster without breaking schemas.

URP value:

- logical contracts;
- table-aware compaction recommendations;
- row-group and partition optimization;
- manifest lineage;
- retention and summarization policies.

### AI platform engineer

Wants to reduce large-model calls, prompt length, duplicated inference, and repeated fine-tunes.

URP value:

- model routing;
- exact and semantic caching;
- context compiler;
- adapter registry;
- training reducer;
- verifier-aware fallback.

### Security and compliance officer

Wants proof that reductions do not violate retention, privacy, legal hold, or audit requirements.

URP value:

- deny-by-default for semantic reduction;
- immutable ledger events;
- policy versioning;
- manifest signing;
- legal hold support;
- explainable reduction proof.

### Startup developer

Wants a simple way to reduce cloud bills before hiring a platform team.

URP value:

- Docker quickstart;
- OpenAI-compatible proxy;
- S3-compatible gateway;
- CLI;
- sane defaults.

### Open-source contributor

Wants clear extension points and not a maze of enterprise-only features.

URP value:

- plugin contracts;
- conformance suite;
- public roadmap;
- stable manifest spec;
- Apache-2.0 core.

## Why one product matters

Splitting data reduction and AI reduction into separate products would create duplicated policy engines, duplicated manifests, duplicated telemetry, duplicated identity models, and conflicting lifecycle decisions.

A prompt request and a Parquet row group are different payloads, but both need:

- identity;
- classification;
- contract;
- policy;
- plan;
- execution;
- verification;
- manifest;
- ledger;
- telemetry;
- rollback.

The unified lifecycle is the product.

## Core product surface

URP exposes five surfaces:

1. **Gateway surface** for existing systems.
2. **Policy surface** for administrators.
3. **Developer surface** through SDKs, CLI, and annotations.
4. **Plugin surface** for transforms, classifiers, adapters, verifiers, and routers.
5. **Observability surface** for metrics, traces, manifests, and ledger events.

## What an enterprise sees

An enterprise deployment might start like this:

```text
Existing app -> URP S3 Gateway -> Existing S3 bucket
Existing app -> URP AI Gateway -> Existing model provider
Existing batch job -> URP Scheduler -> Existing Kubernetes/Ray/Slurm
Existing lakehouse -> URP Optimizer -> Existing object store and table catalog
```

Nothing in the first rollout requires changing application logic.

## Product modes

### Observe mode

URP classifies work units, estimates savings, records planned actions, but does not alter outputs.

Use observe mode to build trust.

### Shadow mode

URP performs reductions in parallel and compares outputs, but the original path remains authoritative.

Use shadow mode to validate correctness and benchmark latency.

### Exact-safe mode

URP enables only exact-byte or exact-logical transformations.

Use exact-safe mode for the first production deployment.

### Policy-expanded mode

URP enables semantic, approximate, lifecycle, and AI routing policies where owners explicitly allow them.

Use this mode after governance is mature.

### Autonomous optimization mode

URP recommends and applies low-risk optimizations within explicit SLO, budget, compliance, and rollback constraints.

Use this only after months of verified telemetry.

## Product packaging

### Open-source core

The open-source core should include:

- work unit model;
- manifest schema;
- ledger schema;
- policy engine;
- local manifest store;
- object gateway reference implementation;
- OpenAI-compatible gateway reference implementation;
- exact cache;
- basic semantic cache;
- chunking and compression plugins;
- context compiler baseline;
- model router baseline;
- CLI and SDKs;
- conformance tests;
- dashboards and metrics examples.

### Enterprise extensions without weakening OSS

Enterprise vendors may offer:

- managed control plane;
- advanced compliance packs;
- policy approval workflows;
- managed connectors;
- premium dashboards;
- certified integrations;
- 24/7 support;
- fleet automation.

The open-source project should remain fully usable without these.

## The adoption ladder

| Stage | What is enabled | Risk | Value |
|---|---|---:|---:|
| 0 | Local CLI and SDK | Low | Developer education |
| 1 | Observe-only gateway | Very low | Savings discovery |
| 2 | Exact object dedupe/compression | Low | Storage savings |
| 3 | Prompt/context telemetry | Low | AI cost visibility |
| 4 | Exact AI cache | Low | Repeated-call savings |
| 5 | Semantic cache with verifiers | Medium | Major inference savings |
| 6 | Lakehouse/stream optimization | Medium | Data platform savings |
| 7 | Model routing and distillation | Medium | GPU demand reduction |
| 8 | Energy-aware scheduling | Medium | Peak reduction |
| 9 | Autonomous recommendations | Higher | Continuous optimization |

## What "works across all data types" means

It does not mean the same transform applies to every type. It means the same control system applies to every type.

For unknown bytes, URP can still:

- identify;
- hash;
- chunk;
- dedupe;
- estimate entropy;
- compress if useful;
- store exact;
- produce a manifest;
- record policy decisions.

For known structures, URP can do more:

- table-aware layout;
- log templates;
- stream compaction;
- media transcoding;
- vector quantization;
- prompt compression;
- model routing;
- training data selection.

Universal control does not require universal transformation.

## Product principles

### Compatibility before cleverness

No savings matter if adoption requires rewriting production applications.

### Exact by default

Unknown, regulated, encrypted, or high-risk data gets exact-byte treatment unless policy says otherwise.

### Semantic reduction is explicit

Summaries, approximations, downsampling, vector quantization, and model distillation must be policy-visible.

### Every decision is explainable

URP must answer: "Why did you do this, who allowed it, how do we reverse it, and what did it save?"

### Reduction is a lifecycle, not a one-time compression event

Data and AI workloads age. Hot data may be exact and fast. Warm data may be exact but compressed. Cold data may become summaries or tombstones. Repeated AI workloads may become cache entries, then small models, then tools.

## Example product story: support AI

Before URP:

```text
Every support question sends full policy docs to a large model.
```

After URP:

```text
URP compiles context from relevant policy sections.
URP checks exact cache.
URP checks semantic cache constrained by tenant and source version.
URP routes easy questions to a small support model.
URP verifies the answer against cited source snippets.
URP calls the large model only for novel or high-risk questions.
URP records a compute manifest and ledger event.
```

## Example product story: observability logs

Before URP:

```text
Every service emits verbose logs retained raw for one year.
```

After URP:

```text
URP stores hot logs exactly.
URP extracts templates and variable fields.
URP dedupes recurring normal events.
URP keeps anomalies raw.
URP stores rollups and sketches for normal periods.
URP expires raw debug logs after policy.
URP preserves lineage and legal holds.
```

## Example product story: model checkpoints

Before URP:

```text
Every training run writes huge full checkpoints.
```

After URP:

```text
URP identifies checkpoint lineage.
URP stores base checkpoint once.
URP stores deltas for later checkpoints.
URP dedupes optimizer-state chunks.
URP keeps adapter weights separately.
URP applies retention policies to failed experiments.
URP records reproducibility metadata.
```

## Competitive positioning

URP is adjacent to but not the same as:

- backup dedupe products;
- object lifecycle management;
- lakehouse optimizers;
- prompt caches;
- AI gateways;
- inference runtimes;
- observability tools;
- MLOps platforms;
- data catalogs.

URP should interoperate with these rather than replace them. Its differentiated value is the shared universal policy, manifest, and planning layer.

## Product success metrics

URP should report:

- storage bytes avoided;
- logical bytes preserved;
- data movement avoided;
- prompt tokens avoided;
- output tokens avoided;
- large-model calls avoided;
- cache hit rates;
- small-model acceptance rate;
- verifier failure rate;
- training GPU hours avoided;
- checkpoint bytes avoided;
- peak compute shifted;
- policy violations blocked;
- restore success rate;
- customer-facing error rate;
- p50/p95/p99 overhead.

## Pricing strategy for a commercial ecosystem

For open-source adoption, the core must be free and useful.

Commercial packaging can charge for:

- managed control plane;
- enterprise support;
- policy governance workflows;
- SaaS telemetry;
- certified compliance packs;
- hosted gateways;
- advanced optimization plugins;
- benchmark certification.

Avoid pricing directly against savings in a way that makes users distrust reported savings.

## Product risks

### Silent data loss

Mitigation: exact default, policy gates, verifiers, restore tests, manifest signatures.

### Latency overhead

Mitigation: observe mode, hot-path bypass, async planning, caches, local manifests, fast exact paths.

### Vendor lock-in concerns

Mitigation: open specs, Apache-2.0 core, portable manifests, exported ledger, pluggable backends.

### Security side channels

Mitigation: tenant isolation, no cross-tenant dedupe by default, cache ACLs, encrypted manifests.

### Complexity

Mitigation: one product, one lifecycle, conservative defaults, staged adoption, strong docs.

## Ideal customer journey

Day 1:

- deploy Docker gateway in observe mode;
- route one dev bucket and one AI dev API key through URP;
- inspect manifests and savings estimates.

Week 1:

- enable exact object dedupe for non-production bucket;
- enable exact prompt cache for internal dev assistant;
- add OpenTelemetry export.

Month 1:

- production observe mode for selected teams;
- exact-safe mode for logs and backups;
- semantic cache pilot for support AI with verifiers.

Quarter 1:

- policy-as-code rollout;
- lakehouse optimizer;
- model router;
- training reducer;
- executive dashboards.

Year 1:

- URP becomes the reduction control layer across data and AI infrastructure.

## Product FAQ

### Does URP compress everything?

No. URP reduces what can be safely reduced and falls back to exact storage or exact computation when reduction is not safe.

### Does URP replace S3?

No. It can expose S3-compatible APIs and store physical chunks in S3 or compatible stores.

### Does URP replace model providers?

No. It routes, caches, compiles context, verifies, and optimizes calls to existing providers and model servers.

### Can URP run on-prem?

Yes. It should be designed for local-only, on-prem, private cloud, public cloud, hybrid, and edge deployments.

### Can URP be adopted by a single developer?

Yes. The CLI and local gateway should be useful for small teams.

### Can semantic reduction be disabled globally?

Yes. Exact-safe mode must be a first-class configuration.

### How does URP avoid vendor lock-in?

By making the manifest, ledger, policy model, plugin API, conformance tests, and SDKs open.

## Product north star

The north-star metric is:

```text
verified useful output per joule, byte, and dollar
```

The product should optimize usefulness under contracts, not blindly minimize bytes.

<!-- END docs/01_PRODUCT_EXPLAINER.md -->


---

<!-- BEGIN docs/02_IDEAL_STATE_ARCHITECTURE.md -->

# 02 — Ideal-State Architecture

## Architecture goal

URP should be deployable as a single product that gradually spans all data and AI workflows without becoming a monolith internally.

The ideal state is a modular, plugin-driven, policy-governed plane with a stable external product surface.

## Ideal-state diagram

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Existing users, applications, agents, workflows, jobs, and pipelines  │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
                                   v
┌──────────────────────────────────────────────────────────────────────┐
│ URP Compatibility Gateways                                           │
│ S3 | POSIX | SQL | Lakehouse | Kafka | OTLP | OpenAI API | Batch API  │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
                                   v
┌──────────────────────────────────────────────────────────────────────┐
│ URP Core Control Surface                                             │
│ Work Unit intake | Classification | Contracts | Policies | Planning   │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
                                   v
┌──────────────────────────────────────────────────────────────────────┐
│ URP Execution Fabric                                                 │
│ Chunks | Compression | Dedupe | Context | Cache | Routing | Scheduler │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
                                   v
┌──────────────────────────────────────────────────────────────────────┐
│ URP Verification, Manifest, Ledger, and Telemetry                    │
│ Restore checks | Verifiers | Manifests | Events | Metrics | Traces     │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
                                   v
┌──────────────────────────────────────────────────────────────────────┐
│ Existing infrastructure                                              │
│ Object stores | DBs | Warehouses | Streams | GPUs | Model providers   │
└──────────────────────────────────────────────────────────────────────┘
```

## One lifecycle

Every work unit follows the same lifecycle:

```text
1. Receive
2. Identify
3. Classify
4. Resolve contract
5. Resolve policy
6. Estimate reducibility
7. Plan actions
8. Execute actions
9. Verify contract
10. Write manifest
11. Emit ledger event
12. Serve reads or results
13. Re-evaluate over lifecycle
```

A simple byte object and a complex AI prompt use the same lifecycle. The actions differ.

## Layer 1: Compatibility gateways

Gateways make URP adoptable.

### S3-compatible gateway

Responsibilities:

- expose S3-compatible object APIs;
- preserve bucket/key semantics;
- handle multipart uploads;
- map object writes to work units;
- support range reads through rehydration;
- preserve metadata and tags;
- support lifecycle tags;
- expose compatibility conformance tests.

### POSIX/filesystem gateway

Responsibilities:

- expose mounted filesystem or CSI volume;
- preserve path, stat, permissions, and rename semantics where possible;
- support transparent compression and dedupe;
- avoid surprising latency on hot files;
- provide opt-in exact-safe mode for production.

### SQL and CDC gateway

Responsibilities:

- observe writes through change data capture;
- classify table data;
- recommend or apply logical optimization;
- store row group manifests;
- respect schema evolution;
- avoid violating transaction semantics.

### Lakehouse adapter

Responsibilities:

- operate on table metadata and object files;
- integrate with Iceberg/Delta/Hudi catalogs;
- propose compaction and clustering plans;
- maintain snapshot lineage;
- avoid table corruption by using native transaction protocols.

### Stream adapter

Responsibilities:

- consume stream segments;
- classify event schemas;
- dedupe repeated events;
- extract templates;
- produce compacted topics where allowed;
- preserve replay semantics for exact contracts.

### AI API gateway

Responsibilities:

- expose OpenAI-compatible endpoints;
- preserve client behavior;
- classify requests;
- cache safe results;
- compile context;
- route to models/tools;
- verify outputs;
- log compute manifests.

### Batch and training gateway

Responsibilities:

- accept fine-tune, evaluation, embedding, and batch inference jobs;
- dedupe datasets;
- choose adapter-based paths where possible;
- schedule flexible jobs by policy;
- capture reproducibility metadata.

## Layer 2: Work unit intake

The intake service normalizes every request into a work unit envelope:

```json
{
  "work_unit_id": "wu_...",
  "kind": "prompt_request",
  "tenant": "tenant_a",
  "logical_ref": "openai://chat/completions/request/...",
  "payload_ref": "inline_or_blob_ref",
  "metadata": {},
  "requested_contract": "semantic",
  "policy_context": {}
}
```

Intake must be fast and side-effect-light. It should be possible to run classification asynchronously in observe mode.

## Layer 3: Classifier

The classifier produces structured hints, not irreversible decisions.

Classification dimensions:

- payload kind;
- compression/encryption status;
- structured/unstructured status;
- media type;
- schema availability;
- entropy estimate;
- duplicate likelihood;
- semantic risk;
- privacy class;
- compliance tags;
- read/write temperature;
- AI task category;
- model difficulty estimate;
- latency sensitivity.

Classifiers must be pluggable and versioned.

## Layer 4: Contract resolver

The contract resolver answers:

```text
What must URP preserve?
```

Contracts can come from:

- explicit API parameters;
- bucket tags;
- table properties;
- namespace defaults;
- policy-as-code;
- detected data class;
- legal hold;
- user role;
- application identity;
- deployment mode.

The resolver must choose the strictest applicable contract unless policy explicitly allows relaxation.

## Layer 5: Policy engine

The policy engine answers:

```text
What is URP allowed to do?
```

It evaluates:

- identity;
- tenant;
- data class;
- workload kind;
- contract;
- environment;
- retention;
- legal hold;
- geographic placement;
- encryption domain;
- cache sharing domain;
- model allowlist;
- transform allowlist;
- verifier requirements;
- risk appetite;
- override approvals.

Policy must be deterministic and auditable.

## Layer 6: Planner

The planner turns classification, contract, and policy into an execution plan.

A plan is not just a list of transforms. It includes:

- action sequence;
- expected savings;
- latency budget impact;
- risk rating;
- required verifiers;
- fallback path;
- rehydration path;
- cache policy;
- ledger fields;
- rollback instructions.

Example plan for a byte object:

```text
hash_whole_object
content_defined_chunk
dedupe_chunks
compress_new_chunks_with_zstd
store_manifest
verify_sample_restore
emit_ledger
```

Example plan for an AI request:

```text
normalize_prompt
check_exact_cache
check_semantic_cache_with_acl
retrieve_context
dedupe_context
route_to_small_model
verify_with_sources
fallback_to_large_model_if_needed
cache_accepted_answer
emit_compute_manifest
```

## Layer 7: Execution fabric

Execution is separated from planning so that plans can be inspected and approved.

Execution engines:

- content-addressed storage engine;
- transform runtime;
- AI gateway runtime;
- cache runtime;
- table optimizer;
- stream processor;
- training reducer;
- energy-aware scheduler;
- verifier runtime.

Executors must report action-level telemetry.

## Layer 8: Manifest store

The manifest store is the durable truth of how logical work units map to physical representations or computed outputs.

Requirements:

- append-friendly updates;
- versioned manifests;
- immutable record snapshots;
- lookup by logical ref;
- lookup by work unit id;
- lookup by hash;
- exportable JSON;
- signature support;
- compatibility across backends.

Backends:

- embedded SQLite for local mode;
- Postgres for production control plane;
- object storage for large manifests;
- cloud-native metadata stores through adapters.

## Layer 9: Ledger

The ledger is append-only. It should be tamper-evident in production.

Ledger events include:

- work unit received;
- classification completed;
- policy evaluated;
- plan created;
- action executed;
- verifier passed or failed;
- manifest written;
- cache hit;
- model routed;
- fallback invoked;
- semantic transform applied;
- deletion/tombstone issued;
- legal hold applied;
- override approved.

Ledger events are distinct from application logs. They are governance artifacts.

## Layer 10: Unified cache

The cache is shared conceptually across data and AI, but partitioned by safety domains.

Cache forms:

- exact byte cache;
- chunk cache;
- transform output cache;
- prompt exact cache;
- semantic response cache;
- retrieval-context cache;
- tool-result cache;
- embedding cache;
- prefix/KV cache metadata;
- training artifact cache.

Each cache entry must have:

- key;
- tenant;
- policy domain;
- source fingerprint;
- contract;
- freshness window;
- invalidation rule;
- verifier status;
- permitted consumers;
- manifest reference.

## Layer 11: Verifier registry

Verifiers decide whether a reduced or generated result satisfies the contract.

Verifier examples:

- byte checksum verifier;
- logical row-count/schema verifier;
- table snapshot verifier;
- approximate error-bound verifier;
- media quality verifier;
- prompt source-consistency verifier;
- code test verifier;
- SQL result verifier;
- policy citation verifier;
- safety verifier;
- model output schema verifier.

A verifier failure must trigger fallback, not silent acceptance.

## Layer 12: Scheduler

The scheduler decides when and where to execute flexible work.

Inputs:

- deadline;
- priority;
- tenant quota;
- data locality;
- GPU/CPU availability;
- storage locality;
- electricity price;
- carbon intensity signal;
- cooling constraints;
- reliability zone;
- cost target.

The scheduler is optional at first but essential in ideal state.

## Layer 13: Plugin system

Plugins are necessary for broad adoption.

Plugin types:

- classifier;
- transform;
- verifier;
- adapter;
- router;
- cache backend;
- manifest backend;
- policy data source;
- scheduler signal;
- observability exporter.

Plugin requirements:

- versioned interface;
- capability declaration;
- risk level;
- deterministic mode where possible;
- sandbox option;
- conformance tests;
- security review metadata.

## Deployment topologies

### Local developer

```text
CLI + embedded manifest store + local cache + optional model API proxy
```

### Startup

```text
Docker Compose: gateway + control service + SQLite/Postgres + object store backend
```

### Enterprise single cloud

```text
Kubernetes deployment + managed Postgres + cloud object store + model providers
```

### Enterprise hybrid

```text
Regional gateways + central policy control + local manifests + replicated ledger
```

### Regulated on-prem

```text
Air-gapped deployment + local model servers + local object storage + signed policies
```

### Edge

```text
Small sidecar + local policy cache + local exact cache + delayed ledger sync
```

## High availability model

URP must fail safely.

Failure modes:

- fail open for observe-only telemetry if configured;
- fail closed for regulated writes if policy requires;
- bypass reduction and store exact when planner is unavailable;
- return cached exact data only if manifest verification passes;
- prevent semantic cache use if policy or source fingerprints are unavailable;
- degrade to baseline provider if AI router fails.

## Control plane versus hot path

The hot path must be small:

```text
intake -> fast policy cache -> fast plan -> execute safe actions -> return
```

Heavy functions should be asynchronous where possible:

- deep classification;
- dedupe index compaction;
- semantic similarity indexing;
- distillation dataset building;
- table optimization;
- training reduction;
- lifecycle reclassification.

## Data locality

URP should avoid moving data just to reduce it.

Principles:

- classify near source;
- chunk near source;
- cache near consumer;
- store manifests centrally but allow regional replicas;
- run model routing near model endpoint;
- schedule jobs where data already lives when possible.

## Ideal-state user interface

URP should offer:

- CLI;
- REST API;
- gRPC API;
- OpenAI-compatible endpoint;
- S3-compatible endpoint;
- admin dashboard;
- policy editor;
- manifest explorer;
- ledger query tool;
- savings explorer;
- plugin registry;
- conformance test runner.

## Ideal-state admin questions

An admin should be able to answer:

- Which teams generate the most reducible work?
- Which buckets are still storing duplicate data?
- Which AI applications send the most wasted context?
- Which workloads repeatedly escalate to the largest model?
- Which cache entries are blocked by policy?
- Which semantic reductions occurred last week?
- Which work units are under legal hold?
- Which plugins are active in production?
- Which optimizations caused latency regressions?
- Which workloads can be shifted away from peak demand?

## Ideal-state developer questions

A developer should be able to answer:

- Why did my request route to this model?
- Why was semantic cache rejected?
- What source fingerprints were used?
- Can I require exact-byte restoration?
- Can I mark this job as flexible for scheduling?
- How much prompt context did URP remove?
- What contract does this work unit have?
- What policy blocked this transform?

## Ideal-state security questions

Security should be able to answer:

- Did any cross-tenant dedupe occur?
- Which caches are tenant isolated?
- Which manifest fields are encrypted?
- Which plugins can see plaintext?
- Which work units used semantic reduction?
- Which legal holds blocked lifecycle deletion?
- Which keys protect which chunk domains?
- Can a user infer another tenant's data through cache timing?

## Non-negotiable architecture invariants

1. Work units are the universal abstraction.
2. Contracts are explicit and enforced.
3. Policies are versioned and auditable.
4. Unknown data defaults to exact preservation.
5. Manifests are portable and exportable.
6. Ledger events are append-only.
7. Verifiers are required for non-trivial reductions.
8. Plugins cannot silently weaken contracts.
9. Cross-tenant reuse is off by default.
10. Rollback must be designed before optimization is enabled.

## Final ideal state

In the ideal state, URP becomes an operating layer for infrastructure efficiency. It is not visible to most end users, but platform teams rely on it the way they rely on identity, observability, and CI/CD.

The product succeeds when enterprises can adopt it incrementally, developers can understand it quickly, and open-source contributors can extend it safely.

<!-- END docs/02_IDEAL_STATE_ARCHITECTURE.md -->


---

<!-- BEGIN docs/03_UNIFIED_WORK_UNIT_AND_MANIFEST_MODEL.md -->

# 03 — Unified Work Unit and Manifest Model

## Purpose

The work unit model is the heart of URP. It is the reason URP can remain one product across files, tables, streams, prompts, embeddings, model artifacts, and training jobs.

A work unit is not a data format. It is a governance envelope around something that may consume storage, compute, network, or energy.

## Minimal work unit

```json
{
  "id": "wu_01J...",
  "kind": "byte_object",
  "tenant": "acme",
  "logical_ref": "s3://logs-prod/service-a/2026/07/08/part-0001.gz",
  "contract": "exact_bytes",
  "metadata": {
    "owner": "observability",
    "environment": "prod"
  }
}
```

## Full work unit fields

| Field | Required | Description |
|---|---:|---|
| id | Yes | Globally unique work unit id. |
| kind | Yes | Workload kind such as byte_object, prompt_request, table_snapshot, stream_segment, training_job. |
| tenant | Yes | Isolation and billing domain. |
| namespace | Recommended | Team, project, app, bucket, table, topic, or model namespace. |
| logical_ref | Yes | Existing-world reference that applications understand. |
| payload_ref | Conditional | Inline bytes, object reference, stream offset, prompt body ref, dataset ref, or artifact pointer. |
| requested_contract | Optional | Explicit contract requested by caller. |
| effective_contract | Filled by URP | Strictest resolved contract after policy. |
| metadata | Yes | Tags, owner, environment, schema hints, source fingerprints. |
| policy_context | Yes | Identity, legal hold, regulatory tags, risk class, region. |
| deadline | Optional | For scheduling. |
| latency_budget_ms | Optional | For online AI or hot reads. |
| quality_target | Optional | For bounded approximate or semantic workloads. |
| created_at | Yes | Intake timestamp. |
| trace_id | Optional | Distributed tracing correlation id. |

## Work unit kinds

### Data-oriented kinds

- `byte_object`
- `file`
- `directory_snapshot`
- `block_extent`
- `backup_snapshot`
- `container_layer`
- `structured_file`
- `table_snapshot`
- `table_row_group`
- `stream_segment`
- `event_batch`
- `metric_series`
- `trace_batch`
- `log_batch`
- `media_asset`
- `image_asset`
- `video_asset`
- `audio_asset`
- `document_asset`
- `vector_index_segment`

### AI-oriented kinds

- `prompt_request`
- `completion_response`
- `chat_session`
- `agent_step`
- `tool_call`
- `embedding_request`
- `embedding_batch`
- `rag_context_pack`
- `fine_tune_job`
- `training_dataset`
- `evaluation_job`
- `model_checkpoint`
- `adapter_artifact`
- `inference_batch`
- `kv_cache_segment`
- `synthetic_data_job`

### Energy and lifecycle kinds

- `batch_compute_job`
- `lifecycle_transition`
- `deletion_candidate`
- `rehydration_request`
- `policy_override`
- `plugin_action`

The taxonomy should be extensible. New kinds must not break old manifests.

## Contract taxonomy

### exact_bytes

Readback or replay must return byte-for-byte identical payload.

Allowed actions:

- whole-object hashing;
- content-defined chunking;
- dedupe inside allowed domain;
- lossless compression;
- encryption;
- physical relocation;
- exact restore verification.

Disallowed unless separately proven exact:

- lossy transcoding;
- summarization;
- downsampling;
- schema coercion;
- semantic-only storage.

### exact_logical

The logical content must be equivalent, but physical layout can change.

Allowed actions:

- columnar conversion;
- row group compaction;
- dictionary encoding;
- partition rewrite through table protocol;
- lossless schema evolution;
- stream segment repacking;
- log template plus variables if exact reconstruction is possible.

### bounded_approx

The output may differ within explicit error bounds.

Allowed actions:

- quantization;
- downsampling;
- approximate indexes;
- lossy media transcode;
- sketching;
- top-k preservation;
- approximate nearest-neighbor compression.

Required:

- metric definition;
- error bound;
- verifier;
- rollback or raw retention window where policy requires.

### semantic

Meaning is preserved for a task, not necessarily original bytes.

Allowed actions:

- summaries;
- extracted facts;
- embeddings;
- intent-preserving prompt compression;
- semantic cache;
- small-model substitution;
- distillation;
- RAG context reduction.

Required:

- source fingerprints;
- policy approval;
- freshness;
- verifier;
- audit event;
- clear user-facing behavior when relevant.

### derived

The work unit is derived from other work units.

Examples:

- thumbnail;
- aggregate;
- summary;
- vector;
- fine-tune adapter;
- distilled model;
- compacted stream.

Required:

- lineage;
- source manifest ids;
- regeneration instructions when possible.

### tombstone

Raw data was deleted or expired.

Required:

- deletion policy id;
- time;
- actor/system;
- legal hold state;
- minimum metadata;
- proof or attestation when backend supports it.

## Contract resolution

URP must always choose the safest effective contract.

Resolution order:

1. legal hold or compliance block;
2. explicit caller contract;
3. namespace policy;
4. data classification default;
5. tenant default;
6. global default.

If multiple rules apply, the stricter contract wins unless an approved exception exists.

## Manifest purpose

A manifest is a durable explanation of how URP represents a work unit.

For data work units, it maps logical bytes or logical records to physical chunks and transforms.

For AI work units, it maps a logical request to cache lookups, context transformations, model routes, verifier outputs, and result provenance.

For training work units, it maps datasets, adapters, base models, checkpoints, evaluations, and schedules.

## Manifest top-level fields

```json
{
  "manifest_version": "urp.manifest.v1",
  "manifest_id": "mf_...",
  "work_unit_id": "wu_...",
  "logical_ref": "s3://bucket/key",
  "kind": "byte_object",
  "tenant": "acme",
  "contract": "exact_bytes",
  "state": "active",
  "created_at": "2026-07-08T00:00:00Z",
  "policy": {},
  "classification": {},
  "plan": {},
  "physical": {},
  "verification": {},
  "lineage": {},
  "telemetry": {}
}
```

## Manifest sections

### identity

- manifest id;
- work unit id;
- logical ref;
- tenant;
- namespace;
- version;
- trace id.

### classification

- classifier id and version;
- detected kind;
- entropy estimate;
- schema hints;
- compression hints;
- encryption hints;
- privacy class;
- AI task category;
- confidence scores.

### policy

- policy bundle id;
- policy rules matched;
- effective contract;
- allowed transforms;
- denied transforms;
- retention decision;
- cache domain;
- legal hold;
- override id.

### plan

- planner id and version;
- action list;
- risk rating;
- expected savings;
- fallback path;
- required verifiers.

### physical representation

For data:

- chunk refs;
- offsets;
- transform stacks;
- checksums;
- original size;
- stored size;
- compression ratio;
- dedupe domain.

For AI:

- normalized prompt hash;
- semantic key;
- context pack id;
- model route;
- tool calls;
- cache hits;
- output hash;
- source fingerprints.

For training:

- dataset manifests;
- base model;
- adapter ids;
- optimizer-state policy;
- checkpoint deltas;
- evaluation manifests.

### verification

- verifier ids;
- verifier versions;
- results;
- sample restore status;
- error bounds;
- fallback status;
- acceptance timestamp.

### lineage

- source work units;
- derived work units;
- superseded manifests;
- source fingerprints;
- regeneration recipe.

### telemetry

- input bytes;
- stored bytes;
- avoided bytes;
- input tokens;
- avoided tokens;
- model calls avoided;
- GPU seconds avoided;
- latency overhead;
- cache hit/miss;
- energy estimate where available.

## Manifest states

```text
planned
executing
active
superseded
rehydrating
failed
quarantined
expired
tombstoned
```

State changes must emit ledger events.

## Ledger event model

Ledger events are immutable facts.

Event categories:

- intake;
- classification;
- policy;
- planning;
- execution;
- verification;
- manifest;
- cache;
- model;
- scheduler;
- lifecycle;
- security;
- override;
- error.

Example:

```json
{
  "event_id": "evt_...",
  "event_type": "policy.evaluated",
  "work_unit_id": "wu_...",
  "manifest_id": "mf_...",
  "tenant": "acme",
  "policy_bundle_id": "pb_2026_07_08",
  "decision": "allow_exact_lossless",
  "denied": ["semantic_summary", "cross_tenant_cache"],
  "actor": "urp-policy-engine",
  "created_at": "2026-07-08T00:00:01Z"
}
```

## Reduction proof

A reduction proof should answer:

- What was the original logical item?
- What contract applied?
- What policy allowed the action?
- What transform ran?
- What verifier passed?
- What is the restoration path?
- What was saved?
- What risks remain?
- How can this be reversed or rehydrated?

Proofs are not necessarily cryptographic at first, but production deployments should support signing and tamper-evident logs.

## Rehydration

Rehydration reconstructs the logical view.

For exact bytes:

```text
lookup manifest
fetch chunks
apply inverse transforms
concatenate by logical offsets
verify checksum
return bytes
```

For exact logical:

```text
lookup manifest
fetch physical data
apply table or stream protocol
validate schema and row/message counts
return logical records
```

For semantic:

```text
lookup manifest
check policy and freshness
return summary, derived artifact, or cached response
expose source fingerprints and confidence where required
```

## Manifest portability

The manifest format must be portable across:

- local filesystem;
- object storage;
- Postgres;
- SQLite;
- cloud metadata stores;
- message streams;
- backup exports.

Do not make a production deployment depend on a SaaS-only manifest store.

## Versioning

URP must version:

- manifest schema;
- work unit schema;
- policy schema;
- plugin API;
- transform identity;
- classifier identity;
- verifier identity;
- planner identity.

Old manifests must remain readable. New fields should be additive where possible.

## Compatibility tests

Every implementation must pass tests for:

- manifest round trip;
- exact rehydration;
- ledger append;
- policy resolution;
- contract escalation;
- denied semantic transform;
- cache isolation;
- plugin version negotiation;
- invalid manifest rejection.

## Anti-patterns

Avoid:

- storing only compressed bytes without manifest;
- hiding semantic transformations behind "optimization";
- deduping across tenants by default;
- relying on filename extensions for classification;
- accepting AI cache hits without source freshness checks;
- using unverifiable approximate transforms for regulated data;
- deleting raw data before legal hold checks;
- making plugins mutate policies at runtime.

## Why this model works

The work unit model avoids creating separate products for every infrastructure category. It gives URP one language for intent, policy, action, verification, and audit.

<!-- END docs/03_UNIFIED_WORK_UNIT_AND_MANIFEST_MODEL.md -->


---

<!-- BEGIN docs/04_REDUCTION_AND_AI_ALGORITHMS.md -->

# 04 — Reduction and AI Algorithms

## Purpose

This document defines the practical algorithm catalog URP should implement. It is organized around the unified planner, not around separate data and AI products.

URP should never assume one technique applies to all payloads. It should apply a sequence of safe, measurable actions chosen by contract and policy.

## Universal planning loop

```python
def plan(work_unit):
    classification = classify(work_unit)
    contract = resolve_contract(work_unit, classification)
    policy = evaluate_policy(work_unit, classification, contract)
    candidates = enumerate_actions(work_unit, classification, contract, policy)
    scored = score_candidates(candidates)
    plan = choose_lowest_risk_highest_value(scored)
    return plan
```

## Universal execution loop

```python
def execute(plan):
    for action in plan.actions:
        result = run_action(action)
        emit_ledger(action, result)
        if result.failed and action.required:
            return fallback(plan)
    verification = verify(plan)
    if not verification.accepted:
        return fallback(plan)
    manifest = write_manifest(plan, verification)
    return manifest
```

## Reducibility estimation

Before spending real resources, URP should estimate whether reduction is worth it.

Signals:

- whole-object duplicate hash;
- sample entropy;
- compression trial on sample;
- file type;
- magic bytes;
- schema hints;
- row-group cardinality;
- repeated log templates;
- stream key distribution;
- media codec status;
- prompt token duplication;
- semantic similarity to cached requests;
- embedding vector duplication;
- model checkpoint lineage.

Output:

```json
{
  "estimated_reduction_ratio": 0.42,
  "confidence": 0.83,
  "cheap_actions": ["hash", "sample_zstd"],
  "expensive_actions": ["near_duplicate_search"],
  "risk": "low"
}
```

## Byte-level algorithms

### Whole-object hashing

Use for exact duplicate detection.

Properties:

- simple;
- safe for exact-byte contracts;
- works across any bytes;
- misses shifted or partial duplicates.

Recommended hashes:

- SHA-256 for correctness and references;
- BLAKE3 as optional high-speed plugin where policy allows;
- backend-native checksums where available.

### Content-defined chunking

Use for partial duplicates across shifted content, backups, object versions, logs, and model checkpoints.

Basic concept:

```text
rolling hash over bytes
cut chunk when hash pattern matches
enforce min and max chunk size
hash chunk
store only new chunks
```

Planner considerations:

- large enough chunks reduce metadata overhead;
- smaller chunks increase dedupe opportunities;
- chunk size should vary by workload kind;
- encrypted payloads should not be chunked after encryption for dedupe purposes;
- cross-tenant chunk indexes must be disabled by default.

### Delta encoding

Use when a base object or checkpoint is known.

Good targets:

- object versions;
- backups;
- model checkpoints;
- container layers;
- repeated CSV exports;
- generated reports;
- source code snapshots.

Delta encoding must record base dependencies in the manifest. Avoid long delta chains without compaction.

### General-purpose compression

Use for unknown or semi-structured bytes after entropy sampling.

Recommended default:

- zstd level 1-6 for hot/warm data;
- higher levels for cold data if CPU budget allows;
- dictionary training for repeated logs and structured events.

Do not waste CPU compressing:

- already compressed media;
- encrypted data;
- random-looking payloads;
- files where sample trials show no benefit.

### Dictionary compression

Use dictionaries for repeated formats:

- service logs;
- JSON events;
- CSV records;
- telemetry;
- small repeated documents;
- application protocol payloads.

Dictionary management:

- version dictionaries;
- store dictionary id in manifest;
- enforce tenant scope;
- rotate when data distribution changes;
- keep dictionaries for rehydration.

## Structured data algorithms

### Columnar conversion

Allowed for exact-logical contracts.

Targets:

- CSV;
- JSONL;
- row-oriented exports;
- semi-structured events.

Output:

- Parquet;
- Arrow IPC;
- ORC plugin;
- table-native file format.

Verifier:

- row count;
- schema;
- null count where relevant;
- checksums per column or row group;
- sampled logical equivalence.

### Row group optimization

Actions:

- compact small files;
- split huge files;
- cluster by query columns;
- apply per-column encoding;
- apply per-column compression;
- eliminate duplicate row groups where safe.

Must use table transaction protocols for lakehouse tables.

### Schema-aware encoding

Examples:

- dictionary encode low-cardinality strings;
- delta encode timestamps;
- run-length encode repeated values;
- bit-pack booleans and small integers;
- normalize enums;
- store decimal precision correctly.

### Data-skipping metadata

For exact-logical workloads, URP can add:

- min/max statistics;
- bloom filters;
- zone maps;
- partition summaries;
- sketches.

These reduce query compute without changing logical data.

## Log and telemetry algorithms

### Log template extraction

Input:

```text
User 123 failed login from 1.2.3.4
User 456 failed login from 5.6.7.8
```

Template:

```text
User <id> failed login from <ip>
```

Variables:

```json
[{"id": 123, "ip": "1.2.3.4"}, {"id": 456, "ip": "5.6.7.8"}]
```

If exact-logical or exact-byte is required, URP must retain enough information to reconstruct.

### Anomaly-biased retention

Policy may keep:

- raw anomalies;
- raw incidents;
- sampled normal traffic;
- rollups for normal periods;
- sketches for cardinality;
- template counts;
- traces linked to incidents.

### Trace compaction

For distributed traces:

- keep error traces raw;
- keep high-latency traces raw;
- sample successful normal traces;
- aggregate service dependency metrics;
- preserve trace ids used for incidents.

## Stream algorithms

### Segment-level dedupe

Detect duplicate event batches or repeated heartbeats.

### Key-aware compaction

For streams with key semantics, preserve latest state or compaction policy.

### Replay-safe representation

Exact stream contracts require replay behavior to match. URP must not drop events unless policy and contract allow it.

### Late-arrival handling

Manifests must record watermarks and late-event policy.

## Media algorithms

### Exact media

For exact-byte contracts, only byte-level transforms are safe.

### Exact-logical media

Rare, but may allow container repacking without changing encoded frames.

### Approximate media

Policy may allow:

- transcoding;
- resolution reduction;
- bitrate reduction;
- thumbnail generation;
- scene-based keyframe retention;
- audio resampling.

Verifier:

- codec metadata;
- perceptual quality metrics;
- duration;
- resolution;
- audio channels;
- human review for sensitive workflows.

## Vector and embedding algorithms

### Embedding cache

Avoid recomputing embeddings for identical or near-identical text under same model and source policy.

Key fields:

- normalized text hash;
- model id;
- model version;
- tenant;
- preprocessing version;
- source fingerprint;
- policy domain.

### Vector quantization

Allowed for bounded approximate contracts.

Options:

- float16;
- int8;
- product quantization;
- scalar quantization;
- residual quantization.

Verifier:

- recall@k;
- distance distortion;
- downstream task accuracy;
- policy-defined error bound.

### Duplicate vector detection

Identify duplicate and near-duplicate embeddings, but do not assume semantic identity implies permission to merge records.

## AI request algorithms

### Prompt normalization

Normalize only for cache key and routing, not necessarily for user-visible content.

Operations:

- trim irrelevant whitespace;
- canonicalize system metadata;
- separate instruction, context, and user request;
- remove duplicated retrieved chunks;
- fingerprint source documents;
- detect tool-solvable requests.

### Exact prompt cache

Safe when:

- exact normalized request matches;
- same tenant/cache domain;
- same policy;
- same model or compatible answer contract;
- same source fingerprints;
- same freshness window;
- output verifier previously passed.

### Semantic cache

Semantic cache is powerful and risky.

Required guardrails:

- tenant isolation;
- source fingerprint comparison;
- freshness checks;
- answer verifier;
- semantic similarity threshold;
- task-type threshold;
- policy approval;
- no use for high-risk personal, legal, medical, or financial advice unless explicitly designed and approved;
- explainability and fallback.

Semantic cache output should record why it was accepted.

### Context compiler

The context compiler reduces prompt length while preserving answerability.

Steps:

1. separate instruction, question, history, and evidence;
2. remove duplicate chunks;
3. rank evidence by relevance and authority;
4. keep citations and source ids;
5. compress conversation history into state;
6. preserve exact quotes only when required;
7. enforce token budget;
8. record removed context fingerprints;
9. attach verifier requirements.

### Tool-first execution

URP should attempt deterministic tools before large models when policy allows:

- SQL;
- search;
- calculator;
- rules engine;
- code formatter;
- schema validator;
- vector lookup;
- retrieval;
- workflow API.

Tools reduce AI compute and improve verifiability.

### Model routing

Routing chooses the smallest safe model/tool path.

Inputs:

- task type;
- risk class;
- latency budget;
- source availability;
- cache confidence;
- user role;
- known model performance;
- verifier strength;
- cost and energy signals.

Routing levels:

```text
cache -> tool -> tiny model -> small specialist -> medium general -> large frontier
```

Escalate when:

- verifier fails;
- confidence is low;
- policy requires high-capability model;
- request is novel;
- user explicitly requires stronger model;
- sensitive domain mandates certified path.

### Verifier-aware routing

Do not route by confidence alone. Route by ability to pass a verifier.

Examples:

- code answer passes tests;
- SQL answer matches schema and row checks;
- support answer cites policy snippets;
- math answer matches calculator;
- extraction answer validates JSON schema.

## AI serving runtime algorithms

URP should integrate with rather than replace high-performance model servers.

Relevant techniques:

- continuous batching;
- prefix caching;
- KV-cache paging;
- KV-cache quantization;
- FlashAttention kernels;
- speculative decoding;
- multi-token decoding;
- LoRA adapter batching;
- model quantization;
- tensor/pipeline parallelism;
- autoscaling by queue depth and deadline.

URP's job is to decide when these techniques apply and record their results.

## Training reducer algorithms

### Dataset dedupe

Before training:

- exact dedupe;
- near-duplicate detection;
- boilerplate removal;
- contaminated benchmark removal;
- quality scoring;
- source balancing;
- license filtering;
- privacy filtering.

### RAG before fine-tune

If the use case is knowledge freshness, prefer retrieval over fine-tuning.

### Adapter before full fine-tune

If the use case is style, domain behavior, or narrow task adaptation, prefer LoRA/QLoRA/adapters.

### Distillation

Repeated successful large-model workflows can become:

- small classifier;
- small domain model;
- adapter;
- prompt template;
- tool workflow;
- retrieval package.

Distillation pipeline:

```text
collect verified examples
filter by policy and license
create train/eval split
train small model or adapter
evaluate against verifier suite
shadow route
gradually increase traffic
retain fallback
```

### Checkpoint reduction

Actions:

- base checkpoint dedupe;
- delta checkpoints;
- adapter-only storage;
- optimizer-state lifecycle;
- failed-run expiration;
- reproducibility manifest.

## Scheduler algorithms

### Deadline-aware scheduling

Classify jobs:

- online;
- interactive;
- nearline;
- batch;
- background;
- archival.

Only flexible jobs are shifted.

### Energy-aware scheduling

Inputs:

- electricity price;
- carbon intensity;
- grid stress;
- cooling efficiency;
- accelerator availability;
- data locality;
- deadline.

The scheduler should never violate user latency or compliance constraints.

### Queue policy

Use fair scheduling by tenant and priority. Avoid a large customer starving smaller tenants.

## Scoring function

A plan score should include:

```text
score = savings_value
      - latency_penalty
      - risk_penalty
      - cpu_overhead
      - rehydration_penalty
      - metadata_overhead
      - verifier_cost
      + policy_bonus
```

The score is explainable, not magic.

## Fallback design

Every non-trivial plan must define fallback.

Examples:

- store exact bytes if compression fails;
- call original model if cache verifier fails;
- use original object if rehydration fails;
- skip semantic reduction if policy lookup fails;
- use provider baseline if router is unavailable.

## Safety matrix

| Contract | Lossless compression | Dedupe | Semantic cache | Summarization | Model routing |
|---|---:|---:|---:|---:|---:|
| exact_bytes | Yes | Yes within domain | No | No | N/A |
| exact_logical | Yes | Yes within domain | No | No | N/A |
| bounded_approx | Yes | Yes | Maybe | Maybe | Maybe |
| semantic | Yes | Yes | Yes with verifier | Yes | Yes |
| tombstone | N/A | N/A | N/A | N/A | N/A |

## Algorithm anti-patterns

Avoid:

- applying lossy media transcodes under exact-byte contract;
- semantic caching without source freshness;
- compressing encrypted data repeatedly;
- writing table files outside catalog transaction protocol;
- routing sensitive tasks to unknown models;
- trusting AI self-evaluation as the only verifier;
- deleting raw training data before reproducibility requirements are known;
- over-optimizing cold data at the cost of unusable restores.

## Implementation priority

1. Hashing, entropy sampling, exact cache, manifest, ledger.
2. Content-defined chunking and zstd compression.
3. AI exact cache and context dedupe.
4. Policy-gated semantic cache.
5. Model router with verifier fallback.
6. Lakehouse exact-logical optimizers.
7. Training reducer and checkpoint deltas.
8. Energy-aware scheduler.
9. Automated distillation factory.

## Outcome

URP should make the cheap path the default, the expensive path the fallback, and the unsafe path impossible without explicit policy.

<!-- END docs/04_REDUCTION_AND_AI_ALGORITHMS.md -->


---

<!-- BEGIN docs/05_ADAPTER_CATALOG_AND_COMPATIBILITY.md -->

# 05 — Adapter Catalog and Compatibility

## Purpose

URP adoption depends on compatibility. Enterprises will not rewrite all systems to use a new reduction platform. URP must meet users where their workloads already live.

Adapters are not secondary. They are the adoption engine.

## Adapter contract

Every adapter must implement some subset of:

```text
discover
observe
ingest
plan
execute
read
rehydrate
delete
tombstone
emit_ledger
export_metrics
run_conformance
```

Adapter metadata:

```json
{
  "adapter_id": "s3.gateway",
  "version": "0.1.0",
  "capabilities": ["object.read", "object.write", "range.read", "multipart.upload"],
  "contracts_supported": ["exact_bytes", "exact_logical"],
  "risk_level": "core",
  "conformance_suite": "s3-basic-v1"
}
```

## S3-compatible object adapter

### Goals

- Preserve bucket and key behavior.
- Support existing SDKs.
- Enable exact-safe reduction without application code changes.
- Work with cloud object stores and S3-compatible on-prem systems.

### Required operations

- PutObject
- GetObject
- HeadObject
- DeleteObject
- ListObjectsV2
- CreateMultipartUpload
- UploadPart
- CompleteMultipartUpload
- AbortMultipartUpload
- Range reads
- Object tags
- Metadata headers

### URP mapping

| S3 concept | URP concept |
|---|---|
| bucket | namespace or policy scope |
| key | logical_ref |
| object version | manifest version |
| object metadata | work unit metadata |
| object tags | policy context |
| lifecycle rule | lifecycle policy |
| ETag | compatibility checksum, not always content hash |
| multipart part | intake segment |

### Edge cases

- Multipart ETags are not simple MD5 hashes.
- Range reads require efficient chunk lookup.
- Object locks and legal holds must override lifecycle reduction.
- Server-side encryption may prevent cross-object dedupe unless URP operates before encryption inside a trusted boundary.
- Object metadata must be preserved.
- Event notifications should preserve expected semantics.

## POSIX/filesystem adapter

### Deployment shapes

- FUSE mount;
- NFS/SMB gateway;
- CSI driver for Kubernetes;
- sidecar volume proxy;
- backup snapshot integration.

### Required semantics

- open/read/write/close;
- stat;
- rename;
- delete;
- permissions;
- extended attributes where possible;
- directory listing;
- fsync behavior disclosure.

### URP mapping

| POSIX concept | URP concept |
|---|---|
| path | logical_ref |
| inode | manifest identity hint |
| file content | byte_object work unit |
| xattr | policy hints |
| snapshot | backup_snapshot work unit |

### Warnings

Do not surprise applications with delayed writes unless documented. Filesystem semantics are harder than object semantics. The first production target should be object storage, not POSIX.

## SQL adapter

### Deployment shapes

- CDC reader;
- proxy for analytical queries;
- extension for supported databases;
- export/import optimizer;
- warehouse integration.

### Use cases

- detect duplicate exports;
- compress archival partitions;
- optimize warehouse staging files;
- classify data for policy;
- reduce AI-generated query workloads through cache and verification.

### Requirements

- never violate transaction semantics;
- respect isolation levels;
- avoid writing to primary DB without native integration;
- prefer CDC and object/table layers for first release.

## Lakehouse adapter

### Targets

- Apache Iceberg;
- Delta Lake;
- Apache Hudi;
- Hive-style tables as read-only or limited support.

### Actions

- file compaction;
- manifest compaction;
- partition evolution recommendations;
- row group sizing;
- column compression recommendations;
- delete file optimization;
- snapshot retention;
- duplicate file detection.

### Safety

Use native transaction APIs. Never mutate table metadata by editing files directly.

### Output

URP should produce:

- proposed optimization plan;
- exact-logical verification steps;
- snapshot lineage;
- rollback instructions;
- cost/savings estimate.

## Stream adapter

### Targets

- Kafka;
- Pulsar;
- Redpanda;
- Kinesis plugin;
- NATS JetStream plugin.

### Modes

- observe only;
- compacted mirror topic;
- archival reduction;
- replay gateway.

### URP mapping

| Stream concept | URP concept |
|---|---|
| topic | namespace |
| partition | shard |
| offset range | stream_segment work unit |
| event key | compaction key |
| schema registry id | schema hint |
| consumer group | policy context |

### Safety

For exact replay, original order and content matter. URP should not alter the canonical topic in early releases.

## Observability adapter

### Targets

- OpenTelemetry traces;
- metrics;
- logs;
- Prometheus remote write;
- log shippers.

### Actions

- hot exact retention;
- template extraction;
- cardinality reduction;
- anomaly preservation;
- trace sampling;
- metric rollup;
- incident-linked raw retention.

### Required controls

Observability data is often needed for incidents. Keep raw windows and fast bypass.

## AI API adapter

### Targets

- OpenAI-compatible APIs;
- provider-specific chat/completion APIs;
- embedding APIs;
- image/audio APIs where supported;
- internal LLM gateways.

### Required operations

- chat completions;
- completions;
- embeddings;
- model list;
- tool calls;
- batch jobs;
- streaming responses.

### URP behavior

- normalize request for cache and routing;
- preserve response format;
- attach URP headers where allowed;
- support streaming with fallback;
- record compute manifest;
- expose trace ids.

### Compatibility headers

Suggested headers:

```text
X-URP-Work-Unit-ID
X-URP-Manifest-ID
X-URP-Cache
X-URP-Route
X-URP-Contract
X-URP-Policy-Bundle
```

Headers should be optional and never break client parsers.

## Inference runtime adapter

### Targets

- vLLM;
- SGLang;
- Text Generation Inference;
- TensorRT-LLM;
- llama.cpp;
- Ollama;
- cloud model providers.

### Actions

- route model;
- select quantized variant;
- select adapter;
- set batching hints;
- use prefix cache;
- collect per-request metrics;
- configure speculative decoding where available.

### URP boundary

URP should not duplicate runtime internals. It should orchestrate and observe them.

## Training adapter

### Targets

- PyTorch jobs;
- Hugging Face Trainer;
- Ray;
- Kubernetes jobs;
- Slurm;
- Argo Workflows;
- managed fine-tuning APIs.

### Actions

- dataset dedupe;
- data selection;
- adapter recommendation;
- checkpoint delta storage;
- experiment dedupe;
- evaluation reuse;
- schedule by deadline and energy signal.

### Required metadata

- base model;
- dataset manifest ids;
- training code version;
- hyperparameters;
- random seeds where available;
- eval suite;
- output artifact manifest.

## Vector database adapter

### Targets

- FAISS;
- Milvus;
- Weaviate;
- Qdrant;
- Pinecone plugin;
- pgvector;
- Elasticsearch/OpenSearch vector search.

### Actions

- embedding dedupe;
- stale vector detection;
- index segment compression;
- quantization recommendations;
- source fingerprint invalidation;
- cache vector search results when safe.

### Safety

Never merge records only because vectors are similar. Similarity is a signal, not identity.

## Edge adapter

### Targets

- local devices;
- branch offices;
- mobile/desktop apps;
- browser extension contexts;
- IoT gateways.

### Actions

- local exact cache;
- local compression;
- local prompt compaction;
- delayed ledger sync;
- offline policy cache;
- low-power scheduling.

### Constraints

- limited CPU;
- intermittent connectivity;
- small storage;
- privacy-sensitive local data;
- slower updates.

## CI/CD adapter

### Use cases

- dedupe build artifacts;
- cache test results;
- reduce generated logs;
- route code assistant requests;
- avoid duplicate benchmark runs;
- store model eval reports.

### Integration targets

- GitHub Actions;
- GitLab CI;
- Jenkins;
- Buildkite;
- Bazel cache plugin.

## Developer SDKs

### Python

Primary for data/AI engineering and prototype.

### TypeScript

Primary for web apps, Node services, and AI product teams.

### Go

Primary for gateways, infrastructure services, and operators.

### Rust

Useful for high-performance chunking and transforms.

## Adapter conformance model

Each adapter must ship:

- unit tests;
- integration tests;
- compatibility tests;
- failure-mode tests;
- performance baseline;
- security review notes;
- documentation;
- sample configuration.

## Minimal adapter interface

```python
class Adapter:
    def discover(self): ...
    def observe(self, event): ...
    def ingest(self, work_unit): ...
    def read(self, logical_ref): ...
    def delete(self, logical_ref): ...
    def capabilities(self): ...
```

## Plugin packaging

A plugin package should include:

```text
plugin.yaml
README.md
src/
tests/
conformance/
security.md
examples/
```

## Plugin trust levels

### Core

Maintained by URP project.

### Certified

Third-party plugin passing conformance and review.

### Community

Available but not certified.

### Local

Private enterprise plugin.

Policy may restrict plugin trust levels by environment.

## Compatibility promise

URP must preserve existing workflows first and optimize second. The easiest adoption story is:

```text
Change endpoint URL. Keep application code. Start in observe mode.
```

## Unsupported platform behavior

When URP cannot support a platform safely, it should say so explicitly, run observe-only if possible, and avoid pretending to be transparent.

## Adoption priority

1. S3-compatible object gateway.
2. OpenAI-compatible AI gateway.
3. CLI and SDK.
4. Manifest/ledger export.
5. Kafka/OpenTelemetry observe adapters.
6. Lakehouse optimizer.
7. Kubernetes batch scheduler.
8. POSIX/CSI for selected use cases.
9. Training and vector DB deep integrations.

<!-- END docs/05_ADAPTER_CATALOG_AND_COMPATIBILITY.md -->


---

<!-- BEGIN docs/06_POLICY_SECURITY_COMPLIANCE.md -->

# 06 — Policy, Security, Compliance, and Trust

## Purpose

URP reduces infrastructure waste by changing how data and AI work units are stored, routed, cached, transformed, summarized, or deleted. That makes policy and trust central, not optional.

The system must be safe before it is clever.

## Policy model

A URP policy answers five questions:

1. What is this work unit?
2. What must be preserved?
3. What is allowed?
4. What is forbidden?
5. What must be proven?

## Policy inputs

Policy may inspect:

- tenant;
- namespace;
- application id;
- user id;
- service account;
- region;
- environment;
- data classification;
- work unit kind;
- schema;
- object tags;
- bucket/table/topic;
- AI task type;
- model/provider;
- legal hold status;
- retention class;
- source fingerprint;
- latency budget;
- request purpose;
- plugin trust level.

## Policy outputs

Policy returns:

- effective contract;
- transform allowlist;
- transform denylist;
- cache domain;
- dedupe domain;
- retention schedule;
- rehydration requirement;
- verifier requirements;
- model allowlist;
- scheduler constraints;
- ledger requirements;
- approval requirements.

## Example policy

```yaml
apiVersion: urp.dev/v1
kind: ReductionPolicy
metadata:
  name: default-enterprise-policy
spec:
  defaults:
    contract: exact_bytes
    semanticReduction: deny
    crossTenantDedupe: deny
    crossTenantCache: deny
  rules:
    - name: exact-finance-ledger
      match:
        tags:
          data_class: financial_ledger
      contract: exact_bytes
      allow:
        transforms: [hash, chunk, dedupe_same_tenant, zstd]
      deny:
        transforms: [semantic_summary, lossy_transcode, approximate_quantization]
      require:
        verifiers: [sha256_restore]
        retention: never_delete
    - name: support-ai-semantic-cache
      match:
        kind: prompt_request
        namespace: support-ai
      contract: semantic
      allow:
        transforms: [exact_cache, semantic_cache, context_compile, model_route]
      require:
        verifiers: [source_consistency, freshness_check]
        max_cache_age: 24h
```

## Policy evaluation principles

### Strictest rule wins

A legal hold should override cost-saving rules. A regulated data class should override a namespace default.

### Deny unknown semantic reduction

Unknown data may be compressed and deduped exactly. It must not be summarized, approximated, or semantically substituted unless explicitly allowed.

### Deterministic evaluation

The same input and policy bundle should produce the same decision.

### Versioned policy bundles

Every manifest and ledger event should record the policy bundle id.

### Explainability

Policy results should include matched rules and denied actions.

## Security domains

URP needs explicit domains.

### Tenant domain

Boundary for data ownership and cache sharing.

### Dedupe domain

Boundary in which duplicate chunks may be reused.

Default: same tenant and policy domain only.

### Cache domain

Boundary in which AI or data cache entries may be reused.

Default: same tenant, same application, same source fingerprints, same policy.

### Encryption domain

Boundary for keys and plaintext visibility.

### Plugin trust domain

Boundary for which plugins may run against which data.

### Network domain

Boundary for where data and compute may move.

## Cross-tenant dedupe risk

Cross-tenant dedupe can leak information through timing, storage accounting, or existence tests. URP must disable cross-tenant dedupe by default.

If an operator wants cross-tenant dedupe:

- require explicit policy;
- use side-channel mitigations;
- aggregate billing carefully;
- avoid exposing hit/miss timing;
- consider convergent encryption risks;
- record high-risk ledger events.

## Semantic cache risk

Semantic cache can return an answer that seems right but is stale, unauthorized, or contextually wrong.

Mitigations:

- tenant isolation;
- source fingerprinting;
- freshness windows;
- permission checks;
- task-specific similarity thresholds;
- verifiers;
- high-risk domain blocklist;
- fallback to model;
- clear ledger event.

## Prompt privacy

AI requests often contain sensitive data.

URP should:

- avoid logging full prompts by default;
- store prompt hashes and redacted summaries;
- encrypt prompt cache entries;
- allow local-only deployments;
- support no-retention mode;
- preserve provider privacy constraints;
- give admins configurable retention.

## Encryption

### Reduce before encrypting

Compression and dedupe work best before encryption, because encrypted data should look random.

Safe architecture:

```text
plaintext inside trusted boundary
-> reduce exactly
-> encrypt chunks/manifests/cache records
-> store physical data
```

### Client-side encryption

If clients encrypt before URP sees data, URP can still:

- store exact;
- hash ciphertext;
- dedupe exact ciphertext within allowed domain;
- lifecycle by metadata;
- observe size and access patterns.

But it cannot semantically reduce or effectively compress.

### Key management

URP should integrate with:

- cloud KMS;
- HashiCorp Vault;
- on-prem HSM;
- Kubernetes secrets for dev only;
- envelope encryption.

Manifest secrets should be separated from metadata where possible.

## Manifest security

Manifest fields can leak sensitive information.

Protect:

- logical refs with sensitive names;
- source fingerprints;
- policy tags;
- prompt summaries;
- model outputs;
- user ids;
- derived facts.

Support:

- encrypted fields;
- redacted export;
- role-based manifest views;
- signed manifests;
- tamper-evident ledger.

## Plugin security

Plugins can be dangerous because they may see plaintext.

Requirements:

- capability declaration;
- least privilege;
- sandboxing option;
- signed plugin packages;
- dependency scanning;
- resource limits;
- deterministic mode for policy-sensitive transforms;
- no network access by default for high-risk transforms;
- conformance tests.

## Identity and access

URP should support:

- API keys for dev;
- mTLS for services;
- OIDC/OAuth for users;
- workload identity in Kubernetes;
- cloud IAM integration;
- SCIM or directory sync for enterprise;
- service-account policies.

## Authorization

Authorization checks should exist for:

- work unit intake;
- manifest read;
- raw rehydration;
- semantic cache use;
- policy override;
- plugin install;
- transform execution;
- model route;
- deletion/tombstone;
- ledger query.

## Compliance support

URP should not claim certification by default. It should provide features that make certification and audits easier.

Relevant capabilities:

- retention policies;
- legal hold;
- deletion proof;
- audit ledger;
- manifest lineage;
- access logs;
- encryption;
- data residency;
- role separation;
- policy versioning;
- eDiscovery export;
- restore testing.

## Regulated data classes

Default recommendations:

| Data class | Default contract | Semantic reduction | Cache sharing |
|---|---|---:|---:|
| financial ledger | exact_bytes | deny | same dataset only |
| medical record | exact_bytes | deny unless approved | highly restricted |
| legal record | exact_bytes | deny | restricted |
| security incident | exact_bytes hot, exact_logical warm | restricted | same team |
| debug logs | exact hot, semantic after window | allow by policy | same tenant |
| public docs | exact_logical or semantic | allow | broader |
| marketing media | bounded_approx | allow | same org |
| AI prompt with PII | semantic only with strict policy | restricted | no cross-app default |

## Legal hold

Legal hold must block:

- deletion;
- tombstoning;
- semantic-only retention;
- lossy transformation if raw is not preserved;
- lifecycle expiration;
- cache eviction when required for evidence.

Legal hold changes must produce ledger events.

## Data minimization

URP can help with privacy by deleting or summarizing low-value data, but only under policy.

The system should distinguish:

- operational minimization;
- legal retention;
- customer deletion requests;
- analytics aggregation;
- AI training exclusion;
- derived artifact deletion.

## AI safety and output trust

For AI output, URP must not treat cache/routing as only a cost problem.

Required controls:

- task classification;
- domain risk;
- source grounding;
- output schema validation;
- tool verification;
- fallback on uncertainty;
- human approval for high-risk automation;
- policy hooks for safety systems.

## Audit trail examples

Semantic cache hit event:

```json
{
  "event_type": "ai.semantic_cache.accepted",
  "similarity": 0.94,
  "source_fingerprints_match": true,
  "freshness_seconds": 318,
  "verifier": "support_policy_source_consistency@1.2.0",
  "fallback_available": true
}
```

Denied transform event:

```json
{
  "event_type": "policy.transform.denied",
  "transform": "semantic_summary",
  "reason": "effective_contract_exact_bytes",
  "matched_rule": "finance-ledger-exact"
}
```

## Incident response

URP security incidents may include:

- unauthorized cache reuse;
- manifest tampering;
- plugin compromise;
- policy misconfiguration;
- verifier bypass;
- data rehydration failure;
- cross-tenant side channel;
- stale semantic answer.

Runbook steps:

1. freeze policy bundle;
2. disable affected plugins;
3. bypass semantic cache;
4. force exact fallback;
5. query ledger;
6. identify affected work units;
7. rehydrate originals where needed;
8. rotate keys;
9. publish incident report;
10. add conformance tests.

## Threat model

### Adversaries

- malicious tenant;
- compromised app service;
- malicious plugin;
- insider with partial access;
- external attacker;
- careless administrator.

### Assets

- raw payloads;
- manifests;
- cache entries;
- ledger;
- policies;
- keys;
- model outputs;
- source fingerprints;
- dedupe indexes.

### Attack paths

- infer data existence from dedupe;
- retrieve unauthorized cache entry;
- install malicious transform;
- alter manifest rehydration path;
- weaken policy;
- poison semantic cache;
- poison training reducer;
- exploit prompt logging;
- abuse model router.

## Required security tests

- cross-tenant cache rejection;
- cross-tenant dedupe rejection;
- legal hold blocks deletion;
- exact contract blocks semantic transform;
- stale source invalidates semantic cache;
- plugin capability enforcement;
- manifest signature verification;
- redacted manifest view;
- policy override audit event;
- fallback on verifier failure.

## Open-source trust posture

The project should be transparent about risks. Avoid exaggerated claims. Publish threat models, conformance tests, and security advisories.

## Security invariant

URP must never silently trade correctness, privacy, or compliance for savings.

<!-- END docs/06_POLICY_SECURITY_COMPLIANCE.md -->


---

<!-- BEGIN docs/07_APIS_SCHEMAS_PROTOCOLS.md -->

# 07 — APIs, Schemas, and Protocols

## Purpose

This document defines the external and internal API shape for URP. The goal is to make URP easy to adopt through existing interfaces while still exposing first-class URP-native control.

## API design principles

1. Existing protocols first.
2. URP-native API for control, planning, policy, manifests, and ledger.
3. SDKs should wrap protocols but not hide important decisions.
4. Every API that changes behavior must expose a traceable work unit id.
5. Every optimization path must support observe-only behavior.
6. REST and gRPC should share the same conceptual model.
7. OpenAPI and protobuf specs must be generated from the same source where possible.

## Public API groups

```text
/v1/work-units
/v1/plans
/v1/manifests
/v1/ledger
/v1/policies
/v1/cache
/v1/ai
/v1/adapters
/v1/plugins
/v1/benchmarks
/v1/admin
```

## Work unit API

### Create work unit

```http
POST /v1/work-units
```

Request:

```json
{
  "kind": "byte_object",
  "tenant": "acme",
  "logical_ref": "s3://bucket/key",
  "contract": "exact_bytes",
  "metadata": {
    "owner": "platform"
  }
}
```

Response:

```json
{
  "work_unit_id": "wu_...",
  "state": "received"
}
```

### Plan work unit

```http
POST /v1/work-units/{id}/plan
```

Response:

```json
{
  "plan_id": "plan_...",
  "actions": [
    {"type": "hash", "required": true},
    {"type": "content_defined_chunk", "required": true},
    {"type": "zstd_compress", "required": false}
  ],
  "risk": "low",
  "expected": {
    "stored_bytes_reduction": 0.37
  }
}
```

### Execute work unit

```http
POST /v1/work-units/{id}/execute
```

Input:

```json
{
  "mode": "observe|shadow|enforce"
}
```

Response:

```json
{
  "manifest_id": "mf_...",
  "verification": {
    "accepted": true
  }
}
```

## Manifest API

### Get manifest

```http
GET /v1/manifests/{manifest_id}
```

### Query by logical ref

```http
GET /v1/manifests?logical_ref=s3://bucket/key
```

### Rehydrate

```http
POST /v1/manifests/{manifest_id}/rehydrate
```

Request:

```json
{
  "format": "original",
  "range": {
    "start": 0,
    "end": 1048576
  }
}
```

### Export

```http
POST /v1/manifests/export
```

Use for migration, audit, and disaster recovery.

## Ledger API

### Query ledger

```http
POST /v1/ledger/query
```

Request:

```json
{
  "tenant": "acme",
  "from": "2026-07-01T00:00:00Z",
  "to": "2026-07-08T00:00:00Z",
  "event_types": ["policy.transform.denied", "ai.semantic_cache.accepted"]
}
```

### Stream ledger

```http
GET /v1/ledger/stream
```

Should support Server-Sent Events or WebSocket in addition to batch query.

## Policy API

### Validate policy

```http
POST /v1/policies/validate
```

### Evaluate policy

```http
POST /v1/policies/evaluate
```

### Publish policy bundle

```http
POST /v1/policies/bundles
```

Policy publishing should require authorization and should produce ledger events.

## Cache API

### Exact cache lookup

```http
POST /v1/cache/exact/lookup
```

### Semantic cache lookup

```http
POST /v1/cache/semantic/lookup
```

Required fields:

- tenant;
- cache domain;
- normalized query or embedding;
- source fingerprints;
- policy id;
- freshness requirements.

### Cache store

```http
POST /v1/cache/store
```

Cache storage must include verifier result.

## AI API compatibility

URP should expose an OpenAI-compatible surface where feasible:

```http
POST /v1/chat/completions
POST /v1/completions
POST /v1/embeddings
GET  /v1/models
```

URP-specific options can live under an extension object:

```json
{
  "model": "auto",
  "messages": [],
  "urp": {
    "contract": "semantic",
    "mode": "enforce",
    "max_context_tokens": 4000,
    "allow_semantic_cache": true,
    "require_citations": true,
    "fallback_model": "frontier-large"
  }
}
```

The response should preserve provider compatibility and optionally add URP metadata:

```json
{
  "id": "chatcmpl_...",
  "choices": [],
  "usage": {},
  "urp": {
    "work_unit_id": "wu_...",
    "manifest_id": "mf_...",
    "cache": "semantic_hit",
    "route": "small_support_model",
    "fallback_used": false,
    "verifier": "source_consistency@1.0.0"
  }
}
```

## Streaming AI responses

Streaming is harder because URP may not know verification outcome until the response is complete.

Options:

1. conservative stream: route directly and record telemetry;
2. buffered stream: verify before sending, increases latency;
3. speculative stream: stream with fallback marker if failure occurs;
4. non-streaming fallback for high-risk tasks.

Default should be conservative and transparent.

## gRPC API

The protobuf file should define:

- WorkUnitService;
- ManifestService;
- PolicyService;
- LedgerService;
- CacheService;
- AIService;
- PluginService.

Use gRPC for high-throughput internal integrations and REST for broad adoption.

## CLI

Core commands:

```bash
urp plan --kind byte_object --file ./data.bin
urp ingest --s3 s3://bucket/key
urp manifest get mf_...
urp ledger query --tenant acme --event ai.route
urp policy validate policy.yaml
urp gateway s3 --listen :9000 --backend s3://bucket
urp gateway ai --listen :8080 --provider openai
urp benchmark run --suite object-exact-v1
```

## SDK design

SDKs should provide:

- simple high-level client;
- typed work unit builder;
- policy annotations;
- manifest fetch;
- ledger query;
- cache controls;
- AI gateway wrapper;
- local test utilities.

Python example:

```python
from urp import URPClient

client = URPClient("http://localhost:8080")
result = client.chat(
    messages=[{"role": "user", "content": "Summarize this policy"}],
    contract="semantic",
    require_citations=True,
)
print(result.urp.manifest_id)
```

TypeScript example:

```ts
const urp = new URPClient({ baseUrl: "http://localhost:8080" });
const plan = await urp.plan({
  kind: "prompt_request",
  tenant: "acme",
  logicalRef: "app://support/chat/123",
  payload: { text: "How do I reset VPN?" }
});
```

Go example:

```go
client := urp.NewClient("http://localhost:8080")
plan, err := client.Plan(ctx, urp.WorkUnit{
    Kind: "byte_object",
    Tenant: "acme",
    LogicalRef: "s3://bucket/key",
})
```

## Headers

Recommended HTTP headers:

```text
X-URP-Work-Unit-ID
X-URP-Manifest-ID
X-URP-Contract
X-URP-Policy-Bundle
X-URP-Mode
X-URP-Cache
X-URP-Route
X-URP-Trace-ID
```

## ID conventions

Suggested prefixes:

- `wu_` work unit
- `mf_` manifest
- `pl_` plan
- `evt_` ledger event
- `pol_` policy
- `pb_` policy bundle
- `ck_` cache key
- `ch_` chunk
- `tx_` transform
- `vr_` verifier result

IDs should be sortable where useful and globally unique.

## Error model

Errors should include:

```json
{
  "error": {
    "code": "policy_denied",
    "message": "semantic_summary is denied by exact_bytes contract",
    "work_unit_id": "wu_...",
    "policy_bundle_id": "pb_...",
    "retryable": false
  }
}
```

Common codes:

- invalid_work_unit;
- policy_denied;
- contract_violation;
- verifier_failed;
- plugin_unavailable;
- adapter_unavailable;
- manifest_not_found;
- rehydration_failed;
- cache_permission_denied;
- model_route_failed;
- backend_timeout.

## Observability protocol

Use OpenTelemetry conventions where possible.

Span names:

- urp.intake
- urp.classify
- urp.policy.evaluate
- urp.plan
- urp.execute
- urp.verify
- urp.manifest.write
- urp.cache.lookup
- urp.ai.route
- urp.rehydrate

Metrics are defined in observability docs.

## Schema compatibility

Schemas should be:

- JSON Schema for REST and config;
- OpenAPI for REST;
- protobuf for gRPC;
- YAML examples for policy;
- language SDK types generated where possible.

## Backward compatibility

Breaking changes require:

- version bump;
- migration guide;
- manifest reader support for old versions;
- conformance update;
- deprecation window.

## API anti-patterns

Avoid:

- hiding URP decisions from API users;
- returning cache hits without metadata;
- accepting semantic reduction with no verifier field;
- using provider-specific fields in core schemas;
- making OpenAI-compatible clients parse URP metadata unless they ask for it;
- exposing sensitive prompt or manifest data through headers.

## Minimum viable API set

For MVP:

- POST /v1/work-units/plan
- POST /v1/work-units/execute
- GET /v1/manifests/{id}
- POST /v1/policies/evaluate
- POST /v1/chat/completions
- GET /healthz
- GET /metrics

## Ideal-state API set

The ideal state includes full policy, plugin, conformance, benchmark, ledger streaming, adapter management, and export/import APIs.

<!-- END docs/07_APIS_SCHEMAS_PROTOCOLS.md -->


---

<!-- BEGIN docs/08_IMPLEMENTATION_BLUEPRINT_CODEX.md -->

# 08 — Implementation Blueprint for Codex

## Purpose

This document is the direct build handoff. Codex should use it to create a production-quality repository from the prototype skeleton.

## Build philosophy

Start with a thin vertical slice. Do not build every adapter before the core lifecycle works.

The first working demo should prove:

```text
one WorkUnit model
one policy resolver
one planner
one manifest writer
one ledger
one exact data path
one AI request path
one CLI
one test suite
```

## Monorepo layout

```text
/
  README.md
  docs/
  specs/
  codex/
  crates/
    urp-core/
    urp-chunker/
    urp-gateway-s3/
  python/
    urp/
  go/
    urp/
  typescript/
    src/
  services/
    control-plane/
    gateway-s3/
    gateway-ai/
    worker/
    scheduler/
  plugins/
    transforms/
    classifiers/
    verifiers/
    adapters/
  deployments/
    docker-compose/
    kubernetes/
    terraform/
  tests/
    unit/
    integration/
    conformance/
    load/
  examples/
```

The package currently includes a smaller reference skeleton under `src/`.

## Language choices

### Rust

Recommended for:

- chunking;
- hashing;
- compression pipelines;
- high-throughput gateways;
- plugin sandbox runtime;
- CLI performance-critical operations.

### Go

Recommended for:

- Kubernetes operators;
- long-running gateways;
- control services;
- adapters;
- gRPC services.

### Python

Recommended for:

- reference implementation;
- AI routing;
- research algorithms;
- policy experiments;
- SDK;
- tests;
- data science integrations.

### TypeScript

Recommended for:

- web dashboard;
- Node SDK;
- developer integrations.

## Core packages

### urp-core

Responsibilities:

- WorkUnit types;
- Contract types;
- Manifest types;
- Ledger event types;
- policy evaluation interface;
- planner interface;
- plugin interface;
- ID generation;
- serialization.

### urp-policy

Responsibilities:

- parse policy YAML;
- validate policy schema;
- evaluate rules;
- produce explainable decisions;
- cache policy bundles;
- version policies.

### urp-manifest

Responsibilities:

- read/write manifests;
- validate schema;
- support version migration;
- store in SQLite/Postgres/object backends;
- sign manifests where configured.

### urp-ledger

Responsibilities:

- append events;
- query events;
- export events;
- support tamper-evident chaining in production;
- emit OpenTelemetry.

### urp-executor

Responsibilities:

- execute action plans;
- call transforms;
- call verifiers;
- handle fallback;
- report metrics.

### urp-gateway-ai

Responsibilities:

- OpenAI-compatible routes;
- exact cache;
- semantic cache;
- context compiler;
- model router;
- response verifier;
- provider adapters.

### urp-gateway-s3

Responsibilities:

- S3-compatible object API;
- multipart upload;
- range reads;
- object tags;
- manifest mapping;
- physical chunk storage.

## Build phases

### Phase 0 — Repository hygiene

Deliverables:

- license;
- contribution guide;
- code of conduct;
- security policy;
- CI;
- formatting;
- linting;
- unit test skeleton;
- documentation build check.

Acceptance:

- clone, test, and lint succeed locally;
- README quickstart works.

### Phase 1 — Core domain model

Deliverables:

- WorkUnit schema;
- Manifest schema;
- Policy schema;
- Ledger event schema;
- JSON serialization;
- schema validation;
- ID generation.

Acceptance:

- all sample manifests validate;
- old unknown fields are preserved or safely ignored;
- schema tests pass.

### Phase 2 — Policy engine

Deliverables:

- YAML policy parser;
- exact default;
- contract escalation;
- allow/deny transforms;
- explain output;
- policy bundle id;
- legal hold override.

Acceptance:

- exact contract blocks semantic transforms;
- legal hold blocks deletion;
- cross-tenant cache disabled by default;
- policy evaluation is deterministic.

### Phase 3 — Planner

Deliverables:

- classification input;
- action candidate registry;
- scoring;
- fallback path;
- explainable plan output;
- observe/shadow/enforce modes.

Acceptance:

- byte object plans include hash/chunk/compress when safe;
- prompt request plans include cache/context/route/verify when allowed;
- denied actions are visible.

### Phase 4 — Exact data execution

Deliverables:

- whole-object hashing;
- content-defined chunking;
- zstd plugin or placeholder with interface;
- content-addressed chunk store;
- exact rehydration;
- checksum verification;
- manifest write;
- ledger events.

Acceptance:

- original bytes restore exactly;
- duplicate chunks are stored once within domain;
- incompressible payload falls back safely.

### Phase 5 — AI gateway MVP

Deliverables:

- OpenAI-compatible route;
- provider adapter interface;
- exact cache;
- normalized request hash;
- basic semantic cache placeholder;
- simple model router;
- verifier hook;
- compute manifest.

Acceptance:

- exact repeated request can bypass provider;
- semantic cache is off by default;
- route decision is recorded;
- fallback provider path works.

### Phase 6 — Observability

Deliverables:

- metrics;
- traces;
- structured logs;
- manifest explorer CLI;
- ledger query CLI.

Acceptance:

- user can see bytes avoided, tokens avoided, cache hit rate, verifier failures, and latency overhead.

### Phase 7 — Conformance

Deliverables:

- S3 basic conformance tests;
- AI API compatibility tests;
- manifest schema conformance;
- policy security tests;
- plugin conformance harness.

Acceptance:

- adapters cannot be marked stable without conformance pass.

### Phase 8 — Production hardening

Deliverables:

- HA deployment;
- Postgres manifest store;
- durable ledger;
- key management integration;
- authn/authz;
- admin API;
- backup/restore tests;
- chaos tests.

Acceptance:

- control plane restart does not lose manifests;
- exact rehydration works after restart;
- policies cannot be changed without audit.

### Phase 9 — Advanced reducers

Deliverables:

- lakehouse optimizer;
- log template extractor;
- semantic cache with source fingerprints;
- model router with eval feedback;
- LoRA/QLoRA training reducer integration;
- checkpoint delta store;
- energy-aware scheduler.

Acceptance:

- each advanced reducer has policy gates, verifiers, benchmarks, and rollback.

## Detailed ticket list

### Ticket 001 — Define core enums

Implement contract, work unit kind, action kind, manifest state, event type, and policy decision enums.

Acceptance:

- serialization tests;
- unknown enum handling strategy;
- docs generated.

### Ticket 002 — Implement WorkUnit builder

Create builders in Python, Go, and TypeScript SDKs.

Acceptance:

- validates required fields;
- attaches trace id;
- supports metadata.

### Ticket 003 — Implement policy parser

Parse YAML policy into validated objects.

Acceptance:

- invalid rule produces line-specific error;
- default exact policy works.

### Ticket 004 — Implement policy resolver

Evaluate policy against a work unit.

Acceptance:

- strictest rule wins;
- explain output includes matched rules.

### Ticket 005 — Implement plan action registry

Actions register capabilities, risk, supported contracts, and executor id.

Acceptance:

- action cannot run if not allowed by contract and policy.

### Ticket 006 — Implement entropy sampler

Estimate byte entropy from sample.

Acceptance:

- repeated bytes produce low entropy;
- random bytes produce high entropy.

### Ticket 007 — Implement content-defined chunker

Use rolling hash with min/avg/max chunk sizes.

Acceptance:

- deterministic chunks;
- changed prefix does not shift all later chunks;
- tests cover boundaries.

### Ticket 008 — Implement chunk store interface

Store by hash and domain.

Acceptance:

- duplicate chunk increments ref metadata, not bytes;
- cross-domain lookup disabled by default.

### Ticket 009 — Implement exact rehydration

Rebuild bytes from manifest segments.

Acceptance:

- byte-for-byte equality;
- checksum verification failure triggers error.

### Ticket 010 — Implement manifest store

Start with SQLite and file backend.

Acceptance:

- create/get/list;
- versioned records;
- JSON export.

### Ticket 011 — Implement ledger

Append JSONL local ledger first.

Acceptance:

- every plan/execute/test emits events;
- query by work_unit_id.

### Ticket 012 — Implement CLI

Commands: plan, execute, manifest get, ledger query, policy validate.

Acceptance:

- README quickstart works.

### Ticket 013 — Implement OpenAI-compatible request parser

Support chat completions and embeddings.

Acceptance:

- passes simple client request tests.

### Ticket 014 — Implement exact AI cache

Key by normalized request, tenant, policy, model, and source fingerprints.

Acceptance:

- cache hit never crosses tenant;
- stale source invalidates entry.

### Ticket 015 — Implement context compiler v0

Remove duplicate context chunks and enforce max token budget using simple token approximation.

Acceptance:

- duplicated chunks removed;
- preserved source ids.

### Ticket 016 — Implement model router v0

Route by policy, task type, and configured model tiers.

Acceptance:

- easy tasks route to small model when allowed;
- high-risk tasks route to required model.

### Ticket 017 — Implement verifier hooks

Basic JSON schema, citation presence, checksum, and exact-match verifiers.

Acceptance:

- verifier failure triggers fallback.

### Ticket 018 — Implement AI compute manifest

Record cache lookup, context token reduction, route, verifier, fallback.

Acceptance:

- manifest is queryable and exportable.

### Ticket 019 — Implement S3 gateway skeleton

Support PutObject/GetObject/HeadObject for exact-safe path.

Acceptance:

- standard SDK can write/read object.

### Ticket 020 — Implement multipart support

Acceptance:

- multipart uploads produce one manifest;
- abort cleans partial chunks.

### Ticket 021 — Implement range reads

Acceptance:

- range read returns expected bytes without full rehydration where possible.

### Ticket 022 — Implement metrics

Expose Prometheus metrics.

Acceptance:

- tests assert key metrics exist.

### Ticket 023 — Implement OpenTelemetry traces

Acceptance:

- spans include work_unit_id and manifest_id.

### Ticket 024 — Implement plugin descriptor

Acceptance:

- invalid plugin descriptors are rejected.

### Ticket 025 — Implement conformance harness

Acceptance:

- adapters report conformance status.

### Ticket 026 — Implement policy security tests

Acceptance:

- CI fails if semantic transform bypasses exact contract.

### Ticket 027 — Implement Docker Compose

Acceptance:

- local gateway and control service start.

### Ticket 028 — Implement Kubernetes manifests

Acceptance:

- deploys in kind/minikube.

### Ticket 029 — Implement benchmark runner

Acceptance:

- can compare baseline versus URP for object and prompt workloads.

### Ticket 030 — Write operator runbook

Acceptance:

- includes backup, restore, bypass, incident steps.

## Testing strategy

### Unit tests

- schema validation;
- policy decisions;
- classifier hints;
- chunking;
- cache isolation;
- verifier behavior.

### Integration tests

- object write/read;
- AI request/cache/fallback;
- manifest persistence;
- ledger query;
- policy reload.

### Conformance tests

- S3 subset;
- OpenAI subset;
- plugin interface;
- manifest compatibility.

### Security tests

- cross-tenant cache rejection;
- legal hold;
- policy override audit;
- plugin capability enforcement.

### Load tests

- object ingest throughput;
- rehydration latency;
- AI gateway p95 latency;
- cache index scalability;
- manifest store write rate.

## Definition of done for any reducer

A reducer is not done until it has:

- policy rule;
- action descriptor;
- planner integration;
- executor;
- verifier;
- manifest fields;
- ledger events;
- metrics;
- tests;
- documentation;
- fallback path;
- disabled-by-default stance if semantic or lossy.

## Codex instruction

When building, do not collapse URP into isolated tools. Keep the shared lifecycle and shared manifest. Every feature must answer:

```text
What work unit is this?
What contract applies?
What policy allowed it?
What manifest records it?
What verifier proved it?
What ledger event audits it?
```

<!-- END docs/08_IMPLEMENTATION_BLUEPRINT_CODEX.md -->


---

<!-- BEGIN docs/09_OBSERVABILITY_BENCHMARKS_OPS.md -->

# 09 — Observability, Benchmarks, SLOs, and Operations

## Purpose

URP must prove it saves resources without hiding risk. Observability is a product feature, not an afterthought.

## Measurement categories

URP should measure:

- bytes received;
- bytes physically stored;
- bytes avoided by dedupe;
- bytes avoided by compression;
- bytes avoided by lifecycle;
- tokens received;
- tokens removed by context compiler;
- tokens avoided by cache;
- model calls avoided;
- large-model calls avoided;
- GPU seconds avoided;
- training runs avoided;
- checkpoint bytes avoided;
- rehydration latency;
- gateway overhead;
- verifier failures;
- policy denials;
- cache staleness;
- fallback rate;
- plugin error rate;
- scheduler shifts.

## North-star metrics

### Verified useful output per joule

This is the long-term target. It is hard to measure perfectly but aligns URP with data-center reduction.

### Verified useful output per dollar

Useful for startups and enterprises.

### Verified useful output per byte

Useful for data platforms.

## Metric naming

Suggested Prometheus metrics:

```text
urp_work_units_total
urp_work_unit_bytes_in_total
urp_work_unit_bytes_stored_total
urp_bytes_avoided_total
urp_chunks_total
urp_chunk_dedupe_hits_total
urp_compression_ratio
urp_rehydration_seconds
urp_policy_denials_total
urp_verifier_failures_total
urp_cache_hits_total
urp_cache_misses_total
urp_ai_input_tokens_total
urp_ai_context_tokens_removed_total
urp_ai_large_model_calls_total
urp_ai_large_model_calls_avoided_total
urp_ai_fallbacks_total
urp_training_gpu_seconds_avoided_total
urp_scheduler_jobs_shifted_total
urp_manifest_write_seconds
urp_ledger_events_total
```

## Trace model

A request trace should include spans:

```text
urp.intake
urp.classify
urp.policy.evaluate
urp.plan
urp.execute
urp.transform
urp.cache.lookup
urp.ai.context_compile
urp.ai.route
urp.verify
urp.manifest.write
urp.ledger.append
urp.rehydrate
```

Span attributes:

- work_unit_id;
- manifest_id;
- tenant hash;
- namespace;
- contract;
- policy_bundle_id;
- mode;
- adapter;
- action;
- cache_result;
- model_route;
- verifier_result.

Do not put raw prompts or sensitive object keys in spans by default.

## Logs

Structured logs should include:

- severity;
- event type;
- work unit id;
- manifest id;
- policy bundle id;
- trace id;
- error code;
- redacted message.

Use logs for debugging, not audit. Ledger is audit.

## Dashboards

### Executive dashboard

- total bytes avoided;
- total AI calls avoided;
- total estimated cost avoided;
- peak compute shifted;
- risk events;
- savings by business unit.

### Platform dashboard

- gateway latency;
- manifest store health;
- chunk store health;
- ledger append rate;
- policy evaluation latency;
- plugin errors;
- fallback rate.

### AI dashboard

- requests by route;
- cache hit rates;
- semantic cache acceptance;
- context tokens removed;
- verifier failures;
- model escalation rates;
- p95 latency by path.

### Data dashboard

- storage by contract;
- hot/warm/cold distribution;
- dedupe domains;
- compression ratios;
- rehydration test status;
- lifecycle candidates.

### Security dashboard

- policy denials;
- semantic reductions;
- legal holds;
- cross-tenant attempts blocked;
- plugin changes;
- high-risk overrides.

## SLOs

### Gateway availability

Target:

- 99.9% for dev/small deployments;
- 99.99% for enterprise hot path.

### Exact rehydration correctness

Target:

- 100% for exact-byte contracts.

Any failure is severe.

### Policy evaluation latency

Target:

- p95 under 10 ms from warm cache for hot path.

### Manifest write latency

Target:

- p95 under 50 ms for local/regional metadata path.

### AI gateway overhead

Target:

- p95 overhead under 100 ms for cache miss pass-through;
- cache hit faster than baseline provider call.

### Cache correctness

Target:

- 0 known cross-tenant unauthorized hits.

### Verifier failure handling

Target:

- 100% fallback for required verifier failures.

## Error budgets

Optimization should consume error budget only explicitly.

If URP increases latency or failure rate beyond SLO:

- disable advanced reducers;
- keep exact path;
- keep observe mode;
- alert maintainers.

## Benchmark suites

### Object exact suite

Workloads:

- random bytes;
- repeated bytes;
- log-like text;
- shifted backups;
- JSON files;
- compressed files;
- encrypted-like random files;
- multipart uploads;
- range reads.

Metrics:

- write throughput;
- read throughput;
- stored bytes;
- metadata overhead;
- rehydration correctness.

### AI gateway suite

Workloads:

- repeated exact prompts;
- paraphrased prompts;
- long duplicated RAG context;
- tool-solvable questions;
- easy classification;
- hard reasoning;
- stale source cache;
- cross-tenant cache attempt.

Metrics:

- cache hit rate;
- false acceptance rate;
- large-model calls avoided;
- tokens avoided;
- latency;
- verifier failure rate.

### Lakehouse suite

Workloads:

- many small files;
- skewed partitions;
- duplicate row groups;
- low-cardinality columns;
- high-cardinality columns.

Metrics:

- storage reduction;
- query scan reduction;
- compaction time;
- snapshot correctness.

### Stream suite

Workloads:

- heartbeat events;
- duplicate messages;
- incident bursts;
- late arrivals;
- schema evolution.

Metrics:

- bytes reduced;
- replay correctness;
- anomaly preservation;
- consumer latency.

### Training suite

Workloads:

- duplicate dataset samples;
- repeated fine-tunes;
- checkpoints;
- adapters;
- failed experiments.

Metrics:

- training examples removed;
- GPU hours avoided;
- checkpoint bytes avoided;
- eval score preservation.

## Savings estimation

Savings should be separated into measured and estimated.

Measured:

- physical bytes stored;
- baseline bytes in;
- cache hit provider call avoided;
- tokens removed from prompt;
- chunks reused.

Estimated:

- joules avoided;
- cost avoided;
- future data-center capacity avoided.

Label estimates clearly.

## Rehydration testing

URP should periodically test restore paths.

Types:

- sampled exact-byte restore;
- full restore for selected critical datasets;
- table logical verification;
- AI cache source validation;
- manifest migration restore.

## Canarying

Rollout pattern:

1. observe only;
2. shadow transform;
3. canary exact mode;
4. expand exact mode;
5. canary semantic mode;
6. expand with SLO guardrails.

Canary inputs:

- tenant;
- namespace;
- percentage;
- work unit kind;
- contract.

## Rollback

Rollback strategies:

- bypass gateway;
- disable plugin;
- switch policy bundle;
- force exact contract;
- rehydrate from original chunks;
- clear semantic cache;
- disable model router;
- route to baseline model provider.

Every advanced feature needs a rollback path documented before production.

## Operations runbook

### Gateway degraded

1. check health endpoint;
2. check backend storage;
3. check manifest store;
4. check policy cache;
5. disable advanced reducers;
6. switch to pass-through if allowed;
7. alert owning team.

### Rehydration failure

1. mark manifest quarantined;
2. block lifecycle deletion for sources;
3. fetch chunks;
4. verify checksums;
5. inspect transform stack;
6. attempt fallback source;
7. emit incident ledger event;
8. run related manifest checks.

### Semantic cache incident

1. disable semantic cache for affected domain;
2. query ledger for accepted hits;
3. invalidate entries with affected source fingerprints;
4. notify application owners;
5. tighten thresholds/verifiers;
6. add regression tests.

### Policy misconfiguration

1. freeze current policy bundle;
2. roll back to previous bundle;
3. query ledger for affected decisions;
4. re-evaluate impacted work units;
5. publish postmortem.

### Plugin failure

1. disable plugin;
2. route to fallback;
3. quarantine manifests produced by plugin if needed;
4. run plugin conformance tests;
5. require signed update.

## Alerting

Critical alerts:

- exact rehydration failure;
- cross-tenant cache attempt accepted;
- policy evaluation unavailable in enforce mode;
- manifest store write failure;
- ledger append failure;
- verifier failure without fallback;
- legal hold deletion attempt;
- plugin signature failure.

Warning alerts:

- cache hit rate drops;
- compression ratio unexpectedly drops;
- p95 latency increases;
- dedupe index growth high;
- semantic cache staleness high;
- model fallback rate high;
- scheduler misses deadlines.

## Capacity planning

URP itself consumes resources.

Plan for:

- gateway CPU;
- chunking CPU;
- compression CPU;
- manifest database IOPS;
- ledger storage;
- cache RAM;
- semantic index storage;
- rehydration bandwidth;
- verifier compute.

URP must report its own overhead separately from savings.

## Cost accounting

Cost reports should break down:

- baseline cost;
- URP overhead;
- net savings;
- storage savings;
- AI inference savings;
- training savings;
- network savings;
- operational cost.

## Data quality

Reduction can expose data-quality problems:

- duplicate datasets;
- stale documents;
- unused logs;
- bloated prompts;
- repeated training samples;
- unused model variants.

URP should report these as recommendations.

## Benchmark acceptance for release

A release should not ship if:

- exact restore tests fail;
- policy tests fail;
- cache isolation tests fail;
- p95 hot-path overhead regresses beyond threshold;
- manifest migration breaks old samples;
- conformance suite fails.

## Ideal-state operations

In the ideal state, URP is operated like identity or observability infrastructure: always on, conservative by default, measured continuously, and rolled out through policy.

<!-- END docs/09_OBSERVABILITY_BENCHMARKS_OPS.md -->


---

<!-- BEGIN docs/10_RESEARCH_LANDSCAPE.md -->

# 10 — Research Landscape and Technical Grounding

## Purpose

This document grounds URP in known systems and research. It is not a literature survey for its own sake. Each item explains what URP should learn and what product decision it supports.

Last reviewed: 2026-07-08

## Foundational constraint: exact universal compression is impossible

URP must never claim it can shrink every arbitrary payload while preserving exact bytes. Shannon's source coding theorem establishes limits for lossless compression relative to entropy. High-entropy, encrypted, already-compressed, or random-like data may not shrink meaningfully.

URP product implication:

- default to exact fallback;
- estimate reducibility before expensive work;
- treat semantic reduction as policy-governed, not lossless compression;
- report incompressible work units honestly.

Reference:

- Shannon source coding theorem: https://en.wikipedia.org/wiki/Shannon%27s_source_coding_theorem

## Data-center and AI energy pressure

Data-center growth is no longer only a storage problem. AI inference, training, networking, memory movement, cooling, and peak power all contribute. URP therefore targets both data and AI work units.

Product implication:

- track storage, network, tokens, model calls, training GPU time, and scheduling;
- optimize peak demand, not only aggregate bytes;
- provide an energy-aware scheduler for flexible workloads.

References:

- IEA Energy and AI: https://www.iea.org/reports/energy-and-ai/energy-demand-from-ai
- Google demand-response/carbon-aware discussion: https://cloud.google.com/blog/products/infrastructure/using-demand-response-to-reduce-data-center-power-consumption

## Compression and physical data reduction

### Zstandard

Zstd is a practical general-purpose lossless compressor with a strong speed/ratio tradeoff.

URP use:

- default exact-safe compression plugin;
- hot/warm/cold compression levels;
- dictionaries for repeated logs and event formats;
- compression trial during reducibility estimation.

Reference:

- RFC 8878: https://datatracker.ietf.org/doc/html/rfc8878

### Content-defined chunking

Content-defined chunking enables dedupe across shifted data because chunk boundaries depend on content rather than fixed offsets.

URP use:

- backups;
- object versions;
- model checkpoints;
- container layers;
- repeated exports;
- log archives.

Reference:

- Borg internals and chunking concepts: https://borgbackup.readthedocs.io/en/stable/internals/data-structures.html

### Content-addressed storage

CAS stores chunks by hash. It is useful but must be domain-isolated to avoid cross-tenant side channels.

URP use:

- chunk store;
- manifest segment refs;
- duplicate detection;
- checkpoint deltas.

## Table and analytics formats

### Apache Parquet

Parquet is a columnar format designed for efficient storage and analytics.

URP use:

- exact-logical structured file conversion;
- per-column compression choices;
- row-group optimization;
- data skipping.

Reference:

- Apache Parquet: https://parquet.apache.org/

### Apache Arrow

Arrow provides a language-independent columnar memory format.

URP use:

- in-memory interchange;
- plugin interface for table data;
- efficient data movement between Python, Rust, Go, and analytics engines.

Reference:

- Arrow columnar format: https://arrow.apache.org/docs/format/Columnar.html

### Apache Iceberg

Iceberg supports schema and partition evolution and table snapshots.

URP use:

- safe lakehouse optimization through table protocol;
- snapshot lineage;
- exact-logical contracts;
- rollback.

Reference:

- Iceberg evolution: https://iceberg.apache.org/docs/latest/evolution/

### Delta Lake

Delta Lake provides ACID table semantics on object storage.

URP use:

- integrate with transaction log rather than raw file mutation;
- exact-logical compaction with rollback.

Reference:

- Delta Lake docs: https://docs.delta.io/latest/index.html

## Observability standards

### OpenTelemetry

OpenTelemetry provides standardized telemetry APIs and formats.

URP use:

- traces for planning/execution;
- metrics for savings and overhead;
- logs for debugging;
- exporter ecosystem.

Reference:

- OpenTelemetry overview: https://opentelemetry.io/docs/what-is-opentelemetry/

## AI routing and cascades

### FrugalGPT

FrugalGPT studies cost reduction through model cascades and adaptive LLM use.

URP use:

- model routing as a first-class action;
- confidence and verifier-aware fallback;
- cost/quality tradeoff tracking.

Reference:

- FrugalGPT: https://arxiv.org/abs/2305.05176

### RouteLLM

RouteLLM explores routing simpler queries to cheaper models and harder queries to stronger models.

URP use:

- model router baseline;
- open router benchmark integration;
- route manifests and fallback reporting.

Reference:

- RouteLLM: https://openreview.net/forum?id=8n3uWUEuue

## AI serving and memory efficiency

### vLLM and PagedAttention

vLLM's PagedAttention manages KV cache memory in blocks to reduce waste.

URP use:

- choose runtime with efficient KV handling;
- record KV/prefix-cache usage in compute manifest;
- avoid long prompts through context compiler before runtime.

Reference:

- vLLM paper: https://arxiv.org/abs/2309.06180

### FlashAttention

FlashAttention reduces memory traffic for attention through IO-aware algorithms.

URP use:

- prefer runtimes and model configurations using efficient attention kernels;
- classify long-context workloads for runtime placement.

Reference:

- FlashAttention: https://arxiv.org/abs/2205.14135

### KIVI and KV cache quantization

KIVI investigates KV-cache quantization for large language models.

URP use:

- bounded approximate contract for KV cache compression;
- runtime selection;
- memory pressure reduction.

Reference:

- KIVI: https://proceedings.mlr.press/v235/liu24bz.html

### KVQuant

KVQuant studies quantization for the KV cache and long-context serving.

URP use:

- memory reduction for long contexts;
- verifier and quality measurements before default enablement.

Reference:

- KVQuant: https://arxiv.org/abs/2401.18079

## AI training and adaptation efficiency

### LoRA

LoRA reduces trainable parameters through low-rank adaptation.

URP use:

- recommend adapters before full fine-tune;
- store adapter artifacts separately;
- route tenant-specific behavior through adapter registry.

Reference:

- LoRA: https://arxiv.org/abs/2106.09685

### QLoRA

QLoRA enables fine-tuning through quantized base models with LoRA adapters.

URP use:

- training reducer path for resource-constrained fine-tunes;
- policy to avoid full model copies.

Reference:

- QLoRA: https://arxiv.org/abs/2305.14314

### S-LoRA

S-LoRA targets scalable serving of many LoRA adapters.

URP use:

- multi-tenant adapter serving;
- route work units to base model + adapter;
- avoid full model duplication.

Reference:

- S-LoRA: https://arxiv.org/abs/2311.03285

## Dataset deduplication and quality

### Deduplicating training data

Research shows deduplication can reduce memorization and improve or preserve training efficiency.

URP use:

- dataset reducer before training;
- contaminated benchmark removal;
- duplicate sample manifesting;
- training GPU-hours avoided metric.

Reference:

- Deduplicating Training Data Makes Language Models Better: https://arxiv.org/abs/2107.06499

## Semantic caching

Semantic caching stores responses or intermediate outputs keyed by meaning, not exact text. It can reduce repeated AI computation but requires strict guardrails.

URP use:

- exact cache first;
- semantic cache only by policy;
- source fingerprints;
- freshness windows;
- verifiers;
- fallback.

References:

- Semantic Cache for LLMs: https://arxiv.org/abs/2406.12649
- LMCache: https://arxiv.org/abs/2503.01185

## Carbon-aware and energy-aware scheduling

Flexible workloads can shift by time and location.

URP use:

- schedule batch inference, embeddings, evaluations, dataset cleaning, and training;
- do not shift interactive workloads beyond latency budgets;
- expose energy-aware policy controls.

Reference:

- Google demand response/carbon-aware scheduling: https://cloud.google.com/blog/products/infrastructure/using-demand-response-to-reduce-data-center-power-consumption

## How URP differs from research prototypes

Most papers optimize one layer:

- model routing;
- cache;
- attention kernel;
- quantization;
- data dedupe;
- compression;
- scheduling.

URP's product opportunity is the control plane that safely composes these techniques across existing infrastructure.

## Research-to-product mapping

| Research area | URP product feature |
|---|---|
| Source coding | exact fallback and entropy estimates |
| Content-defined chunking | chunk store and dedupe |
| Columnar formats | exact-logical table optimization |
| OpenTelemetry | metrics/traces/observability |
| FrugalGPT/RouteLLM | model router |
| vLLM/PagedAttention | runtime placement and KV awareness |
| FlashAttention | efficient runtime preference |
| KV quantization | long-context memory reduction |
| LoRA/QLoRA/S-LoRA | training reducer and adapter registry |
| Dataset dedupe | training dataset optimizer |
| Semantic cache | AI reuse layer |
| Carbon-aware scheduling | flexible job scheduler |

## Research gaps URP should explore

1. Verifier-aware semantic cache safety.
2. Unified manifest for data and AI work units.
3. Cross-workload savings attribution.
4. Tenant-safe dedupe without side channels.
5. Energy-aware model routing with quality contracts.
6. Lifecycle conversion from raw data to semantic artifacts.
7. Open conformance suite for AI gateways.
8. Reduction proofs for semantic transformations.
9. Portable manifests across storage and AI providers.
10. Distillation from repeated verified enterprise workflows.

## Evaluation methodology

URP research evaluation should report:

- baseline path;
- URP path;
- workload type;
- contract;
- policy;
- verifier;
- reduction ratio;
- false acceptance;
- fallback rate;
- latency overhead;
- quality delta;
- cost estimate;
- energy estimate if measured.

## Claims to avoid

Avoid claims such as:

- "compresses all data";
- "eliminates data centers";
- "AI with no GPUs";
- "semantic cache is always safe";
- "lossless summarization";
- "drop-in for every POSIX workload";
- "zero overhead".

Use measured, scoped claims.

## Responsible claim examples

Better claims:

- "reduces duplicate object chunks within configured domains";
- "can avoid repeated large-model calls for verified repeated requests";
- "can reduce prompt tokens by deduplicating context";
- "falls back to exact storage for incompressible payloads";
- "supports policy-gated semantic retention";
- "can shift flexible jobs when deadlines allow."

## Maintainer research process

For each new paper or technique:

1. summarize problem;
2. record assumptions;
3. identify contract compatibility;
4. identify policy risks;
5. define verifier;
6. design manifest fields;
7. benchmark against baseline;
8. document fallback;
9. add conformance tests if promoted.

## Current recommended implementation order from research

1. Exact hash/dedupe/compression.
2. Exact AI cache and prompt normalization.
3. Context compiler.
4. Model router with fallback.
5. Efficient runtime integrations.
6. Semantic cache with source/verifier guardrails.
7. Training reducer with adapters and dedupe.
8. Energy-aware scheduler.
9. Distillation factory.

## Research source index

```yaml
{
  "shannon_source_coding": "https://en.wikipedia.org/wiki/Shannon%27s_source_coding_theorem",
  "iea_energy_ai": "https://www.iea.org/reports/energy-and-ai/energy-demand-from-ai",
  "zstd_rfc": "https://datatracker.ietf.org/doc/html/rfc8878",
  "borg_cdc": "https://borgbackup.readthedocs.io/en/stable/internals/data-structures.html",
  "parquet": "https://parquet.apache.org/",
  "arrow": "https://arrow.apache.org/docs/format/Columnar.html",
  "iceberg_evolution": "https://iceberg.apache.org/docs/latest/evolution/",
  "delta_lake": "https://docs.delta.io/latest/index.html",
  "opentelemetry": "https://opentelemetry.io/docs/what-is-opentelemetry/",
  "frugalgpt": "https://arxiv.org/abs/2305.05176",
  "routellm": "https://openreview.net/forum?id=8n3uWUEuue",
  "vllm": "https://arxiv.org/abs/2309.06180",
  "flashattention": "https://arxiv.org/abs/2205.14135",
  "kivi": "https://proceedings.mlr.press/v235/liu24bz.html",
  "kvquant": "https://arxiv.org/abs/2401.18079",
  "lora": "https://arxiv.org/abs/2106.09685",
  "qlora": "https://arxiv.org/abs/2305.14314",
  "slora": "https://arxiv.org/abs/2311.03285",
  "dedupe_lm_training": "https://arxiv.org/abs/2107.06499",
  "semcache_2024": "https://arxiv.org/abs/2406.12649",
  "lmcache_2025": "https://arxiv.org/abs/2503.01185",
  "google_carbon_aware": "https://cloud.google.com/blog/products/infrastructure/using-demand-response-to-reduce-data-center-power-consumption"
}
```

<!-- END docs/10_RESEARCH_LANDSCAPE.md -->


---

<!-- BEGIN docs/11_OPEN_SOURCE_GOVERNANCE_ADOPTION.md -->

# 11 — Open Source Governance and Adoption

## Purpose

URP should be open source to maximize trust, adoption, auditability, and platform compatibility. The open-source strategy must be designed from the beginning rather than added later.

## License recommendation

Use Apache-2.0 for the core project.

Reasons:

- enterprise-friendly;
- patent grant;
- widely understood;
- compatible with commercial offerings;
- encourages broad adoption.

## Governance goals

- prevent single-vendor lock-in;
- keep manifest and policy specs open;
- maintain conformance suites publicly;
- support commercial ecosystems without weakening the commons;
- make security and compatibility decisions transparent.

## Project structure

Recommended top-level repositories:

### urp

Core monorepo.

### urp-conformance

Protocol and plugin conformance tests. Can be inside monorepo initially.

### urp-plugins

Community plugin registry.

### urp-spec

If URP becomes widely adopted, split manifest/policy/protocol specs into a standards repo.

## Maintainer roles

### Core maintainer

Can merge core changes, release versions, and approve plugin API changes.

### Area maintainer

Owns an area such as S3 gateway, AI gateway, policy, security, SDK, docs, or conformance.

### Security maintainer

Handles private vulnerability reports and coordinated disclosure.

### Plugin maintainer

Owns a plugin but not core.

### Reviewer

Can approve changes but not release.

## Decision process

Use:

- public RFCs for major changes;
- maintainer approval for routine changes;
- security private process for vulnerabilities;
- compatibility review for manifest/policy changes.

## RFC template

```markdown
# RFC: Title

## Summary
## Problem
## Goals
## Non-goals
## User impact
## Technical design
## Manifest changes
## Policy changes
## Security impact
## Compatibility impact
## Alternatives
## Rollout
## Open questions
```

## Compatibility policy

Stable specs:

- manifest schema;
- work unit schema;
- policy schema;
- ledger event schema;
- plugin descriptor;
- conformance tests.

Breaking changes require:

- RFC;
- migration tool;
- version bump;
- deprecation window;
- compatibility tests.

## Conformance certification

A plugin or adapter can claim conformance only when it passes public tests.

Conformance levels:

- experimental;
- alpha;
- beta;
- stable;
- certified.

Certified may require human review or third-party validation.

## Open-source core boundaries

The open-source core must include enough to be useful:

- policy engine;
- manifest store;
- ledger;
- S3 gateway baseline;
- AI gateway baseline;
- chunking;
- compression plugin interface;
- exact cache;
- basic semantic cache with guardrails;
- CLI;
- SDKs;
- conformance tests.

Do not put the entire useful product behind a proprietary wall.

## Commercial ecosystem

Healthy commercial offerings can include:

- managed URP cloud;
- enterprise dashboards;
- hosted policy workflows;
- compliance templates;
- certified connectors;
- support;
- managed semantic indexes;
- optimization recommendations.

Avoid proprietary-only manifest formats or plugins required for basic functionality.

## Community adoption tactics

### Developers

- simple Docker quickstart;
- CLI demos;
- OpenAI-compatible proxy demo;
- S3 local gateway demo;
- clear SDK examples.

### Startups

- cost-saving templates;
- Vercel/Fly/Render/Railway examples;
- local object store examples;
- small team policy defaults.

### Enterprises

- reference architectures;
- threat model;
- compliance guide;
- migration playbooks;
- conformance reports;
- policy-as-code integration;
- Helm chart.

### Researchers

- benchmark harness;
- reproducible workloads;
- paper implementation notes;
- plugin API for new algorithms.

### Cloud providers

- backend adapters;
- marketplace packages;
- compatibility docs;
- no lock-in stance.

## Documentation standards

Each feature doc must include:

- purpose;
- user story;
- configuration;
- API;
- manifest fields;
- policy fields;
- metrics;
- security considerations;
- tests;
- rollback.

## Release process

Recommended release train:

- monthly minor releases;
- patch releases as needed;
- LTS every six months once mature;
- security releases immediately.

Release checklist:

- all tests pass;
- conformance pass;
- schema compatibility check;
- docs updated;
- changelog;
- migration notes;
- signed artifacts;
- SBOM;
- vulnerability scan.

## Security process

- SECURITY.md with contact;
- private vulnerability intake;
- severity scoring;
- embargo process;
- patch releases;
- advisory publication;
- credit reporters.

## Supply-chain security

Use:

- signed commits for maintainers where possible;
- signed releases;
- SBOM;
- dependency scanning;
- SLSA-oriented build process;
- reproducible builds for critical binaries;
- container image scanning.

## Trademark

If URP becomes large, define trademark rules:

- allow "compatible with URP" only with conformance tests;
- prevent misleading "certified" claims;
- keep community forks healthy.

## Project values

- compatibility;
- transparency;
- reversibility;
- safety;
- measurable savings;
- open specs;
- pragmatic engineering.

## Community anti-patterns

Avoid:

- hype claims;
- closed governance;
- cloud-provider favoritism;
- proprietary extensions that break portability;
- unreviewed plugins advertised as safe;
- docs that hide limitations.

## Good first issues

- improve CLI examples;
- add manifest sample;
- add policy validation tests;
- build a small adapter;
- add dashboard screenshots;
- write a benchmark workload;
- improve SDK docs.

## Advanced contributor areas

- S3 conformance;
- semantic cache verifier;
- lakehouse transaction integration;
- KV-cache telemetry;
- training reducer;
- plugin sandbox;
- policy proof engine;
- energy scheduler.

## Adoption message

URP should be introduced as:

> A compatibility-first open-source reduction layer for data and AI workloads, designed to reduce infrastructure waste without forcing rewrites or hiding risk.

## Long-term standardization

If widely adopted, URP can become an open standard for:

- reduction manifests;
- compute manifests;
- semantic cache safety metadata;
- AI route manifests;
- reduction proofs;
- policy-gated lifecycle transformations.

## Governance invariant

The open-source project must preserve user trust by making reduction decisions inspectable and portable.

<!-- END docs/11_OPEN_SOURCE_GOVERNANCE_ADOPTION.md -->


---

<!-- BEGIN docs/12_DEPLOYMENT_PLAYBOOKS.md -->

# 12 — Deployment Playbooks

## Purpose

This document explains how different users adopt URP without disrupting current workflows.

## Universal deployment rule

Start in observe mode. Measure. Then enable exact-safe reductions. Only later enable semantic or approximate reductions with policy and verifiers.

## Local developer playbook

### Goal

Understand URP and reduce repeated local AI calls or test data.

### Steps

1. Install CLI.
2. Run local manifest store.
3. Plan a file.
4. Run AI gateway against a test provider key.
5. Inspect manifest.
6. Inspect ledger.
7. Enable exact cache.

### Commands

```bash
urp init
urp plan --kind byte_object --file sample.log
urp gateway ai --listen :8080 --provider-env OPENAI_API_KEY
urp ledger query --last 20
```

### Success criteria

- developer understands work units;
- exact cache works;
- no production data involved.

## Startup playbook

### Goal

Reduce AI and object storage costs quickly.

### Deployment

```text
Docker Compose
  urp-control
  urp-ai-gateway
  urp-s3-gateway
  postgres
  minio or cloud object backend
```

### Steps

1. Put internal tools behind AI gateway.
2. Enable exact cache.
3. Measure repeated prompts.
4. Add context compiler for RAG app.
5. Put backup bucket behind object gateway.
6. Enable exact dedupe/compression.
7. Add dashboards.

### Policies

- semantic cache off by default;
- exact cache same app only;
- object dedupe same tenant only;
- deletion disabled until reviewed.

## Enterprise observe-only playbook

### Goal

Discover savings without changing behavior.

### Deployment

- traffic mirror;
- proxy in non-invasive mode;
- read-only lakehouse scan;
- AI request logs with redaction;
- manifest store;
- telemetry export.

### Outputs

- savings estimate;
- risk classification;
- duplicate map;
- prompt waste report;
- workload heat map;
- policy recommendations.

### Success criteria

- no application behavior changes;
- owners receive useful reports;
- security signs off on next stage.

## Enterprise exact-safe playbook

### Goal

Enable safe savings for selected workloads.

### Candidate workloads

- backups;
- container layers;
- log archives;
- duplicate objects;
- generated reports;
- repeated AI dev prompts.

### Actions

- whole-object dedupe;
- content-defined chunking;
- zstd compression;
- exact prompt cache;
- context dedupe in shadow mode.

### Required tests

- exact restore;
- range read;
- cache isolation;
- policy denial;
- failover.

## AI platform playbook

### Goal

Reduce model calls and prompt bloat.

### Steps

1. Insert OpenAI-compatible gateway.
2. Run observe mode for all requests.
3. Report task classes and token waste.
4. Enable exact cache for deterministic internal assistants.
5. Enable context compiler for RAG apps.
6. Add model router in shadow mode.
7. Add verifiers.
8. Enable small-model route for accepted classes.
9. Pilot semantic cache.
10. Distill repeated workflows.

### Required controls

- source fingerprints;
- freshness;
- tenant isolation;
- fallback model;
- verifier logs;
- redacted prompt storage.

## Data platform playbook

### Goal

Reduce lakehouse and stream waste.

### Steps

1. Scan object store and catalog.
2. Identify duplicate files and tiny files.
3. Recommend compaction.
4. Run table-native compaction in dev.
5. Verify exact-logical results.
6. Enable snapshot-aware policy.
7. Add lifecycle rules.
8. Add stream archival reduction.

### Do not

- mutate table files outside transaction protocol;
- drop raw data before retention review;
- summarize regulated data silently.

## Regulated enterprise playbook

### Goal

Use URP safely under strict controls.

### Defaults

- exact_bytes global;
- semantic reduction disabled;
- cross-tenant cache disabled;
- local-only manifest store;
- encryption everywhere;
- signed policy bundles;
- legal hold integration;
- manual approvals for lifecycle deletion.

### Rollout

1. observe-only;
2. exact compression/dedupe for non-regulated data;
3. manifest and ledger audit review;
4. limited exact-logical table optimization;
5. semantic reduction only for approved non-record data.

## Edge playbook

### Goal

Reduce network and local AI calls.

### Actions

- compress before upload;
- dedupe chunks locally;
- cache repeated prompts locally;
- summarize low-risk telemetry;
- send manifests when online;
- preserve raw incident data.

### Constraints

- policy cache expiry;
- local key storage;
- offline mode;
- resource caps;
- delayed ledger sync.

## Kubernetes deployment

Components:

- control-plane deployment;
- gateway deployment;
- worker deployment;
- scheduler;
- Postgres;
- object store credentials;
- config maps for policies;
- secrets for keys;
- service monitors.

Rollout:

```bash
kubectl apply -f examples/kubernetes/urp-control-plane.yaml
```

## Cloud deployment patterns

### AWS

- S3 backend;
- EKS;
- RDS Postgres;
- KMS;
- CloudWatch/OpenTelemetry exporter;
- IAM roles for service accounts.

### Azure

- Blob Storage backend;
- AKS;
- Azure Database for PostgreSQL;
- Key Vault;
- Monitor exporter.

### Google Cloud

- Cloud Storage backend;
- GKE;
- Cloud SQL;
- Cloud KMS;
- Cloud Monitoring exporter.

### On-prem

- MinIO/Ceph;
- Kubernetes or systemd;
- Postgres;
- Vault/HSM;
- local model server;
- Prometheus/Grafana.

## Migration plan

### Existing object bucket

1. observe reads/writes;
2. build duplicate map;
3. select prefix;
4. enable exact-safe writes;
5. backfill old objects asynchronously;
6. verify sample restores;
7. update lifecycle.

### Existing AI app

1. switch base URL to URP gateway;
2. run pass-through;
3. enable metrics;
4. enable exact cache;
5. enable context compiler;
6. shadow model router;
7. enforce router with fallback.

### Existing lakehouse

1. catalog scan;
2. recommendations only;
3. dev table optimization;
4. snapshot verification;
5. production canary;
6. rollback test.

## Rollback procedures

### Object gateway rollback

- switch DNS/endpoint to original object store;
- keep manifest store read-only;
- rehydrate affected objects if needed;
- disable lifecycle jobs.

### AI gateway rollback

- switch base URL to provider;
- disable semantic cache;
- export compute manifests;
- preserve ledger for audit.

### Policy rollback

- publish previous bundle;
- mark bad bundle deprecated;
- re-evaluate affected manifests;
- emit rollback event.

## Enterprise change management

Required artifacts:

- architecture diagram;
- threat model;
- data flow;
- policy defaults;
- rollback plan;
- SLOs;
- test evidence;
- owner signoff.

## Adoption success checklist

- observe mode data collected;
- exact restore tested;
- security policy approved;
- metrics exported;
- rollback tested;
- owners trained;
- cache isolation tested;
- semantic features disabled or approved;
- incident runbook written.

## Ideal-state adoption

URP becomes part of platform golden paths:

- new object buckets default through URP;
- AI apps default through URP gateway;
- batch jobs declare deadlines;
- training jobs declare dataset manifests;
- tables include URP optimization metadata;
- developers inspect manifests in CI.

<!-- END docs/12_DEPLOYMENT_PLAYBOOKS.md -->


---

<!-- BEGIN codex/CODEX_BUILD_PROMPT.md -->

# Codex Build Prompt

You are building Universal Reduction Plane (URP), a single open-source product that reduces data and AI infrastructure waste through one lifecycle:

```text
Work Unit + Contract + Policy -> Plan -> Execute -> Verify -> Manifest + Ledger
```

Do not split the product into separate data and AI products. Internal modules may be separated, but the external model must be one URP.

## Build goals

1. Implement the core domain model.
2. Implement policy evaluation with safe defaults.
3. Implement a planner that handles byte objects and AI prompt requests.
4. Implement exact-safe data execution.
5. Implement an OpenAI-compatible AI gateway skeleton.
6. Implement manifests, ledger, CLI, metrics, and tests.
7. Keep all semantic/approximate reducers policy-gated and disabled by default.

## Hard invariants

- Unknown data defaults to exact preservation.
- Cross-tenant cache and dedupe are disabled by default.
- Semantic reduction requires policy approval and verifier.
- Every executed action writes ledger events.
- Every stored or computed result gets a manifest.
- Exact-byte contracts must support byte-for-byte rehydration.
- Plugin interfaces must be versioned and conformance-tested.
- Rollback paths must exist before advanced reducers are enabled.

## First issue sequence

1. Make tests pass.
2. Convert reference skeleton into packages.
3. Add schema validation.
4. Add local manifest store.
5. Add JSONL ledger.
6. Add CLI commands.
7. Add object exact path.
8. Add AI exact cache.
9. Add context compiler.
10. Add API skeleton.

## Definition of done

A demo should show:

```bash
urp plan --kind byte_object --input ./sample.log
urp execute --kind byte_object --input ./sample.log
urp manifest get <id>
urp gateway ai --provider mock
curl /v1/chat/completions twice and see second request served from exact cache
```

All output must include work_unit_id and manifest_id where applicable.

<!-- END codex/CODEX_BUILD_PROMPT.md -->


---

<!-- BEGIN codex/ACCEPTANCE_CHECKLIST.md -->

# Acceptance Checklist

## Repository

- [ ] License present.
- [ ] README quickstart works.
- [ ] CI runs tests.
- [ ] Formatting configured.
- [ ] Security policy present.
- [ ] Contribution guide present.

## Core

- [ ] WorkUnit schema implemented.
- [ ] Manifest schema implemented.
- [ ] Policy schema implemented.
- [ ] Ledger event schema implemented.
- [ ] IDs use stable prefixes.
- [ ] JSON serialization tested.

## Policy

- [ ] Exact default.
- [ ] Legal hold override.
- [ ] Cross-tenant cache denied.
- [ ] Cross-tenant dedupe denied.
- [ ] Semantic transforms denied unless allowed.
- [ ] Explain output includes matched rules.

## Data path

- [ ] Hashing.
- [ ] Chunking.
- [ ] Chunk store.
- [ ] Compression plugin interface.
- [ ] Exact rehydration.
- [ ] Restore verifier.
- [ ] Manifest write.
- [ ] Ledger events.

## AI path

- [ ] OpenAI-compatible request parsing.
- [ ] Exact cache.
- [ ] Tenant isolation.
- [ ] Context dedupe.
- [ ] Model router.
- [ ] Fallback provider.
- [ ] Verifier hook.
- [ ] Compute manifest.

## Security

- [ ] No raw prompts in default logs.
- [ ] Manifest redaction mode.
- [ ] Plugin descriptor validation.
- [ ] Policy override audited.
- [ ] Cache source fingerprint checks.

## Observability

- [ ] Metrics endpoint.
- [ ] Trace ids.
- [ ] Ledger query.
- [ ] Savings report.
- [ ] Error codes.

## Release

- [ ] Conformance tests.
- [ ] Benchmark suite.
- [ ] Migration notes.
- [ ] Signed release artifacts.

<!-- END codex/ACCEPTANCE_CHECKLIST.md -->


---

<!-- BEGIN codex/ROADMAP_AND_TICKETS.md -->

# Roadmap and Tickets

## Milestone 0: Trustworthy skeleton

- Core dataclasses/types.
- Policy evaluation.
- Planner.
- CLI.
- Unit tests.
- Manifest schema.

## Milestone 1: Exact object MVP

- S3-compatible minimal Put/Get/Head.
- Chunk store.
- Rehydration.
- zstd plugin.
- Manifest store.
- Ledger.

## Milestone 2: AI gateway MVP

- OpenAI-compatible chat endpoint.
- Exact cache.
- Context compiler v0.
- Model router v0.
- Mock provider.
- Compute manifests.

## Milestone 3: Security and policy

- Authn/authz.
- Policy bundles.
- Legal hold.
- Cache isolation.
- Plugin descriptors.
- Redacted manifests.

## Milestone 4: Observability and conformance

- Metrics.
- Traces.
- Dashboards.
- S3 conformance subset.
- AI conformance subset.
- Benchmark runner.

## Milestone 5: Advanced reductions

- Semantic cache.
- Lakehouse optimizer.
- Stream observe adapter.
- Training reducer.
- Checkpoint delta store.
- Energy scheduler.

## Milestone 6: Production

- HA deployments.
- Postgres backends.
- KMS integration.
- Operator.
- Multi-region.
- Disaster recovery.
- Release process.

<!-- END codex/ROADMAP_AND_TICKETS.md -->
