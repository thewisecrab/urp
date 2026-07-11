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
