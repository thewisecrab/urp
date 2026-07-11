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
