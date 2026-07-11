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
- The local reference denies delete by default; allowed deletes tombstone manifests, retain raw chunks, and omit tombstoned objects from normal list results.
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
The local SDK includes typed WorkUnit builders, manifest lookup/rehydration,
ledger lookups, exact cache controls, local S3 object/multipart helpers, and AI
gateway wrappers.

### Go

Primary for gateways, infrastructure services, and operators.
The local SDK mirrors the TypeScript surface for WorkUnit lifecycle calls,
manifest lookup/rehydration, ledger lookups, exact cache controls, local S3
object/multipart helpers, and AI gateway wrappers.

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
