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
