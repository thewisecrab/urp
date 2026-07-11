# Acceptance Checklist

## Repository

- [x] License present.
- [x] README quickstart works.
- [x] CI runs tests.
- [x] Formatting configured.
- [x] Security policy present.
- [x] Contribution guide present.
- [x] Local service commands documented.
- [x] Hardened deployment artifacts cover Docker Compose, Kubernetes, Terraform, operator, on-prem, and edge targets.
- [x] Static deployment validation covers Kubernetes probes/resources, Terraform providers/backends, Docker Compose stateful services, and operator CRD schema.
- [x] Platform readiness profiles cover local, Kubernetes, AWS, Azure, GCP, on-prem, edge, OpenAI-compatible providers, and CI/CD.
- [x] Live adapter readiness registry exposes credential gates for AWS S3, Postgres manifests, Azure Blob, GCP Storage, and OpenAI-compatible providers.
- [x] Top-level digest-pinned plugin packages cover transforms, classifiers, verifiers, and adapters.
- [x] Rust workspace covers core, chunker, and S3 gateway crate families.

## Core

- [x] WorkUnit schema implemented.
- [x] Manifest schema implemented.
- [x] Policy schema implemented.
- [x] Ledger event schema implemented.
- [x] gRPC protobuf service contracts cover WorkUnit, Plan, Manifest, Policy, Ledger, Cache, AI, Plugin, ObjectGateway, Scheduler, Admin, and Observability APIs.
- [x] OpenAPI and protobuf specs are parsed and checked by admin readiness.
- [x] IDs use stable prefixes.
- [x] JSON serialization tested.
- [x] File-backed WorkUnit create/list/get lifecycle.
- [x] Stored WorkUnit plan and execute by id.
- [x] File-backed Plan create/list/get lifecycle.
- [x] CLI and REST planning persist inspectable plans.
- [x] CLI, REST, service, AI, and mock-adapter planning emit `plan.created` ledger events.
- [x] Go and TypeScript WorkUnit builders.
- [x] Go SDK compatibility package exists under `go/urp`.
- [x] Go and TypeScript stored WorkUnit client helpers.
- [x] Go and TypeScript persisted Plan client helpers.
- [x] Typed SDK manifest and ledger lookup helpers.
- [x] Typed SDK manifest query and export helpers.

## Policy

- [x] Exact default.
- [x] Legal hold override.
- [x] Cross-tenant cache denied.
- [x] Cross-tenant dedupe denied.
- [x] Semantic transforms denied unless allowed.
- [x] Explain output includes matched rules.

## Data path

- [x] Hashing.
- [x] Chunking.
- [x] Chunk store.
- [x] Compression plugin interface.
- [x] Exact rehydration.
- [x] Optimized range rehydration.
- [x] S3-compatible multipart lifecycle with state and per-part integrity verification.
- [x] S3-compatible object tags and metadata are preserved.
- [x] S3-compatible list and delete policy-gate routes exist.
- [x] Restore verifier.
- [x] Manifest write.
- [x] Manifest logical-ref query.
- [x] Redacted manifest export.
- [x] Ledger events.
- [x] Lakehouse compaction recommendation interface.
- [x] Checkpoint delta interface.
- [x] Training sample dedupe interface.

## AI path

- [x] OpenAI-compatible request parsing.
- [x] OpenAI-compatible opt-in HTTP provider adapter.
- [x] Exact cache.
- [x] Embedding requests use WorkUnit, Policy, Plan, Manifest, Ledger, and exact-cache lifecycle.
- [x] Tenant isolation.
- [x] Context dedupe.
- [x] Policy-gated semantic cache.
- [x] Model router.
- [x] Route feedback store.
- [x] Fallback provider.
- [x] Verifier hook.
- [x] Compute manifest.

## Security

- [x] No raw prompts in default logs.
- [x] Manifest redaction mode.
- [x] Plugin descriptor validation.
- [x] Plugin package conformance validates descriptor, source, tests, conformance, examples, and security docs.
- [x] Policy override audited.
- [x] Cache source fingerprint checks.

## Observability

- [x] Metrics endpoint.
- [x] Trace ids.
- [x] JSONL trace spans.
- [x] Ledger query.
- [x] Savings report.
- [x] Local load suite covers object ingest, rehydration latency, AI p95 latency, cache scalability, and manifest write rate.
- [x] Log template extraction.
- [x] Error codes.
- [x] OpenAPI path conformance for local API surface.
- [x] Energy-aware scheduler persistence.

## Services

- [x] Control-plane service starts locally.
- [x] Control-plane service exposes manifest rehydration.
- [x] Control-plane service exposes policy validate/evaluate routes.
- [x] Control-plane service exposes policy bundle management routes.
- [x] Control-plane service exposes plugin registry routes.
- [x] Control-plane service exposes local KMS and backup/restore routes.
- [x] Control-plane service exposes platform profile and readiness routes.
- [x] Control-plane service exposes exact and semantic cache routes.
- [x] Control-plane service exposes savings, trace, route feedback, auth, and adapter conformance routes.
- [x] Control-plane service exposes ledger query and local SSE ledger stream routes.
- [x] AI gateway service starts locally.
- [x] AI gateway service exposes chat completions, text completions, embeddings, and models.
- [x] S3 gateway service starts locally.
- [x] S3 gateway service exposes Put/Get/Head/range routes.
- [x] S3 gateway service exposes ListObjects and DeleteObject policy-gate routes.
- [x] S3 gateway service exposes multipart create/part/complete/abort routes.
- [x] AWS S3 opt-in SigV4 adapter path covers Put/Get/Head/range signing.
- [x] Optional FastAPI app mirrors cache, scheduler, S3, AI, manifest, policy, and WorkUnit routes.
- [x] Worker service starts locally.
- [x] Scheduler service starts locally.
- [x] Service health command and endpoint.

## Advanced Reducers

- [x] Disabled by default.
- [x] Policy gates defined.
- [x] Required verifiers defined.
- [x] Benchmark suites defined.
- [x] Rollback plans defined.
- [x] Conformance test covers reducer specs.

## Release

- [x] Conformance tests.
- [x] Benchmark suite.
- [x] Migration notes.
- [x] Signed release artifacts.
- [x] Runnable live examples produce local evidence for object, AI, adapter, audit, and dashboard use cases.
- [x] White paper maps URP claims to implementation evidence and platform/live-credential boundaries.
- [x] Platform readiness matrix and live credential gates are tested.

Platform-ready note: cloud/provider integrations are represented by adapter contracts, deployment artifacts, readiness profiles, local mocks, and conformance hooks. Live production integrations are opt-in and skipped by default unless credentials and environment-specific configuration are supplied.
