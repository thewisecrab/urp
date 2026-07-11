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
