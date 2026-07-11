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
