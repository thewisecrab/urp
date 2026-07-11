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
8. Identity comes from server configuration, never token text or request-body actor fields.
9. Binary payloads use explicit JSON envelopes on JSON routes and raw bytes on rehydration routes.

## Public API groups

```text
/v1/work-units
/v1/plans
/v1/manifests
/v1/ledger
/v1/policies
/v1/approvals
/v1/cache
/v1/chat/completions
/v1/completions
/v1/embeddings
/v1/s3
/v1/scheduler
/v1/adapters
/v1/plugins
/v1/benchmarks
/v1/admin
```

## Authentication and tenant binding

`/healthz` and `/readyz` are public. `/v1/*` and `/metrics` require either:

```http
Authorization: Bearer <configured-token>
```

or `X-API-Key`. Configure tokens through `URP_LOCAL_API_KEY` or
`URP_API_KEYS_JSON`. The latter maps opaque tokens to an actor, tenant, and role
set. Prefix-shaped strings do not assign roles. A tenant-bound principal cannot
override its tenant in a query, body, or nested `urp` options.

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
  "requested_contract": "exact_bytes",
  "payload": {"_urp_encoding": "base64", "data": "..."},
  "metadata": {
    "owner": "platform"
  }
}
```

Response:

```json
{
  "work_unit_id": "wu_...",
  "trace_id": "tr_...",
  "state": "received"
}
```

### List and get work units

```http
GET /v1/work-units?tenant=acme
GET /v1/work-units/{id}
```

### Plan work unit

```http
POST /v1/work-units/{id}/plan
```

Response:

```json
{
  "plan_id": "pl_...",
  "contract": "exact_bytes",
  "mode": "observe",
  "actions": [
    {"type": "hash", "required": true, "risk": "low"},
    {"type": "content_defined_chunk", "required": true, "risk": "low"},
    {"type": "zstd", "required": false, "risk": "low"}
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
  "work_unit_id": "wu_...",
  "manifest_id": "mf_...",
  "accepted": true,
  "mode": "enforce",
  "output": {"sha256": "..."},
  "details": {"bytes_in": 1024, "bytes_stored": 512}
}
```

## Plan API

Planning endpoints return the same `Plan` structure as WorkUnit planning, but
also persist the plan locally so operators and tests can inspect the proposed
action set before execution.

```http
POST /v1/plans
GET /v1/plans?work_unit_id=wu_...
GET /v1/plans/{plan_id}
```

`POST /v1/work-units/{id}/plan`, `POST /v1/work-units/plan`, and CLI planning
commands also write to the local plan store and emit a `plan.created` ledger
event with the WorkUnit id, policy bundle id, trace id, and plan payload.

## Manifest API

### Get manifest

```http
GET /v1/manifests/{manifest_id}
```

### Query by logical ref

```http
GET /v1/manifests?logical_ref=s3://bucket/key
GET /v1/manifests?tenant=acme&redacted=true
```

### Explore manifests

```http
GET /v1/manifests/explore?tenant=acme&kind=byte_object&redacted=true
```

Returns aggregate counts by kind, contract, and state plus redacted row
summaries with manifest ids, trace ids, byte totals, verifier status, and cache
results. It is the local manifest explorer surface for operators and tests.

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

Request:

```json
{
  "tenant": "acme",
  "logical_ref": "s3://bucket/key",
  "redacted": true
}
```

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

Local-ideal mode supports Server-Sent Events using `text/event-stream`.
Production adapters may add WebSocket or managed log-stream backends.

## Structured log API

Operational logs are debug artifacts, not governance records. The default local
store redacts prompt, payload, body, content, token, and secret fields before
writing JSONL entries.

```http
POST /v1/logs/query
```

Request:

```json
{
  "tenant": "acme",
  "event_types": ["manifest.written"],
  "trace_id": "tr_...",
  "limit": 20
}
```

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

### Reload active policy bundle

```http
POST /v1/policies/bundles/{name}/reload
```

Reload validates the currently active local bundle from disk and writes a
`policy.bundle.reloaded` ledger event with the active version and bundle hash.

## Approval API

```http
POST /v1/approvals
GET /v1/approvals?tenant=acme
GET /v1/approvals/{id}
```

Approvals are short-lived signed records bound to tenant, contract, policy
bundle, and optionally WorkUnit id. The authenticated principal supplies the
actor. Policies marked `requires_approval` reject execution until the approval
signature, scope, and expiry validate.

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

Cache storage includes a server-executed verifier specification, for example:

```json
{
  "key": "ck_...",
  "tenant": "acme",
  "value": {"answer": "verified"},
  "verification": {"type": "json_shape", "required_keys": ["answer"]},
  "ttl_seconds": 3600
}
```

Supported verifier types are `chat_completion`, `embedding_shape`,
`json_shape`, `non_empty_text`, and `sha256`. A client-supplied
`verifier_passed` boolean is ignored and rejected by the schema.

## Local S3 gateway API

The local-ideal S3 facade is JSON-over-HTTP. It is not a full AWS S3 wire clone,
but it exercises the same URP object lifecycle: WorkUnit creation, exact
chunking, manifest write, rehydration, range reads, and audit events.

```http
POST /v1/s3/objects
POST /v1/s3/objects/head
POST /v1/s3/objects/get
POST /v1/s3/objects/range
POST /v1/s3/objects/list
POST /v1/s3/objects/delete
POST /v1/s3/multipart/create
POST /v1/s3/multipart/part
POST /v1/s3/multipart/complete
POST /v1/s3/multipart/abort
```

`PutObject` requests may send `body_text` or `body_base64`. Get and range
responses return raw `application/octet-stream` bytes. Multipart parts carry
server-computed digests and completion re-verifies every part before writing
the assembled object through the exact object
executor and returns the resulting manifest id. Delete is denied by default; an
allowed delete tombstones the manifest, retains chunks for audit/rehydration, and
normal list requests hide tombstoned objects unless `include_tombstoned` is true.

## Scheduler API

```http
POST /v1/scheduler/submit
GET /v1/scheduler/jobs
```

The local scheduler persists energy-aware flexible-job decisions and is safe to
run without external grid, queue, or cloud-provider dependencies.

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

Chat completions, text completions, and embeddings all create AI WorkUnits,
evaluate policy, persist plans, write compute manifests, emit ledger events, and
return URP metadata with `work_unit_id`, `manifest_id`, cache status, verifier,
route, and trace id.

The stored compute manifest records fallback status in `result.fallback_used`,
with `result.fallback_reason` populated when the first verifier failure caused a
fallback route. Fallback outputs are written to exact cache only after the
fallback response also passes its verifier.

## Streaming AI responses

Streaming is harder because URP may not know verification outcome until the response is complete.

Options:

1. conservative stream: route directly and record telemetry;
2. buffered stream: verify before sending, increases latency;
3. speculative stream: stream with fallback marker if failure occurs;
4. non-streaming fallback for high-risk tasks.

Default should be conservative and transparent.

## gRPC API

The protobuf file defines the same local-control-plane capability families as
REST so high-throughput internal integrations can avoid ad hoc JSON wrappers:

- WorkUnitService;
- PlanService;
- ManifestService;
- PolicyService;
- LedgerService;
- CacheService;
- AIService;
- PluginService;
- ObjectGatewayService;
- SchedulerService;
- AdminService;
- ObservabilityService.

Provider-specific or plugin-specific payloads use protobuf `Struct` or `Value`
fields, while canonical URP concepts such as `WorkUnitKind`, `Contract`,
`Plan`, `Manifest`, `PolicyDecision`, `VerificationResult`, and `LedgerEvent`
remain typed.

Use gRPC for high-throughput internal integrations and REST for broad adoption.

## CLI

Core commands:

```bash
PYTHONPATH=python python3 -m urp.cli init
PYTHONPATH=python python3 -m urp.cli plan --kind byte_object --file ./data.bin
PYTHONPATH=python python3 -m urp.cli execute --kind byte_object --file ./data.bin
PYTHONPATH=python python3 -m urp.cli work-unit create --kind byte_object --tenant acme --logical-ref file://data.bin --file ./data.bin
PYTHONPATH=python python3 -m urp.cli work-unit plan wu_...
PYTHONPATH=python python3 -m urp.cli work-unit execute wu_...
PYTHONPATH=python python3 -m urp.cli manifest get mf_...
PYTHONPATH=python python3 -m urp.cli manifest rehydrate mf_...
PYTHONPATH=python python3 -m urp.cli manifest rehydrate mf_... --range 0:128
PYTHONPATH=python python3 -m urp.cli manifest list --tenant acme --redacted
PYTHONPATH=python python3 -m urp.cli manifest export --tenant acme
PYTHONPATH=python python3 -m urp.cli manifest explore --tenant acme
PYTHONPATH=python python3 -m urp.cli ledger query --tenant acme
PYTHONPATH=python python3 -m urp.cli ledger query --tenant acme --event-type manifest.written
PYTHONPATH=python python3 -m urp.cli logs query --tenant acme --event-type manifest.written
PYTHONPATH=python python3 -m urp.cli policy validate policy.yaml
PYTHONPATH=python python3 -m urp.cli policy reload --name default-safe
PYTHONPATH=python python3 -m urp.cli gateway ai --provider mock
PYTHONPATH=python python3 -m urp.cli platform matrix
PYTHONPATH=python python3 -m urp.cli platform validate --target all
PYTHONPATH=python python3 -m urp.cli benchmark run --suite object-exact-v1
```

## SDK design

SDKs should provide:

- simple high-level client;
- typed work unit builder;
- stored work unit create/list/get/plan/execute helpers;
- persisted plan create/list/get helpers;
- policy annotations;
- manifest fetch;
- manifest query, explorer, export, and rehydration;
- ledger query;
- structured operational log query;
- policy bundle reload;
- cache controls;
- local S3 object and multipart helpers;
- AI gateway wrapper;
- platform readiness helpers;
- local test utilities.

Python local-runtime example:

```python
from urp.contracts import WorkUnit, WorkUnitKind
from urp.planner import plan_work_unit

work_unit = WorkUnit(
    kind=WorkUnitKind.PROMPT_REQUEST,
    tenant="acme",
    logical_ref="app://support/chat/123",
    payload={"messages": [{"role": "user", "content": "How do I reset VPN?"}]},
)
plan = plan_work_unit(work_unit)
print(plan.plan_id)
```

TypeScript example:

```ts
const urp = new URPClient("http://localhost:8080", { apiKey });
const workUnit = WorkUnitBuilder.promptRequest(
  "acme",
  "app://support/chat/123",
  { messages: [{ role: "user", content: "How do I reset VPN?" }] },
).build();
const plan = await urp.plan(workUnit);
```

Go example:

```go
client := urp.NewAuthenticatedClient("http://localhost:8080", apiKey, "acme")
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

- POST /v1/work-units
- GET /v1/work-units/{id}
- POST /v1/work-units/{id}/plan
- POST /v1/work-units/{id}/execute
- POST /v1/work-units/plan
- POST /v1/work-units/execute
- POST /v1/plans
- GET /v1/plans
- GET /v1/plans/{id}
- GET /v1/manifests/{id}
- GET /v1/manifests
- GET /v1/manifests/explore
- POST /v1/manifests/{id}/rehydrate
- POST /v1/manifests/export
- POST /v1/ledger/query
- POST /v1/logs/query
- POST /v1/policies/evaluate
- POST /v1/policies/validate
- POST /v1/policies/bundles/{name}/reload
- POST /v1/cache/exact/lookup
- POST /v1/cache/store
- POST /v1/chat/completions
- POST /v1/completions
- POST /v1/embeddings
- GET /v1/models
- GET /v1/reports/dashboard
- GET /v1/conformance/ai
- GET /v1/admin/readiness
- GET /v1/platforms
- GET /v1/platforms/readiness
- GET /v1/platforms/matrix
- GET /healthz
- GET /metrics

## Ideal-state API set

The ideal state includes stored and inline WorkUnit lifecycles, manifest lookup/query/explorer/export/rehydration, full policy including active bundle reload, plugin, conformance, benchmark, ledger query/streaming, redacted operational log querying, adapter management, local S3 object and multipart routes, scheduler routes, report/dashboard APIs, AI gateway conformance, production-readiness checks, platform-readiness checks, and export/import APIs.
